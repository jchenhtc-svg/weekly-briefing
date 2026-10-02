/**
 * 週會宣導 — 回應收集用的 Cloudflare Worker
 *
 * 三個端點：
 *   POST /submit     寫入一則回應到 D1
 *   GET  /responses  讀出回應（可用 ?episode=xxx 篩選單一篇集）
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
  "Access-Control-Allow-Headers": "Content-Type, X-Site-Key",
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
      const submittedAt = new Date().toISOString();
      if (!episode || !response) {
        return json({ error: "episode and response are required" }, 400);
      }
      await env.DB.prepare(
        "INSERT INTO responses (episode, question, response, submitted_at) VALUES (?, ?, ?, ?)"
      ).bind(episode, question, response, submittedAt).run();
      return json({ ok: true });
    }

    if (url.pathname === "/responses" && request.method === "GET") {
      if (env.SITE_KEY && request.headers.get("X-Site-Key") !== env.SITE_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      const episode = url.searchParams.get("episode");
      const stmt = episode
        ? env.DB.prepare("SELECT episode, question, response, submitted_at FROM responses WHERE episode = ? ORDER BY id DESC").bind(episode)
        : env.DB.prepare("SELECT episode, question, response, submitted_at FROM responses ORDER BY id DESC");
      const { results } = await stmt.all();
      return json({ responses: results });
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
