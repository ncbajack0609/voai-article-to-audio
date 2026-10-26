#!/usr/bin/env python3
"""Portable CLI for the Article-to-Audio skill package."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence, TextIO

from article_audio.config import ConfigError, load_settings
from article_audio.credentials import resolve_credential
from article_audio.pipeline import PipelineError, run_pipeline
from article_audio.providers import ProviderError, build_provider
from article_audio.segment import readable_count, segment_text
from article_audio.source import extract_source


def _section(value: str) -> dict[str, object]:
    if value == "all":
        return {"type": "all"}
    if value.startswith("heading:"):
        title = value.removeprefix("heading:").strip()
        return {"type": "heading", "value": title, "include_heading": True}
    if value.startswith("markers:") and "::" in value:
        start, end = value.removeprefix("markers:").split("::", 1)
        return {"type": "markers", "value": start, "end": end}
    if value.startswith("lines:"):
        parts = value.removeprefix("lines:").split(":")
        if len(parts) == 2:
            try:
                return {"type": "line_range", "start_line": int(parts[0]), "end_line": int(parts[1])}
            except ValueError:
                pass
    raise argparse.ArgumentTypeError(
        "section must be all, heading:TITLE, markers:START::END, or lines:START:END"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a selected article range through a TTS API.")
    parser.add_argument("--config", type=Path, required=True, help="JSON configuration file")
    parser.add_argument("--validate-only", action="store_true", help="validate and plan without credentials, network, or output")
    parser.add_argument("--credential-file", type=Path, help="explicit protected credential file")
    parser.add_argument("--source", help="source path, or - for standard input")
    parser.add_argument("--section", type=_section, help="all, heading:TITLE, markers:START::END, or lines:START:END")
    parser.add_argument("--provider", choices=("voai_dialogue", "openai_speech"))
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--voice", action="append", dest="voices", metavar="NAME[:STYLE]")
    parser.add_argument("--speed", type=float)
    parser.add_argument("--sample-rate", type=int)
    parser.add_argument("--format")
    parser.add_argument("--segment-range", metavar="MIN:TARGET:MAX")
    parser.add_argument("--output-dir")
    parser.add_argument("--output-mode", choices=("segments", "single", "both"))
    parser.add_argument(
        "--retry-uncertain",
        action="store_true",
        help="resend an uncertain checkpoint only after provider usage was reviewed",
    )
    return parser


def _json_line(stream: TextIO, payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=stream)


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    environment = os.environ if environ is None else environ
    args = build_parser().parse_args(argv)
    overrides = {
        key: value
        for key, value in {
            "source": args.source,
            "section": args.section,
            "provider": args.provider,
            "base_url": args.base_url,
            "model": args.model,
            "voices": args.voices,
            "speed": args.speed,
            "sample_rate": args.sample_rate,
            "format": args.format,
            "segment_range": args.segment_range,
            "output_dir": args.output_dir,
            "output_mode": args.output_mode,
        }.items()
        if value is not None
    }
    try:
        settings = load_settings(args.config, overrides=overrides)
        if args.validate_only:
            extracted = extract_source(settings.source)
            segments = segment_text(extracted.text, settings.segmentation)
            _json_line(
                out,
                {
                    "status": "valid",
                    "provider": settings.provider.name,
                    "model": settings.synthesis.model,
                    "voices": [asdict(voice) for voice in settings.synthesis.voices],
                    "speed": settings.synthesis.speed,
                    "sample_rate": settings.synthesis.sample_rate,
                    "format": settings.synthesis.format,
                    "output_mode": settings.output.mode,
                    "source_characters": readable_count(extracted.text),
                    "segment_count": len(segments),
                },
            )
            return 0
        api_key = resolve_credential(
            environment_name=settings.provider.credential_env,
            credential_file=args.credential_file,
            environ=environment,
        )
        provider = build_provider(settings.provider, api_key)
        result = run_pipeline(settings, provider, retry_uncertain=args.retry_uncertain)
        del api_key
        _json_line(
            out,
            {
                "status": "complete",
                "output_directory": str(settings.output.directory),
                "segment_files": [str(path) for path in result.segment_files],
                "combined_file": str(result.combined_file) if result.combined_file else None,
                "manifest": str(result.manifest_path),
                "normalized_source": str(result.normalized_source_path),
                "report": str(result.report_path),
            },
        )
        return 0
    except ConfigError as exc:
        _json_line(err, exc.as_dict())
        return 2
    except (ProviderError, PipelineError, OSError) as exc:
        _json_line(
            err,
            {
                "status": "execution_error",
                "missing_parameters": [],
                "validation_errors": [str(exc)],
            },
        )
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
