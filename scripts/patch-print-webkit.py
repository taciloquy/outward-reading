#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修 iPhone Safari 打印「第 2 页空白」问题（WebKit 分页加固 v1）。

两处改动，幂等（跑多次只生效一次）：
1) JS：iPhone「打开分享菜单」分支里，分享面板一关就撤 print-sheet 样式，
   会让 Safari 在生成打印预览的过程中回流，分页错位、多出一张空白页。
   改为 only afterprint / 120s 后恢复（页面任何点击也会兜底恢复）。
2) CSS：在样式表末尾追加 @media print 加固块：
   - 把 flex 容器（.layout/.main）全部改块级，避免 WebKit flex 分页 bug
   - 粘性头改 static、去掉 backdrop-filter（这两者在打印里会触发独立渲染层）
   - 非正文块 display:none + 高度归零 + 移出定位
   - 去掉 .headline-block 的 break-after:avoid（高块 avoid 是空白页高发点），
     保留 h1 与 .p-label 的 avoid

用法：
  python3 scripts/patch-print-webkit.py --dry-run articles/2026/10/2026-10-30_001.reading.html
  python3 scripts/patch-print-webkit.py            # 默认处理全站 *.reading.html
"""
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS_MARK = "print-hardened-v1"
JS_MARK = "share-cleanup-safe-v1"

CSS_BLOCK = f"""
/* ===== {CSS_MARK}：WebKit / Safari 打印分页加固，勿删 ===== */
@media print{{
  html,body{{height:auto !important;min-height:0 !important;overflow:visible !important}}
  /* 非正文块彻底移出流：固定定位 / 视口高元素是 Safari 空白页的头号来源 */
  .side,.mindmap,.mm-switch,.mm-legend,.practice,.anchors,.tool-row,.meta,
  .zh-block,.notes-toggle,.notes-group,.print-tip,.pg-mask,.back-cal,.print-btn{{
    display:none !important;position:static !important;
    height:0 !important;min-height:0 !important;max-height:0 !important;
    margin:0 !important;padding:0 !important;border:0 !important;
    overflow:hidden !important;
  }}
  /* flex 容器分页在 WebKit 上不可靠，一律摊成块级文档流 */
  .layout,.main,main,.paragraph,.headline-block,header,section,.en-block{{
    display:block !important;float:none !important;
    width:auto !important;max-width:none !important;
  }}
  header{{
    position:static !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;
  }}
  /* 分页控制：只留低风险的 avoid，高块不 avoid */
  h1{{break-after:avoid !important;page-break-after:avoid !important}}
  .headline-block{{break-after:auto !important;page-break-after:auto !important;
                   break-inside:auto !important;page-break-inside:auto !important}}
  .paragraph,.en-block{{break-inside:auto !important;page-break-inside:auto !important}}
  .p-label{{break-after:avoid !important;page-break-after:avoid !important}}
  p{{orphans:2 !important;widows:2 !important}}
}}
body.print-sheet header{{position:static !important;
  -webkit-backdrop-filter:none !important;backdrop-filter:none !important}}
body.print-sheet .layout,body.print-sheet .main{{display:block !important}}
"""

OLD_JS = """          document.body.classList.add('print-sheet');   /* beforeprint 之外的冗余保险 */
          var cleanup = function(){ document.body.classList.remove('print-sheet'); };
          try{ window.addEventListener('afterprint', cleanup, {once:true}); }catch(e){}
          try{
            var pr = navigator.share({ title: document.title, url: location.href });
            if(pr && pr.then){ pr.then(cleanup, cleanup); }
            else{ setTimeout(cleanup, 90000); }
          }catch(e){ cleanup(); }"""

NEW_JS = """          document.body.classList.add('print-sheet');   /* beforeprint 之外的冗余保险 */
          var sheetDone = false;
          var cleanup = function(){ if(sheetDone) return; sheetDone = true; document.body.classList.remove('print-sheet'); };
          try{ window.addEventListener('afterprint', cleanup, {once:true}); }catch(e){}
          try{
            var pr = navigator.share({ title: document.title, url: location.href });
            /* {mark}：分享面板一关就撤样式，Safari 会在排版打印预览时回流，
               分页错位、多出一张空白页。改成 afterprint 或 120s 后再恢复。 */
            var later = function(){ setTimeout(cleanup, 120000); };
            if(pr && pr.then){ pr.then(later, later); }
            else{ setTimeout(cleanup, 120000); }
          }catch(e){ cleanup(); }""".replace("{mark}", JS_MARK)


def patch(path, dry=False):
    s = open(path, encoding="utf-8").read()
    orig = s
    changed = []

    if CSS_MARK not in s:
        i = s.rfind("</style>")
        if i < 0:
            return None
        s = s[:i] + CSS_BLOCK + s[i:]
        changed.append("css")

    if JS_MARK not in s:
        if OLD_JS in s:
            s = s.replace(OLD_JS, NEW_JS, 1)
            changed.append("js")
        else:
            changed.append("js-miss")

    if s != orig and not dry:
        open(path, "w", encoding="utf-8").write(s)
    return changed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    files = args or sorted(glob.glob(os.path.join(REPO, "articles/**/*.reading.html"), recursive=True))
    stat = {}
    for f in files:
        c = patch(f, dry)
        if c is None:
            print("⚠ 跳过（找不到 </style>）：", f)
            continue
        key = ",".join(c) or "已是最新"
        stat[key] = stat.get(key, 0) + 1
        if c and ("js-miss" in c):
            print("⚠ JS 未匹配（可能已手改）：", os.path.relpath(f, REPO))
    print(("预览模式（未落盘）" if dry else "已处理"), len(files), "个文件：", stat)


if __name__ == "__main__":
    main()
