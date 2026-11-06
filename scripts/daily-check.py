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
SOURCE_ROOT = "/Volumes/WORK DISK/QHY/读书/1.早安英文"


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
        elif "预习原文" in base:
            out["preview"].append(p)
        else:
            out["other"].append(p)
    return out, month_dir


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
    return {"date": date_str, "pdfs": pdfs, "month_dir": month_dir,
            "state": st, "action": action, "stale": stale}


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
    hint = {
        "PREVIEW": "上【预习原文】原文首发：audio=false、zh/notes/proper/practice 留空、导图先矢量（手绘等用户确认）",
        "NOTES": "上【完整笔记】：覆盖同日期同 URL，补译文/词卡/练习，audio=true 并生成标题+段落英音朗读",
        "DONE": "已是最新",
        "NONE": "无 PDF",
    }[r["action"]]
    print(f"  → {r['action']}：{hint}")
    if r["stale"]:
        print("  ⚠ 完整笔记 PDF 比已发布页面更新，建议重跑一遍完整笔记流水线")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--window", type=int, default=1, help="前后各查几天（默认 1）")
    ap.add_argument("--source", default=None, help="源根目录（测试用，默认 WORK DISK 路径）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    base = datetime.strptime(a.date, "%Y-%m-%d") if a.date else datetime.now()
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
