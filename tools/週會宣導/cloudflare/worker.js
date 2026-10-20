/**
 * 週會宣導 — 回應收集用的 Cloudflare Worker
 *
 * 端點：
 *   POST /submit     寫入一則回應到 D1（response 打字回應、choice 選項，至少要有一個；
 *                    name 具名欄＝名字＋社編去掉最後一碼，只有 USB 必答題與結訓測驗會帶）
 *   GET  /responses  讀出回應（可用 ?episode=xxx 篩選單一篇集）——刻意不回傳 name，
 *                    因為 SITE_KEY 寫在公開網頁裡，誰都拿得到
 *   GET  /admin/responses  連 name 一起讀出；要帶 X-Admin-Key，值是只有主辦人知道的
 *                    ADMIN_KEY（`npx wrangler secret put ADMIN_KEY` 設定，不寫在任何網頁或 repo 裡）
 *   GET  /open-state       各集「開放／關閉」的手動設定（入口網站主題頁讀，公開）
 *   POST /admin/open-state 主辦人在後台按「開放／關閉／依網頁預設」，要帶 X-Admin-Key
 *                    （存在 D1 的 settings 表，第一次寫入時自動建表，不用另外跑 migration）
 *   GET  /respond    手機掃 QR Code 進來看到的簡易回應頁面
 *                    （?ep=<episode>&q=<question> 帶入要回答的問題）
 *
 * SITE_KEY 不是真正的身分驗證，只是一個簡單的防呆／防隨機掃描機器人的
 * 門檻——這個 Worker 網址一旦被知道，理論上任何人都能打，SITE_KEY
 * 只是讓「不小心路過」的機器人寫不進去，不是拿來擋蓄意攻擊的。
 * 部署時用 `npx wrangler secret put SITE_KEY` 設定實際的值。
 */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function respondPage(episode, question, siteKey) {
  return `<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>週會宣導回應</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#efefef;color:#111;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif;padding:24px 16px}
  .card{max-width:480px;margin:0 auto;background:#fff;border:3px solid #111;border-radius:10px;padding:20px}
  h1{font-size:18px;margin:0 0 12px}
  .q{font-size:15px;font-weight:800;line-height:1.6;margin-bottom:16px;padding-bottom:16px;border-bottom:2px dashed #111}
  textarea{width:100%;min-height:100px;border:2px solid #111;border-radius:10px;padding:10px 12px;font-family:inherit;font-size:15px;resize:vertical;box-sizing:border-box}
  button{margin-top:12px;width:100%;background:#111;color:#fff;border:2px solid #111;border-radius:999px;padding:12px;font-size:15px;font-weight:700;font-family:inherit}
  .note{margin-top:10px;font-size:13px;color:#6b6b6b;text-align:center;min-height:18px}
</style></head>
<body>
  <div class="card">
    <h1>《工程師的價值》${escapeHtml(episode)}</h1>
    <div class="q">${escapeHtml(question) || "說說你的想法"}</div>
    <textarea id="r" maxlength="300" placeholder="打幾個字，說說你的想法……"></textarea>
    <button type="button" onclick="submitIt()">送出回應</button>
    <div class="note" id="note"></div>
  </div>
<script>
const EP = ${JSON.stringify(episode)};
const Q = ${JSON.stringify(question)};
const KEY = ${JSON.stringify(siteKey)};
async function submitIt(){
  const el = document.getElementById("r"), note = document.getElementById("note");
  const text = el.value.trim();
  if(!text){ note.textContent = "打點字再送出喔"; return; }
  note.textContent = "送出中……";
  try{
    const res = await fetch("/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Site-Key": KEY },
      body: JSON.stringify({ episode: EP, question: Q, response: text })
    });
    if(!res.ok) throw new Error("HTTP " + res.status);
    el.value = "";
    note.textContent = "已送出，感謝分享！";
  } catch(e){
    note.textContent = "送出失敗，檢查一下網路連線再試一次";
  }
}
</script>
</body></html>`;
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*", // 播放器是 file:// 開啟，Origin 會是 "null"，用 * 才會過
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Site-Key, X-Admin-Key",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    if (url.pathname === "/submit" && request.method === "POST") {
      if (env.SITE_KEY && request.headers.get("X-Site-Key") !== env.SITE_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      const episode = String(body.episode || "").slice(0, 200);
      const question = String(body.question || "").slice(0, 500);
      const response = String(body.response || "").trim().slice(0, 1000);
      const choice = String(body.choice || "").trim().slice(0, 100);
      const name = String(body.name || "").trim().slice(0, 40);
      const submittedAt = new Date().toISOString();
      if (!episode || (!response && !choice)) {
        return json({ error: "episode and a response or choice are required" }, 400);
      }
      if (name) {
        // 具名的回應一定要存到 name 欄；還沒跑 migrations/002_add_name.sql 就回 503，
        // 讓播放器提示「雲端還沒準備好」，而不是默默把名字丟掉
        try {
          await env.DB.prepare(
            "INSERT INTO responses (episode, question, response, choice, name, submitted_at) VALUES (?, ?, ?, ?, ?, ?)"
          ).bind(episode, question, response, choice || null, name, submittedAt).run();
        } catch (e) {
          if (!String(e).includes("name")) throw e;
          return json({ error: "name column missing; run migration 002" }, 503);
        }
        return json({ ok: true, named: true });
      }
      try {
        await env.DB.prepare(
          "INSERT INTO responses (episode, question, response, choice, submitted_at) VALUES (?, ?, ?, ?, ?)"
        ).bind(episode, question, response, choice || null, submittedAt).run();
      } catch (e) {
        // 還沒跑 migrations/001_add_choice.sql 的舊資料表沒有 choice 欄位：只存文字，
        // 只選了選項沒打字的那種回應就無處可存，回 503 讓播放器退回本機下載。
        if (!String(e).includes("choice")) throw e;
        if (!response) return json({ error: "choice column missing; run migration" }, 503);
        await env.DB.prepare(
          "INSERT INTO responses (episode, question, response, submitted_at) VALUES (?, ?, ?, ?)"
        ).bind(episode, question, response, submittedAt).run();
      }
      return json({ ok: true });
    }

    if (url.pathname === "/responses" && request.method === "GET") {
      if (env.SITE_KEY && request.headers.get("X-Site-Key") !== env.SITE_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      const episode = url.searchParams.get("episode");
      const query = (cols) => {
        const where = episode ? " WHERE episode = ?" : "";
        const stmt = env.DB.prepare(`SELECT ${cols} FROM responses${where} ORDER BY id DESC`);
        return (episode ? stmt.bind(episode) : stmt).all();
      };
      let results;
      try {
        ({ results } = await query("episode, question, response, choice, submitted_at"));
      } catch (e) {
        if (!String(e).includes("choice")) throw e;
        ({ results } = await query("episode, question, response, submitted_at"));
      }
      return json({ responses: results });
    }

    if (url.pathname === "/open-state" && request.method === "GET") {
      // 還沒建表（從沒在後台按過）就當作沒有任何手動設定
      try {
        const row = await env.DB.prepare("SELECT value FROM settings WHERE key = 'open_state'").first();
        return json({ state: row ? JSON.parse(row.value) : {} });
      } catch (e) {
        return json({ state: {} });
      }
    }

    if (url.pathname === "/admin/open-state" && request.method === "POST") {
      if (!env.ADMIN_KEY || request.headers.get("X-Admin-Key") !== env.ADMIN_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      const ep = String(body.ep || "").toLowerCase().replace(/[^0-9a-z]/g, "").slice(0, 20);
      if (!ep || ![true, false, null].includes(body.open)) {
        return json({ error: "ep and open (true/false/null) are required" }, 400);
      }
      await env.DB.prepare("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)").run();
      const row = await env.DB.prepare("SELECT value FROM settings WHERE key = 'open_state'").first();
      const state = row ? JSON.parse(row.value) : {};
      if (body.open === null) delete state[ep]; // null＝回到網頁上的預設（排程開放的日期）
      else state[ep] = body.open;
      await env.DB.prepare(
        "INSERT INTO settings (key, value) VALUES ('open_state', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
      ).bind(JSON.stringify(state)).run();
      return json({ ok: true, state });
    }

    if (url.pathname === "/admin/responses" && request.method === "GET") {
      // 沒設定 ADMIN_KEY 時一律拒絕，避免忘了設密碼就把具名資料公開出去
      if (!env.ADMIN_KEY || request.headers.get("X-Admin-Key") !== env.ADMIN_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      const episode = url.searchParams.get("episode");
      const where = episode ? " WHERE episode = ?" : "";
      const stmt = env.DB.prepare(
        `SELECT episode, question, response, choice, name, submitted_at FROM responses${where} ORDER BY id DESC`
      );
      try {
        const { results } = await (episode ? stmt.bind(episode) : stmt).all();
        return json({ responses: results });
      } catch (e) {
        if (!String(e).includes("name")) throw e;
        return json({ error: "name column missing; run migration 002" }, 503);
      }
    }

    if (url.pathname === "/respond" && request.method === "GET") {
      const episode = url.searchParams.get("ep") || "";
      const question = url.searchParams.get("q") || "";
      const html = respondPage(episode, question, env.SITE_KEY || "");
      return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8", ...CORS_HEADERS } });
    }

    return json({ error: "not found" }, 404);
  },
};
