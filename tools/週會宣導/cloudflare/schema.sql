-- D1 資料表：存放週會宣導的回應
-- 部署指令（第一次建立資料庫後）：
--   npx wrangler d1 execute weekly-briefing-responses --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode TEXT NOT NULL,
  question TEXT NOT NULL,
  response TEXT NOT NULL,
  submitted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_responses_episode ON responses(episode);
