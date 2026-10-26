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

## Need a VoAI API key?

1. Open [VoAI 聲音創造所](https://app.voai.ai/) in a desktop browser and follow the site's registration/sign-in prompts.
2. Open the account menu → **API Key 管理** (API Key Management) and create a key.
3. For paid API usage, open **方案價格 → API 方案**, or the [API credit top-up page](https://app.voai.ai/api-topup), and purchase API generation credits. Creating a key and buying credits are separate steps; choose API credits rather than assuming a web subscription supplies API usage.
4. Store the key locally via `VOAI_API_KEY` or a protected credential file as described below. **Do not paste it into agent chat, JSON, documentation, or Git.** Keep `provider.name` set to `voai_dialogue` and confirm the remaining service settings before synthesis.

Use the [official VoAI API page](https://www.voai.ai/api) for current onboarding, trial conditions, and pricing; offers and interface labels may change. You can run `--validate-only` without a key while completing setup. Registration, payment, and any chargeable synthesis remain under your control.

## Quick start

Run these commands from the repository directory. Use your Python 3.11+ executable if it is named differently.

### 1. Try the offline validation

```sh
python3 scripts/article_to_audio.py --config config.example.json --validate-only
python3 -m unittest discover -s tests -v
```

Validation reads the included short public smoke-test fixture and plans its segments. It does **not** read credentials, call an API, create audio, or create an output directory. A successful result contains `"status": "valid"`; it does not prove that service credentials or model/voice identifiers work.

### 2. Configure your VoAI run

Copy `config.example.json` to `config.json` in the same directory using your file manager or shell. `config.json` is ignored by Git. Edit it before synthesis:

| Setting | What to use |
| --- | --- |
| `provider.name` | Keep `voai_dialogue`. |
| `provider.base_url` | `https://connect.voai.ai` (production). |
| `provider.credential_env` | Use `VOAI_API_KEY`, the **name** of the environment variable, not the key itself. |
| `synthesis.model` | `Sota+` (SOTA Plus), preferred in this example; `Classic` and `Neo` are also documented API literals. |
| `synthesis.voices` | Official quickstart combination: `佑希` / `聊天`. Confirm account availability with `GET /TTS/GetSpeaker`. |
| `source.path` | Your UTF-8 Markdown or text file; `-` reads standard input. |
| `source.section` | The example uses `{"type": "all"}` on the tiny `tests/fixtures/voai-smoke.txt` fixture. |
| `output.directory` | Your destination; the example uses `generated-audio`. |

Confirm that speed, sample rate, format, and styles are supported by your service. Relative source and output paths resolve from the **config file's directory**, including paths supplied through CLI overrides. Keep the explicit segmentation settings and output mode, or adjust them intentionally.

The adapter appends `/TTS/generate-dialogue` to `provider.base_url` unless you supply `provider.endpoint`. Do not duplicate that endpoint in the base URL. The example contains documented production identifiers, not credentials. SOTA Plus is a preference, not a benchmark or listening-comparison claim.

### 3. Provide `VOAI_API_KEY` securely

Set an environment variable named `VOAI_API_KEY` in the shell or runtime that launches Python, using your local secret-management mechanism. Its value is your VoAI API credential; do not put that value in JSON, documentation, command examples, or version control.

The CLI reads only the variable named by `provider.credential_env`: the example selects `VOAI_API_KEY`; omission retains the legacy `TTS_API_KEY` default. Existing configs using `TTS_API_KEY` still work; there is no automatic key fallback. It does **not** automatically load `.env` files. No key is needed for `--validate-only`.

Alternatively, pass an existing protected UTF-8 file containing only the credential:

```sh
python3 scripts/article_to_audio.py --config config.json --credential-file path/to/credential.txt
```

A credential file takes precedence over the environment variable. On POSIX it must have no group/other permission bits; on other systems, apply user-only access controls. Keep it outside shared files.

### 4. Validate your article, then generate audio

After configuring the environment variable and reviewing the source and settings:

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

Useful overrides include `--source`, `--section`, `--provider`, `--base-url`, `--model`, repeated `--voice NAME[:STYLE]`, `--speed`, `--sample-rate`, `--format`, `--segment-range MIN:TARGET:MAX`, `--output-dir`, and `--output-mode`. For example, validate the heading-selection fixture instead of the tiny smoke test:

```sh
python3 scripts/article_to_audio.py --config config.example.json --source tests/fixtures/article.md --section "heading:Selected Section" --validate-only
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

## VoAI-native request settings

The existing config names remain compatible: `synthesis.model` maps to **`input.dialogue[].voice.version`**, not `voice.model`; each configured voice's `name` and `style` map directly to that item. One segment becomes one `voai_script_text` dialogue item. `synthesis.speed` maps to its `audio_config.speed` (0.5–1.5).

Optional `synthesis.audio_config` accepts `pitch_shift` (-5–5), `breath_pause` (0–10 seconds), and `style_weight` (0–1, **Classic only**). Do not duplicate `speed` inside this object. Omitted fields use service defaults; unsupported fields and ineffective non-Classic `style_weight` are rejected rather than silently ignored. These settings participate in resume digests; upgrading adds the new field to digests, so older checkpoints may regenerate. Use a fresh output directory and review costs. The compatibility adapter remains available but rejects nonempty VoAI-only `audio_config`.

`format` and `sample_rate` become `x-output-format` and `x-sample-rate` headers. This file-oriented CLI supports **MP3/WAV**, not raw PCM streaming (although the API offers PCM for eligible accounts). Documented model ceilings are Classic 44100, Neo 32000, Sota+ 24000 Hz. The Swagger header lists 8000/16000/32000/44100 but separately documents Sota+'s native/default 24000; the example uses 24000. That documentation inconsistency is not proof of a live request: confirm the actual response rate during your smoke test, or explicitly choose the listed 16000 rate. Sample-rate `null`/automatic selection is not exposed by this CLI.

VoAI limits each dialogue item to 1000 characters. Segmentation targets are soft, so an unusually long unbroken clause can exceed them; the adapter rejects text longer than 1000 characters before sending that item. Shorten such passages rather than blindly retrying.

### Official contract references

Discovered from the [official API entry page](https://www.voai.ai/api): [documentation](https://connect.voai.ai/docs/index.html), [quickstart](https://connect.voai.ai/docs/guides/quickstart.html), [dialogue fields](https://connect.voai.ai/docs/features/dialogue.html), [voices / GetSpeaker](https://connect.voai.ai/docs/features/voices.html), and [production Swagger schema](https://connect.voai.ai/swagger/tts/swagger.json). The docs' [navigation configuration](https://connect.voai.ai/docs/assets/js/nav-data.js) supplies the production base URL. The quickstart's `Sota+` / `佑希` / `聊天` example uses `/TTS/Speech`; this adapter deliberately retains the documented `/TTS/generate-dialogue` structure instead of copying the Speech payload.

`GetSpeaker` requires a key and returns `data.models[]`, each with `info.version` and `speakers[]` (`name`, `styles`). Voice availability depends on the account: the packaged example is sourced from official examples and has passed the authorized smoke test below; this does not guarantee availability for every account. The automated tests are offline contract tests using fake audio. After authorization, check the account catalogue, run the tiny fixture once, decode/probe the resulting MP3 and confirm duration/sample rate before any larger run.

## Live smoke-test result

An authorized live request to the production dialogue endpoint with `config.example.json` completed successfully using `Sota+`, `佑希` / `聊天`, and the included short public fixture. The MP3 was 3.072 seconds, 24000 Hz, mono; `ffmpeg` fully decoded it without errors. This verifies the default request and decodable output, not a comparative listening-quality assessment or every optional model/setting. The automated suite separately passes 17 offline tests. Credentials, account catalogue responses, and generated audio are not committed.

## Adapter details

`scripts/article_audio/providers.py` keeps API-specific behavior separate from source extraction and segmentation:

- `voai_dialogue`: one dialogue item per request; sends the credential in `x-api-key` by default, with `x-output-format` and `x-sample-rate` headers.
- `openai_speech`: optional OpenAI-compatible `/v1/audio/speech` adapter with style instructions. Set `provider.options.sample_rate_header` only if your server supports it; otherwise the requested sample rate is not sent by this adapter.

These describe the included adapters, not a guarantee that every service supports every setting. Confirm your service contract before a paid run.

## Share safely

Follow `SHARE_CHECKLIST.md`. Do not publish local configs, credentials, private source text, generated audio, account/quota details, or absolute machine paths. Output JSON includes source content, so review it before sharing too.

## License

Licensed under the [MIT License](LICENSE).
