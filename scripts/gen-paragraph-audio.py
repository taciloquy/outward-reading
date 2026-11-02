#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐段朗读音频生成器（para-audio-v3 + 标题，仅英音 + 原速，32kbps AAC）
用法：
    python3 scripts/gen-paragraph-audio.py scripts/content/2026-11-01.json [输出目录]

默认输出目录：articles/YYYY/MM/audio/<日期>/（从 JSON 的 date 字段推导）
2026-11-02 用户决策：
    - 音色只保留英音 en-GB-SoniaNeural（去掉美音，页面不再提供选择器）
    - 语速只保留原速（去掉慢速档）
    - 码率压缩：edge-tts 原始 48kbps mp3 → 32kbps 单声道 AAC (.m4a)，macOS 自带 afconvert
    - 标题也要朗读（2026-11-02 追加）：headline.en_html → uk-title.m4a
输出：uk-title.m4a + uk-p<N>.m4a（9 段 ≈ 1.3MB，62 篇全量 ≈ 80MB）
串行生成，断点续跑（已存在且非空的文件跳过）。
依赖：pip3 install edge-tts；macOS 自带 afconvert（Linux 需另装 ffmpeg 并改 transcode 函数）
"""
import json
import re
import html
import sys
import os
import asyncio
import subprocess

VOICE = {"uk": "en-GB-SoniaNeural"}   # 2026-11-02 起只保留英音
BITRATE = 32000                        # 32kbps AAC 单声道
TMP_DIR = "/tmp/tts-mp3"               # 中间 mp3 落在这里，不落仓库（见 transcode 注释）


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


def transcode(mp3_path: str, m4a_path: str) -> int:
    """48kbps mp3 → 32kbps 单声道 m4a，返回 m4a 大小。

    注意：中间 mp3 一律放在系统临时目录（见 main 里的 TMP_DIR），
    这里不删除任何仓库内文件——批量生成时逐篇删 mp3 会触发「批量删除确认」而中断。
    """
    subprocess.run(
        ["afconvert", "-f", "m4af", "-d", "aac", "-b", str(BITRATE), "-c", "1",
         mp3_path, m4a_path],
        check=True, capture_output=True,
    )
    return os.path.getsize(m4a_path)


async def gen_one(text: str, voice_id: str, path: str):
    import edge_tts
    c = edge_tts.Communicate(text, voice_id)   # 不传 rate = 原速
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
    os.makedirs(TMP_DIR, exist_ok=True)

    # 任务清单：(文件名主干, 要朗读的文本)
    jobs = []

    # ① 标题（headline 英文，两行 span 已被压成一行空格分隔）
    head = data.get("headline") or {}
    head_text = html_to_text(head.get("en_html", ""))
    if head_text:
        jobs.append(("uk-title", head_text))
    else:
        print("警告：headline.en_html 为空，跳过标题音频")

    # ② 正文各段
    for i, p in enumerate(data["paragraphs"], 1):
        text = html_to_text(p["en_html"])
        if not text:
            print(f"警告：P{i} 抽取文本为空，跳过")
            continue
        jobs.append((f"uk-p{i}", text))

    total = 0
    for voice_id in VOICE.values():
        for stem, text in jobs:
            m4a_path = os.path.join(out_dir, stem + ".m4a")
            # 已存在且非空则跳过（断点续跑）
            if os.path.exists(m4a_path) and os.path.getsize(m4a_path) > 1000:
                print(f"跳过（已存在）{m4a_path}")
                continue
            tmp_mp3 = os.path.join(TMP_DIR, stem + ".mp3")
            await gen_one(text, voice_id, tmp_mp3)
            size = transcode(tmp_mp3, m4a_path)
            total += size
            print(f"{m4a_path}  {size/1024:.0f}KB")
    print(f"完成：{out_dir}，新增 {total/1024/1024:.2f}MB")


if __name__ == "__main__":
    asyncio.run(main())
