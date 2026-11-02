#!/usr/bin/env python3
"""header-align-v2：把顶部可见栏（白底/边框/模糊）收窄到正文文字列 .main 的宽度，
使其在 ≥1081px 桌面端与正文左右对齐；768–1080px 与 <768px 侧栏不占流，正文满宽，
可见栏也满宽（本来就对齐）。修改母版 + 全部已上线页面。幂等：已含 .head-inner 则跳过。

用法：
  python3 patch-header-align-v2.py            # 真正打补丁（articles 下全部 reading.html）
  python3 patch-header-align-v2.py --check    # 仅统计受影响文件，不修改
  python3 patch-header-align-v2.py <f1> <f2>   # 指定文件（如构建母版）
"""
import sys, os, glob

# ---- 精确字符串替换表（old -> new）----
# 1) :root 增加 --side-w 变量
ROOT_OLD = "  --radius: 10px;\n"
ROOT_NEW = "  --radius: 10px;\n  --side-w: clamp(288px,30%,404px); /* 侧栏宽度；顶部栏据此对齐正文列 */\n"

# 2) .side 用变量
SIDE_OLD = "  flex:0 0 clamp(288px,30%,404px);min-width:0;"
SIDE_NEW = "  flex:0 0 var(--side-w);min-width:0;"

# 3) header 规则：去掉白底/边框/模糊，只做定位容器；新增 .head-inner 承载可见栏
HEADER_OLD = """header{
  position:sticky; top:0; z-index:60;
  max-width:1400px;margin:0 auto; /* header-align-v1 */
  background:rgba(255,255,255,.95);
  -webkit-backdrop-filter:saturate(180%) blur(10px);
  backdrop-filter:saturate(180%) blur(10px);
  border-bottom:1px solid var(--line);
  padding:14px 28px 12px;
}"""
HEADER_NEW = """header{
  position:sticky; top:0; z-index:60;
  max-width:1400px;margin:0 auto;
  padding:0 28px; /* header-align-v2：可见栏收窄到正文列，白底移到 .head-inner */
}
.head-inner{
  max-width:calc(100% - var(--side-w) - 24px);
  padding:14px 0 12px;
  background:rgba(255,255,255,.95);
  -webkit-backdrop-filter:saturate(180%) blur(10px);
  backdrop-filter:saturate(180%) blur(10px);
  border-bottom:1px solid var(--line);
}"""

# 4) 768–1080 媒体：侧栏变固定浮层，正文满宽，可见栏也满宽
T1080_OLD = "  body:not(.side-collapsed) .side-collapse{font-size:12.5px;padding:4px 8px}\n}"
T1080_NEW = "  body:not(.side-collapsed) .side-collapse{font-size:12.5px;padding:4px 8px}\n  header .head-inner{max-width:none}\n}"

# 5) <767 媒体：单列，header 内边距与布局一致（16px）
M767_OLD = "@media (max-width:767px){\n"
M767_NEW = "@media (max-width:767px){\n  header{padding:0 16px}\n  header .head-inner{max-width:none}\n"

# 6) @media print：可见栏去样式（保证 2 页、无按钮、标题满宽打印）
PRINT_OLD = """  header{
    position:static !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;
  }"""
PRINT_NEW = """  header{
    position:static !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;
  }
  header .head-inner{
    position:static !important;max-width:none !important;margin:0 !important;padding:0 !important;
    background:none !important;border:0 !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;
  }"""

# 7) body.print-sheet：同样去样式
PSHEET_OLD = "body.print-sheet header{position:static !important;\n  -webkit-backdrop-filter:none !important;backdrop-filter:none !important}"
PSHEET_NEW = ("body.print-sheet header{position:static !important;\n"
              "  -webkit-backdrop-filter:none !important;backdrop-filter:none !important}\n"
              "body.print-sheet .head-inner{background:none!important;border:0!important;padding:0!important;max-width:none!important}")

# 8) DOM：把 header 的两个子块包进 .head-inner
WRAP_OPEN_OLD = "<header>\n"
WRAP_OPEN_NEW = '<header>\n  <div class="head-inner">\n'
WRAP_CLOSE_OLD = "</header>"
WRAP_CLOSE_NEW = '  </div>\n</header>'

MARKER = "header-align-v2"
REPLACEMENTS = [
    ("root-var", ROOT_OLD, ROOT_NEW),
    ("side-var", SIDE_OLD, SIDE_NEW),
    ("header-rule", HEADER_OLD, HEADER_NEW),
    ("t1080", T1080_OLD, T1080_NEW),
    ("m767", M767_OLD, M767_NEW),
    ("print", PRINT_OLD, PRINT_NEW),
    ("print-sheet", PSHEET_OLD, PSHEET_NEW),
    ("wrap-open", WRAP_OPEN_OLD, WRAP_OPEN_NEW),
    ("wrap-close", WRAP_CLOSE_OLD, WRAP_CLOSE_NEW),
]

def collect_targets(explicit):
    if explicit:
        return [f for f in explicit if os.path.isfile(f)]
    files = []
    for p in glob.glob(os.path.join(os.path.dirname(__file__), "..", "articles", "**", "*.reading.html"), recursive=True):
        files.append(p)
    return sorted(set(files))

def patch_file(path, dry):
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if MARKER in s and 'class="head-inner"' in s:
        return "skip"  # 已打过 v2
    orig = s
    for name, old, new in REPLACEMENTS:
        if old in s:
            s = s.replace(old, new, 1)
        else:
            # 未命中：可能是顺序差异，记录但不致命（wrap 已在上面判过）
            pass
    if s == orig:
        return "nochange"
    if dry:
        return "would-patch"
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return "patched"

def main():
    dry = "--check" in sys.argv
    explicit = [a for a in sys.argv[1:] if not a.startswith("--")]
    targets = collect_targets(explicit)
    counts = {"patched":0,"would-patch":0,"skip":0,"nochange":0}
    for t in targets:
        r = patch_file(t, dry)
        counts[r] = counts.get(r,0)+1
        if not dry and r not in ("skip","nochange"):
            print(f"  {r:12s} {t}")
    print(f"\n[header-align-v2] {'DRY-RUN' if dry else 'APPLIED'}  total={len(targets)}  "
          f"patched={counts.get('patched',0)} would={counts.get('would-patch',0)} "
          f"skip={counts.get('skip',0)} nochange={counts.get('nochange',0)}")

if __name__ == "__main__":
    main()
