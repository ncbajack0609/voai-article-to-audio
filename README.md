# Article to Audio — powered by VoAI API

[繁體中文](README.zh-TW.md)

Turn articles, listening scripts, and selected chapters into a repeatable audio-production workflow. This portable Python skill selects your text, splits it at semantic boundaries, rotates configured voices, and saves audio with a traceable manifest.

**Start with VoAI API.** `voai_dialogue` is the recommended provider and the default selection in `config.example.json`. The included adapter connects each text segment to VoAI's dialogue endpoint with voice, style, model/version, and speed settings. The package handles segmentation, checkpoints, and output organization around those requests.

## Why use it?

- **Read exactly what you choose:** a whole document, a heading, a marker-delimited passage, or a line range.
- **Keep control of narration:** use one voice throughout or rotate an ordered list of voices across segments.
- **Make runs inspectable:** retain source text, segment boundaries, voice assignments, request digests, and completion status.
- **Resume completed work:** reuse matching completed segments that still pass media checks.
- **Fit your workflow:** run the standalone CLI or use it with an agent; no Python dependencies beyond the standard library.

VoAI is the example default, **not an implicit CLI fallback**: a provider must be specified in the config or a CLI override. `openai_speech` is an optional compatibility adapter, not the recommended starting path.

## Requirements

- Python 3.11 or newer; no `pip install` step.
- For actual synthesis: network access, VoAI credentials, and valid service/model/voice settings.
- For merging multiple segments in `single` or `both` mode: `ffmpeg` on `PATH`. The example uses `segments`, which needs no external media tool. A one-segment merged output is copied without `ffmpeg`.

## Quick start

Run these commands from the repository directory. Use your Python 3.11+ executable if it is named differently.

### 1. Try the offline validation

```sh
python3 scripts/article_to_audio.py --config config.example.json --validate-only
python3 -m unittest discover -s tests -v
```

Validation reads the included public article fixture and plans its segments. It does **not** read credentials, call an API, create audio, or create an output directory. A successful result contains `"status": "valid"`; it does not prove that service credentials or model/voice identifiers work.

### 2. Configure your VoAI run

Copy `config.example.json` to `config.json` in the same directory using your file manager or shell. `config.json` is ignored by Git. Edit it before synthesis:

| Setting | What to use |
| --- | --- |
| `provider.name` | Keep `voai_dialogue`. |
| `provider.base_url` | Your VoAI service base URL; the example URL is a placeholder. |
| `provider.credential_env` | Keep `TTS_API_KEY`, the **name** of the environment variable, not the key itself. |
| `synthesis.model` | A valid VoAI model/version identifier. |
| `synthesis.voices` | Your supported voice names and styles; replace both placeholder voices, or use one voice. |
| `source.path` | Your UTF-8 Markdown or text file; `-` reads standard input. |
| `source.section` | For the whole document, use `{"type": "all"}`. The example instead selects the heading `Selected Section`. |
| `output.directory` | Your destination; the example uses `generated-audio`. |

Confirm that speed, sample rate, format, and styles are supported by your service. Relative source and output paths resolve from the **config file's directory**, including paths supplied through CLI overrides. Keep the explicit segmentation settings and output mode, or adjust them intentionally.

The adapter appends `/TTS/generate-dialogue` to `provider.base_url` unless you supply `provider.endpoint`. Do not duplicate that endpoint in the base URL. The supplied URL, model, and voice names are examples—not working service credentials or identifiers.

### 3. Provide `TTS_API_KEY` securely

Set an environment variable named `TTS_API_KEY` in the shell or runtime that launches Python, using your local secret-management mechanism. Its value is your VoAI API credential; do not put that value in JSON, documentation, command examples, or version control.

The CLI reads the variable named by `provider.credential_env` (which defaults to `TTS_API_KEY`). It does **not** automatically load `.env` files. No key is needed for `--validate-only`.

