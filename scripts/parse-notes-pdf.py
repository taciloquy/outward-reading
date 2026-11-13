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


RADICAL_MAP = {
    # U+2E80–U+2EFF 这一段没有 NFKC 映射，必须手写（pymupdf 抽简体字时常见）
    '\u2ea0': '民', '\u2ed3': '长', '\u2ecb': '车', '\u2edb': '风', '\u2ee2': '马',
    '\u2ed4': '门', '\u2edd': '食', '\u2edc': '飞', '\u2ec6': '角', '\u2eee': '齿',
    '\u2ebf': '言', '\u2ea2': '月', '\u2eb9': '高', '\u2ec2': '页',
    '\u2ec4': '西', '\u2ec5': '见', '\u2ee9': '黄',
    '\u2ef0': '龙', '\u2ee4': '鬼', '\u2eec': '齐', '\u2ed8': '青',
}

# 练习区起头语随课件版式变化（旧版「请将以下中文句子」，新版「请根据今天学习的文章」）。
# 默认多候选自动识别；--practice-mark 传参时只用指定值。
DEFAULT_PRACTICE_STARTS = (
    '请将以下中文句子',
    '请根据今天学习的文章',
    '请根据今天所学',
    '根据今天学习的文章',
    '根据今天所学',
)
PRACTICE_STARTS = DEFAULT_PRACTICE_STARTS


def is_practice_start(t: str) -> bool:
    return any(t.startswith(m) for m in PRACTICE_STARTS)


def fix_radicals(t: str) -> str:
    """康熙部首 / CJK 部首码位（U+2E80–U+2FDF）→ 常用汉字。"""
    out = []
    for ch in t:
        o = ord(ch)
        if ch in RADICAL_MAP:
            out.append(RADICAL_MAP[ch])
        elif 0x2E80 <= o <= 0x2FDF:
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
            # 单词级小写串（something/value 这类跨卡片折行续尾）不可能是页眉页脚，
            # 却会因为出现 ≥3 次被误判——一律豁免。
            if s and not re.fullmatch(r'[a-z]+', s):
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


# ---------- 新版式（62 页起：无【】标记，专名条目插在段落之间） ----------
# 词卡头形如 `blame sb/sth for sth phr. /bleɪm/`、`a blow to sth n. phr. /ə bləʊ tuː/`
CARD_HEAD = re.compile(
    r'^(?P<w>.+?)\s+(?P<pos>(?:n\.\s*phr\.|phr\.v\.|phr|n|v|adj|adv|prep|phrase)\.?)\s*'
    r'(?P<ipa>/[^/]+/)?$')
# 又一版式（2026-11-10 起）：词卡头没有词性标记，形如 `investigation /ɪnˌvestɪˈɡeɪʃən/`
CARD_HEAD_NOP = re.compile(r'^(?P<w>[A-Za-z][^/]{0,70}?)\s+(/[^/]+/)$')
CARD_FIELD_RE = re.compile(r'^(英文释义|中文释义|文中含义|文中意|例句一|例句二)：')
# 分隔符兼容两种版式：「N. 英文名 / 中文名」（20261112 起）与
# 「N. 英文名 — 中文名」（20261113 起，em-dash / en-dash）
PROPER_LINE = re.compile(
    r'^(\d{1,2})\.\s+([A-Z][^/—–]{1,60}?)\s*[/—–]\s*(.*[\u4e00-\u9fff].*)$')
PARA_HEAD = re.compile(r'^(\d{1,2})\.(?=\S)\s*(.+)$')
CARD_FIELDS = [('英文释义', 'en'), ('中文释义', 'zh'), ('文中意', 'ctx'),
               ('例句一', 'ex1'), ('例句二', 'ex2')]


def _card_body(lines):
    """`· 英文释义：…` 之类的行 → 卡片字段；不带标记的续行并回上一字段。"""
    out = {'en': '', 'zh': '', 'ctx': '', 'ex1': '', 'ex2': ''}
    field = None
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        body = s.lstrip('·•').strip()
        # 「文中含义：」与旧版「文中意：」是同一字段，先归一
        body = re.sub(r'^文中含义：', '文中意：', body)
        hit = next((k for k, _ in CARD_FIELDS if body.startswith(k + '：')), None)
        if hit:
            field = dict(CARD_FIELDS)[hit]
            out[field] = body[len(hit) + 1:].strip()
            continue
        if field:
            out[field] += ' ' + body
    return out


