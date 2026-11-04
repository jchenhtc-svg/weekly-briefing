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
 *   GET/POST /admin/settings?key=roster  主辦人在後台存的學員名單（應完成名單），要帶 X-Admin-Key；
 *                    名單有真名，所以只放在 D1、不寫進任何網頁或 repo
 *   GET/POST /admin/site-lead  主辦人替每個據點設「據點長密碼」（POST {region, password}，password 空白＝取消）；
 *                    只存 SHA-256 雜湊，GET 只回「哪些據點設好了」，不回密碼
 *   GET  /lead/data  據點長用自己的密碼（X-Lead-Key）登入：只回自己據點的名單與真名；
 *                    其他據點的人換成代號（台南-A…），名單外的具名紀錄拿掉名字——其他據點的真名不會送到據點長的瀏覽器
 *   GET  /meeting/state  據點長例會（南部據點長②）：例會清單、某一場的各據點報告／臨時動議、全部待辦；
 *                    要帶管理密碼（X-Admin-Key）或據點長密碼（X-Lead-Key）
 *   POST /meeting/save   寫入例會資料（type = meeting｜report｜motion｜todo）：
 *                    例會本身（日期、出席、決議、紀錄）只有主辦人能改；據點長只能寫自己據點的報告、
 *                    自己提的臨時動議、自己據點待辦的狀態
 *   POST /meeting/todo   新增／修改／刪除待辦（主辦人全部可改；據點長只能改自己據點待辦的狀態與備註）
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
  "Access-Control-Allow-Headers": "Content-Type, X-Site-Key, X-Admin-Key, X-Lead-Key",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS },
  });
}

