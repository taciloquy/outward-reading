#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mm-preflight.py — 思维导图「生图前」硬闸门（用户 2026-11-04 强制定）。

用途：在调用 ImageGen（花积分）之前，先校验大纲 JSON 是否真的按原文论证层次
搭出来的骨架，而不是套模板。通过后才允许出矢量 / 手绘。

用法：
  python3 scripts/mm-preflight.py outline.json          # 校验并打印骨架表
  python3 scripts/mm-preflight.py outline.json --quiet  # 只返回退出码

退出码：
  0  通过（可有 WARN）
  2  未通过：骨架不合格，禁止生图（按提示回 S1 重做）

检查项（对应 MEMORY.md 的 S1–S5 与 G0）：
  F1 枝数 2–6，且不是「4 枝 × 每枝 3 点」这类模板形状
  F2 各枝子点数量不得齐平（齐平＝机械凑数，禁止）
  F3 第 2 枝起必须有 relation（关系链不能缺）
  F4 每枝必须有 range（段落依据）与 title
  F5 分支标题 ≤7 字（矢量卡片 190px 装不下更长的，会溢出）
  F6 center 必须有 main + sub
"""
import json
import os
import sys
import time

MAX_TITLE = 7
FAILS, WARNS = [], []


def fail(msg):
    FAILS.append(msg)


def warn(msg):
    WARNS.append(msg)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in argv
    confirm = "--confirm" in argv
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    try:
        o = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[FAIL] 读不了大纲 JSON：{e}")
        return 2

    center = o.get("center") or {}
    branches = o.get("branches") or []
    n = len(branches)

    # F6 center
    if not center.get("main"):
        fail("center.main 为空：中心必须是全文主张")
    if not center.get("sub"):
        warn("center.sub 为空：建议补一句概括副标题")

    # F1 枝数
    if n < 2:
        fail(f"只有 {n} 枝：至少 2 枝")
    if n > 6:
        fail(f"{n} 枝过多：超过 6 枝说明没归并，退回 S2 合并论证层次")

    subs_counts = [len(b.get("subs") or []) for b in branches]

    # F1b 模板形状（4 枝 / 3 枝 × 每枝 3 点）
    if n in (3, 4) and subs_counts and len(set(subs_counts)) == 1 and subs_counts[0] == 3:
        fail(f"疑似模板化：{n} 枝 × 每枝恰好 3 点（{subs_counts}）。枝数/点数必须由原文论证层次得出，回 S1 重做")

    # F2 子点齐平
    if n >= 3 and len(set(subs_counts)) == 1:
        fail(f"各枝子点数完全相同 {subs_counts}：属于机械凑数，真实论证各枝长度不等（如 2/3/1/2）")

    # F3 关系链
    missing_rel = [i + 1 for i, b in enumerate(branches) if i > 0 and not b.get("relation")]
    if n >= 3 and len(missing_rel) == n - 1:
        fail("所有枝都没有 relation：没有关系链＝目录不是导图，先在 S3 判关系（对比/转折/递进/因果/解释）")
    elif missing_rel:
        warn(f"第 {missing_rel} 枝缺 relation（关系链有断点）")

    # F4/F5 逐枝
    for i, b in enumerate(branches, 1):
        t = (b.get("title") or "").strip()
        if not t:
            fail(f"第 {i} 枝 title 为空")
        elif len(t) > MAX_TITLE:
            fail(f"第 {i} 枝标题「{t}」{len(t)} 字 > {MAX_TITLE}：矢量卡片会溢出，压短")
        if not b.get("range"):
            warn(f"第 {i} 枝「{t}」缺 range（段落依据）")
        if not (b.get("subs") or []):
            fail(f"第 {i} 枝「{t}」没有子点")

    # F0 大纲必须落在仓库里（不许放 /tmp 这类临时目录，否则无法追溯、下次没法复核）
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_outline = os.path.abspath(path)
        if not abs_outline.startswith(repo_root + os.sep):
            fail(f"大纲不在仓库内（{abs_outline}）：必须存到 scripts/content/outlines/ 下，"
                 f"临时目录的骨架无从追溯")
    except Exception:
        repo_root, abs_outline = None, os.path.abspath(path)

    # ---- 输出骨架表（生图前必须把这个贴给用户）----
    if not quiet:
        print("=" * 60)
        print("思维导图骨架（生图前闸门）")
        print("=" * 60)
        print(f"中心：[{center.get('main','(空)')}] —— {center.get('sub','(空)')}")
        print(f"模式：{o.get('pattern','hub')}　枝数：{n}　子点数：{subs_counts}")
        print("-" * 60)
        chain = []
        for i, b in enumerate(branches, 1):
            rel = b.get("relation") or "—"
            print(f"{i}. {b.get('title','(空)')}　[{b.get('range','(无段落标注)')}]　"
                  f"关系={rel}　子点{len(b.get('subs') or [])}：{'／'.join(b.get('subs') or [])}")
            if i > 1 and b.get("relation"):
                chain.append(b["relation"])
        print("-" * 60)
        print("关系链：" + (" → ".join([branches[0].get("title", "①")] +
                                  [f"({r}) {branches[i].get('title','')}" for i, r in enumerate(chain, 1)])))
        print("=" * 60)
        if FAILS:
            print("\n[FAIL] 骨架不合格，禁止生图：")
            for f in FAILS:
                print("  ✗ " + f)
        for w in WARNS:
            print("  ! " + w)
        if not FAILS:
            print("\n[PASS] 骨架合格。下一步：出矢量 → 截图自查 → 把上表报用户 → 确认后才可 ImageGen")

    if FAILS:
        return 2

    # PASS → 写通行证（gen-mindmap 认这张票；改了骨架没重验就作废）
    if repo_root:
        stamp_path = abs_outline + ".pass.json"
        mtime = os.path.getmtime(abs_outline)
        # 确认过的骨架不该被「再跑一次 preflight 看表」这种动作悄悄撤销：
        # 只有骨架本身没动过，才沿用手上的 user_confirmed。
        carried = False
        if not confirm and os.path.exists(stamp_path):
            try:
                old = json.load(open(stamp_path, encoding="utf-8"))
                same_shape = (
                    old.get("branch_count") == n
                    and [b.get("subs") for b in (old.get("branches") or [])] == subs_counts
                    and (old.get("center") or "") == (center.get("main") or "")
                    and abs(float(old.get("outline_mtime", 0)) - mtime) <= 0.001
                )
                carried = bool(old.get("user_confirmed")) and same_shape
            except Exception:
                carried = False
        stamp = {
            "outline": os.path.relpath(abs_outline, repo_root),
            "outline_mtime": mtime,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # 只有用户在对话里点头后才允许带 --confirm 重跑一次，把确认落到文件里
            "user_confirmed": bool(confirm) or carried,
            "center": center.get("main"),
            "branches": [{"title": b.get("title"), "subs": len(b.get("subs") or []),
                          "relation": b.get("relation")} for b in branches],
            "branch_count": n,
            "subs_counts": subs_counts,
            "warns": WARNS,
        }
        with open(stamp_path, "w", encoding="utf-8") as f:
            json.dump(stamp, f, ensure_ascii=False, indent=2)
        if not quiet:
            print(f"通行证已写：{os.path.relpath(stamp_path, repo_root)}"
                  f"　user_confirmed={stamp['user_confirmed']}"
                  + ("（沿用上次确认）" if carried and not confirm else ""))
            if not stamp["user_confirmed"]:
                print("→ 只允许出矢量；把上面骨架表报给用户，用户点头后再跑一次 --confirm，"
                      "否则禁止调用 ImageGen")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
