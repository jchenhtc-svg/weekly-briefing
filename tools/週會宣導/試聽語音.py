#!/usr/bin/env python3
"""快速試聽 edge-tts 產生的語音，確認品質可以接受再往下做整合。

用法：
    pip install edge-tts
    python3 試聽語音.py

會在同一個資料夾產生四個 mp3（四個角色各一句台詞），雙擊播放確認效果。
確認滿意後，跟 Claude 說一聲，就能幫你把整個播放引擎改成用這種預先產生
好的語音檔案，取代瀏覽器即時合成（好處：任何裝置、任何瀏覽器都能聽到
一樣的聲音，不再依賴手機/電腦裝了什麼系統語音）。
"""

import asyncio
import edge_tts

# 對應目前腳本設定裡 voicePref 的角色分配
SAMPLES = [
    ("主持人", "zh-TW-HsiaoChenNeural", "設備修好，客戶就會放心？不一定，因為修好跟放心，是兩回事。"),
    ("阿凱工程師", "zh-TW-YunJheNeural", "客戶系統當機，我到場二十分鐘搞定。好了，可以用了，收工具準備走人。"),
    ("主管", "zh-TW-HsiaoYuNeural", "我不是不信任你會修，是因為知道你會修，才希望你把最後那幾步確認做完。"),
    ("客戶", "zh-TW-HsiaoYuNeural", "你們到底在搞什麼？每停一分鐘我們損失幾十萬！"),
]


async def main():
    for role, voice, text in SAMPLES:
        out = f"試聽_{role}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out)
        print(f"✅ {role}（{voice}）→ {out}")

    print("\n四個檔案都在這個資料夾裡，雙擊播放看看效果如何。")


if __name__ == "__main__":
    asyncio.run(main())
