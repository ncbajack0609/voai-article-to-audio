"""Offline contract tests; fake transport never contacts VoAI."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from article_audio.config import ConfigError, load_settings
from article_audio.providers import HttpResponse, SynthesisRequest, build_provider
from article_audio.pipeline import run_pipeline


class VoAIContractTests(unittest.TestCase):
    def test_validate_only_reports_native_audio_settings_without_credentials(self):
        import io
        from article_to_audio import run
        out, err = io.StringIO(), io.StringIO()
        code = run(["--config", str(ROOT / "config.example.json"), "--validate-only"],
                   environ={}, stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(json.loads(out.getvalue()).get("audio_config"),
                         {"pitch_shift": 0, "breath_pause": 0})

    def test_public_example_uses_documented_voai_values_and_tiny_source(self):
        from article_audio.source import extract_source
        from article_audio.segment import segment_text
        settings = load_settings(ROOT / "config.example.json")
        self.assertEqual(settings.provider.base_url, "https://connect.voai.ai")
        self.assertEqual(settings.provider.credential_env, "VOAI_API_KEY")
        self.assertEqual(settings.synthesis.model, "Sota+")
        self.assertEqual([(v.name, v.style) for v in settings.synthesis.voices], [("佑希", "聊天")])
        source = extract_source(settings.source)
        self.assertLess(len(source.text), 50)
        self.assertEqual(len(segment_text(source.text, settings.segmentation)), 1)

    def test_compatibility_adapter_rejects_voai_only_audio_config(self):
        raw = json.loads((ROOT / "config.example.json").read_text())
        raw["provider"]["name"] = "openai_speech"
        raw["synthesis"]["audio_config"] = {"pitch_shift": 1}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw))
            with self.assertRaises(ConfigError):
                load_settings(path)

    def test_voai_rejects_overlong_dialogue_without_transport(self):
        settings = load_settings(ROOT / "config.example.json")
        calls = []
        def transport(*args):
            calls.append(args)
            return HttpResponse(200, {}, b"ID3fake")
        provider = build_provider(settings.provider, "offline-fake-key", transport=transport)
        from article_audio.providers import ProviderError
        with self.assertRaisesRegex(ProviderError, "1000"):
            provider.synthesize(SynthesisRequest("字" * 1001, "Sota+", "佑希", "聊天", 1, 24000, "mp3"))
        self.assertEqual(calls, [])

    def test_voai_rejects_unsupported_settings_before_network(self):
        cases = [
            {"speed": 1.6}, {"speed": float("nan")},
            {"sample_rate": 44100}, {"sample_rate": 22050},
            {"format": "ogg"}, {"format": "pcm"},
            {"audio_config": {"pitch_shift": 6}},
            {"audio_config": {"breath_pause": -1}},
            {"audio_config": {"breath_pause": True}},
            {"audio_config": {"style_weight": 0.5}},
            {"audio_config": {"speed": 1}},
            {"audio_config": {"unknown": 0}},
            {"audio_config": []},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for changes in cases:
                with self.subTest(changes=changes):
                    raw = json.loads((ROOT / "config.example.json").read_text())
                    raw["synthesis"]["model"] = "Sota+"
                    raw["synthesis"].update(changes)
                    path.write_text(json.dumps(raw), encoding="utf-8")
                    with self.assertRaises(ConfigError):
                        load_settings(path)

    def test_native_audio_config_reaches_dialogue_and_changes_resume_digest(self):
        raw = json.loads((ROOT / "config.example.json").read_text())
        raw["source"] = {"path": "tiny.txt", "section": {"type": "all"}}
        raw["synthesis"]["audio_config"] = {"pitch_shift": 1, "breath_pause": 0.2}
        calls = []

        def transport(method, url, headers, body, timeout):
            calls.append((url, headers, json.loads(body)))
            return HttpResponse(200, {}, b"ID3" + b"0" * 200)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tiny.txt").write_text("你好，這是語音測試。", encoding="utf-8")
            path = root / "config.json"
            for pitch in (1, 2):
                raw["synthesis"]["audio_config"]["pitch_shift"] = pitch
                path.write_text(json.dumps(raw), encoding="utf-8")
                settings = load_settings(path)
                run_pipeline(settings, build_provider(settings.provider, "offline-fake-key", transport=transport))
        self.assertEqual(len(calls), 2, "changed audio settings must not reuse old audio")
        item = calls[-1][2]["input"]["dialogue"][0]
        self.assertEqual(item["audio_config"], {"speed": 1.0, "pitch_shift": 2, "breath_pause": 0.2})
        self.assertNotIn("offline-fake-key", json.dumps(calls[-1][2]))
