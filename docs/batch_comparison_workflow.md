# 批量对比测试工作流指南

## 概述

本文档说明如何使用自动化脚本批量运行 **ASR+文本** vs **音频直传** 对比测试，并分析结果。

## 测试批次

```
Zoe61330_2025-12-29
Zoe61330_2025-12-15
Zoe41900_2025-11-20
Zoe41900_2025-10-24
Abby61000_2025-11-05
Niko60900_2025-10-12
```

## 一键运行全流程

### 1. 设置环境变量（一次性）

```bash
export GEMINI_API_KEY=你的密钥
export HTTPS_PROXY=http://127.0.0.1:7890
```

### 2. 运行批量测试

```bash
./run_batch_comparison.sh
```

**功能**:
- 对 6 个批次分别运行方案A和方案B，各2次
- 总计 24 次运行 (6批次 × 2方案 × 2次)
- 自动记录所有日志到 `reports/batch_comparison_<时间戳>/`
- 运行完成后自动调用结果分析

**输出**:
- `reports/batch_comparison_YYYYMMDD_HHMMSS/master_log.txt` - 总日志
- `reports/batch_comparison_YYYYMMDD_HHMMSS/methodA_*.log` - 方案A详细日志
- `reports/batch_comparison_YYYYMMDD_HHMMSS/methodB_*.log` - 方案B详细日志
- `reports/batch_comparison_YYYYMMDD_HHMMSS/analysis_summary.txt` - 分析报告
- `reports/batch_comparison_YYYYMMDD_HHMMSS/detailed_results.json` - JSON格式详细数据

## 手动运行单个测试

### 方案 A: ASR + 文本

```bash
uv run python scripts/main.py \
  --archive-batch <批次名> \
  --only cards \
  --annotator gemini-3-pro-preview
```

### 方案 B: 音频直传

```bash
uv run python scripts/gemini_batch_audio.py run \
  --archive-batch <批次名> \
  --model gemini-3-pro-preview \
  --display-name "audio-<批次名>-r1"
```

## 检查任务状态

### 快速检查所有批次

```bash
uv run python check_batch_status.py
```

### 检查单个批次（详细）

```bash
uv run python check_batch_status.py --batch Niko60900_2025-10-12 -v
```

### 检查所有批次（详细）

```bash
uv run python check_batch_status.py --all -v
```

## 如何判断是否已成功提交

### 提交成功的标记

1. **命令行输出**:
   - 方案A: 看到 `Run ID: <run_id>` 输出
   - 方案B: 看到 `✅ 批次任务已提交` 和 `Job Name: batches/xxx`

2. **文件系统标记**:
   - 方案A: 创建了 `archive/<batch>/runs/gemini-3-pro-preview/<run_id>/`
   - 方案B: 创建了 `archive/<batch>/_batch_runs/<run_id>/`
   - 两者都有 `batch_manifest.json` 文件
   - `batch_manifest.json` 中有 `job_name` 字段

3. **使用状态检查工具**:
   ```bash
   uv run python check_batch_status.py --batch <批次名>
   ```

   输出示例:
   ```
   方案 B (音频直传):
     总运行数: 3
     已提交: 3    ← 这个数字表示成功提交的任务数
     已完成: 3
     失败: 0
   ```

### 完成的标记

1. **batch_manifest.json 中的关键字段**:
   ```json
   {
     "final_state": "JOB_STATE_SUCCEEDED",
     "timing": {
       "submitted_at": "2026-01-07T00:04:46.981727",
       "completed_at": "2026-01-07T00:06:19.521719"
     }
   }
   ```

2. **文件系统标记**:
   - 有 `batch_output.jsonl` 文件
   - 有 `students/` 目录，包含每个学生的 `4_llm_annotation.json`

3. **状态检查工具显示** `✅` 图标

## 结果分析

### 查看详细分析报告

```bash
uv run python analyze_comparison_results.py
```

### 导出 JSON 格式报告

```bash
uv run python analyze_comparison_results.py --export-json results.json
```

### 分析指定批次

```bash
uv run python analyze_comparison_results.py --batches Niko60900_2025-10-12 Zoe61330_2025-12-15
```

## 关键指标说明

### 1. 成功率
- `success_count / total_students × 100%`
- 表示有多少学生成功完成评分

### 2. 失败学生名单
- `failed_students` 字段
- 列出所有 `status != 'success'` 的学生

### 3. Token 使用
- `total_input_tokens`: 输入 token 数
- `total_output_tokens`: 输出 token 数
- `total_tokens`: 总 token 数

