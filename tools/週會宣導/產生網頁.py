#!/usr/bin/env python3
"""把一集週會宣導腳本（JSON）產生成一個可雙擊播放的單檔 HTML。

播放引擎不在這裡，而是在技能 .claude/skills/ai-dialogue-podcast-builder/assets/template.html。
這支程式只做一件事：把腳本資料塞進那個範本，其他一律不動。
所以每週出新的一集，只要新增一個 JSON，不需要改網頁或改這支程式。

用法：
    python3 產生網頁.py                      # 產生 腳本/ 底下全部（公開版，網頁/，會進 git）
    python3 產生網頁.py 腳本/04-*.json        # 只產生指定的一集
    python3 產生網頁.py --cloud               # 額外產生連得到 Cloudflare 的「雲端版」到
                                              # 網頁-雲端版/（讀 cloudflare/local-config.json，
                                              # 這兩個都在 .gitignore 裡，絕不會進 git）
"""

import base64
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = REPO / ".claude" / "skills" / "ai-dialogue-podcast-builder" / "assets" / "template.html"
SCRIPT_DIR = HERE / "腳本"
OUT_DIR = HERE / "網頁"
CLOUD_OUT_DIR = HERE / "網頁-雲端版"  # .gitignore 排除，絕不進版控
CLOUD_CONFIG = HERE / "cloudflare" / "local-config.json"  # 同樣排除在外

# 範本裡「資料區」的頭尾，中間整段會被換掉；引擎與樣式維持原樣。
DATA_START = "const ROLES = {"
DATA_END = "// flatten SCRIPT into d[]"

WRAP_END = "\n</div>\n\n<script>\n"


def js(value):
    """轉成安全的 JS 字面值（中文不轉義，比較好讀也好除錯）。"""
    return json.dumps(value, ensure_ascii=False)


def build_data_block(ep):
    roles = ep["roles"]

    role_lines = []
    for r in roles:
        voice_pref = f', voicePref:{js(r["voicePref"].lower())}' if r.get("voicePref") else ""
        role_lines.append(
            '  {name}: {{key:"{key}", color:"{color}", basePitch:{pitch:.2f}, '
            'baseRate:{rate:.2f}, avatar:"{avatar}", side:"{side}"{voice_pref}}}'.format(
                name=js(r["name"]), key=r["key"], color=r["color"],
                pitch=r["pitch"], rate=r["rate"], avatar=r["avatar"], side=r["side"],
                voice_pref=voice_pref,
            )
        )

    scene_blocks = []
    for scene in ep["scenes"]:
        out = []
        for line in scene["lines"]:
            role, text = line[0], line[1]
            meta = line[2] if len(line) > 2 else None
            if meta:
                parts = ", ".join(f"{k}:{js(v)}" for k, v in meta.items())
                out.append(f"  [{js(role)}, {js(text)}, {{{parts}}}]")
            else:
                out.append(f"  [{js(role)}, {js(text)}]")
        scene_blocks.append(
            '{{bg:"{bg}", tag:{tag}, icon:"{icon}", lines:[\n{lines}\n]}}'.format(
                bg=scene["bg"], tag=js(scene["tag"]), icon=scene["icon"],
                lines=",\n".join(out),
            )
        )

    return (
        "const ROLES = {\n" + ",\n".join(role_lines) + "\n};\n"
        + "const ROLE_ORDER = " + js([r["name"] for r in roles]) + ";\n"
        + "const DEFAULT_EXPR = "
        + js({r["name"]: r["expr"] for r in roles}) + ";\n\n"
        + "const SCRIPT = [\n" + ",\n".join(scene_blocks) + "\n];\n\n"
        + "const GOLDEN_QUOTE = " + js(ep["golden_quote"]) + ";\n"
        + "const MANAGER_QUESTION = " + js(ep["manager_question"]) + ";\n"
        + "const EPISODE_LABEL = " + js(f'{ep_num(ep)}_{ep["title"]}') + ";\n\n"
    )


