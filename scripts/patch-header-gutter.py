#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把精读页的左右留白改为随视口缩放。

用户 2026-11-03 两轮反馈：「文字离左边框太近了」「右边的打印按钮也有同样问题」
「桌面效果还是紧紧贴着」。固定 36px 在中窄窗口（900–1300px）仍显得贴边，改为：

    桌面：clamp(36px, 5vw, 80px)    900px 窗≈45px、1200px≈60px、1440px≈72px
    窄屏：clamp(24px, 5.5vw, 40px)  手机 390px≈24px、平板 767px≈40px

页头 / 正文容器 / 练习区 三处共用同一条左边缘（header{padding:0 N}、
.layout{padding:24px N}、.practice{padding:0 N 40px}），必须一起改，
否则页头会比正文卡片更靠里、上下对不齐。

用法：
    python3 scripts/patch-header-gutter.py            # 全站 articles/**/*.reading.html
    python3 scripts/patch-header-gutter.py 文件1 …     # 只改指定文件
幂等：替换是「旧值 → 新值」的字符串级操作，已改过的页面 0 改动。
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = 'header-gutter-v5'
CLAMP = 'clamp(36px,5vw,80px)'
MCLAMP = 'clamp(24px,5.5vw,40px)'

RULES = [
    # 桌面：页头 / 正文容器 / 练习区（v4 的 36px → clamp）
    ('padding:0 36px; /* header-gutter-v4：可见栏占满内容区整宽，左缘对正文、右缘对查询面板 */',
     'padding:0 ' + CLAMP + '; /* ' + MARK + '：可见栏占满内容区整宽，左缘对正文、右缘对查询面板 */'),
    ('padding:24px 36px;', 'padding:24px ' + CLAMP + ';'),
    ('padding:0 36px 40px;', 'padding:0 ' + CLAMP + ' 40px;'),
    # 少数页面还停在 v3（28px），一并兜住
    ('padding:0 28px; /* header-align-v3', 'padding:0 ' + CLAMP + '; /* ' + MARK),
    ('padding:24px 28px;', 'padding:24px ' + CLAMP + ';'),
    ('padding:0 28px 40px;', 'padding:0 ' + CLAMP + ' 40px;'),
    # 窄屏（≤767 / ≤700）：固定 22px → 24–40px 自适应，
    # 桌面上的窄窗口、预览面板也会落到这个断点，固定 22px 同样显得贴边
    ('header{padding:0 22px}', 'header{padding:0 ' + MCLAMP + '}'),
    ('padding:12px 22px 10px', 'padding:12px ' + MCLAMP + ' 10px'),
    ('.layout,.practice{padding-left:22px;padding-right:22px}',
     '.layout,.practice{padding-left:' + MCLAMP + ';padding-right:' + MCLAMP + '}'),
]


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'articles/*/*/*.reading.html')))
    changed = skipped = 0
    for f in files:
        s = open(f, encoding='utf-8').read()
        ns = s
        for old, new in RULES:
            ns = ns.replace(old, new)
        if ns == s:
            skipped += 1
            continue
        open(f, 'w', encoding='utf-8').write(ns)
        changed += 1
    print(f'改动 {changed} 个文件，跳过 {skipped} 个（已是最新值）')


if __name__ == '__main__':
    main()
