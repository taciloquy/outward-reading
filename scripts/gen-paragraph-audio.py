#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐段朗读音频生成器（para-audio-v2）
用法：
    python3 scripts/gen-paragraph-audio.py scripts/content/2026-11-01.json [输出目录]

默认输出目录：articles/YYYY/MM/audio/<日期>/（从 JSON 的 date 字段推导）
音色：us = en-US-AndrewMultilingualNeural（美音男）
      uk = en-GB-SoniaNeural（英音女）
语速：原速 = 0%，慢速 = -10%
输出：<us|uk>-p<N>.mp3（原速）与 <us|uk>-p<N>-s.mp3（慢速）
串行生成，避免并发被限流。断点续跑：已存在且非空的文件跳过。
依赖：pip3 install edge-tts

注意：v1 的旧音频是 -8% 语速且文件名无 -s 后缀，与 v2 语速定义不符；
升级到 v2 时请先删除旧的 audio/<日期>/ 目录再重新生成。
"""
import json
import re
import html
import sys
import os
import asyncio

VOICES = {
    "us": "en-US-AndrewMultilingualNeural",
    "uk": "en-GB-SoniaNeural",
}
# (文件后缀, edge-tts rate 参数)
RATES = [("", "+0%"), ("-s", "-10%")]


def fix_radicals(t: str) -> str:
    """pymupdf 同款坑：康熙部首/部首补充区码位还原"""
    import unicodedata
    out = []
    for ch in t:
        o = ord(ch)
        if 0x2E80 <= o <= 0x2FDF:
            n = unicodedata.normalize("NFKC", ch)
            if len(n) == 1 and '\u4e00' <= n <= '\u9fff':
                out.append(n)
            else:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def html_to_text(en_html: str) -> str:
    t = re.sub(r"<[^>]+>", "", en_html)
    t = html.unescape(t)
    t = fix_radicals(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


async def gen_one(text: str, voice_id: str, rate: str, path: str):
    import edge_tts
    c = edge_tts.Communicate(text, voice_id, rate=rate)
    await c.save(path)


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    json_path = sys.argv[1]
    data = json.load(open(json_path, encoding="utf-8"))
    date = data["date"]                       # YYYY-MM-DD
    if len(sys.argv) >= 3:
        out_dir = sys.argv[2]
    else:
        yy, mm = date[:4], date[5:7]
        out_dir = os.path.join("articles", yy, mm, "audio", date)
    os.makedirs(out_dir, exist_ok=True)

    paras = []
    for i, p in enumerate(data["paragraphs"], 1):
        text = html_to_text(p["en_html"])
        if not text:
            print(f"警告：P{i} 抽取文本为空，跳过")
            continue
        paras.append((i, text))

    total = 0
    for key, voice_id in VOICES.items():
        for suffix, rate in RATES:
            for i, text in paras:
                path = os.path.join(out_dir, f"{key}-p{i}{suffix}.mp3")
                # 已存在且非空则跳过（断点续跑）
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    print(f"跳过（已存在）{path}")
                    continue
                await gen_one(text, voice_id, rate, path)
                size = os.path.getsize(path)
                total += size
                print(f"{path}  {size/1024:.0f}KB")
    print(f"完成：{out_dir}，新增 {total/1024/1024:.1f}MB")


if __name__ == "__main__":
    asyncio.run(main())
