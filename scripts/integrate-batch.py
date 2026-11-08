#!/usr/bin/env python3
"""
批量接入精读页：装配产物 → articles/YYYY/MM/ → articles.js 的 readingPath → processed 清单。
不做 git 操作（由调用方批量 commit / push，避免多次推送触发网络失败）。

用法：
    python3 scripts/integrate-batch.py 2026-10-19 2026-10-18 ...
    python3 scripts/integrate-batch.py --list dates.txt

对没有条目的日期（如 9 月上旬），会在 articles.js 的 ARTICLES 开头插入新记录；
首页轻量化后条目不再内联 plainText，收尾自动跑 sync-search-index.py 生成全文索引。
"""
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "articles.js")
if not os.path.exists(INDEX):          # 兼容尚未拆分的工作区
    INDEX = os.path.join(REPO, "index.html")
CONTENT = os.path.join(REPO, "scripts", "content")
MANIFEST = os.path.join(REPO, "scripts", "processed-reading.list")


def make_entry(c, web_path):
    """生成一条 ARTICLES 记录（正文全文不进首页，见 sync-search-index.py）。"""
    return (
        '{\n'
        f'        title: {json.dumps(c["h1"], ensure_ascii=False)},\n'
        f'        publishDate: "{c["date"]}",\n'
        f'        fileKey: "{c["date"]}_001",\n'
        f'        readingPath: "{web_path}",\n'
        f'        source: {json.dumps(c.get("source_en") or c.get("source_label", ""), ensure_ascii=False)}\n'
        '      }'
    )


def patch_index(date, web_path, content):
    s = open(INDEX, encoding="utf-8").read()
    if web_path in s:
        return "已有 readingPath"
    re_ = r'(publishDate:\s*"%s",\n(\s*)fileKey:\s*"[^"]+",)' % re.escape(date)
    m = re.search(re_, s)
    if m:
        s = s[:m.end()] + '\n%sreadingPath: "%s",' % (m.group(2), web_path) + s[m.end():]
        open(INDEX, "w", encoding="utf-8").write(s)
        return "已补 readingPath"

    # 首页还没有这一天的条目：插入到数组开头（文章按日期倒序存放）
    entry = make_entry(content, web_path)
    i = s.index("const ARTICLES = [") + len("const ARTICLES = [")
    rest = s[i:]
    # 去掉紧随其后的换行，保持 "const ARTICLES = [\n{...}"
    lead = len(rest) - len(rest.lstrip("\n"))
    s = s[:i] + "\n" + entry + ",\n" + rest[lead:]
    open(INDEX, "w", encoding="utf-8").write(s)
    return "已新建条目 + readingPath"


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "--list":
        dates = [x.strip() for x in open(argv[1], encoding="utf-8") if x.strip()]
    else:
        dates = argv

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    done = []
    for date in dates:
        cpath = os.path.join(CONTENT, f"{date}.json")
        if not os.path.exists(cpath):
            print(f"✗ {date} 缺少内容 JSON：{cpath}")
            continue
        c = json.load(open(cpath, encoding="utf-8"))
        yy, mm = date[:4], date[5:7]
        dest_dir = os.path.join(REPO, "articles", yy, mm)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{date}_001.reading.html")
        src = f"/tmp/r{date[8:10]}_{date[5:7]}.html"
        if not os.path.exists(src):
            src = f"/tmp/r{date[8:10]}.html"
        if not os.path.exists(src):
            print(f"✗ {date} 找不到装配产物 {src}")
            continue
        shutil.copy(src, dest)
        web = f"/outward-reading/articles/{yy}/{mm}/{date}_001.reading.html"
        msg = patch_index(date, web, c)
        # 记入已处理清单
        lines = open(MANIFEST, encoding="utf-8").read().splitlines() if os.path.exists(MANIFEST) else []
        if date not in lines:
            with open(MANIFEST, "a", encoding="utf-8") as f:
                f.write(date + "\n")
        size = os.path.getsize(dest) // 1024
        print(f"✓ {date} → {web}  ({size} KB, {msg})")
        done.append(date)
    print(f"\n共接入 {len(done)} 篇：{' '.join(done)}")
    if done:
        sync = os.path.join(REPO, "scripts", "sync-search-index.py")
        if os.path.exists(sync):
            r = subprocess.run([sys.executable, sync], capture_output=True, text=True)
            print(r.stdout.strip() or "")
            if r.returncode != 0:
                print(f"  ⚠ 全文索引同步失败（返回 {r.returncode}）：{r.stderr.strip()[:200]}")
                print("    务必手动跑 python3 scripts/sync-search-index.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
