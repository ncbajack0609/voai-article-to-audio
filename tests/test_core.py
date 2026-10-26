from __future__ import annotations

import json
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))

from article_audio.config import ConfigError, load_settings
from article_audio.credentials import resolve_credential
from article_audio.providers import (
    HttpResponse,
    OpenAISpeechAdapter,
    ProviderUncertainError,
    SynthesisRequest,
    VoAIDialogueAdapter,
)
from article_audio.pipeline import run_pipeline
from article_audio.segment import segment_text
from article_audio.source import extract_source
from article_to_audio import run as run_cli


FIXTURE = Path(__file__).parent / "fixtures" / "article.md"


def valid_config(source: str, output: str) -> dict[str, object]:
    return {
        "source": {
            "path": source,
            "format": "markdown",
            "section": {
                "type": "heading",
                "value": "Selected Section",
                "level": 2,
                "include_heading": True,
            },
        },
        "provider": {
            "name": "voai_dialogue",
            "base_url": "https://api.example.test",
            "credential_env": "DEMO_TTS_API_KEY",
        },
        "synthesis": {
            "model": "demo-model",
            "voices": [
                {"name": "voice-a", "style": "neutral"},
                {"name": "voice-b", "style": "warm"},
            ],
            "speed": 1.0,
            "sample_rate": 24000,
            "format": "wav",
        },
        "segmentation": {"min_characters": 35, "target_characters": 55, "max_characters": 80},
        "output": {"directory": output, "mode": "segments", "minimum_bytes": 12},
    }


class ConfigurationAndSourceTests(unittest.TestCase):
    def test_config_overrides_anchor_paths_and_heading_extraction_is_conserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.md"
            source.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(valid_config("article.md", "generated")), encoding="utf-8"
            )

            settings = load_settings(
                config_path,
                overrides={"speed": 0.9, "segment_range": "30:50:90"},
            )
            extracted = extract_source(settings.source)
            segments = segment_text(extracted.text, settings.segmentation)

            self.assertEqual(settings.source.path, source)
            self.assertEqual(settings.output.directory, root / "generated")
            self.assertEqual(settings.synthesis.speed, 0.9)
            self.assertEqual(
                (
                    settings.segmentation.min_characters,
                    settings.segmentation.target_characters,
                    settings.segmentation.max_characters,
                ),
                (30, 50, 90),
            )
            self.assertTrue(extracted.text.startswith("Selected Section"))
            self.assertNotIn("Excluded Section", extracted.text)
            self.assertEqual("".join(segment.text for segment in segments), extracted.text)
            self.assertEqual([segment.index for segment in segments], list(range(1, len(segments) + 1)))
            self.assertTrue(all(segment.spoken_text for segment in segments))

    def test_missing_parameters_and_inline_credentials_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(
                json.dumps({"provider": {"api_key": "do-not-store-this"}}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as raised:
                load_settings(path)

            payload = raised.exception.as_dict()
            self.assertIn("source.path", payload["missing_parameters"])
            self.assertTrue(
                any("credential" in message.lower() for message in payload["validation_errors"])
            )
            self.assertNotIn("do-not-store-this", json.dumps(payload))


class ProviderAdapterTests(unittest.TestCase):
    def test_timeout_is_uncertain_and_cannot_be_treated_as_a_safe_retry(self) -> None:
        def transport(method, url, headers, body, timeout):
            raise TimeoutError("request may have reached the server")

        adapter = VoAIDialogueAdapter(
            base_url="https://api.example.test",
            endpoint=None,
            api_key="private-value",
            timeout_seconds=10,
            options={},
            transport=transport,
        )

        with self.assertRaises(ProviderUncertainError):
            adapter.synthesize(
                SynthesisRequest("Text", "model", "voice", "", 1.0, 24000, "mp3")
            )

    def test_voai_adapter_maps_the_canonical_request_without_leaking_credentials(self) -> None:
        calls: list[tuple[object, ...]] = []

        def transport(method, url, headers, body, timeout):
            calls.append((method, url, headers, json.loads(body), timeout))
            return HttpResponse(200, {"content-type": "audio/wav"}, b"RIFF0000WAVE")

        adapter = VoAIDialogueAdapter(
            base_url="https://api.example.test",
            endpoint=None,
            api_key="private-value",
            timeout_seconds=42,
            options={},
            transport=transport,
        )
        audio = adapter.synthesize(
            SynthesisRequest(
                text="Hello world.",
                model="model-x",
                voice="voice-a",
                style="warm",
                speed=0.9,
                sample_rate=24000,
                format="wav",
            )
        )

        self.assertEqual(audio, b"RIFF0000WAVE")
        method, url, headers, payload, timeout = calls[0]
        self.assertEqual((method, url, timeout), ("POST", "https://api.example.test/TTS/generate-dialogue", 42))
        self.assertEqual(headers["x-api-key"], "private-value")
        self.assertEqual(headers["x-output-format"], "wav")
        self.assertEqual(headers["x-sample-rate"], "24000")
        item = payload["input"]["dialogue"][0]
        self.assertEqual(item["voai_script_text"], "Hello world.")
        self.assertEqual(item["voice"], {"name": "voice-a", "style": "warm", "version": "model-x"})
        self.assertNotIn("private-value", json.dumps(payload))

    def test_openai_adapter_is_a_separate_swappable_payload_mapping(self) -> None:
        payloads: list[dict[str, object]] = []

        def transport(method, url, headers, body, timeout):
            payloads.append(json.loads(body))
            self.assertEqual(headers["Authorization"], "Bearer private-value")
            return HttpResponse(200, {}, b"ID3mock-audio")

        adapter = OpenAISpeechAdapter(
            base_url="https://api.example.test",
            endpoint="/custom/speech",
            api_key="private-value",
            timeout_seconds=10,
            options={},
            transport=transport,
        )
        adapter.synthesize(
            SynthesisRequest("Text", "tts-model", "alloy", "calm", 1.1, 24000, "mp3")
        )

        self.assertEqual(
            payloads,
            [{
                "model": "tts-model",
                "input": "Text",
                "voice": "alloy",
                "speed": 1.1,
                "response_format": "mp3",
                "instructions": "calm",
            }],
        )


class PipelineTests(unittest.TestCase):
    def test_uncertain_request_is_checkpointed_and_not_resent_without_opt_in(self) -> None:
        class UncertainProvider:
            def __init__(self) -> None:
                self.calls = 0

            def synthesize(self, request: SynthesisRequest) -> bytes:
                self.calls += 1
                raise ProviderUncertainError("timeout")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "article.md").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps(valid_config("article.md", "generated")), encoding="utf-8")
            settings = load_settings(config_path)
            provider = UncertainProvider()

            with self.assertRaisesRegex(Exception, "uncertain"):
                run_pipeline(settings, provider)
            with self.assertRaisesRegex(Exception, "retry_uncertain"):
                run_pipeline(settings, provider)

            self.assertEqual(provider.calls, 1)
            manifest = json.loads((root / "generated" / "segments-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["segments"][0]["status"], "uncertain")

    def test_mock_provider_fixture_run_writes_auditable_multi_voice_artifacts(self) -> None:
        class RecordingProvider:
            def __init__(self) -> None:
                self.requests: list[SynthesisRequest] = []

            def synthesize(self, request: SynthesisRequest) -> bytes:
                self.requests.append(request)
                return b"RIFF0000WAVE" + request.text.encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.md"
            source.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(valid_config("article.md", "generated")), encoding="utf-8"
            )
            settings = load_settings(config_path)
            provider = RecordingProvider()

            result = run_pipeline(settings, provider)

            self.assertGreater(len(result.segment_files), 1)
            self.assertTrue(all(path.is_file() for path in result.segment_files))
            self.assertIsNone(result.combined_file)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["segments"]), len(provider.requests))
            self.assertEqual(
                [request.voice for request in provider.requests],
                ["voice-a" if index % 2 == 0 else "voice-b" for index in range(len(provider.requests))],
            )
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["provider"], "voai_dialogue")
            self.assertEqual(report["segment_count"], len(provider.requests))
            serialized = "".join(
                path.read_text(encoding="utf-8")
                for path in (result.manifest_path, result.report_path, result.normalized_source_path)
            )
            self.assertNotIn("private-value", serialized)