def build_masthead(ep):
    chips = "\n".join(
        '      <div class="chip"><span class="dot {key}">{avatar}</span>{chip}</div>'.format(
            key=r["key"], avatar=r["avatar"], chip=r["chip"]
        )
        for r in ep["roles"]
    )
    return (
        '  <div class="masthead">\n'
        f'    <div class="idplate">EP {ep_num(ep)}</div>\n'
        f'    <div class="kicker"><span class="led"></span>《{ep["series"]}》{ep["episode_label"]}晨會宣導</div>\n'
        f'    <h1>{ep["title"]}</h1>\n'
        f'    <div class="sub">{ep["subtitle"]}</div>\n'
        f'    <div class="cast">\n{chips}\n    </div>\n'
        '  </div>\n'
    )


def build_prep_card(ep):
    notes = ep.get("prep_notes")
    if not notes:
        return ""
    items = "\n".join(f"      <li>{n}</li>" for n in notes)
    return (
        '\n  <div class="card">\n'
        '    <div id="prepHead" class="panel-head" onclick="togglePrep()">\n'
        '      <h2>主管備課筆記（不會播出）</h2>\n'
        '      <span class="arrow">▾</span>\n'
        '    </div>\n'
        '    <div id="prepBody" class="panel-body">\n'
        '      <ul style="margin:0;padding-left:20px;line-height:1.85;'
        'font-size:13.5px;color:var(--sub);font-weight:500">\n'
        f'{items}\n'
        '      </ul>\n'
        '    </div>\n'
        '  </div>\n'
    )


PREP_TOGGLE_JS = """
function togglePrep(){
  document.getElementById("prepHead").classList.toggle("open");
  document.getElementById("prepBody").classList.toggle("open");
}
"""


def plain_text(html_fragment):
    """把 golden_quote/manager_question 裡的 <br> 等標籤去掉，跟播放器 JS 端的處理邏輯對齊。"""
    return re.sub(r"<[^>]+>", " ", html_fragment).strip()


def make_qr_data_uri(url):
    """用 qrcode 套件產生 SVG QR Code，回傳可以直接放進 <img src> 的 base64 data URI。
    刻意不在瀏覽器裡用 JS 即時產生 QR Code（手刻編碼演算法容易做出「像但掃不出來」的圖），
    改成這裡用成熟、驗證過的套件先產生好，包進雲端版網頁。"""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        sys.exit(
            "--cloud 需要 qrcode 套件才能產生 QR Code：\n"
            "    pip install qrcode\n"
            "裝好之後重新執行一次 --cloud。"
        )
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def render(ep, template, cloud_config=None):
    start = template.index(DATA_START)
    end = template.index(DATA_END)
    html = template[:start] + build_data_block(ep) + template[end:]

    if cloud_config:
        html = re.sub(
            r'const RESPONSE_API_BASE = ".*?";',
            f'const RESPONSE_API_BASE = {js(cloud_config["apiBase"])};',
            html, count=1,
        )
        html = re.sub(
            r'const RESPONSE_SITE_KEY = ".*?";',
            f'const RESPONSE_SITE_KEY = {js(cloud_config["siteKey"])};',
            html, count=1,
        )
        episode_label = f'{ep_num(ep)}_{ep["title"]}'
        # 只帶 ep（集數標籤），不帶完整問題文字：CJK 經過 URL 編碼會膨脹約 9 倍，
        # 問題全文塞進去會讓 QR Code 密度太高、印出來/顯示在小尺寸時掃不出來。
        # 手機頁面改用通用提示語，因為看的人剛剛已經在共用畫面上看過/聽過問題了。
        respond_url = (
            cloud_config["apiBase"].rstrip("/") + "/respond"
            + f"?ep={quote(episode_label)}"
        )
        html = re.sub(
            r'const RESPONSE_QR_IMG = ".*?";',
            f'const RESPONSE_QR_IMG = {js(make_qr_data_uri(respond_url))};',
            html, count=1,
        )
        html = re.sub(
            r'const RESPONSE_QR_URL = ".*?";',
            f'const RESPONSE_QR_URL = {js(respond_url)};',
            html, count=1,
        )

    # 標題列
    html = re.sub(
        r"<title>.*?</title>",
        f'<title>《{ep["series"]}》{ep["episode_label"]}｜{ep["title"]}</title>',
        html, count=1, flags=re.S,
    )
    html = re.sub(
        r'  <div class="masthead">.*?\n  </div>\n',
        lambda _: build_masthead(ep),
        html, count=1, flags=re.S,
    )

    # 說明文字
    html = re.sub(
        r'<div class="hint">.*?</div>',
        '<div class="hint">按「執行播放」會自動一段接一段唸完整集，'
        '字幕跟著唸到的地方變色。四個角色各有自己的聲音、音調與語速，'
        '可以在下面的「配音設定」逐一調整；RATE 是整體語速（0.75×～1.5×）。'
        '播完會停在今日金句，再按一次播放就從頭重播。</div>',
        html, count=1, flags=re.S,
    )

    prep = build_prep_card(ep)
    if prep:
        html = html.replace(WRAP_END, prep + WRAP_END, 1)
        html = html.replace("\nfunction togglePanel(){", PREP_TOGGLE_JS + "\nfunction togglePanel(){", 1)

    return html


