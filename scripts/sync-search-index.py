#!/usr/bin/env python3
"""
首页轻量化：把内联 Vue、文章元数据、全文搜索索引拆成独立静态资源。

一次性迁移（只需跑一次）：
    python3 scripts/sync-search-index.py --split
      · index.html 内联 Vue     → vue.global.prod.js（浏览器长期缓存）
      · index.html 的 ARTICLES  → articles.js（只留元数据，不含正文）
      · 各条目的 plainText      → search-index.js（仅点「搜全文」时才加载）
      · index.html 只保留 HTML / CSS / 交互逻辑

日常发布（新增或更新文章条目后跑）：
    python3 scripts/sync-search-index.py            # 只补新增条目，已有索引原样沿用
    python3 scripts/sync-search-index.py --refresh 2026-11-09
      # 该期英文原文有修订时，显式按 scripts/content/<date>.json 重建该期 _001 索引
    python3 scripts/sync-search-index.py --check    # 只报告覆盖率，不写文件

默认不重写历史条目：索引内容不变则版本戳不变，浏览器/CDN 缓存不会天天失效。

索引用 .js（window.__SEARCH_INDEX__）而非 .json：动态注入 script 标签即可加载，
本地 file:// 直接打开首页也不会被 CORS 拦住。
"""
import hashlib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "index.html")
ARTICLES_JS = os.path.join(REPO, "articles.js")
VUE_JS = os.path.join(REPO, "vue.global.prod.js")
SEARCH_JS = os.path.join(REPO, "search-index.js")
CONTENT_DIR = os.path.join(REPO, "scripts", "content")

STR_LIT = r'("(?:[^"\\]|\\.)*")'
FIELD = lambda name: re.compile(r'\b' + name + r'\s*:\s*' + STR_LIT)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def article_span(s):
    """返回 (起点, 终点)；覆盖 ARTICLES 定义整段，含前置注释。"""
    i = s.index("const ARTICLES = [")
    k = s.index("\n    ]", i) + len("\n    ]")
    c = s.rfind("    // ===== 文章数据库", 0, i)
    return (c if c >= 0 else i), k


def split_entries(seg):
    """按大括号平衡切出 ARTICLES 里的每个顶层对象（字符串内的括号不计）。"""
    start = seg.index("[") + 1
    depth, entries, buf = 0, [], []
    in_str, esc = None, False
    for ch in seg[start:]:
        if in_str:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
            buf.append(ch)
            continue
        if ch in "{[":
            depth += 1
            buf.append(ch)
            continue
        if ch in "}]":
            if ch == "]" and depth == 0:
                break
            depth -= 1
            buf.append(ch)
            if depth == 0:
                entries.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    return entries


def field(obj, name):
    m = FIELD(name).search(obj)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def entries_from(s):
    a, b = article_span(s)
    out = []
    for obj in split_entries(s[a:b]):
        key = field(obj, "fileKey")
        if key:
            out.append({
                "key": key,
                "date": field(obj, "publishDate") or "",
                "title": field(obj, "title") or "",
                "text": field(obj, "plainText") or "",
            })
    return out


def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html or "")


def text_from_content(c):
    """按内容 JSON 生成全文：中文标题 + 英文标题 + 全部英文段落。"""
    parts = [strip_tags(c.get("h1") or "")]
    hl = c.get("headline") or {}
    if isinstance(hl, dict):
        parts.append(strip_tags(hl.get("en_html") or ""))
    parts += [strip_tags(p.get("en_html") or "") for p in c.get("paragraphs") or []]
    return " ".join(x.strip() for x in parts if x and x.strip())


def load_index():
    if not os.path.exists(SEARCH_JS):
        return {}
    s = read(SEARCH_JS)
    m = re.search(r"window\.__SEARCH_INDEX__\s*=\s*(\{.*\})\s*;?\s*$", s, re.S)
    if not m:
        raise RuntimeError("search-index.js 格式异常")
    return (json.loads(m.group(1)).get("texts") or {})


def save_index(texts):
    body = json.dumps({"texts": texts}, ensure_ascii=False, separators=(",", ":"))
    version = hashlib.sha256(body.encode("utf-8")).hexdigest()[:10]
    write(SEARCH_JS, "window.__SEARCH_INDEX__=" +
          json.dumps({"v": version, "texts": texts}, ensure_ascii=False,
                     separators=(",", ":")) + ";\n")
    # 版本戳写进首页，索引内容一变 URL 就变，CDN 缓存自动失效
    s = read(INDEX)
    pat = r'const SEARCH_INDEX_V = "[^"]*";'
    if re.search(pat, s):
        s = re.sub(pat, 'const SEARCH_INDEX_V = "%s";' % version, s, count=1)
    elif "const { createApp } = Vue" in s:
        s = s.replace("const { createApp } = Vue",
                      'const SEARCH_INDEX_V = "%s";\n    const { createApp } = Vue' % version, 1)
    else:
        raise RuntimeError("index.html 找不到版本常量插入点")
    write(INDEX, s)
    return version


