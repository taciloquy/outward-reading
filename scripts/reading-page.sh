#!/bin/bash
# ============================================================
# 外刊精读页流水线（手动执行版）
# 用法：
#   bash scripts/reading-page.sh check              # 检查有哪些新 PDF 还没做精读页
#   bash scripts/reading-page.sh integrate <精读页.html> [YYYY-MM-DD]
#                                                   # 把 WorkBuddy 做好的精读页挂上日历并发布
# 说明：
#   1) PDF → 精读页 这一步需要 AI 处理（WorkBuddy 对话完成），脚本负责其余全部机械环节；
#   2) integrate 会：复制精读页到 articles/YYYY/MM/ → 给 index.html 对应日期条目
#      加 readingPath（若无）→ 记入已处理清单 → git commit + push（GitHub Pages 自动部署）；
#   3) 已处理清单：scripts/processed-reading.list（每行一个 YYYY-MM-DD）。
# ============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_ROOT="/Volumes/WORK DISK/QHY/读书/1.早安英文"
MANIFEST="$REPO_DIR/scripts/processed-reading.list"
INDEX="$REPO_DIR/index.html"

touch "$MANIFEST"

cmd="${1:-help}"

case "$cmd" in

  check)
    echo "== 扫描 $SOURCE_ROOT 下的【完整笔记】PDF =="
    found=0
    for pdf in "$SOURCE_ROOT"/20*/*【完整笔记】*.pdf; do
      [ -e "$pdf" ] || continue
      found=1
      base="$(basename "$pdf")"
      # 从文件名取日期前缀 YYYYMMDD → 20YY-MM-DD
      if [[ "$base" =~ ^([0-9]{4})([0-9]{2})([0-9]{2}) ]]; then
        date="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      else
        date="(未知日期)"
      fi
      if grep -qx "$date" "$MANIFEST"; then
        echo "  [已处理] $date  $base"
      else
        echo "  [待处理] $date  $base   ←→ 把这个 PDF 发给 WorkBuddy 制作精读页"
      fi
    done
    if [ "$found" -eq 0 ]; then echo "  （没有找到任何【完整笔记】PDF）"; fi
    exit 0
    ;;

  integrate)
    html="${2:-}"
    [ -f "$html" ] || { echo "错误：请传入做好的精读页 HTML 路径"; exit 1; }
    html="$(cd "$(dirname "$html")" && pwd)/$(basename "$html")"

    # 日期：优先第 3 参数，否则从文件名 YYYYMMDD / YYMMDD 推断
    date="${3:-}"
    if [ -z "$date" ]; then
      base="$(basename "$html")"
      if   [[ "$base" =~ (^|[^0-9])(20[0-9]{2})([0-9]{2})([0-9]{2})([^0-9]|$) ]]; then
        date="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      elif [[ "$base" =~ (^|[^0-9])([0-9]{2})([0-9]{2})([0-9]{2})([^0-9]|$) ]]; then
        date="20${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      else
        echo "错误：无法从文件名推断日期，请手动指定：integrate <html> YYYY-MM-DD"; exit 1
      fi
    fi

    yy="${date:0:4}"; mm="${date:5:2}"
    dest_dir="$REPO_DIR/articles/$yy/$mm"
    dest="$dest_dir/${date}_001.reading.html"
    web_path="/outward-reading/articles/$yy/$mm/${date}_001.reading.html"
    mkdir -p "$dest_dir"

    echo "== 1/4 复制精读页 → $dest"
    cp "$html" "$dest"

    echo "== 2/4 更新 index.html（为 $date 条目加 readingPath）"
    node - "$INDEX" "$date" "$web_path" <<'NODE'
const fs = require('fs');
const [,, file, date, webPath] = process.argv;
let h = fs.readFileSync(file, 'utf8');
const re = new RegExp(
  '(publishDate:\\s*"' + date + '",\\n(\\s*)fileKey:\\s*"[^"]+",)');
if (h.includes('"' + webPath + '"')) {
  console.log('   该日期已有 readingPath，跳过');
} else if (re.test(h)) {
  h = h.replace(re,
    '$1\n$2readingPath: "' + webPath + '",');
  fs.writeFileSync(file, h);
  console.log('   已写入 readingPath:', webPath);
} else {
  console.error('   ✗ 未找到 publishDate 为 ' + date + ' 的文章条目（该日期可能尚未录入日历）');
  process.exit(1);
}
NODE

    echo "== 3/4 记入已处理清单"
    grep -qx "$date" "$MANIFEST" || echo "$date" >> "$MANIFEST"

    echo "== 4/4 提交并推送"
    cd "$REPO_DIR"
    git add "$dest" "$INDEX" "$MANIFEST"
    git commit -m "新增 $date 精读页并接入日历"
    git push
    echo ""
    echo "✅ 完成。GitHub Pages 部署约需 1-2 分钟，之后访问："
    echo "   https://taciloquy.github.io/outward-reading/  （选 ${date}，默认即精读页）"
    ;;

  *)
    sed -n '2,12p' "$0"
    ;;
esac
