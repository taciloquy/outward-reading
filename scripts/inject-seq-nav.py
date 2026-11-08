#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为精读页注入「上一篇 / 下一篇」跳转（不必回日历选择）。

形态（2026-11-03 用户定）：
  - 与「← 返回日历」同一行，左侧返回日历、右侧两枚圆形箭头（← →）
  - 平时只有箭头，鼠标悬停 / 键盘聚焦时才浮现「上一篇」「下一篇」
  - 首尾篇缺失的一侧显示为不可点的灰箭头，保持两枚位置固定
  - 手机上不额外占竖向空间；打印隐藏

用法：
  python3 scripts/inject-seq-nav.py            # 更新所有已发布精读页
  python3 scripts/inject-seq-nav.py 2026-11-03 # 更新该日期页 + 其前后相邻页（integrate 用）

依据 articles.js 里的 ARTICLES 数组（按 publishDate + fileKey 排序）确定相邻文章。幂等。
（首页轻量化后元数据已外置；未拆分的工作区自动回退读 index.html。）
"""
import json, re, sys, os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "articles.js")
if not os.path.exists(INDEX):
    INDEX = os.path.join(REPO, "index.html")

PAGER_CSS = """<style id="pager-css">
/* 上一篇 / 下一篇：与「返回日历」同行，右侧双箭头，悬停出字 */
.head-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.pager{display:flex;align-items:center;gap:6px;flex:none;margin:0}
.pg-btn{position:relative;display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;border-radius:50%;flex:none;
  color:#4a6fa5;background:rgba(74,111,165,.10);text-decoration:none;
  font:600 15px/1 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  -webkit-tap-highlight-color:transparent;transition:background .15s,color .15s,transform .15s}
