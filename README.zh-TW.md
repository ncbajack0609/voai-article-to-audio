# 可攜式文章轉音訊 API Skill

> 可搭配公開的「繁中有聲書寫作 V2」（`audiobook-writing-skill-v2`）準備耳讀稿，再交由本套件轉為音訊。

一套獨立各agent通用、只使用 Python 標準函式庫的套件，可用來選取文章文字、依語意邊界分段、輪替使用一個或多個 voice、呼叫 TTS API，並產生可稽核的輸出。它不綁定作業系統、家目錄、文章、voice、model 或 agent framework。

## 推薦供應商：VoAI API

VoAI（`voai_dialogue`）是本套件推薦的供應商，也是 `config.example.json` 的預設選擇。為什麼用 VoAI？其對話語音 API 可串接朗讀文字、聲線與風格設定，再搭配本套件的語意分段與聲線輪替，建立文章轉音訊工作流程。

CLI 仍要求明確指定 provider，不會在設定缺漏時自動選取。`openai_speech` 保留為可選的相容 adapter。範例的 base URL、model 與 voices 都是 placeholder，不能直接用來連線合成。實際使用時請填入你的 VoAI 服務設定，並將憑證放在 `TTS_API_KEY` 或受保護的憑證檔，絕不寫入分享的設定檔。

## 需求

- Python 3.11 或更新版本
- 只有實際合成時才需要網路連線
- `single` 或 `both` 輸出模式可選用 `ffmpeg`；`segments` 不需要外部媒體工具

不需要安裝任何 Python 套件。

## 快速開始

在本目錄中，先對隨附的公開 fixture 進行驗證；此步驟不需要憑證或網路連線：

```text
python scripts/article_to_audio.py --config config.example.json --validate-only
python -m unittest discover -s tests -v
```

將 `config.example.json` 複製成區域設定檔，變更 source/provider/model/voices，並設定所指定的憑證環境變數。接著執行：

```text
python scripts/article_to_audio.py --config path/to/config.json
```

或改用受保護的憑證檔：

```text
python scripts/article_to_audio.py --config path/to/config.json --credential-file path/to/credential.txt
```

在 POSIX 系統上，此檔案不得有群組或其他使用者的權限位元。其他系統請使用該平台僅限使用者的存取控制保護檔案。憑證檔優先於環境變數。

## 必填設定

- `source.path`：UTF-8 Markdown／文字檔路徑，或 `-` 代表 stdin
- `source.section`：`all`、`heading`、`markers` 或 `line_range`
- `provider.name`：`voai_dialogue` 或 `openai_speech`
- `provider.base_url`、可選的 `endpoint` 與 `credential_env`
- `synthesis.model`、非空且依序排列的 `voices`、`speed`、`sample_rate` 與 `format`
- `segmentation.min_characters`、`target_characters` 與 `max_characters`
- `output.directory`、`mode` 與 `minimum_bytes`

範圍、速度、sample rate、格式、三個分段限制與輸出模式，都必須在 config 或 CLI 覆寫中明確指定。CLI 不會將省略的決策悄悄轉為可重複套件的預設值。

相對的來源與輸出路徑，會以 config 檔所在目錄為基準解析。分段限制是寬鬆條件：段落／句子／子句邊界的重要性高於精確字元目標。manifest 會記錄任何無法避免的例外。

每個主要設定都有 CLI 覆寫選項：`--source`、`--section`、`--provider`、`--base-url`、`--model`、可重複使用的 `--voice NAME[:STYLE]`、`--speed`、`--sample-rate`、`--format`、`--segment-range MIN:TARGET:MAX`、`--output-dir` 與 `--output-mode`。逾時請求會被 checkpoint 為不確定狀態；只有在確認供應商用量，並接受可能重複計費後，才使用 `--retry-uncertain`。

## 非互動式執行約定

`--validate-only` 會進行 config 驗證、來源擷取與分段，但不讀取憑證、不發出請求，也不建立輸出目錄。無效輸入會以結束碼 2 離開，並輸出 JSON：

```json
{"status":"configuration_error","missing_parameters":["source.path"],"validation_errors":[]}
```

互動式 agent 應只對尚未決定的事項提出精簡問題。完整且有效的 config 應能執行，不應反覆提問。

## 供應商 adapter

`scripts/article_audio/providers.py` 包含一個精簡、標準化的 `SynthesisRequest`，以及兩個獨立 adapter：

- `voai_dialogue`：單項目 `/TTS/generate-dialogue` 請求，使用格式／sample-rate headers；
- `openai_speech`：OpenAI 相容的 `/v1/audio/speech` 請求，可選擇使用 style instructions。

若 OpenAI 相容伺服器接受 sample-rate header，請設定 `provider.options.sample_rate_header`。否則，所要求的 sample rate 仍是必須驗證的預期輸出限制；實際供應商行為具有優先權。

如需支援其他 API，請實作 `TTSProvider.synthesize(request)`，並在 `build_provider` 中註冊。不要將網路相關知識加入 `source.py`、`segment.py` 或 `pipeline.py`。

## 輸出

- `normalized-source.json`：選取文字、來源行號範圍與 SHA-256
- `segments-manifest.json`：精確文字範圍、語意邊界、voice/style、request digests、檔案、位元組與狀態
- `segments/`：checkpoint 媒體；只有 request digests 與媒體檢查仍相符時才會重複利用
- `article-audio.<format>`：可選的合併輸出
- `run-report.json`：不含憑證的供應商／model／輸出摘要

內建媒體檢查涵蓋檔案大小，以及常見的 WAV／MP3／Ogg／FLAC 簽章。交付前，請使用可用的 decoder／probe，並由人工聆聽發音、語速、風格與轉場。

## 分享

請遵守 `SHARE_CHECKLIST.md`。套件不得包含區域 config、憑證、私密來源、生成音訊、帳戶／額度細節或機器絕對路徑。
