#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全文索引中文增强：把页面上真实可见的中文译文并入 search-index.js 的 texts。

原则：只收页面实际显示的中文 —— 精读页 <div class="zh-block">，旧式文章的
translated.html 里 <p class='cn'>。这样「搜得到」与「点进去跳得到」始终一致；
内容 JSON 中未渲染的译文（如预习期 zh 为空）不作为来源。

英文原文部分原样保留，中文部分以 ZH_MARK 分隔，重复运行幂等
（每次取标记之前的内容当英文部分，中文部分重新从页面抽取）。

由 sync-search-index.py 的 do_sync 在写索引前调用；本模块不直接写文件。
"""
import html as html_mod
import json
import os
import re
import subprocess

ZH_MARK = "\n⟪中文译文⟫\n"

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


def load_articles(repo):
    path = os.path.join(repo, "articles.js")
    out = subprocess.run(["node", "-e", NODE_JS, path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("node 解析 ARTICLES 失败：" + out.stderr)
    return json.loads(out.stdout)


def _path(repo, web):
    if not web:
        return ""
    p = web.lstrip("/")
    if p.startswith("outward-reading/"):
        p = p[len("outward-reading/"):]
    return os.path.join(repo, p)


def _clean(s):
    s = html_mod.unescape(re.sub(r"<[^>]+>", "", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _is_cn(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _from_reading(p):
    s = open(p, encoding="utf-8").read()
    out = []
    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", s)
    if m:
        out.append(_clean(m.group(1)))
    out += [_clean(x) for x in re.findall(
        r'<div class=["\']zh-block["\'][^>]*>([\s\S]*?)</div>', s)]
    return out


def _from_translated(p):
    s = open(p, encoding="utf-8").read()
    return [_clean(x) for x in re.findall(
        r"<p class=['\"]cn['\"][^>]*>([\s\S]*?)</p>", s)]


def enrich(texts, repo):
    """返回增强后的 texts；不动传入对象。"""
    arts = load_articles(repo)
    out = dict(texts)
    stats = {"reading": 0, "translated": 0, "none": 0}
    for a in arts:
        key = a.get("fileKey")
        if not key:
            continue
        en = (texts.get(key) or "").split(ZH_MARK)[0]
        paras, kind = [], "none"
        rp = _path(repo, a.get("readingPath"))
        if rp and os.path.exists(rp):
            paras, kind = _from_reading(rp), "reading"
        else:
            cp = a.get("cleanPath") or ""
            tp = _path(repo, cp.replace(".clean.html", ".translated.html")) if cp else ""
            if tp and os.path.exists(tp):
                paras, kind = _from_translated(tp), "translated"
        stats[kind] += 1

        # 中文标题兜底（保证「搜标题」的同一批词在全文索引里也能带出上下文）
        t = a.get("titleZh") or (a.get("title") or "")
        if _is_cn(t) and t not in paras:
            paras.insert(0, t)

        seen, zh = set(), []
        for x in paras:
            x = _clean(x)
            if x and _is_cn(x) and x not in seen:
                seen.add(x)
                zh.append(x)
        out[key] = en + (ZH_MARK + " ".join(zh) if zh else "")
    return out, stats


if __name__ == "__main__":
    # 独立自检：python3 scripts/zh_index.py
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    s = open(os.path.join(repo, "search-index.js"), encoding="utf-8").read()
    texts = json.loads(s[s.index("=") + 1:].strip().rstrip(";"))["texts"]
    enriched, st = enrich(texts, repo)
    print("条目 %d | 精读页 %d / 旧式译文页 %d / 无中文源 %d"
          % (len(enriched), st["reading"], st["translated"], st["none"]))
    cn = sum(1 for v in enriched.values() if ZH_MARK in v)
    print("含中文译文段落的条目：%d（原索引含中文：%d）"
          % (cn, sum(1 for v in texts.values() if _is_cn(v))))
