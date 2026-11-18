#!/usr/bin/env python3
"""页头内容左右缩进：让 header 内的文字/按钮与下方 headline 卡片对齐。

背景：header 外层有 gutter（clamp(36px,5vw,80px) / 窄屏 clamp(24px,5.5vw,40px)），
但 .head-inner 左右 padding 为 0，导致 h1/返回/锚点贴内容区左缘、pager/打印贴右缘；
而正文 headline 卡片另有 padding:18px 20px（窄屏 14px）。用户要求「两头都不要顶格」。

做法：给 .head-inner 加 padding 20px（窄屏 14px），与 headline 卡片内边距一致。
打印态已有 .head-inner{padding:0 !important}，不受影响，仍为 2 页。

幂等：已打过标记 header-inner-gutter-v1 的文件原样跳过。
    python3 scripts/patch-head-inner-gutter.py           # 全站
    python3 scripts/patch-head-inner-gutter.py 文件1 ...  # 指定文件
"""
import os, re, glob, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = 'header-inner-gutter-v1'
OLD = '.head-inner{\n  max-width:100%;\n  padding:14px 0 12px;'
NEW = ('.head-inner{\n  max-width:100%;\n'
       '  padding:14px 20px 12px; /* ' + MARK +
       '：与 headline 卡片内边距对齐，页头两头不顶格 */')

# 窄屏：headline 卡片是 padding:14px，页头同步缩到 14px
M_OLD = '  .paragraph,.headline-block{padding:14px}\n}'
M_NEW = ('  .paragraph,.headline-block{padding:14px}\n'
         '  header .head-inner{padding:14px}\n}')


def patch(path):
    s = open(path, encoding='utf-8').read()
    if MARK in s:
        return 'skip'
    if OLD not in s or M_OLD not in s:
        return 'MISS'
    s = s.replace(OLD, NEW, 1).replace(M_OLD, M_NEW, 1)
    open(path, 'w', encoding='utf-8').write(s)
    return 'ok'


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'articles/*/*/*.reading.html')))
    stat = {}
    bad = []
    for f in files:
        r = patch(f)
        stat[r] = stat.get(r, 0) + 1
        if r == 'MISS':
            bad.append(f)
    print(dict(stat))
    for f in bad[:10]:
        print('  MISS:', os.path.relpath(f, ROOT))


if __name__ == '__main__':
    main()
