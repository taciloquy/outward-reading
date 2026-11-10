#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向所有精读页注入「搜全文跳转」脚本（幂等，可重复跑）。

功能：页面 URL 带 ?q=关键词 时，自动定位到该句并把关键词橙色高亮
     （#ffc078，与首页搜索结果列表的黄色 #fef08a 区分）。

注入位置：</body> 前；标记 <script id="search-jump">，重复跑不重复注入。
母版（2026-10-30 页）同样注入，此后 build-reading-page.py 产出的新页自动继承。

用法：
  python3 scripts/inject-search-jump.py            # 注入所有缺失页
  python3 scripts/inject-search-jump.py --check    # 只报告，不写
"""
import glob
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = '<script id="search-jump">'

SNIPPET = '''<script id="search-jump">
/* 搜全文跳转：?q=关键词 → 定位到该句并橙色高亮（#ffc078，与列表页黄色区分） */
(function(){
  try{
    var q=(new URLSearchParams(location.search)).get('q');
    if(!q||!q.trim())return;
    var parts=q.trim().split(/\\s+/).map(function(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')});
    var re=new RegExp(parts.join('\\\\s+'),'i');
    var walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,
      {acceptNode:function(n){return n.nodeValue.trim()?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});
    var nodes=[],nd;while((nd=walker.nextNode()))nodes.push(nd);
    var full='',spans=[];
    nodes.forEach(function(x){spans.push([full.length,full.length+x.nodeValue.length,x]);full+=x.nodeValue});
    var m=full.match(re);
    function toView(el){try{el.scrollIntoView({behavior:'smooth',block:'center'})}catch(e){el.scrollIntoView()}}
    if(m){
      var s=m.index,e=s+m[0].length,done=null;
      spans.forEach(function(sp){
        var a=sp[0],b=sp[1],x=sp[2];
        if(b<=s||a>=e)return;
        try{
          var rng=document.createRange();
          rng.setStart(x,Math.max(s,a)-a);rng.setEnd(x,Math.min(e,b)-a);
          var mk=document.createElement('mark');
          mk.style.background='#ffc078';mk.style.color='inherit';
          rng.surroundContents(mk);
          if(!done)done=mk;
        }catch(err){}
      });
      if(done)toView(done);
    }else{
      /* 关键词跨标签拼接无法整体匹配时：退而定位到包含它的最小块级元素，橙框提示 */
      var els=document.querySelectorAll('div,p,h1,h2,h3,li');
      for(var i=0;i<els.length;i++){var el=els[i];
        if(el.querySelector('div,p,li'))continue;
        if(re.test(el.textContent)){
          el.style.outline='3px solid #ffc078';el.style.outlineOffset='2px';
          toView(el);break;
        }
      }
    }
  }catch(e){}
})();
</script>'''


def main():
    check = "--check" in sys.argv
    pages = sorted(glob.glob(os.path.join(REPO, "articles", "*", "*", "*.reading.html")))
    injected, skipped = [], []
    for p in pages:
        with open(p, encoding="utf-8") as f:
            html = f.read()
        if MARKER in html:
            skipped.append(p)
            continue
        idx = html.rfind("</body>")
        if idx < 0:
            print(f"[×] 无 </body>：{p}")
            continue
        injected.append(p)
        if not check:
            html = html[:idx] + SNIPPET + html[idx:]
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)
    print(f"共 {len(pages)} 页：{'需注入' if check else '已注入'} {len(injected)}，已有 {len(skipped)}")
    if not check:
        for p in injected:
            print("  + " + os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
