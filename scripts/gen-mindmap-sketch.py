#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-mindmap-sketch.py — 手绘笔记风导图（纯 SVG，零积分，替代 ImageGen 手绘版）

为什么有它：ImageGen 出的手绘图为了不写错字，只能放 6 个关键词，信息量为 0，
看着像草稿（2026-11-12 用户批评「敷衍 / 浪费积分」）。本脚本改为「矢量画手绘」：
  * 纸张纹理 + 铅笔抖线（feTurbulence + feDisplacementMap）→ 手绘手感
  * 水彩晕染底块 + 纸卡 + 斜贴胶带 → 手账便签质感
  * 信息量与矢量版完全一致：中心论点 + 全部枝与子点，一字不漏、不会写错
  * 不调用任何图像模型，出图成本为 0，可随时重排重出

用法：
  python3 scripts/gen-mindmap-sketch.py scripts/content/outlines/2026-11-12.json --out /tmp/sketch.svg
  # 再截图：chrome --headless --screenshot --window-size=1460,790 --force-device-scale-factor=2
"""
import json
import sys

from html import escape as _esc

# ---------- 配色 ----------
PAPER = "#f7f1e3"
PAPER2 = "#f1e9d7"
INK = "#3f3a30"
INK_SOFT = "#6b6355"
CARD = "#fdfaf1"
WASH = [("#8fa9bd", 0.40), ("#c4936d", 0.36), ("#9b93b3", 0.38)]
CENTER_WASH = ("#d9c49c", 0.45)

FONT_CN = "Hiragino Sans GB, STHeiti, Heiti SC, PingFang SC, sans-serif"
FONT_HAND = "Bradley Hand, Noteworthy, Chalkboard SE, " + FONT_CN


def esc(s):
    return _esc(str(s), quote=True)


def defs():
    return f"""<defs>
 <style>
  .sk-cn{{font-family:"Hiragino Sans GB","STHeiti","Heiti SC","PingFang SC",sans-serif}}
  .sk-hand{{font-family:"Bradley Hand","Noteworthy","Chalkboard SE","Hiragino Sans GB",sans-serif}}
 </style>
 <filter id="rough" x="-8%" y="-8%" width="116%" height="116%">
  <feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="3" seed="11" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G"/>
 </filter>
 <filter id="rough2" x="-10%" y="-10%" width="120%" height="120%">
  <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="4" seed="5" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="4.5" xChannelSelector="R" yChannelSelector="G"/>
 </filter>
 <filter id="grain" x="0%" y="0%" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="4" seed="3"/>
  <feColorMatrix type="saturate" values="0"/>
  <feComponentTransfer><feFuncA type="linear" slope="0.11"/></feComponentTransfer>
 </filter>
 <filter id="washblur"><feGaussianBlur stdDeviation="2.2"/></filter>
 <marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7"
   orient="auto-start-reverse" markerUnits="strokeWidth">
  <path d="M1,1.6 L8.6,5 L1.2,8.6" fill="none" stroke="{INK}" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round"/>
 </marker>
