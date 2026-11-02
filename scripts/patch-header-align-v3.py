#!/usr/bin/env python3
"""
header-align-v3
================
把顶部可见白栏的右缘，从「正文右缘」改到「查询面板（右侧栏）右缘」，
即占满 .layout 内容区整宽（与 header 内容区同宽：左缘=正文左缘 288@1920，
右缘=查询面板右缘 1632@1920）。

背景：
  v1：header 限 1400px 整条 → 用户嫌太宽。
  v2：.head-inner 限为 正文列宽（calc(100% - var(--side-w) - 24px)）→ 左对正文、右也停在正文右缘。
  v3：.head-inner 改为 max-width:100% → 左缘不变（正文左缘），右缘拉到查询面板右缘。

因为 header 与 .layout 都是 max-width:1400px;margin:0 auto;padding:28px(横向)，
两者内容区完全同宽同位置；.side 又是 .layout 最右 flex 子项，所以 100% 即对齐查询面板右缘。

幂等：已含 header-align-v3 标记则跳过。
打印态：print-sheet .head-inner 与 @media print header .head-inner 已重置，不受影响。
"""
import os, glob, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(glob.glob(os.path.join(ROOT, "articles", "**", "*.reading.html"), recursive=True))

OLD_CALC = "max-width:calc(100% - var(--side-w) - 24px);"
NEW_CALC = "max-width:100%;"

OLD_COMMENT = "padding:0 28px; /* header-align-v2：可见栏收窄到正文列，白底移到 .head-inner */"
NEW_COMMENT = "padding:0 28px; /* header-align-v3：可见栏占满内容区整宽，左缘对正文、右缘对查询面板 */"

OLD_SIDEW = "--side-w: clamp(288px,30%,404px); /* 侧栏宽度；顶部栏据此对齐正文列 */"
NEW_SIDEW = "--side-w: clamp(288px,30%,404px); /* 侧栏宽度 */"

def patch_file(path, dry=False):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "header-align-v3" in s:
        return "skip"
    if OLD_CALC not in s:
        # 可能是 v1 或其他状态，跳过避免误伤
        return "nomatch"
    if dry:
        return "would-patch"
    s = s.replace(OLD_COMMENT, NEW_COMMENT)
    s = s.replace(OLD_CALC, NEW_CALC)
    s = s.replace(OLD_SIDEW, NEW_SIDEW)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return "patched"

def main():
    dry = "--check" in sys.argv
    targets = PAGES
    if len(sys.argv) > 1 and sys.argv[1] not in ("--check",):
        targets = [sys.argv[1]]
    patched = skip = nomatch = 0
    for p in targets:
        r = patch_file(p, dry=dry)
        if r == "patched": patched += 1
        elif r == "skip": skip += 1
        elif r == "nomatch": nomatch += 1
        if dry and r == "would-patch":
            patched += 1
            print("WOULD PATCH:", os.path.relpath(p, ROOT))
    if dry:
        print(f"[check] would-patch={patched} skip(already v3)={skip} nomatch={nomatch}")
    else:
        print(f"[done] patched={patched} skip={skip} nomatch={nomatch}")

if __name__ == "__main__":
    main()
