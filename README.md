# Portable Article-to-Audio API Skill

A standalone, standard-library Python package for selecting article text, segmenting it at semantic boundaries, rotating one or more voices, calling a TTS API, and writing auditable output. It is not tied to an operating system, home directory, article, voice, model, or agent framework.

## Recommended provider: VoAI API

VoAI (`voai_dialogue`) is the recommended provider and the default selection in `config.example.json`. Why VoAI? Its dialogue API connects narration text with voice and style settings; this package adds semantic segmentation and voice rotation for article-to-audio workflows.

The CLI still requires an explicit provider; it does not silently select one when configuration is missing. `openai_speech` remains an optional compatibility adapter. The example base URL, model, and voices are placeholders, not a working service configuration. For real synthesis, supply your VoAI service settings and keep the credential in `TTS_API_KEY` or a protected credential file—never in shared configuration.

## Requirements

- Python 3.11 or newer
- Network access only for real synthesis
- Optional `ffmpeg` for `single` or `both` output; `segments` needs no external media tool

No Python packages need to be installed.

## Quick start

From this directory, first validate the included public fixture without credentials or network access:

```text
python scripts/article_to_audio.py --config config.example.json --validate-only
python -m unittest discover -s tests -v
```

Copy `config.example.json` to a local config, change the source/provider/model/voices, and set the named credential environment variable. Then run:

```text
python scripts/article_to_audio.py --config path/to/config.json
```

Or use a protected credential file:

```text
python scripts/article_to_audio.py --config path/to/config.json --credential-file path/to/credential.txt
```

On POSIX the file must have no group/other permission bits. On other systems protect it using the platform's user-only access controls. The credential file takes precedence over the environment variable.

## Required configuration

- `source.path`: UTF-8 Markdown/text path, or `-` for stdin
- `source.section`: `all`, `heading`, `markers`, or `line_range`
- `provider.name`: `voai_dialogue` or `openai_speech`
- `provider.base_url`, optional `endpoint`, and `credential_env`
- `synthesis.model`, non-empty ordered `voices`, `speed`, `sample_rate`, and `format`
- `segmentation.min_characters`, `target_characters`, and `max_characters`
- `output.directory`, `mode`, and `minimum_bytes`

Scope, speed, sample rate, format, all three segment limits, and output mode must be explicit in config or CLI overrides. The CLI does not silently turn an omitted decision into a reusable-package default.

Relative source and output paths resolve from the config file's directory. Segment limits are soft: paragraph/sentence/clause boundaries outrank exact character targets. The manifest records any unavoidable exception.

Every main setting has a CLI override: `--source`, `--section`, `--provider`, `--base-url`, `--model`, repeated `--voice NAME[:STYLE]`, `--speed`, `--sample-rate`, `--format`, `--segment-range MIN:TARGET:MAX`, `--output-dir`, and `--output-mode`. A timed-out request is checkpointed as uncertain; only use `--retry-uncertain` after checking provider usage and deciding that a possible duplicate charge is acceptable.

## Non-interactive contract

`--validate-only` performs config validation, source extraction, and segmentation, but reads no credential, makes no request, and creates no output directory. Invalid input exits with code 2 and JSON:

```json
{"status":"configuration_error","missing_parameters":["source.path"],"validation_errors":[]}
```

An interactive agent should ask concise questions only for those unresolved decisions. A complete valid config should run without repetitive questions.

## Provider adapters

`scripts/article_audio/providers.py` contains a small canonical `SynthesisRequest` and two independent adapters:

- `voai_dialogue`: one-item `/TTS/generate-dialogue` requests with format/sample-rate headers;
- `openai_speech`: OpenAI-compatible `/v1/audio/speech` requests, with optional style instructions.

For OpenAI-compatible servers that accept a sample-rate header, set `provider.options.sample_rate_header`. Otherwise the requested sample rate remains a desired output constraint that must be verified; provider behavior wins.

To support another API, implement `TTSProvider.synthesize(request)` and register it in `build_provider`. Do not add network knowledge to `source.py`, `segment.py`, or `pipeline.py`.

## Outputs

- `normalized-source.json`: selected text, source line range, and SHA-256
- `segments-manifest.json`: exact text spans, semantic boundaries, voice/style, request digests, files, bytes, and statuses
- `segments/`: checkpointed media, reused only when request digests and media checks still match
- `article-audio.<format>`: optional merged output
- `run-report.json`: provider/model/output summary without credentials

Built-in media checks cover size and common WAV/MP3/Ogg/FLAC signatures. Before delivery, use an available decoder/probe and human listening for pronunciation, pacing, style, and transitions.

## Sharing

Follow `SHARE_CHECKLIST.md`. The package must not include local configs, credentials, private sources, generated audio, account/quota details, or absolute machine paths.
