#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精读页「移动端打印」兜底补丁（幂等）

背景：手机上点打印按钮常常毫无反应，原因是
  1) 微信内置浏览器直接屏蔽 window.print()
  2) 部分手机浏览器 / 内嵌 webview 也不支持

本补丁把 onclick="window.print()" 换成 doPrint()：
  - 微信内  → 提示「··· → 在浏览器打开」的正确路径，不硬调
  - 其他手机 → 先弹出提示条说明备选路径，再调起打印
  - 桌面     → 行为不变

用法：
    python3 patch-print-mobile.py 文件1.html 文件2.html ...
    python3 patch-print-mobile.py --check 文件1.html   # 只看状态
"""

import sys
import os
import io

CSS_ANCHOR = '.print-btn:hover{color:var(--accent);border-color:var(--accent)}'

CSS_BLOCK = CSS_ANCHOR + """

/* ========== 打印提示条：手机 / 微信内兜底 ========== */
.print-tip{
  position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom));
  transform:translate(-50%,10px);
  max-width:min(92vw,460px);width:max-content;
  background:rgba(28,32,38,.94);color:#f5f2ec;
  font-size:13px;line-height:1.6;letter-spacing:.01em;
  padding:10px 14px;border-radius:12px;
  box-shadow:0 8px 24px rgba(0,0,0,.22);
  z-index:9999;opacity:0;pointer-events:none;
  transition:opacity .25s ease,transform .25s ease;
  text-align:center;
}
.print-tip.show{opacity:1;transform:translate(-50%,0)}
@media print{.print-tip{display:none !important}}"""

JS_ANCHOR = '/* ========== 极简原生 JS：折叠 / 搜索高亮 / 面板显隐 ========== */'

JS_BLOCK = JS_ANCHOR + """

/* ========== 打印：桌面直调；微信给引导、其他手机给提示后再调 ========== */
function printTip(msg, ms){
  var old = document.getElementById('print-tip');
  if(old && old.parentNode) old.parentNode.removeChild(old);
  var t = document.createElement('div');
  t.id = 'print-tip';
  t.className = 'print-tip';
  t.textContent = msg;
  document.body.appendChild(t);
  requestAnimationFrame(function(){ t.classList.add('show'); });
  setTimeout(function(){
    t.classList.remove('show');
    setTimeout(function(){ if(t.parentNode) t.parentNode.removeChild(t); }, 300);
  }, ms || 4600);
}

function doPrint(){
  var ua = navigator.userAgent || '';
  var inWX = /MicroMessenger/i.test(ua);
  var mobile = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS/i.test(ua);

  if(inWX){
    printTip('微信内不能直接打印：点右上角 ··· ，选「在浏览器打开」，再用浏览器菜单里的「打印 / 存为 PDF」。', 6200);
    return;
  }
  if(mobile){
    printTip('正在调起打印…若没反应，请用浏览器右上角菜单里的「打印 / 存为 PDF」。', 5200);
    /* 同步调用：iOS Safari 要求打印紧贴用户手势，放进 setTimeout 会失效 */
    try{ window.print(); }catch(e){}
    return;
  }
  try{ window.print(); }
  catch(e){ printTip('当前浏览器没有响应打印，请用浏览器菜单里的「打印 / 存为 PDF」。'); }
}"""

BTN_OLD = 'onclick="window.print()"'
BTN_NEW = 'onclick="doPrint()"'


def read(path):
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, text):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(text)


def patch(path, check_only=False):
    if not os.path.isfile(path):
        return ('skip', '文件不存在：%s' % path)

    src = read(path)
    total = 0

    # 1) 按钮改指向 doPrint()
    n_btn = src.count(BTN_OLD)
    if n_btn:
        src = src.replace(BTN_OLD, BTN_NEW)
        total += n_btn

    # 2) CSS
    if '.print-tip{' not in src:
        if CSS_ANCHOR in src:
            src = src.replace(CSS_ANCHOR, CSS_BLOCK, 1)
            total += 1
        else:
            return ('warn', 'CSS 锚点未找到：%s' % os.path.basename(path))

    # 3) JS
    if 'function doPrint' not in src:
        if JS_ANCHOR in src:
            src = src.replace(JS_ANCHOR, JS_BLOCK, 1)
            total += 1
        else:
            return ('warn', 'JS 锚点未找到：%s' % os.path.basename(path))

    if check_only:
        state = '已打补丁' if ('.print-tip{' in src and 'function doPrint' in src and BTN_OLD not in src) else '未打补丁'
        return ('check', '%s  %s' % (os.path.basename(path), state))

    if total == 0:
        return ('same', '无变化（已是新版）：%s' % os.path.basename(path))

    write(path, src)
    return ('done', '已更新 %d 处：%s' % (total, os.path.basename(path)))


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
