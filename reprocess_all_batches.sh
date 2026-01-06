#!/bin/bash
# reprocess_all_batches.sh
# 重新运行所有批次的 qwen_asr 阶段

BATCHES=(
  "Abby61000_2025-11-05"
  "Niko60900_2025-10-12"
  "Niko60900_2025-11-12"
  "Niko60900_2025-11-14"
  "Niko60900_2025-11-19"
  "Niko60900_2025-12-15"
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

LOG_FILE="reprocess_$(date +%Y%m%d_%H%M%S).log"

echo "开始重新处理所有批次 (只运行 qwen_asr 阶段)" | tee "$LOG_FILE"
echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

success_count=0
failed_count=0

for batch in "${BATCHES[@]}"; do
  echo "========================================" | tee -a "$LOG_FILE"
  echo "Processing batch: $batch" | tee -a "$LOG_FILE"
  echo "Started at: $(date)" | tee -a "$LOG_FILE"

  python3 scripts/main.py --archive-batch "$batch" --only qwen_asr 2>&1 | tee -a "$LOG_FILE"

  if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "✓ Success: $batch" | tee -a "$LOG_FILE"
    success_count=$((success_count + 1))
  else
    echo "✗ Failed: $batch" | tee -a "$LOG_FILE"
    failed_count=$((failed_count + 1))
  fi

  echo "Finished at: $(date)" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
done

echo "========================================" | tee -a "$LOG_FILE"
echo "所有批次处理完成" | tee -a "$LOG_FILE"
echo "成功: $success_count" | tee -a "$LOG_FILE"
echo "失败: $failed_count" | tee -a "$LOG_FILE"
echo "详细日志: $LOG_FILE" | tee -a "$LOG_FILE"
