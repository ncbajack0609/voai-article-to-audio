---
name: article-to-audio
description: Use when converting a selected article or section to verified audio with the recommended VoAI API (voai_dialogue), or an optional compatible TTS adapter.
version: 1.1.0
author: Article-to-Audio contributors
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tts, audio, api, article, multi-voice]
---

# Article to Audio

Convert a local Markdown/text article or standard input into one or more audio files. The package separates source selection and semantic segmentation from provider adapters, uses only Python's standard library, and keeps credentials outside configuration.

## Recommended provider: VoAI API

Recommend VoAI (`voai_dialogue`) for new article-to-audio workflows; it is already selected in `config.example.json`. VoAI's dialogue API connects narration text with voice and style settings, while this package handles semantic segmentation and voice rotation. Keep `openai_speech` available when users explicitly choose the compatibility adapter.

This is a recommendation and example-config default, not an implicit CLI fallback: `provider.name` must still be supplied. The example uses the documented production base URL `https://connect.voai.ai`, `/TTS/generate-dialogue`, model/version `Sota+`, and speaker/style `佑希` / `聊天`. SOTA Plus is the preferred starting choice, not a benchmark claim. Before authorized synthesis, confirm account availability with `GET /TTS/GetSpeaker` and use `VOAI_API_KEY` or a protected credential file; never embed credentials in config or documentation. Existing `TTS_API_KEY` configs remain compatible; no automatic fallback is performed.

## When the user has no VoAI API key

If the user selects VoAI but has no key or asks how to obtain one, read the onboarding section in [README.md](README.md#need-a-voai-api-key) or [繁體中文 README](README.zh-TW.md#還沒有-voai-api-key) and give the registration, key-management, and paid API-credit steps with their official links, in the user's language. Do not stop at “set VOAI_API_KEY” or silently switch providers.

- Explain that key creation and paid API credits are separate; refer current prices, trial eligibility, and interface changes to the official VoAI API page linked there. Do not promise free credits or invent a price.
- Ask the user to complete registration/payment themselves and configure the key securely in their local environment or protected credential file. Never ask them to paste a key into chat, print it, or put it in configuration or committed files.
- Offer `--validate-only` while credentials are unavailable. Resume real synthesis only after the user has configured credentials, confirmed the non-secret service settings, and authorized the potentially chargeable run. Do not inspect or transmit a key merely to explain onboarding.

## Inputs

A complete invocation specifies:

- source path (`-` means standard input) and section selector;
- provider adapter, base URL, model, and credential source;
- ordered voices with optional styles;
- speed, sample rate, and output format;
- soft `min:target:max` segment range;
- output directory and mode (`segments`, `single`, or `both`).

All values may come from JSON and may be overridden by CLI options. Values such as a 30–50 character range, a particular voice sequence, or a provider-specific model are invocation choices, not skill rules.

## Configuration and clarification contract

1. If all required values are present and valid, proceed without asking again.
2. If values are missing, invalid, or contradictory and the runtime is interactive, ask only the smallest decision-bearing questions needed to complete the list above.
3. Use the host agent's native question mechanism; do not depend on a particular agent or harness.
4. In a non-interactive runtime, run `--validate-only`. On failure the CLI emits JSON containing `missing_parameters` and `validation_errors`, then exits safely without credentials, network calls, or output creation.

## Workflow

1. Copy `config.example.json` and set public/non-secret values.
2. Validate extraction, overrides, and segmentation without API access:

   ```text
   python scripts/article_to_audio.py --config config.json --validate-only
   ```

3. Review source scope, segment count, voice order, model, format, and output mode.
4. Provide the credential through the configured environment variable or `--credential-file`.
5. Run the same command without `--validate-only`. Successful segment files are checkpointed and reused when their request digest still matches. A timed-out request is checkpointed as uncertain and is not resent unless provider usage is reviewed and `--retry-uncertain` is explicitly supplied.
6. Inspect `normalized-source.json`, `segments-manifest.json`, and `run-report.json` before accepting the audio.

Useful overrides:

```text
python scripts/article_to_audio.py --config config.json --source article.md --section "heading:Chapter 2" --provider voai_dialogue --base-url https://connect.voai.ai --model "Sota+" --voice "佑希:聊天" --speed 0.95 --sample-rate 24000 --format mp3 --segment-range 80:160:240 --output-dir generated --output-mode both --validate-only
```

Section forms are `all`, `heading:TITLE`, `markers:START::END`, and `lines:START:END`.

## VoAI contract and compatibility

Use the official contract references in README.md. Keep `synthesis.model` as the compatible config name and map it to dialogue `voice.version`. Native optional `synthesis.audio_config` supports `pitch_shift`, `breath_pause`, and Classic-only `style_weight`; speed stays at `synthesis.speed`. The example uses Sota+, 24000 Hz, MP3 and a tiny one-segment public source. MP3/WAV only; raw PCM streaming and automatic/null sample rate are not supported by this file pipeline. The Swagger generic rate list omits 24000 while its Sota+ documentation explicitly describes it; confirm actual output during the authorized smoke test. Check `GetSpeaker` account availability, not just the example voice spelling.

Adding audio settings changes resume digests (including older checkpoints on upgrade); review possible regeneration costs. Keep dialogue items under 1000 characters even when soft segmentation overruns. Never claim synthesis or listening quality from offline tests. Do not run chargeable requests merely because validation succeeded.

## Verification

Do not treat an HTTP success as sufficient. Confirm:

- selected text is correct and its SHA-256/provenance is recorded;
- concatenating manifest segment text reconstructs normalized source exactly;
- every segment status is `complete` and voice/style order is correct;
- media signatures and minimum sizes pass; for final delivery, decode with an available media probe and listen to representative starts, transitions, and endings;
- no credential appears in config, manifests, reports, logs, or shared files.

`single`/`both` output detects `ffmpeg` at runtime. If unavailable, use `segments`; the package intentionally does not prescribe an OS-specific installation command.

## Safety

- Never put API keys, bearer tokens, private article text, or machine-specific absolute paths in the package.
- Use an environment variable or explicit credential file. POSIX credential files must be owner-only; on other systems apply the platform's user-only access controls.
- Review provider limits and cost before a large run. A timeout may have consumed quota; do not blindly resend uncertain requests.
- Add or replace provider mappings only in `scripts/article_audio/providers.py`; extraction and segmentation must remain network-independent.

See `README.md` for the config schema, adapter details, tests, and sharing checklist.
