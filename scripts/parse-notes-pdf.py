#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课件 PDF → 结构化 JSON（段落/词卡/专名/练习），供 make-content-json.py 使用。

用法：
    python3 scripts/parse-notes-pdf.py "/path/to/20261102【完整笔记】xxx.pdf" \
        --out /tmp/2026-11-02-parsed.json [--dump-text /tmp/1102.txt]

设计原则：
- 不写死文章标题/期号：页眉页脚靠「多页重复行」自动识别，纯数字行丢弃。
- 段落靠 `1. ` 起首 + 首个词非中文 判断；词卡靠 `【词】 /音标/ 词性` 判断。
- 专名区以 `【背景信息` 起头，练习区以 `请将以下中文句子` 起头（可用参数改）。
- pymupdf 偶发把常用字抽成康熙部首码位（⻓/⺠ 等），逐字符 NFKC 修正。

输出结构：
{ paragraphs:[{n,en,zh}], headline_cards:[card], para_cards:{"1":[card]},
  proper:[{name,def}], practice:[str], answers:[str] }
card = {w, ipa, pos, en, zh, ctx, ex1, ex2}
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

CJK = re.compile(r'[\u4e00-\u9fff]')


def fix_radicals(t: str) -> str:
    """康熙部首码位（U+2E80–U+2FDF）→ 常用汉字。"""
    out = []
    for ch in t:
        o = ord(ch)
        if 0x2E80 <= o <= 0x2FDF:
            n = unicodedata.normalize('NFKC', ch)
            out.append(n if len(n) == 1 and '\u4e00' <= n <= '\u9fff' else ch)
        else:
            out.append(ch)
    return ''.join(out)


def extract(pdf, dump=None):
    import pymupdf
    doc = pymupdf.open(pdf)
    pages = [pg.get_text() for pg in doc]
    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            for i, t in enumerate(pages, 1):
                f.write(f'\n===== PAGE {i} =====\n{t}')
    return pages


def boilerplate(pages):
    """全文重复 ≥3 次且短（≤40 字）的行 = 页眉/页脚。

    用「去掉所有空白」后的形式比对，才能抓住 `早安英文 Morning English 20261102`
    和 `早安英文Morning English20261102` 这类同一页脚的变体。
    """
    cnt = Counter()
    for t in pages:
        for line in t.split('\n'):
            s = re.sub(r'\s+', '', line)
            if s:
                cnt[s] += 1
    return {s for s, c in cnt.items() if c >= 3 and len(s) <= 40}


def flatten(pages, proper_mark, practice_mark, drop=()):
    """逐行整理成线性列表，插入 @@PAGE@@ / @@PROPER@@ 标记。"""
    boiler = boilerplate(pages)
    drop_re = [re.compile(p) for p in drop]
    out = []
    for t in pages:
        for raw in t.split('\n'):
            s = raw.strip()
            if not s:
                out.append('')
                continue
            if s in boiler or re.fullmatch(r'\d{1,3}', s):
                continue
            if re.sub(r'\s+', '', s) in boiler:
                continue
            if any(r.search(s) for r in drop_re):
                continue
            if s.startswith(proper_mark):
                out.append('@@PROPER@@')
                continue
            out.append(fix_radicals(raw.rstrip()))
        out.append('@@PAGE@@')          # 每页末尾插一个页标记
    return out


def parse_card_text(c):
    body = re.sub(r'\s+', ' ', c['body']).strip()
    en = ''
    m = re.search(r'英文释义：(.*?)(?=本义为|核心搭配：|$)', body)
    if m:
        en = m.group(1).strip()
    zh, ctx = '', ''
    m = re.search(r'本义为(.*?)(?=核心搭配：|$)', body)
    if m:
        seg = m.group(1).strip()
        mc = re.search(r'（本文特指：(.*?)）\s*$', seg)
        if mc:
            ctx = mc.group(1).strip()
            zh = seg[:mc.start()].strip()
        else:
            zh = seg
        zh = zh.rstrip('，。 ')
    exs = [x.strip() for x in re.findall(r'・(.*?)(?=・|$)', body) if x.strip()]
    return {'w': c['w'], 'ipa': c['ipa'], 'pos': c['pos'], 'en': en,
            'zh': zh, 'ctx': ctx,
            'ex1': exs[0] if exs else '', 'ex2': exs[1] if len(exs) > 1 else ''}


