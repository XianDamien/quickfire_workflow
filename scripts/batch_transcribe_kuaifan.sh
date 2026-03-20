#!/usr/bin/env zsh
# 快反录音批量转写脚本（带跳过逻辑）
# 逐文件检查输出是否存在，跳过已完成，THREADS 控制并发避免限流
# 用法：zsh scripts/batch_transcribe_kuaifan.sh

SCRIPT_DIR="$HOME/.claude/skills/qwen-asr-transcriber/scripts"
CONTEXT_FILE="$(cd "$(dirname "$0")" && pwd)/../prompts/asr_context/system_kuaifan.md"
THREADS=4

DIRS=(
  "/Users/damien/Desktop/机构资料/R1 快反录音"
  "/Users/damien/Desktop/机构资料/R2 快反录音"
  "/Users/damien/Desktop/机构资料/R3 快反录音"
)

count_total() { find "$1" -maxdepth 1 -name "*.m4a" | wc -l | tr -d ' '; }
count_done()  { find "$1" -mindepth 2 -name "*.txt" -not -name "meta*" 2>/dev/null | wc -l | tr -d ' '; }

echo "======================================"
echo "  快反录音批量转写"
echo "======================================"
echo ""

for dir in "${DIRS[@]}"; do
  name=$(basename "$dir")
  total=$(count_total "$dir")
  skipped=0

  echo "--------------------------------------"
  echo "▶ $name（共 $total 个文件）"
  echo "--------------------------------------"

  # 收集待处理文件，写入临时列表（null-delimited 避免特殊字符问题）
  pending_list=$(mktemp)
  for f in "$dir"/*.m4a; do
    [[ -f "$f" ]] || continue
    stem=$(basename "$f" .m4a)
    out_txt="$dir/$stem/$stem.txt"
    if [[ -f "$out_txt" ]]; then
      (( skipped++ ))
    else
      printf '%s\0' "$f" >> "$pending_list"
    fi
  done

  pending_count=$(tr -cd '\0' < "$pending_list" | wc -c | tr -d ' ')
  echo "  跳过已完成：$skipped，待处理：$pending_count"

  if [[ $pending_count -eq 0 ]]; then
    echo "✓ 全部已完成，跳过"
    rm -f "$pending_list"
    echo ""
    continue
  fi

  # 通过 xargs -0 并发转写，null-delimited 安全处理含引号的文件名
  xargs -0 -P "$THREADS" -I {} \
    zsh -c 'cd "$1" && uv run qwen_asr.py "$2" --context "$(cat "$3")" 2>&1 | grep -E "(Saved|Failed|Duration|Processing)"' \
    _ "$SCRIPT_DIR" {} "$CONTEXT_FILE" < "$pending_list"

  rm -f "$pending_list"

  done_after=$(count_done "$dir")
  echo ""
  echo "✓ $name 完成：$done_after/$total"
  echo ""
done

echo "======================================"
echo "全部完成！"
total_done=0
for dir in "${DIRS[@]}"; do
  d=$(count_done "$dir")
  t=$(count_total "$dir")
  echo "  $(basename "$dir"): $d/$t"
  (( total_done += d ))
done
echo "  合计：$total_done/540"
echo "======================================"
