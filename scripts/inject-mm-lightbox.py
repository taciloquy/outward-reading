#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给精读页注入「手绘导图点击放大」浮层（手机上手绘图缩到 ~340px，字太小）。

片段唯一来源：scripts/assets/mm-lightbox.html —— 构建器与新页面共用同一份，
避免两处代码漂移。

用法：
  python3 scripts/inject-mm-lightbox.py            # 处理所有精读页
  python3 scripts/inject-mm-lightbox.py 2026-11-03 # 只处理某一天

幂等：已有则整块替换（片段更新后重跑即可升级）；无手绘图的页面跳过。
"""
import os
import re
import sys
import glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNIPPET = os.path.join(REPO, "scripts/assets/mm-lightbox.html")

# 整块：<style id="mm-lb-css"> … <script id="mm-lb-js">…</script>
BLOCK_RE = re.compile(
    r'<style id="mm-lb-css">.*?<script id="mm-lb-js">.*?</script>', re.S)
HAS_IMG_RE = re.compile(
    r'id="mm-image"[^>]*>\s*<img src="data:image/jpeg;base64,([A-Za-z0-9+/=]*)', re.S)
MM_SECTION = '<section class="mindmap" id="mindmap">'


def inject(html, block):
    """返回 (新 html, 是否改动)"""
    m = HAS_IMG_RE.search(html)
    if not m or len(m.group(1)) < 1000:
        return html, False                     # 没有手绘图，不需要放大

    if BLOCK_RE.search(html):                  # 已注入：整块替换（升级片段）
        new = BLOCK_RE.sub(lambda _: block, html, count=1)
        return new, new != html

    i = html.find(MM_SECTION)                  # 首次注入：放在导图 section 之后
    if i < 0:
        return html, False
    j = html.find('</section>', i)
    if j < 0:
        return html, False
    j += len('</section>')
    new = html[:j] + '\n' + block + html[j:]
    return new, True


def main():
    if not os.path.exists(SNIPPET):
        sys.exit(f'✗ 找不到片段文件：{SNIPPET}')
    block = open(SNIPPET, encoding='utf-8').read().strip()

    if len(sys.argv) > 1:
        day = sys.argv[1]
        files = sorted(glob.glob(f'articles/*/*/{day}*.reading.html'))
    else:
        files = sorted(glob.glob('articles/*/*/*.reading.html'))

    if not files:
        sys.exit('没有找到目标页面')

    changed = replaced = skipped = 0
    for f in files:
        html = open(f, encoding='utf-8').read()
        before = BLOCK_RE.search(html) is not None
        new, ok = inject(html, block)
        if ok:
            open(f, 'w', encoding='utf-8').write(new)
            if before:
                replaced += 1
            else:
                changed += 1
        else:
            skipped += 1
    print(f'新增 {changed} 页 | 升级 {replaced} 页 | 跳过 {skipped} 页（无手绘图或已是最新）')


if __name__ == '__main__':
    main()
