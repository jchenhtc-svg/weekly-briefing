#!/usr/bin/env python3
"""試聽用：把一集台詞匯出成 Breeze TTS 2（BreezeBlue）的 Kaggle 筆記本。

⚠️ 授權：Breeze TTS 2 的模型與「自己架設產生的聲音」只限研究與非商業用途
（BreezeBlue Research and Non-Commercial License）。公司確認可以用之前，產生的音檔只做內部試聽，
不要匯入 語音/、不要放上網站。

用法（在 tools/週會宣導/ 底下）：
    python3 預錄語音/匯出Kaggle筆記本_Breeze2.py 11
→ 預錄語音/輸出/11/Breeze2_11.ipynb，到 Kaggle Import 後 Run All（GPU、Internet 打開），
  下載 /kaggle/working/11_語音_breeze2.zip。

做法：Breeze TTS 2 可以用文字描述「設計」聲音，但每句都用描述生成，聲音會一句一句飄。
所以先用描述替每個角色生一段參考錄音（固定 seed），再用這段錄音「複製」來唸該角色的每一句。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module

base = import_module("匯出Kaggle筆記本")  # 共用：找腳本、唸法處理

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 角色 → 聲音描述（用中文寫，跟要唸的內容同語言）。沒列到的角色依音調自動給男聲／女聲描述
DESIGN = {
    "主持人": "一位三十歲左右的台灣女性節目主持人，說話快、直接、有梗，聲音明亮有自信，標準的台灣國語口音。",
    "阿凱工程師": "一位三十歲左右的台灣男性工程師，聲音低沉一點，個性愛自嘲、有點無奈但很真誠，語速稍快，標準的台灣國語口音。",
    "主管": "一位四十多歲的台灣女性主管，聲音沉穩有分量，說話不多但一句話戳重點，語速平穩，標準的台灣國語口音。",
    "客戶": "一位著急的台灣女性客戶，說話短、直接、不太客氣，語速快，標準的台灣國語口音。",
    "AI 助理": "一個友善的 AI 語音助理，聲音清楚中性、略帶電子感，語速平穩，標準的台灣國語口音。",
}
SAMPLE = "大家好，今天我們來聊聊在現場維修的時候，怎麼跟客戶溝通，讓事情處理得又快又好。"


def design_for(role):
    if role["name"] in DESIGN:
        return DESIGN[role["name"]]
    who = "男性" if role.get("pitch", 1) < 0.95 else "女性"
    return f"一位台灣{who}，{role.get('chip', '').split('·')[-1].strip()}，標準的台灣國語口音。"


def notebook(key, ep, rows):
    roles = {r["name"]: {"instruction": design_for(r), "seed": 1000 + n} for n, r in enumerate(ep["roles"])}
    lines = [{"role": r["role"], "text": r["content_to_synthesize"], "out": r["output_audio_filename"]} for r in rows]
    cells = [
        f"# Breeze TTS 2 試聽：{ep['title']}（⚠️ 模型限研究／非商業用途，產生的聲音只做內部試聽）\n"
        "# 右側 Settings：Accelerator 選 GPU（T4 x2 或 P100 都可，至少 12 GB），Internet 打開，然後 Run All。\n"
        "# 模型如果要求先同意授權：到 huggingface.co/BreezeBlue/breeze-tts-2 按同意，\n"
        "# 再把 Hugging Face token 加到 Kaggle 右側 Add-ons → Secrets，名稱 HF_TOKEN。\n"
        "import os, subprocess, sys\n"
        "os.chdir('/kaggle/working')\n"
        "if not os.path.exists('breeze-tts'):\n"
        "    subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/breezeblue-ai/breeze-tts.git'], check=True)\n"
        "req = [l for l in open('breeze-tts/requirements.txt') if not l.startswith(('pytest', 'ruff'))]\n"
        "open('req_kaggle.txt', 'w').writelines(req)\n"
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'req_kaggle.txt'], check=True)\n"
        "token = None\n"
        "try:\n"
        "    from kaggle_secrets import UserSecretsClient\n"
        "    token = UserSecretsClient().get_secret('HF_TOKEN')\n"
        "except Exception:\n"
        "    pass\n"
        "from huggingface_hub import snapshot_download\n"
        "MODEL = snapshot_download('BreezeBlue/breeze-tts-2', local_dir='/kaggle/working/breeze-tts-2', token=token)\n"
        "print('模型下載完成：', MODEL)\n"
        "",

        "# 這一集的台詞與角色聲音描述（由 匯出Kaggle筆記本_Breeze2.py 產生）\n"
        "import json\n"
        f"LINES = json.loads({json.dumps(json.dumps(lines, ensure_ascii=False), ensure_ascii=False)})\n"
        f"ROLES = json.loads({json.dumps(json.dumps(roles, ensure_ascii=False), ensure_ascii=False)})\n"
        f"SAMPLE = {json.dumps(SAMPLE, ensure_ascii=False)}\n"
        "print(len(LINES), '句，', len(ROLES), '個角色')\n",

        "# 載入模型（只載一次）\n"
        "import os, sys, torch\n"
        "from pathlib import Path\n"
        "os.chdir('/kaggle/working/breeze-tts'); sys.path.insert(0, '/kaggle/working/breeze-tts')\n"
        "import soundfile as sf\n"
        "from breeze_infer.runtime import load_runtime, resolve_device, set_all_seeds, update_generation_config_for_breeze\n"
        "from breeze_infer.templates import get_template, prepare_inputs, select_template_name\n"
        "from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig\n"
        "print('GPU：', torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))\n"
        "tok, model, atok = load_runtime(Path('/kaggle/working/breeze-tts-2'), device=resolve_device(), attn_implementation='eager')\n"
        "update_generation_config_for_breeze(model)\n"
        "runtime = FastBreezeStreamingRuntime(model, atok, FastStreamingConfig(max_new_tokens=1500, max_seq_len=2048, fast_all=False,\n"
        "    fast_text_encoder=False, fast_backbone_prefill=False, fast_backbone_decode=False, fast_depth_decoder=False,\n"
        "    fast_codec=False, repetition_penalty=1.1), tokenizer=tok)\n"
        "\n"
        "def synth(text, out, seed, cfg=1.0, instruction=None, ref_audio=None, ref_text=None):\n"
        "    req = {'id': 'r', 'text': text, 'speaker': 'S0'}\n"
        "    if instruction: req['instruction'] = instruction\n"
        "    if ref_audio: req['ref_audio_path'] = ref_audio; req['ref_text'] = ref_text\n"
        "    set_all_seeds(seed)\n"
        "    inputs = prepare_inputs(tok, atok, model, [req], get_template(select_template_name(req)),\n"
        "                            guidance_scale=cfg, guidance_scale_ref=None, guidance_scale_ins=None)\n"
        "    with sf.SoundFile(out, mode='w', samplerate=runtime.sample_rate, channels=1, subtype='PCM_16') as f:\n"
        "        for chunk in runtime.iter_audio_chunks(inputs, request_id='r', seed=seed):\n"
        "            f.write(chunk.audio)\n"
        "print('模型載入完成')\n",

        "# 1) 每個角色用描述設計一段參考聲音　2) 用參考聲音複製來唸每一句（同一角色聲音才會一致）\n"
        "os.makedirs('/kaggle/working/wav', exist_ok=True)\n"
        "for role, r in ROLES.items():\n"
        "    if not any(l['role'] == role for l in LINES): continue\n"
        "    r['ref'] = f'/kaggle/working/wav/ref_{r[\"seed\"]}.wav'\n"
        "    synth(SAMPLE, r['ref'], r['seed'], cfg=4.0, instruction=r['instruction'])\n"
        "    print('角色聲音：', role)\n"
        "for n, l in enumerate(LINES):\n"
        "    r = ROLES[l['role']]\n"
        "    synth(l['text'], f\"/kaggle/working/wav/{l['out']}.wav\", 42 + n, ref_audio=r['ref'], ref_text=SAMPLE)\n"
        "    print(n + 1, '/', len(LINES), l['text'][:20])\n",

        "# 轉 mp3 打包（ref_*.mp3 是各角色的參考聲音，也可以先聽聽看）\n"
        "import glob, subprocess, zipfile\n"
        "os.makedirs('/kaggle/working/mp3', exist_ok=True)\n"
        "for w in sorted(glob.glob('/kaggle/working/wav/*.wav')):\n"
        "    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', w, '-ac', '1', '-b:a', '48k',\n"
        "                    '/kaggle/working/mp3/' + os.path.basename(w)[:-4] + '.mp3'], check=True)\n"
        f"zp = '/kaggle/working/{key}_語音_breeze2.zip'\n"
        "with zipfile.ZipFile(zp, 'w') as z:\n"
        "    for m in sorted(glob.glob('/kaggle/working/mp3/*.mp3')):\n"
        "        z.write(m, os.path.basename(m))\n"
        "print('完成 →', zp)\n",
    ]
    nb = base.notebook(key, ep["title"], rows)  # 借用 notebook 外框格式
    nb["cells"] = [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                    "source": c.splitlines(keepends=True)} for c in cells]
    return nb


def main(argv):
    if not argv:
        sys.exit(__doc__)
    key, ep = base.find_episode(argv[0])
    rows = base.rows_for(key, ep)
    out = HERE / "輸出" / key
    out.mkdir(parents=True, exist_ok=True)
    nb = out / f"Breeze2_{key}.ipynb"
    nb.write_text(json.dumps(notebook(key, ep, rows), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "台詞.json").write_text(json.dumps({"key": key, "title": ep["title"],
        "lines": {r["output_audio_filename"]: r["text"] for r in rows}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {nb.relative_to(ROOT)}（{len(rows)} 句；⚠️ 限非商業，只做內部試聽）")


if __name__ == "__main__":
    main(sys.argv[1:])
