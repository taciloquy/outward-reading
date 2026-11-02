#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐段朗读按钮补丁（para-audio-v3，幂等）
用法：
    python3 scripts/add-paragraph-audio.py <精读页.html> [--base audio/2026-11-01]

- 在每个 Paragraph N 的 .p-label 里注入描边喇叭按钮（SVG，JS 动态注入），点击朗读/停止本段
- 标题（#p-headline）的 .p-label 注入喇叭按钮 + 「连播」开关（标记 para-audio-title-v2）
  - 连播：按 标题 → P1 → P2 → … → Pn 顺序播完整篇；偏好存 localStorage('pa-chain')
  - 连播中自动滚动跟随当前段落，并预载下一段消除段间空档
  - 手动点了任意段落 → 从那里继续连播；连播关闭时播完当前段即停
  - 旧标记 para-audio-title-v1 会被原位升级替换为 v2（正文 v3 不动）
- 2026-11-02 用户决策：音色固定英音 Sonia、语速固定原速，**不提供任何选择器**
  （v1 顶栏切换 / v2 段内胶囊均已废弃）
- CSS：按钮态样式 + 播放中声波动画 + 连播开关态 + 打印隐藏
- 音频文件由 scripts/gen-paragraph-audio.py（v3）预生成：
    <base>/uk-title.m4a、<base>/uk-p<N>.m4a（英音原速，32kbps AAC 单声道）
"""
import re
import sys

MARK = "para-audio-v3"
TITLE_MARK = "para-audio-title-v2"

CSS = """/* ===== 逐段朗读 para-audio-v3 ===== */
.p-label{display:flex;align-items:center;gap:8px}
.p-label .p-label-text{flex:none}
.p-audio{appearance:none;border:none;background:transparent;cursor:pointer;
  padding:3px;line-height:0;color:var(--ink-light);border-radius:6px;
  transition:color .15s,background .15s}
