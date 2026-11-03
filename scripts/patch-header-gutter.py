#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把精读页的左右留白统一放宽：桌面 28px → 36px，手机 16px → 22px。

用户 2026-11-03：「文字离左边框太近了」「右边的打印按钮也有同样问题」。

页头 / 正文容器 / 练习区 三处共用同一条左边缘（header{padding:0 Npx}、
.layout{padding:24px Npx}、.practice{padding:0 Npx 40px}），必须一起改，
否则页头会比正文卡片更靠里、上下对不齐。

用法：
    python3 scripts/patch-header-gutter.py            # 全站 articles/**/*.reading.html
    python3 scripts/patch-header-gutter.py 文件1 …     # 只改指定文件
幂等：已是新值则 0 改动（靠 CSS 注释里的 header-gutter-v4 标记判定）。
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = 'header-gutter-v4'

RULES = [
    # 桌面：页头 / 正文容器 / 练习区
    ('padding:0 28px; /* header-align-v3', 'padding:0 36px; /* ' + MARK),
    ('padding:24px 28px;', 'padding:24px 36px;'),
    ('padding:0 28px 40px;', 'padding:0 36px 40px;'),
    # 手机（≤767 与 ≤700 两个断点）
    ('header{padding:0 16px}', 'header{padding:0 22px}'),
    ('padding:12px 16px 10px', 'padding:12px 22px 10px'),
    ('.layout,.practice{padding-left:16px;padding-right:16px}',
     '.layout,.practice{padding-left:22px;padding-right:22px}'),
]


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'articles/*/*/*.reading.html')))
    changed = skipped = 0
    for f in files:
        s = open(f, encoding='utf-8').read()
        if MARK in s:
            skipped += 1
            continue
        ns = s
        for old, new in RULES:
            ns = ns.replace(old, new)
        if ns == s:
            skipped += 1
            continue
        open(f, 'w', encoding='utf-8').write(ns)
        changed += 1
    print(f'改动 {changed} 个文件，跳过 {skipped} 个')


if __name__ == '__main__':
    main()
