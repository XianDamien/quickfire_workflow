#!/bin/bash
# clean_qwen_artifacts.sh
# 删除所有批次的 2_qwen_asr*.json 文件

ARCHIVE_DIR="archive"

echo "开始清理 Qwen ASR 产物..."
echo "警告: 此操作将删除所有 2_qwen_asr*.json 文件"
echo ""

read -p "确认继续？(yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "操作已取消"
  exit 0
fi

echo ""
total_files=0

for batch_dir in "$ARCHIVE_DIR"/*; do
  if [ ! -d "$batch_dir" ]; then
    continue
  fi

  batch=$(basename "$batch_dir")

  for student_dir in "$batch_dir"/*; do
    if [ ! -d "$student_dir" ]; then
      continue
    fi

    student=$(basename "$student_dir")

    # 检查并删除 qwen ASR 产物
    if ls "$student_dir"/2_qwen_asr*.json 1> /dev/null 2>&1; then
      file_count=$(ls "$student_dir"/2_qwen_asr*.json 2>/dev/null | wc -l)
      rm "$student_dir"/2_qwen_asr*.json 2>/dev/null
      total_files=$((total_files + file_count))

      echo "✓ Cleaned: $batch/$student ($file_count files)"
    fi
  done
done

echo ""
echo "清理完成！总共删除了 $total_files 个文件"
