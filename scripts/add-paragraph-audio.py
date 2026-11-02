#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐段朗读按钮补丁（para-audio-v2，幂等）
用法：
    python3 scripts/add-paragraph-audio.py <精读页.html> [--base audio/2026-11-01]

- 在每个 Paragraph N 的 .p-label 里注入：
    1. 描边喇叭按钮（SVG，JS 动态注入）——点击朗读/停止本段
    2. 「英音·原速」小胶囊——点开弹出面板选「音色（美音/英音）+ 语速（原速/慢速）」
- 选择对全篇所有段落统一生效，记在 localStorage（outward-tts-pref-v2）
- 默认：英音 + 原速
- CSS：按钮态样式 + 播放中声波动画 + 弹出面板 + 打印隐藏
- 音频文件由 scripts/gen-paragraph-audio.py（v2）预生成：
    <base>/<us|uk>-p<N>.mp3（原速） 与 <base>/<us|uk>-p<N>-s.mp3（慢速）
- v2 不再往 .tool-row 注入顶栏切换（v1 行为已废弃）
"""
import re
import sys

MARK = "para-audio-v2"

CSS = """/* ===== 逐段朗读 para-audio-v2 ===== */
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
.p-audio-pref{appearance:none;border:1px solid rgba(0,0,0,.14);background:transparent;
  cursor:pointer;font-size:10.5px;letter-spacing:.04em;line-height:1;
  padding:3px 7px;border-radius:99px;color:var(--ink-light);white-space:nowrap;
  transition:color .15s,border-color .15s,background .15s}
