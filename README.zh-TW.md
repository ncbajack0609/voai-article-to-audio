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

1. 用電腦瀏覽器開啟 [VoAI 聲音創造所](https://app.voai.ai/)，註冊／登入帳號；登入方式可參考[官方使用教學](https://user-guide.voai.ai/)。
2. 開啟右上角會員選單 → **API Key 管理**，建立金鑰。
3. 要付費使用 API，進入**方案價格 → API 方案**，或開啟 [API 點數儲值頁](https://app.voai.ai/api-topup)，購買 API 生成點數。建立金鑰與購買點數是兩個步驟；請選擇 API 點數，不要將網頁版訂閱視為 API 額度。
4. 依下方說明，在本機透過 `TTS_API_KEY` 或受保護的憑證檔提供金鑰。**不要把金鑰貼進 agent 對話、JSON、文件或 Git。** 保留 `provider.name` 為 `voai_dialogue`，並在合成前確認其他服務設定。

最新申請流程、試用條件與價格以 [VoAI 官方 API 頁](https://www.voai.ai/api)為準；優惠與介面名稱可能調整。設定期間可先執行 `--validate-only`，不需要金鑰。註冊、付款與可能計費的合成都由你決定是否進行。

## 快速開始

請在儲存庫目錄中執行以下指令。若你的 Python 3.11+ 執行檔名稱不同，請替換指令中的 `python3`。

### 1. 先試離線驗證

```sh
python3 scripts/article_to_audio.py --config config.example.json --validate-only
python3 -m unittest discover -s tests -v
```

驗證會讀取隨附的公開文章測試檔並規劃分段，**不會**讀取憑證、呼叫 API、生成音訊或建立輸出目錄。成功結果包含 `"status": "valid"`；這不代表服務憑證、模型或聲線識別碼已通過線上驗證。

### 2. 設定你的 VoAI 合成工作

使用檔案管理員或 shell，將 `config.example.json` 複製為同一目錄下的 `config.json`。Git 已忽略 `config.json`。合成前請編輯以下設定：

| 設定 | 填寫內容 |
| --- | --- |
| `provider.name` | 保留 `voai_dialogue`。 |
| `provider.base_url` | 你的 VoAI 服務基底網址；範例網址只是佔位值。 |
| `provider.credential_env` | 保留 `TTS_API_KEY`，這是環境變數的**名稱**，不是金鑰本身。 |
| `synthesis.model` | 有效的 VoAI 模型／版本識別碼。 |
| `synthesis.voices` | 服務支援的聲線名稱與風格；替換兩個範例聲線，或改用單一聲線。 |
| `source.path` | UTF-8 Markdown 或純文字檔；`-` 代表從標準輸入讀取。 |
| `source.section` | 朗讀全文時使用 `{"type": "all"}`；原範例只選取 `Selected Section` 標題。 |
| `output.directory` | 輸出位置；範例為 `generated-audio`。 |

請確認服務支援所選的語速、取樣率、格式與風格。相對來源路徑與輸出路徑均以**設定檔所在目錄**為基準，包含透過 CLI 覆寫的路徑。請保留明確的分段設定與輸出模式，或依需求調整。

介接器預設會在 `provider.base_url` 後接上 `/TTS/generate-dialogue`；也可用 `provider.endpoint` 指定端點。不要在基底網址重複加入端點路徑。隨附的網址、模型與聲線名稱只是範例，不能直接用於服務連線與合成。

### 3. 安全提供 `TTS_API_KEY`

透過本機的機密管理方式，在啟動 Python 的 shell 或執行環境中設定名為 `TTS_API_KEY` 的環境變數。它的值是你的 VoAI API 憑證；請勿將實際值寫入 JSON、文件、指令範例或版本控制。

CLI 會讀取 `provider.credential_env` 指定的環境變數，預設名稱為 `TTS_API_KEY`；**不會**自動載入 `.env` 檔案。執行 `--validate-only` 不需要金鑰。

也可以指定既有、受保護的 UTF-8 憑證檔，檔案內容只放憑證：

```sh
python3 scripts/article_to_audio.py --config config.json --credential-file path/to/credential.txt
```

憑證檔優先於環境變數。在 POSIX 系統上，檔案不得開放群組或其他使用者的權限；其他系統請設定僅限使用者存取。不要將憑證檔放入分享內容。

### 4. 驗證文章，再生成音訊

設定環境變數並替換所有佔位值後，執行：

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

常用覆寫選項包括 `--source`、`--section`、`--provider`、`--base-url`、`--model`、可重複指定的 `--voice NAME[:STYLE]`、`--speed`、`--sample-rate`、`--format`、`--segment-range MIN:TARGET:MAX`、`--output-dir` 與 `--output-mode`。例如，驗證隨附測試文章的全文，而非只有範例指定的標題：

```sh
python3 scripts/article_to_audio.py --config config.example.json --section all --validate-only
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

## 介接器細節

`scripts/article_audio/providers.py` 將 API 行為與來源擷取、分段邏輯分開：

- `voai_dialogue`：每次請求送出一個對話項目；預設使用 `x-api-key` 傳遞憑證，並附上 `x-output-format` 與 `x-sample-rate` 標頭。
- `openai_speech`：可選的 OpenAI 相容 `/v1/audio/speech` 介接器，支援傳送風格指示。僅在伺服器支援時設定 `provider.options.sample_rate_header`；否則此介接器不會傳送要求的取樣率。

以上描述的是套件內建介接器，不保證每個服務都支援每項設定。付費執行前請確認你的服務規格。

## 安全分享

請遵守 `SHARE_CHECKLIST.md`。不要發布本機設定、憑證、私密來源文字、生成音訊、帳戶／額度資訊或機器絕對路徑。輸出的 JSON 含有來源內容，分享前也須審閱。

## 授權

本專案採用 [MIT 授權條款](LICENSE)。
