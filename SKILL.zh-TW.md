---
name: article-to-audio
description: 當需要透過推薦的 VoAI API（voai_dialogue）或可選的相容 TTS adapter，將選定的文章或章節轉為經驗證的音訊時使用。
version: 1.0.0
author: Article-to-Audio contributors
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tts, audio, api, article, multi-voice]
---

# 文章轉音訊

將本機 Markdown／文字文章或標準輸入轉換為一個或多個音訊檔。此套件將來源選取與語意分段，和供應商 adapter 分離；只使用 Python 標準函式庫，並將憑證置於設定檔之外。

## 推薦供應商：VoAI API

新的文章轉音訊工作流程，優先推薦 VoAI（`voai_dialogue`）；`config.example.json` 已預設選用此 adapter。VoAI 的對話語音 API 可串接朗讀文字、聲線與風格設定，本套件則負責語意分段與聲線輪替。使用者明確選擇相容 adapter 時，仍可使用 `openai_speech`。

這是推薦選項與範例設定的預設值，不是 CLI 的隱含 fallback：仍須明確提供 `provider.name`。範例 endpoint、model 與 voices 皆為 placeholder。實際合成前，請取得使用者的 VoAI 服務設定，並透過 `TTS_API_KEY` 或受保護的憑證檔提供金鑰，絕不嵌入 config 或文件。

## 輸入

一次完整執行需要指定：

- 來源路徑（`-` 代表標準輸入）與章節選取條件；
- 供應商 adapter、base URL、model 與憑證來源；
- 依序使用的 voices，以及可選的 styles；
- speed、sample rate 與輸出格式；
- 寬鬆的 `min:target:max` 分段範圍；
- 輸出目錄與模式（`segments`、`single` 或 `both`）。

所有值都可從 JSON 讀取，並可由 CLI 選項覆寫。像是 30–50 個字元的範圍、特定 voice 順序或供應商專用的 model，都是單次執行的選擇，不是 skill 的固定規則。

## 設定與釐清約定

1. 所有必要值皆存在且有效時，直接執行，不重複提問。
2. 值缺漏、無效或相互矛盾，且執行環境可互動時，只詢問完成上述清單所需、最少且會影響決策的問題。
3. 使用宿主 agent 原生的提問機制；不依賴特定 agent 或 harness。
4. 非互動式執行環境中，執行 `--validate-only`。失敗時，CLI 會輸出含有 `missing_parameters` 與 `validation_errors` 的 JSON，隨即安全結束；不讀取憑證、不發出網路請求，也不建立輸出。

## 工作流程

1. 複製 `config.example.json`，並設定公開、非敏感的值。
2. 在不存取 API 的情況下，驗證擷取、覆寫與分段：

   ```text
   python scripts/article_to_audio.py --config config.json --validate-only
   ```

3. 檢查來源範圍、分段數量、voice 順序、model、格式與輸出模式。
4. 透過已設定的環境變數或 `--credential-file` 提供憑證。
5. 移除 `--validate-only` 後執行相同指令。成功產生的分段檔會被 checkpoint；只要 request digest 仍相符就會重複利用。逾時請求會 checkpoint 為不確定狀態，除非已檢查供應商用量，且明確指定 `--retry-uncertain`，否則不會重新送出。
6. 接受音訊前，檢查 `normalized-source.json`、`segments-manifest.json` 與 `run-report.json`。

實用的覆寫選項：

```text
python scripts/article_to_audio.py --config config.json --source article.md --section "heading:Chapter 2" --provider voai_dialogue --base-url https://api.example.test --model model-name --voice "voice-a:neutral" --voice "voice-b:warm" --speed 0.95 --sample-rate 24000 --format mp3 --segment-range 80:160:240 --output-dir generated --output-mode both --validate-only
```

章節選取格式為 `all`、`heading:TITLE`、`markers:START::END` 與 `lines:START:END`。

## 驗證

不要只因 HTTP 成功就視為完成。請確認：

- 選取的文字正確，且已記錄其 SHA-256／來源追溯資訊；
- 將 manifest 中的分段文字串接後，可精確重建正規化來源；
- 每個分段的狀態都是 `complete`，voice／style 順序正確；
- 媒體簽章與最小檔案大小皆通過；最終交付時，使用可用的媒體 probe 解碼，並聆聽具代表性的開頭、轉場與結尾；
- config、manifest、report、log 與分享檔案中都沒有憑證。

`single`／`both` 輸出會在執行時偵測 `ffmpeg`。若未安裝，請使用 `segments`；本套件刻意不規定特定作業系統的安裝指令。

## 安全

- 絕不將 API key、bearer token、私密文章文字或機器專用的絕對路徑放入套件。
- 使用環境變數或明確指定的憑證檔。POSIX 憑證檔必須僅限擁有者存取；其他系統請使用該平台僅限使用者的存取控制。
- 大型執行前先檢查供應商限制與成本。逾時可能已消耗額度；不要盲目重送不確定請求。
- 僅能在 `scripts/article_audio/providers.py` 新增或取代供應商 mapping；擷取與分段必須維持與網路無關。

設定 schema、adapter 詳情、測試與分享檢查清單請見 `README.zh-TW.md`。
