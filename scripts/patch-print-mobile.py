#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精读页「移动端打印」补丁 v2（幂等）

实测结论（2026-10-30）：
  - 桌面 / iPad Safari / Android Chrome：window.print() 正常，直接调即可
  - iPhone Safari：window.print() 静默失败（无任何 UI），只能走系统「分享」菜单里的「打印」
  - 微信内置浏览器：屏蔽 window.print()，必须先「在浏览器打开」

v2 行为：
  - 微信内        → 底部引导卡片：右上角 ··· → 在浏览器打开（附「复制链接」）
  - iPhone Safari → 底部引导卡片：分享菜单 → 打印（附「打开分享菜单」，走 navigator.share）
  - iPad / Android / 鸿蒙 / 桌面 → 直接 window.print()，失败再提示

用法：
    python3 patch-print-mobile.py 文件1.html 文件2.html ...
    python3 patch-print-mobile.py --check 文件1.html
"""

import sys
import os
import io

# ---------------- 片段一：打印提示条（v1 已有，缺失才补） ----------------

CSS_ANCHOR = '.print-btn:hover{color:var(--accent);border-color:var(--accent)}'

CSS_TIP = CSS_ANCHOR + """

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
.print-tip.show{opacity:1;transform:translate(-50%,0)}"""

# ---------------- 片段二：引导卡片（v2 新增） ----------------

CSS_GUIDE_ANCHOR = '.print-tip.show{opacity:1;transform:translate(-50%,0)}'

CSS_GUIDE = CSS_GUIDE_ANCHOR + """

