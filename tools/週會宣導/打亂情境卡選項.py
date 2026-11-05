#!/usr/bin/env python3
"""把腳本情境卡的選項順序打亂，讓建議做法（分數總和最高的選項）不會老是在同一個位置。

用法（在 tools/週會宣導/ 底下）：
    python3 打亂情境卡選項.py 腳本/21-xxx.json 腳本/22-xxx.json
    python3 打亂情境卡選項.py --check 腳本/*.json 腳本-AI素養/*.json   # 只看建議做法在哪個位置，不改檔

做法：同一集的 3 張卡，建議做法的位置用亂數排成 A、B、C 各一次（卡片多於 3 張就每 3 張一輪）；
另外兩個選項的順序也用亂數決定。選項的文字、分數、結果都跟著一起搬，內容不變。

⚠️ 只能用在「還沒有人作答」的集數：資料庫存的是 A／B／C 字母，已經有人作答的集數改順序，
後台統計就會對到錯的選項。
"""
import json
import random
import sys
from pathlib import Path

LETTERS = "ABCDE"


def best_index(card):
    totals = [sum(o.get("score", {}).values()) for o in card["options"]]
    top = max(totals)
    tied = [i for i, v in enumerate(totals) if v == top]
    return tied[0] if len(tied) == 1 else None  # 平手（兩個都好）就不算有單一建議做法


def cards_of(ep):
    return ep.get("scenario_cards", []) + [c for ch in ep.get("chapters", []) for c in ch.get("scenarios", [])]


def positions(ep):
    out = []
    for c in cards_of(ep):
        b = best_index(c)
        out.append(LETTERS[b] if b is not None else "＝")
    return " ".join(out)


def shuffle_episode(ep, rng):
    cards = cards_of(ep)
    targets = []
    for c in cards:  # 每一輪（3 張）把 0、1、2 亂數排一次，當作建議做法要放的位置
        if not targets:
            targets = list(range(len(c["options"])))
            rng.shuffle(targets)
        b, n = best_index(c), len(c["options"])
        want = targets.pop()
        if b is None or want >= n:
            rng.shuffle(c["options"])
            continue
        rest = [o for i, o in enumerate(c["options"]) if i != b]
        rng.shuffle(rest)
        rest.insert(want, c["options"][b])
        c["options"] = rest


def main(argv):
    check = "--check" in argv
    paths = [Path(a) for a in argv if a != "--check"]
    if not paths:
        sys.exit(__doc__)
    rng = random.SystemRandom()
    for p in paths:
        ep = json.loads(p.read_text(encoding="utf-8"))
        if not cards_of(ep):
            continue
        before = positions(ep)
        if not check:
            shuffle_episode(ep, rng)
            p.write_text(json.dumps(ep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{p.name}：建議做法位置 {before}" + ("" if check else f" → {positions(ep)}"))


if __name__ == "__main__":
    main(sys.argv[1:])
