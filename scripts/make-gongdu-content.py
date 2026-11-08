#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共读内容装配器：parse-gongdu-pdf.py 的输出 → 精读页 content JSON。

词卡定位：按 标题 → ¶1..N 的阅读顺序，给每个词条找正文首现位置（带屈折变形：
-s/-es/-ed/-ing/y→ies/y→ier/去e加ing 等），按出现顺序重排 notes 并打
<mark class="voc">；标题区词条进 headline.notes，正文词条进对应段 notes。
用法：
  python3 scripts/make-gongdu-content.py <parsed.json> <content.json> [--meta meta.json]
"""
import json, re, sys, os, argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def inflect(word):
    """常见屈折变形。"""
    w = word.lower()
    forms = {w, w + 's'}
    if re.search(r'(ch|sh|s|x|z)$', w):
        forms |= {w + 'es'}
    if w.endswith('y') and len(w) > 1 and w[-2] not in 'aeiou':
        forms |= {w[:-1] + 'ies', w[:-1] + 'ied', w[:-1] + 'ier', w[:-1] + 'iest', w[:-1] + 'ily'}
    if w.endswith('e') and len(w) > 1:
        forms |= {w + 'd', w[:-1] + 'ing'}
    elif w.endswith('ee') or w.endswith('oe') or w.endswith('ye'):
        forms |= {w + 'd', w + 'ing'}
    else:
        forms |= {w + 'ed', w + 'ing'}
        # 双写辅音：run→running 类（仅对短词尝试，误报无害——仍需整体匹配）
        if len(w) >= 3 and w[-1] not in 'aeiouwy' and w[-2] in 'aeiou':
            forms |= {w + w[-1] + 'ed', w + w[-1] + 'ing'}
    if w.endswith('f'):
        forms |= {w[:-1] + 'ves'}
    return forms


def surface_pattern(surface):
    """短语匹配：词间允许空格/连字符，首尾词允许屈折，边界用字母断言。"""
    tokens = surface.lower().split()
    regex_parts = []
    for i, tok in enumerate(tokens):
        alts = sorted(inflect(tok) if i in (0, len(tokens) - 1) else {tok},
                      key=len, reverse=True)
        regex_parts.append('(?:' + '|'.join(re.escape(a) for a in alts) + ')')
    body = r'[\s\-]+'.join(regex_parts)
    return re.compile(r'(?<![A-Za-z])' + body + r'(?![A-Za-z])', re.I)


def match_entry(en_text, entry, overrides):
    """返回 (start, end, matched_surface)；找不到返回 None。"""
    ov = overrides.get(entry['w'])
    surfaces = [ov] if ov else [entry['w']]
    best = None
    for s in surfaces:
        m = surface_pattern(s).search(en_text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.end())
    return best


def mark_text(en_text, matches):
    """按位置从后往前插 <mark class="voc">。"""
    out = en_text
    for st, en in sorted(matches, key=lambda x: -x[0]):
        out = out[:st] + '<mark class="voc">' + out[st:en] + '</mark>' + out[en:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parsed')
    ap.add_argument('out')
    ap.add_argument('--meta', help='元信息覆盖 JSON（date/h1/source_label/category/...）')
    a = ap.parse_args()

    r = json.load(open(a.parsed, encoding='utf-8'))
    meta_path = os.path.join(REPO, 'scripts/content/gongdu-meta/2026-11-09.json')
    if a.meta:
        meta_path = a.meta
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.exists(meta_path) else {}
    overrides = meta.get('surface_overrides', {})

    # ---- 词卡定位 ----
    body_paras = [p for p in r['paragraphs'] if p['no'] >= 1]  # no=0 是标题词条伪段
    sections = []  # (key, text, entries)
    hl_text = r['en_title'] + ' ' + meta.get('headline_sub_en', '')
    sections.append(('headline', hl_text, []))
    for p in body_paras:
        sections.append((f"p{p['no']}", p['en'], []))

    all_entries = []
    for p in r['paragraphs']:
        for v in p['vocab']:
            all_entries.append(v)

    unmatched = []
    for v in all_entries:
        hit = None
        for key, text, bucket in sections:
            m = match_entry(text, v, overrides)
            if m:
                hit = (key, m)
                break
        if not hit:
            unmatched.append(v['w'])
            continue
        for i, (key, text, bucket) in enumerate(sections):
            if key == hit[0]:
                bucket.append({'entry': v, 'pos': hit[1]})
                break

    # ---- 组装 ----
    hl_entries = sorted(sections[0][2], key=lambda x: x['pos'][0])
    hl_text_marked = mark_text(sections[0][1], [e['pos'] for e in hl_entries])
    # 标题 = 主标题 span + 副题 span
    main_span, sub_span = hl_text_marked, ''
    sub_en = meta.get('headline_sub_en', '')
    if sub_en and sub_en in hl_text_marked:
        i = hl_text_marked.index(sub_en)
        main_span = hl_text_marked[:i].strip()
        sub_span = hl_text_marked[i:].strip()
    en_html = f'<span>{main_span}</span>'
    if sub_span:
        en_html += f'<span class="headline-sub">{sub_span}</span>'

    def note(n):
        return {'w': n['w'], 'ipa': n['ipa'], 'pos': n['pos'], 'en': n['en'],
                'zh': n['zh'], 'ctx': '', 'ex1': n['ex1'], 'ex2': n['ex2']}

    headline = {'en_html': en_html, 'zh': meta.get('headline_zh', r['zh_title_sub']),
                'notes': [note(e['entry']) for e in hl_entries]}

    paras = []
    for pi, (key, text, bucket) in enumerate(sections[1:], 1):
        es = sorted(bucket, key=lambda x: x['pos'][0])
        marked = mark_text(text, [e['pos'] for e in es])
        src = body_paras[pi - 1]
        paras.append({'en_html': f'<span>{marked}</span>', 'zh': src['zh'],
                      'notes': [note(e['entry']) for e in es]})

    practice = {}
    if r.get('practice_items'):
        practice = {
            'intro': meta.get('practice_intro', '请将以下中文句子翻译为英文（参考答案见后）。'),
            'items': r['practice_items'],
            'critical_en': '', 'critical_zh': '',
            'answer': '<br>'.join(f'{i+1}. {t}' for i, t in enumerate(r.get('answers', []))),
        }

    c = {
        'date': meta.get('date', '2026-11-09'),
        'title_tag': meta.get('title_tag', ''),
        'h1': meta.get('h1', ''),
        'source_label': meta.get('source_label', ''),
        'category': meta.get('category', ''),
        'read_minutes': meta.get('read_minutes', 15),
        'nav_hint': meta.get('nav_hint', ''),
        'headline': headline,
        'paragraphs': paras,
        'proper': r['proper'],
        'sources_note': meta.get('sources_note', ''),
        'practice': practice,
        'mindmap': {'svg': '', 'img': '', 'alt': '', 'aria': ''},
        'audio': meta.get('audio', True),
        'audio_dir': meta.get('audio_dir', ''),
        'tail_image': meta.get('tail_image', ''),
    }
    json.dump(c, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    n_notes = len(hl_entries) + sum(len(p['notes']) for p in paras)
    print(f'段落 {len(paras)}，词卡定位 {n_notes}/{len(all_entries)}')
    if unmatched:
        print('未定位词条：', unmatched)
    for key, text, bucket in sections:
        if bucket:
            ws = [e['entry']['w'] for e in sorted(bucket, key=lambda x: x['pos'][0])]
            print(f'  {key}: {ws}')


if __name__ == '__main__':
    main()