def ep_num(ep):
    """集數編號可以是整數（04）或字串（像示範版的 '6b'），兩種都要能顯示。"""
    n = ep["episode"]
    return f'{n:02d}' if isinstance(n, int) else str(n)


def out_name(ep):
    return f'第{ep_num(ep)}週_{ep["title"]}.html'


def main(argv):
    if not TEMPLATE.exists():
        sys.exit(f"找不到播放器範本：{TEMPLATE}\n請確認技能 ai-dialogue-podcast-builder 已在 .claude/skills/ 底下。")

    cloud_mode = "--cloud" in argv
    argv = [a for a in argv if a != "--cloud"]

    targets = [Path(a) for a in argv] or sorted(SCRIPT_DIR.glob("*.json"))
    if not targets:
        sys.exit(f"{SCRIPT_DIR} 底下沒有腳本 JSON。")

    template = TEMPLATE.read_text(encoding="utf-8")
    OUT_DIR.mkdir(exist_ok=True)

    for path in targets:
        ep = json.loads(path.read_text(encoding="utf-8"))
        dest = OUT_DIR / out_name(ep)
        dest.write_text(render(ep, template), encoding="utf-8")
        n = sum(len(s["lines"]) for s in ep["scenes"])
        print(f"✅ {path.name} → 網頁/{dest.name}（{len(ep['scenes'])} 幕 / {n} 段對話）")

    print("\n產生完成。雙擊「網頁」資料夾裡的 .html 就能播放，不需要安裝任何東西。")

    if cloud_mode:
        if not CLOUD_CONFIG.exists():
            sys.exit(
                f"\n--cloud 需要 {CLOUD_CONFIG} 這個檔案（不進版控），"
                "裡面放 apiBase 跟 siteKey。"
            )
        cloud_config = json.loads(CLOUD_CONFIG.read_text(encoding="utf-8"))
        CLOUD_OUT_DIR.mkdir(exist_ok=True)
        print(f"\n另外產生連得到雲端的版本（{CLOUD_OUT_DIR.name}/，不會進 git）：")
        for path in targets:
            ep = json.loads(path.read_text(encoding="utf-8"))
            dest = CLOUD_OUT_DIR / out_name(ep)
            dest.write_text(render(ep, template, cloud_config), encoding="utf-8")
            print(f"☁️  {path.name} → {CLOUD_OUT_DIR.name}/{dest.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
