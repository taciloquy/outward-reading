#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精读页装配器：以 10-30 页为母版，把 content JSON 装配成完整精读页。

用法：
  python3 scripts/build-reading-page.py <content.json> <output.html>

JSON 结构见 scripts/reading-content-schema.md（或参考 workbuddy 目录下 10-31 的 content 文件）。
母版固定用 articles/2026/10/2026-10-30_001.reading.html（含最新打印链路与按钮文案）。
"""
import json, re, sys, base64, os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO, "articles/2026/10/2026-10-30_001.reading.html")


def die(msg):
    print("错误：" + msg)
    sys.exit(1)


def mm_gate_check(c, out_path):
    """完整笔记（有音频/练习）的正式页面必须过导图闸门（用户 2026-11-08 定）。

    规则：完整笔记上线前也要先让用户确认导图骨架，确认之后才做手绘版。
    闸门只拦「写进仓库」的正式页面；指到 /tmp 的自查输出照常放行。
    """
    practice = c.get("practice") or {}
    is_notes = bool(c.get("audio")) or bool(practice.get("items") or practice.get("answer"))
    if not is_notes:
        return
    r = subprocess.run([sys.executable, os.path.join(REPO, "scripts/mm-gate.py"),
                        "--date", c.get("gate_key", c["date"]), "--stage", "publish"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return
    print(((r.stdout or "") + (r.stderr or "")).strip())
    if not os.path.abspath(out_path).startswith(REPO + os.sep):
        print("（输出在仓库外，按自查用途放行）")
        return
    print("\n错误：导图闸门未通过，正式页面不写。")
    print("  顺序：写骨架 → scripts/mm-preflight.py 出表 → 把骨架表报给用户 → ")
    print("        用户确认后 preflight --confirm → 再构建上线。")
    print("  只想先看版式：把输出路径指到 /tmp 即可。")
    sys.exit(23)


def note_html(n):
    parts = [f"<b>{n['w']}</b> {n.get('ipa','')} {n.get('pos','')}".rstrip()]
    parts.append(f"英文释义：{n['en']}")
    parts.append(f"中文释义：{n['zh']}")
    if n.get("ctx"):
        parts.append(f"文中意：{n['ctx']}")
    if n.get("ex1"):
        parts.append(f"例句一：{n['ex1']}")
    if n.get("ex2"):
        parts.append(f"例句二：{n['ex2']}")
    return "<br>".join(parts)


def assign_notes(sec_html, prefix, notes):
    """按出现顺序给 <mark class="voc"> 补 data-note，并校验数量。"""
    marks = re.findall(r'<mark class="voc"[^>]*>', sec_html)
    if len(marks) != len(notes):
        die(f"{prefix}：mark 数 {len(marks)} != 注释数 {len(notes)}")
    idx = [0]
    def sub(m):
        idx[0] += 1
        tag = m.group(0)
        if "data-note" in tag:
            return tag
        return tag.replace('<mark class="voc"', f'<mark class="voc" data-note="n-{prefix}-{idx[0]}"')
    out = re.sub(r'<mark class="voc"[^>]*>', sub, sec_html)
    return out


def build_section(sec_id, p_label, toggle_text, en_html, zh, notes, prefix, headline=False):
    marks = assign_notes(en_html, prefix, notes)
    note_divs = "\n".join(
        f'        <div class="note-item" id="n-{prefix}-{i+1}">{note_html(n)}</div>'
        for i, n in enumerate(notes))
    ng = f'\n      <div class="notes-group">\n{note_divs}\n      </div>' if notes else ""
    # 没有注释就不出折叠按钮：否则按钮找不到兄弟节点，点击会报 JS 错
    btn = f'\n      <button class="notes-toggle" onclick="toggleNotes(this)">{toggle_text}</button>' if notes else ""
    sec_cls = "paragraph headline-block" if headline else "paragraph"
    en_cls = "headline-en" if headline else "en-block en"
    # 原文无译文时不出译文块（否则留一条空白灰带）
    zh_html = f'\n      <div class="zh-block">{zh}</div>' if zh and zh.strip() else ""
    return f'''    <section class="{sec_cls}" id="{sec_id}">
      <div class="p-label">{p_label}</div>
      <div class="{en_cls}">{marks}</div>{zh_html}{btn}{ng}
    </section>'''


def main():
    if len(sys.argv) != 3:
        die("用法：build-reading-page.py <content.json> <output.html>")
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    mm_gate_check(c, sys.argv[2])
    s = open(TEMPLATE, encoding="utf-8").read()

    # 0.5 紧凑打印：段落数 ≥11 或显式 print_compact 时给 body 加 class，
    #     把打印从 3 页压回 2 页（只改间距，不动内容；CSS 在母版 scoped）。
    paras_n = len(c.get("paragraphs") or [])
    if c.get("print_compact") or paras_n >= 11:
        s = s.replace("<body>", '<body class="print-compact">', 1)

    # 1. <title>
    s = re.sub(r"<title>.*?</title>", f"<title>{c['title_tag']}</title>", s, flags=re.S)

    # 2. h1 与 meta
    s = re.sub(r"<h1>.*?</h1>", f"<h1>{c['h1']}</h1>", s, count=1, flags=re.S)
    meta = (f'<div class="meta">\n      <span>日期：{c["date"]}</span>\n'
            f'      <span>分类：{c["category"]}</span>\n'
            f'      <span>阅读时长：约 {c.get("read_minutes",18)} 分钟</span>\n    </div>')
    s = re.sub(r'<div class="meta">.*?</div>', meta, s, count=1, flags=re.S)

    # 3. back-cal 日期
    s = re.sub(r'index\.html\?d=\d{4}-\d{2}-\d{2}', f'index.html?d={c["date"]}', s)

    # 4. 思维导图区（到 headline 开始前）
    mm = c["mindmap"]
    img_b64 = ""
    if mm.get("img"):
        raw = open(mm["img"], "rb").read()
        try:  # 压到手绘导图宽 ≤1400px、q86（笔记风导图含大量小字，1000px 会糊）
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.width > 1400:
                im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=86)
            raw = buf.getvalue()
        except Exception:
            pass
        img_b64 = base64.b64encode(raw).decode()
    # 课件原版图（共读）：作为导图区第三个视图，不单独占正文尾部
    extra_b64 = ""
    if mm.get("extra_img"):
        raw = open(mm["extra_img"], "rb").read()
        try:  # 中文图要能看字：留到 1400px 宽、q88，配合 1:1 放大仍清晰
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.width > 1400:
                im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
            raw = buf.getvalue()
        except Exception:
            pass
        extra_b64 = base64.b64encode(raw).decode()
    # 默认显示手绘版（用户 2026-11-03：手绘版更容易留印象）；没有手绘图时退回矢量版
    vector_attr = ' style="display:none"' if img_b64 else ""
    image_attr = "" if img_b64 else ' style="display:none"'
    vector_active = "" if img_b64 else " active"
    image_active = " active" if img_b64 else ""
    # 手绘图点击放大浮层（仅在有手绘图时需要）；片段与 inject-mm-lightbox.py 共用
    lb = ""
    if img_b64 or extra_b64:
        lb_path = os.path.join(REPO, "scripts/assets/mm-lightbox.html")
        if os.path.exists(lb_path):
            lb = open(lb_path, encoding="utf-8").read()
    # 无手绘图时不留空标签：手绘版按钮与容器一并省略，避免点开是一片空白
    if img_b64:
        mm_btns = (f'<button class="mm-btn{vector_active}" id="mm-vector-btn" '
                   f'onclick="showMindmap(\'vector\',this)">矢量版</button>\n'
                   f'        <button class="mm-btn{image_active}" '
                   f'onclick="showMindmap(\'image\',this)">手绘版</button>')
        mm_views = (f'''<div class="mm-view" id="mm-vector"{vector_attr}>
      {mm["svg"]}
      </div>
      <div class="mm-view" id="mm-image"{image_attr}>
        <img src="data:image/jpeg;base64,{img_b64}" alt="{mm.get("alt","手绘版思维导图")}">
      </div>''')
    else:
        mm_btns = ('<button class="mm-btn active" id="mm-vector-btn" '
                   'onclick="showMindmap(\'vector\',this)">矢量版</button>')
        mm_views = f'''<div class="mm-view" id="mm-vector">
      {mm["svg"]}
      </div>'''
    # 课件原版图：并入导图区做第三视图（点击可放大）
    if extra_b64:
        mm_btns += ('\n        <button class="mm-btn" '
                    'onclick="showMindmap(\'extra\',this)">课件原图</button>')
        extra_cap = mm.get("extra_caption", "课件原版导图 · 与矢量/手绘版内容对应，点击可放大")
        extra_alt = mm.get("extra_alt", "课件原版思维导图")
        mm_views += (f'''
      <div class="mm-view" id="mm-extra" style="display:none">
        <div style="font-size:13px;color:#7b7266;margin:2px 2px 8px">{extra_cap}</div>
        <img src="data:image/jpeg;base64,{extra_b64}" alt="{extra_alt}">
      </div>''')
    mm_head = f'''<section class="mindmap" id="mindmap">
      <div class="mm-switch">
        <button class="mm-btn" id="mm-all-btn" onclick="toggleAllMindmap()">全部收起</button>
        {mm_btns}
      </div>
      {mm_views}
    </section>
{lb}

    '''
    m = re.search(r'<section class="mindmap" id="mindmap">', s)
    e = s.index('<section class="paragraph headline-block" id="p-headline">')
    s = s[:m.start()] + mm_head + s[e:]

    # 5. headline 区块
    hl = c["headline"]
    s = re.sub(
        r'<section class="paragraph headline-block" id="p-headline">.*?</section>',
        build_section("p-headline", f'{c["source_label"]} · 标题', "查看标题注释",
                      hl["en_html"], hl["zh"], hl["notes"], "p-headline", headline=True),
        s, count=1, flags=re.S)

    # 6. 正文段落：整段替换（母版 9 段，各篇段数不定）
    paras = c["paragraphs"]
    gen = []
    for n, p in enumerate(paras, 1):
        gen.append(build_section(f"p{n}", f"Paragraph {n}", "查看本段注释",
                                 p["en_html"], p["zh"], p.get("notes", []), f"p{n}"))
    spans = [(m.start(), m.end()) for m in re.finditer(r'<section class="paragraph" id="p\d+">.*?</section>', s, re.S)]
    if not spans:
        die("母版中找不到正文段落")
    s = s[:spans[0][0]] + ("\n\n".join(gen)) + s[spans[-1][1]:]

    # 7. 词汇列表（tab-1）与专有名词（tab-2）
    rows, vi = [], 0
    if hl["notes"]:
        for n in hl["notes"]:
            vi += 1
            rows.append(f'<div class="row" id="v-{vi}"><div class="row-top"><span class="w en">{n["w"]}</span><span class="ph en">{n.get("ipa","")}</span><a class="src" href="#p-headline">标题</a></div><div class="def">英文释义：{n["en"]}</div></div>')
    for pi, p in enumerate(paras, 1):
        for n in p.get("notes", []):
            vi += 1
            rows.append(f'<div class="row" id="v-{vi}"><div class="row-top"><span class="w en">{n["w"]}</span><span class="ph en">{n.get("ipa","")}</span><a class="src" href="#p{pi}">¶{pi}</a></div><div class="def">英文释义：{n["en"]}</div></div>')
    vocab_block = "\n".join(rows) + "\n            "

    proper_rows = []
    for i, pn in enumerate(c["proper"], 1):
        inner = pn["def"] + (f'<div class="def role">{c["sources_note"]}</div>' if i == len(c["proper"]) and c.get("sources_note") else "")
        proper_rows.append(f'<div class="row" id="pn-{i}"><div class="row-top"><span class="w">{pn["name"]}</span></div><div class="def">{inner}</div></div>')
    proper_block = "\n".join(proper_rows) + "\n            "

    # 边界手术：vocab-list 到 tab-2 之间
    a = s.index('<div class="tab-list" id="vocab-list">') + len('<div class="tab-list" id="vocab-list">')
    b = s.index('<div class="tab-pane" id="tab-2">', a)
    # 原区间末尾是 rows + </div>(list) + </div>(pane tab-1) + 空行
    s = s[:a] + "\n" + vocab_block + "</div>\n          </div>\n\n          " + s[b:]
    a = s.index('<div class="tab-list" id="proper-list">') + len('<div class="tab-list" id="proper-list">')
    b = s.index('<div class="tab-pane" id="tab-3">', a)
    s = s[:a] + "\n" + proper_block + "</div>\n          </div>\n\n          " + s[b:]

    # 8. 段落导航（tab-3 p-nav）
    links = [f'<a href="#p-headline">标题 · {c["source_label"]}<span class="hint">{c.get("nav_hint","")}</span></a>']
    for pi, p in enumerate(paras, 1):
        hint = re.sub(r"<[^>]+>", "", p["en_html"])[:34] + "…"
        links.append(f'<a href="#p{pi}">Paragraph {pi}<span class="hint">{hint}</span></a>')
    pnav = "\n".join(links) + "\n              "
    a = s.index('<div class="p-nav">') + len('<div class="p-nav">')
    b = s.index('</div>', a)
    s = s[:a] + "\n" + pnav + s[b:]

    # 9. 练习区（原文无练习时整段隐藏，避免留一个空的「翻译练习」区）
    pr = c.get("practice") or {}
    has_practice = pr.get("items") or pr.get("answer") or pr.get("intro") or pr.get("critical_en")
    if has_practice:
        items_html = "<br><br>".join(f"{i+1}. {it}" for i, it in enumerate(pr.get("items") or []))
        ex_body = f"{pr.get('intro','')}<br><br>{items_html}"
        # 本期待无思考题时不留一个只有标题的空块（如 2026-11-12）。
        if pr.get("critical_en") or pr.get("critical_zh"):
            ex_body += (f"<br><br>Critical Thinking 课后思考<br>{pr.get('critical_en','')}"
                        f"<br><br>{pr.get('critical_zh','')}")
        practice = f'''<section class="practice" id="practice">
  <h2>翻译练习</h2>

  <div class="fold" id="fold-exercise">
    <button class="fold-head" onclick="toggleFold('fold-exercise')">
      <span>练习题</span><span class="arrow">▶</span>
    </button>
    <div class="fold-body">{ex_body}</div>
  </div>

  <div class="fold" id="fold-answer">
    <button class="fold-head" onclick="toggleFold('fold-answer')">
      <span>参考答案</span><span class="arrow">▶</span>
    </button>
    <div class="fold-body">{pr.get("answer","")}</div>
  </div>
</section>'''
    else:
        practice = ""
    s = re.sub(r'<section class="practice" id="practice">.*?</section>', lambda _: practice, s, count=1, flags=re.S)

    # 9.5 音频目录与开关：预习原文阶段不配音（audio=false），页面也不出现朗读/听全文按钮
    # audio_dir：同日第二篇（如【共读】）用独立音频目录，避免与 _001 冲突
    audio_on = bool(c.get("audio", True))
    audio_base = c.get("audio_dir") or f"audio/{c['date']}"
    if "PARA_AUDIO_BASE" in s:
        s = re.sub(r"var PARA_AUDIO_BASE = 'audio/[\w-]+'",
                   f"var PARA_AUDIO_BASE = '{audio_base}'", s)
        s = re.sub(r"var PARA_AUDIO_ENABLED = (?:true|false);",
                   f"var PARA_AUDIO_ENABLED = {'true' if audio_on else 'false'};", s)

    # 9.55 文末自带图（共读课件：中文图原样呈现，不翻译；打印隐藏以保 2 页）
    if c.get("tail_image") and not mm.get("extra_img"):
        raw = open(c["tail_image"], "rb").read()
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.width > 1100:
                im = im.resize((1100, round(im.height * 1100 / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
            raw = buf.getvalue()
        except Exception:
            pass
        b64 = base64.b64encode(raw).decode()
        tail = (f'<section class="tail-figure" id="tail-figure">\n'
                f'      <img src="data:image/jpeg;base64,{b64}" '
                f'alt="{c.get("tail_alt", "文末配图（课件原版，原样呈现）")}" '
                f'style="display:block;max-width:100%;height:auto;margin:26px auto 8px;'
                f'border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.12)">\n'
                f'    </section>\n'
                f'    <style>@media print{{.tail-figure{{display:none !important}}}}</style>\n\n    ')
        spans = [(m.start(), m.end())
                 for m in re.finditer(r'<section class="paragraph" id="p\d+">.*?</section>', s, re.S)]
        s = s[:spans[-1][1]] + "\n\n" + tail + s[spans[-1][1]:]

    # 9.7 打印紧凑模式：预习版自然段多、但打印必须正好 2 页时，只压缩打印态留白，
    # 绝不合并原文段落（2026-11-11 用户定：预习版段落编号要与次日完整笔记对齐，
    # 完整笔记才是最终版，会带逐段译文/词卡）。仅 @media print 生效，屏幕版式不变。
    # 在 content JSON 里写 "print_compact": true 可显式开启；段落 >= 11 时自动兜底
    # （次日完整笔记往往沿用原文的 12 段，打印只出英文正文，同样需要紧凑留白）。
    if c.get("print_compact") or len(paras) >= 11:
        compact = (
            '<style id="print-compact">@media print{\n'
            '  .paragraph,.headline-block{margin:0 0 5pt !important}\n'
            '  .p-label{margin:0 0 2pt !important}\n'
            '  .en-block{line-height:1.48 !important}\n'
            '  h1{margin:0 0 4pt !important}\n'
            '}</style>\n'
        )
        s = s.replace("</head>", compact + "</head>", 1)

    open(sys.argv[2], "w", encoding="utf-8").write(s)
    print(f"已生成 {sys.argv[2]}（{len(s)//1024} KB，段落 {len(paras)}，词汇 {vi}，专名 {len(c['proper'])}）")

    # 9.6 翻页导航：母版里的「上一篇／下一篇」是 10-30 的邻居，直接沿用会链到别人身上。
    # 装配完立刻按 articles.js 的 ARTICLES 重注入一遍（幂等，integrate 里再跑也无害）。
    nav = os.path.join(REPO, "scripts/inject-seq-nav.py")
    if os.path.exists(nav):
        r = subprocess.run([sys.executable, nav, c["date"]],
                           capture_output=True, text=True)
        print(r.stdout.strip() or "", end="")
        if r.returncode != 0:
            print(f"  ⚠ 翻页导航注入失败（返回 {r.returncode}）：{r.stderr.strip()[:200]}")
            print("    务必手动跑 scripts/inject-seq-nav.py "
                  f"{c['date']}，否则翻页会指向母版 10-30 的邻居。")


if __name__ == "__main__":
    main()
