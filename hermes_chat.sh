#!/bin/bash
# Hermes 钉钉对话工具
# 用法: ./hermes_chat.sh "你的消息" [--silent]

HERMES_URL="http://localhost:8002"
USER_ID=${USER:-"cli_user"}

MESSAGE="$1"
MODE="${2:---chat}"

if [ -z "$MESSAGE" ]; then
    echo "用法: $0 \"你的消息\" [--silent]"
    echo ""
    echo "选项:"
    echo "  --silent   仅在终端显示结果，不发送到钉钉群"
    echo ""
    echo "示例:"
    echo "  $0 \"你好\""
    echo "  $0 \"帮我分析数据\" --silent"
    exit 1
fi

if [ "$MODE" == "--silent" ]; then
    ENDPOINT="/chat/silent"
    echo "🤖 发送消息到 Hermes (静默模式)..."
else
    ENDPOINT="/chat"
    echo "🤖 发送消息到 Hermes (结果将发送到钉钉群)..."
fi

echo "📝 消息: $MESSAGE"
echo "👤 用户: $USER_ID"
echo ""

RESPONSE=$(curl -s -X POST "${HERMES_URL}${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"${MESSAGE}\", \"user_id\": \"${USER_ID}\"}")

echo "✅ Hermes 回复:"
echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('response', d.get('error', '未知错误')))"