def detect_lede(clean, para_end, is_head):
    """识别编号段之前的无编号导语块（英文长句 + 其译文），返回 {'n':0,...} 或 None。

    部分期次在标题之后、编号段之前另置一块导语（如 20261112）。它是正文第 1 段，
    漏掉会让段号整体前移、与预习版和导图 range 错位。判据：标题块之后最后一个
    英文块以句号收尾且不少于 8 词，其后紧跟中文块即为它的译文。
    """
    lead_lines, k = [], 0
    while k < para_end:
        s = clean[k].strip()
        if not s or s == '@@PAGE@@':
            k += 1
            continue
        if is_head(s):
            break
        lead_lines.append(s)
        k += 1
    blocks = []
    for line in lead_lines:
        is_cjk = bool(CJK.search(line))
        if blocks and blocks[-1][0] == is_cjk:
            blocks[-1][1].append(line)
        else:
            blocks.append((is_cjk, [line]))
    if len(blocks) < 3:
        return None

    def ok(t):
        return t.rstrip().endswith(('.', '.”', '."')) and len(t.split()) >= 8

    if not blocks[-1][0] and ok(' '.join(blocks[-1][1])):
        en, zh = ' '.join(blocks[-1][1]), ''
        head = ' '.join(' '.join(b[1]) for b in blocks[:-1])
    elif not blocks[-2][0] and blocks[-1][0] and ok(' '.join(blocks[-2][1])):
        en = ' '.join(blocks[-2][1])
        zh = re.sub(r'\s+', '', ''.join(blocks[-1][1]))
        head = ' '.join(' '.join(b[1]) for b in blocks[:-2])
    else:
        return None
    en = re.sub(r'([A-Za-z])-\s+([a-z])', r'\1-\2', en)
    return {'n': 0, 'en': fix_radicals(re.sub(r'\s+', ' ', en).strip()), 'zh': zh,
            'head': re.sub(r'\s+', ' ', head).strip()}


def split_lead_cards(cards, head_text):
    """导语出现前的词卡分流：词在标题里出现的留在 headline，其余归导语段（¶1）。

    版面上一整页的词卡都排在编号段之前，但其中一部分注释的是标题
    （valuation / blockbuster / IPO），另一部分注释的是导语句
    （PBC / fully diluted valuation / in a bid to），必须按实际词形归位。
    """
    head, body = [], []
    for c in cards:
        base = c['w'].split(' / ')[0]
        pat = r'\s+'.join(re.escape(t) for t in base.split())
        (head if re.search(pat, head_text or '', re.I) else body).append(c)
    return head, body


