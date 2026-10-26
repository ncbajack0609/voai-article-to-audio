"""Configuration loading, validation, and CLI override handling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


class ConfigError(ValueError):
    """A safe, machine-readable configuration failure."""

    def __init__(
        self,
        *,
        missing_parameters: Sequence[str] = (),
        validation_errors: Sequence[str] = (),
    ) -> None:
        self.missing_parameters = tuple(dict.fromkeys(missing_parameters))
        self.validation_errors = tuple(validation_errors)
        super().__init__("article-to-audio configuration is incomplete or invalid")

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "configuration_error",
            "missing_parameters": list(self.missing_parameters),
            "validation_errors": list(self.validation_errors),
        }


@dataclass(frozen=True)
class SectionSelector:
    type: str = "all"
    value: str | None = None
    end: str | None = None
    level: int | None = None
    include_heading: bool = False
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True)
class SourceConfig:
    path: Path | None
    format: str
    section: SectionSelector
    include_code: bool = False


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    endpoint: str | None
    credential_env: str
    timeout_seconds: float
    options: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Voice:
    name: str
    style: str = ""


@dataclass(frozen=True)
class SynthesisConfig:
    model: str
    voices: tuple[Voice, ...]
    speed: float
    sample_rate: int
    format: str


@dataclass(frozen=True)
class SegmentationConfig:
    min_characters: int
    target_characters: int
    max_characters: int


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    mode: str
    minimum_bytes: int


@dataclass(frozen=True)
class Settings:
    source: SourceConfig
    provider: ProviderConfig
    synthesis: SynthesisConfig
    segmentation: SegmentationConfig
    output: OutputConfig


_SECRET_KEYS = {"apikey", "token", "password", "secret", "authorization"}
_SUPPORTED_PROVIDERS = {"voai_dialogue", "openai_speech"}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_inline_secret(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = "".join(character for character in str(key).casefold() if character.isalnum())
            if normalized in _SECRET_KEYS:
                return True
            if _has_inline_secret(nested):
                return True
    elif isinstance(value, list):
        return any(_has_inline_secret(item) for item in value)
    return False


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _integer(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def _parse_section(value: object) -> SectionSelector:
    section = _mapping(value)
    return SectionSelector(
        type=_string(section.get("type")) or "all",
        value=_string(section.get("value")) or None,
        end=_string(section.get("end")) or None,
        level=_integer(section.get("level"), 0) or None,
        include_heading=section.get("include_heading", False) is True,
        start_line=_integer(section.get("start_line"), 0) or None,
        end_line=_integer(section.get("end_line"), 0) or None,
    )


def _parse_segment_range(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        parsed = tuple(int(part) for part in parts)
    except ValueError:
        return None
    return parsed if len(parsed) == 3 else None


def _parse_voice_overrides(value: object) -> list[dict[str, str]] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return None
    result: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, Voice):
            result.append({"name": item.name, "style": item.style})
        elif isinstance(item, str):
            name, separator, style = item.partition(":")
            result.append({"name": name.strip(), "style": style.strip() if separator else ""})
        elif isinstance(item, dict):
            result.append({"name": _string(item.get("name")), "style": _string(item.get("style"))})
        else:
            return None
    return result


def load_settings(
    path: Path | str,
    *,
    overrides: Mapping[str, object] | None = None,
) -> Settings:
    """Load JSON settings and apply explicit CLI-style overrides."""

    config_path = Path(path).expanduser()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(validation_errors=[f"cannot read configuration file: {exc.strerror}"]) from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            validation_errors=[f"configuration is not valid JSON at line {exc.lineno}, column {exc.colno}"]
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(validation_errors=["configuration root must be an object"])

    override = dict(overrides or {})
    source_raw = dict(_mapping(raw.get("source")))
    provider_raw = dict(_mapping(raw.get("provider")))
    synthesis_raw = dict(_mapping(raw.get("synthesis")))
    segmentation_raw = dict(_mapping(raw.get("segmentation")))
    output_raw = dict(_mapping(raw.get("output")))

    simple_overrides = {
        "source": (source_raw, "path"),
        "section": (source_raw, "section"),
        "provider": (provider_raw, "name"),
        "base_url": (provider_raw, "base_url"),
        "model": (synthesis_raw, "model"),
        "speed": (synthesis_raw, "speed"),
        "sample_rate": (synthesis_raw, "sample_rate"),
        "format": (synthesis_raw, "format"),
        "output_dir": (output_raw, "directory"),
        "output_mode": (output_raw, "mode"),
    }
    for key, (target, target_key) in simple_overrides.items():
        if key in override and override[key] is not None:
            target[target_key] = override[key]
    voice_override = _parse_voice_overrides(override.get("voices"))
    if voice_override is not None:
        synthesis_raw["voices"] = voice_override
    range_override = _parse_segment_range(override.get("segment_range"))
    invalid_range_override = "segment_range" in override and override.get("segment_range") is not None and range_override is None
    if range_override is not None:
        segmentation_raw["min_characters"], segmentation_raw["target_characters"], segmentation_raw["max_characters"] = range_override

    missing: list[str] = []
    errors: list[str] = []
    if _has_inline_secret(raw):
        errors.append("inline credentials are forbidden; use credential_env or --credential-file")
    if invalid_range_override:
        errors.append("segment range override must be MIN:TARGET:MAX")

    section_raw = _mapping(source_raw.get("section"))
    required_explicit = (
        ("source.section.type", "type" in section_raw),
        ("synthesis.speed", "speed" in synthesis_raw),
        ("synthesis.sample_rate", "sample_rate" in synthesis_raw),
        ("synthesis.format", "format" in synthesis_raw),
        ("segmentation.min_characters", "min_characters" in segmentation_raw),
        ("segmentation.target_characters", "target_characters" in segmentation_raw),
        ("segmentation.max_characters", "max_characters" in segmentation_raw),
        ("output.mode", "mode" in output_raw),
    )
    missing.extend(key for key, present in required_explicit if not present)

    source_value = _string(source_raw.get("path"))
    if not source_value:
        missing.append("source.path")
        source_path: Path | None = None
    elif source_value == "-":
        source_path = Path("-")
    else:
        source_path = Path(source_value).expanduser()
        if not source_path.is_absolute():
            source_path = config_path.parent / source_path

    provider_name = _string(provider_raw.get("name"))
    base_url = _string(provider_raw.get("base_url"))
    model = _string(synthesis_raw.get("model"))
    output_value = _string(output_raw.get("directory"))
    for key, value in (
        ("provider.name", provider_name),
        ("provider.base_url", base_url),
        ("synthesis.model", model),
        ("output.directory", output_value),
    ):
        if not value:
            missing.append(key)

    voices_raw = synthesis_raw.get("voices")
    voices: list[Voice] = []
    if not isinstance(voices_raw, list) or not voices_raw:
        missing.append("synthesis.voices")
    else:
        for index, value in enumerate(voices_raw):
            voice = _mapping(value)
            name = _string(voice.get("name"))
            if not name:
                errors.append(f"synthesis.voices[{index}].name must be a non-empty string")
            else:
                voices.append(Voice(name=name, style=_string(voice.get("style"))))

    section = _parse_section(source_raw.get("section", {}))
    if section.type not in {"all", "heading", "markers", "line_range"}:
        errors.append("source.section.type must be all, heading, markers, or line_range")
    if section.type == "heading" and not section.value:
        missing.append("source.section.value")
    if section.type == "markers" and (not section.value or not section.end):
        missing.extend(key for key, value in (("source.section.value", section.value), ("source.section.end", section.end)) if not value)
    if section.type == "line_range" and (section.start_line is None or section.end_line is None):
        missing.append("source.section.start_line/end_line")

    if provider_name and provider_name not in _SUPPORTED_PROVIDERS:
        errors.append("provider.name must be voai_dialogue or openai_speech")
    if base_url:
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"https", "http"} or not parsed_url.netloc:
            errors.append("provider.base_url must be an absolute HTTP(S) URL")
        elif parsed_url.scheme != "https" and parsed_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            errors.append("provider.base_url must use HTTPS except for localhost testing")

    speed_value = synthesis_raw.get("speed")
    sample_rate_value = synthesis_raw.get("sample_rate")
    speed = _number(speed_value, 1.0)
    sample_rate = _integer(sample_rate_value, 24000)
    audio_format = _string(synthesis_raw.get("format")) or "mp3"
    minimum_value = segmentation_raw.get("min_characters")
    target_value = segmentation_raw.get("target_characters")
    maximum_value = segmentation_raw.get("max_characters")
    minimum = _integer(minimum_value, 80)
    target = _integer(target_value, 160)
    maximum = _integer(maximum_value, 240)
    if "speed" in synthesis_raw and (
        not isinstance(speed_value, (int, float)) or isinstance(speed_value, bool)
    ):
        errors.append("synthesis.speed must be a number")
    if "sample_rate" in synthesis_raw and (
        not isinstance(sample_rate_value, int) or isinstance(sample_rate_value, bool)
    ):
        errors.append("synthesis.sample_rate must be an integer")
    for key, value in (
        ("segmentation.min_characters", minimum_value),
        ("segmentation.target_characters", target_value),
        ("segmentation.max_characters", maximum_value),
    ):
        if key.rsplit(".", 1)[1] in segmentation_raw and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            errors.append(f"{key} must be an integer")
    if speed <= 0:
        errors.append("synthesis.speed must be positive")
    if sample_rate <= 0:
        errors.append("synthesis.sample_rate must be a positive integer")
    if not 0 < minimum <= target <= maximum:
        errors.append("segmentation range must satisfy 0 < min <= target <= max")

    mode = _string(output_raw.get("mode")) or "segments"
    if mode not in {"segments", "single", "both"}:
        errors.append("output.mode must be segments, single, or both")
    minimum_bytes = _integer(output_raw.get("minimum_bytes"), 128)
    if minimum_bytes <= 0:
        errors.append("output.minimum_bytes must be a positive integer")

    if missing or errors:
        raise ConfigError(missing_parameters=missing, validation_errors=errors)

    output_path = Path(output_value).expanduser()
    if not output_path.is_absolute():
        output_path = config_path.parent / output_path
    return Settings(
        source=SourceConfig(
            path=source_path,
            format=_string(source_raw.get("format")) or "auto",
            section=section,
            include_code=source_raw.get("include_code", False) is True,
        ),
        provider=ProviderConfig(
            name=provider_name,
            base_url=base_url.rstrip("/"),
            endpoint=_string(provider_raw.get("endpoint")) or None,
            credential_env=_string(provider_raw.get("credential_env")) or "TTS_API_KEY",
            timeout_seconds=_number(provider_raw.get("timeout_seconds"), 180.0),
            options=dict(_mapping(provider_raw.get("options"))),
        ),
        synthesis=SynthesisConfig(
            model=model,
            voices=tuple(voices),
            speed=speed,
            sample_rate=sample_rate,
            format=audio_format.casefold(),
        ),
        segmentation=SegmentationConfig(minimum, target, maximum),
        output=OutputConfig(output_path, mode, minimum_bytes),
    )
