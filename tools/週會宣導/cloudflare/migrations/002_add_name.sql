-- USB 資安宣導的必答題與結訓測驗要具名（名字＋社編去掉最後一碼）。
-- 只有 /admin/responses（帶 ADMIN_KEY）讀得到這一欄，公開的 /responses 不回傳。
-- 在 weekly-briefing 的 tools/週會宣導/cloudflare 資料夾執行：
--   npx wrangler d1 execute weekly-briefing-responses --remote --command="ALTER TABLE responses ADD COLUMN name TEXT"
ALTER TABLE responses ADD COLUMN name TEXT;