.pg-btn:hover,.pg-btn:focus-visible{background:#4a6fa5;color:#fff;transform:translateY(-1px)}
.pg-btn:active{transform:translateY(0)}
.pg-btn.is-off{background:transparent;color:#cfc9bd;pointer-events:none;cursor:default}
.pg-tip{position:absolute;top:calc(100% + 7px);left:50%;
  transform:translateX(-50%) translateY(-4px);
  padding:4px 9px;border-radius:6px;background:#3d3a34;color:#fff;
  font:500 12px/1.3 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  white-space:nowrap;opacity:0;visibility:hidden;pointer-events:none;z-index:90;
  transition:opacity .15s,visibility .15s,transform .15s}
.pg-tip:before{content:"";position:absolute;bottom:100%;left:50%;transform:translateX(-50%);
  border:5px solid transparent;border-bottom-color:#3d3a34}
.pg-btn:hover .pg-tip,.pg-btn:focus-visible .pg-tip{opacity:1;visibility:visible;
  transform:translateX(-50%) translateY(0)}
@media print{.pager{display:none !important}}
body.print-sheet .pager{display:none !important}
</style>
"""

OLD_NAV_RE = r'<nav class="(?:seq-nav|pager)"[^>]*>.*?</nav>'


def load_articles():
    """用 node 解析 index.html 里的 ARTICLES（合法 JS 字面量），返回按日期排序的列表。"""
    js = (
        "const fs=require('fs');"
        "const h=fs.readFileSync(process.argv[1],'utf8');"
        "const i=h.indexOf('const ARTICLES = [');"
        "const start=i+'const ARTICLES = '.length;"
        "let depth=0,end=-1;"
        "for(let k=start;k<h.length;k++){if(h[k]==='[')depth++;else if(h[k]===']'){depth--;if(depth===0){end=k+1;break;}}}"
        "const a=eval('('+h.slice(start,end)+')');"
        "process.stdout.write(JSON.stringify(a));"
    )
    out = subprocess.run(["node", "-e", js, INDEX], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("node 解析 ARTICLES 失败: " + out.stderr)
    arts = json.loads(out.stdout)
    arts.sort(key=lambda x: (x.get("publishDate", ""), x.get("fileKey", "")))
    return arts


def local_path(reading_path):
    rel = reading_path
    if rel.startswith("/outward-reading"):
        rel = rel[len("/outward-reading"):]
    return REPO + rel


def build_block(prev_e, next_e):
    """两枚固定位置的圆箭头；缺失一侧渲染为灰箭头占位。"""
    def btn(kind, e, ico, tip):
        if e and e.get("readingPath"):
            return (f'<a class="pg-btn pg-{kind}" href="{e["readingPath"]}" '
                    f'aria-label="{tip}"><span class="pg-ico" aria-hidden="true">{ico}</span>'
                    f'<span class="pg-tip" role="tooltip">{tip}</span></a>')
        return (f'<span class="pg-btn pg-{kind} is-off" aria-hidden="true">'
                f'<span class="pg-ico">{ico}</span></span>')

    parts = [btn("prev", prev_e, "←", "上一篇"), btn("next", next_e, "→", "下一篇")]
    return '<nav class="pager" aria-label="文章翻页">' + "".join(parts) + "</nav>"


def ensure_css(html):
    """替换/插入自带样式块（幂等）。"""
    html = re.sub(r'<style id="pager-css">.*?</style>\s*', '', html, flags=re.S)
    if "</head>" in html:
        html = html.replace("</head>", PAGER_CSS + "</head>", 1)
    return html


def mount_nav(html, block):
    """把 nav 放进与「返回日历」同行的 .head-top 容器（已有则复用，无则新建）。"""
    html = re.sub(OLD_NAV_RE, "", html, flags=re.S)

    m = re.search(r'<div class="head-top">(.*?)</div>', html, re.S)
    if m:
        inner = re.sub(OLD_NAV_RE, "", m.group(1), flags=re.S).rstrip()
        new = '<div class="head-top">' + inner + block + "</div>"
        return html[:m.start()] + new + html[m.end():]

    m = re.search(r'<a class="back-cal"[^>]*>.*?</a>', html, re.S)
    if not m:
        return None
    new = '<div class="head-top">' + m.group(0) + block + "</div>"
    return html[:m.start()] + new + html[m.end():]


def update_page(path, prev_e, next_e):
    if not os.path.exists(path):
        print("  [跳过] 本地文件不存在:", path)
        return False
    html = open(path, encoding="utf-8").read()
    out = mount_nav(html, build_block(prev_e, next_e))
    if out is None:
        print("  [跳过] 找不到 back-cal 锚点:", path)
        return False
    out = ensure_css(out)
    if out == html:
        return True
    open(path, "w", encoding="utf-8").write(out)
    return True


def main():
    arts = load_articles()
    # 2026-11-09 起同日可能有两篇（如【共读】_002），翻页按 (publishDate, fileKey) 全序
    focal = sys.argv[1] if len(sys.argv) > 1 else None

    def neighbors(idx):
        prev_e = arts[idx - 1] if idx - 1 >= 0 else None
        next_e = arts[idx + 1] if idx + 1 < len(arts) else None
        return prev_e, next_e

    if focal:
        targets = set()
        for i, a in enumerate(arts):
            if a.get("publishDate") == focal:
                targets.add(i)
                if i - 1 >= 0:
                    targets.add(i - 1)
                if i + 1 < len(arts):
                    targets.add(i + 1)
        target_idx = sorted(targets)
        print("更新焦点页及其相邻页:", [arts[i]["fileKey"] for i in target_idx])
    else:
        target_idx = list(range(len(arts)))
        print(f"批量更新全部 {len(target_idx)} 篇")

    for i in target_idx:
        e = arts[i]
        if not e.get("readingPath"):
            print(f"  [跳过] 无 readingPath: {e.get('fileKey')}")
            continue
        prev_e, next_e = neighbors(i)
        update_page(local_path(e["readingPath"]), prev_e, next_e)
        tags = []
        if prev_e:
            tags.append("←" + prev_e.get("fileKey", ""))
        if next_e:
            tags.append("→" + next_e.get("fileKey", ""))
        print(f"  ✓ {e.get('fileKey')}: " + (" ".join(tags) if tags else "（无相邻）"))


if __name__ == "__main__":
    main()
