#!/bin/bash
# 批处理服务端测试脚本

set -e

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
BATCH="${1:-Zoe61330_2025-12-15}"
MODE="${2:-asr}"

echo "=========================================="
echo "  批处理服务端测试"
echo "=========================================="
echo "  服务端: $BASE_URL"
echo "  批次: $BATCH"
echo "  模式: $MODE"
echo "=========================================="

# 1. 创建任务
echo ""
echo "1. 创建任务..."
RESPONSE=$(curl -s -X POST "$BASE_URL/jobs" \
  -H 'Content-Type: application/json' \
  -d "{\"mode\":\"$MODE\",\"archive_batch\":\"$BATCH\"}")

JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')
echo "   ✓ Job ID: $JOB_ID"

# 2. 查询状态
echo ""
echo "2. 查询任务状态..."
sleep 2
STATUS_RESPONSE=$(curl -s "$BASE_URL/jobs/$JOB_ID")
STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
echo "   ✓ Status: $STATUS"

# 3. 增量获取日志
echo ""
echo "3. 增量获取日志（前 5 次）..."
CURSOR=0
for i in {1..5}; do
  sleep 3
  LOG_RESPONSE=$(curl -s "$BASE_URL/jobs/$JOB_ID/logs?cursor=$CURSOR")
  CURSOR=$(echo "$LOG_RESPONSE" | jq -r '.next_cursor')
  STATUS=$(echo "$LOG_RESPONSE" | jq -r '.status')
  HAS_MORE=$(echo "$LOG_RESPONSE" | jq -r '.has_more')
  LOGS=$(echo "$LOG_RESPONSE" | jq -r '.logs')

  echo "   第 $i 次轮询 - Status: $STATUS, Cursor: $CURSOR, Has More: $HAS_MORE"
  if [ -n "$LOGS" ]; then
    echo "$LOGS" | head -n 5
  fi

  if [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ]; then
    echo "   ✓ 任务已完成"
    break
  fi
done

# 4. 获取结果
echo ""
echo "4. 获取结果..."
sleep 2
RESULT=$(curl -s "$BASE_URL/jobs/$JOB_ID/result")
echo "$RESULT" | jq '.'

echo ""
echo "=========================================="
echo "  测试完成"
echo "=========================================="
echo "Job ID: $JOB_ID"
echo ""
echo "查看完整日志:"
echo "  curl \"$BASE_URL/jobs/$JOB_ID/logs?cursor=0\" | jq -r '.logs'"