/* ========== 打印引导卡片：iPhone / 微信内 ========== */
.pg-mask{
  position:fixed;inset:0;z-index:10000;
  background:rgba(28,24,20,.44);
  display:flex;align-items:flex-end;justify-content:center;
  opacity:0;transition:opacity .22s ease;
}
.pg-mask.show{opacity:1}
.pg-card{
  width:100%;max-width:480px;
  background:var(--paper,#fbf8f2);color:var(--ink,#2b2622);
  border-radius:18px 18px 0 0;
  padding:20px 20px calc(20px + env(safe-area-inset-bottom));
  box-shadow:0 -10px 34px rgba(0,0,0,.2);
  transform:translateY(16px);transition:transform .26s ease;
  font-family:-apple-system,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
}
.pg-mask.show .pg-card{transform:translateY(0)}
.pg-card h3{margin:0 0 6px;font-size:16px;font-weight:600;letter-spacing:.01em}
.pg-card p{margin:0 0 12px;font-size:13px;line-height:1.7;color:var(--ink-light,#6b6259)}
.pg-card ol{margin:0 0 16px;padding-left:20px;font-size:13.5px;line-height:1.85}
.pg-card ol li{margin-bottom:2px}
.pg-acts{display:flex;gap:10px}
.pg-acts button{
  flex:1;font-size:14px;padding:11px 0;border-radius:10px;cursor:pointer;
  font-family:inherit;-webkit-tap-highlight-color:transparent;
}
.pg-primary{border:1px solid var(--accent,#8a6b4f);background:var(--accent,#8a6b4f);color:#fff}
.pg-ghost{border:1px solid var(--line,#e2dad0);background:transparent;color:var(--ink-light,#6b6259)}"""

MEDIA_OLD = '@media print{.print-tip{display:none !important}}'
MEDIA_NEW = '@media print{.print-tip{display:none !important}.pg-mask{display:none !important}}'

# ---------------- 片段三：JS ----------------

JS_ANCHOR = '/* ========== 极简原生 JS：折叠 / 搜索高亮 / 面板显隐 ========== */'

JS_BLOCK = JS_ANCHOR + """

/* ========== 打印：桌面 / iPad / Android 直调；iPhone 走分享菜单；微信先回浏览器 ========== */
function printTip(msg, ms){
  var old = document.getElementById('print-tip');
  if(old && old.parentNode) old.parentNode.removeChild(old);
  var t = document.createElement('div');
  t.id = 'print-tip';
  t.className = 'print-tip';
  t.textContent = msg;
  document.body.appendChild(t);
  void t.offsetHeight;            /* 强制 reflow：不依赖 rAF，任何环境都能上过渡 */
  t.classList.add('show');
  setTimeout(function(){
    t.classList.remove('show');
    setTimeout(function(){ if(t.parentNode) t.parentNode.removeChild(t); }, 300);
  }, ms || 4600);
}

function legacyCopy(text, cb){
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly','');
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try{ document.execCommand('copy'); }catch(e){}
  document.body.removeChild(ta);
  if(cb) cb();
}

function copyPageLink(){
  var url = location.href;
  var done = function(){ printTip('链接已复制，粘到 Safari 里打开就能打印。', 3200); };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(url).then(done, function(){ legacyCopy(url, done); });
  }else{
    legacyCopy(url, done);
  }
}

function closePrintGuide(){
  var m = document.getElementById('pg-mask');
  if(!m) return;
  m.classList.remove('show');
  setTimeout(function(){ if(m.parentNode) m.parentNode.removeChild(m); }, 240);
}

/* opts: {title, desc, steps:[...], primaryLabel, primaryAction} */
function openPrintGuide(opts){
  closePrintGuide();
  var m = document.createElement('div');
  m.id = 'pg-mask';
  m.className = 'pg-mask';

  var card = document.createElement('div');
  card.className = 'pg-card';

  var h = document.createElement('h3');
  h.textContent = opts.title;
  card.appendChild(h);

  var p = document.createElement('p');
  p.textContent = opts.desc;
  card.appendChild(p);

  var ol = document.createElement('ol');
  (opts.steps || []).forEach(function(s){
    var li = document.createElement('li');
    li.textContent = s;
    ol.appendChild(li);
  });
  card.appendChild(ol);

  var acts = document.createElement('div');
  acts.className = 'pg-acts';
  if(opts.primaryLabel && opts.primaryAction){
    var b1 = document.createElement('button');
    b1.className = 'pg-primary';
    b1.textContent = opts.primaryLabel;
    b1.onclick = function(){ closePrintGuide(); opts.primaryAction(); };
    acts.appendChild(b1);
  }
  var b2 = document.createElement('button');
  b2.className = 'pg-ghost';
  b2.textContent = opts.primaryLabel ? '取消' : '知道了';
  b2.onclick = closePrintGuide;
  acts.appendChild(b2);
  card.appendChild(acts);

  m.appendChild(card);
  document.body.appendChild(m);
  void m.offsetHeight;            /* 强制 reflow：不依赖 rAF */
  m.classList.add('show');
  m.addEventListener('click', function(e){ if(e.target === m) closePrintGuide(); });
}

function doPrint(){
  var ua = navigator.userAgent || '';
  var inWX = /MicroMessenger|WeChat/i.test(ua);
  var isIPhone = /iPhone|iPod/i.test(ua);
  var isIPad = /iPad/i.test(ua) || (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/i.test(ua);
  var isHarmony = /HarmonyOS/i.test(ua);

  /* 1) 微信内置浏览器：打印接口被屏蔽，先请用户回到系统浏览器 */
  if(inWX){
    openPrintGuide({
      title: '微信里打不了印',
      desc: '微信内置浏览器屏蔽了打印功能，换到 Safari 或系统浏览器里打开就能用。',
      steps: [
        '点右上角 ···',
        '选「在默认浏览器打开」（找不到就先把链接复制出来）',
        '在浏览器里再点一次「🖨 打印」'
      ],
      primaryLabel: '复制链接',
      primaryAction: copyPageLink
    });
    return;
  }

  /* 2) iPhone Safari：window.print() 静默失败，只能走系统分享菜单 */
  if(isIPhone && !isIPad){
    if(navigator.share){
      openPrintGuide({
        title: '在 iPhone 上打印',
        desc: 'iPhone 的 Safari 不响应网页里的直接打印，从系统的「分享」两步就到。',
        steps: [
          '点下面的「打开分享菜单」',
          '在弹出面板里向下滑，找到并点「打印」',
          '只要 PDF：在打印预览里双指放大，即可「存储到文件」'
        ],
        primaryLabel: '打开分享菜单',
        primaryAction: function(){
          try{
            navigator.share({ title: document.title, url: location.href });
          }catch(e){}
        }
      });
    }else{
      openPrintGuide({
        title: '在 iPhone 上打印',
        desc: '这个浏览器没有开放网页打印，用 Safari 打开后按下面两步操作。',
        steps: [
          '点 Safari 工具栏中间的「分享」图标 ⤴',
          '向下滑找到「打印」；只要 PDF 就在预览里双指放大后「存储到文件」'
        ],
        primaryLabel: '复制链接',
        primaryAction: copyPageLink
      });
    }
    return;
  }

  /* 3) iPad / Android / 鸿蒙 / 桌面：直接调起 */
  if(isIPad || isAndroid || isHarmony){
    printTip('正在调起打印…若没反应，请用浏览器菜单里的「打印 / 存为 PDF」。', 4200);
    try{ window.print(); }catch(e){}
    return;
  }
  try{
    window.print();
  }catch(e){
    printTip('当前浏览器没有响应打印，请用浏览器菜单里的「打印 / 存为 PDF」。');
  }
}"""

BTN_OLD = 'onclick="window.print()"'
BTN_NEW = 'onclick="doPrint()"'

V1_START = '/* ========== 打印：桌面直调'
V2_START = '/* ========== 打印：桌面 / iPad'
BLOCK_STARTS = (V1_START, V2_START)


def read(path):
    with io.open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        return f.read()


def write(path, text):
    with io.open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(text)


def strip_v1(src):
    """把旧版（v1 或 上一版 v2）的 printTip/doPrint 整块摘掉，便于整块换新"""
    start = -1
    for marker in BLOCK_STARTS:
        pos = src.find(marker)
        if pos >= 0 and (start < 0 or pos < start):
            start = pos
    if start < 0:
        return src, 0
    k = src.find('function doPrint', start)
    if k < 0:
        return src, 0
    end = src.find('\n}\n', k)
    if end < 0:
        return src, 0
    end += 2
    while end < len(src) and src[end] == '\n':
        end += 1
    return src[:start] + src[end:], 1


def is_v2(src):
    return ('function openPrintGuide' in src) and ('.pg-card{' in src) and ('.pg-mask{display:none' in src)


def patch(path, check_only=False):
    if not os.path.isfile(path):
        return ('skip', '文件不存在：%s' % path)

    src = read(path)
    orig = src

    if check_only:
        return ('check', '%s  %s' % (os.path.basename(path), 'v2 已就位' if is_v2(src) else '未就位 / 仍是 v1'))

    total = 0

    n_btn = src.count(BTN_OLD)
    if n_btn:
        src = src.replace(BTN_OLD, BTN_NEW)
        total += n_btn

    src, removed = strip_v1(src)
    total += removed

    if 'function openPrintGuide' not in src:
        if JS_ANCHOR in src:
            src = src.replace(JS_ANCHOR, JS_BLOCK, 1)
            total += 1
        else:
            return ('warn', 'JS 锚点未找到：%s' % os.path.basename(path))

    # 提示条 CSS（v1 已有则跳过）
    if '.print-tip{' not in src:
        if CSS_ANCHOR in src:
            src = src.replace(CSS_ANCHOR, CSS_TIP, 1)
            total += 1
        else:
            return ('warn', '提示条 CSS 锚点未找到：%s' % os.path.basename(path))

    # 引导卡片 CSS（v2 新增）
    if '.pg-card{' not in src:
        if CSS_GUIDE_ANCHOR in src:
            src = src.replace(CSS_GUIDE_ANCHOR, CSS_GUIDE, 1)
            total += 1
        else:
            return ('warn', '引导卡 CSS 锚点未找到：%s' % os.path.basename(path))

    # 打印时隐藏引导卡
    if '.pg-mask{display:none' not in src:
        if MEDIA_OLD in src:
            src = src.replace(MEDIA_OLD, MEDIA_NEW, 1)
            total += 1
        elif '</style>' in src:
            src = src.replace('</style>', MEDIA_NEW + '\n</style>', 1)
            total += 1

    if src == orig:
        return ('same', '无变化（已是 v2）：%s' % os.path.basename(path))

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
