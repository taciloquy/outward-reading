#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把手绘版思维导图（AI 生成的 PNG/JPG）处理并内嵌进精读页 HTML。

处理步骤：
  1) 自动识别并抹掉右下角的 AI 水印（用邻近干净纸纹做羽化补丁，不改变画风）；
  2) 等比缩到宽 1280，导出 JPEG(q80)，压到 ~150KB；
  3) base64 内嵌，补上「手绘版」切换按钮，写进 <div id="mm-image">。

用法：
  python3 embed-handmap.py <精读页.html> <手绘图.png|jpg>
  python3 embed-handmap.py <精读页.html> <手绘图.png> --wm-box 1415,948,1536,1024
  python3 embed-handmap.py <精读页.html> <手绘图.png> --no-watermark   # 图本来就干净

依赖：Pillow、numpy（pip3 install pillow numpy）
"""

import base64
import io
import os
import re
import sys

import numpy as np
from PIL import Image, ImageFilter

TARGET_W = 1280
JPEG_Q = 80


# ---------- 1. 去水印 ---------------------------------------------------------
def _clean_source_patch(a, W, H, avoid_box, tgt_mean):
    """在整图里找一个最干净（边缘能量最低、颜色最接近）的同尺寸纸纹块。"""
    h, w, _ = a.shape
    gray = np.asarray(Image.fromarray(a.astype(np.uint8)).convert("L")
                      .filter(ImageFilter.FIND_EDGES)).astype(np.float32)
    best = None
    ax0, ay0, ax1, ay1 = avoid_box
    for yy in range(0, max(1, h - H - 1), 8):
        for xx in range(0, max(1, w - W - 1), 8):
            if xx + W > ax0 - 12 and xx < ax1 and yy + H > ay0 - 12 and yy < ay1:
                continue                      # 别把要修的地方自己当补丁源
            e = gray[yy:yy + H, xx:xx + W].mean()
            m = a[yy:yy + H, xx:xx + W].reshape(-1, 3).mean(axis=0)
            score = e + np.abs(m - tgt_mean).mean() * 0.6
            if best is None or score < best[0]:
                best = (score, xx, yy)
    _, sx, sy = best
    src = a[sy:sy + H, sx:sx + W].copy()
    # 尺寸不够就平铺
    if src.shape[0] != H or src.shape[1] != W:
        src = np.tile(src, (H // src.shape[0] + 1, W // src.shape[1] + 1, 1))[:H, :W]
    return src


def remove_watermark(im, wm_box=None):
    """抹掉右下角水印（只处理水印笔画本身，不动画面），返回新图。

    wm_box=(x0,y0,x1,y1) 可手动指定搜索范围；默认识别右下角。
    做法：检测近白色低饱和笔画 → 膨胀 → 只在蒙版内做扩散填充（颜色来自周围纸面）
         → 再从干净纸面借一层高频纹理，避免出现一块「过于光滑」的补丁。
    """
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape

    if wm_box is None:
        # 水印只出现在右下角：搜索范围钉在角落，避免把浅色插画（旗子、云朵）误判
        rx0, ry0 = int(w * 0.86), int(h * 0.86)
        note = "自动识别"
    else:
        rx0, ry0 = int(wm_box[0]), int(wm_box[1])
        note = "手动指定"

    sub = a[ry0:, rx0:]
    b = sub.mean(axis=2)
    sat = sub.max(axis=2) - sub.min(axis=2)
    paper = float(np.median(b))
    m = (b > paper + 18) & (sat < 40)
    if m.sum() < 80:
        return im, "未发现水印（跳过）"

    # 膨胀，把抗锯齿边缘一起吃掉
    mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    m = np.asarray(mi) > 127

    mask = np.zeros((h, w), bool)
    mask[ry0:, rx0:] = m

    ys, xs = np.nonzero(mask)
    y0, y1 = max(0, ys.min() - 26), min(h, ys.max() + 27)
    x0, x1 = max(0, xs.min() - 26), min(w, xs.max() + 27)
    win = a[y0:y1, x0:x1].copy()
    mwin = mask[y0:y1, x0:x1]

    # 扩散填充：只让蒙版内的像素反复取周围模糊值
    fill = win.copy()
    for _ in range(60):
        blur = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
        fill = np.where(mwin[..., None], blur, win)

    # 借一层干净纸面的高频纹理，补回纸纹颗粒
    H, W = y1 - y0, x1 - x0
    src = _clean_source_patch(a, W, H, (x0, y0, x1, y1), win.reshape(-1, 3).mean(axis=0))
    src_low = np.asarray(Image.fromarray(np.clip(src, 0, 255).astype(np.uint8))
                         .filter(ImageFilter.GaussianBlur(10))).astype(np.float32)
    tex = (src - src_low) * 0.95

    # 蒙版羽化，拼接自然
    soft = np.asarray(Image.fromarray((mwin * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[..., None] / 255.0
    out = fill + tex * soft
    a[y0:y1, x0:x1] = np.where(mwin[..., None], out, win)

    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), \
        f"{note}：抹除 {int(mwin.sum())} px（{x0},{y0} → {x1},{y1} 范围内）"


# ---------- 2. 压缩 -----------------------------------------------------------
def to_jpeg_b64(im, target_w=TARGET_W, q=JPEG_Q):
    im = im.convert("RGB")
    if im.width > target_w:
        im = im.resize((target_w, round(im.height * target_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
    raw = buf.getvalue()
    return base64.b64encode(raw).decode(), len(raw)


# ---------- 3. 内嵌 -----------------------------------------------------------
BTN_OLD = ('<button class="mm-btn active" id="mm-vector-btn" '
           'onclick="showMindmap(\'vector\',this)">矢量版</button>')


def embed(html_path, b64, alt):
    s = open(html_path, encoding="utf-8").read()
    img_tag = f'<img src="data:image/jpeg;base64,{b64}" alt="{alt}">'

    # a) 补「手绘版」按钮
    if "手绘版" not in s:
        if BTN_OLD not in s:
            raise SystemExit("✗ 页面里没找到矢量版切换按钮，请确认这是精读页模板")
        s = s.replace(BTN_OLD, BTN_OLD +
                      '\n        <button class="mm-btn" onclick="showMindmap(\'image\',this)">手绘版</button>', 1)

    # b) 写入 / 替换 #mm-image 里的图
    m = re.search(r'(<div class="mm-view" id="mm-image"[^>]*>)(.*?)(</div>)', s, re.S)
    if not m:
        # 还没有这个容器：手动补一段（放在矢量版 </div> 之后）
        raise SystemExit("✗ 页面里没有 <div id=\"mm-image\">，请先按模板加空容器")
    head, body, tail = m.group(1), m.group(2), m.group(3)
    if "<img" in body:
        body = re.sub(r"<img[^>]*>", img_tag, body, count=1)
        action = "替换旧图"
    else:
        body = f'\n        {img_tag}\n      '
        action = "写入新图"

    s = s[:m.start()] + head + body + tail + s[m.end():]
    open(html_path, "w", encoding="utf-8").write(s)
    return action, len(s)


def main():
    args = [a for a in sys.argv[1:]]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    html_path, img_path = args[0], args[1]
    wm_box = None
    no_wm = "--no-watermark" in args
    if "--wm-box" in args:
        raw = args[args.index("--wm-box") + 1]
        wm_box = tuple(int(v) for v in raw.split(","))

    im = Image.open(img_path)
    size0 = im.size
    if no_wm:
        note = "跳过（--no-watermark）"
    else:
        im, note = remove_watermark(im, wm_box)

    b64, raw_len = to_jpeg_b64(im)
    alt = "文章思维导图（手绘版）"
    action, total = embed(html_path, b64, alt)

    print(f"原图      : {size0[0]}×{size0[1]}")
    print(f"去水印    : {note}")
    print(f"内嵌图    : {im.size[0]}×{im.size[1]}, JPEG {raw_len/1024:.0f} KB")
    print(f"页面      : {action}，当前 {total/1024:.0f} KB  →  {os.path.basename(html_path)}")


if __name__ == "__main__":
    main()
