#!/usr/bin/env python3
"""把一集的台詞匯出成 Kaggle 筆記本，用開源的 BreezyVoice（聯發創新基地，Apache 2.0）預錄語音。

用法（在 tools/週會宣導/ 底下）：
    python3 預錄語音/匯出Kaggle筆記本.py 11          # 52 週第十一篇
    python3 預錄語音/匯出Kaggle筆記本.py ai01        # AI 素養第一堂

會產生 預錄語音/輸出/<代號>/BreezyVoice_<代號>.ipynb：
  1. 到 Kaggle 新增 Notebook → File → Import Notebook 上傳這個檔
  2. 右側 Settings：Accelerator 選 GPU（T4），Internet 打開（第一次要手機驗證）
  3. Run All，跑完下載 /kaggle/working/<代號>_語音.zip
  4. 把 zip 交給 Claude（或自己跑 預錄語音/匯入音檔.py），網頁就會改用預錄語音

試做階段所有角色都用官方範例聲音 example.wav（女聲）；網頁播放時男聲角色會降速降調區分。
之後要換成同事錄的聲音，在 VOICES 指定每個角色用哪個檔（記得先取得本人同意）。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT_DIRS = [ROOT / "腳本", ROOT / "腳本-AI素養"]

# 角色 → 參考聲音（BreezyVoice repo 裡 data/ 的檔名，不含 .wav）與那段錄音的逐字稿
OFFICIAL_EXAMPLE = ("example", "在密碼學中，加密是將明文資訊改變為難以讀取的密文內容，使之不可讀的方法。"
                               "只有擁有解密方法的對象，經由解密過程，才能將密文還原為正常可讀的內容。")
VOICES = {}  # 例：{"主持人": ("host", "這段錄音的逐字稿……")}；沒列到的角色用官方範例


def speech_text(text):
    """跟播放引擎的 speechText() 一樣的唸法處理：去掉標籤、SOP／AI 一個字母一個字母唸。"""
    text = re.sub(r"<br\s*/?>", "，", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"([，。！？、；：])，", r"\1", text)  # 換行前本來就有標點，就不要再多一個逗號
    text = text.replace("SOP", "S O P")
    return re.sub(r"(^|[^A-Za-z])AI(?![A-Za-z])", r"\1A I", text).strip()


def find_episode(key):
    for d in SCRIPT_DIRS:
        for p in sorted(d.glob("*.json")):
            ep = json.loads(p.read_text(encoding="utf-8"))
            k = ep["id"].lower() if ep.get("id") else (f'{ep["episode"]:02d}' if isinstance(ep["episode"], int) else str(ep["episode"]))
            if k == key.lower():
                return k, ep
    sys.exit(f"找不到代號 {key} 的腳本（52 週用 11、AI 素養用 ai01）")


def rows_for(key, ep):
    lines = [l for sc in ep["scenes"] for l in sc["lines"]]
    rows = []
    for n, line in enumerate(lines):
        role, text = line[0], line[1]
        voice, transcript = VOICES.get(role, OFFICIAL_EXAMPLE)
        rows.append({"speaker_prompt_audio_filename": voice, "speaker_prompt_text_transcription": transcript,
                     "content_to_synthesize": speech_text(text), "output_audio_filename": f"{key}_{n:03d}",
                     "role": role, "text": text})
    host = "主持人" if any(l[0] == "主持人" for l in lines) else lines[-1][0]
    voice, transcript = VOICES.get(host, OFFICIAL_EXAMPLE)
    rows.append({"speaker_prompt_audio_filename": voice, "speaker_prompt_text_transcription": transcript,
                 "content_to_synthesize": speech_text(ep["golden_quote"]), "output_audio_filename": f"{key}_quote",
                 "role": host, "text": ep["golden_quote"]})
    return rows


def notebook(key, title, rows):
    csv_rows = [{k: r[k] for k in ("speaker_prompt_audio_filename", "speaker_prompt_text_transcription",
                                   "content_to_synthesize", "output_audio_filename")} for r in rows]
    cells = [
        f"# BreezyVoice 預錄語音：{title}\n"
        "# 右側 Settings：Accelerator 選 GPU、Internet 打開，然後 Run All。\n"
        "# 跑完到右側 Output 下載 /kaggle/working/" + key + "_語音.zip\n"
        "import os, subprocess, sys\n"
        "os.chdir('/kaggle/working')\n"
        "if not os.path.exists('BreezyVoice'):\n"
        "    subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/mtkresearch/BreezyVoice.git'], check=True)\n"
        "os.chdir('/kaggle/working/BreezyVoice')\n"
        "# 官方 requirements 有只給 Python 3.10 的 ttsfrd 與用不到的 deepspeed，先拿掉（沒有 ttsfrd 會自動改用 WeTextProcessing）\n"
        "req = [l for l in open('requirements.txt') if 'ttsfrd' not in l and 'deepspeed' not in l]\n"
        "open('requirements_kaggle.txt', 'w').writelines(req)\n"
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements_kaggle.txt'], check=True)\n"
        "print('安裝完成')\n",

        "# 這一集的台詞（由 匯出Kaggle筆記本.py 產生，不用改）\n"
        "import csv, json\n"
        f"ROWS = json.loads({json.dumps(json.dumps(csv_rows, ensure_ascii=False), ensure_ascii=False)})\n"
        "with open('batch_this.csv', 'w', newline='', encoding='utf-8') as f:\n"
        "    w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()))\n"
        "    w.writeheader(); w.writerows(ROWS)\n"
        "print(len(ROWS), '句')\n",

        "import os, subprocess, sys\n"
        "os.environ['PYTHONUTF8'] = '1'\n"
        "subprocess.run([sys.executable, 'batch_inference.py', '--csv_file', 'batch_this.csv',\n"
        "                '--speaker_prompt_audio_folder', './data', '--output_audio_folder', '/kaggle/working/wav'], check=True)\n",

        "# 轉成 mp3（小很多，網頁直接內嵌）並打包\n"
        "import glob, os, subprocess, zipfile\n"
        "os.makedirs('/kaggle/working/mp3', exist_ok=True)\n"
        "for w in sorted(glob.glob('/kaggle/working/wav/*.wav')):\n"
        "    out = '/kaggle/working/mp3/' + os.path.basename(w)[:-4] + '.mp3'\n"
        "    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', w, '-ac', '1', '-b:a', '48k', out], check=True)\n"
        f"zp = '/kaggle/working/{key}_語音.zip'\n"
        "with zipfile.ZipFile(zp, 'w') as z:\n"
        "    for m in sorted(glob.glob('/kaggle/working/mp3/*.mp3')):\n"
        "        z.write(m, os.path.basename(m))\n"
        f"print('完成：', len(glob.glob('/kaggle/working/mp3/*.mp3')), '/', {len(rows)}, '個檔 →', zp)\n",
    ]
    return {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                   "source": c.splitlines(keepends=True)} for c in cells],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4, "nbformat_minor": 5,
    }


def main(argv):
    if not argv:
        sys.exit(__doc__)
    key, ep = find_episode(argv[0])
    rows = rows_for(key, ep)
    out = HERE / "輸出" / key
    out.mkdir(parents=True, exist_ok=True)
    nb = out / f"BreezyVoice_{key}.ipynb"
    nb.write_text(json.dumps(notebook(key, ep["title"], rows), ensure_ascii=False, indent=1), encoding="utf-8")
    # 台詞對照表：匯入時用來確認音檔跟現在的台詞對得上（腳本改過的句子不會套用舊音檔）
    (out / "台詞.json").write_text(json.dumps({"key": key, "title": ep["title"],
        "lines": {r["output_audio_filename"]: r["text"] for r in rows}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {nb.relative_to(ROOT)}（{len(rows)} 句，含金句）")


if __name__ == "__main__":
    main(sys.argv[1:])
