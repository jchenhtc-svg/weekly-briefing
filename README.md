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
