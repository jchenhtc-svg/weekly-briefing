#!/usr/bin/env python3
"""把一集腳本轉成 media-tool `mediatool dub`（F5-TTS）用的旁白稿，在自己的電腦上配音。

用法（在 tools/週會宣導/ 底下）：
    python3 預錄語音/匯出F5旁白稿.py 腳本/15-想離職的那個月.json
輸出：預錄語音/輸出/<代號>/第NN篇_F5旁白稿.txt

旁白稿一句台詞一段（`---` 分隔），段首 `[角色]` 指定聲音，最後一段是金句（主持人唸）。
段落順序跟網頁的台詞編號一樣：dub 產生的 segments/001-*.wav 就是第 0 句、002 是第 1 句……
最後一個是金句，之後要放進網頁時可以直接對應。

角色標籤預設：主持人→[主持人]、阿凱工程師→[阿凱]、主管→[主管]、客戶→[客戶]。
你在 media-tool 錄音室（mediatool voice studio）錄的角色名稱不一樣的話，用 --map 改，例如：
    python3 預錄語音/匯出F5旁白稿.py 腳本/15-xxx.json --map 主持人=main --map 阿凱工程師=kai

F5-TTS 遇到阿拉伯數字、英文縮寫容易念錯：台詞裡有的話會寫成 {顯示|念法} 的提示，請手動補念法。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import 產生網頁 as gen  # noqa: E402

DEFAULT_TAGS = {"主持人": "主持人", "阿凱工程師": "阿凱", "主管": "主管", "客戶": "客戶"}


def main(argv):
    paths = [a for a in argv if not a.startswith("--") and "=" not in a]
    maps = [a.split("=", 1) for a in argv if "=" in a]
    if len(paths) != 1:
        sys.exit(__doc__)
    tags = dict(DEFAULT_TAGS, **{k: v for k, v in maps})
    ep = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    lines = [(l[0], l[1]) for sc in ep["scenes"] for l in sc["lines"]]
    host = next((r["name"] for r in ep["roles"] if r.get("side") == "center"), ep["roles"][0]["name"])
    lines.append((host, gen.plain_text(ep["golden_quote"]).replace(" ", "")))
    blocks, warn = [], []
    for n, (role, text) in enumerate(lines):
        tag = tags.get(role, role)
        if not re.fullmatch(r"[\w-]+", tag):
            sys.exit(f"角色標籤「{tag}」只能用文字、數字、底線或連字號（media-tool 的規定）")
        if re.search(r"[0-9A-Za-z]", text):
            warn.append(f"第 {n + 1} 段有數字或英文，請改成 {{顯示|念法}}：{text}")
        label = "金句" if n == len(lines) - 1 else f"第 {n} 句"
        blocks.append(f"# {n + 1:03d}｜{label}｜{role}\n[{tag}] {text}")
    code = gen.ep_key(ep)
    out = HERE / "輸出" / code / f"第{code}篇_F5旁白稿.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    head = (f"# 《{ep['title']}》F5-TTS 旁白稿（{len(lines)} 段；由 匯出F5旁白稿.py 產生）\n"
            f"# 用到的聲音：{'、'.join(sorted({tags.get(r, r) for r, _ in lines}))}\n")
    out.write_text(head + "\n---\n".join(blocks) + "\n", encoding="utf-8")
    print(f"✅ {out.relative_to(HERE.parent)}（{len(lines)} 段）")
    for w in warn:
        print("⚠️", w)


if __name__ == "__main__":
    main(sys.argv[1:])
