#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为精读页注入「上一篇 / 下一篇」跳转（不再需要回日历选择）。

用法：
  python3 scripts/inject-seq-nav.py            # 更新所有已发布精读页
  python3 scripts/inject-seq-nav.py 2026-11-03 # 更新该日期页 + 其前后相邻页（integrate 用）

依据 index.html 里的 ARTICLES 数组（按 publishDate + fileKey 排序）确定相邻文章，
把 <nav class="seq-nav"> 插到 <a class="back-cal"> 之后；幂等（重复运行只更新）。
"""
import json, re, sys, os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "index.html")


def load_articles():
    """用 node 解析 index.html 里的 ARTICLES（合法 JS 字面量），返回按日期排序的列表。"""
    js = (
        "const fs=require('fs');"
        "const h=fs.readFileSync(process.argv[1],'utf8');"
        "const i=h.indexOf('const ARTICLES = [');"
        "const start=i+'const ARTICLES = '.length;"
        "let depth=0,end=-1;"
        "for(let k=start;k<h.length;k++){if(h[k]==='[')depth++;else if(h[k]===']'){depth--;if(depth===0){end=k+1;break;}}}"
        "const a=eval('('+h.slice(start,end)+')');"
        "process.stdout.write(JSON.stringify(a));"
    )
    out = subprocess.run(["node", "-e", js, INDEX], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("node 解析 ARTICLES 失败: " + out.stderr)
    arts = json.loads(out.stdout)
    # 按 (publishDate, fileKey) 升序，决定「上一篇(更早) / 下一篇(更晚)」
    arts.sort(key=lambda x: (x.get("publishDate", ""), x.get("fileKey", "")))
    return arts


def local_path(reading_path):
    """readingPath 形如 /outward-reading/articles/... → 仓库内本地路径。"""
    rel = reading_path
    if rel.startswith("/outward-reading"):
        rel = rel[len("/outward-reading"):]
    return REPO + rel


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_block(prev_e, next_e):
    parts = []
    if prev_e and prev_e.get("readingPath"):
        parts.append(
            f'<a class="seq-prev" href="{prev_e["readingPath"]}">'
            f'<span class="seq-l">← 上一篇</span>'
            f'<span class="seq-t">{esc(prev_e["title"])}</span></a>')
    if next_e and next_e.get("readingPath"):
        parts.append(
            f'<a class="seq-next" href="{next_e["readingPath"]}">'
            f'<span class="seq-l">下一篇 →</span>'
            f'<span class="seq-t">{esc(next_e["title"])}</span></a>')
    if not parts:
        return ""
    return '<nav class="seq-nav" aria-label="上一篇/下一篇">' + "".join(parts) + "</nav>"


def ensure_print_hide(html):
    if "seq-nav{display:none" in html:
        return html
    rule = ("\n@media print{.seq-nav{display:none !important}}\n"
            "body.print-sheet .seq-nav{display:none !important}\n")
    return html.replace("</style>", rule + "</style>", 1)


def update_page(path, prev_e, next_e):
    if not os.path.exists(path):
        print("  [跳过] 本地文件不存在:", path)
        return False
    html = open(path, encoding="utf-8").read()
    block = build_block(prev_e, next_e)
    # 1. 移除旧的 seq-nav（幂等）
    html = re.sub(r'<nav class="seq-nav"[^>]*>.*?</nav>', "", html, flags=re.S)
    # 2. 插到 back-cal 之后
    m = re.search(r'<a class="back-cal"[^>]*>.*?</a>', html, re.S)
    if not m:
        print("  [跳过] 找不到 back-cal 锚点:", path)
        return False
    html = html[:m.end()] + block + html[m.end():]
    # 3. 保证打印隐藏
    html = ensure_print_hide(html)
    open(path, "w", encoding="utf-8").write(html)
    return True


def main():
    arts = load_articles()
    by_date = {}
    for a in arts:
        d = a.get("publishDate")
        if d:
            by_date.setdefault(d, a)  # 同日多篇时取排序后第一份

    focal = sys.argv[1] if len(sys.argv) > 1 else None
    dates = sorted(by_date.keys())

    def entry_for(d):
        return by_date.get(d)

    if focal:
        targets = set()
        if focal in by_date:
            targets.add(focal)
            idx = dates.index(focal)
            if idx - 1 >= 0:
                targets.add(dates[idx - 1])
            if idx + 1 < len(dates):
                targets.add(dates[idx + 1])
        targets = sorted(targets)
        print("更新焦点页及其相邻页:", targets)
    else:
        targets = dates
        print(f"批量更新全部 {len(targets)} 个日期页")

    for d in targets:
        prev_d = None
        next_d = None
        idx = dates.index(d)
        if idx - 1 >= 0:
            prev_d = dates[idx - 1]
        if idx + 1 < len(dates):
            next_d = dates[idx + 1]
        e = entry_for(d)
        prev_e = entry_for(prev_d)
        next_e = entry_for(next_d)
        if not e or not e.get("readingPath"):
            print(f"  [跳过] 该日期无 readingPath（尚未发布精读页）: {d}")
            continue
        ok = update_page(local_path(e["readingPath"]), prev_e, next_e)
        if ok:
            tags = []
            if prev_e:
                tags.append("上一篇→" + prev_e["publishDate"])
            if next_e:
                tags.append("下一篇→" + next_e["publishDate"])
            print(f"  ✓ {d}: " + (" / ".join(tags) if tags else "（无相邻）"))


if __name__ == "__main__":
    main()
