# 週會宣導入口網站

《工程師的價值》週會宣導課程，9 週份。線上版由 GitHub Pages 服務。

## 這個 repo 為什麼獨立出來

原本放在 `jchenhtc-svg/my-research-tools` 裡，靠一個 feature 分支部署 Pages。
後來該 repo 要轉為 private，而 **GitHub Pages 在 private repo 上需要 Pro 以上方案**，
所以把需要公開的這部分拆出來，維持公開、維持 Pages。

## 部署

推到 `main` 會自動觸發 `.github/workflows/pages.yml`：產生雲端版網頁 → 組 `_site` → 發布到 Pages。

**需要兩個 Actions Secrets**（Settings → Secrets and variables → Actions）：

| 名稱 | 內容 |
|---|---|
| `WEEKLY_BRIEFING_API_BASE` | Cloudflare Worker 的網址 |
| `WEEKLY_BRIEFING_SITE_KEY` | 作答頁用的 site key |

兩個值都在 Cloudflare 那邊，`tools/週會宣導/cloudflare/README.md` 有取得方式。
**舊 repo 的 secret 值無法搬移**（GitHub 不提供讀取），必須重新輸入。

## 後端

作答資料走 Cloudflare Worker + D1，程式在 `tools/週會宣導/cloudflare/`。
Worker 的 CORS 設為 `*`，不綁來源，所以 Pages 網址改變不影響它。

## 為什麼有一個孤零零的 `.claude/skills/.../assets/template.html`

`產生網頁.py` 第 26 行把播放器範本的位置寫死成
`<repo根>/.claude/skills/ai-dialogue-podcast-builder/assets/template.html`，
所以這個 repo 必須在同樣位置放一份，CI 才生得出雲端版網頁。

**只搬了 `assets/template.html`，沒搬整個技能。** 技能本體（`SKILL.md`）留在原本的
`my-research-tools`（private），這個公開 repo 只保留建置真正需要的那一個檔案。
