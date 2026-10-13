#!/bin/bash
# 自动重试推送脚本
# 每隔 5 分钟推送一次，直到成功

cd ~/outward-reading-site-prod

echo "🚀 开始自动推送..."
echo "⏰ 每 5 分钟重试一次，直到成功"

MAX_RETRIES=20
RETRY_INTERVAL=300  # 5 分钟 = 300 秒

for ((i=1; i<=MAX_RETRIES; i++)); do
  echo ""
  echo "📅 第 $i 次尝试推送..."
  
  # 先提交所有更改
  git add -A
  git commit -m "新增 10 月 14 日文章" 2>/dev/null || echo "ℹ️  没有新的更改"
  
  # 尝试推送
  if git push origin main 2>&1; then
    echo ""
    echo "✅ 推送成功！"
    exit 0
  fi
  
  echo "⚠️  第 $i 次推送失败"
  
  if [ $i -lt $MAX_RETRIES ]; then
    echo "⏰ 等待 $((RETRY_INTERVAL/60)) 分钟后重试..."
    sleep $RETRY_INTERVAL
  fi
done

echo ""
echo "❌ 已经重试 $MAX_RETRIES 次，还是推送失败"
exit 1
