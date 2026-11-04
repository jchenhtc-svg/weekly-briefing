#!/usr/bin/env python3
"""用微軟 Azure 語音（zh-TW 神經語音）幫集數產生預錄語音，存到 語音/<代號>/。

平常不用自己跑：把集數代號寫進 預錄語音/azure要產生.txt 再 push，
GitHub Actions（.github/workflows/azure-tts.yml）會用 repo secret 裡的金鑰產生語音、自動 commit 回來。

自己跑的話（需要金鑰，金鑰不要寫進任何檔案）：
    AZURE_SPEECH_KEY=… AZURE_SPEECH_REGION=eastasia python3 預錄語音/azure_tts.py 14 13
代號就是網頁網址 ?r= 後面那個（52 週是 14、AI 素養是 ai01…）；寫 all 代表全部集數。

每個角色用哪個聲音：看腳本角色的 voicePref（曉臻／雲哲／曉雨）對到 VOICES；
角色的 pitch／rate 換成 SSML 的語調、語速，讓同一個聲音的兩個角色（例如主管和客戶）聽得出差別。
已經產生過、台詞和聲音設定都沒變的句子會跳過，不會重複花額度。
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import 產生網頁 as gen  # noqa: E402  共用 ep_key()、腳本清單

VOICE_DIR = ROOT / "語音"
ENGINE = "Azure 語音（zh-TW 神經語音）"
VOICES = {"曉臻": "zh-TW-HsiaoChenNeural", "雲哲": "zh-TW-YunJheNeural", "曉雨": "zh-TW-HsiaoYuNeural"}
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"


def role_voice(role):
    """角色 → (聲音名稱, 語調 %, 語速 %)。沒寫 voicePref 就照音調猜男女聲。"""
    name = VOICES.get(role.get("voicePref", "")) or ("zh-TW-YunJheNeural" if role.get("pitch", 1) < 0.95 else "zh-TW-HsiaoChenNeural")
    pitch = max(-20, min(20, round((role.get("pitch", 1) - 1) * 30)))
    rate = max(-30, min(40, round((role.get("rate", 1) - 1) * 100)))
    return name, pitch, rate


def ssml(text, voice):
    name, pitch, rate = voice
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-TW">'
            f'<voice name="{name}"><prosody pitch="{pitch:+d}%" rate="{rate:+d}%">{escape(text)}</prosody></voice></speak>')


def synth(text, voice, key, endpoint):
    req = urllib.request.Request(endpoint, data=ssml(text, voice).encode("utf-8"), method="POST", headers={
        "Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": OUTPUT_FORMAT, "User-Agent": "weekly-briefing-tts"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit("Azure 拒絕了金鑰（HTTP %d）：請確認 AZURE_SPEECH_KEY 和 AZURE_SPEECH_REGION 是同一個語音資源的" % e.code)
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt * 3)
                continue
            sys.exit(f"Azure 回傳錯誤 HTTP {e.code}：{e.read()[:300]!r}")
        except urllib.error.URLError:
            time.sleep(2 ** attempt * 3)
    sys.exit("連不上 Azure 語音服務，重試多次都失敗")


def build(ep, key, endpoint):
    code = gen.ep_key(ep)
    folder = VOICE_DIR / code
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "台詞.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    old_sig = old.get("sig", {}) if old.get("engine") == ENGINE else {}
    roles = {r["name"]: role_voice(r) for r in ep["roles"]}
    lines = [l for sc in ep["scenes"] for l in sc["lines"]]
    host = next((r for r in ep["roles"] if r.get("side") == "center"), ep["roles"][0])["name"]
    jobs = [(f"{n:03d}", l[1], roles[l[0]]) for n, l in enumerate(lines)]
    jobs.append(("quote", ep["golden_quote"], roles[host]))
    out = {"engine": ENGINE, "multi_voice": True, "lines": {}, "sig": {}}
    made = skipped = 0
    for name, text, voice in jobs:
        spoken = gen.plain_text(text) if name == "quote" else text
        sig = hashlib.sha1(json.dumps([spoken, voice], ensure_ascii=False).encode()).hexdigest()[:12]
        mp3 = folder / f"{name}.mp3"
        if old_sig.get(name) == sig and mp3.exists():
            skipped += 1
        else:
            mp3.write_bytes(synth(spoken, voice, key, endpoint))
            made += 1
        out["lines"][name] = text  # 產生網頁.py 用這個核對「錄的是不是現在這句」
        out["sig"][name] = sig
    for f in folder.glob("*.mp3"):  # 腳本刪掉的句子，舊音檔一併清掉
        if f.stem not in out["lines"]:
            f.unlink()
    manifest_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(f.stat().st_size for f in folder.glob("*.mp3")) // 1024
    print(f"✅ {code}：新產生 {made} 句、沿用 {skipped} 句，共 {size} KB → 語音/{code}/")


def main(argv):
    key, region = os.environ.get("AZURE_SPEECH_KEY", ""), os.environ.get("AZURE_SPEECH_REGION", "")
    endpoint = os.environ.get("AZURE_TTS_ENDPOINT") or f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    if not key or not (region or os.environ.get("AZURE_TTS_ENDPOINT")):
        sys.exit("缺少 AZURE_SPEECH_KEY／AZURE_SPEECH_REGION（GitHub 上要在 repo 的 Settings → Secrets 設定）")
    wanted = [a.strip() for a in argv if a.strip()]
    if not wanted:
        sys.exit(__doc__)
    eps = [json.loads(p.read_text(encoding="utf-8")) for p in gen.all_script_paths()]
    eps = [e for e in eps if not e.get("chapters")]  # USB 課程模式另外處理，先不做
    pick = eps if "all" in wanted else [e for e in eps if gen.ep_key(e) in wanted]
    missing = set(wanted) - {"all"} - {gen.ep_key(e) for e in pick}
    if missing:
        sys.exit("找不到這些集數代號：" + "、".join(sorted(missing)))
    for ep in pick:
        build(ep, key, endpoint)


if __name__ == "__main__":
    main(sys.argv[1:])