</defs>"""


def paper(w, h):
    return (f'<rect width="{w}" height="{h}" fill="{PAPER}"/>'
            f'<rect width="{w}" height="{h}" fill="{PAPER2}" filter="url(#grain)" opacity="0.5"/>')


def tape(x, y, w=92, h=26, rot=-4):
    """斜贴的半透明胶带。"""
    return (f'<g transform="translate({x},{y}) rotate({rot})">'
            f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" fill="#e8dcc0" opacity="0.62"/>'
            f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" fill="none" stroke="#d3c3a0" '
            f'stroke-width="0.6" opacity="0.6"/></g>')


def wave_line(x1, y, x2, color=INK_SOFT, sw=1.3, amp=2.2, step=26):
    """手绘波浪下划线。"""
    d = f"M{x1},{y}"
    x = x1
    up = True
    while x < x2 - step:
        x += step
        d += f" Q{x - step/2},{y + (amp if up else -amp)} {x},{y}"
        up = not up
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" filter="url(#rough)"/>')


def doodles():
    """空白处的铅笔涂鸦：星号、螺旋、短线、墨点。"""
    g = []
    # 左上角小星
    g.append('<g stroke="#9a9182" stroke-width="1.1" stroke-linecap="round" fill="none" filter="url(#rough)" opacity="0.75">'
             '<path d="M78,86 l0,-16 M70,78 l16,0 M72.4,71.6 l11.2,11.2 M83.6,71.6 l-11.2,11.2"/></g>')

    # 左下短划线组
    for i, (x, y, w) in enumerate([(84, 690, 54), (96, 704, 38), (84, 718, 62)]):
        g.append(f'<path d="M{x},{y} l{w},{1.5 if i % 2 else -1.5}" stroke="#a89f8d" '
                 f'stroke-width="1.4" stroke-linecap="round" filter="url(#rough)" opacity="0.6"/>')
    # 墨点
    for x, y, r in [(214, 742, 2.4), (120, 566, 1.8), (402, 128, 2.0), (1396, 372, 2.2)]:
        g.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#8b8271" opacity="0.55"/>')
    # 左下角：一支斜放的铅笔（纯手绘线条，不写字）
    g.append('<g transform="translate(158,636) rotate(-34)" filter="url(#rough)">'
             '<path d="M-58,-11 L58,-11 L58,11 L-58,11 Z" fill="#efe0bf" opacity="0.75" '
             'stroke="' + INK + '" stroke-width="1.35"/>'
             '<path d="M58,-11 L84,0 L58,11 Z" fill="#f4e8cf" stroke="' + INK + '" stroke-width="1.35" '
             'stroke-linejoin="round"/>'
             '<path d="M74,-3.4 L84,0 L74,3.4 Z" fill="' + INK + '" opacity="0.85"/>'
             '<path d="M-58,-11 L-74,-11 Q-78,-11 -78,-7 L-78,7 Q-78,11 -74,11 L-58,11 Z" '
             'fill="#d8b7a4" opacity="0.8" stroke="' + INK + '" stroke-width="1.35"/>'
             '<path d="M-58,0 L58,0" stroke="' + INK + '" stroke-width="0.9" opacity="0.45"/>'
             '</g>')
    # 右上角圈线圈
    g.append('<path d="M1232,74 c16,-12 34,-6 36,8 c2,16 -18,24 -30,16 c-10,-7 -4,-22 10,-24" '
             'fill="none" stroke="#a89f8d" stroke-width="1.2" stroke-linecap="round" '
             'filter="url(#rough)" opacity="0.65"/>')
    return "".join(g)


def card(x, y, w, h, title, rng, subs, color, tilt):
    """一张便签：水彩底 + 纸卡 + 胶带 + 标题 + 子点。"""
    fill, alpha = color
    out = [f'<g transform="rotate({tilt} {x + w/2} {y + h/2})">']
    # 水彩晕染：三层错位叠色，模拟笔尖出水与混色
    out.append(f'<rect x="{x-5}" y="{y-4}" width="{w+10}" height="{h+9}" rx="16" '
               f'fill="{fill}" opacity="{alpha}" filter="url(#rough2)"/>')
    out.append(f'<rect x="{x + w*0.55}" y="{y-2}" width="{w*0.42}" height="{h+6}" rx="18" '
               f'fill="{fill}" opacity="{alpha*0.55:.2f}" filter="url(#rough2)"/>')
    out.append(f'<rect x="{x-2}" y="{y-2}" width="{w+4}" height="{h+4}" rx="12" '
               f'fill="{fill}" opacity="{alpha*0.6:.2f}" filter="url(#washblur)"/>')
    # 纸卡
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{CARD}" '
               f'stroke="{INK}" stroke-width="1.35" filter="url(#rough)"/>')
    # 胶带
    out.append(tape(x + 62, y - 4, 96, 25, -5))
    out.append(tape(x + w - 78, y - 3, 76, 22, 6))
    # 标题
    out.append(f'<text x="{x+30}" y="{y+36}" fill="{INK}" font-size="20" font-weight="700" '
               f'class="sk-cn" letter-spacing="1.2">{esc(title)}</text>')
    tw = sum(20.6 if ord(c) > 127 else 11.5 for c in title)
    out.append(wave_line(x + 28, y + 45, x + 32 + tw, color="#8b9a8e", sw=1.6))
    if rng:
        out.append(f'<text x="{x+w-26}" y="{y+34}" text-anchor="end" fill="{INK_SOFT}" '
                   f'font-size="13" class="sk-cn" opacity="0.7">{esc(rng)}</text>')
    # 子点
    ty = y + 78
    for s in subs:
        out.append(f'<circle cx="{x+34}" cy="{ty-5}" r="3" fill="{INK}" opacity="0.8"/>')
        out.append(f'<text x="{x+50}" y="{ty}" fill="{INK}" font-size="16" '
                   f'class="sk-cn">{esc(s)}</text>')
        ty += 33
    out.append('</g>')
    return "".join(out)


def gen(o):
    branches = o.get("branches") or []
    if not branches:
        raise ValueError("branches 不能为空")
    center = o.get("center") or {}

    W = 1300
    card_x, card_w = 540, 720
    hdr, line_h, pad = 78, 33, 24
    gap, top = 56, 62

    heights = [hdr + len(b.get("subs") or []) * line_h + pad for b in branches]
    total = sum(heights) + gap * (len(branches) - 1)
    H = top * 2 + total

    # 中心椭圆位置：取所有卡片纵向中点
    cy = top + total / 2
    cx, rx, ry = 250, 158, 104

    out = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="{esc(o.get("aria", "手绘笔记风思维导图"))}" '
           f'style="width:100%;height:auto">']
    out.append(defs())
    out.append(paper(W, H))
    out.append(doodles())

    # 卡片纵向位置
    ys = []
    y = top
    for h in heights:
        ys.append((y, h))
        y += h + gap

    # 中心 → 卡片 的箭头
    arrow_paths = []
    for i, (y0, h) in enumerate(ys):
        ty = y0 + h / 2
        sx, sy = cx + rx - 6, cy
        ex, ey = card_x - 14, ty
        mx = (sx + ex) / 2
        d = f"M{sx},{sy} C{mx - 20},{sy} {mx + 10},{ey + (0 if i != 1 else 0)} {ex},{ey}"
        arrow_paths.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="1.7" '
                           f'stroke-linecap="round" marker-end="url(#ah)" filter="url(#rough)"/>')
    out.extend(arrow_paths)

    # 结合词（关系词）手写标注
    for i, b in enumerate(branches):
        rel = (b.get("relation") or "").strip()
        if not rel:
            continue
        y0, h = ys[i]
        # 关系词写成「卡片上沿外侧的小批注」：左对齐卡片标题、压在缝隙里，不与箭头相撞
        out.append(f'<g transform="rotate(-2.4 {card_x + 12} {y0 - 14})">'
                   f'<path d="M{card_x + 8},{y0 - 18} l14,-7" stroke="{INK_SOFT}" stroke-width="1.3" '
                   f'fill="none" stroke-linecap="round" marker-end="url(#ah)" filter="url(#rough)"/>'
                   f'<text x="{card_x + 30}" y="{y0 - 16}" fill="{INK_SOFT}" '
                   f'font-size="15" font-style="italic" class="sk-hand">{esc(rel)}</text></g>')

    # 中心块
    cf, ca = CENTER_WASH
    out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx+7}" ry="{ry+6}" fill="{cf}" '
               f'opacity="{ca}" filter="url(#rough2)"/>')
    out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{CARD}" '
               f'stroke="{INK}" stroke-width="1.5" filter="url(#rough)"/>')
    # 外侧再补半圈手绘弧线（不闭合，像草图打底）
    import math as _m
    arc = []
    for k in range(0, 100):
        a = _m.radians(-208 + k * 3.4)
        arc.append((cx + (rx + 13) * _m.cos(a), cy + (ry + 12) * _m.sin(a)))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in arc)
    out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="0.9" '
               f'opacity="0.38" stroke-linecap="round" filter="url(#rough)"/>')
    out.append(f'<text x="{cx}" y="{cy-6}" text-anchor="middle" fill="{INK}" font-size="30" '
               f'font-weight="700" class="sk-cn" letter-spacing="2">'
               f'{esc(center.get("main", ""))}</text>')
    out.append(wave_line(cx - 62, cy + 12, cx + 62, color="#a8935f", sw=1.8))
    out.append(f'<text x="{cx}" y="{cy+42}" text-anchor="middle" fill="{INK_SOFT}" font-size="16" '
               f'class="sk-cn">{esc(center.get("sub", ""))}</text>')

    # 卡片
    tilts = [-1.5, 0.8, -1.1, 0.9]
    for i, b in enumerate(branches):
        y0, h = ys[i]
        out.append(card(card_x, y0, card_w, h, b.get("title", ""), b.get("range", ""),
                        b.get("subs") or [], WASH[i % len(WASH)], tilts[i % len(tilts)]))

    out.append('</svg>')
    return "\n".join(out)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    out_path = '/tmp/mm-sketch.svg'
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1]
        args = [a for a in args if a != out_path]
    if not args:
        print(__doc__)
        return 2
    o = json.load(open(args[0], encoding='utf-8'))
    svg = gen(o)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'written: {out_path} ({len(svg)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
