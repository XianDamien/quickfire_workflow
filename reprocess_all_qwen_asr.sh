#!/bin/bash
# 批量重新处理所有批次的 qwen_asr

BATCHES=(
    "Abby61000_2025-11-05"
    "Niko60900_2025-10-12"
    "Niko60900_2025-11-12"
    "Niko60900_2025-11-14"
    "Niko60900_2025-11-19"
    "Niko60900_2025-12-15"
    "TestClass88888_2026-01-05"
    "TestClass99999_2026-01-05"
    "Zoe41900_2025-09-08"
    "Zoe41900_2025-10-24"
    "Zoe41900_2025-11-20"
    "Zoe51530_2025-09-08"
    "Zoe51530_2025-12-16"
    "Zoe61330_2025-12-15"
    "Zoe61330_2025-12-16"
    "Zoe61330_2025-12-29"
    "Zoe61330_2025-12-30"
    "Zoe70930_2025-11-14"
)

echo "=========================================="
echo "开始批量重新处理 qwen_asr"
echo "总批次数: ${#BATCHES[@]}"
echo "=========================================="
echo ""

TOTAL=${#BATCHES[@]}
CURRENT=1

for batch in "${BATCHES[@]}"; do
    echo ""
    echo "=========================================="
    echo "[$CURRENT/$TOTAL] 处理批次: $batch"
    echo "=========================================="

    python3 scripts/main.py --archive-batch "$batch" --only qwen_asr --force

    if [ $? -eq 0 ]; then
        echo "✅ 批次 $batch 处理成功"
    else
        echo "❌ 批次 $batch 处理失败"
    fi

    CURRENT=$((CURRENT + 1))
    echo ""
done

echo ""
echo "=========================================="
echo "所有批次处理完成！"
echo "=========================================="
