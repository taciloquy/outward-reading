#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily-check.py — 每日自动发布前的状态检查（供定时任务用，只读不写）

用法：
  python3 scripts/daily-check.py                 # 检查 昨天/今天/明天（默认窗口 ±1）
  python3 scripts/daily-check.py --window 2      # 前后各 2 天
  python3 scripts/daily-check.py --date 2026-11-07 --window 0
  python3 scripts/daily-check.py --json

为什么默认覆盖前后一天：早安英文的 PDF 常提前一天到（11-06 收到 20261107 的
预习原文），只查「今天」会漏。

每个日期给出建议动作：
  PREVIEW  有预习原文、页面还没有      → 上原文首发（audio=false，导图先矢量）
  NOTES    有完整笔记、页面还非完整版  → 上/覆盖完整笔记（audio=true，生成朗读）
  DONE     当天已最新
  NONE     当天无 PDF
汇总段列出所有需要动手的日期，供定时任务直接按序执行。
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_ROOT = "/Volumes/WORK DISK/QHY/03_学习与阅读/读书/1.早安英文"


def find_pdfs(date_str, source_root=None):
    ymd = date_str.replace("-", "")
    month_dir = os.path.join(source_root or SOURCE_ROOT, ymd[:6])
    out = {"preview": [], "notes": [], "other": []}
    if not os.path.isdir(month_dir):
        return out, month_dir
    for p in sorted(glob.glob(os.path.join(month_dir, f"{ymd}*.pdf"))):
        base = os.path.basename(p)
        if "完整笔记" in base:
            out["notes"].append(p)
        elif "预习" in base:  # 预习原文 与 原文预习 等价，均按预习原文处理
            out["preview"].append(p)
        else:
            out["other"].append(p)
    return out, month_dir


def mm_state(date_str):
    """导图骨架状态（与 scripts/mm-gate.py 同源，只读）。"""
    op = os.path.join(REPO, "scripts", "content", "outlines", f"{date_str}.json")
    if not os.path.exists(op):
        return {"state": "missing", "label": "缺（还没写大纲）", "branches": 0, "subs": []}
    try:
        o = json.load(open(op, encoding="utf-8"))
    except Exception:
        return {"state": "bad", "label": "大纲读不了", "branches": 0, "subs": []}
    n = len(o.get("branches") or [])
    subs = [len(b.get("subs") or []) for b in o.get("branches") or []]
    sp = op + ".pass.json"
    if not os.path.exists(sp):
        return {"state": "nocheck", "label": "未跑 preflight", "branches": n, "subs": subs}
    try:
        stamp = json.load(open(sp, encoding="utf-8"))
    except Exception:
        return {"state": "bad", "label": "通行证读不了", "branches": n, "subs": subs}
    if os.path.getmtime(op) > float(stamp.get("outline_mtime", 0)) + 0.001:
        return {"state": "stale", "label": "骨架改过未复检", "branches": n, "subs": subs}
    if not stamp.get("user_confirmed"):
        return {"state": "pending", "label": "待用户确认", "branches": n, "subs": subs}
    return {"state": "confirmed", "label": "已确认", "branches": n, "subs": subs}


