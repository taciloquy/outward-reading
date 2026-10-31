#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 29 日之前的老三件套（clean / annotated / translated）反推成精读页素材。

只做解析与报告，不改任何文件。用于评估「一键升级」的可行边界：
  英文段落  <- clean.html 的 <p>
  中文译文  <- translated.html 每个 div.g 里的第二个 <p>
  生词/音标/释义  <- annotated.html 红字 + 蓝色音标 + 灰色释义（按列对齐）
  专有名词  <- annotated.html 蓝字 + 相邻释义

用法：python3 parse-legacy-article.py <YYYY-MM-DD_001> [正文目录]
"""
import re
import sys
import os

RED = "color:#EE0000"
BLUE = "color:#0000CC"
YEL = "background:#FFFF00"
GREEN = "color:#008000"
IPA = "color:#1A6FB0"
GLOSS = "color:#555555"

SPAN_RE = re.compile(r"<span style='([^']*)'>(.*?)</span>", re.S)


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def parse_clean(html: str):
    title = re.search(r"<h2>(.*?)</h2>", html, re.S)
    paras = [strip_tags(p).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S)]
    return (strip_tags(title.group(1)).strip() if title else ""), [p for p in paras if p]


def parse_translated(html: str):
    """返回 [(en, cn), ...]，每个 div.g 里第一个 p 是英文、第二个是中文。"""
    out = []
    for block in re.findall(r"<div class='g'>(.*?)</div>", html, re.S):
        ps = [strip_tags(x).strip() for x in re.findall(r"<p[^>]*>(.*?)</p>", block, re.S)]
        if len(ps) >= 2:
            out.append((ps[0], ps[1]))
        elif ps:
            out.append((ps[0], ""))
    return out


def line_width(pre_inner: str) -> int:
    """一个 <pre> 的显示宽度（字符数，&nbsp; 计 1）。不能 rstrip，否则列坐标整体左移。"""
    return len(strip_tags(pre_inner))


def parse_annotated(html: str):
    """按 div.g 切段；段内保留 <pre> 的原始顺序，把注释行挂到它上面那条正文行。

    返回结构：[[ (text_pre, [note_pre, ...]), ... ], ...]
    列坐标只在同一行内可比——原作者是用 &nbsp; 把音标/释义推到对应词的
    水平位置，跨行比较必然错位。
    """
    blocks = re.findall(r"<div class='g'>(.*?)</div>", html, re.S)
    segs = []
    for blk in blocks:
        pres = re.findall(r"<pre>(.*?)</pre>", blk, re.S)
        groups = []  # [[text_pre, [note_pre...]], ...]
        for pre in pres:
            if _note_only(pre):
                if groups:
                    groups[-1][1].append(pre)
                else:
                    groups.append(["", [pre]])
            else:
                groups.append([pre, []])
        segs.append(groups)
    return segs


def _note_only(pre: str) -> bool:
    """去掉音标/释义 span 后，这一行是否只剩空白。"""
    s = pre
    for m in SPAN_RE.finditer(pre):
        style = m.group(1)
        if IPA in style or GLOSS in style:
            s = s.replace(m.group(0), "")
    return strip_tags(s).strip() == ""


def spans_of(pre: str):
    """返回 [(kind, text, start_col)]，kind: word/ipa/gloss/proper/phrase"""
    out = []
    for m in SPAN_RE.finditer(pre):
        style, inner = m.group(1), m.group(2)
        txt = strip_tags(inner).strip()
        col = line_width(pre[: m.start()])
        if RED in style or GREEN in style:
            out.append(("word", txt, col))
        elif BLUE in style:
            out.append(("proper", txt, col))
        elif YEL in style:
            out.append(("phrase", txt, col))
        elif IPA in style:
            out.append(("ipa", txt, col))
        elif GLOSS in style:
            out.append(("gloss", txt, col))
    return out


def pair_group(text_pre: str, note_pres):
    """把同一组（正文行 + 其下若干注释行）里的音标/释义，按列吸附到词上。"""
    targets = []
    for kind, txt, col in spans_of(text_pre):
        if kind in ("word", "proper", "phrase"):
            targets.append({"kind": kind, "word": txt, "col": col, "ipa": "", "gloss": ""})

    pairs, pending = [], None
    for pre in note_pres:
        for kind, txt, col in spans_of(pre):
            if kind == "ipa":
                pending = (txt, col)
            elif kind == "gloss":
                if pending:
                    pairs.append({"ipa": pending[0], "gloss": txt, "col": pending[1]})
                    pending = None
                else:
                    pairs.append({"ipa": "", "gloss": txt, "col": col})

    used = set()
    # 数量相等时，作者一定是按正文出现顺序写的注释，直接 1:1 最稳；
    # 列匹配只在数量不等时兜底（避免 &nbsp; 居中偏移把相邻词抢走）。
    if len(pairs) == len(targets) and targets:
        for t, p in zip(targets, pairs):
            t["ipa"], t["gloss"] = p["ipa"], p["gloss"]
        return targets

    for p in pairs:
        best, bestd = None, 10 ** 9
        for i, t in enumerate(targets):
            if i in used:
                continue
            d = abs(t["col"] - p["col"])
            if d < bestd:
                best, bestd = i, d
        if best is not None and bestd <= 18:
            targets[best]["ipa"] = p["ipa"]
            targets[best]["gloss"] = p["gloss"]
            used.add(best)
        else:
            targets.append({"kind": "bare", "word": "", "col": p["col"],
                            "ipa": p["ipa"], "gloss": p["gloss"]})
    return targets


def pair_by_column(seg):
    """对整段做配对，返回扁平列表。"""
    out = []
    for text_pre, note_pres in seg:
        out.extend(pair_group(text_pre, note_pres))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    key = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "./articles/2026/10"
    clean = read(os.path.join(base, f"{key}.clean.html"))
    trans = read(os.path.join(base, f"{key}.translated.html"))
    anno = read(os.path.join(base, f"{key}.annotated.html"))

    title, en_paras = parse_clean(clean)
    pairs = parse_translated(trans)
    segs = parse_annotated(anno)

    print(f"标题：{title[:70]}")
    print(f"clean 英文段：{len(en_paras)}   translated 段对：{len(pairs)}   annotated 段：{len(segs)}")
    print()

    all_items = []
    for s in segs:
        all_items.append(pair_by_column(s))

    words = [i for seg in all_items for i in seg if i["kind"] == "word"]
    props = [i for seg in all_items for i in seg if i["kind"] == "proper"]
    phr = [i for seg in all_items for i in seg if i["kind"] == "phrase"]
    print(f"生词 {len(words)}（有释义 {sum(1 for w in words if w['gloss'])}，有音标 {sum(1 for w in words if w['ipa'])}）")
    print(f"专名 {len(props)}（有释义 {sum(1 for w in props if w['gloss'])}）")
    print(f"搭配 {len(phr)}（有释义 {sum(1 for w in phr if w['gloss'])}）")
    print()
    print("前 3 段解析样例：")
    for si in range(min(3, len(segs))):
        nlines = len(segs[si])
        print(f"\n[段 {si+1}] 正文 {nlines} 行 / 注释行 {sum(len(g[1]) for g in segs[si])} 行")
        print("  中文：", (pairs[si][1][:60] + "…") if si < len(pairs) and pairs[si][1] else "（配对失败）")
        for it in all_items[si][:10]:
            print(f"  · {it['kind']:6s} {it['word'][:24]:26s} {it['ipa'][:16]:18s} {it['gloss'][:20]}")


if __name__ == "__main__":
    main()
