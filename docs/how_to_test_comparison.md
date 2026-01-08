# ASR vs 音频方案对比测试指南

本指南提供客观的测试方法，帮助你收集两种方案的数据并生成对比报告。

---

## 前置准备

### 1. 环境配置

```bash
# 安装依赖
uv sync

# 设置环境变量
export GEMINI_API_KEY=<your_api_key>
export HTTPS_PROXY=http://127.0.0.1:7890
```

### 2. 选择测试数据

```bash
# 查看可用的测试班级
ls archive/

# 确认班级有完整的学生音频数据
ls archive/<batch_id>/

# 示例
ls archive/Zoe61330_2025-12-15/
```

---

## 测试步骤

### 方案 A: ASR + 文本方案

这个方案先将音频转为文本，再由 LLM 根据文本时间戳进行评分。

```bash
# 运行完整流程（如果还没有 ASR 数据）
uv run python scripts/main.py \
  --archive-batch <batch_id> \
  --annotator gemini-3-pro-preview

# 或者只运行评分阶段（如果已有 ASR 数据）
uv run python scripts/main.py \
  --archive-batch <batch_id> \
  --annotator gemini-3-pro-preview \
  --only cards
```

**查看结果**：
```bash
# 找到最新的运行记录
ls -lt archive/<batch_id>/_batch_runs/ | head

# 查看详细结果
cat archive/<batch_id>/_batch_runs/<run_id>/batch_manifest.json | jq '.'
```

---

### 方案 B: 音频直传方案

这个方案直接将音频文件发送给 LLM，由 LLM 听音频后进行评分。

```bash
GEMINI_API_KEY=<your_api_key> \
HTTPS_PROXY=http://127.0.0.1:7890 \
uv run python scripts/gemini_batch_audio.py submit \
  --archive-batch <batch_id> \
  --display-name "audio-test-1"

# 稍后拉取结果（使用 submit 输出的 manifest 路径）
uv run python scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json
```

**查看结果**：
```bash
# 找到音频测试记录
ls -lt archive/<batch_id>/_batch_runs/*.audio/ | head

# 查看详细结果
cat archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json | jq '.'
```

---

## 建议的测试计划

为了获得可靠的数据，建议：

### 单次测试
如果只想快速对比一次：
```bash
# 1. 运行 ASR 方案
uv run python scripts/main.py --archive-batch <batch_id> --only cards

# 2. 提交音频方案
GEMINI_API_KEY=<key> HTTPS_PROXY=http://127.0.0.1:7890 \
uv run python scripts/gemini_batch_audio.py submit \
  --archive-batch <batch_id> --display-name "audio-test-1"

# 3. 稍后拉取音频结果
uv run python scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json
```

### 多次测试（验证稳定性）
如果想验证稳定性，建议对每种方案运行多次：

```bash
# ASR 方案 - 测试 3 次
for i in 1 2 3; do
  echo "=== ASR 测试 $i ==="
  uv run python scripts/main.py \
    --archive-batch <batch_id> \
    --only cards
  sleep 600  # 等待 10 分钟
done

# 音频方案 - 测试 3 次（先 submit）
for i in 1 2 3; do
  echo "=== 音频测试 $i ==="
  GEMINI_API_KEY=<key> HTTPS_PROXY=http://127.0.0.1:7890 \
  uv run python scripts/gemini_batch_audio.py submit \
    --archive-batch <batch_id> \
    --display-name "audio-test-$i"
done

# 统一拉取（只拉当前批次的音频运行）
for manifest in archive/<batch_id>/_batch_runs/*.audio/batch_manifest.json; do
  uv run python scripts/gemini_batch_audio.py fetch --manifest "$manifest"
done
```

---

## 生成对比报告

使用对比工具生成 Excel 报告：

```bash
# 语法
uv run python scripts/compare_asr_audio.py <batch_id> <run_id1> <run_id2> [run_id3] ...

# 示例：对比 1 个 ASR 测试和 3 个音频测试
uv run python scripts/compare_asr_audio.py \
  Zoe61330_2025-12-15 \
  002933 \
  110826 \
  192906 \
  200220
```

**说明**：
- `batch_id`：班级目录名
- `run_id`：运行 ID 的关键部分（如 `002933` 可以匹配 `20260106_002933_eb28926`）

**输出**：
- Excel 文件：`archive/<batch_id>/comparison_report_<run_ids>.xlsx`
- 包含 2 个工作表：
  1. **核心指标**：成功率、Token 消耗、处理时间、失败学生数等
  2. **错误详情**：逐条错误题目明细（issue_type != null）

---

## 查看测试结果

### 命令行快速查看

```bash
# 查看关键指标
jq '{
  run_id: .run_id,
  mode: .mode,
  success: "\(.statistics.success_count)/\(.statistics.students_count)",
  total_tokens: .token_usage.total_tokens,
  thoughts_tokens: .token_usage.thoughts_tokens,
  processing_time: .timing.api_processing_time_seconds
}' archive/<batch_id>/_batch_runs/<run_id>/batch_manifest.json
```

### 完整的成绩报告

生成包含所有 archive 数据的总表：

```bash
uv run python scripts/consolidate_grades.py
```

这会生成 `archive/consolidated_grades.xlsx`，包含：
- 成绩总表
- 错误详情
- 未测试数据

---

## 数据收集清单

对比两种方案时，关注以下指标：

### 可靠性指标
- [ ] 成功率（成功学生数 / 总学生数）
- [ ] 失败模式（哪些学生失败，原因是什么）

