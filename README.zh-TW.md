# Article to Audio — 用 VoAI API，讓文章變成可聆聽的內容

[English](README.md)

將文章、耳讀稿與指定章節，轉為可重複執行的音訊製作流程。這套可攜式 Python skill 能選取文字、依語意邊界分段、輪替指定聲線，並保存音訊與可追溯的處理紀錄。

**推薦從 VoAI API 開始。** `voai_dialogue` 是本套件推薦的供應商，也是 `config.example.json` 的預設選擇。內建介接器會將每段文字連同聲線、風格、模型／版本與語速設定，送至 VoAI 對話語音端點；本套件則負責分段、進度保存與輸出整理。

## 為什麼使用這套工具？

- **只朗讀你選的內容：** 整份文件、指定標題、標記之間的段落，或特定行號範圍。
- **掌握旁白配置：** 全文使用同一聲線，或依清單順序在各段輪替聲線。
- **讓製作過程可檢查：** 保留來源文字、分段邊界、聲線配置、請求摘要與完成狀態。
- **接續已完成的工作：** 重用請求相符、且仍通過媒體檢查的已完成片段。
- **融入既有工作流程：** 可獨立執行 CLI，也可搭配 agent；只需 Python 標準函式庫。

VoAI 是範例設定的預設選擇，**不是 CLI 自動補上的供應商**：仍須在設定檔或 CLI 覆寫中明確指定。`openai_speech` 保留為可選的相容介接器，並非推薦的起始路徑。

## 執行需求

- Python 3.11 或更新版本，不需要執行 `pip install`。
- 實際合成需要網路、VoAI 憑證，以及有效的服務、模型與聲線設定。
- 使用 `single` 或 `both` 模式合併多個片段時，`PATH` 中須有 `ffmpeg`。範例採用 `segments`，不需要外部媒體工具；只有一個片段時，合併輸出直接複製檔案，不需 `ffmpeg`。

## 還沒有 VoAI API Key？