Alternatively, pass an existing protected UTF-8 file containing only the credential:

```sh
python3 scripts/article_to_audio.py --config config.json --credential-file path/to/credential.txt
```

A credential file takes precedence over the environment variable. On POSIX it must have no group/other permission bits; on other systems, apply user-only access controls. Keep it outside shared files.

### 4. Validate your article, then generate audio

With the environment variable configured and all placeholders replaced:

```sh
python3 scripts/article_to_audio.py --config config.json --validate-only
python3 scripts/article_to_audio.py --config config.json
```

The second command sends the selected text to the configured service and may incur API charges. With the example output settings, audio segments and reports go into `generated-audio/` beside the config file.

## Optional pairing: audiobook-writing-skill-v2

Use `audiobook-writing-skill-v2` to prepare a listening-oriented manuscript, then save the reviewed script as UTF-8 Markdown or text and pass it to this skill. The workflow is simple: **prepare the script → review the wording → synthesize with VoAI API → listen and check**.

This is an optional file-based handoff, not an installed dependency or an automatic integration. This package handles synthesis; it does not rewrite the manuscript for you.

## Configuration and CLI controls

Source scope, provider, model, voices, speed, sample rate, format, all three segment limits, output directory, and output mode must be supplied explicitly in configuration or supported CLI overrides. `source.section` is an object whose `type` is `all`, `heading`, `markers`, or `line_range`; scoped selectors need their corresponding fields.

Useful overrides include `--source`, `--section`, `--provider`, `--base-url`, `--model`, repeated `--voice NAME[:STYLE]`, `--speed`, `--sample-rate`, `--format`, `--segment-range MIN:TARGET:MAX`, `--output-dir`, and `--output-mode`. For example, validate the entire included fixture rather than only its selected heading:

```sh
python3 scripts/article_to_audio.py --config config.example.json --section all --validate-only
python3 scripts/article_to_audio.py --help
```

CLI section syntax is `all`, `heading:TITLE`, `markers:START::END`, or `lines:START:END`. Segment limits are soft: paragraph, sentence, and clause boundaries take priority over exact character targets; exceptions are recorded in the manifest.

Configuration errors return exit code 2 with JSON fields `status`, `missing_parameters`, and `validation_errors`. A timed-out request is checkpointed as uncertain. Only use `--retry-uncertain` after checking provider usage and accepting the risk of a duplicate charge.

## Outputs and quality checks

| Output | Purpose |
| --- | --- |
| `normalized-source.json` | Selected text, source line range, and SHA-256. |
| `segments-manifest.json` | Text spans, boundaries, voices/styles, request digests, files, and statuses. |
| `segments/` | Individual audio files and resumable completed work. |
| `article-audio.<format>` | Merged output in `single` or `both` mode; segment files are retained in either mode. |
| `run-report.json` | Completion summary without credentials. |

Built-in checks cover minimum file size and common WAV/MP3/Ogg/FLAC signatures, not full decoding or listening quality. Verify audio with a decoder/probe and listen for pronunciation, pacing, and transitions before publishing. Use a separate output directory when switching services: resume digests describe synthesis requests, not the provider URL.

## Adapter details

`scripts/article_audio/providers.py` keeps API-specific behavior separate from source extraction and segmentation:

- `voai_dialogue`: one dialogue item per request; sends the credential in `x-api-key` by default, with `x-output-format` and `x-sample-rate` headers.
- `openai_speech`: optional OpenAI-compatible `/v1/audio/speech` adapter with style instructions. Set `provider.options.sample_rate_header` only if your server supports it; otherwise the requested sample rate is not sent by this adapter.

These describe the included adapters, not a guarantee that every service supports every setting. Confirm your service contract before a paid run.

## Share safely

Follow `SHARE_CHECKLIST.md`. Do not publish local configs, credentials, private source text, generated audio, account/quota details, or absolute machine paths. Output JSON includes source content, so review it before sharing too.