.p-audio-pref:hover{color:#0F6E56;border-color:rgba(15,110,86,.45);background:rgba(15,110,86,.06)}
.pa-pop{position:fixed;z-index:120;display:none;background:#fff;
  border:1px solid rgba(0,0,0,.12);border-radius:12px;padding:10px 12px;
  box-shadow:0 8px 28px rgba(0,0,0,.16);min-width:148px;
  font-size:12.5px;color:var(--ink,#333)}
.pa-pop.open{display:block}
.pa-pop .pa-pop-row{display:flex;align-items:center;gap:8px;margin:5px 0}
.pa-pop .pa-pop-cap{flex:none;width:2.6em;color:#999;letter-spacing:.08em}
.pa-pop .pa-opt{appearance:none;border:1px solid transparent;background:transparent;
  cursor:pointer;font-size:12.5px;padding:3px 10px;border-radius:99px;
  color:var(--ink-light);line-height:1.5;white-space:nowrap}
.pa-pop .pa-opt:hover{background:rgba(15,110,86,.08);color:#0F6E56}
.pa-pop .pa-opt.active{background:#0F6E56;color:#fff}
@media print{.p-audio,.p-audio-pref,.pa-pop{display:none !important}}
"""

JS = r"""/* ===== 逐段朗读 para-audio-v2 ===== */
var PARA_AUDIO_BASE = '__AUDIO_BASE__';
var PARA_PREF_KEY = 'outward-tts-pref-v2';
var paraPref = {voice:'uk', rate:'normal'};
try{
  var _pp = JSON.parse(localStorage.getItem(PARA_PREF_KEY) || 'null');
  if(_pp && (_pp.voice === 'us' || _pp.voice === 'uk') && (_pp.rate === 'normal' || _pp.rate === 'slow')){
    paraPref = _pp;
  }
}catch(e){}
var paraAudioEl = null, paraPlayingBtn = null;
var PARA_VOICE_LABEL = {us:'美音', uk:'英音'};
var PARA_RATE_LABEL = {normal:'原速', slow:'慢速'};

function paraFile(n){
  return PARA_AUDIO_BASE + '/' + paraPref.voice + '-p' + n + (paraPref.rate === 'slow' ? '-s' : '') + '.mp3';
}
function stopParaAudio(){
  if(paraAudioEl){ paraAudioEl.pause(); try{paraAudioEl.currentTime = 0;}catch(e){} }
  if(paraPlayingBtn){ paraPlayingBtn.classList.remove('playing'); paraPlayingBtn = null; }
}
function toggleParaAudio(btn, n){
  if(paraPlayingBtn === btn){ stopParaAudio(); return; }
  stopParaAudio();
  if(!paraAudioEl) paraAudioEl = new Audio();
  paraAudioEl.src = paraFile(n);
  paraAudioEl.onended = stopParaAudio;
  paraAudioEl.onerror = function(){
    stopParaAudio(); btn.classList.add('error'); btn.title = '本段音频未生成';
  };
  paraAudioEl.play().catch(function(){});
  paraPlayingBtn = btn; btn.classList.add('playing');
}
function saveParaPref(){
  try{ localStorage.setItem(PARA_PREF_KEY, JSON.stringify(paraPref)); }catch(e){}
}
function refreshPrefUI(){
  document.querySelectorAll('.p-audio-pref').forEach(function(c){
    c.textContent = PARA_VOICE_LABEL[paraPref.voice] + '·' + PARA_RATE_LABEL[paraPref.rate];
  });
  document.querySelectorAll('.pa-pop .pa-opt').forEach(function(o){
    o.classList.toggle('active',
      (o.getAttribute('data-voice') === paraPref.voice) ||
      (o.getAttribute('data-rate') === paraPref.rate));
  });
}
function setParaPref(key, val){
  paraPref[key] = val;
  saveParaPref(); refreshPrefUI(); stopParaAudio();
}
function closePaPop(){
  var pop = document.getElementById('pa-pop');
  if(pop) pop.classList.remove('open');
}
function openPaPop(anchor){
  var pop = document.getElementById('pa-pop');
  if(!pop) return;
  var r = anchor.getBoundingClientRect();
  pop.classList.add('open');
  var pw = pop.offsetWidth, ph = pop.offsetHeight;
  var left = Math.min(Math.max(8, r.left - 8), window.innerWidth - pw - 8);
  var top = r.bottom + 6;
  if(top + ph > window.innerHeight - 8) top = r.top - ph - 6;
  pop.style.left = left + 'px';
  pop.style.top = Math.max(8, top) + 'px';
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
    btn.setAttribute('aria-label', '朗读本段'); btn.title = '朗读本段';
    btn.innerHTML = SVG;
    btn.addEventListener('click', function(){ toggleParaAudio(btn, m[1]); });
    var chip = document.createElement('button');
    chip.className = 'p-audio-pref'; chip.type = 'button';
    chip.title = '选择音色与语速';
    chip.addEventListener('click', function(e){
      e.stopPropagation();
      var pop = document.getElementById('pa-pop');
      if(pop && pop.classList.contains('open') && pop.__anchor === chip){ closePaPop(); return; }
      pop.__anchor = chip; openPaPop(chip);
    });
    label.appendChild(btn);
    label.appendChild(chip);
  });
  /* 共享弹出面板 */
  if(!document.getElementById('pa-pop')){
    var pop = document.createElement('div');
    pop.className = 'pa-pop'; pop.id = 'pa-pop';
    pop.innerHTML =
        '<div class="pa-pop-row"><span class="pa-pop-cap">音色</span>'
      + '<button type="button" class="pa-opt" data-voice="us">美音</button>'
      + '<button type="button" class="pa-opt" data-voice="uk">英音</button></div>'
      + '<div class="pa-pop-row"><span class="pa-pop-cap">语速</span>'
      + '<button type="button" class="pa-opt" data-rate="normal">原速</button>'
      + '<button type="button" class="pa-opt" data-rate="slow">慢速</button></div>';
    pop.addEventListener('click', function(e){
      var o = e.target.closest('.pa-opt');
      if(!o) return;
      if(o.getAttribute('data-voice')) setParaPref('voice', o.getAttribute('data-voice'));
      else if(o.getAttribute('data-rate')) setParaPref('rate', o.getAttribute('data-rate'));
      closePaPop();
    });
    document.body.appendChild(pop);
    document.addEventListener('click', function(e){
      var pop2 = document.getElementById('pa-pop');
      if(pop2 && pop2.classList.contains('open')
         && !pop2.contains(e.target) && e.target !== pop2.__anchor) closePaPop();
    });
    document.addEventListener('keydown', function(e){ if(e.key === 'Escape') closePaPop(); });
  }
  refreshPrefUI();
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
    if MARK in s:
        print(f"已打过补丁（{MARK}），跳过：{page}")
        return
    if "para-audio-v1" in s:
        print(f"检测到 v1 补丁，请先还原页面（git checkout）再打 v2：{page}")
        sys.exit(2)

    # 1) CSS：插在 </style> 前
    assert s.count("</style>") == 1, "预期单个 </style>"
    s = s.replace("</style>", CSS + "</style>", 1)

    # 2) JS：插在 </script> 前
    assert s.count("</script>") == 1, "预期单个 </script>"
    js = JS.replace("__AUDIO_BASE__", base)
    s = s.replace("</script>", js + "</script>", 1)

    open(page, "w", encoding="utf-8").write(s)
    print(f"已打补丁 {MARK} → {page}（音频目录 {base}）")


if __name__ == "__main__":
    main()
