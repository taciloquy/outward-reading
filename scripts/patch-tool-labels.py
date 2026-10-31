#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精简文章页顶部按钮文字，解决窄屏下与「打印」按钮拥挤重叠。

映射：
  双语正文   -> 正文
  词汇总表   -> 词汇
  专有名词表 -> 专有名词
  翻译练习   -> 练习
  打印按钮   -> 只保留 🖨 图标（+ aria-label）

只处理 <nav class="anchors"> 内的链接与 .print-btn 按钮，不动正文里的
「翻译练习」小节标题、右侧面板内的「词汇总表」标签等。

用法：python3 patch-tool-labels.py [--check] 文件1.html 文件2.html ...
"""
import re
import sys

MAP = {
    "双语正文": "正文",
    "词汇总表": "词汇",
    "专有名词表": "专有名词",
    "翻译练习": "练习",
}

ANCHORS_RE = re.compile(r'(<nav class="anchors">)(.*?)(</nav>)', re.S)
LINK_TEXT_RE = re.compile(r'(<a\b[^>]*>)([^<]*)(</a>)')
PRINT_RE = re.compile(r'(<button\b[^>]*class="print-btn"[^>]*>)\s*[^<]*?(</button>)')


def patch_anchors(block: str) -> str:
    def repl(m):
        label = m.group(2).strip()
        return m.group(1) + MAP.get(label, m.group(2)) + m.group(3)
    return LINK_TEXT_RE.sub(repl, block)


def patch(text: str) -> str:
    text = ANCHORS_RE.sub(lambda m: m.group(1) + patch_anchors(m.group(2)) + m.group(3), text)

    def print_repl(m):
        open_tag = m.group(1)
        if "aria-label" not in open_tag:
            open_tag = open_tag[:-1] + ' aria-label="打印">'
        return open_tag + "🖨" + m.group(2)

    return PRINT_RE.sub(print_repl, text)


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    check = "--check" in sys.argv
    for path in args:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        out = patch(src)
        state = "已是最新" if src == out else "需修改"
        print(f"{state}  {path}")
        if src != out and not check:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)


if __name__ == "__main__":
    main()
