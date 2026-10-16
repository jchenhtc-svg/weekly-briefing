-- D1 資料表：存放週會宣導的回應
-- 部署指令（第一次建立資料庫後）：
--   npx wrangler d1 execute weekly-briefing-responses --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode TEXT NOT NULL,
  question TEXT NOT NULL,
  response TEXT NOT NULL,
  choice TEXT,                 -- 「這集你最有感的是哪一點」選的選項文字（可空）
  name TEXT,                   -- 具名欄（USB 必答題／結訓測驗）：名字＋社編去掉最後一碼；只有 /admin/responses 讀得到
  submitted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_responses_episode ON responses(episode);
