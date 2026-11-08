#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mm-gate.py — 发布侧导图闸门（用户 2026-11-08 定）。

背景：11-08 这一期完整笔记直接上线，导图骨架只在事后汇报里才被用户看到。
用户要求：完整笔记上线前也要像预习原文一样，先让他确认骨架过不过关，
确认之后才做手绘版的图。此脚本把这条规则落成可执行的闸门，而不是只写在提示词里。

用法：
  python3 scripts/mm-gate.py --date YYYY-MM-DD --stage publish   # 构建正式页面 / 推送前
  python3 scripts/mm-gate.py --date YYYY-MM-DD --stage handmap   # 出 ImageGen 手绘版前
  python3 scripts/mm-gate.py --date YYYY-MM-DD --quiet           # 只看退出码

退出码：
  0   放行
  20  没有骨架大纲（scripts/content/outlines/DATE.json 不存在）
  21  骨架没跑过 preflight，或通过后又被改过，或本身不合格（需重跑 preflight）
  22  骨架未经用户确认（待确认：不许写仓库页面、不许推送、不许出图）
  23  配置不生效（该日期早于 apply_from，历史重建按老规矩放行），仅提示

判定依据：
  - 骨架质量沿用 gen-mindmap.py 的同一套检查（单一事实来源，避免两处规则漂移）
  - 「已确认」只认 outlines/DATE.json.pass.json 里的 user_confirmed
    （该字段只由 `mm-preflight.py <outline> --confirm` 写入，即用户在对话里点头之后）
"""
import argparse
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO, "scripts/config/publish-gates.json")
DEFAULT_CONFIG = {"mm_confirm_before_publish": True, "apply_from": "2099-01-01"}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
        except Exception as e:
            print(f"⚠ 闸门配置读取失败（按默认从严处理）：{e}")
            cfg["mm_confirm_before_publish"] = True
    return cfg


def inspect(date_str):
    """读大纲与通行证，返回状态字典（不打印）。"""
    outline_path = os.path.join(REPO, "scripts/content/outlines", f"{date_str}.json")
    st = {"date": date_str, "outline_path": outline_path, "outline": None,
          "outline_mtime": 0, "has_outline": os.path.exists(outline_path),
          "confirmed": False, "checked_at": None, "checks": [], "fails": [],
          "branch_count": 0, "subs_counts": [], "center": "", "branches": []}
    if not st["has_outline"]:
        return st
    st["outline_mtime"] = os.path.getmtime(outline_path)
    try:
        o = json.load(open(outline_path, encoding="utf-8"))
    except Exception as e:
        st["fails"].append(f"大纲 JSON 读不了：{e}")
        return st
    st["outline"] = o
    st["center"] = (o.get("center") or {}).get("main", "")
    st["branches"] = o.get("branches") or []
    st["branch_count"] = len(st["branches"])
    st["subs_counts"] = [len(b.get("subs") or []) for b in st["branches"]]

    # 骨架质量：与 gen-mindmap 共用同一份检查
    try:
        gm = load_module(os.path.join(REPO, "scripts/gen-mindmap.py"), "gen_mindmap")
        st["fails"] = gm._preflight_check(o)
    except Exception as e:
        st["fails"].append(f"骨架检查器加载失败：{e}")

    stamp_path = outline_path + ".pass.json"
    if not os.path.exists(stamp_path):
        st["fails"].append("没有 preflight 通行证（先跑 scripts/mm-preflight.py）")
        return st
    try:
        stamp = json.load(open(stamp_path, encoding="utf-8"))
    except Exception as e:
        st["fails"].append(f"通行证读不了：{e}")
        return st
    st["checked_at"] = stamp.get("checked_at")
    st["confirmed"] = bool(stamp.get("user_confirmed"))
    if st["outline_mtime"] > float(stamp.get("outline_mtime", 0)) + 0.001:
        st["fails"].append("大纲在通过校验之后又被改过（骨架变了但没重跑 preflight）")
    return st


def print_report(st, stage):
    print("-" * 60)
    print(f"导图闸门：{st['date']}　阶段={stage}")
    if not st["has_outline"]:
        print("  骨架：缺（没有 outlines/%s.json）" % st["date"])
        print("-" * 60)
        return
    print(f"  骨架：{st['branch_count']} 枝　子点数 {st['subs_counts']}　"
          f"中心「{st['center']}」")
    print(f"  校验：{'通过' if not st['fails'] else '不合格'}"
          f"　preflight：{st['checked_at'] or '未跑'}"
          f"　用户确认：{'已确认' if st['confirmed'] else '待确认'}")
    for i, b in enumerate(st["branches"], 1):
        print(f"    {i}. {b.get('title', '(空)')}　[{b.get('range', '无段落')}]　"
              f"关系={b.get('relation') or '—'}　子点 {len(b.get('subs') or [])}")
    if st["fails"]:
        for f in st["fails"]:
            print("    ✗ " + f)
    print("-" * 60)


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--stage", choices=["publish", "handmap"], default="publish")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    cfg = load_config()
    st = inspect(a.date)
    apply_from = (cfg.get("apply_from") or "").strip()

    if not a.quiet:
        print_report(st, a.stage)

    # 手绘版闸门：不受生效日影响，任何日期都只认用户确认
    if a.stage == "handmap":
        if not st["has_outline"]:
            if not a.quiet:
                print("✗ 没有骨架：手绘版必须先有大纲并通过 preflight")
            return 20
        if st["fails"]:
            if not a.quiet:
                print("✗ 骨架不合格或被改过：先修骨架并重跑 preflight")
            return 21
        if not st["confirmed"]:
            if not a.quiet:
                print("✗ 骨架未获用户确认：禁止调用 ImageGen 出手绘版。"
                      f"先把骨架表报给用户；用户点头后跑 "
                      f"`python3 scripts/mm-preflight.py scripts/content/outlines/{a.date}.json --confirm`")
            return 22
        if not a.quiet:
            print("✓ 骨架已确认，可以出手绘版")
        return 0

    # 发布闸门：早于生效日的日期整体放行，历史重建不受这条规则牵连
    if apply_from and a.date < apply_from:
        if not a.quiet:
            print(f"· 该日期早于规则生效日 {apply_from}，放行（历史重建）")
        return 0

    if not st["has_outline"]:
        if not a.quiet:
            print("✗ 没有骨架：完整笔记也必须先出大纲、跑 preflight、把骨架表报给用户")
        return 20
    if st["fails"]:
        if not a.quiet:
            print("✗ 骨架不合格或被改过：先修骨架，再跑 "
                  f"`python3 scripts/mm-preflight.py scripts/content/outlines/{a.date}.json`")
        return 21
    if cfg.get("mm_confirm_before_publish", True) and not st["confirmed"]:
        if not a.quiet:
            print("✗ 骨架待用户确认：不许把完整笔记写进仓库、不许推送。\n"
                  "   可先把页面构建到仓库外（如 /tmp）做版式与打印核验，把骨架表报给用户；\n"
                  f"   用户点头后跑 `python3 scripts/mm-preflight.py scripts/content/outlines/{a.date}.json --confirm`，"
                  "再正式构建上线。")
        return 22
    if not a.quiet:
        print("✓ 放行：骨架合格且已确认" if st["confirmed"] else "✓ 放行：骨架合格（配置不要求上线前确认）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
