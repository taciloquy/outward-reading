#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键给全部精读页补朗读（para-audio-v3）
用法：
    python3 scripts/batch-audio-all.py [--dry-run] [--only 2026-09-01,2026-09-03]

对 articles/2026/{09,10,11}/ 下每个 *.reading.html：
  1. 找 scripts/content/<日期>.json（.part1/.part2 等后缀自动忽略；无 JSON 跳过并提示）
  2. 音频目录 articles/YYYY/MM/audio/<日期>/ 缺哪个 uk-pN.m4a 就补生成（gen-paragraph-audio.py 断点续跑）
  3. 页面没有 para-audio-v3 标记就打补丁（add-paragraph-audio.py）
已完成的自动跳过，可随时中断重跑。11-01 已是定稿，也会被自动跳过。
"""
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def pages():
    out = []
    for mm in ("09", "10", "11"):
        out += sorted(glob.glob(os.path.join(REPO, f"articles/2026/{mm}/*.reading.html")))
    return out


def json_for(page):
    name = os.path.basename(page)             # 2026-09-01_001.reading.html
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    if not m:
        return None
    d = m.group(1)
    p = os.path.join(SCRIPTS, "content", f"{d}.json")
    if os.path.exists(p):
        return p
    return extract_json(page)                 # 无 JSON 时从页面正文兜底抽取


def extract_json(page):
    """早期手工页（10-29/10-30 等）没有 content JSON，
    从页面自身抽取各段英文到临时 JSON，供音频生成使用。"""
    d = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(page)).group(1)
    s = open(page, encoding="utf-8").read()
    paras = []
    for m in re.finditer(
            r'<section class="paragraph" id="p(\d+)">.*?<div class="en-block en">(.*?)</div>',
            s, re.S):
        paras.append({"en_html": m.group(2)})
    if not paras:
        return None
    tmp = f"/tmp/audio-json-{d}.json"
    json.dump({"date": d, "paragraphs": paras}, open(tmp, "w", encoding="utf-8"),
              ensure_ascii=False)
    return tmp


def audio_ok(json_path, page_dir):
    """该日期需要的 uk-pN.m4a 是否全部存在"""
    data = json.load(open(json_path, encoding="utf-8"))
    n = len(data["paragraphs"])
    return all(
        os.path.exists(os.path.join(page_dir, f"uk-p{i}.m4a"))
        and os.path.getsize(os.path.join(page_dir, f"uk-p{i}.m4a")) > 1000
        for i in range(1, n + 1)
    )


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))

    todo_gen, todo_patch, skip, nojson = [], [], [], []
    for page in pages():
        if only and not any(o in page for o in only):
            continue
        jp = json_for(page)
        if not jp:
            nojson.append(os.path.basename(page))
            continue
        d = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(page)).group(1)
        yy, mm = d[:4], d[5:7]
        adir = os.path.join(REPO, "articles", yy, mm, "audio", d)
        need_gen = not audio_ok(jp, adir)
        s = open(page, encoding="utf-8").read()
        need_patch = "para-audio-v3" not in s
        if need_gen:
            todo_gen.append((page, jp, adir))
        if need_patch:
            todo_patch.append((page, jp, adir))
        if not need_gen and not need_patch:
            skip.append(os.path.basename(page))

    print(f"待生成音频 {len(todo_gen)} 页 / 待打补丁 {len(todo_patch)} 页 / 已完成 {len(skip)} 页"
          + (f" / 无内容JSON {len(nojson)}" if nojson else ""))
    for f in nojson:
        print("  无 JSON：", f)
    if dry:
        for p, _, _ in todo_gen:
            print("  [将生成音频]", os.path.basename(p))
        for p, _, _ in todo_patch:
            print("  [将打补丁]  ", os.path.basename(p))
        return

    for k, (page, jp, adir) in enumerate(todo_gen, 1):
        print(f"\n=== [{k}/{len(todo_gen)}] 生成音频 {os.path.basename(page)} ===", flush=True)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gen-paragraph-audio.py"), jp])
        if r.returncode != 0:
            print(f"!! 音频生成失败，中止：{page}")
            sys.exit(1)
    for k, (page, jp, adir) in enumerate(todo_patch, 1):
        print(f"\n=== [{k}/{len(todo_patch)}] 打补丁 {os.path.basename(page)} ===", flush=True)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "add-paragraph-audio.py"), page])
        if r.returncode != 0:
            print(f"!! 补丁失败，中止：{page}")
            sys.exit(1)
    print("\n全部完成。下一步：git add -A && git commit && git push（记得线上 curl 抽查）")


if __name__ == "__main__":
    main()
