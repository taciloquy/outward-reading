#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch-back-cal.py —— 文章页「← 返回日历」入口补丁（幂等）

背景：首页点文章直接进文章页本体（不再套弹窗），返回靠浏览器返回键 +
文章页顶部这个链接。所以所有宽度都显示，只在打印时隐藏。

用法：
  python3 patch-back-cal.py a.html b.html ...
  python3 patch-back-cal.py --check a.html

补丁内容：
  1) <div class="meta-row"> 后插入 <a class="back-cal" href="../../../index.html">← 返回日历</a>
  2) </style> 前插入 CSS；若存在旧版（仅手机显示）的 .back-cal 块，自动升级为新版
  3) 给已有 back-cal 链接补上 smart-back：若本次是从日历点进来的（referrer 为同源首页），
     点「← 返回日历」改用 history.back()，命中 bfcache 瞬时恢复，避免重新下载解析
     650KB 首页；直接打开文章链接时仍走 href 兜底。
     幂等：onclick 已存在则跳过。注意 onclick 内不能出现 > 或 <（inject-seq-nav.py 用 [^>]* 匹配标签）。
"""
import io
import os
import re
import sys

SMART_ONCLICK = (
    "onclick=\"try{var h=new URL(this.href,location.href),"
    "r=document.referrer?new URL(document.referrer):null,"
    "f=function(p){return p.replace(/index\\.html$/,'').replace(/\\/$/,'')};"
    "if(history.length-1&&r&&r.origin===location.origin&&f(r.pathname)===f(h.pathname))"
    "{event.preventDefault();setTimeout(function(){history.back()},0)}}catch(e){}\""
)

LINK_HTML = '<a class="back-cal" href="../../../index.html" ' + SMART_ONCLICK + '>← 返回日历</a>\n  '
LINK_RE = re.compile(r'<a class="back-cal"([^>]*)>')
ANCHOR_HTML = '<div class="meta-row">'

CSS_NEW = """
/* 返回日历入口：文章页独立打开时（首页点击直达），顶部提供回日历链接 */
.back-cal{display:inline-block;font-size:13px;color:#4a6fa5;text-decoration:none;padding:0 0 8px}
.back-cal:hover{color:#2c4a7c}
.back-cal:active{opacity:.55}
@media print{.back-cal{display:none !important}}
body.print-sheet .back-cal{display:none !important}
"""

CSS_OLD = """
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
MARK_CSS = '.back-cal{display:inline-block;font-size:13px;color:#4a6fa5'


def read(path):
    with io.open(path, encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, s):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(s)


def process(path, check_only=False):
    src = read(path)
    link_m = LINK_RE.search(src)
    has_link = bool(link_m)
    has_smart = bool(link_m and SMART_ONCLICK in link_m.group(1))
    has_new_css = MARK_CSS in src

    if check_only:
        return ('ok' if (has_link and has_smart and has_new_css) else 'missing',
                '链接=%s 智能返回=%s 新版CSS=%s' % (has_link, has_smart, has_new_css))

    if has_link and has_smart and has_new_css:
        return ('same', '已是最新：%s' % os.path.basename(path))

    notes = []
    if not has_link:
        i = src.find(ANCHOR_HTML)
        if i < 0:
            return ('skip', '找不到 <div class="meta-row">：%s' % path)
        src = src[:i] + LINK_HTML + src[i:]
        notes.append('link')
    elif not has_smart:
        # 幂等升级：保留原有 href（含 ?d= 日期），替换旧版 onclick 或追加新版
        attrs = re.sub(r'\s*onclick="[^"]*"', '', link_m.group(1)).rstrip()
        src = (src[:link_m.start()] + '<a class="back-cal"' + attrs + ' ' + SMART_ONCLICK + '>'
               + src[link_m.end():])
        notes.append('smart-back')

    if not has_new_css:
        if CSS_OLD in src:
            src = src.replace(CSS_OLD, CSS_NEW)
            notes.append('css-upgrade')
        else:
            i = src.find('</style>')
            if i < 0:
                return ('skip', '找不到 </style>：%s' % path)
            src = src[:i] + CSS_NEW + src[i:]
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