### 4. 耗时统计
- `duration_seconds`: 总处理时间（秒）
- 可计算分钟: `duration_seconds // 60`

### 5. 成绩分布
```json
{
  "grade_distribution": {
    "A": 5,
    "B": 3,
    "C": 2
  }
}
```

## 数据存储位置

### 方案 A (ASR + 文本)
```
archive/<batch>/runs/gemini-3-pro-preview/<run_id>/
├── batch_manifest.json          # 运行元数据
├── batch_input.jsonl            # 输入请求
├── batch_output.jsonl           # API 原始输出
├── batch_report.json            # 运行报告
└── students/                    # 学生结果
    └── <student>/
        └── 4_llm_annotation.json
```

### 方案 B (音频直传)
```
archive/<batch>/_batch_runs/<run_id>/
├── batch_manifest.json          # 运行元数据（包含 audio_files 映射）
├── batch_input.jsonl            # 输入请求（含音频 URI）
├── batch_output.jsonl           # API 原始输出
├── batch_report.json            # 运行报告
└── students/                    # 学生结果
    └── <student>/
        └── 4_llm_annotation.json
```

## 工作流总结

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 准备环境                                                  │
│    export GEMINI_API_KEY=...                                │
│    export HTTPS_PROXY=...                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 运行批量测试                                              │
│    ./run_batch_comparison.sh                                │
│                                                              │
│    → 6批次 × 2方案 × 2次 = 24次运行                         │
│    → 每次运行自动记录日志                                   │
│    → 自动保存到 reports/batch_comparison_<时间>/            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 检查任务状态                                              │
│    uv run python check_batch_status.py                      │
│                                                              │
│    查看:                                                     │
│    - 提交状态（已提交/未提交）                              │
│    - 完成状态（成功/失败/进行中）                           │
│    - 学生统计（总数/成功/失败）                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 分析结果                                                  │
│    uv run python analyze_comparison_results.py              │
│                                                              │
│    提取指标:                                                 │
│    - 成功率                                                  │
│    - 失败学生名单                                            │
│    - Token 使用量                                            │
│    - 处理耗时                                                │
│    - 成绩分布                                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 查看报告                                                  │
│    - master_log.txt: 完整执行日志                           │
│    - analysis_summary.txt: 分析总结                         │
│    - detailed_results.json: JSON 格式详细数据               │
└─────────────────────────────────────────────────────────────┘
```

## 自动化方案特点

✅ **一键运行**: 单个命令启动全部测试
✅ **自动记录**: 所有日志自动保存
✅ **状态可查**: 随时检查任务提交和完成状态
✅ **结果汇总**: 自动提取和分析关键指标
✅ **失败处理**: 自动记录失败学生和错误信息
✅ **并发控制**: 自动添加延迟避免 API 限流

## 故障排查

### 问题: 如何知道任务是否提交成功？

**解决方案**:
```bash
# 方法 1: 使用状态检查工具
uv run python check_batch_status.py --batch <批次名> -v

# 方法 2: 手动检查目录
ls -la archive/<批次名>/_batch_runs/

# 方法 3: 查看 manifest 文件
cat archive/<批次名>/_batch_runs/<run_id>/batch_manifest.json | jq .job_name
```

### 问题: 任务提交了但一直不完成？

**检查**:
1. 查看 `batch_manifest.json` 的 `final_state` 字段
2. 如果是 `null` 或空，说明还在处理中
3. 可以用 Gemini Batch API 查询任务状态

### 问题: 部分学生失败了？

**查找失败学生**:
```bash
# 使用分析脚本
uv run python analyze_comparison_results.py --batch <批次名>

# 或手动查询
cat archive/<batch>/_batch_runs/<run_id>/batch_manifest.json | \
  jq -r '.student_results[] | select(.status!="success") | .student'
```

## 常见问题

**Q: 可以同时运行多个批次吗？**
A: 可以，但建议添加延迟避免 API 限流。脚本已内置 2 秒延迟。

**Q: 如何只运行某几个批次？**
A: 编辑 `run_batch_comparison.sh` 中的 `BATCHES` 数组。

**Q: 能否只运行一次而不是两次？**
A: 修改 `run_batch_comparison.sh` 中的 `NUM_RUNS=1`。

**Q: 结果保存在哪里？**
A:
- 方案A: `archive/<batch>/runs/gemini-3-pro-preview/<run_id>/`
- 方案B: `archive/<batch>/_batch_runs/<run_id>/`
- 日志: `reports/batch_comparison_<时间>/`

**Q: 如何重新运行失败的任务？**
A: 直接重新运行对应的批次和方案命令即可，会创建新的 run_id。