def run(pdf, proper_mark, practice_mark, drop):
    pages = extract(pdf, dump=None)
    clean = flatten(pages, proper_mark, practice_mark, drop)

    if '@@PROPER@@' not in clean:
        sys.exit('✗ 找不到专名区标记（默认「【背景信息」），用 --proper-mark 指定')
    para_end = next((j for j, l in enumerate(clean)
                     if l.strip().startswith(practice_mark)), len(clean))
    proper_idx = clean.index('@@PROPER@@')

    paras, pool = [], {'headline': []}
    cur = 'headline'
    i = 0
    while i < para_end:
        l = clean[i]
        m = re.match(r'^(\d+)\.\s+(.+)$', l)
        mcard = re.match(r'^【(.+?)】\s*(/[^/]+/)?\s*(.*)$', l)
        if l == '@@PAGE@@' or not l.strip():
            i += 1
            continue
        if m and not CJK.search(m.group(2)[:2]):
            cur = 'p' + m.group(1)
            pool.setdefault(cur, [])
            en = [m.group(2)]
            i += 1
            while i < para_end and clean[i] != '@@PAGE@@' and not CJK.search(clean[i]):
                en.append(clean[i].strip())
                i += 1
            zh = []
            while i < para_end and clean[i] != '@@PAGE@@':
                zh.append(clean[i].strip())
                i += 1
            en_txt = ' '.join(en)
            en_txt = re.sub(r'([A-Za-z])-\s+([a-z])', r'\1-\2', en_txt)  # 断行连字符
            en_txt = re.sub(r'\s+', ' ', en_txt).strip()
            paras.append({'n': int(m.group(1)), 'en': fix_radicals(en_txt),
                          'zh': re.sub(r'\s+', '', ''.join(zh))})
            continue
        if mcard:
            w, ipa, pos = mcard.group(1).strip(), (mcard.group(2) or '').strip(), mcard.group(3).strip()
            i += 1
            body = []
            while (i < para_end and clean[i] != '@@PAGE@@'
                   and not re.match(r'^【.+?】\s*/', clean[i])
                   and not re.match(r'^\d+\.\s+[A-Z“]', clean[i])):
                if clean[i].strip():
                    body.append(clean[i].strip())
                i += 1
            pool[cur].append({'w': w, 'ipa': ipa, 'pos': pos, 'body': ' '.join(body)})
            continue
        i += 1

    # 专名：名字行以括注结尾，或下一行是「简要介绍…」
    proper, seg, cur_p = [], clean[proper_idx + 1:para_end], None
    for idx, l in enumerate(seg):
        t = l.strip()
        if t == '@@PAGE@@' or not t:
            continue
        if t.startswith('简要介绍') or t.startswith('本文中的意思'):
            if cur_p:
                cur_p['def'] += t
            continue
        is_name = bool(re.match(r'^.{2,64}（[^）]+）$', t))
        if not is_name and idx + 1 < len(seg) and seg[idx + 1].strip().startswith('简要介绍'):
            is_name = True
        if is_name:
            cur_p = {'name': re.sub(r'（[^）]*）$', '', t).strip(), 'def': ''}
            proper.append(cur_p)
            continue
        if cur_p:
            cur_p['def'] += t

    # 练习 + 答案
    # 题干与答案都会折行（中文一行约 35 字、英文约 75 字符），
    # 不带编号的续行必须并回上一条，否则会被整条丢掉。
    practice, answers, mode = [], [], 'q'
    for l in clean[para_end:]:
        t = l.strip()
        if not t or t == '@@PAGE@@' or re.fullmatch(r'\d+', t) or t.startswith(practice_mark[:5]):
            continue
        if t == '参考答案' or t.startswith('参考答案'):
            mode = 'a'
            continue
        bucket = practice if mode == 'q' else answers
        m = re.match(r'^\d+\.\s*(.+)$', t)
        if m:
            bucket.append(m.group(1).strip())
        elif bucket:
            prev = bucket[-1]
            # 中文之间不加空格，中英/英文之间补一个空格
            sep = '' if (prev and CJK.match(prev[-1]) and CJK.match(t[0])) else ' '
            bucket[-1] = prev + sep + t

    return {
        'paragraphs': paras,
        'headline_cards': [parse_card_text(c) for c in pool.get('headline', [])],
        'para_cards': {p['n']: [parse_card_text(c) for c in pool.get('p%d' % p['n'], [])]
                       for p in paras},
        'proper': proper,
        'practice': practice,
        'answers': answers,
    }


def main():
    ap = argparse.ArgumentParser(description='课件 PDF → 结构化 JSON')
    ap.add_argument('pdf')
    ap.add_argument('--out', required=True)
    ap.add_argument('--dump-text', help='把整份文本落到这个文件，便于排查')
    ap.add_argument('--proper-mark', default='【背景信息', help='专名区起头文字')
    ap.add_argument('--practice-mark', default='请将以下中文句子', help='练习区起头文字')
    ap.add_argument('--drop', action='append', default=[], help='额外丢弃的行正则，可多次')
    a = ap.parse_args()

    pages = extract(a.pdf, dump=a.dump_text)
    data = run(a.pdf, a.proper_mark, a.practice_mark, a.drop)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    total = len(data['headline_cards']) + sum(len(v) for v in data['para_cards'].values())
    print(f'页数 {len(pages)}')
    print(f'段落 {len(data["paragraphs"])} | 词卡 {total}'
          f'（标题 {len(data["headline_cards"])} + 正文 {total - len(data["headline_cards"])}）')
    print(f'专名 {len(data["proper"])} | 练习 {len(data["practice"])} | 答案 {len(data["answers"])}')
    empty = [n for n, v in data['para_cards'].items() if not v]
    if empty:
        print(f'⚠ 这些段落没有词卡：{empty}')
    print(f'→ {a.out}')


if __name__ == '__main__':
    main()
