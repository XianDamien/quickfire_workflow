#!/bin/bash
# backup_qwen_artifacts.sh
# 备份所有批次的 2_qwen_asr*.json 文件

BACKUP_DIR="archive_backup_qwen_hotwords"
ARCHIVE_DIR="archive"

echo "开始备份 Qwen ASR 产物..."
echo "备份目录: $BACKUP_DIR"
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

    # 检查是否有 2_qwen_asr*.json 文件
    if ls "$student_dir"/2_qwen_asr*.json 1> /dev/null 2>&1; then
      # 创建备份目录
      mkdir -p "$BACKUP_DIR/$batch/$student"

      # 备份 qwen ASR 产物
      cp "$student_dir"/2_qwen_asr*.json "$BACKUP_DIR/$batch/$student/" 2>/dev/null

      file_count=$(ls "$student_dir"/2_qwen_asr*.json 2>/dev/null | wc -l)
      total_files=$((total_files + file_count))

      echo "✓ Backed up: $batch/$student ($file_count files)"
    fi
  done
done

echo ""
echo "备份完成！总共备份了 $total_files 个文件"
echo "备份位置: $BACKUP_DIR"