def page_state(date_str):
    y, m = date_str[:4], date_str[5:7]
    html = os.path.join(REPO, "articles", y, m, f"{date_str}_001.reading.html")
    cj = os.path.join(REPO, "scripts", "content", f"{date_str}.json")
    st = {
        "html": os.path.exists(html), "html_path": html,
        "content": os.path.exists(cj),
        "paras": 0, "translated": False, "cards": 0, "proper": 0,
        "practice": False, "audio": None, "mindmap_img": False,
        "registered": False, "notes_ready": False,
        "mm": mm_state(date_str),
        "html_mtime": os.path.getmtime(html) if os.path.exists(html) else 0,
    }
    if st["content"]:
        try:
            c = json.load(open(cj, encoding="utf-8"))
        except Exception:
            c = {}
        paras = c.get("paragraphs") or []
        st["paras"] = len(paras)
        st["translated"] = any((p.get("zh") or "").strip() for p in paras)
        st["cards"] = sum(len(p.get("notes") or []) for p in paras)
        st["proper"] = len(c.get("proper") or [])
        pr = c.get("practice") or {}
        st["practice"] = bool(pr.get("items") or pr.get("answer") or pr.get("critical_en"))
        st["audio"] = c.get("audio")
        st["mindmap_img"] = bool((c.get("mindmap") or {}).get("img"))
        st["notes_ready"] = bool(st["translated"] or st["cards"] or st["practice"])
    # 2026-11-08 首页轻量化：文章元数据已外置到 articles.js；
    # 兼容尚未拆分的工作区，回退读 index.html。
    idx = os.path.join(REPO, "articles.js")
    if not os.path.exists(idx):
        idx = os.path.join(REPO, "index.html")
    if os.path.exists(idx):
        s = open(idx, encoding="utf-8", errors="ignore").read()
        st["registered"] = f'publishDate: "{date_str}"' in s
    return st


def judge(date_str, source_root=None):
    pdfs, month_dir = find_pdfs(date_str, source_root)
    st = page_state(date_str)
    stale = False
    if pdfs["notes"]:
        action = "DONE" if st["notes_ready"] else "NOTES"
        newest = max(os.path.getmtime(p) for p in pdfs["notes"])
        stale = st["notes_ready"] and newest > st["html_mtime"] + 60
    elif pdfs["preview"]:
        action = "DONE" if st["html"] else "PREVIEW"
    else:
        action = "NONE"
    blocked = bool(pdfs["notes"])  # 同日已有完整笔记 → 预习原文一律不处理
    return {"date": date_str, "pdfs": pdfs, "month_dir": month_dir,
            "state": st, "action": action, "stale": stale, "preview_blocked": blocked}


