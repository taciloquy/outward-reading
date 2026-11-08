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
  F1 枝数 2–4（2026-11-08 用户定：超过 4 枝的骨架不提交给用户），且不是模板形状
  F2 各枝子点数量不得齐平（齐平＝机械凑数，禁止）
  F3 第 2 枝起必须有 relation，关系链不许有断点
  F4 每枝必须有 range（段落依据）与 title
  F5 分支标题 ≤7 字（矢量卡片 190px 装不下更长的，会溢出）
  F6 center 必须有 main + sub
  F7 逻辑性：relation 不得是无逻辑信息的泛词（然后/接着/同时…），也不得全程重复
      （2026-11-08 用户强调「要有逻辑性」：枝与枝之间必须能连成一条论证主线）
  F8 range 必须按原文顺序递进且不重叠：骨架按论证层次搭，不许乱序拼贴段落
"""
import json
import os
import re
import sys
import time

MAX_TITLE = 7
MAX_BRANCHES = 4          # 2026-11-08 用户定：主干骨架超过 4 枝不提交
WEAK_RELATIONS = {
    "然后", "接着", "以及", "另外", "同时", "其次", "再者", "最后", "继续",
    "此外", "还有", "其它", "其他", "下一步", "以下", "接下来", "下一个",
    "一是", "二是", "三是", "首先", "again", "then", "also", "next",
}
RANGE_RE = re.compile(r"¶?\s*(\d+)\s*(?:[-–—~]\s*(\d+))?")
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
    if n > MAX_BRANCHES:
        fail(f"{n} 枝过多：用户 2026-11-08 定规矩「主干骨架超过 {MAX_BRANCHES} 枝不要提交」，"
             f"回 S2 把同层论证合并，别按段落平铺")

    subs_counts = [len(b.get("subs") or []) for b in branches]

    # F1b 模板形状（4 枝 / 3 枝 × 每枝 3 点）
    if n in (3, 4) and subs_counts and len(set(subs_counts)) == 1 and subs_counts[0] == 3:
        fail(f"疑似模板化：{n} 枝 × 每枝恰好 3 点（{subs_counts}）。枝数/点数必须由原文论证层次得出，回 S1 重做")

    # F2 子点齐平
    if n >= 3 and len(set(subs_counts)) == 1:
        fail(f"各枝子点数完全相同 {subs_counts}：属于机械凑数，真实论证各枝长度不等（如 2/3/1/2）")

    # F3 关系链：第 2 枝起每枝都要有 relation，断点即不合格
    missing_rel = [i + 1 for i, b in enumerate(branches) if i > 0 and not b.get("relation")]
    if missing_rel:
        fail(f"第 {missing_rel} 枝缺 relation：关系链有断点就等于目录，先在 S3 判清"
             f"枝与枝之间的因果/转折/递进关系（用户 2026-11-08 强调逻辑性）")

    # F7 逻辑性：relation 必须承载逻辑信息，且不能全程复用同一个词
    rels = [(b.get("relation") or "").strip() for b in branches[1:]]
    weak = [(i + 2, r) for i, r in enumerate(rels) if r and r.lower() in WEAK_RELATIONS]
    if weak:
        fail(f"relation 是无逻辑信息的泛词 {weak}：换成能说明推进方向的词"
             f"（为何／因此／但／于是／反而），别只标顺序")
    if len(rels) >= 2 and all(rels) and len(set(rels)) == 1:
        fail(f"所有 relation 都是「{rels[0]}」：层次没有推进，等于按段落平铺，回 S2 重判论证关系")

    # F8 range 顺序：按原文递进、不重叠，保证骨架真按论证层次搭
    spans = []
    for i, b in enumerate(branches, 1):
        m = RANGE_RE.search(b.get("range") or "")
        if m:
            a = int(m.group(1))
            z = int(m.group(2) or m.group(1))
            spans.append((i, a, z))
    if len(spans) != n:
        warn("有 range 解析不出段落数字：建议统一写成 ¶1-4 这样的格式，便于复核顺序")
    else:
        for k in range(1, len(spans)):
            prev_i, prev_a, prev_z = spans[k - 1]
            cur_i, cur_a, cur_z = spans[k]
            if cur_a <= prev_a:
                fail(f"第 {cur_i} 枝 range 起点 {cur_a} 未晚于第 {prev_i} 枝 {prev_a}："
                     f"骨架不是按原文顺序推进的，回 S2 重排")
            if cur_a <= prev_z:
                fail(f"第 {cur_i} 枝 range 与第 {prev_i} 枝重叠（{prev_a}-{prev_z} / "
                     f"{cur_a}-{cur_z}）：同一段内容被拆进两枝，逻辑层级没分清")
        if spans[0][1] != 1:
            warn(f"第 1 枝从 ¶{spans[0][1]} 起：确认开头段落是否被漏掉")

    # 论证主线（2026-11-08 用户要求逻辑性）：建议显式写一句，便于复核
    if not (o.get("logic") or "").strip():
        warn("缺 logic 一句话论证主线：建议写明「现象 → 为何 → 结果」这类能讲通的主线")

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
        if (o.get("logic") or "").strip():
            print(f"论证主线：{o['logic'].strip()}")
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
