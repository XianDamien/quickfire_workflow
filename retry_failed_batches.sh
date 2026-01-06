#!/bin/bash
# 重新处理失败的批次

FAILED_BATCHES=(
    "Abby61000_2025-11-05"
    "Niko60900_2025-10-12"
    "Niko60900_2025-11-12"
    "Niko60900_2025-12-15"
    "Zoe41900_2025-09-08"
    "Zoe51530_2025-12-16"
    "Zoe61330_2025-12-15"
    "Zoe61330_2025-12-16"
    "Zoe61330_2025-12-29"
    "Zoe61330_2025-12-30"
)

echo "=========================================="
echo "重新处理失败的批次"
echo "总批次数: ${#FAILED_BATCHES[@]}"
echo "=========================================="
echo ""

TOTAL=${#FAILED_BATCHES[@]}
CURRENT=1
SUCCESS=0
FAILED=0

for batch in "${FAILED_BATCHES[@]}"; do
    echo ""
    echo "=========================================="
    echo "[$CURRENT/$TOTAL] 重试批次: $batch"
    echo "=========================================="

    # 添加 5 秒延迟以避免 API 限流
    if [ $CURRENT -gt 1 ]; then
        echo "⏳ 等待 5 秒避免 API 限流..."
        sleep 5
    fi

    python3 scripts/main.py --archive-batch "$batch" --only qwen_asr --force

    if [ $? -eq 0 ]; then
        echo "✅ 批次 $batch 处理成功"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "❌ 批次 $batch 处理失败"
        FAILED=$((FAILED + 1))
    fi

    CURRENT=$((CURRENT + 1))
    echo ""
done

echo ""
echo "=========================================="
echo "重试完成！"
echo "成功: $SUCCESS"
echo "失败: $FAILED"
echo "=========================================="