// ==== 據點長（南部據點長專案）====
// 名單格式跟後台一樣：一行一個地區「地區：名字、名字1234…」（名字後可附社編）
function parseRoster(text) {
  const out = [];
  String(text || "").split(/\n+/).forEach((line) => {
    const m = line.match(/^\s*([^：:]+)[：:](.*)$/);
    const region = m ? m[1].trim() : "";
    (m ? m[2] : line).split(/[、,，\s]+/).map((x) => x.trim()).filter(Boolean).forEach((item) => {
      const mm = item.match(/^(.*?)[（(]?(\d{2,12})[）)]?$/);
      out.push(mm && mm[1] ? { region, name: mm[1], id: mm[2] } : { region, name: item.replace(/[（()）]/g, ""), id: "" });
    });
  });
  return out;
}
// 學員填的「名字＋社編」對到名單上的人（跟後台 memberOwns 同一套規則）
const namePart = (n) => String(n).replace(/\d+$/, "");
const idPart = (n) => (String(n).match(/\d+$/) || [""])[0];
const memberOwns = (m, name) => namePart(name).endsWith(m.name) || (!!m.id && idPart(name) === m.id);
async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const leadHash = (region, password) => sha256(`site-lead:${region}:${password}`);
async function getSetting(env, key) {
  await env.DB.prepare("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)").run();
  const row = await env.DB.prepare("SELECT value FROM settings WHERE key = ?").bind(key).first();
  return row ? row.value : "";
}
async function putSetting(env, key, value) {
  await env.DB.prepare(
    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
  ).bind(key, value).run();
}
const CODE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// ==== 據點長例會（南部據點長②）：存在 D1 的 meeting_kv（一筆一個 key，各據點各寫各的，不會互相蓋掉）====
//   meeting:<日期>          {date, attendance, decisions, note, minutes, closed}（主辦人）
//   report:<日期>:<據點>     {work, issues, staff, needs}（該據點長或主辦人）
//   motion:<日期>:<id>      {region, text, at}（提案的據點長或主辦人）
//   todo:<id>               {text, region, due, status, note, from}（主辦人建；負責據點長可改狀態與備註）
const MEET_DDL = "CREATE TABLE IF NOT EXISTS meeting_kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)";
const TODO_STATUS = ["未開始", "進行中", "完成", "延期"];
const clip = (v, n) => String(v ?? "").slice(0, n);
const isDate = (d) => /^\d{4}-\d{2}-\d{2}$/.test(String(d || ""));
async function whoIs(request, env) {
  const ak = request.headers.get("X-Admin-Key");
  if (ak && env.ADMIN_KEY && ak === env.ADMIN_KEY) return { admin: true, region: "" };
  const lk = request.headers.get("X-Lead-Key") || "";
  if (!lk) return null;
  const leads = JSON.parse((await getSetting(env, "site_leads")) || "{}");
  for (const r of Object.keys(leads)) {
    if ((await leadHash(r, lk)) === leads[r]) return { admin: false, region: r };
  }
  return null;
}
async function kvGet(env, key) {
  const row = await env.DB.prepare("SELECT value FROM meeting_kv WHERE key = ?").bind(key).first();
  return row ? JSON.parse(row.value) : null;
}
async function kvPut(env, key, value) {
  await env.DB.prepare(
    "INSERT INTO meeting_kv (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
  ).bind(key, JSON.stringify(value), new Date().toISOString()).run();
}
async function kvPrefix(env, prefix) {
  const { results } = await env.DB.prepare("SELECT key, value, updated_at FROM meeting_kv WHERE key >= ? AND key < ? ORDER BY key")
    .bind(prefix, prefix + "\uffff").all();
  return results.map((r) => ({ key: r.key, updated_at: r.updated_at, ...JSON.parse(r.value) }));
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

    if (url.pathname === "/admin/settings") {
      if (!env.ADMIN_KEY || request.headers.get("X-Admin-Key") !== env.ADMIN_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      const key = url.searchParams.get("key") || "";
      if (!["roster"].includes(key)) return json({ error: "unknown key" }, 400);
      await env.DB.prepare("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)").run();
      if (request.method === "GET") {
        const row = await env.DB.prepare("SELECT value FROM settings WHERE key = ?").bind(key).first();
        return json({ value: row ? row.value : "" });
      }
      if (request.method === "POST") {
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "invalid json" }, 400);
        }
        const value = String(body.value || "").slice(0, 20000);
        await env.DB.prepare(
          "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        ).bind(key, value).run();
        return json({ ok: true });
      }
    }

    if (url.pathname === "/admin/site-lead") {
      if (!env.ADMIN_KEY || request.headers.get("X-Admin-Key") !== env.ADMIN_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
      const leads = JSON.parse((await getSetting(env, "site_leads")) || "{}");
      if (request.method === "GET") return json({ regions: Object.keys(leads) });
      if (request.method === "POST") {
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "invalid json" }, 400);
        }
        const region = String(body.region || "").trim().slice(0, 20);
        const password = String(body.password || "");
        if (!region) return json({ error: "region required" }, 400);
        if (!password) delete leads[region];
        else if (password.length < 6) return json({ error: "password too short" }, 400);
        else if (password === env.ADMIN_KEY) return json({ error: "same as admin key" }, 400);
        else leads[region] = await leadHash(region, password);
        await putSetting(env, "site_leads", JSON.stringify(leads));
        return json({ ok: true, regions: Object.keys(leads) });
      }
    }

    if (url.pathname === "/lead/data" && request.method === "GET") {
      const password = request.headers.get("X-Lead-Key") || "";
      const leads = JSON.parse((await getSetting(env, "site_leads")) || "{}");
      let region = "";
      if (password) {
        for (const r of Object.keys(leads)) {
          if ((await leadHash(r, password)) === leads[r]) { region = r; break; }
        }
      }
      if (!region) return json({ error: "unauthorized" }, 401);
      const roster = parseRoster(await getSetting(env, "roster"));
      // 自己據點：保留名單上的名（不帶社編）；其他據點：換成「地區-A」代號
      const count = {};
      const shown = roster.map((m) => {
        if (m.region === region) return { region: m.region, name: m.name, id: "" };
        const k = (count[m.region] = (count[m.region] || 0) + 1) - 1;
        return { region: m.region, name: `${m.region}-${CODE_LETTERS[k % 26]}${k >= 26 ? Math.floor(k / 26) : ""}`, id: "" };
      });
      const { results } = await env.DB.prepare(
        "SELECT episode, question, response, choice, name, submitted_at FROM responses ORDER BY id DESC"
      ).all();
      const rows = results.map((r) => {
        if (!r.name) return r;
        const k = roster.findIndex((m) => memberOwns(m, r.name));
        return Object.assign({}, r, { name: k < 0 ? null : shown[k].name });
      });
      return json({ region, roster: shown, responses: rows });
    }

    if (url.pathname === "/meeting/state" && request.method === "GET") {
      const who = await whoIs(request, env);
      if (!who) return json({ error: "unauthorized" }, 401);
      await env.DB.prepare(MEET_DDL).run();
      const meetings = (await kvPrefix(env, "meeting:")).sort((a, b) => b.date.localeCompare(a.date));
      const want = url.searchParams.get("date");
      const cur = meetings.find((m) => m.date === want) || meetings[0] || null;
      const reports = {}, motions = [];
      if (cur) {
        (await kvPrefix(env, `report:${cur.date}:`)).forEach((r) => { reports[r.key.split(":")[2]] = r; });
        (await kvPrefix(env, `motion:${cur.date}:`)).forEach((m) => motions.push({ id: m.key.split(":")[2], ...m }));
      }
      const todos = (await kvPrefix(env, "todo:")).map((t) => ({ id: t.key.slice(5), ...t }));
      return json({ admin: who.admin, region: who.region, dates: meetings.map((m) => m.date), meeting: cur, reports, motions, todos });
    }

    if (url.pathname === "/meeting/save" && request.method === "POST") {
      const who = await whoIs(request, env);
      if (!who) return json({ error: "unauthorized" }, 401);
      let b;
      try {
        b = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      await env.DB.prepare(MEET_DDL).run();
      const date = String(b.date || "");
      const meeting = isDate(date) ? await kvGet(env, `meeting:${date}`) : null;
      const forbid = () => json({ error: "forbidden" }, 403);
      if (b.type === "meeting") {
        if (!who.admin) return forbid();
        if (!isDate(date)) return json({ error: "bad date" }, 400);
        if (b.delete) {
          await env.DB.prepare("DELETE FROM meeting_kv WHERE key = ? OR key LIKE ? OR key LIKE ?")
            .bind(`meeting:${date}`, `report:${date}:%`, `motion:${date}:%`).run();
          return json({ ok: true });
        }
        const m = Object.assign({ date, attendance: [], decisions: [], note: "", minutes: "", closed: false }, meeting || {});
        if (Array.isArray(b.attendance)) m.attendance = b.attendance.slice(0, 20).map((x) => clip(x, 20));
        if (Array.isArray(b.decisions)) m.decisions = b.decisions.slice(0, 100).map((d) => ({ id: clip(d.id, 20), text: clip(d.text, 1000), todo: clip(d.todo, 20) }));
        if ("note" in b) m.note = clip(b.note, 5000);
        if ("minutes" in b) m.minutes = clip(b.minutes, 50000);
        if ("closed" in b) m.closed = !!b.closed;
        await kvPut(env, `meeting:${date}`, m);
        return json({ ok: true, meeting: m });
      }
      if (!meeting) return json({ error: "no such meeting" }, 404);
      if (b.type === "report") {
        const region = who.admin ? clip(b.region, 20) : who.region;
        if (!region) return json({ error: "region required" }, 400);
        if (meeting.closed && !who.admin) return json({ error: "closed" }, 409);
        const r = { work: clip(b.work, 3000), issues: clip(b.issues, 3000), staff: clip(b.staff, 3000), needs: clip(b.needs, 3000) };
        await kvPut(env, `report:${date}:${region}`, r);
        return json({ ok: true });
      }
      if (b.type === "motion") {
        if (b.delete) {
          const old = await kvGet(env, `motion:${date}:${clip(b.id, 20)}`);
          if (!old) return json({ ok: true });
          if (!who.admin && old.region !== who.region) return forbid();
          await env.DB.prepare("DELETE FROM meeting_kv WHERE key = ?").bind(`motion:${date}:${clip(b.id, 20)}`).run();
          return json({ ok: true });
        }
        const text = clip(b.text, 1000).trim();
        if (!text) return json({ error: "empty" }, 400);
        const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        await kvPut(env, `motion:${date}:${id}`, { region: who.admin ? clip(b.region || "主辦人", 20) : who.region, text, at: new Date().toISOString() });
        return json({ ok: true, id });
      }
      return json({ error: "unknown type" }, 400);
    }

    if (url.pathname === "/meeting/todo" && request.method === "POST") {
      const who = await whoIs(request, env);
      if (!who) return json({ error: "unauthorized" }, 401);
      let b;
      try {
        b = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      await env.DB.prepare(MEET_DDL).run();
      const id = clip(b.id, 20);
      const old = id ? await kvGet(env, `todo:${id}`) : null;
      if (b.delete) {
        if (!who.admin) return json({ error: "forbidden" }, 403);
        await env.DB.prepare("DELETE FROM meeting_kv WHERE key = ?").bind(`todo:${id}`).run();
        return json({ ok: true });
      }
      const status = TODO_STATUS.includes(b.status) ? b.status : (old && old.status) || "未開始";
      if (!who.admin) {
        // 據點長只能改自己據點待辦的狀態和備註
        if (!old || old.region !== who.region) return json({ error: "forbidden" }, 403);
        await kvPut(env, `todo:${id}`, Object.assign(old, { status, note: clip(b.note ?? old.note, 1000) }));
        return json({ ok: true });
      }
      const t = Object.assign({ text: "", region: "", due: "", status: "未開始", note: "", from: "" }, old || {});
      if ("text" in b) t.text = clip(b.text, 1000).trim();
      if ("region" in b) t.region = clip(b.region, 20);
      if ("due" in b) t.due = isDate(b.due) ? b.due : "";
      if ("note" in b) t.note = clip(b.note, 1000);
      if ("from" in b && !old) t.from = isDate(b.from) ? b.from : "";
      t.status = status;
      if (!t.text) return json({ error: "empty" }, 400);
      const newId = id || Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      await kvPut(env, `todo:${newId}`, t);
      return json({ ok: true, id: newId });
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
