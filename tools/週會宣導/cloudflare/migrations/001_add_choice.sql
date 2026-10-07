-- 已經在用的資料庫加上「最有感的一點」欄位（2026-10 新增）。只要跑一次：
--   npx wrangler d1 execute weekly-briefing-responses --remote --file=migrations/001_add_choice.sql
-- 新建的資料庫直接用 schema.sql 就有這個欄位，不用跑這支。
ALTER TABLE responses ADD COLUMN choice TEXT;
