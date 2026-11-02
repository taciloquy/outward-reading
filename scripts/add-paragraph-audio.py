#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐段朗读按钮补丁（para-audio-v1，幂等）
用法：
    python3 scripts/add-paragraph-audio.py <精读页.html> [--base audio/2026-11-01]

- 在每个 Paragraph N 的 .p-label 里注入描边喇叭按钮（SVG，JS 动态注入）
- 在 .tool-row 里注入「美音 / 英音」切换胶囊
- CSS：按钮态样式 + 播放中声波动画 + 打印隐藏
- JS：单 Audio 实例播放/停止、localStorage 记忆音色（outward-tts-voice-v1）
- 音频文件由 scripts/gen-paragraph-audio.py 预生成于 <base>/<us|uk>-p<N>.mp3
"""
import re
import sys

MARK = "para-audio-v1"

CSS = """/* ===== 逐段朗读 para-audio-v1 ===== */
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
.voice-switch{display:flex;align-items:center;border:1px solid var(--line,#ddd);
  border-radius:99px;overflow:hidden;flex:none}
.voice-switch .vs-btn{appearance:none;border:none;background:transparent;
  font-size:12px;padding:4px 12px;cursor:pointer;color:var(--ink-light);
  line-height:1.4;letter-spacing:.05em}
.voice-switch .vs-btn.active{background:#0F6E56;color:#fff}
@media print{.p-audio,.voice-switch{display:none !important}}
"""

JS = r"""/* ===== 逐段朗读 para-audio-v1 ===== */
var PARA_AUDIO_BASE = '__AUDIO_BASE__';
var paraVoice = localStorage.getItem('outward-tts-voice-v1') || 'us';
var paraAudioEl = null, paraPlayingBtn = null;
function setParaVoice(v){
  paraVoice = v;
  localStorage.setItem('outward-tts-voice-v1', v);
  document.querySelectorAll('.voice-switch .vs-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-voice') === v);
  });
  stopParaAudio();
}
function stopParaAudio(){
  if(paraAudioEl){ paraAudioEl.pause(); try{paraAudioEl.currentTime = 0;}catch(e){} }
  if(paraPlayingBtn){ paraPlayingBtn.classList.remove('playing'); paraPlayingBtn = null; }
}
function toggleParaAudio(btn, n){
  if(paraPlayingBtn === btn){ stopParaAudio(); return; }
  stopParaAudio();
  if(!paraAudioEl) paraAudioEl = new Audio();
  paraAudioEl.src = PARA_AUDIO_BASE + '/' + paraVoice + '-p' + n + '.mp3';
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
    btn.setAttribute('aria-label', '朗读本段'); btn.title = '朗读本段';
    btn.innerHTML = SVG;
    btn.addEventListener('click', function(){ toggleParaAudio(btn, m[1]); });
    label.appendChild(btn);
  });
  var sw = document.getElementById('voice-switch');
  if(sw){
    sw.querySelectorAll('.vs-btn').forEach(function(b){
      b.classList.toggle('active', b.getAttribute('data-voice') === paraVoice);
    });
    sw.addEventListener('click', function(e){
      var b = e.target.closest('.vs-btn');
      if(b) setParaVoice(b.getAttribute('data-voice'));
    });
  }
})();
"""

VOICE_SWITCH_HTML = (
    '          <div class="voice-switch" id="voice-switch" role="group" aria-label="朗读音色">\n'
    '            <button type="button" class="vs-btn" data-voice="us">美音</button>\n'
    '            <button type="button" class="vs-btn" data-voice="uk">英音</button>\n'
    '          </div>\n'
)


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

    # 1) CSS：插在 </style> 前
    assert s.count("</style>") == 1, "预期单个 </style>"
    s = s.replace("</style>", CSS + "</style>", 1)

    # 2) 音色切换：插在 .print-btn 所在按钮前
    m = re.search(r'(\n\s*)(<button class="print-btn")', s)
    assert m, "未找到 print-btn"
    s = s.replace(m.group(0), "\n" + VOICE_SWITCH_HTML + m.group(1) + m.group(2), 1)

    # 3) JS：插在 </script> 前
    assert s.count("</script>") == 1, "预期单个 </script>"
    js = JS.replace("__AUDIO_BASE__", base)
    s = s.replace("</script>", js + "</script>", 1)

    open(page, "w", encoding="utf-8").write(s)
    print(f"已打补丁 {MARK} → {page}（音频目录 {base}）")


if __name__ == "__main__":
    main()
