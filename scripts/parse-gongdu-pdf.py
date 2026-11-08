#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共读 PDF 解析器（【共读】课件格式，2026-11-09 首次出现）。

版式（35 页典型）：
  p1     英文主标题 + 中文副标题 + 课程中文标题（页脚每页重复）
  p3     英文副标题 + 中文副标题
  p4..   正文段：`N.英文...` 开头，英段 → 中译 → 若干词条
         词条首行：`word pos. /ipa/ (附注)` 或 `word phrase`（无音标）
         释义行：英文释义 + 中文释义（同行）
         例句：以 `• ` 开头，每条英文 + 中文（跨行折行）
  p29    文末自带中文图片（原样呈现，不翻译）
  p30    翻译作业（中文 6 句）
  p31    翻译作业答案（英文 6 句）
  p32..  背景知识（编号条目，等价于「专有名词」区）

用法：
  python3 scripts/parse-gongdu-pdf.py <共读.pdf> <输出.json> [--image 输出图片路径]
"""
import json, re, sys, os

CJK = re.compile(r'[\u4e00-\u9fff]')
PAGE_NO = re.compile(r'^\d{1,2}$')
HEADER = re.compile(r'^早安英文\s*MORNING ENGLISH\s*\d+')
PARA_START = re.compile(r'^(\d{1,2})\.(?=[A-Z“\'"])')
PRACTICE_INTRO = re.compile(r'翻译作业')
ANSWER_INTRO = re.compile(r'翻译作业答案')
BG_INTRO = re.compile(r'背景知识')
BULLET = re.compile(r'^[•·]\s*')

POS_TOKENS = ('phrasal verb', 'n. phrase', 'v. phrase', 'adj. phrase',
              'adv. phrase', 'phrase', 'n.', 'v.', 'adj.', 'adv.', 'prep.',
              'conj.', 'pron.', 'num.', 'interj.')


def is_cjk_line(t):
    return bool(CJK.search(t))


def split_en_zh(s):
    """在第一个 CJK 字符处切成 (英文, 中文)。"""
    m = CJK.search(s)
    if not m:
        return s.strip(), ''
    return s[:m.start()].strip(), s[m.start():].strip()


def merge_lines(lines):
    """CJK 折行合并：中文行间不补空格，英文行间补一个空格。"""
    out = ''
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
            continue
        if CJK.search(out[-1:]) or CJK.search(ln[:1]):
            out += ln
        else:
            out += ' ' + ln
    return out


def extract_lines(doc, course_title):
    """逐页取行，剥掉页码/页眉/课程标题页脚，返回 [(page_no, line)]。"""
    cleaned = []
    for pno, page in enumerate(doc, 1):
        for raw in page.get_text('text', sort=True).split('\n'):
            t = raw.strip()
            if not t or PAGE_NO.match(t) or HEADER.match(t):
                continue
            # 页脚 / 页眉里的课程标题（可能折成两行）
            if course_title[0] in t or (course_title[1] and course_title[1] in t):
                continue
            cleaned.append((pno, t))
    return cleaned


def looks_like_vocab_header(t):
    """词条首行：短行、含词性标记。"""
    if BULLET.match(t) or PARA_START.match(t):
        return False
    if len(t) > 60:
        return False
    low = ' ' + t.lower() + ' '
    for tok in POS_TOKENS:
        # "fail v. /feɪl/" → ' v. '；"hear a call phrase" → ' phrase '
        if f' {tok} ' in low or low.endswith(f' {tok} '):
            return True
    return False


def parse_vocab_header(t):
    """拆出 (word, pos, ipa, extra)。"""
    pos_alt = '|'.join(re.escape(p) for p in POS_TOKENS)
    m = re.match(r'^(.+?)\s+(' + pos_alt + r')(?:\s*(\([^)]*\)))?\s*(/.*)?$', t)
    if not m:
        return None
    word = m.group(1).strip()
    pos = m.group(2).strip()
    extra = (m.group(3) or '').strip()
    ipa = (m.group(4) or '').strip()
    if extra:
        # "(常用复数 confines)" / "(BrE)"
        if ipa:
            ipa = ipa + ' ' + extra
        else:
            pos = pos + ' ' + extra
    return word, pos, ipa


def main():
    import pymupdf
    ap = sys.argv
    if len(ap) < 3:
        print(__doc__)
        sys.exit(1)
    pdf, out_json = ap[1], ap[2]
    img_out = None
    if '--image' in ap:
        img_out = ap[ap.index('--image') + 1]

    doc = pymupdf.open(pdf)

    # 课程中文标题：取第 1 页最长的 CJK 行
    p1 = [l.strip() for l in doc[0].get_text('text').split('\n') if l.strip()]
    cjk_lines = [l for l in p1 if is_cjk_line(l)]
    zh_title_sub = cjk_lines[0] if cjk_lines else ''      # 为何传统职业建议在Z世代面前失灵
    course_full = max(cjk_lines, key=len) if cjk_lines else ''
    # 课程标题可能被折成两行：找最长行之后，看是否有后续行是它的延续
    idx = cjk_lines.index(course_full)
    second = cjk_lines[idx + 1] if idx + 1 < len(cjk_lines) else ''
    course_title = (course_full, second if len(second) < 20 else '')

    en_lines = [l for l in p1 if not is_cjk_line(l)]
    en_title = ' '.join(en_lines[:2]).strip()

    # 中文副题：课程标题行之前的 CJK 行合并（p1 上标题常折两行）
    zh_parts = []
    for l in cjk_lines:
        if '做你喜欢的事情' in l or course_full[:8] in l or '早安英文' in l:
            break
        zh_parts.append(l)
    zh_title_sub = merge_lines(zh_parts)

    lines = extract_lines(doc, course_title)

    paras = []          # [{no, en_lines, zh_lines, vocab}]
    practice_items, answers = [], []
    proper = []
    mode = 'body'       # body / practice / answer / background
    cur = None          # 当前段或当前词条
    cur_bg = None

    for pno, t in lines:
        if BG_INTRO.search(t) and '2026' in t:
            mode = 'background'
            continue
        if ANSWER_INTRO.search(t):
            mode = 'answer'
            continue
        if PRACTICE_INTRO.search(t) and '答案' not in t:
            mode = 'practice'
            continue
        m = re.match(r'^(\d{1,2})\.\s+(.*)$', t)
        if mode in ('practice', 'answer') and m:
            (answers if mode == 'answer' else practice_items).append(m.group(2).strip())
            continue
        if mode == 'background':
            m2 = re.match(r'^(\d{1,2})\.\s*(.+)$', t)
            if m2:
                if cur_bg:
                    proper.append(cur_bg)
                cur_bg = {'name': m2.group(2).strip(), 'def_lines': []}
            elif cur_bg is not None:
                cur_bg['def_lines'].append(t)
            continue
        # ---- 正文区 ----
        mp = PARA_START.match(t)
        if mp:
            cur = {'no': int(mp.group(1)), 'en_lines': [t[mp.end():].strip()],
                   'zh_lines': [], 'vocab': [], 'page': pno}
            paras.append(cur)
            continue
        if cur is None:
            # 正文前的独立词条页（如 p2 的 fail）：归入 no=0 的伪段（对应标题注释）
            if looks_like_vocab_header(t):
                h = parse_vocab_header(t)
                if h:
                    cur = {'no': 0, 'en_lines': [], 'zh_lines': [], 'page': pno,
                           'vocab': [{'w': h[0], 'pos': h[1], 'ipa': h[2],
                                      'def_lines': [], 'ex_lines': []}]}
                    paras.append(cur)
            continue
        if looks_like_vocab_header(t):
            h = parse_vocab_header(t)
            if h:
                cur['vocab'].append({'w': h[0], 'pos': h[1], 'ipa': h[2],
                                     'def_lines': [], 'ex_lines': []})
            continue
        v = cur['vocab'][-1] if cur['vocab'] else None
        if v is not None:
            if BULLET.match(t):
                v['ex_lines'].append([BULLET.sub('', t)])
                continue
            if not v['def_lines'] and not v['ex_lines']:
                # 词条首行后的第一行：英文释义（可能已带中文）
                v['def_lines'].append(t)
                continue
            if v['ex_lines']:
                # 例句折行续行（英文或中文都可能）
                v['ex_lines'][-1].append(t)
                continue
            # 释义折行续行
            v['def_lines'].append(t)
            continue
        if is_cjk_line(t):
            cur['zh_lines'].append(t)
            continue
        cur['en_lines'].append(t)

    if cur_bg:
        proper.append(cur_bg)

    # ---- 结构化 ----
    out_paras = []
    for p in paras:
        en = merge_lines(p['en_lines'])
        # 行尾连字符：保留连字符、去掉折行空格（cyber-\nsecurity → cyber-security）
        en = re.sub(r'(\w)-\s+(?=[a-z])', r'\1-', en)
        zh = merge_lines(p['zh_lines'])
        vocab = []
        for v in p['vocab']:
            d_en, d_zh = split_en_zh(merge_lines(v['def_lines']))
            exs = []
            for ex in v['ex_lines']:
                e, z = split_en_zh(merge_lines(ex))
                exs.append((e + ' ' + z).strip())
            vocab.append({'w': v['w'], 'pos': v['pos'], 'ipa': v['ipa'],
                          'en': d_en, 'zh': d_zh,
                          'ex1': exs[0] if len(exs) > 0 else '',
                          'ex2': exs[1] if len(exs) > 1 else ''})
        out_paras.append({'no': p['no'], 'en': en, 'zh': zh, 'vocab': vocab,
                          'page': p['page']})

    proper_out = [{'name': b['name'], 'def': merge_lines(b['def_lines'])} for b in proper]

    result = {
        'en_title': en_title, 'zh_title_sub': zh_title_sub,
        'course_title': course_full + (course_title[1] or ''),
        'paragraphs': out_paras, 'proper': proper_out,
        'practice_items': practice_items, 'answers': answers,
    }
    json.dump(result, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if img_out:
        pg = doc[len(doc) - 6]  # 倒数第 6 页附近找纯图页
        best = None
        for page in doc:
            txt = page.get_text().strip()
            imgs = page.get_images(full=True)
            if len(txt) < 60 and len(imgs) == 1:
                info = doc.extract_image(imgs[0][0])
                best = info
                break
        if best:
            open(img_out, 'wb').write(best['image'])
            print(f'文末图片：{img_out} ({best["width"]}x{best["height"]} {best["ext"]})')
        else:
            print('未找到文末纯图页')

    print(f'段落数 {len(out_paras)}，词条 {sum(len(p["vocab"]) for p in out_paras)}，'
          f'背景 {len(proper_out)}，作业 {len(practice_items)}/{len(answers)}')
    print(f'英文标题: {en_title}')
    print(f'中文副题: {zh_title_sub}')
    print(f'课程标题: {course_full}{" / " + course_title[1] if course_title[1] else ""}')


if __name__ == '__main__':
    main()
