#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精读页「打印样式」升级到 v3（Safari / iOS 兼容 + 桌面更干净），幂等

为什么要改（2026-10-31 实测）：
  1. 原写法把 @page 放在 @media print 里面。Safari 要求 @page 与 @media print
     平级，嵌套时整块 print 样式可能被丢弃 → iPhone 打印出来是「整页缩小 + 侧栏还在」。
  2. Safari 对 print 的权重解析更激进，普通声明容易被屏幕样式覆盖，需 !important。
  3. 段落卡片的边框/圆角/底色没有清掉，桌面 Chrome 打印会印出一圈灰框。
  4. 高亮 mark.voc 只对 .en-block 内生效，标题块里的仍然带底色。

v3 输出：
  @page 顶层 + @media print 全量 !important + 去边框/圆角/底色 + block 布局 +
  -webkit-text-size-adjust:100%（否则 Safari 按视口宽度自动放大字号）。

用法：
    python3 patch-print-css.py 文件1.html 文件2.html ...
    python3 patch-print-css.py --check 文件1.html
"""

import sys
import os
import io

MARK = '/* ========== 打印样式'

NEW_CSS = """/* ========== 打印样式：A4，仅标题 + 英文正文（v3 / Safari 兼容） ========== */
@page{size:A4 portrait;margin:18mm 16mm}

@media print{
  html,body{
    width:auto !important;max-width:none !important;
    margin:0 !important;padding:0 !important;
    background:#fff !important;color:#111 !important;
    -webkit-text-size-adjust:100% !important;text-size-adjust:100% !important;
  }
  /* 一律不打印：导航 / 元信息 / 按钮 / 导图 / 侧栏 / 译文 / 注释 / 练习 / 提示层 */
  .anchors,.meta,.tool-row,.print-btn,.mindmap,.side,.practice,
  .zh-block,.notes-toggle,.notes-group,.mm-switch,
  .print-tip,.pg-mask{display:none !important}
  .meta-row{display:block !important;margin:0 !important}
  header{
    position:static !important;display:block !important;
    background:#fff !important;border:none !important;box-shadow:none !important;
    padding:0 0 6pt !important;margin:0 !important;
  }
  h1{font-size:19pt !important;line-height:1.4 !important;margin:0 0 6pt !important;color:#111 !important}
  .layout{
    display:block !important;max-width:none !important;
    padding:0 !important;margin:0 !important;gap:0 !important;
  }
  .main,main{width:100% !important;max-width:none !important;flex:none !important;min-width:0 !important}
  .paragraph,.headline-block{
    background:#fff !important;border:none !important;border-radius:0 !important;
    box-shadow:none !important;padding:0 !important;margin:0 0 12pt !important;
  }
  .p-label{font-size:8.5pt !important;color:#777 !important;letter-spacing:.06em !important;margin:0 0 3pt !important}
  .en-block{
    background:#fff !important;border:none !important;border-left:2px solid #ccc !important;
    border-radius:0 !important;box-shadow:none !important;
    padding:1pt 0 1pt 8pt !important;
    font-size:10.5pt !important;line-height:1.7 !important;color:#111 !important;
  }
  mark.voc{
    background:transparent !important;border-bottom:none !important;
    padding:0 !important;color:inherit !important;font-weight:600 !important;
  }
  .headline-en{font-size:13pt !important;line-height:1.5 !important;color:#111 !important}
  .headline-sub{font-size:10.5pt !important;color:#444 !important;font-style:italic !important;margin-top:4pt !important}
  h2,h3{page-break-after:avoid}
  a{color:#111 !important;text-decoration:none !important}
}
"""


def read(path):
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, text):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(text)


def find_print_block(src):
    """返回 (start, end) —— 覆盖注释头到 @media print 的闭合大括号"""
    start = src.find(MARK)
    if start < 0:
        return None
    m = src.find('@media print{', start)
    if m < 0:
        return None
    i = src.find('{', m)
    depth = 0
    while i < len(src):
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None


def is_v3(src):
    i = src.find(MARK)
    if i < 0:
        return False
    seg = src[i:i + 400]
    return ('v3 / Safari' in seg) and ('@page{size:A4 portrait;margin:18mm 16mm}' in src)


def patch(path, check_only=False):
    if not os.path.isfile(path):
        return ('skip', '文件不存在：%s' % path)

    src = read(path)

    if check_only:
        return ('check', '%s  %s' % (os.path.basename(path), 'v3 已就位' if is_v3(src) else '仍是旧版'))

    blk = find_print_block(src)
    if not blk:
        return ('warn', '打印样式块未找到：%s' % os.path.basename(path))

    s, e = blk
    tail = src[e:]
    if tail.startswith('\n') and NEW_CSS.endswith('\n'):
        tail = tail[1:]
    new = src[:s] + NEW_CSS + tail
    if new == src:
        return ('same', '无变化（已是 v3）：%s' % os.path.basename(path))
    write(path, new)
    return ('done', '打印样式已升级为 v3：%s' % os.path.basename(path))


def main():
    args = sys.argv[1:]
    check_only = False
    if args and args[0] == '--check':
        check_only = True
        args = args[1:]
    if not args:
        print(__doc__)
        return 1

    ok = True
    for p in args:
        tag, msg = patch(p, check_only)
        print('[%s] %s' % (tag, msg))
        if tag in ('warn', 'skip'):
            ok = False
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