def do_split():
    s = read(INDEX)

    # 1) 抽出全文，生成按需加载的索引
    items = entries_from(s)
    texts = {x["key"]: x["text"] for x in items if x["text"]}
    print("抽取条目 %d 条，其中有全文 %d 条，正文合计 %d 字符"
          % (len(items), len(texts), sum(len(v) for v in texts.values())))

    # 2) 删掉每个条目里的 plainText 行（连同它前面的逗号）
    s, n = re.subn(r',\s*\n\s*plainText\s*:\s*' + STR_LIT, "", s)
    print("从首页移除 plainText 字段 %d 处" % n)
    if n != len(texts):
        raise RuntimeError("plainText 移除数与抽取数不一致，已中止（未写任何文件）")

    # 3) 内联 Vue → vue.global.prod.js
    m = re.search(r"<script>\s*(.*?)\s*</script>", s, re.S)
    if not m or "var Vue=" not in m.group(1)[:200]:
        raise RuntimeError("找不到内联 Vue 脚本，已中止")
    write(VUE_JS, m.group(1).strip() + "\n")
    s = s[:m.start()] + '<script src="vue.global.prod.js"></script>' + s[m.end():]
    print("内联 Vue 已拆出：%s (%d KB)" % (os.path.basename(VUE_JS),
                                        os.path.getsize(VUE_JS) // 1024))

    # 4) ARTICLES → articles.js
    a, b = article_span(s)
    block = s[a:b].strip()
    write(ARTICLES_JS, block + "\n")
    s = s[:a] + s[b:]

    # 在主逻辑 script 前插入外部引用，保持原缩进
    p = s.index("<script>")
    line_start = s.rfind("\n", 0, p) + 1
    indent = s[line_start:p]
    s = (s[:line_start] + indent + '<script src="articles.js"></script>\n'
         + indent + s[line_start:])
    write(INDEX, s)
    print("文章元数据已拆出：%s (%d KB)；index.html 现为 %d KB"
          % (os.path.basename(ARTICLES_JS), os.path.getsize(ARTICLES_JS) // 1024,
             os.path.getsize(INDEX) // 1024))

    # 5) 写索引（会顺带写入 SEARCH_INDEX_V 版本戳）
    v = save_index(texts)
    print("全文索引已生成：%s (%d KB)，版本 %s"
          % (os.path.basename(SEARCH_JS), os.path.getsize(SEARCH_JS) // 1024, v))


def do_sync(check_only=False, refresh_dates=()):
    src = ARTICLES_JS if os.path.exists(ARTICLES_JS) else INDEX
    items = entries_from(read(src))
    old = load_index()
    texts, added, updated, kept = {}, [], [], []
    for x in items:
        key = x["key"]
        prior = old.get(key, "") or x["text"]   # 兼容尚未拆分的工作区（条目仍带 inline plainText）
        new = prior
        cp = os.path.join(CONTENT_DIR, x["date"] + ".json")
        # 只在「缺索引」或「显式 --refresh 该日期」时读内容 JSON，避免每次发布重写全部历史
        need = (not prior) or (x["date"] in refresh_dates and key.endswith("_001"))
        if need and key.endswith("_001") and os.path.exists(cp):
            try:
                c = json.loads(read(cp))
                candidate = text_from_content(c)
                # 防退化：老文章的内容 JSON 结构可能不完整，生成文本明显变短时沿用旧索引
                if candidate and (not prior or len(candidate) >= len(prior) * 0.6):
                    new = candidate
                else:
                    print("  ! %s 生成的正文明显偏短，沿用旧索引" % key)
            except Exception as e:
                print("  ! %s 内容 JSON 读取失败，沿用旧索引：%s" % (key, e))
        if not prior and new:
            added.append(key)
        elif new and new != prior:
            updated.append(key)
        elif prior:
            kept.append(key)
        if new:
            texts[key] = new
    missing = [x["key"] for x in items if not texts.get(x["key"])]
    print("条目 %d | 新增 %d | 刷新 %d | 沿用 %d | 缺索引 %d"
          % (len(items), len(added), len(updated), len(kept), len(missing)))
    if missing:
        print("  缺索引：", ", ".join(missing[:8]))
    if check_only:
        return 0
    v = save_index(texts)
    print("search-index.js 已更新（%d KB），版本 %s"
          % (os.path.getsize(SEARCH_JS) // 1024, v))
    return 0


def main(argv):
    if "--split" in argv:
        do_split()
        return 0
    refresh = set()
    for i, a in enumerate(argv):
        if a == "--refresh" and i + 1 < len(argv):
            refresh.add(argv[i + 1])
        elif a.startswith("--refresh="):
            refresh.add(a.split("=", 1)[1])
    return do_sync(check_only="--check" in argv, refresh_dates=refresh)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
