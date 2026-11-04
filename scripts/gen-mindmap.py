#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-mindmap.py — 数据驱动的导图 SVG 生成器（替代「克隆 11-02 再换文字」）。

设计目标：导图结构由文章大纲决定，而非固定 4×3。支持：
  * hub  ：中心块（全文主张）+ N 条分支（章节）向右堆叠，每枝子点数任意；高度自适应。
  * flow ：横向链式（适合时间推进 / 流程类文章），卡片间用箭头连接。
  * 每条分支可带 relation 字段（相对上一条的关系标签，如「因果」「转折」「递进」），
    在 hub 模式中渲染为分支间隙的小字注释，直接体现章节关系。

输入大纲 JSON 结构：
{
  "aria": "……思维导图",
  "pattern": "hub" | "flow",
  "center": {"main": "全文主张", "sub": "副标题"},
  "branches": [
    {"title": "章节名", "range": "¶1–3", "subs": ["要点1", "要点2", "要点3"],
     "relation": "（可选）相对上一章的关系，如 递进/因果/转折/对比"},
    ...
  ]
}

用法：
  python3 scripts/gen-mindmap.py outline.json out.svg
  python3 scripts/gen-mindmap.py --demo /tmp/mm_demo.svg     # 生成一份可变结构示例
"""
import json
import sys
from html import escape as _esc

# 站点既有四色（描边, 浅底, 深字），循环使用
PALETTE = [
    ("#6b8f71", "#e6efe7", "#4c6b52"),  # 绿
    ("#7d98ad", "#e5edf4", "#3d5872"),  # 蓝
    ("#bd7a6d", "#f4e7e4", "#7c4a3e"),  # 砖红
    ("#9b86b3", "#ece4f2", "#5a4670"),  # 紫
]
FONT = ("-apple-system,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif")
CENTER_FILL, CENTER_STROKE = "#eae3d2", "#9a8f76"
TXT_MAIN, TXT_SUB = "#3d3a34", "#5c5648"
REL_FILL = "#8a8578"


def esc(s: str) -> str:
    return _esc(str(s), quote=True)


def _num(x) -> str:
    """整数就不带小数点，避免 '46.0' 之类。"""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    if isinstance(x, float):
        return f"{x:.1f}"
    return str(x)


def gen_hub(o: dict) -> str:
    branches = o.get("branches") or []
    n = len(branches)
    if n == 0:
        raise ValueError("branches 不能为空")

    W = 960
    M = 24
    cx_x, cx_w, cx_h = 24, 176, 88          # 中心块
    hd_x, hd_w, hd_h = 260, 190, 34          # 分支标题
    sd_x = 480                               # 子点起点
    sd_w = W - sd_x - M                      # 456
    sd_h = 32
    pitch = 42                               # 子点行距 = 32 + 10
    gap = 40                                 # 分支之间
    top = bottom = 30

    # 每个分支的“组高”（枝头垂直居中于本组）
    groups = []
    for b in branches:
        k = len(b.get("subs") or [])
        gh = (k * sd_h + (k - 1) * 10) if k > 0 else hd_h
        groups.append((k, gh))

    total = sum(gh for _, gh in groups) + gap * (n - 1)
    H = top + total + bottom
    center_cy = top + total / 2

    # 预排位置
    layout = []
    y = top
    for k, gh in groups:
        header_cy = y + gh / 2
        subs_cy = [y + sd_h / 2 + j * pitch for j in range(k)]
        layout.append({"top": y, "header_cy": header_cy, "subs_cy": subs_cy, "gh": gh, "k": k})
        y += gh + gap

    out = []
    out.append(
        f'<svg viewBox="0 0 {W} {_num(H)}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{esc(o.get("aria", "思维导图"))}" '
        f'style="width:100%;height:auto;font-family:{FONT}">'
    )

    # 中心块
    out.append(f'<rect x="{cx_x}" y="{_num(center_cy - cx_h / 2)}" width="{cx_w}" height="{cx_h}" rx="14" '
               f'fill="{CENTER_FILL}" stroke="{CENTER_STROKE}"/>')
    out.append(f'<text x="{cx_x + cx_w // 2}" y="{_num(center_cy - 8)}" text-anchor="middle" '
               f'fill="{TXT_MAIN}" font-size="17" font-weight="700">{esc(o.get("center", {}).get("main", ""))}</text>')
    out.append(f'<text x="{cx_x + cx_w // 2}" y="{_num(center_cy + 18)}" text-anchor="middle" '
               f'fill="{TXT_SUB}" font-size="12.5">{esc(o.get("center", {}).get("sub", ""))}</text>')

    # 中心 → 各分支 的连线（先画，压在节点下）
    for i, b in enumerate(branches):
        stroke = PALETTE[i % len(PALETTE)][0]
        hcy = layout[i]["header_cy"]
        out.append(f'<path d="M{cx_x + cx_w},{_num(center_cy)} '
                   f'C232,{_num(center_cy)} 232,{_num(hcy)} {hd_x},{_num(hcy)}" '
                   f'stroke="{stroke}" stroke-width="2" fill="none"/>')

    # 分支
    for i, b in enumerate(branches):
        stroke, fill, dark = PALETTE[i % len(PALETTE)]
        L = layout[i]
        hcy = L["header_cy"]
        title = b.get("title", "")
        if b.get("range"):
            title = f'{title}（{b["range"]}）' if "（" not in b.get("range", "") else f'{title}{b["range"]}'
        out.append(f'<g class="mm-branch" data-target="bc{i + 1}">')
        out.append(f'<rect x="{hd_x}" y="{_num(hcy - hd_h / 2)}" width="{hd_w}" height="{hd_h}" rx="8" '
                   f'fill="{fill}" stroke="{stroke}"/>')
        out.append(f'<text x="{hd_x + hd_w // 2}" y="{_num(hcy + 5)}" text-anchor="middle" '
                   f'fill="{dark}" font-size="15" font-weight="700">{esc(title)}</text>')
        out.append(f'<text class="mm-arrow" data-for="bc{i + 1}" x="{hd_x + hd_w - 8}" y="{_num(hcy + 5)}" '
                   f'text-anchor="end" fill="{dark}">▾</text>')
        out.append('</g>')

        out.append(f'<g class="mm-children" id="bc{i + 1}">')
        subs = b.get("subs") or []
        for j, sc in enumerate(L["subs_cy"]):
            out.append(f'<path d="M{hd_x + hd_w},{_num(hcy)} C462,{_num(hcy)} 462,{_num(sc)} {sd_x},{_num(sc)}" '
                       f'stroke="{stroke}" stroke-width="1.5" fill="none"/>')
        for j, (sub, sc) in enumerate(zip(subs, L["subs_cy"])):
            out.append(f'<rect x="{sd_x}" y="{_num(sc - sd_h / 2)}" width="{sd_w}" height="{sd_h}" rx="8" fill="{fill}"/>'
                       f'<text x="{sd_x + 12}" y="{_num(sc + 5)}" fill="{TXT_MAIN}" font-size="14">{esc(sub)}</text>')
        out.append('</g>')

    # 章节关系标签（放在上一组底部与本组顶部之间的空隙）
    for i in range(1, n):
        rel = branches[i].get("relation")
        if not rel:
            continue
        prev_bottom = layout[i - 1]["top"] + layout[i - 1]["gh"]
        this_top = layout[i]["top"]
        ry = (prev_bottom + this_top) / 2 + 4
        out.append(f'<text x="{sd_x + 6}" y="{_num(ry)}" fill="{REL_FILL}" font-size="11.5">↓ {esc(rel)}</text>')

    out.append("</svg>")
    return "\n".join(out)


def gen_flow(o: dict) -> str:
    branches = o.get("branches") or []
    n = len(branches)
    if n == 0:
        raise ValueError("branches 不能为空")

    M = 26
    card_w = int(o.get("card_w", 236))
    gap = int(o.get("gap", 46))              # 卡片间箭头区
    title_h = 40
    line_h = 24
    pad = 14
    maxk = max((len(b.get("subs") or []) for b in branches), default=0)
    card_h = title_h + pad + maxk * line_h + 6
    W = 2 * M + n * card_w + (n - 1) * gap
    H = 2 * M + card_h

    out = []
    out.append(
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{esc(o.get("aria", "思维导图"))}" '
        f'style="width:100%;height:auto;font-family:{FONT}">'
    )
    for i, b in enumerate(branches):
        stroke, fill, dark = PALETTE[i % len(PALETTE)]
        x = M + i * (card_w + gap)
        y = M
        out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="12" fill="{fill}" stroke="{stroke}"/>')
        # 标题
        title = b.get("title", "")
        if b.get("range"):
            title = f'{title}（{b["range"]}）'
        out.append(f'<text x="{x + card_w // 2}" y="{y + 26}" text-anchor="middle" fill="{dark}" '
                   f'font-size="15" font-weight="700">{esc(title)}</text>')
        out.append(f'<line x1="{x + 14}" y1="{y + title_h - 2}" x2="{x + card_w - 14}" y2="{y + title_h - 2}" '
                   f'stroke="{stroke}" stroke-width="1" opacity="0.5"/>')
        # 要点
        for j, sub in enumerate(b.get("subs") or []):
            ty = y + title_h + pad + j * line_h + 16
            out.append(f'<text x="{x + 14}" y="{ty}" fill="{TXT_MAIN}" font-size="12.5">· {esc(sub)}</text>')
        # 箭头
        if i < n - 1:
            ax = x + card_w + gap / 2
            ay = y + card_h / 2
            out.append(f'<text x="{ax}" y="{ay + 6}" text-anchor="middle" fill="#8a8578" font-size="20">→</text>')
            if b.get("relation"):
                out.append(f'<text x="{ax}" y="{ay - 14}" text-anchor="middle" fill="{REL_FILL}" '
                           f'font-size="10.5">{esc(b["relation"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def generate(o: dict) -> str:
    pattern = (o.get("pattern") or "hub").lower()
    if pattern == "flow":
        return gen_flow(o)
    return gen_hub(o)


DEMO = {
    "aria": "德国青年抗议示例思维导图",
    "pattern": "hub",
    "center": {"main": "德国青年抗议", "sub": "30余城·暴力升级"},
    "branches": [
        {"title": "导火索", "range": "¶1–2", "subs": ["多地游行演变为打砸", "警民冲突与逮捕"]},
        {"title": "为何愤怒", "range": "¶3–5", "relation": "因果",
         "subs": ["生活成本与房租高企", "Z 世代组织化抗议", "对建制信任崩塌", "社交媒体放大"]},
        {"title": "当局应对", "range": "¶6–8", "relation": "递进",
         "subs": ["警力部署与定性", "政治人物表态"]},
        {"title": "欧洲连锁", "range": "¶9–10", "relation": "外溢",
         "subs": ["邻国同类抗议", "欧盟层面压力"]},
    ],
}


def _preflight_check(outline: dict) -> list:
    """生图硬闸门（用户 2026-11-04 定）：骨架若像套模板，拒绝生成。

    规则见 scripts/mm-preflight.py 与 MEMORY.md「思维导图硬性流程」。
    返回 FAIL 列表；空列表＝通过。
    """
    fails = []
    branches = outline.get("branches") or []
    n = len(branches)
    subs = [len(b.get("subs") or []) for b in branches]
    if n < 2:
        fails.append(f"只有 {n} 枝：至少 2 枝")
    if n > 6:
        fails.append(f"{n} 枝过多：说明没归并论证层次，回 S2 合并")
    if n in (3, 4) and subs and len(set(subs)) == 1 and subs[0] == 3:
        fails.append(f"疑似模板化：{n} 枝 × 每枝恰好 3 点（{subs}）——枝数/点数必须由原文论证层次得出")
    if n >= 3 and len(set(subs)) == 1:
        fails.append(f"各枝子点数完全相同 {subs}：机械凑数，真实论证各枝不等长（如 2/3/1/2）")
    if n >= 3 and all(not b.get("relation") for b in branches[1:]):
        fails.append("所有枝都没 relation：没有关系链＝目录不是导图，先判关系（对比/转折/递进/因果/解释）")
    for i, b in enumerate(branches, 1):
        t = (b.get("title") or "").strip()
        if not t:
            fails.append(f"第 {i} 枝 title 为空")
        elif len(t) > 7:
            fails.append(f"第 {i} 枝标题「{t}」{len(t)} 字 > 7：矢量卡片会溢出")
        if not (b.get("subs") or []):
            fails.append(f"第 {i} 枝「{t}」没有子点")
    return fails


def main(argv):
    if len(argv) == 3 and argv[1] == "--demo":
        svg = generate(DEMO)
        with open(argv[2], "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"demo written: {argv[2]} ({len(svg)} bytes)")
        return 0
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        return 2
    outline = json.load(open(args[1], encoding="utf-8"))
    fails = _preflight_check(outline)
    if fails and not force:
        print("✗ 生图闸门未通过（骨架像套模板，禁止生成）：")
        for f in fails:
            print("  ✗ " + f)
        print("\n先按 MEMORY.md「思维导图硬性流程」S1–S5 重做骨架：")
        print("  python3 scripts/mm-preflight.py " + args[1] + "   # 看骨架表")
        print("  （确认确实合理才可加 --force 强行生成）")
        return 3
    if fails and force:
        print("⚠ --force：无视闸门强行生成，注意核对骨架是否真由原文得出")
    svg = generate(outline)
    with open(args[2], "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"written: {args[2]} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
