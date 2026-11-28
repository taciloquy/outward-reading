#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外刊精读页 · 无人值守发布编排器（2026-11-21 之后的新期次，无思维导图）。

设计原则：
  1. 全部中间产物落在 /tmp 暂存区，只有全部硬校验通过才写回仓库；
  2. 任一异常（闸门、逐字核验、词卡定位、打印页数、DOM 结构、音频缺失）立即停止，
     写状态文件并退出非 0，绝不带着半成品上线；
  3. 默认 dry-run，只有显式 --apply 才写仓库、提交、推送；
  4. 使用文件锁，避免与手动运行或模型定时任务并发。

用法：
    python3 scripts/auto-publish.py                    # dry-run，只检查+暂存+核验
    python3 scripts/auto-publish.py --apply            # 正式发布
    python3 scripts/auto-publish.py --force-date 2026-11-28 --no-push   # 演练指定日期
"""
import argparse
import datetime as dt
import fcntl
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = Path.home() / ".workbuddy/skills/outward-reading-publish/scripts"
PDF_ROOT = Path("/Volumes/WORK DISK/QHY/03_学习与阅读/读书/1.早安英文")
LOG_DIR = Path.home() / ".workbuddy/logs"
LOCK_PATH = LOG_DIR / "auto-publish.lock"
LOG_PATH = LOG_DIR / "auto-publish.log"
STATUS_PATH = LOG_DIR / "auto-publish-last.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SOURCE_EN = {
    "经济学人": "The Economist", "卫报": "The Guardian", "彭博社": "Bloomberg",
    "华盛顿邮报": "The Washington Post", "纽约时报": "The New York Times",
    "CNN": "CNN", "QUARTZ": "Quartz", "金融时报": "The Financial Times",
}
UI_WORDS = ["朗读", "连播", "译文", "翻译练习", "生词", "导图", "返回日历", "下一篇"]

# 不规则动词/名词变形；用于把词卡自动定位到正文里的实际写法。
IRREGULAR = {
    "be": ["is", "are", "was", "were", "been", "being"],
    "take": ["took", "taken", "taking"], "make": ["made", "making"],
    "go": ["went", "gone", "going"], "come": ["came", "coming"],
    "see": ["saw", "seen", "seeing"], "fall": ["fell", "fallen", "falling"],
    "sweep": ["swept", "sweeping"], "face": ["faced", "facing"],
    "meet": ["met", "meeting"], "hold": ["held", "holding"],
    "bring": ["brought", "bringing"], "buy": ["bought", "buying"],
    "catch": ["caught", "catching"], "deal": ["dealt", "dealing"],
    "find": ["found", "finding"], "get": ["got", "gotten", "getting"],
    "give": ["gave", "given", "giving"], "grow": ["grew", "grown", "growing"],
    "keep": ["kept", "keeping"], "know": ["knew", "known", "knowing"],
    "lead": ["led", "leading"], "leave": ["left", "leaving"],
    "lose": ["lost", "losing"], "pay": ["paid", "paying"],
    "put": ["put", "putting"], "read": ["read", "reading"],
    "run": ["ran", "run", "running"], "say": ["said", "saying"],
    "send": ["sent", "sending"], "set": ["set", "setting"],
    "show": ["showed", "shown", "showing"], "sit": ["sat", "sitting"],
    "speak": ["spoke", "spoken", "speaking"], "stand": ["stood", "standing"],
    "teach": ["taught", "teaching"], "tell": ["told", "telling"],
    "think": ["thought", "thinking"], "throw": ["threw", "thrown", "throwing"],
    "write": ["wrote", "written", "writing"], "win": ["won", "winning"],
    "understand": ["understood", "understanding"], "become": ["became", "becoming"],
    "begin": ["began", "begun", "beginning"], "break": ["broke", "broken", "breaking"],
    "build": ["built", "building"], "choose": ["chose", "chosen", "choosing"],
    "cut": ["cut", "cutting"], "do": ["did", "done", "doing"],
    "eat": ["ate", "eaten", "eating"], "feel": ["felt", "feeling"],
    "fight": ["fought", "fighting"], "forget": ["forgot", "forgotten", "forgetting"],
    "hear": ["heard", "hearing"], "mean": ["meant", "meaning"],
    "ride": ["rode", "ridden", "riding"], "rise": ["rose", "risen", "rising"],
    "sing": ["sang", "sung", "singing"], "sleep": ["slept", "sleeping"],
    "spend": ["spent", "spending"], "steal": ["stole", "stolen", "stealing"],
    "stick": ["stuck", "sticking"], "swim": ["swam", "swum", "swimming"],
    "tear": ["tore", "torn", "tearing"], "wake": ["woke", "woken", "waking"],
    "wear": ["wore", "worn", "wearing"], "weave": ["wove", "woven", "weaving"],
}


class PublishError(RuntimeError):
    pass


def log(msg):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, cwd=ROOT, capture=True, check=True):
    r = subprocess.run([str(x) for x in cmd], cwd=str(cwd), capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise PublishError(f"命令失败（{r.returncode}）：{' '.join(str(x) for x in cmd)}\n"
                           f"STDOUT: {(r.stdout or '')[-2000:]}\nSTDERR: {(r.stderr or '')[-2000:]}")
    return r


def py(script, *args, cwd=ROOT, check=True):
    return run([sys.executable, str(script), *[str(a) for a in args]], cwd=cwd, check=check)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def join_en(lines):
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif out.endswith("-"):
            out += ln
        else:
            out += " " + ln
    return re.sub(r"\s+", " ", out).strip()


# ---------------- 源 PDF 判定与闸门 ----------------

def find_pdfs(date):
    folder = PDF_ROOT / (date[:4] + date[5:7])
    if not folder.exists():
        raise PublishError(f"源目录不存在或外接盘未挂载：{folder}")
    pre, notes = [], []
    for p in folder.glob(f"{date.replace('-', '')}*.pdf"):
        n = p.name
        if "预习" in n or "原文预习" in n:
            pre.append(p)
        elif "完整笔记" in n:
            notes.append(p)
    if len(pre) > 1 or len(notes) > 1:
        raise PublishError(f"{date} 同日同类 PDF 多于 1 份，需人工判定，脚本停止")
    return (pre[0] if pre else None), (notes[0] if notes else None)


def gate(kind, date):
    r = py(ROOT / "scripts/daily-check.py", "--gate", kind, "--date", date, check=False)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse_todo(text):
    todo = []
    seen = False
    for line in text.splitlines():
        if "需要动手" in line:
            seen = True
            continue
        if not seen:
            continue
        m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s+(\w+)", line)
        if m:
            todo.append((m.group(1), m.group(2)))
    return todo


def decide_type(date, notes_pdf, preview_pdf, forced=False):
    if forced:
        if notes_pdf:
            return "NOTES", "forced（指定日期）"
        if preview_pdf:
            return "PREVIEW", "forced（指定日期）"
        return "ERROR", "指定日期没有源 PDF"
    code, out = gate("notes", date)
    if code == 13 and not forced:
        return "SKIP", out
    if code == 13 and forced:
        code = 0  # 演练指定日期时忽略「已发布且 PDF 未更新」
    if code == 14 and not notes_pdf:
        return "ERROR", out
    code_pre, out_pre = gate("preview", date)
    if code_pre == 10 or notes_pdf:
        if code != 0:
            return "ERROR", out + out_pre
        return "NOTES", out + out_pre
    if code_pre == 0:
        return "PREVIEW", out + out_pre
    return "ERROR", out + out_pre


# ---------------- 词卡 mark 自动生成 ----------------

def token_variants(tok):
    vs = {tok}
    low = tok.lower()
    vs |= {v for v in IRREGULAR.get(low, [])}
    if low.endswith("e"):
        vs |= {low[:-1] + "ing", low + "d", low + "s"}
    elif low.endswith("y") and len(low) > 2:
        vs |= {low[:-1] + "ies", low[:-1] + "ied", low[:-1] + "ying", low + "s"}
    else:
        vs |= {low + "s", low + "es", low + "ed", low + "d", low + "ing"}
        if len(low) >= 3 and low[-1] not in "aeiou" and low[-2] in "aeiou" and low[-3] not in "aeiou":
            vs |= {low + low[-1] + "ing", low + low[-1] + "ed", low + low[-1] + "d"}
    out = set(vs)
    for v in vs:
        if v:
            out.add(v[0].upper() + v[1:])
    return [v for v in out if v]


def regex_for_tokens(toks):
    parts = []
    for t in toks:
        parts.append(r"\s+".join(re.escape(x) for x in t.split()))
    return r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)"


def find_card_surface(word, text):
    """返回正文中与词卡对应的最短连续写法；找不到返回 None。"""
    toks = [t for t in str(word).split() if t and t not in ("A", "B", "sb.", "sth.", "phr.")]
    if not toks:
        return None
    # ① 整词（含不规则变形）：依次尝试替换每个 token 的变形
    for i in range(len(toks)):
        for v in token_variants(toks[i]):
            trial = list(toks)
            trial[i] = v
            m = re.search(regex_for_tokens(trial), text, re.I)
            if m:
                return re.sub(r"\s+", " ", m.group(0))
    # ② 逐个截短尾部 token，保住最长可命中的前缀
    for n in range(len(toks) - 1, 0, -1):
        sub = toks[:n]
        for i in range(n):
            for v in token_variants(sub[i]):
                trial = list(sub)
                trial[i] = v
                m = re.search(regex_for_tokens(trial), text, re.I)
                if m:
                    return re.sub(r"\s+", " ", m.group(0))
    return None


def generate_marks(cards, text):
    pairs = []
    for c in cards:
        w = c["w"]
        s = find_card_surface(w, text)
        if not s:
            raise PublishError(f"词卡无法在原文定位：{w}")
        pairs.append([w, s])
    return pairs


# ---------------- PDF 文本抽取 ----------------

def extract_headline(pdf_path, preview=False):
    doc = pymupdf.open(str(pdf_path))
    lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
    if preview:
        body = [l for l in lines if "Morning English" not in l and "早安英" not in l
                and not re.fullmatch(r"\d{1,2}", l)]
        if not body:
            raise PublishError(f"无法从预习 PDF 抽取标题：{pdf_path.name}")
        title_en = join_en([body[0]])
        deck_en = ""
        if len(body) > 1 and len(body[1].split()) <= 10 and not body[1].endswith(","):
            deck_en = join_en([body[1]])
        m = re.search(r"第\s*(\d+)\s*天", doc[0].get_text())
        return title_en, "", deck_en, "", (int(m.group(1)) if m else None)
    groups = []
    for line in lines:
        if "Morning English" in line or "早安英" in line or re.fullmatch(r"\d{1,2}", line):
            continue
        typ = "zh" if re.search(r"[\u4e00-\u9fff]", line) else "en"
        if groups and groups[-1][0] == typ:
            groups[-1][1].append(line)
        else:
            groups.append((typ, [line]))
    ens = [join_en(g) for t, g in groups if t == "en"]
    zhs = ["".join(g) for t, g in groups if t == "zh"]
    if not ens or not zhs:
        raise PublishError(f"无法从 PDF 首页抽取标题：{pdf_path.name}")
    title_en, title_zh = ens[0], zhs[0]
    deck_en = ens[1] if len(ens) > 1 else ""
    deck_zh = zhs[1] if len(zhs) > 1 else ""
    full = doc[0].get_text()
    m = re.search(r"第\s*(\d+)\s*天", full)
    day = int(m.group(1)) if m else None
    return title_en, title_zh, deck_en, deck_zh, day


def extract_preview_paragraphs(pdf_path):
    doc = pymupdf.open(str(pdf_path))
    pages_blocks = []
    for page in doc:
        raw = page.get_text()
        blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
        kept = []
        for b in blocks:
            lines = [l.strip() for l in b.splitlines() if l.strip()]
            lines = [l for l in lines if not re.search(r"早安英|Morning English", l)
                     and not re.fullmatch(r"\d{1,2}", l)]
            if not lines:
                continue
            text = join_en(lines)
            if len(text) < 20:
                continue  # 标题/副标题/页码
            kept.append(text.rstrip(" ■"))
        pages_blocks.append(kept)
    paras = []
    for block in pages_blocks:
        if not block:
            continue
        if paras and not re.search(r"[.!?]\u201d?$|[\u201d!?]$", paras[-1].strip()):
            paras[-1] += " " + block[0]
            block = block[1:]
        paras.extend(block)
    if len(paras) < 5:
        # 文本层无空行：按 bbox 行距切段（段内约 31pt、段间约 62pt，阈值 45）
        groups = []
        for pi, page in enumerate(doc):
            rows = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    t = "".join(sp["text"] for sp in line["spans"]).strip()
                    if not t or re.search(r"早安英|Morning English", t) or re.fullmatch(r"\d{1,2}", t):
                        continue
                    rows.append((line["bbox"][1], t))
            rows.sort()
            if not rows:
                continue
            cur, prev_y = [rows[0][1]], rows[0][0]
            for y, t in rows[1:]:
                if y - prev_y > 45:
                    groups.append((pi, cur))
                    cur = []
                cur.append(t)
                prev_y = y
            groups.append((pi, cur))
        paras = []
        for pi, group in groups:
            txt = join_en(group).rstrip(" ■")
            if pi == 0 and len(txt.split()) < 20:
                continue  # 首页标题/副标题不进正文
            if paras and not re.search(r"[.!?][\u201d\u2019]?$", paras[-1]):
                paras[-1] += " " + txt
            else:
                paras.append(txt)
    if len(paras) < 5:
        raise PublishError(f"预习 PDF 切段异常，仅 {len(paras)} 段：{pdf_path.name}")
    return paras


# ---------------- 核验 ----------------

def verify_page_stage(html_path, paras, cards, audio, stage_audio_dir=None):
    if not CHROME or not os.path.exists(CHROME):
        raise PublishError("找不到 Chrome，无法核验")
    target = "file://" + str(html_path)
    with tempfile.TemporaryDirectory(prefix="auto-pdf-") as td:
        pdf = os.path.join(td, "check.pdf")
        r = subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
                            "--no-pdf-header-footer", f"--print-to-pdf={pdf}", target],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(pdf):
            raise PublishError("打印 PDF 生成失败")
        d = pymupdf.open(pdf)
        text = "".join(p.get_text() for p in d)
        if d.page_count != 2:
            raise PublishError(f"打印页数 {d.page_count} != 2")
        found = [w for w in UI_WORDS if w in text]
        if found:
            raise PublishError(f"打印文本含界面词：{found}")
    r = subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
                        "--dump-dom", "--virtual-time-budget=12000", target],
                       capture_output=True, text=True)
    dom = r.stdout or ""
    n_par = len(re.findall(r'class="en-block en"', dom))
    n_card = len(re.findall(r'class="voc"', dom))
    n_audio = len(re.findall(r'class="p-audio', dom))
    if n_par != paras:
        raise PublishError(f"DOM 正文段 {n_par} != {paras}")
    if n_card != cards:
        raise PublishError(f"DOM 词卡 {n_card} != {cards}")
    if audio:
        if n_audio < paras + 1:
            raise PublishError(f"朗读按钮 {n_audio} < {paras + 1}")
        if stage_audio_dir:
            files = list(Path(stage_audio_dir).glob("*.m4a"))
            if len(files) != paras + 1 or any(f.stat().st_size < 1000 for f in files):
                raise PublishError(f"音频文件数/大小异常：{len(files)} 个")
    elif n_audio:
        raise PublishError(f"预习版不应有朗读按钮，实为 {n_audio}")
    log(f"核验通过：打印 2 页、段落 {n_par}、词卡 {n_card}、朗读按钮 {n_audio}")


def verify_verbatim(content, pdf_path):
    doc = pymupdf.open(str(pdf_path))
    pages = [p.get_text() for p in doc]
    ex_pages, an_pages = [], []
    for i, t in enumerate(pages):
        if "请将以下中文句子翻译为英文" in t:
            ex_pages.append(i)
        if "参考答案" in t and i > len(pages) // 2:
            an_pages.append(i)
    if not ex_pages or not an_pages:
        raise PublishError("找不到练习/答案页，逐字校验失败")
    norm = lambda s: re.sub(r"\s+", "", s)
    ex_src = "".join(pages[i] for i in range(ex_pages[0], max(ex_pages) + 1))
    an_src = "".join(pages[i] for i in range(an_pages[0], max(an_pages) + 1))
    practice = content["practice"]
    items = practice.get("exercise_verbatim") or practice.get("items") or []
    answers = practice.get("answer_verbatim") or practice.get("answer") or ""
    if isinstance(answers, list):
        answers = "<br><br>".join(answers)
    for i, item in enumerate(items, 1):
        if norm(strip_tags(item)) not in norm(ex_src):
            raise PublishError(f"练习第 {i} 条未逐字命中源 PDF")
    for i, ans in enumerate(re.split(r"<br\s*/?>", str(answers)), 1):
        ans = re.sub(r"^\s*\d+\.\s*", "", strip_tags(ans))
        if ans and norm(ans) not in norm(an_src):
            raise PublishError(f"答案第 {i} 条未逐字命中源 PDF")
    log(f"练习/答案逐字校验通过：{len(items)} 题")


# ---------------- 流程 ----------------

def make_common(date, source_label, title_en, title_zh, day):
    source_en = SOURCE_EN.get(source_label, source_label)
    category = f"英国《{source_label}》外刊讲解 第{day}天"
    return {
        "date": date,
        "title_tag": f"{title_en} —— 英国《{source_label}》外刊讲解第{day}天",
        "h1": title_en,
        "source_label": source_label,
        "source_en": source_en,
        "category": category,
        "read_minutes": 12,
        "nav_hint": title_zh[:40],
        "sources_note": f"依据《{source_label}》{date} 报道。",
    }


def next_day(date):
    r = py(ROOT / "scripts/daily-check.py", check=False)
    days = []
    for d, _ in parse_todo(r.stdout or ""):
        days.append(d)
    for f in (ROOT / "scripts/content").glob("*.json"):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:_\d+)?\.json", f.name)
        if m:
            days.append(m.group(1))
    prev = max((d for d in days if d < date), default=None)
    if not prev:
        raise PublishError("无法推算期次天数")
    c = json.load(open(ROOT / "scripts/content" / f"{prev}.json", encoding="utf-8"))
    m = re.search(r"第\s*(\d+)\s*天", c.get("category", ""))
    if not m:
        raise PublishError(f"上一期 {prev} 无天数标签")
    return int(m.group(1)) + 1


def stage_notes(date, pdf, stage):
    log(f"B 流程：{date} {pdf.name}")
    parsed = stage / "parsed.json"
    dump = stage / "dump.txt"
    py(ROOT / "scripts/parse-notes-pdf.py", pdf, "--out", parsed, "--dump-text", dump)
    p = json.load(open(parsed, encoding="utf-8"))
    title_en, title_zh, deck_en, deck_zh, day = extract_headline(pdf)
    m = re.search(r"【来源：([^】]+)】", pdf.name)
    source_label = m.group(1) if m else "经济学人"
    day = day or next_day(date)
    common = make_common(date, source_label, title_en, title_zh, day)
    headline_en = title_en + ("|" + deck_en if deck_en else "")
    headline_zh = title_zh + deck_zh
    config = {
        "date": date, "title_tag": common["title_tag"], "h1": common["h1"],
        "source_label": source_label, "category": common["category"],
        "read_minutes": common["read_minutes"], "nav_hint": common["nav_hint"],
        "headline_en": headline_en, "headline_zh": headline_zh,
        "sources_note": common["sources_note"],
        "headline_marks": generate_marks(p["headline_cards"], headline_en),
        "marks": {},
        "mindmap": {"template": "scripts/content/2026-11-21.json", "aria": "", "alt": "", "repl": []},
    }
    for n in p["paragraphs"]:
        n = str(n["n"])
        cards = p["para_cards"].get(n) or []
        if cards:
            config["marks"][n] = generate_marks(cards, p["paragraphs"][int(n) - 1]["en"])
    issue = stage / "issue.json"
    json.dump(config, open(issue, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    content = stage / "content.json"
    py(ROOT / "scripts/make-content-json.py", parsed, "--issue", issue, "--out", content)
    c = json.load(open(content, encoding="utf-8"))
    c["mindmap"] = {"aria": "", "alt": "", "svg": "", "img": ""}
    c["audio"] = True
    json.dump(c, open(content, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for i, para in enumerate(c["paragraphs"], 1):
        marks = para["en_html"].count('<mark class="voc">')
        if marks != len(para["notes"]):
            raise PublishError(f"第 {i} 段词卡 {len(para['notes'])} != 标记 {marks}")
    verify_verbatim(c, pdf)
    audio_dir = stage / "audio"
    py(ROOT / "scripts/gen-paragraph-audio.py", content, audio_dir)
    page = stage / "page.html"
    py(ROOT / "scripts/build-reading-page.py", content, page)
    cards = sum(len(x["notes"]) for x in c["paragraphs"]) + len(c["headline"]["notes"])
    verify_page_stage(page, len(c["paragraphs"]), cards, True, audio_dir)
    return {
        "date": date, "kind": "NOTES", "pdf": str(pdf), "content": c,
        "source_label": source_label, "source_en": common["source_en"],
        "title": title_en, "stage": str(stage), "stage_content": str(content),
        "stage_issue": str(issue), "stage_page": str(page), "stage_audio": str(audio_dir),
        "paras": len(c["paragraphs"]), "cards": cards, "proper": len(c["proper"]),
    }


def stage_preview(date, pdf, stage):
    log(f"A 流程：{date} {pdf.name}")
    paras = extract_preview_paragraphs(pdf)
    title_en, title_zh, deck_en, deck_zh, day = extract_headline(pdf, preview=True)
    m = re.search(r"【来源：([^】]+)】", pdf.name)
    source_label = m.group(1) if m else "经济学人"
    day = day or next_day(date)
    common = make_common(date, source_label, title_en, title_zh, day)
    c = {
        "date": date, "title_tag": common["title_tag"], "h1": common["h1"],
        "source_label": source_label, "category": common["category"],
        "read_minutes": common["read_minutes"], "nav_hint": common["nav_hint"],
        "audio": False,
        "headline": {"en_html": "", "zh": "", "notes": []},
        "paragraphs": [{"en_html": p, "zh": "", "notes": []} for p in paras],
        "proper": [], "sources_note": common["sources_note"], "practice": {},
        "mindmap": {"aria": "", "alt": "", "svg": "", "img": ""},
    }
    if len(paras) >= 11 or sum(len(x) for x in paras) >= 5800:
        c["print_compact_dense"] = True
    content = stage / "content.json"
    json.dump(c, open(content, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    skip = [title_en] + ([deck_en] if deck_en else [])
    r = py(SKILL_SCRIPTS / "verify-transcript.py", content, pdf,
           *[x for s in skip for x in ("--skip", s)], check=False)
    if r.returncode != 0:
        raise PublishError("预习版逐字核验失败：" + (r.stdout or "")[-1500:])
    page = stage / "page.html"
    py(ROOT / "scripts/build-reading-page.py", content, page)
    verify_page_stage(page, len(paras), 0, False)
    return {
        "date": date, "kind": "PREVIEW", "pdf": str(pdf), "content": c,
        "source_label": source_label, "source_en": common["source_en"],
        "title": title_en, "stage": str(stage), "stage_content": str(content),
        "stage_page": str(page), "paras": len(paras), "cards": 0, "proper": 0,
    }


def apply_to_repo(item, no_push=False):
    date = item["date"]
    ym = f"{date[:4]}/{date[5:7]}"
    page_path = ROOT / "articles" / ym / f"{date}_001.reading.html"
    content_path = ROOT / "scripts/content" / f"{date}.json"
    issue_path = ROOT / "scripts/content/issues" / f"{date}.json"
    files = [page_path, content_path]

    # 英文原文相对预习版是否修订：决定索引是否 refresh
    refresh = False
    if item["kind"] == "NOTES" and content_path.exists() and page_path.exists():
        old = json.load(open(content_path, encoding="utf-8"))
        new_en = [strip_tags(p["en_html"]) for p in item["content"]["paragraphs"]]
        old_en = [strip_tags(p.get("en_html", "")) for p in old.get("paragraphs", [])]
        refresh = old_en != new_en
        log(f"索引策略：{'refresh' if refresh else '沿用'}（英文原文{'有' if refresh else '无'}修订）")

    # articles.js 登记
    art = ROOT / "articles.js"
    src = art.read_text(encoding="utf-8")
    if f'publishDate: "{date}"' not in src:
        entry = (f"      {{\n        title: {json.dumps(item['title'], ensure_ascii=False)},\n"
                 f"        publishDate: \"{date}\",\n        fileKey: \"{date}_001\",\n"
                 f"        readingPath: \"/outward-reading/articles/{ym}/{date}_001.reading.html\",\n"
                 f"        source: {json.dumps(item['source_en'], ensure_ascii=False)}\n      }},\n")
        marker = "const ARTICLES = [\n"
        if marker not in src:
            raise PublishError("articles.js 找不到 ARTICLES 数组")
        src = src.replace(marker, marker + entry, 1)
        art.write_text(src, encoding="utf-8")
        log(f"articles.js 新增 {date} 条目")
    files.append(art)

    shutil.copyfile(item["stage_content"], content_path)
    if "stage_issue" in item:
        shutil.copyfile(item["stage_issue"], issue_path)
        files.append(issue_path)
    if "stage_audio" in item:
        audio_target = ROOT / "articles" / ym / "audio" / date
        if audio_target.exists():
            shutil.rmtree(audio_target)
        shutil.copytree(item["stage_audio"], audio_target)
        files.extend(sorted(audio_target.glob("*.m4a")))
    shutil.copyfile(item["stage_page"], page_path)

    py(ROOT / "scripts/inject-seq-nav.py", date)
    py(ROOT / "scripts/patch-back-cal.py", page_path)
    prev_date = None
    ds = sorted(p.stem[:10] for p in (ROOT / "articles" / ym).glob("*_001.reading.html"))
    ds = [d for d in ds if d < date]
    if ds:
        prev_date = ds[-1]
        py(ROOT / "scripts/patch-back-cal.py", ROOT / "articles" / ym / f"{prev_date}_001.reading.html")
    idx_args = ["--refresh", date] if refresh else []
    py(ROOT / "scripts/sync-search-index.py", *idx_args)
    run(["node", "--check", "articles.js"])
    run(["node", "--check", "search-index.js"])
    files.extend([ROOT / "index.html", ROOT / "search-index.js"])
    files = list(dict.fromkeys(files))

    kind_cn = "完整笔记" if item["kind"] == "NOTES" else "预习原文"
    audio_cn = "含音频" if item["kind"] == "NOTES" else "无音频"
    msg = (f"{date} {kind_cn}上线：{item['title'][:48]}，{item['paras']}段/"
           f"{item['cards']}词卡/{item['proper']}专名，{audio_cn}（无人值守脚本）")
    run(["git", "add", *[str(f) for f in files]])
    r = run(["git", "commit", "-m", msg], check=False)
    if r.returncode != 0:
        log("git commit 返回非 0：" + (r.stdout + r.stderr)[-800:])
    else:
        log("已提交：" + msg)

    if no_push:
        log("--no-push：跳过推送与线上核验")
        return {"committed": True, "pushed": False}
    pushed = False
    for i in range(1, 9):
        r = run(["git", "push", "origin", "main"], check=False)
        if r.returncode == 0:
            pushed = True
            log(f"推送成功（第 {i} 次）")
            break
        log(f"推送第 {i} 次失败：{(r.stderr or '').strip().splitlines()[-1:]}")
        if i < 8:
            time.sleep(10)
    if not pushed:
        return {"committed": True, "pushed": False, "error": "推送失败，提交已保留"}
    time.sleep(65)
    online = "https://taciloquy.github.io/outward-reading/articles/" + f"{ym}/{date}_001.reading.html"
    r = subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
                        "--dump-dom", "--virtual-time-budget=15000", online],
                       capture_output=True, text=True)
    dom = r.stdout or ""
    ok = (item["title"] in dom
          and len(re.findall(r'class="en-block en"', dom)) == item["paras"])
    log(f"线上核验：{'通过' if ok else '失败'} {online}")
    return {"committed": True, "pushed": True, "online_ok": ok, "url": online}


def scan_handmap_window():
    """C 章节：新期次无骨架直接跳过；历史期次只报告，不出图。"""
    today = dt.date.today()
    notes = []
    for delta in (-1, 0, 1):
        d = (today + dt.timedelta(days=delta)).isoformat()
        outline = ROOT / "scripts/content/outlines" / f"{d}.json"
        if not outline.exists():
            continue
        g = py(ROOT / "scripts/mm-gate.py", "--date", d, "--stage", "handmap", check=False)
        page = ROOT / "articles" / f"{d[:4]}/{d[5:7]}" / f"{d}_001.reading.html"
        if g.returncode == 0 and page.exists() and "手绘版</button>" not in page.read_text(encoding="utf-8"):
            notes.append(f"{d} 骨架已确认但缺手绘版：脚本不调用图像生成，留待人工处理")
    return notes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="正式写仓库并提交推送；默认只 dry-run")
    ap.add_argument("--force-date", help="演练/强制处理指定日期（跳过 daily-check 清单）")
    ap.add_argument("--no-push", action="store_true", help="提交但不推送（演练用）")
    ap.add_argument("--status-file", default=str(STATUS_PATH))
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("已有实例在运行，退出")
        return 0

    result = {"started": dt.datetime.now().isoformat(timespec="seconds"),
              "apply": args.apply, "items": [], "errors": [], "handmap": []}
    try:
        if not PDF_ROOT.exists():
            raise PublishError(f"源盘未挂载：{PDF_ROOT}")
        if args.force_date:
            dates = [(args.force_date, "FORCED")]
        else:
            r = py(ROOT / "scripts/daily-check.py")
            dates = parse_todo(r.stdout or "")
        log("待处理：" + (", ".join(f"{d}:{t}" for d, t in dates) or "无"))
        for date, todo in dates:
            preview_pdf, notes_pdf = find_pdfs(date)
            kind, why = decide_type(date, notes_pdf, preview_pdf, forced=bool(args.force_date))
            if kind == "SKIP":
                log(f"{date} 已发布且 PDF 未更新，跳过")
                continue
            if kind == "ERROR":
                raise PublishError(f"{date} 闸门不通过：{why[-600:]}")
            pdf = notes_pdf if kind == "NOTES" else preview_pdf
            if not pdf:
                raise PublishError(f"{date} 无可用 PDF")
            with tempfile.TemporaryDirectory(prefix="auto-publish-") as td:
                stage = Path(td)
                item = stage_notes(date, pdf, stage) if kind == "NOTES" else stage_preview(date, pdf, stage)
                item["why"] = why.strip().splitlines()[-1] if why.strip() else ""
                if args.apply:
                    item.update(apply_to_repo(item, no_push=args.no_push))
                else:
                    log(f"dry-run：{date} 全部核验通过，未写仓库")
                result["items"].append({k: v for k, v in item.items()
                                        if k not in ("content", "stage", "stage_content",
                                                     "stage_issue", "stage_page", "stage_audio")})
        result["handmap"] = scan_handmap_window()
        for n in result["handmap"]:
            log("C 章节提示：" + n)
        status = 0
    except PublishError as e:
        result["errors"].append(str(e))
        log("异常停止：" + str(e))
        status = 2
    except Exception as e:
        result["errors"].append(repr(e))
        log("未预期异常：" + repr(e))
        status = 3
    finally:
        result["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        json.dump(result, open(args.status_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        fcntl.flock(lock, fcntl.LOCK_UN)
    return status


if __name__ == "__main__":
    sys.exit(main())