class CredentialAndCliTests(unittest.TestCase):
    def test_credential_file_takes_precedence_and_unsafe_posix_permissions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            credential = Path(directory) / "credential.txt"
            credential.write_text("file-value\n", encoding="utf-8")
            if os.name == "posix":
                credential.chmod(0o600)
            self.assertEqual(
                resolve_credential(
                    environment_name="DEMO_TTS_API_KEY",
                    credential_file=credential,
                    environ={"DEMO_TTS_API_KEY": "environment-value"},
                ),
                "file-value",
            )
            if os.name == "posix":
                credential.chmod(0o644)
                with self.assertRaises(ConfigError):
                    resolve_credential(
                        environment_name="DEMO_TTS_API_KEY",
                        credential_file=credential,
                        environ={},
                    )

    def test_validate_only_needs_no_credential_and_prints_a_machine_readable_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "article.md"
            source.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(valid_config("article.md", "generated")), encoding="utf-8"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = run_cli(
                [
                    "--config",
                    str(config_path),
                    "--validate-only",
                    "--speed",
                    "0.95",
                    "--voice",
                    "voice-z:calm",
                ],
                environ={},
                stdout=stdout,
                stderr=stderr,
            )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(payload["status"], "valid")
            self.assertEqual(payload["speed"], 0.95)
            self.assertEqual(payload["voices"], [{"name": "voice-z", "style": "calm"}])
            self.assertGreater(payload["segment_count"], 1)
            self.assertFalse((root / "generated").exists())

    def test_invalid_noninteractive_config_prints_missing_parameters_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = run_cli(
                ["--config", str(config_path), "--validate-only"],
                environ={},
                stdout=stdout,
                stderr=stderr,
            )

            payload = json.loads(stderr.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("source.path", payload["missing_parameters"])
            self.assertIn("provider.name", payload["missing_parameters"])
            self.assertIn("source.section.type", payload["missing_parameters"])
            self.assertIn("synthesis.speed", payload["missing_parameters"])
            self.assertIn("synthesis.sample_rate", payload["missing_parameters"])
            self.assertIn("synthesis.format", payload["missing_parameters"])
            self.assertIn("segmentation.min_characters", payload["missing_parameters"])
            self.assertIn("segmentation.target_characters", payload["missing_parameters"])
            self.assertIn("segmentation.max_characters", payload["missing_parameters"])
            self.assertIn("output.mode", payload["missing_parameters"])

    def test_invalid_numeric_decisions_are_not_silently_replaced_by_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = valid_config(str(FIXTURE), "generated")
            synthesis = config["synthesis"]
            segmentation = config["segmentation"]
            assert isinstance(synthesis, dict)
            assert isinstance(segmentation, dict)
            synthesis["speed"] = "fast"
            synthesis["sample_rate"] = 24000.0
            segmentation["target_characters"] = "55"
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(ConfigError) as raised:
                load_settings(config_path)

            errors = raised.exception.as_dict()["validation_errors"]
            self.assertIn("synthesis.speed must be a number", errors)
            self.assertIn("synthesis.sample_rate must be an integer", errors)
            self.assertIn("segmentation.target_characters must be an integer", errors)


if __name__ == "__main__":
    unittest.main()
