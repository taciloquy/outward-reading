#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打印 v4：
1) body.print-sheet「打印视图」普通规则兜底（不依赖 @media print，iOS 分享菜单打印也生效）
   挂在 beforeprint / afterprint 上，任何打印入口都会切到干净视图、打完恢复。
2) doPrint 增加弹窗（iframe）内拦截：手机上在首页弹窗里打印会把首页日历一起印出来，
   改为引导卡「复制精读页链接 → Safari 独立打开 → 再打印」。
3) iPhone 分享菜单主按钮点击时预先挂 print-sheet（beforeprint 之外的冗余保险）。
幂等：所有插入都以唯一锚点判断，重复执行无变化。--check 只查状态。
"""
import io, os, sys

SHEET_CSS = """
/* ========== 打印视图兜底：body.print-sheet（普通规则，任何 WebKit 都生效） ========== */
body.print-sheet{background:#fff !important;margin:0 !important;padding:0 !important}
body.print-sheet .layout{display:block !important}
body.print-sheet .side,body.print-sheet .mindmap,body.print-sheet .practice,
body.print-sheet .zh-block,body.print-sheet .notes-toggle,body.print-sheet .notes-group,
body.print-sheet .mm-switch,body.print-sheet .anchors,body.print-sheet .tool-row,
body.print-sheet .meta,body.print-sheet .print-tip,body.print-sheet .pg-mask{display:none !important}
body.print-sheet .meta-row{display:block !important}
body.print-sheet .main{width:100% !important;max-width:100% !important;margin:0 !important;padding:0 !important}
body.print-sheet header,body.print-sheet .headline-block{background:none !important;border:none !important;box-shadow:none !important;padding:0 0 6mm !important}
body.print-sheet .paragraph{background:none !important;border:none !important;border-radius:0 !important;box-shadow:none !important;padding:0 0 4mm !important;color:#000 !important}
body.print-sheet .paragraph .en-block{font-size:11.5pt !important;line-height:1.75 !important;color:#000 !important}
body.print-sheet mark,body.print-sheet mark.voc{background:none !important;color:inherit !important}
body.print-sheet .p-label{color:#555 !important}
"""

HOOK_JS = """
/* ========== 打印视图兜底：任何入口打印前切到 print-sheet 视图，打完恢复 ========== */
window.addEventListener('beforeprint', function(){ document.body.classList.add('print-sheet'); });
window.addEventListener('afterprint', function(){ document.body.classList.remove('print-sheet'); });
"""

SAFETY_JS = """/* print-sheet-safety：万一浏览器不触发 afterprint，用户再碰页面就自动恢复 */
document.addEventListener('pointerdown', function(){ document.body.classList.remove('print-sheet'); }, true);
"""

INFRAME_JS = """  /* 0) 首页弹窗（iframe）里：打印的是外层首页（日历+弹窗叠加），必须先去独立页面 */
  var inFrame = false;
  try{ inFrame = (window.self !== window.top); }catch(e){ inFrame = true; }
  if(inFrame && (inWX || isIPhone || isIPad || isAndroid || isHarmony)){
    openPrintGuide({
      title: '先去独立页面再打印',
      desc: '你现在是在首页的弹窗里看这篇精读页，在这里打印会把首页的日历一起印出来。',
      steps: [
        '点下面的「复制精读页链接」',
        '粘到 Safari 打开（独立完整页面）',
        '再点一次「🖨 打印」，按提示操作'
      ],
      primaryLabel: '复制精读页链接',
      primaryAction: copyPageLink
    });
    return;
  }

"""

OLD_IPHONE_ACTION = """        primaryAction: function(){
          try{
            navigator.share({ title: document.title, url: location.href });
          }catch(e){}
        }"""

NEW_IPHONE_ACTION = """        primaryAction: function(){
          document.body.classList.add('print-sheet');   /* beforeprint 之外的冗余保险 */
          var cleanup = function(){ document.body.classList.remove('print-sheet'); };
          try{ window.addEventListener('afterprint', cleanup, {once:true}); }catch(e){}
          try{
            var pr = navigator.share({ title: document.title, url: location.href });
            if(pr && pr.then){ pr.then(cleanup, cleanup); }
            else{ setTimeout(cleanup, 90000); }
          }catch(e){ cleanup(); }
        }"""


def read(p):
    with io.open(p, encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(s)


def do_file(path, check_only=False):
    src = read(path)
    orig = src
    notes = []

    # 1) CSS：插到 </style> 前
    if 'body.print-sheet{' not in src:
        i = src.find('</style>')
        if i < 0:
            return ('skip', '找不到 </style>：%s' % path)
        src = src[:i] + SHEET_CSS + src[i:]
        notes.append('css')

    # 2) beforeprint/afterprint 钩子：插到 doPrint 函数前
    if "addEventListener('beforeprint'" not in src:
        i = src.find('function doPrint')
        if i < 0:
            return ('skip', '找不到 doPrint：%s' % path)
        src = src[:i] + HOOK_JS.strip() + '\n\n' + src[i:]
        notes.append('hook')

    # 2b) 恢复兜底：afterprint 可能不触发
    if 'print-sheet-safety' not in src:
        anchor = "window.addEventListener('afterprint', function(){ document.body.classList.remove('print-sheet'); });"
        i = src.find(anchor)
        if i < 0:
            return ('skip', '找不到 afterprint 钩子：%s' % path)
        j = i + len(anchor)
        src = src[:j] + '\n' + SAFETY_JS.rstrip('\n') + src[j:]
        notes.append('safety')

    # 3) iframe 拦截：插到 isHarmony 变量行后
    if 'var inFrame = false;' not in src:
        anchor = 'var isHarmony = /HarmonyOS/i.test(ua);'
        i = src.find(anchor)
        if i < 0:
            return ('skip', '找不到 doPrint UA 变量区：%s' % path)
        j = i + len(anchor)
        src = src[:j] + '\n' + INFRAME_JS.rstrip('\n') + src[j:]
        notes.append('iframe')

    # 4) iPhone 主按钮：预先挂 print-sheet
    if OLD_IPHONE_ACTION in src:
        src = src.replace(OLD_IPHONE_ACTION, NEW_IPHONE_ACTION, 1)
        notes.append('share')

    if src == orig:
        return ('same', '无变化（已是 v4）：%s' % os.path.basename(path))
    if check_only:
        return ('pending', '待更新 %s：%s' % ('+'.join(notes), os.path.basename(path)))
    write(path, src)
    return ('done', '已更新 %s：%s' % ('+'.join(notes), os.path.basename(path)))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    check_only = '--check' in sys.argv
    if not args:
        print('用法: patch-print-sheet.py [--check] 文件1.html 文件2.html …')
        sys.exit(1)
    for p in args:
        st, msg = do_file(p, check_only)
        print('[%s] %s' % (st, msg))


if __name__ == '__main__':
    main()
