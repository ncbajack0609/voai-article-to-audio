"""Provider-independent extraction, segmentation, synthesis, and artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .config import Settings
from .providers import ProviderUncertainError, SynthesisRequest, TTSProvider
from .segment import Segment, segment_text
from .source import extract_source


class PipelineError(RuntimeError):
    """A safe pipeline or media validation failure."""


@dataclass(frozen=True)
class RunResult:
    normalized_source_path: Path
    manifest_path: Path
    report_path: Path
    segment_files: tuple[Path, ...]
    combined_file: Path | None


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _audio_signature_valid(data: bytes, audio_format: str, minimum_bytes: int) -> bool:
    if len(data) < minimum_bytes:
        return False
    normalized = audio_format.casefold()
    if normalized == "wav":
        return data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    if normalized == "mp3":
        return data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    if normalized == "ogg":
        return data.startswith(b"OggS")
    if normalized == "flac":
        return data.startswith(b"fLaC")
    return True


def _validate_audio_file(path: Path, audio_format: str, minimum_bytes: int) -> None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PipelineError(f"cannot read generated audio '{path.name}'") from exc
    if not _audio_signature_valid(data, audio_format, minimum_bytes):
        raise PipelineError(f"generated audio '{path.name}' has an invalid signature or is too small")


def _request_digest(request: SynthesisRequest) -> str:
    payload = json.dumps(asdict(request), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_completed(path: Path) -> dict[int, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = document.get("segments") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        return {}
    return {
        int(row["index"]): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("index"), int)
    }


def _manifest_document(
    settings: Settings,
    segments: Sequence[Segment],
    rows: dict[int, dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": settings.provider.name,
        "model": settings.synthesis.model,
        "audio": {
            "format": settings.synthesis.format,
            "sample_rate": settings.synthesis.sample_rate,
            "speed": settings.synthesis.speed,
        },
        "segment_range": asdict(settings.segmentation),
        "segments": [rows[segment.index] for segment in segments if segment.index in rows],
    }


def _assemble(
    files: Sequence[Path],
    output_path: Path,
    *,
    sample_rate: int,
    audio_format: str,
    minimum_bytes: int,
) -> None:
    if len(files) == 1:
        shutil.copyfile(files[0], output_path)
        return
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise PipelineError(
            "single-file output requires ffmpeg; use output.mode=segments or make ffmpeg available"
        )
    list_path = output_path.with_suffix(".concat.txt")
    lines = []
    for path in files:
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    temporary = output_path.with_suffix(output_path.suffix + ".tmp" + output_path.suffix)
    command = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-ar",
        str(sample_rate),
        str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=300)
        _validate_audio_file(temporary, audio_format, minimum_bytes)
        os.replace(temporary, output_path)
    except (OSError, subprocess.SubprocessError, PipelineError) as exc:
        temporary.unlink(missing_ok=True)
        raise PipelineError("ffmpeg could not assemble the final audio file") from exc
    finally:
        list_path.unlink(missing_ok=True)


def run_pipeline(
    settings: Settings,
    provider: TTSProvider,
    *,
    retry_uncertain: bool = False,
) -> RunResult:
    """Run a deterministic, resumable article-to-audio conversion."""

    extracted = extract_source(settings.source)
    segments = segment_text(extracted.text, settings.segmentation)
    if not segments:
        raise PipelineError("selected source produced no speech segments")

    output = settings.output.directory
    segment_directory = output / "segments"
    output.mkdir(parents=True, exist_ok=True)
    segment_directory.mkdir(parents=True, exist_ok=True)
    normalized_path = output / "normalized-source.json"
    manifest_path = output / "segments-manifest.json"
    report_path = output / "run-report.json"
    _atomic_json(
        normalized_path,
        {
            "schema_version": 1,
            "source_name": extracted.source_name,
            "selector": extracted.selector,
            "source_line_start": extracted.source_line_start,
            "source_line_end": extracted.source_line_end,
            "sha256": hashlib.sha256(extracted.text.encode("utf-8")).hexdigest(),
            "text": extracted.text,
        },
    )

    prior = _load_completed(manifest_path)
    rows: dict[int, dict[str, object]] = {}
    files: list[Path] = []
    for index, segment in enumerate(segments):
        voice = settings.synthesis.voices[index % len(settings.synthesis.voices)]
        request = SynthesisRequest(
            text=segment.spoken_text,
            model=settings.synthesis.model,
            voice=voice.name,
            style=voice.style,
            speed=settings.synthesis.speed,
            sample_rate=settings.synthesis.sample_rate,
            format=settings.synthesis.format,
            audio_config=settings.synthesis.audio_config,
        )
        digest = _request_digest(request)
        filename = f"segment-{segment.index:04d}.{settings.synthesis.format}"
        path = segment_directory / filename
        previous = prior.get(segment.index, {})
        if (
            previous.get("status") == "uncertain"
            and previous.get("request_sha256") == digest
            and not retry_uncertain
        ):
            raise PipelineError(
                f"segment {segment.index} has an uncertain checkpoint; inspect provider usage "
                "before retrying with retry_uncertain=True"
            )
        if (
            previous.get("status") == "complete"
            and previous.get("request_sha256") == digest
            and path.exists()
        ):
            try:
                _validate_audio_file(path, settings.synthesis.format, settings.output.minimum_bytes)
            except PipelineError:
                pass
            else:
                rows[segment.index] = previous
                files.append(path)
                continue

        row = {
            **asdict(segment),
            "voice": voice.name,
            "style": voice.style,
            "file": f"segments/{filename}",
            "request_sha256": digest,
            "status": "pending",
        }
        rows[segment.index] = row
        _atomic_json(manifest_path, _manifest_document(settings, segments, rows))
        try:
            audio = provider.synthesize(request)
        except ProviderUncertainError as exc:
            row["status"] = "uncertain"
            row["error"] = "provider delivery and quota usage are uncertain"
            _atomic_json(manifest_path, _manifest_document(settings, segments, rows))
            raise PipelineError(
                f"segment {segment.index} result is uncertain; inspect provider usage before retrying"
            ) from exc
        if not _audio_signature_valid(audio, settings.synthesis.format, settings.output.minimum_bytes):
            row["status"] = "invalid"
            _atomic_json(manifest_path, _manifest_document(settings, segments, rows))
            raise PipelineError(f"provider returned invalid audio for segment {segment.index}")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(audio)
        os.replace(temporary, path)
        row["status"] = "complete"
        row["bytes"] = path.stat().st_size
        _atomic_json(manifest_path, _manifest_document(settings, segments, rows))
        files.append(path)

    combined: Path | None = None
    if settings.output.mode in {"single", "both"}:
        combined = output / f"article-audio.{settings.synthesis.format}"
        _assemble(
            files,
            combined,
            sample_rate=settings.synthesis.sample_rate,
            audio_format=settings.synthesis.format,
            minimum_bytes=settings.output.minimum_bytes,
        )
    _atomic_json(
        report_path,
        {
            "schema_version": 1,
            "status": "complete",
            "provider": settings.provider.name,
            "model": settings.synthesis.model,
            "segment_count": len(segments),
            "output_mode": settings.output.mode,
            "combined_file": combined.name if combined else None,
            "manifest": manifest_path.name,
            "normalized_source": normalized_path.name,
        },
    )
    return RunResult(normalized_path, manifest_path, report_path, tuple(files), combined)
