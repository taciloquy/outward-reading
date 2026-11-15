#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回填老文章条目的中文标题 titleZh（仅用于搜索，不改首页列表展示）。

背景：首页轻量化后，49 篇老文章 ARTICLES.title 是英文标题，而精读页 <h1>
是中文标题；全文索引也只收英文原文，导致搜「诈骗」等中文词命中不了 10-23
这类文章。新文章（title 本身已是中文）不需要此字段。

做法：按 readingPath 找到精读页，抽 <h1> 中文标题，在 articles.js 对应条目
的 fileKey 行后插入 titleZh 字段。幂等：已有 titleZh 或英文标题已含中文则跳过。

用法：
  python3 scripts/sync-title-zh.py            # 回填
  python3 scripts/sync-title-zh.py --check    # 只报告，不写
"""
import html
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_JS = os.path.join(REPO, "articles.js")

NODE_JS = (
    "const fs=require('fs');"
    "const h=fs.readFileSync(process.argv[1],'utf8');"
    "const i=h.indexOf('const ARTICLES = [');"
    "const start=i+'const ARTICLES = '.length;"
    "let depth=0,end=-1;"
    "for(let k=start;k<h.length;k++){if(h[k]==='[')depth++;else if(h[k]===']'){depth--;if(depth===0){end=k+1;break;}}}"
    "const a=eval('('+h.slice(start,end)+')');"
    "process.stdout.write(JSON.stringify(a));"
)


def load_articles():
    out = subprocess.run(["node", "-e", NODE_JS, ARTICLES_JS], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("node 解析 ARTICLES 失败：" + out.stderr)
    return json.loads(out.stdout)


def page_path(reading_path):
    if not reading_path:
        return ""
    p = reading_path.lstrip("/")
    if p.startswith("outward-reading/"):
        p = p[len("outward-reading/"):]
    return os.path.join(REPO, p)


def zh_h1(path):
    """抽精读页 <h1> 的中文标题；无中文返回空串。"""
    if not os.path.exists(path):
        return ""
    s = open(path, encoding="utf-8").read()
    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", s)
    if not m:
        return ""
    t = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    t = re.split(r"\s*[—–]{2,}\s*", t)[0].strip()   # 去掉「—— 早安英文 …」后缀
    return t if re.search(r"[\u4e00-\u9fff]", t) else ""


def main():
    check = "--check" in sys.argv
    src = open(ARTICLES_JS, encoding="utf-8").read()
    items = load_articles()
    pending, no_page, no_h1 = [], [], []
    for a in items:
        if a.get("titleZh"):
            continue
        if re.search(r"[\u4e00-\u9fff]", a.get("title") or ""):
            continue          # 新文章：title 已是中文，搜索天然可命中
        key = a.get("fileKey")
        p = page_path(a.get("readingPath"))
        if not os.path.exists(p):
            no_page.append(key)
            continue
        t = zh_h1(p)
        if not t:
            no_h1.append(key)
            continue
        pending.append((key, t))

    print("条目 %d | 需回填 %d | 无页面 %d | 无中文 h1 %d"
          % (len(items), len(pending), len(no_page), len(no_h1)))
    for k in (no_page + no_h1)[:10]:
        print("  ! 跳过", k)
    if check or not pending:
        return 0

    for key, title in pending:
        # 在 fileKey 行后插入 titleZh（缩进沿用该行）
        m = re.search(r'(?m)^(\s*)fileKey:\s*"%s",' % re.escape(key), src)
        if not m:
            print("  ! 未定位", key)
            continue
        src = (src[:m.end()] + "\n" + m.group(1)
               + "titleZh: " + json.dumps(title, ensure_ascii=False) + ","
               + src[m.end():])
        print("  + %s  %s" % (key, title[:36]))
    open(ARTICLES_JS, "w", encoding="utf-8").write(src)
    print("articles.js 已写入 %d 条 titleZh" % len(pending))
    return 0


if __name__ == "__main__":
    sys.exit(main())