def run_new_edition(clean, practice_mark):
    """新版式解析：卡片靠「词 + 词性 + 音标」识别，专名靠「编号. 英文名 / 中文名」。"""
    para_end = next((j for j, l in enumerate(clean)
                     if is_practice_start(l.strip())), len(clean))

    def stops(i):
        """该行是否意味着「上一块内容到此为止」。"""
        s = clean[i].strip()
        return (s == '@@PAGE@@' or not s or PROPER_LINE.match(s)
                or (CARD_HEAD.match(s) and '/' in s and s.count('/') >= 2)
                or CARD_HEAD_NOP.match(s)
                or (PARA_HEAD.match(s) and not CJK.search(s[:24])
                    and not s.startswith('（')))

    lede = detect_lede(clean, para_end, lambda s: bool(
        PROPER_LINE.match(s) or (CARD_HEAD.match(s) and s.count('/') >= 2)
        or CARD_HEAD_NOP.match(s) or PARA_HEAD.match(s)))

    paras, pool, proper = [], {'headline': [], 'p0': []}, []
    lede_head = ''
    if lede:
        lede_head = lede.pop('head', '')
        paras.append(lede)
    cur = 'headline'
    i = 0
    while i < para_end:
        l = clean[i].strip()
        if l == '@@PAGE@@' or not l:
            i += 1
            continue
        mp = PROPER_LINE.match(l)
        if mp:
            proper.append({'name': f'{mp.group(2).strip()} / {mp.group(3).strip()}', 'def': ''})
            i += 1
            # 说明文字 = 后续普通行，直到下一个专名/段落/卡片
            buf = []
            while i < para_end:
                s = clean[i].strip()
                if s == '@@PAGE@@':
                    i += 1
                    continue
                if (not s or PROPER_LINE.match(s) or PARA_HEAD.match(s)
                        or (CARD_HEAD.match(s) and s.count('/') >= 2)):
                    break
                buf.append(s)
                i += 1
            # 说明尾部常混入检索引用（如「Al Jazeera +1」「GOV.UK」，与中文同行），
            # 统一在句号后把纯英文尾巴剥掉；说明正文全中文，句号后不应再接英文。
            dfn = ' '.join(buf)
            dfn = re.sub(r'(?<=[。！？；])\s*[A-Za-z][A-Za-z .+&\'-]*?(?:\+\s*\d+)?\s*$',
                         '', dfn).strip()
            proper[-1]['def'] = dfn
            cur = 'proper'
            continue
        mc = CARD_HEAD.match(l)
        nop = CARD_HEAD_NOP.match(l)
        if nop and not CJK.search(nop.group('w')):
            # 防误伤：无词性词卡头的下一行必须是字段行（英文释义/中文释义/文中含义）
            j = i + 1
            nxt = ''
            while j < min(i + 4, len(clean)):
                s2 = clean[j].strip()
                if s2 and s2 != '@@PAGE@@':
                    nxt = s2
                    break
                j += 1
            if not CARD_FIELD_RE.match(nxt):
                nop = None
        if (mc and mc.group('ipa')) or nop:
            buf = []
            i += 1
            while i < para_end:
                if stops(i):
                    # 折页后正文续行也算停止，交给外层处理
                    if clean[i].strip() == '@@PAGE@@':
                        j = i + 1
                        while j < para_end and (clean[j].strip() == '@@PAGE@@'
                                                or not clean[j].strip()):
                            j += 1
                        if j < para_end and not stops(j):
                            i = j
                            continue
                    break
                buf.append(clean[i])
                i += 1
            if mc and mc.group('ipa'):
                card = {'w': mc.group('w').strip(), 'ipa': mc.group('ipa'),
                        'pos': mc.group('pos')}
            else:
                card = {'w': nop.group('w').strip(), 'ipa': nop.group(2), 'pos': ''}
            card.update(_card_body(buf))
            pool.setdefault(cur, []).append(card)
            continue
        mpar = PARA_HEAD.match(l)
        if mpar and not CJK.search(mpar.group(2)[:24]):
            n = int(mpar.group(1))
            cur = 'p%d' % n
            pool.setdefault(cur, [])
            en = [mpar.group(2)]
            i += 1
            while i < para_end:
                s = clean[i].strip()
                if s == '@@PAGE@@':
                    j = i + 1
                    while j < para_end and (clean[j].strip() == '@@PAGE@@'
                                            or not clean[j].strip()):
                        j += 1
                    nxt = clean[j].strip() if j < para_end else ''
                    if nxt and not CJK.search(nxt[:12]) and not CARD_HEAD.match(nxt):
                        i = j
                        continue
                    break
                if not s:
                    i += 1
                    continue
                if CJK.search(s) or (CARD_HEAD.match(s) and s.count('/') >= 2) \
                        or CARD_HEAD_NOP.match(s):
                    break
                en.append(s)
                i += 1
            en_txt = ' '.join(en)
            en_txt = re.sub(r'([A-Za-z])-\s+([a-z])', r'\1-\2', en_txt)
            en_txt = re.sub(r'\s+', ' ', en_txt).strip()
            zh = []
            while i < para_end:
                s = clean[i].strip()
                if s == '@@PAGE@@':
                    j = i + 1
                    while j < para_end and (clean[j].strip() == '@@PAGE@@'
                                            or not clean[j].strip()):
                        j += 1
                    nxt = re.sub(r'^\d+\.\s*', '', clean[j].strip()) if j < para_end else ''
                    if nxt and CJK.search(nxt[:6]):
                        clean[j] = nxt
                        i = j
                        continue
                    break
                if not s:
                    i += 1
                    continue
                if (CARD_HEAD.match(s) and s.count('/') >= 2) \
                        or CARD_HEAD_NOP.match(s) or PROPER_LINE.match(s):
                    break
                zh.append(s)
                i += 1
            paras.append({'n': n, 'en': fix_radicals(en_txt),
                          'zh': re.sub(r'\s+', '', ''.join(zh))})
            continue
        i += 1

    # ---------- 练习 / 思考题 / 答案 ----------
    practice, answers = [], []
    mode, seg = 'q', {'a': [], 'a2': []}
    for l in clean[para_end:]:
        t = fix_radicals(l.strip())
        if not t or t == '@@PAGE@@' or re.fullmatch(r'[\d：:，。]+', t):
            continue
        if is_practice_start(t):
            mode = 'q'
            continue
        if t.startswith('思考题参考答案'):
            mode = 'a2'
            continue
        if t == '思考题' or t.startswith('思考题（') or t.startswith('思考题('):
            mode = 'critical'
            continue
        if t.startswith('参考答案'):
            mode = 'a'
            continue
        if mode == 'q':
            m = re.match(r'^\d+\.\s*(.+)$', t)
            if m:
                practice.append(m.group(1).strip())
            elif practice:
                # 复述型练习的「关键词：a / b / c」提示行 → 括号提示词，
                # 与旧版题干末尾的「（a / b / c）」保持同一版式。
                prev = practice[-1]
                if t.startswith('关键词：'):
                    practice[-1] = prev + '（' + t[len('关键词：'):].strip() + '）'
                    continue
                # 题干折行直接拼回（中文之间不加空格）；编号标题行短且无末标点，
                # 其后第一行是题干正文，补一个句号隔开；正文折行行长满，直接拼。
                is_head = len(prev) <= 20 and prev[-1] not in '。，；、！？：））》”…'
                sep = '。' if is_head else ''
                practice[-1] = prev + sep + t
        elif mode in ('a', 'a2'):
            seg[mode].append(t)
    for key in ('a', 'a2'):
        lines = seg[key]
        if not lines:
            continue
        cut = next((k for k, s in enumerate(lines) if CJK.search(s[:6])), len(lines))
        en = ' '.join(lines[:cut]).strip()
        zh = ''.join(lines[cut:]).strip()
        answers.append(f'{en}<br>参考译文：{zh}' if zh else en)
    if lede_head:
        pool['headline'], pool['p0'] = split_lead_cards(pool.get('headline', []), lede_head)
    return {'paragraphs': paras,
            'headline_cards': pool.get('headline', []),
            'para_cards': {p['n']: pool.get('p%d' % p['n'], []) for p in paras},
            'proper': proper,
            'practice': practice,
            'answers': answers}