1. 用電腦瀏覽器開啟 [VoAI 聲音創造所](https://app.voai.ai/)，依網站提示註冊／登入帳號。
2. 開啟右上角會員選單 → **API Key 管理**，建立金鑰。
3. 要付費使用 API，進入**方案價格 → API 方案**，或開啟 [API 點數儲值頁](https://app.voai.ai/api-topup)，購買 API 生成點數。建立金鑰與購買點數是兩個步驟；請選擇 API 點數，不要將網頁版訂閱視為 API 額度。
4. 依下方說明，在本機透過 `VOAI_API_KEY` 或受保護的憑證檔提供金鑰。**不要把金鑰貼進 agent 對話、JSON、文件或 Git。** 保留 `provider.name` 為 `voai_dialogue`，並在合成前確認其他服務設定。

最新申請流程、試用條件與價格以 [VoAI 官方 API 頁](https://www.voai.ai/api)為準；優惠與介面名稱可能調整。設定期間可先執行 `--validate-only`，不需要金鑰。註冊、付款與可能計費的合成都由你決定是否進行。

## 快速開始

請在儲存庫目錄中執行以下指令。若你的 Python 3.11+ 執行檔名稱不同，請替換指令中的 `python3`。

### 1. 先試離線驗證

```sh
python3 scripts/article_to_audio.py --config config.example.json --validate-only
python3 -m unittest discover -s tests -v
```

驗證會讀取隨附的短篇公開語音測試檔並規劃分段，**不會**讀取憑證、呼叫 API、生成音訊或建立輸出目錄。成功結果包含 `"status": "valid"`；這不代表服務憑證、模型或聲線識別碼已通過線上驗證。

### 2. 設定你的 VoAI 合成工作

使用檔案管理員或 shell，將 `config.example.json` 複製為同一目錄下的 `config.json`。Git 已忽略 `config.json`。合成前請編輯以下設定：

| 設定 | 填寫內容 |
| --- | --- |
| `provider.name` | 保留 `voai_dialogue`。 |
| `provider.base_url` | 正式服務基底網址 `https://connect.voai.ai`。 |
| `provider.credential_env` | 使用 `VOAI_API_KEY`，這是環境變數的**名稱**，不是金鑰本身。 |
| `synthesis.model` | 範例優先使用 `Sota+`（SOTA Plus）；官方另列 `Classic`、`Neo`。請保留 API 字面值與大小寫。 |
| `synthesis.voices` | 官方 quickstart 使用 `佑希`／`聊天`；實際帳戶可用組合須以 `GET /TTS/GetSpeaker` 確認。 |
| `source.path` | UTF-8 Markdown 或純文字檔；`-` 代表從標準輸入讀取。 |
| `source.section` | 範例使用 `{"type": "all"}`，朗讀短篇 `tests/fixtures/voai-smoke.txt`。 |
| `output.directory` | 輸出位置；範例為 `generated-audio`。 |

請確認服務支援所選的語速、取樣率、格式與風格。相對來源路徑與輸出路徑均以**設定檔所在目錄**為基準，包含透過 CLI 覆寫的路徑。請保留明確的分段設定與輸出模式，或依需求調整。

介接器預設會在 `provider.base_url` 後接上 `/TTS/generate-dialogue`；也可用 `provider.endpoint` 指定端點。不要在基底網址重複加入端點路徑。範例已填入官方文件中的正式網址、模型與聲線，但不含憑證。優先使用 SOTA Plus 是使用偏好，不是效能評測或實際音質比較結論。

### 3. 安全提供 `VOAI_API_KEY`

透過本機的機密管理方式，在啟動 Python 的 shell 或執行環境中設定名為 `VOAI_API_KEY` 的環境變數。它的值是你的 VoAI API 憑證；請勿將實際值寫入 JSON、文件、指令範例或版本控制。

CLI 只讀取 `provider.credential_env` 指定的環境變數：新範例使用 `VOAI_API_KEY`；省略此欄位時仍保留舊版 `TTS_API_KEY` 預設，因此既有設定相容，不會自動嘗試另一把金鑰；**不會**自動載入 `.env` 檔案。執行 `--validate-only` 不需要金鑰。

也可以指定既有、受保護的 UTF-8 憑證檔，檔案內容只放憑證：

```sh
python3 scripts/article_to_audio.py --config config.json --credential-file path/to/credential.txt
```

憑證檔優先於環境變數。在 POSIX 系統上，檔案不得開放群組或其他使用者的權限；其他系統請設定僅限使用者存取。不要將憑證檔放入分享內容。

### 4. 驗證文章，再生成音訊

設定環境變數並審閱來源與參數後，執行：

```sh
python3 scripts/article_to_audio.py --config config.json --validate-only
python3 scripts/article_to_audio.py --config config.json
```

第二個指令會將選取的文字傳送至設定的服務，可能產生 API 費用。沿用範例輸出設定時，音訊片段與報告會放在設定檔旁的 `generated-audio/` 目錄。

## 選用搭配：audiobook-writing-skill-v2

可先用 `audiobook-writing-skill-v2` 準備適合聆聽的稿件，審閱後存成 UTF-8 Markdown 或純文字檔，再交給本套件。流程是：**準備耳讀稿 → 審閱文字 → 用 VoAI API 合成 → 試聽檢查**。

這是可選的檔案交接流程，不是必須安裝的依賴，也不是自動整合。本套件負責語音合成，不會代你改寫稿件。

## 設定與 CLI 控制

來源範圍、供應商、模型、聲線、語速、取樣率、格式、三個分段限制、輸出目錄與輸出模式，都須透過設定檔或支援的 CLI 覆寫明確提供。`source.section` 是物件，其 `type` 可為 `all`、`heading`、`markers` 或 `line_range`；選取特定範圍時須補上對應欄位。

常用覆寫選項包括 `--source`、`--section`、`--provider`、`--base-url`、`--model`、可重複指定的 `--voice NAME[:STYLE]`、`--speed`、`--sample-rate`、`--format`、`--segment-range MIN:TARGET:MAX`、`--output-dir` 與 `--output-mode`。例如，改用標題選取測試文章，而非短篇語音測試檔：

```sh
python3 scripts/article_to_audio.py --config config.example.json --source tests/fixtures/article.md --section "heading:Selected Section" --validate-only
python3 scripts/article_to_audio.py --help
```

CLI 的範圍語法為 `all`、`heading:TITLE`、`markers:START::END` 或 `lines:START:END`。分段限制是彈性目標：段落、句子與子句邊界優先於精確字元數；例外會記錄在 manifest 中。

設定錯誤會以結束碼 2 回傳 JSON，包含 `status`、`missing_parameters` 與 `validation_errors`。逾時請求會保存為不確定狀態；只有在查核供應商用量，並接受可能重複計費的風險後，才使用 `--retry-uncertain`。

## 輸出與品質檢查

| 輸出 | 用途 |
| --- | --- |
| `normalized-source.json` | 選取文字、來源行號範圍與 SHA-256。 |
| `segments-manifest.json` | 文字範圍、邊界、聲線／風格、請求摘要、檔案與狀態。 |
| `segments/` | 各段音訊，以及可供接續執行的已完成片段。 |
| `article-audio.<format>` | `single` 或 `both` 模式的合併音訊；兩種模式都會保留片段檔案。 |
| `run-report.json` | 不含憑證的完成摘要。 |

內建檢查涵蓋最小檔案大小與常見 WAV／MP3／Ogg／FLAC 簽章，不代表已完整解碼或確認聆聽品質。發布前，請用解碼／媒體探測工具檢查，並試聽發音、語速與轉場。切換服務時請使用不同輸出目錄：續跑比對的摘要描述合成請求，不包含供應商網址。

## VoAI 原生請求設定

保留既有設定欄位以相容舊設定：`synthesis.model` 對應 **`input.dialogue[].voice.version`**，不是 `voice.model`；聲線的 `name`、`style` 直接對應 API 欄位。每個文字片段成為一個 `voai_script_text` 對話項目。`synthesis.speed` 對應該項目的 `audio_config.speed`（0.5–1.5）。

可選的 `synthesis.audio_config` 接受 `pitch_shift`（-5–5）、`breath_pause`（0–10 秒）與 `style_weight`（0–1，**僅 Classic**）。不要在此物件重複填 `speed`。省略時採服務預設；不支援的欄位、非 Classic 的 `style_weight` 會被拒絕，避免看似生效卻被忽略。新欄位納入續跑摘要，因此升級後舊 checkpoint 可能重新生成；請使用新輸出目錄並先確認費用。保留相容介接器，但它不接受非空的 VoAI 專用 `audio_config`。

`format`、`sample_rate` 分別對應 `x-output-format`、`x-sample-rate` 標頭。本 CLI 處理檔案，支援 **MP3／WAV**，不支援原始 PCM 串流（API 本身對符合資格的帳戶提供 PCM）。官方模型上限為 Classic 44100、Neo 32000、Sota+ 24000 Hz。Swagger 標頭清單列出 8000／16000／32000／44100，但另明載 Sota+ 原生／預設 24000；範例採 24000。這個文件差異不等於已完成線上驗證：短測時須核對實際回傳取樣率，也可明確改用清單列出的 16000。本 CLI 不提供 `null`／自動取樣率。

每個對話項目上限為 1000 字。語意分段是彈性目標，極長且不中斷的子句可能超標；介接器會在送出該項目前拒絕超過 1000 字的文字。請縮短來源，不要盲目重試。

### 官方規格來源

由[官方 API 入口](https://www.voai.ai/api)找到：[文件首頁](https://connect.voai.ai/docs/index.html)、[quickstart](https://connect.voai.ai/docs/guides/quickstart.html)、[對話欄位](https://connect.voai.ai/docs/features/dialogue.html)、[配音員／GetSpeaker](https://connect.voai.ai/docs/features/voices.html)、[正式 Swagger schema](https://connect.voai.ai/swagger/tts/swagger.json)。正式基底網址取自文件的[導覽設定](https://connect.voai.ai/docs/assets/js/nav-data.js)。Quickstart 的 `Sota+`／`佑希`／`聊天` 範例使用 `/TTS/Speech`；本介接器刻意保留 `/TTS/generate-dialogue` 的正確結構，不直接照搬 Speech 請求內容。

`GetSpeaker` 需要金鑰，回傳 `data.models[]`，其中包含 `info.version` 與 `speakers[]`（`name`、`styles`）。可用聲線依帳戶而異：套件範例來自官方文件，並已通過下方記載的授權短句實測；不保證每個帳戶都有相同聲線權限。自動測試使用假音訊，僅驗證離線契約。獲得授權後，先核對帳戶目錄，再以短篇測試檔執行一次，解碼／探測 MP3 並確認時長與取樣率，再考慮長文。

## 真實 API 短句實測結果

已經授權，以 `config.example.json` 的 `Sota+`、`佑希`／`聊天` 與隨附公開短句，呼叫正式 dialogue 端點並成功產生音檔。MP3 為 3.072 秒、24000 Hz、單聲道；`ffmpeg` 完整解碼無錯誤。這驗證預設請求與音檔可解碼，不代表完成音質比較或所有選用模型／參數的實測；另有 17 項離線測試通過。金鑰、帳戶聲優清單回應與生成音檔均不提交。

## 介接器細節

`scripts/article_audio/providers.py` 將 API 行為與來源擷取、分段邏輯分開：

- `voai_dialogue`：每次請求送出一個對話項目；預設使用 `x-api-key` 傳遞憑證，並附上 `x-output-format` 與 `x-sample-rate` 標頭。
- `openai_speech`：可選的 OpenAI 相容 `/v1/audio/speech` 介接器，支援傳送風格指示。僅在伺服器支援時設定 `provider.options.sample_rate_header`；否則此介接器不會傳送要求的取樣率。

以上描述的是套件內建介接器，不保證每個服務都支援每項設定。付費執行前請確認你的服務規格。

## 安全分享

請遵守 `SHARE_CHECKLIST.md`。不要發布本機設定、憑證、私密來源文字、生成音訊、帳戶／額度資訊或機器絕對路徑。輸出的 JSON 含有來源內容，分享前也須審閱。

## 授權

本專案採用 [MIT 授權條款](LICENSE)。
