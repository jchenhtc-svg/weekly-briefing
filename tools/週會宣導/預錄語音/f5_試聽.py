#!/usr/bin/env python3
"""F5-TTS 技術預覽：用 Azure 語音當參考音，照 F5 旁白稿幫一集配音，給主辦人試聽比較。

平常不用自己跑：把集數代號寫進 預錄語音/f5試做.txt 再 push，
GitHub Actions（.github/workflows/f5-preview.yml）會在雲端 CPU 上跑完、把結果 commit 到 內部試聽/F5-第NN篇/。

⚠️ 只是內部試聽：結果不放網頁、不同步到公開的 weekly-briefing。
參考音用的是已經上網站的 Azure 合成語音（第十四篇），不是真人的聲音。
之後要換成真人錄的參考音，請在自己的電腦上用 media-tool（mediatool dub）跑，參考人聲不要上傳。

流程：
1. 參考音：預錄語音/F5參考音/<角色>.mp3（Azure 合成語音剪出來的，5～10 秒），文字在 參考音.json
2. 讀 預錄語音/輸出/<代號>/第NN篇_F5旁白稿.txt（匯出F5旁白稿.py 產生的）；沒有的話直接從腳本取台詞
3. 一段一段用 F5TTS_v1_Base 合成 → 每句一個 mp3、整集接起來一個 mp3、
   另外做一個「Azure 一句 → F5 同一句」交錯的比較檔

正式用（F5_PUBLISH=1；平常是在公開的 weekly-briefing 把代號寫進 預錄語音/f5要產生.txt 再 push，
由那邊的 .github/workflows/f5-tts.yml 跑，公開 repo 的 Actions 不算額度）：
每句長度對齊原本 Azure 版的長度（F5 自己估的長度常常講太快），
結果直接取代 語音/<代號>/ 的音檔，網頁播放的就是 F5 的聲音。
Azure 原本每句幾秒記在 台詞.json 的 durations，之後重跑也照這個長度。
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
VOICE_DIR = ROOT / "語音"

# 參考音：固定放在 預錄語音/F5參考音/<角色標籤>.mp3，文字在 參考音.json
# （從第十四篇、AI 素養第二堂的 Azure 語音剪出來的；固定一份，集數換成 F5 之後參考音也不會跟著變）
REF_DIR = HERE / "F5參考音"
TAGS = {"主持人": "主持人", "阿凱工程師": "阿凱", "主管": "主管", "客戶": "客戶", "AI助理": "AI助理"}


def sh(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_script(path):
    segs = []
    for block in path.read_text(encoding="utf-8").split("\n---\n"):
        body = [l for l in block.splitlines() if l.strip() and not l.startswith("#")]
        m = re.match(r"\[([\w-]+)\]\s*(.*)", " ".join(body))
        if m:
            text = re.sub(r"\{[^|}]*\|([^}]*)\}", r"\1", m.group(2))  # {顯示|念法} → 念法
            segs.append((m.group(1), text.strip()))
    return segs


def make_refs(work):
    info = json.loads((REF_DIR / "參考音.json").read_text(encoding="utf-8"))
    refs = {}
    for tag, item in info.items():
        wav = work / f"ref-{tag}.wav"
        sh("ffmpeg", "-y", "-i", str(REF_DIR / f"{tag}.mp3"), "-ar", "24000", "-ac", "1", str(wav))
        refs[tag] = (str(wav), item["text"])
    return refs


def segs_from_episode(code):
    """沒有旁白稿的集數，直接從腳本取台詞（順序跟網頁一樣，最後一段是金句、主持人唸）。"""
    sys.path.insert(0, str(ROOT))
    import 產生網頁 as gen
    ep = next((e for e in (json.loads(p.read_text(encoding="utf-8")) for p in gen.all_script_paths())
               if gen.ep_key(e) == code), None)
    if not ep:
        sys.exit(f"找不到集數 {code}")
    host = next((r["name"] for r in ep["roles"] if r.get("side") == "center"), ep["roles"][0]["name"])
    lines = [(l[0], l[1]) for sc in ep["scenes"] for l in sc["lines"]]
    lines.append((host, gen.plain_text(ep["golden_quote"]).replace(" ", "")))
    missing = {r for r, _ in lines if TAGS.get(r, r) not in json.loads((REF_DIR / "參考音.json").read_text(encoding="utf-8"))}
    if missing:
        sys.exit(f"這些角色沒有參考音：{'、'.join(missing)}（放進 預錄語音/F5參考音/）")
    return [(TAGS.get(r, r), t) for r, t in lines]


PAUSE = 1.2  # 只有「……」的台詞（停頓）：Azure 給的是空檔，這裡產生這麼長的靜音


def duration(path):
    if not Path(path).exists() or Path(path).stat().st_size == 0:
        return PAUSE
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else PAUSE


def speakable(text):
    return bool(re.search(r"[0-9A-Za-z\u3400-\u9fff]", text))


# 開頭靜音剪掉（保留 0.08 秒）：F5 被指定總長度時，多出來的時間常常變成句首的靜音
TRIM_HEAD = "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.08"


def target_durations(code, count):
    """每句要講幾秒：用 Azure 版的長度（已經換成 F5 的話，用當初記下來的）。"""
    folder = VOICE_DIR / code
    manifest = json.loads((folder / "台詞.json").read_text(encoding="utf-8")) if (folder / "台詞.json").exists() else {}
    if manifest.get("durations"):
        return manifest["durations"]
    names = [f"{n:03d}" for n in range(count - 1)] + ["quote"]
    if not all((folder / f"{n}.mp3").exists() for n in names):
        return None
    return {n: round(duration(folder / f"{n}.mp3"), 2) for n in names}


def main(argv):
    code = (argv or ["15"])[0]
    script = next((HERE / "輸出" / code).glob("*_F5旁白稿.txt"), None) if (HERE / "輸出" / code).is_dir() else None
    segs = parse_script(script) if script else segs_from_episode(code)
    out = REPO / "內部試聽" / f"F5-第{code}篇"
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)
    refs = make_refs(work)
    publish = os.environ.get("F5_PUBLISH") == "1"
    targets = target_durations(code, len(segs))
    names = [f"{n:03d}" for n in range(len(segs) - 1)] + ["quote"]
    if publish and not targets:
        sys.exit(f"語音/{code}/ 沒有 Azure 版可以對齊長度")

    import soundfile
    import torch
    import torchaudio

    def load(path, *a, **k):  # 跟 media-tool 一樣：torchaudio.load 改用 soundfile，不經 torchcodec
        data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T.copy()), rate
    torchaudio.load = load

    from concurrent.futures import ThreadPoolExecutor
    from f5_tts.infer import utils_infer
    if hasattr(utils_infer, "ThreadPoolExecutor"):
        utils_infer.ThreadPoolExecutor = lambda *a, **k: ThreadPoolExecutor(max_workers=1)
    from f5_tts.api import F5TTS

    t0 = time.monotonic()
    tts = F5TTS(model="F5TTS_v1_Base", device="cpu")
    print(f"[f5] 模型載入 {time.monotonic() - t0:.0f}s", flush=True)

    limit = int(os.environ.get("F5_LIMIT") or 0)
    wavs, silent = [], set()
    for i, (tag, text) in enumerate(segs[:limit] if limit else segs):
        ref_wav, ref_text = refs[tag]
        t = time.monotonic()
        wav = work / f"{i + 1:03d}-{tag}.wav"
        if not speakable(text):  # 純停頓：不叫 F5，直接放一段靜音
            secs = targets[names[i]] if publish and targets else PAUSE
            sh("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{secs:.2f}", str(wav))
            wavs.append(wav)
            silent.add(wav)
            print(f"[f5] {i + 1:03d}/{len(segs)} {tag} 停頓 {secs:.1f}s", flush=True)
            continue
        fix = None
        if publish and targets:  # 總長度＝參考音＋要講的這句（F5 的 fix_duration 是兩段合計）
            fix = duration(ref_wav) + targets[names[i]]
        tts.infer(ref_file=ref_wav, ref_text=ref_text, gen_text=text, file_wave=str(wav),
                  nfe_step=32, seed=1234, remove_silence=False, fix_duration=fix)
        wavs.append(wav)
        print(f"[f5] {i + 1:03d}/{len(segs)} {tag} {time.monotonic() - t:.0f}s：{text}", flush=True)

    for f in out.glob("*.mp3"):
        f.unlink()
    gap = work / "gap.wav"
    sh("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", str(gap))

    def concat(files, name):
        lst = work / (name + ".txt")
        lst.write_text("".join(f"file '{f}'\nfile '{gap}'\n" for f in files), encoding="utf-8")
        sh("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", "-b:a", "48k",
           str(out / f"{name}.mp3"))

    norm = []  # 先把每句統一成 24kHz 單聲道 wav，concat 才不會出錯
    for wav in wavs:
        n = work / f"n-{wav.name}"
        sh("ffmpeg", "-y", "-i", str(wav), *(["-af", TRIM_HEAD] if publish and wav not in silent else []), "-ar", "24000", "-ac", "1", str(n))
        norm.append(n)
    for wav, n in zip(wavs, norm):
        sh("ffmpeg", "-y", "-i", str(n), "-ar", "24000", "-ac", "1", "-b:a", "48k", str(out / (wav.stem + ".mp3")))
    concat(norm, f"第{code}篇_F5整集")
    azure = sorted((VOICE_DIR / code).glob("[0-9][0-9][0-9].mp3")) + [VOICE_DIR / code / "quote.mp3"]
    pairs = []
    for i, n in enumerate(norm[:6]):  # 前 6 句：Azure 一句 → F5 同一句
        if i < len(azure) and azure[i].exists():
            a = work / f"az-{i:03d}.wav"
            sh("ffmpeg", "-y", "-i", str(azure[i]), "-ar", "24000", "-ac", "1", str(a))
            pairs += [a, n]
    if pairs:
        concat(pairs, f"第{code}篇_比較_Azure對F5")
    if publish:
        folder = VOICE_DIR / code
        old = json.loads((folder / "台詞.json").read_text(encoding="utf-8"))
        for wav, name in zip(norm, names):
            sh("ffmpeg", "-y", "-i", str(wav), "-ar", "24000", "-ac", "1", "-b:a", "48k", str(folder / f"{name}.mp3"))
        manifest = {"engine": "F5-TTS（參考音＝Azure 語音）", "multi_voice": True, "lines": old["lines"],
                    "durations": targets}
        (folder / "台詞.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 語音/{code}/ 換成 F5 的聲音（{len(names)} 句）")
    for f in work.iterdir():
        f.unlink()
    work.rmdir()
    refs_desc = "、".join(f"{k}＝{v['來源']}" for k, v in json.loads((REF_DIR / "參考音.json").read_text(encoding="utf-8")).items())
    (out / "說明.txt").write_text(
        f"第{code}篇 F5-TTS 技術預覽（內部試聽，不放網站）\n"
        f"模型：F5TTS_v1_Base（CPU，nfe_step=32，seed=1234）\n"
        f"參考音：{refs_desc}\n"
        f"第{code}篇_F5整集.mp3：整集接起來\n"
        f"第{code}篇_比較_Azure對F5.mp3：前 6 句，每句先放 Azure、再放 F5\n"
        f"001～：每一句單獨的音檔（最後一個是金句）\n", encoding="utf-8")
    print(f"✅ 內部試聽/F5-第{code}篇/（{len(wavs)} 句，總共 {time.monotonic() - t0:.0f}s）")


if __name__ == "__main__":
    main(sys.argv[1:])
