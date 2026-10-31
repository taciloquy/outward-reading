#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阅读体验补丁（幂等）：右侧查询面板在宽屏默认收成右侧竖条，把宽度让给正文与矢量导图；
点击竖条展开——电脑上与正文并排（正文左缩），平板（≤1080px）上是右侧抽屉浮层，不挤压正文。

用法：
  python3 scripts/patch-side-rail.py            # 全站 articles/**/*.reading.html
  python3 scripts/patch-side-rail.py --dry-run f1 f2
"""
import glob, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "side-rail-v1"

CSS = """/* ========== 右侧查询面板：宽屏默认收成竖条，点击展开（side-rail-v1） ========== */
/* 平板（768–1080）：展开态是右侧抽屉浮层，正文宽度不变、不重排，只盖住右侧一小条 */
@media (min-width:768px) and (max-width:1080px){
  body:not(.side-collapsed) .side{
    position:fixed;z-index:70;right:12px;
    top:calc(var(--header-h) + 12px);
    width:min(360px,64vw);height:calc(100vh - var(--header-h) - 24px);
    flex:none;min-width:0;
  }
  body:not(.side-collapsed) .side-inner{
    box-shadow:0 16px 40px rgba(24,25,28,.22),0 2px 8px rgba(24,25,28,.10);
  }
  body:not(.side-collapsed) .side-collapse{font-size:12.5px;padding:4px 8px}
}
@media (min-width:768px){
  body.side-collapsed .layout{gap:14px}
  body.side-collapsed .side{flex:0 0 60px;width:60px;min-width:0;height:auto}
  body.side-collapsed .side-inner{
    background:transparent;border:0;padding:0;height:auto;display:block;overflow:visible;
  }
  body.side-collapsed .side-head{margin:0;padding:0;display:block}
  body.side-collapsed .side-head h2{display:none}
  body.side-collapsed .side-collapse{
    writing-mode:vertical-rl;-webkit-writing-mode:vertical-rl;
    display:block;margin:0 auto;width:38px;height:auto;padding:18px 0;
    border-radius:999px;border:1px solid var(--line);
    background:var(--accent-light);color:var(--accent);
    font-size:13px;letter-spacing:.2em;line-height:1;
  }
  body.side-collapsed .side-collapse:hover{border-color:var(--accent);filter:brightness(.98)}
  body.side-collapsed .side-body{display:none}
}
"""

OLD_SIDE = ".side{\n  flex:3;min-width:0;"
NEW_SIDE = ".side{\n  flex:0 0 clamp(288px,30%,404px);min-width:0;"

OLD_BP = "@media (max-width:1024px){"
NEW_BP = "@media (max-width:767px){"

OLD_TOGGLE = """function toggleSide(){
  var body = document.getElementById('side-body');
  body.classList.toggle('hidden');
  var btn = document.querySelector('.side-collapse');
  btn.textContent = body.classList.contains('hidden') ? '展开面板' : '收起面板';
}"""

NEW_TOGGLE = """/* ========== 右侧面板开合：宽屏默认收成竖条，点击展开；偏好记入 localStorage ========== */
var SIDE_PREF = 'outward-side-open-v1';
function sideWide(){ return window.matchMedia('(min-width:768px)').matches; }
function sideHidden(){
  var b = document.getElementById('side-body');
  return !!b && b.classList.contains('hidden');
}
function syncSideBtn(){
  var btn = document.querySelector('.side-collapse');
  if(!btn) return;
  if(sideWide() && sideHidden()){
    btn.textContent = '展开查询面板';
    btn.title = '点击展开查询面板，与正文并排显示';
  }else{
    btn.textContent = sideHidden() ? '展开面板' : '收起面板';
    btn.title = '';
  }
}
function setSide(open, remember){
  var body = document.getElementById('side-body');
  if(!body) return;
  body.classList.toggle('hidden', !open);
  document.body.classList.toggle('side-collapsed', !open);
  if(remember){ try{ localStorage.setItem(SIDE_PREF, open ? '1' : '0'); }catch(e){} }
  syncSideBtn();
  if(typeof syncHeaderHeight === 'function') syncHeaderHeight();
}
function toggleSide(){
  setSide(sideHidden(), true);   /* 收起状态点一下就展开 */
}
(function initSide(){
  var saved = null;
  try{ saved = localStorage.getItem(SIDE_PREF); }catch(e){}
  /* 手机保持展开（面板在页面底部）；电脑 / iPad 首次访问默认收起，之后按用户上次的选择 */
  var open = sideWide() ? (saved === '1') : true;
  setSide(open, false);
  window.addEventListener('resize', syncSideBtn);
})();"""

OLD_SHOWTAB = "if(body && body.classList.contains('hidden')) toggleSide();"
NEW_SHOWTAB = "if(body && body.classList.contains('hidden')) setSide(true, false);"


def patch(path):
    s = open(path, encoding="utf-8").read()
    if MARK in s:
        return "skip"
    missing = []
    for old in (OLD_SIDE, OLD_BP, OLD_TOGGLE, OLD_SHOWTAB):
        if old not in s:
            missing.append(old.split("\n")[0][:40])
    if missing:
        return "MISS " + str(missing)

    s = s.replace(OLD_SIDE, NEW_SIDE, 1)
    s = s.replace(OLD_BP, NEW_BP, 1)
    s = s.replace(OLD_TOGGLE, NEW_TOGGLE, 1)
    s = s.replace(OLD_SHOWTAB, NEW_SHOWTAB, 1)
    i = s.rfind("</style>")
    s = s[:i] + CSS + s[i:]
    open(path, "w", encoding="utf-8").write(s)
    return "ok"


def inspect(path):
    s = open(path, encoding="utf-8").read()
    if MARK in s:
        return "skip"
    miss = [o.split("\n")[0][:40] for o in (OLD_SIDE, OLD_BP, OLD_TOGGLE, OLD_SHOWTAB) if o not in s]
    return "MISS " + str(miss) if miss else "todo"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    files = args or sorted(glob.glob(os.path.join(REPO, "articles/**/*.reading.html"), recursive=True))
    stats = {}
    for f in files:
        r = inspect(f) if dry else patch(f)
        stats[r] = stats.get(r, 0) + 1
        if r.startswith("MISS"):
            print(r, f)
    print(("DRY " if dry else "") + "files:", len(files), stats)


if __name__ == "__main__":
    main()
