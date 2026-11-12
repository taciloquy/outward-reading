#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构化解析结果 + 期次配置 → scripts/content/YYYY-MM-DD.json（装配器吃的格式）。

用法：
    python3 scripts/parse-notes-pdf.py "<课件.pdf>" --out /tmp/2026-11-02-parsed.json
    python3 scripts/make-content-json.py /tmp/2026-11-02-parsed.json \
        --issue scripts/content/issues/2026-11-02.json \
        --out  scripts/content/2026-11-02.json

期次配置（issues/*.json）字段见 scripts/content/issues/2026-11-02.json 示例。
`marks` 缺省时按卡片词自动在原文里找位置（支持 -s/-ed/-ing/-ies 变形），
自动找不到的会列出来，去 marks / headline_marks 里手工补「卡片词 → 原文写法」。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = '\u4e00-\u9fff！？，。、；：“”‘’"\'（）《》—…·'


def tidy(s):
    s = s or ''
    s = s.replace('— —', '——').replace('—— ——', '——')
    s = re.sub(r'(?<=[' + CJK + r'])\s+(?=[' + CJK + r'])', '', s)   # 中文之间的 PDF 断行空格
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip()


def _variants(token):
    """单个词的合法变形：复数/过去式/进行时/比较级。"""
    out = [token]
    if token.endswith('e'):
        out += [token[:-1] + x for x in ('ing', 'ed', 'es', 's', 'd')]
    elif token.endswith('y') and len(token) > 2:
        out += [token[:-1] + 'ies', token + 's', token + 'ed']
    else:
        out += [token + x for x in ('s', 'es', 'ed', 'd', 'ing')]
        if len(token) > 3 and token[-1] not in 'aeiou' and token[-2] in 'aeiou' and token[-3] not in 'aeiou':
            out.append(token + token[-1] + 'ing')      # 双写辅音
    return out


def _pattern(surface):
    """把「原文写法」变成容错正则（空格弹性 + 末词变形）。"""
    toks = surface.split()
    head = r'\s+'.join(re.escape(t) for t in toks[:-1])
    last = _variants(toks[-1])
    tail = '(?:' + '|'.join(re.escape(v) for v in sorted(last, key=len, reverse=True)) + ')'
    return (head + r'\s+' if head else '') + tail


def find_surface(text, surface, start=0):
    pat = re.compile(_pattern(surface), re.I)
    m = pat.search(text, start)
    if not m and start:
        # 回退全文搜时必须确保命中点在 start 之后，否则游标会倒退、
        # 导致 text[pos:m.start()] 切出空串后再拼一遍，成段文字被重复。
        m2 = pat.search(text)
        if m2 and m2.start() >= start:
            m = m2
    return m


def auto_mark(text, cards, overrides=None):
    """按卡片顺序在原文里定位并包 <mark>；返回 (html, 未命中的卡片词)。"""
    overrides = overrides or []
    pairs = overrides if overrides else [[c['w'], c['w']] for c in cards]
    if len(pairs) != len(cards):
        sys.exit(f'✗ marks 条数 {len(pairs)} ≠ 卡片数 {len(cards)}')
    out, pos, missing = [], 0, []
    for word, surface in pairs:
        cand = [surface]
        base = word.split(' / ')[0]
        cand += [base, base + 's', base.rstrip('e') + 'ing']
        m = None
        for s in cand:
            m = find_surface(text, s, pos)
            if m:
                break
        if not m:
            missing.append((word, surface))
            continue
        out.append(text[pos:m.start()])
        out.append(f'<mark class="voc">{m.group(0)}</mark>')
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out), missing


def card_surface(w):
    """卡片词 → 可在正文里检索的写法。

    去掉 PDF 常见装饰：「cool（动词）」的中文括注、「capital spending / capex」
    的备选写法——否则这些卡在正文里永远定位不到，连带整段排序失效。
    """
    s = re.sub(r'（[^）]*）', '', w or '').strip()
    return s.split(' / ')[0].strip() or (w or '')


def order_cards_by_position(text, cards, marks_pairs=None):
    """按词卡在正文中首次出现的位置重排；marks 的「词→写法」随卡片一起重排。

    返回 (cards_sorted, marks_pairs_sorted)。任何一张卡在正文里找不到时保持原顺序，
    交给 auto_mark 报错，避免把真正的问题掩盖掉。
    """
    surf = {w: s for w, s in (marks_pairs or [])}
    pos = []
    for c in cards:
        # 卡片词本身不可检索时（如 be not limited to → was not limited to），
        # 退到 marks 里登记的原文写法，排序才不会整体失效。
        cands = [card_surface(c['w'])]
        alt = surf.get(c['w'])
        if alt and alt not in cands:
            cands.append(alt)
        hit = None
        for s in cands:
            m = find_surface(text, s, 0)
            if m:
                hit = m.start()
                break
        pos.append(hit)
    if any(p is None for p in pos):
        return cards, marks_pairs
    order = sorted(range(len(cards)), key=lambda i: pos[i])
    cards2 = [cards[i] for i in order]
    if not marks_pairs:
        return cards2, marks_pairs
    return cards2, [[c['w'], surf.get(c['w'], c['w'])] for c in cards2]


def card_out(c):
    return {'w': c['w'], 'ipa': c['ipa'], 'pos': c['pos'],
            'en': tidy(c['en']), 'zh': tidy(c['zh']), 'ctx': tidy(c['ctx']),
            'ex1': tidy(c['ex1']), 'ex2': tidy(c['ex2'])}


def main():
    ap = argparse.ArgumentParser(description='解析结果 + 期次配置 → 内容 JSON')
    ap.add_argument('parsed')
    ap.add_argument('--issue', required=True, help='期次配置 JSON（标题/刊名/导图映射等）')
    ap.add_argument('--out', required=True)
    ap.add_argument('--rebuild-mindmap', action='store_true',
                    help='输出文件已存在时，强制用模板重新生成导图（默认沿用已有的手工导图）')
    a = ap.parse_args()

    d = json.load(open(a.parsed, encoding='utf-8'))
    cfg = json.load(open(a.issue, encoding='utf-8'))
    marks = {str(k): v for k, v in (cfg.get('marks') or {}).items()}

    # ---------- 标题 ----------
    hl_cards = [card_out(c) for c in d['headline_cards']]
    if cfg.get('headline_html'):
        hl_html = cfg['headline_html']
    else:
        hl_html, miss = auto_mark(cfg['headline_en'], hl_cards, cfg.get('headline_marks'))
        if miss:
            sys.exit('✗ 标题里找不到这些卡片词：' + '；'.join(f'{w}→{s}' for w, s in miss)
                     + '\n  在 issue 的 headline_marks 里补「卡片词, 原文写法」。')
    # 标题卡片可能同时取自主标题与副标题（PDF 的 headline_cards 混装）。
    # 按卡片词在标题全文里的首次出现位置重排，词卡列表才不会跳序。
    hl_plain = re.sub(r'<[^>]+>', '', hl_html).replace('|', ' ')
    hl_cards, _ = order_cards_by_position(hl_plain, hl_cards, None)
    # `|` 之后是副标题（deck）：拆成独立一行（.headline-sub），不把竖线渲染出来。
    if '|' in hl_html:
        parts = [p.strip() for p in hl_html.split('|') if p.strip()]
        hl_html = (f'<span>{parts[0]}</span>'
                   + ''.join(f'<span class="headline-sub">{p}</span>' for p in parts[1:]))

    # ---------- 正文 ----------
    # PDF 里浮动的批注/图注偶尔会插进词中间（如 approacrare-earth empireh），
    # 这类段落在 issue 的 paragraph_overrides 里给正确原文（只改英文，其它照旧）。
    overrides = {str(k): v for k, v in (cfg.get('paragraph_overrides') or {}).items()}
    paras, problems = [], []
    for p in d['paragraphs']:
        n = p['n']
        cards = [card_out(c) for c in d['para_cards'].get(str(n)) or d['para_cards'].get(n) or []]
        if not cards and n != 0:
            # 第 0 段是无编号导语，本来就不带词卡；其余段落无卡说明解析出错。
            sys.exit(f'✗ 第 {n} 段没有词卡，检查 PDF 或 --drop 是否误删')
        en = overrides.get(str(n), p['en'])
        if str(n) in overrides:
            print(f'  · 第 {n} 段用配置里的原文覆盖（PDF 抽取有误）')
        # PDF 词卡偶有不按正文出现顺序排列（如把短语卡放段末），
        # 这里按各卡在正文中的首次出现位置重排，marks 的「词→写法」映射随之重排。
        cards, marks_n = order_cards_by_position(en, cards, marks.get(str(n)))
        html, miss = auto_mark(en, cards, marks_n)
        if miss:
            problems.append((n, miss))
        paras.append({'en_html': html, 'zh': tidy(p['zh']), 'notes': cards})
    if problems:
        msg = '\n'.join(f'  第 {n} 段：' + '；'.join(f'{w}→{s}' for w, s in m) for n, m in problems)
        sys.exit('✗ 这些卡片词在原文里定位不到，先在 issue 的 marks 里补「卡片词, 原文写法」：\n' + msg)

    # ---------- 专名 ----------
    proper = []
    for pn in d['proper']:
        txt = tidy(pn['def'])
        txt = txt.replace('本文中的意思：', '<br>本文中的意思：', 1)
        proper.append({'name': tidy(pn['name']), 'def': txt})

    # ---------- 练习 ----------
    answers = [tidy(x) for x in d['answers']]
    answer_html = '<br><br>'.join(f'{i}. {x}' for i, x in enumerate(answers, 1))

    # ---------- 导图 SVG：克隆模板只换字 ----------
    # 已有输出文件里的导图是人工归纳的成果（含手绘图路径），默认原样继承；
    # 完整笔记覆盖同一期时不得冲掉，须显式 --rebuild-mindmap 才按模板重做。
    mm = cfg['mindmap']
    prev_mm = None
    if not a.rebuild_mindmap and os.path.exists(a.out):
        try:
            prev_mm = json.load(open(a.out, encoding='utf-8')).get('mindmap')
        except Exception:
            prev_mm = None
    if prev_mm and (prev_mm.get('svg') or '').strip():
        mindmap = {'aria': prev_mm.get('aria', ''),
                   'alt': prev_mm.get('alt', ''),
                   'svg': prev_mm['svg'],
                   'img': prev_mm.get('img', '')}
        print(f'导图：沿用 {a.out} 中已有的手工导图（{len(prev_mm["svg"])} 字符，'
              f'手绘图{"有" if prev_mm.get("img") else "无"}路径）')
        if prev_mm.get('img') and not os.path.exists(prev_mm['img']):
            print(f'  ⚠ 手绘图文件不存在：{prev_mm["img"]}，构建后需重新指定或重嵌')
    else:
        svg = json.load(open(os.path.join(ROOT, mm['template']), encoding='utf-8'))['mindmap']['svg']
        for old, new in mm.get('repl', []):
            if old not in svg:
                sys.exit(f'✗ 导图模板里找不到文字「{old}」，模板换错了？')
            svg = svg.replace(old, new)
        left = re.findall(r'<text[^>]*>([^<]*)</text>', svg)
        if mm.get('template_texts') and len(left) != mm['template_texts']:
            print(f'⚠ 导图文本节点 {len(left)} 个（配置写 {mm["template_texts"]} 个），请目检')
        mindmap = {'aria': mm.get('aria', ''), 'alt': mm.get('alt', ''), 'svg': svg, 'img': ''}

    category = cfg['category']
    # 惯例：category 里「外刊讲解 第N天」带空格，title_tag 里不带
    tag_style = re.sub(r'\s+', '', category)
    out = {
        'date': cfg['date'],
        'title_tag': cfg.get('title_tag') or f'{cfg["h1"]}—— {tag_style}',
        'h1': cfg['h1'],
        'source_label': cfg.get('source_label', ''),
        'category': category,
        'read_minutes': cfg.get('read_minutes', 18),
        'nav_hint': cfg.get('nav_hint', ''),
        'headline': {'en_html': hl_html, 'zh': tidy(cfg.get('headline_zh', '')), 'notes': hl_cards},
        'paragraphs': paras,
        'proper': proper,
        'sources_note': cfg.get('sources_note', ''),
        'practice': {
            'intro': cfg.get('practice_intro', '请将以下中文句子翻译为英文（参考答案见后）。'),
            'items': [tidy(x) for x in d['practice']],
            'critical_en': cfg.get('critical_en', ''),
            'critical_zh': cfg.get('critical_zh', ''),
            'answer': answer_html,
        },
        'mindmap': mindmap,
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    total = len(hl_cards) + sum(len(p['notes']) for p in paras)
    print(f'段落 {len(paras)} | 词卡 {total}（标题 {len(hl_cards)} + 正文 {total - len(hl_cards)}）'
          f' | 专名 {len(proper)} | 练习 {len(out["practice"]["items"])} | 答案 {len(answers)}')
    print(f'→ {a.out}')
    if not out['practice']['critical_en']:
        print('  提示：本期待无 Critical Thinking 段，critical_en/zh 已置空')


if __name__ == '__main__':
    main()
