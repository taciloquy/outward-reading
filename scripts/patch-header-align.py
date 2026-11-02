#!/usr/bin/env python3
"""
patch-header-align.py  —  顶部标题栏/按钮/打印区与正文列对齐（header-align-v1）

问题：
  header 是 <body> 直接子元素且只有 padding，没有 max-width，宽屏下整条标题栏
  跟着页面宽度铺开；而正文 .layout / .practice 都被 max-width:1400px;margin:0 auto
  约束成居中列。于是顶部标题、锚点按钮、打印按钮和下方正文左右对不齐。

修复：
  给基础 header 规则（position:sticky; top:0; z-index:60 那条）补上
  max-width:1400px;margin:0 auto，与 .layout / .practice 完全同宽同居中，
  水平 padding 也都是 28px，因此标题/按钮/打印按钮与正文左、右边缘精确对齐。

打印安全：
  @media print 与 body.print-sheet 已把 header 设为 max-width:none / margin:0，
  本补丁不影响打印（仍 2 页、按钮不打印）。移动端 <767px 远低于 1400，约束自动失效。

幂等：已含 marker 'header-align-v1' 的文件跳过。
用法：
  python3 scripts/patch-header-align.py [文件 ...]   # 缺省扫描 articles/**/*.reading.html
  --check   只统计状态不写入
"""
import os, re, sys, glob

MARKER = "header-align-v1"
# 只匹配「基础 header 规则」：紧跟 position:sticky; top:0; z-index:60;
HEADER_RE = re.compile(r"(header\{\s*position:sticky; top:0; z-index:60;\n)")

def patch_file(path, check=False):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if MARKER in s:
        return "skip"
    m = HEADER_RE.search(s)
    if not m:
        return "nomatch"
    if check:
        return "would-patch"
    inject = m.group(1) + "  max-width:1400px;margin:0 auto; /* {} */\n".format(MARKER)
    s = s[:m.start()] + inject + s[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return "patched"

def main():
    check = "--check" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--check"]
    files = args if args else glob.glob("articles/**/*.reading.html", recursive=True)
    if not files:
        print("no reading html found (run from repo root)")
        sys.exit(2)
    c = {"patched":0,"skip":0,"nomatch":0,"would-patch":0}
    for p in files:
        r = patch_file(p, check=check)
        c[r] = c.get(r,0)+1
        if not check:
            print("{:12} {}".format(r, p))
    print("---")
    print(("CHECK " if check else "") + "summary: " + ", ".join("{}={}".format(k,v) for k,v in c.items()))

if __name__ == "__main__":
    main()
