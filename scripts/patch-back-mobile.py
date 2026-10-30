#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch-back-mobile.py —— 手机端「← 返回日历」按钮补丁（幂等）

背景：首页 index.html 在手机窄屏 / iPhone 上点「精读页」不再开弹窗，
而是整页跳到文章独立页（规避 iOS iframe 打印缺陷）。本补丁给文章页
头部加一个仅手机端显示的返回链接，指向站点首页（相对路径 ../../../index.html，
即 articles/YYYY/MM/ 结构下的站点根）。桌面端弹窗预览不受影响。

用法：
  python3 patch-back-mobile.py a.html b.html ...
  python3 patch-back-mobile.py --check a.html

补丁内容：
  1) <div class="meta-row"> 后插入 <a class="back-cal" href="../../../index.html">← 返回日历</a>
  2) </style> 前插入 CSS（默认隐藏，@media max-width:700px 显示；打印与 print-sheet 视图均隐藏）
"""
import io
import os
import sys

LINK_HTML = '  <a class="back-cal" href="../../../index.html">← 返回日历</a>\n'
ANCHOR_HTML = '<div class="meta-row">\n'

CSS_BLOCK = """
/* 手机端：返回日历按钮（桌面为弹窗预览，不显示） */
.back-cal{display:none}
@media (max-width:700px){
  .back-cal{display:inline-block;font-size:12.5px;color:#4a6fa5;text-decoration:none;padding:0 0 6px}
  .back-cal:active{opacity:.55}
}
@media print{.back-cal{display:none !important}}
body.print-sheet .back-cal{display:none !important}
"""

MARK_HTML = 'class="back-cal"'
MARK_CSS = '.back-cal{display:none}'


def read(path):
    with io.open(path, encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, s):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(s)


def process(path, check_only=False):
    src = read(path)

    has_link = MARK_HTML in src
    has_css = MARK_CSS in src
    if check_only:
        return ('ok' if (has_link and has_css) else 'missing',
                'back-cal 链接=%s CSS=%s' % (has_link, has_css))

    if has_link and has_css:
        return ('same', '已是最新：%s' % os.path.basename(path))

    notes = []
    if not has_link:
        i = src.find(ANCHOR_HTML)
        if i < 0:
            return ('skip', '找不到 <div class="meta-row">：%s' % path)
        j = i + len(ANCHOR_HTML)
        src = src[:j] + LINK_HTML + src[j:]
        notes.append('link')

    if not has_css:
        i = src.find('</style>')
        if i < 0:
            return ('skip', '找不到 </style>：%s' % path)
        src = src[:i] + CSS_BLOCK + src[i:]
        notes.append('css')

    write(path, src)
    return ('done', '%s：%s' % ('+'.join(notes), os.path.basename(path)))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    check_only = '--check' in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    for p in args:
        st, msg = process(p, check_only)
        print('[%s] %s' % (st, msg))


if __name__ == '__main__':
    main()