def run(pdf, proper_mark, practice_mark, drop):
    pages = extract(pdf, dump=None)
    clean = flatten(pages, proper_mark, practice_mark, drop)

    if '@@PROPER@@' not in clean:
        return run_new_edition(clean, practice_mark)
    para_end = next((j for j, l in enumerate(clean)
                     if is_practice_start(l.strip())), len(clean))
    proper_idx = clean.index('@@PROPER@@')

    paras, pool = [], {'headline': []}
    lede = detect_lede(clean, para_end, lambda s: bool(
        s == '@@PROPER@@' or s.startswith('【') or re.match(r'^(\d+)\.(\s|$)', s)))
    cur = 'headline'
    i = 0
    while i < para_end:
        l = clean[i]
        m = re.match(r'^(\d+)\.\s+(.+)$', l)
        mn = re.match(r'^(\d+)\.$', l)          # 编号单独占一行（PDF 折行）
        if mn and not m:
            j = i + 1
            while j < para_end and (clean[j] == '@@PAGE@@' or not clean[j].strip()):
                j += 1
            if j < para_end and not CJK.search(clean[j][:2]):
                l = f'{mn.group(1)}. ' + clean[j].strip()
                clean[i] = l
                clean[j] = ''                   # 已并入，勿重复计入
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
            # 译文可能与英文原文分属两页：允许跨页续收，但下一页必须以中文起首。
            zh = []
            while i < para_end:
                if clean[i] == '@@PAGE@@':
                    j = i + 1
                    while j < para_end and (clean[j] == '@@PAGE@@' or not clean[j].strip()):
                        j += 1
                    nxt = clean[j].strip() if j < para_end else ''
                    probe = re.sub(r'^\d+\.\s*', '', nxt)   # 折页后译文可能重复段落编号
                    if (probe and not nxt.startswith('【') and CJK.search(probe[:6])):
                        clean[j] = probe
                        i = j
                        continue
                    break
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

    if lede:
        lede_head = lede.pop('head', '')
        paras.insert(0, lede)
        pool.setdefault('p0', [])
        pool['headline'], pool['p0'] = split_lead_cards(pool.get('headline', []), lede_head)

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
        if not t or t == '@@PAGE@@' or re.fullmatch(r'\d+', t) or is_practice_start(t):
            continue
        if t == '参考答案' or t.startswith('参考答案'):
            mode = 'a'
            continue
        bucket = practice if mode == 'q' else answers
        mb = re.match(r'^[•·]\s*(.+)$', t)      # 答案常用「•」列条目
        if mb and mode == 'a':
            bucket.append(mb.group(1).strip())
            continue
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
    ap.add_argument('--practice-mark', default=None,
                    help='练习区起头文字（不传则自动识别多种课件版式）')
    ap.add_argument('--drop', action='append', default=[], help='额外丢弃的行正则，可多次')
    a = ap.parse_args()

    global PRACTICE_STARTS
    PRACTICE_STARTS = (a.practice_mark,) if a.practice_mark else DEFAULT_PRACTICE_STARTS
    pages = extract(a.pdf, dump=a.dump_text)
    data = run(a.pdf, a.proper_mark, a.practice_mark, a.drop)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    total = len(data['headline_cards']) + sum(len(v) for v in data['para_cards'].values())
    print(f'页数 {len(pages)}')
    print(f'段落 {len(data["paragraphs"])} | 词卡 {total}'
          f'（标题 {len(data["headline_cards"])} + 正文 {total - len(data["headline_cards"])}）')
    print(f'专名 {len(data["proper"])} | 练习 {len(data["practice"])} | 答案 {len(data["answers"])}')
    # 第 0 段是无编号导语，本来就不带词卡，不算异常。
    empty = [n for n, v in data['para_cards'].items() if not v and n != 0]
    if empty:
        print(f'⚠ 这些段落没有词卡：{empty}')
    print(f'→ {a.out}')


if __name__ == '__main__':
    main()