.p-audio:hover{color:#0F6E56;background:rgba(15,110,86,.08)}
.p-audio:focus-visible{outline:2px solid #0F6E56;outline-offset:1px}
.p-audio svg{width:16px;height:16px;display:block}
.p-audio .pa-w1,.p-audio .pa-w2{opacity:.45;transition:opacity .15s}
.p-audio:hover .pa-w1,.p-audio:hover .pa-w2{opacity:.75}
.p-audio.playing{color:#0F6E56}
.p-audio.playing .pa-w1{opacity:1;animation:paWave 1.2s ease-in-out infinite}
.p-audio.playing .pa-w2{opacity:1;animation:paWave 1.2s ease-in-out infinite reverse}
@keyframes paWave{0%,100%{opacity:.2}50%{opacity:1}}
.p-audio.error{color:#b3543e}
@media print{.p-audio{display:none !important}}
"""

JS = r"""/* ===== 逐段朗读 para-audio-v3 ===== */
var PARA_AUDIO_BASE = '__AUDIO_BASE__';
var paraAudioEl = null, paraPlayingBtn = null;
function stopParaAudio(){
  if(paraAudioEl){ paraAudioEl.pause(); try{paraAudioEl.currentTime = 0;}catch(e){} }
  if(paraPlayingBtn){ paraPlayingBtn.classList.remove('playing'); paraPlayingBtn = null; }
}
function toggleParaAudio(btn, n){
  if(paraPlayingBtn === btn){ stopParaAudio(); return; }
  stopParaAudio();
  if(!paraAudioEl) paraAudioEl = new Audio();
  paraAudioEl.src = PARA_AUDIO_BASE + '/uk-p' + n + '.m4a';
  paraAudioEl.onended = stopParaAudio;
  paraAudioEl.onerror = function(){
    stopParaAudio(); btn.classList.add('error'); btn.title = '本段音频未生成';
  };
  paraAudioEl.play().catch(function(){});
  paraPlayingBtn = btn; btn.classList.add('playing');
}
(function initParaAudio(){
  var SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M11 5 L6.5 9 H3.5 V15 H6.5 L11 19 Z"/>'
    + '<path class="pa-w1" d="M14.8 9.4 A4 4 0 0 1 14.8 14.6"/>'
    + '<path class="pa-w2" d="M17.4 7 A7.6 7.6 0 0 1 17.4 17"/></svg>';
  document.querySelectorAll('section.paragraph').forEach(function(sec){
    var m = (sec.id || '').match(/^p(\d+)$/);
    if(!m) return;
    var label = sec.querySelector('.p-label');
    if(!label || label.querySelector('.p-audio')) return;
    label.innerHTML = '<span class="p-label-text">' + label.innerHTML + '</span>';
    var btn = document.createElement('button');
    btn.className = 'p-audio'; btn.type = 'button';
    btn.setAttribute('aria-label', '朗读本段'); btn.title = '朗读本段（英音）';
    btn.innerHTML = SVG;
    btn.addEventListener('click', function(){ toggleParaAudio(btn, m[1]); });
    label.appendChild(btn);
  });
})();
"""

# 标题朗读 + 连播：复用 v3 的按钮样式与播放器全局变量，独立标记，可单独增补/升级
TITLE_CSS = """/* ===== 连续播放 para-audio-title-v2 ===== */
.pa-loop{appearance:none;border:1px solid rgba(24,25,28,.25);background:transparent;cursor:pointer;
  font:inherit;font-size:12px;line-height:1;color:var(--ink-light);
  padding:4px 9px;border-radius:999px;transition:color .15s,background .15s,border-color .15s;
  white-space:nowrap;flex:none}
.pa-loop:hover{color:#0F6E56;border-color:#0F6E56;background:rgba(15,110,86,.08)}
.pa-loop.on{color:#fff;background:#0F6E56;border-color:#0F6E56}
.pa-loop:focus-visible{outline:2px solid #0F6E56;outline-offset:1px}
@media print{.pa-loop{display:none !important}}
"""

TITLE_JS = r"""/* ===== 标题朗读 + 连续播放 para-audio-title-v2 ===== */
var paChain = false;
try{ paChain = localStorage.getItem('pa-chain') === '1'; }catch(e){}
var paOrder = [], paCur = -1, paPre = null;

function paSrcOf(btn){
  var sec = btn.closest('section');
  var m = sec && (sec.id || '').match(/^p(\d+)$/);
  return PARA_AUDIO_BASE + (m ? '/uk-p' + m[1] : '/uk-title') + '.m4a';
}
function paPreload(i){
  var nxt = paOrder[i + 1];
  if(!nxt) return;
  if(!paPre) paPre = new Audio();
  paPre.preload = 'auto';
  paPre.src = paSrcOf(nxt);
}
function paAttachWatch(){
  if(paraAudioEl && !paraAudioEl.__paWatch){
    paraAudioEl.__paWatch = 1;
    paraAudioEl.addEventListener('ended', function(){
      if(!paChain || paCur < 0) return;
      var nxt = paOrder[paCur + 1];
      if(nxt) nxt.click();          // 复用按钮点击：状态/动画/滚动全部走同一入口
    });
  }
}
function toggleTitleAudio(btn){
  if(paraPlayingBtn === btn){ stopParaAudio(); return; }
  stopParaAudio();
  if(!paraAudioEl) paraAudioEl = new Audio();
  paraAudioEl.src = PARA_AUDIO_BASE + '/uk-title.m4a';
  paraAudioEl.onended = stopParaAudio;
  paraAudioEl.onerror = function(){
    stopParaAudio(); btn.classList.add('error'); btn.title = '标题音频未生成';
  };
  paraAudioEl.play().catch(function(){});
  paraPlayingBtn = btn; btn.classList.add('playing');
}
(function initTitleAudioV2(){
  var sec = document.getElementById('p-headline');
  if(!sec) return;
  var label = sec.querySelector('.p-label');
  if(!label) return;
  var SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M11 5 L6.5 9 H3.5 V15 H6.5 L11 19 Z"/>'
    + '<path class="pa-w1" d="M14.8 9.4 A4 4 0 0 1 14.8 14.6"/>'
    + '<path class="pa-w2" d="M17.4 7 A7.6 7.6 0 0 1 17.4 17"/></svg>';
  var titleBtn;
  if(label.querySelector('.p-audio')){          // v1 已注入过喇叭，直接复用
    titleBtn = label.querySelector('.p-audio');
  }else{
    label.innerHTML = '<span class="p-label-text">' + label.innerHTML + '</span>';
    titleBtn = document.createElement('button');
    titleBtn.className = 'p-audio'; titleBtn.type = 'button';
    titleBtn.setAttribute('aria-label', '朗读标题'); titleBtn.title = '朗读标题（英音）';
    titleBtn.innerHTML = SVG;
    titleBtn.addEventListener('click', function(){ toggleTitleAudio(titleBtn); });
    label.appendChild(titleBtn);
  }
  // 「连播」开关（放在标题喇叭右侧）
  var loop = document.createElement('button');
  loop.className = 'pa-loop' + (paChain ? ' on' : '');
  loop.type = 'button'; loop.textContent = '连播';
  loop.title = '连续播放：从当前位置按顺序播完整篇';
  loop.setAttribute('aria-pressed', String(paChain));
  loop.addEventListener('click', function(){
    paChain = !paChain;
    loop.classList.toggle('on', paChain);
    loop.setAttribute('aria-pressed', String(paChain));
    try{ localStorage.setItem('pa-chain', paChain ? '1' : '0'); }catch(e){}
  });
  label.appendChild(loop);

  // 播放序列：标题 → 各段（DOM 顺序；排除标题区自身——它的 class 也含 paragraph）
  paOrder = [titleBtn];
  document.querySelectorAll('section.paragraph').forEach(function(s2){
    if(!/^p\d+$/.test(s2.id || '')) return;
    var b = s2.querySelector('.p-audio');
    if(b) paOrder.push(b);
  });

  // 捕获阶段监听任意喇叭点击：记录连播起点 / 滚动跟随 / 预载下一段
  document.addEventListener('click', function(e){
    var b = e.target.closest ? e.target.closest('.p-audio') : null;
    if(!b) return;
    paCur = paOrder.indexOf(b);
    setTimeout(paAttachWatch, 0);               // paraAudioEl 可能刚由 v3 创建
    if(paChain){
      var s2 = b.closest('section');
      if(s2 && s2.scrollIntoView) s2.scrollIntoView({behavior:'smooth', block:'center'});
      paPreload(paCur);
    }
  }, true);
})();
"""


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    page = args[0]
    base = "audio/x"
    if "--base" in args:
        base = args[args.index("--base") + 1]
    else:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", page)
        if m:
            d = m.group(1)
            base = "audio/" + d
    s = open(page, encoding="utf-8").read()
    for old in ("para-audio-v1", "para-audio-v2"):
        if old in s:
            print(f"检测到旧补丁 {old}，请先还原页面再打 v3："
                  f"git checkout HEAD~N -- <页面>（N = 该页面打补丁的次数）")
            sys.exit(2)

    have_body = MARK in s
    have_title_v2 = TITLE_MARK in s
    have_title_v1 = "para-audio-title-v1" in s
    if have_body and have_title_v2:
        print(f"已打过补丁（{MARK} + {TITLE_MARK}），跳过：{page}")
        return

    done = []
    if not have_body:
        # 1) CSS：插在 </style> 前
        assert s.count("</style>") == 1, "预期单个 </style>"
        s = s.replace("</style>", CSS + "</style>", 1)
        # 2) JS：插在 </script> 前
        assert s.count("</script>") == 1, "预期单个 </script>"
        s = s.replace("</script>", JS.replace("__AUDIO_BASE__", base) + "</script>", 1)
        done.append("正文段落")

    if not have_title_v2:
        # 标题按钮复用 v3 的 CSS 与播放器全局变量，因此必须在正文补丁之后注入
        assert s.count("</script>") == 1, "预期单个 </script>"
        if have_title_v1:
            # v1 → v2 升级：整块替换旧标题脚本（连播开关等新增能力）
            i = s.index("/* ===== 标题朗读 para-audio-title-v1 ===== */")
            j = s.index("</script>", i)
            s = s[:i] + TITLE_JS + s[j:]
            assert s.count("</style>") == 1, "预期单个 </style>"
            s = s.replace("</style>", TITLE_CSS + "</style>", 1)
            done.append("标题 v1→v2（连播）")
        else:
            assert s.count("</style>") == 1, "预期单个 </style>"
            s = s.replace("</style>", TITLE_CSS + "</style>", 1)
            s = s.replace("</script>", TITLE_JS + "</script>", 1)
            done.append("标题+连播")

    open(page, "w", encoding="utf-8").write(s)
    print(f"已打补丁 {' + '.join(done)} → {page}（音频目录 {base}，固定英音原速）")


if __name__ == "__main__":
    main()
