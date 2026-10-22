#!/usr/bin/env python3
"""把 Kaggle 跑出來的 <代號>_語音.zip 匯入網頁用的語音資料夾。

用法（在 tools/週會宣導/ 底下）：
    python3 預錄語音/匯入音檔.py ~/Downloads/11_語音.zip
然後照常跑 python3 產生網頁.py，有音檔的集數就會改放預錄語音（沒有音檔的句子照舊用瀏覽器唸）。

音檔放在 語音/<代號>/：每句一個 mp3（000.mp3、001.mp3…、quote.mp3）＋ 台詞.json。
台詞.json 記錄每個音檔錄的是哪一句；之後腳本改了某句，產生網頁時那一句會自動退回瀏覽器語音，
不會放出跟字幕對不上的舊錄音。zip 裡是 wav 也可以（需要 pip install lameenc 轉成 mp3）。
"""
import io
import json
import re
import sys
import wave
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VOICE_DIR = ROOT / "語音"


def wav_to_mp3(data):
    import lameenc  # 只有 zip 裡是 wav 才需要
    with wave.open(io.BytesIO(data)) as w:
        ch, rate, width, frames = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.readframes(w.getnframes())
    if width != 2:
        sys.exit("只支援 16-bit wav")
    enc = lameenc.Encoder()
    enc.set_bit_rate(48); enc.set_in_sample_rate(rate); enc.set_channels(ch); enc.set_quality(2)
    return enc.encode(frames) + enc.flush()


def main(argv):
    if not argv:
        sys.exit(__doc__)
    # --out 資料夾：匯到別的地方（例如 Breeze TTS 2 只做內部試聽，不要放進 語音/ 上網站）
    out_root = VOICE_DIR
    if "--out" in argv:
        k = argv.index("--out"); out_root = Path(argv[k + 1]); argv = argv[:k] + argv[k + 2:]
    engine = "Breeze TTS 2" if "breeze2" in Path(argv[0]).name.lower() else "BreezyVoice"
    z = zipfile.ZipFile(argv[0])
    names = [n for n in z.namelist() if re.search(r"\.(mp3|wav)$", n, re.I)]
    keys = {re.match(r"(?:.*/)?([0-9a-z]+)_(\d{3}|quote)\.", n, re.I).group(1).lower() for n in names
            if re.match(r"(?:.*/)?([0-9a-z]+)_(\d{3}|quote)\.", n, re.I)}
    if len(keys) != 1:
        sys.exit(f"zip 裡的檔名要像 11_000.mp3、11_quote.mp3（找到的代號：{sorted(keys) or '無'}）")
    key = keys.pop()
    lines_file = HERE / "輸出" / key / "台詞.json"
    if not lines_file.exists():
        sys.exit(f"找不到 {lines_file.relative_to(ROOT)}，請先跑 預錄語音/匯出Kaggle筆記本.py {key}")
    expected = json.loads(lines_file.read_text(encoding="utf-8"))["lines"]
    out = out_root / key
    out.mkdir(parents=True, exist_ok=True)
    done = {}
    for n in names:
        m = re.match(r"(?:.*/)?[0-9a-z]+_(\d{3}|quote)\.(mp3|wav)$", n, re.I)
        if not m:
            continue
        stem = f"{key}_{m.group(1)}"
        if stem not in expected:
            print(f"⚠️  {n} 對不上台詞，略過"); continue
        data = z.read(n)
        if m.group(2).lower() == "wav":
            data = wav_to_mp3(data)
        (out / f"{m.group(1)}.mp3").write_bytes(data)
        done[m.group(1)] = expected[stem]
    (out / "台詞.json").write_text(json.dumps({"key": key, "engine": engine, "lines": dict(sorted(done.items()))},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    missing = [s for s in expected if s.split("_", 1)[1] not in done]
    size = sum(p.stat().st_size for p in out.glob("*.mp3"))
    print(f"✅ {out}（{engine}）：{len(done)} / {len(expected)} 句，共 {size // 1024} KB" + (f"（缺 {missing}，這幾句照舊用瀏覽器唸）" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
