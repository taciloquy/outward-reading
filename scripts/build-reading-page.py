#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精读页装配器：以 10-30 页为母版，把 content JSON 装配成完整精读页。

用法：
  python3 scripts/build-reading-page.py <content.json> <output.html>

JSON 结构见 scripts/reading-content-schema.md（或参考 workbuddy 目录下 10-31 的 content 文件）。
母版固定用 articles/2026/10/2026-10-30_001.reading.html（含最新打印链路与按钮文案）。
"""
import json, re, sys, base64, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO, "articles/2026/10/2026-10-30_001.reading.html")


def die(msg):
    print("错误：" + msg)
    sys.exit(1)


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
    sec_cls = "paragraph headline-block" if headline else "paragraph"
    en_cls = "headline-en" if headline else "en-block en"
    return f'''    <section class="{sec_cls}" id="{sec_id}">
      <div class="p-label">{p_label}</div>
      <div class="{en_cls}">{marks}</div>
      <div class="zh-block">{zh}</div>

      <button class="notes-toggle" onclick="toggleNotes(this)">{toggle_text}</button>{ng}
    </section>'''


def main():
    if len(sys.argv) != 3:
        die("用法：build-reading-page.py <content.json> <output.html>")
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    s = open(TEMPLATE, encoding="utf-8").read()

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
        try:  # 压到手绘导图宽 ≤1000px、q80，控制单页体积
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.width > 1000:
                im = im.resize((1000, round(im.height * 1000 / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            raw = buf.getvalue()
        except Exception:
            pass
        img_b64 = base64.b64encode(raw).decode()
    mm_head = f'''<section class="mindmap" id="mindmap">
      <div class="mm-switch">
        <button class="mm-btn" id="mm-all-btn" onclick="toggleAllMindmap()">全部收起</button>
        <button class="mm-btn active" id="mm-vector-btn" onclick="showMindmap('vector',this)">矢量版</button>
        <button class="mm-btn" onclick="showMindmap('image',this)">手绘版</button>
      </div>
      <div class="mm-view" id="mm-vector">
      {mm["svg"]}
      </div>
      <div class="mm-view" id="mm-image" style="display:none">
        <img src="data:image/jpeg;base64,{img_b64}" alt="{mm.get("alt","手绘版思维导图")}">
      </div>
    </section>

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

    # 9. 练习区
    pr = c["practice"]
    items_html = "<br><br>".join(f"{i+1}. {it}" for i, it in enumerate(pr["items"]))
    ex_body = f"{pr['intro']}<br><br>{items_html}<br><br>Critical Thinking 课后思考<br>{pr['critical_en']}<br><br>{pr['critical_zh']}"
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
    <div class="fold-body">{pr["answer"]}</div>
  </div>
</section>'''
    s = re.sub(r'<section class="practice" id="practice">.*?</section>', lambda _: practice, s, count=1, flags=re.S)

    open(sys.argv[2], "w", encoding="utf-8").write(s)
    print(f"已生成 {sys.argv[2]}（{len(s)//1024} KB，段落 {len(paras)}，词汇 {vi}，专名 {len(c['proper'])}）")


if __name__ == "__main__":
    main()