### 成本指标
- [ ] Total Tokens（总 Token 消耗）
- [ ] Thoughts Tokens（思考 Token，通常占大头）
- [ ] Prompt Tokens（输入 Token）
- [ ] 处理时间（秒）

### 质量指标
- [ ] 成绩分布（A/B/C 的比例）
- [ ] 错误检测的细节（是否有漏检或误检）

---

## 测试示例

### 示例 1: Zoe61330_2025-12-15（5 名学生）

```bash
# 1. ASR 方案
uv run python scripts/main.py \
  --archive-batch Zoe61330_2025-12-15 \
  --only cards

# 2. 音频方案（提交 3 次）
for i in 1 2 3; do
  GEMINI_API_KEY=<key> HTTPS_PROXY=http://127.0.0.1:7890 \
  uv run python scripts/gemini_batch_audio.py submit \
    --archive-batch Zoe61330_2025-12-15 \
    --display-name "audio-test-$i"
done

# 2.1 拉取结果
for manifest in archive/Zoe61330_2025-12-15/_batch_runs/*.audio/batch_manifest.json; do
  uv run python scripts/gemini_batch_audio.py fetch --manifest "$manifest"
done

# 3. 生成对比报告
uv run python scripts/compare_asr_audio.py \
  Zoe61330_2025-12-15 \
  002933 110826 192906 200220
```

**查看结果**：
- Excel 报告：`archive/Zoe61330_2025-12-15/comparison_report_002933-110826-192906-200220.xlsx`

---

## 常见问题

### Q1: 音频上传失败
**现象**: `Failed to upload audio file`

**解决**:
```bash
# 确认代理设置
echo $HTTPS_PROXY

# 如果为空，重新设置
export HTTPS_PROXY=http://127.0.0.1:7890
```

### Q2: ASR 方案找不到时间戳
**现象**: `No ASR timestamp found`

**解决**:
```bash
# 先运行 ASR 转写
uv run python scripts/main.py --archive-batch <batch_id> --only qwen_asr

# 再运行时间戳生成
uv run python scripts/main.py --archive-batch <batch_id> --only timestamps

# 最后运行评分
uv run python scripts/main.py --archive-batch <batch_id> --only cards
```

### Q3: 如何重新测试
如果需要重新运行测试：
```bash
# 方案 A (ASR)：直接重新运行即可，会创建新的 run
uv run python scripts/main.py --archive-batch <batch_id> --only cards

# 方案 B (音频)：先提交，再拉取
GEMINI_API_KEY=<key> HTTPS_PROXY=http://127.0.0.1:7890 \
uv run python scripts/gemini_batch_audio.py submit \
  --archive-batch <batch_id> --display-name "retest"

uv run python scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json
```

### Q4: 找不到 run_id
```bash
# 列出所有运行记录
ls archive/<batch_id>/_batch_runs/

# 查看运行记录详情
cat archive/<batch_id>/_batch_runs/<run_dir>/batch_manifest.json | jq '.run_id'
```

---

## 自动化测试脚本

创建 `test_comparison.sh`：

```bash
#!/bin/bash
set -e

BATCH="${1:-Zoe61330_2025-12-15}"
AUDIO_TESTS="${2:-3}"  # 默认音频测试 3 次

echo "=========================================="
echo "  ASR vs 音频方案对比测试"
echo "=========================================="
echo "  批次: $BATCH"
echo "  音频测试次数: $AUDIO_TESTS"
echo "=========================================="

# ASR 方案
echo ""
echo "运行 ASR 方案..."
uv run python scripts/main.py --archive-batch "$BATCH" --only cards

# 音频方案：先 submit
for i in $(seq 1 $AUDIO_TESTS); do
  echo ""
  echo "提交音频方案 (第 $i/$AUDIO_TESTS 次)..."
  GEMINI_API_KEY=$GEMINI_API_KEY HTTPS_PROXY=$HTTPS_PROXY \
  uv run python scripts/gemini_batch_audio.py submit \
    --archive-batch "$BATCH" \
    --display-name "audio-test-$i"
done

# 拉取最近的音频结果
for manifest in $(ls -t archive/$BATCH/_batch_runs/*.audio/batch_manifest.json | head -n "$AUDIO_TESTS"); do
  uv run python scripts/gemini_batch_audio.py fetch --manifest "$manifest"
done

echo ""
echo "=========================================="
echo "  测试完成"
echo "=========================================="
echo "结果位置: archive/$BATCH/_batch_runs/"
echo ""
echo "使用以下命令生成对比报告:"
echo "  uv run python scripts/compare_asr_audio.py $BATCH <run_id1> <run_id2> ..."
```

**使用方法**：
```bash
chmod +x test_comparison.sh

# 使用默认设置
./test_comparison.sh

# 自定义批次和测试次数
./test_comparison.sh Zoe61330_2025-12-15 3
```

---

## 附录：数据文件位置

```
archive/<batch_id>/
├── _batch_runs/                      # 所有测试运行记录
│   ├── 20260106_002933_eb28926/      # ASR 方案运行
│   │   └── batch_manifest.json
│   ├── 20260106_110826.audio/        # 音频方案运行 1
│   │   └── batch_manifest.json
│   ├── 20260106_192906.audio/        # 音频方案运行 2
│   │   └── batch_manifest.json
│   └── 20260106_200220.audio/        # 音频方案运行 3
│       └── batch_manifest.json
└── comparison_report_*.xlsx          # 生成的对比报告
```

---

**文档版本**: 2026-01-06
**说明**: 本指南提供客观的测试方法，不预设任何方案的优劣。请根据实际测试数据得出结论。
