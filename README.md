# Offline OpenAI Docs

可持續更新、以 Git 追蹤的 OpenAI 官方文件離線快照。初始資料於 2026-11-11 取得；目前快照時間與下載結果以 [manifest.json](manifest.json) 和 [summary.json](summary.json) 為準。

## 離線查閱

- [Codex 常用設定入口](CODEX-START.md)：設定、權限、Skills、MCP 與 Codex manual。
- [全部文件索引](INDEX.md)：本機文件及官方來源連結。
- [下載缺漏](MISSING.md)：目前官方索引列出、但未能取得的網址。
- [已退出索引的文件](RETIRED.md)：保留最後成功版本，不視為目前有效的官方指引。
- `manifest.json`：原始 URL、重新導向後 URL、下載時間、SHA-256 與本機路徑。
- `changes.json`：最近一次同步的新增、修改、退出索引與失敗 URL。

來源正文保留原始位元組；圖片、影片、外部儲存庫與未明列 Markdown／文字匯出的網頁不在本包範圍。原文內的相對連結不會改寫，可透過 INDEX.md 查找本機對應檔案。

## 更新與版本管理

需要 Python 3.10 以上、Git，以及可連線到官方文件網站的環境。無額外 Python 套件需求。

```powershell
Set-Location -LiteralPath 'C:\Users\lai98\OneDrive\ShihHsuan\ChatGPT\offline-openai-docs'
python sync.py update
python sync.py verify
git status --short
git diff --stat
git diff -- changes.json MISSING.md RETIRED.md
git add .
git commit -m "docs: refresh official OpenAI documentation"
```

更新行為：

1. 從 `https://developers.openai.com/llms.txt` 和 `https://learn.chatgpt.com/llms.txt` 重新發現子索引及 `.md`／`.txt` 連結。
2. 在 `.cache/` 中重新下載所有文件；可用 `--workers 3` 降低並行數。這是完整抓取，不是 HTTP 增量同步。
3. 驗證正文不是 HTML 錯誤頁，檢查檔案大小與 SHA-256。
4. 原本成功的文件現在失敗、或原本成功的索引無法取得時，停止發布，保留目前快照。錯誤詳情在 `.cache/last-attempt.json`。首次出現或一直失敗的 URL 則列在 MISSING.md。
5. 退出索引的文件保留原檔及 `retired.json` 紀錄；再次進入索引時恢復為目前文件。
6. 重新產生索引、導讀和異動清單。程式不會自動 commit 或 push。

若索引被官方永久移除，保護機制也會停止更新；應先確認新的官方入口再調整，而非把整個產品文件集默默移除。

下載及校驗完成後才開始替換檔案；每個檔案以暫存檔替換，但整個資料夾並非單一原子交易。更新時請勿同時在其他電腦更新這個 OneDrive 資料夾。若在發布階段斷電，先檢查 Git diff 和 `python sync.py verify`，再重新同步或使用 Git 恢復需要的版本。

## Git 與初始提交

此為本機 repository，預設使用 `main` 分支，未設定遠端或自動排程。`.gitattributes` 禁止 Git 對官方原始文件轉換換行，以維持校驗碼。

如果環境尚未設定 Git 作者資訊，初始提交以 `Codex <codex@local.invalid>` 作為自動產生快照的作者，僅作用於該次提交，不更動使用者或全域 Git 設定。後續個人提交請設定你自己的 repository-local 作者資訊：

```powershell
git config user.name "你的姓名"
git config user.email "你的電子郵件"
```

## 與 OpenAI Docs 技能的關係

這個 repository 更新的是官方文件內容，不會自動同步或覆寫已安裝的 OpenAI Docs 技能。本 repo 的 [AGENTS.md](AGENTS.md) 指引 Codex 優先查閱本機快照；在其他專案使用時，請明確指定此 repo 的路徑，並讓該專案的技能流程符合離線查閱需求。

回答應標示來源與快照日期，不將離線內容宣稱為已確認的最新線上狀態。產品設定仍須核對實際部署版本。此包不包含模型或軟體的離線執行環境，內容權利仍屬原權利人。

## 維護同步程式

```powershell
python -m unittest discover -s tests -v
python sync.py render
python sync.py verify
```

`download.py` 是由同步流程呼叫的底層抓取器。日常更新使用 `sync.py update`，才能保留失敗保護與異動紀錄；不要直接在此 repo 執行 `download.py --refresh`。