def render(r):
    st, pdfs = r["state"], r["pdfs"]
    print(f"===== {r['date']} =====")
    print(f"源目录：{r['month_dir']}（{'存在' if os.path.isdir(r['month_dir']) else '不存在'}）")
    for key, label in (("preview", "预习原文"), ("notes", "完整笔记"), ("other", "其它 PDF（不处理）")):
        if pdfs[key]:
            for p in pdfs[key]:
                mt = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")
                print(f"  [{label}] {os.path.basename(p)}  {os.path.getsize(p)//1024} KB  改于 {mt}")
        else:
            print(f"  [{label}] 无")
    print(f"  页面：{'有' if st['html'] else '无'}　段落 {st['paras']}　"
          f"译文 {'有' if st['translated'] else '无'}　词卡 {st['cards']}　"
          f"专名 {st['proper']}　练习 {'有' if st['practice'] else '无'}　"
          f"audio={st['audio']}　手绘={'已接' if st['mindmap_img'] else '未接'}　"
          f"首页={'已登记' if st['registered'] else '未登记'}")
    mm = st.get("mm") or {}
    if mm:
        extra = f"　{mm['branches']} 枝 {mm['subs']}" if mm.get("branches") else ""
        print(f"  导图：{mm.get('label','?')}{extra}")
    hint = {
        "PREVIEW": "上【预习原文】原文首发：audio=false、zh/notes/proper/practice 留空、导图先矢量（手绘等用户确认）",
        "NOTES": "上【完整笔记】：先出导图骨架等用户确认，再补译文/词卡/练习、audio=true 并生成标题+段落英音朗读",
        "DONE": "已是最新",
        "NONE": "无 PDF",
    }[r["action"]]
    print(f"  → {r['action']}：{hint}")
    if pdfs["notes"] and pdfs["preview"]:
        print("  ⛔ 同日已有【完整笔记】：预习原文一律不处理（直接按完整笔记上）")
    elif st["notes_ready"]:
        print("  ⛔ 页面已是完整笔记版：不许用预习原文覆盖")
    if r["stale"]:
        print("  ⚠ 完整笔记 PDF 比已发布页面更新，建议重跑一遍完整笔记流水线")
    if r["action"] == "NOTES" and mm.get("state") != "confirmed":
        print(f"  ⛔ 导图骨架未就绪（{mm.get('label','缺')}）：先写大纲 → 跑 scripts/mm-preflight.py "
              "→ 把骨架表报给用户；用户确认后 preflight --confirm，才可正式构建与推送"
              "（scripts/mm-gate.py 会拦）")
    elif r["action"] == "PREVIEW" and mm.get("state") in ("missing", "nocheck", "stale", "bad"):
        print(f"  · 导图骨架{mm.get('label','缺')}：先写大纲 + preflight 再构建（预习原文可先上矢量，手绘等用户确认）")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--window", type=int, default=1, help="前后各查几天（默认 1）")
    ap.add_argument("--source", default=None, help="源根目录（测试用，默认 WORK DISK 路径）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", choices=["preview", "notes"], default=None,
                    help="闸门模式：preview=确认可以按预习原文处理；notes=确认需要/可以重跑完整笔记")
    a = ap.parse_args()

    root = a.source or SOURCE_ROOT
    if not os.path.isdir(root):
        print(f"⚠ 源目录根不存在：{root}")
        print("  多半是移动硬盘「WORK DISK」没挂载或未插上，PDF 无从检查。")
        print("  处置：直接汇报这一条，不要当作「今天没有新 PDF」。")
        if a.json:
            print(json.dumps({"error": "source_root_missing", "root": root}, ensure_ascii=False))
        return 0

    base = datetime.strptime(a.date, "%Y-%m-%d") if a.date else datetime.now()

    # ---- 闸门模式（供自动发布前强制检查，退出码非 0 即停止） ----
    if a.gate:
        d = base.strftime("%Y-%m-%d")
        r = judge(d, a.source)
        pdfs, st = r["pdfs"], r["state"]
        if a.gate == "preview":
            if pdfs["notes"]:
                name = os.path.basename(pdfs["notes"][0])
                print(f"[STOP] {d} 同日已有完整笔记：{name}")
                print("       规则：有完整笔记就不做预习原文，直接走完整笔记流程。")
                return 10
            if st["notes_ready"]:
                print(f"[STOP] {d} 页面已是完整笔记版，禁止用预习原文覆盖。")
                return 11
            if not pdfs["preview"]:
                print(f"[STOP] {d} 没有【预习原文】PDF，无从处理。")
                return 12
            print(f"[GO] {d} 可以按预习原文处理：{os.path.basename(pdfs['preview'][0])}")
            return 0
        # gate == notes
        if st["notes_ready"] and not r["stale"]:
            print(f"[SKIP] {d} 完整笔记版已发布且 PDF 未更新，无需重跑。")
            return 13
        if not pdfs["notes"]:
            print(f"[STOP] {d} 没有【完整笔记】PDF，无法走完整笔记流程。")
            return 14
        print(f"[GO] {d} 可以按完整笔记处理：{os.path.basename(pdfs['notes'][0])}")
        return 0
    dates = [(base + timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(-a.window, a.window + 1)]
    results = [judge(d, a.source) for d in dates]

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for r in results:
        render(r)

    todo = [r for r in results if r["action"] in ("PREVIEW", "NOTES") or r["stale"]]
    print("========== 汇总 ==========")
    if not todo:
        print("  全部已是最新，无需动作。")
    else:
        print("  需要动手：")
        for r in todo:
            tag = r["action"] if r["action"] != "DONE" else "RERUN"
            print(f"    {r['date']}  {tag}")
        print("  按日期从早到晚依次处理（先早后晚，保证翻页链接正确）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
