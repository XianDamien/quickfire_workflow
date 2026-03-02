# Audio vs ASR 批量对比测试总结

生成时间: 2026-01-07 05:32:36
**最新版本**: 已修复成功率、token、时间等所有指标

## 📊 执行概况

### Fetch统计
- **总批次数**: 14个PENDING批次
- **成功Fetch**: 14个（100%）
- **生成文件**: `fetch_results_20260107_052259.json`

### 报告统计
- **对比总览**: 36行（36个运行实例）
- **错误详情**: 123条错误记录
- **批次汇总**: 13个批次

## 📈 批次分布

### 已提交并完成的批次

#### Niko60900系列（3个批次）
- `Niko60900_2025-10-12`: Audio + ASR ✅
- `Niko60900_2025-11-12`: Audio ✅
- `Niko60900_2025-12-15`: Audio + ASR ✅

#### Zoe61330系列（3个批次）
- `Zoe61330_2025-12-15`: Audio + ASR ✅
- `Zoe61330_2025-12-16`: ASR ✅
- `Zoe61330_2025-12-30`: ASR ✅

#### Zoe51530系列（1个批次）
- `Zoe51530_2025-12-16`: Audio + ASR ✅

#### Zoe41900系列（3个批次）
- `Zoe41900_2025-09-08`: ASR ✅
- `Zoe41900_2025-10-24`: ASR ✅
- `Zoe41900_2025-11-20`: ASR ✅

#### 其他批次
- `Abby61000_2025-11-05`: ASR ✅
- `Zoe51530_2025-09-08`: ASR ✅

## 📋 报告内容说明

### Sheet 1: 对比总览
包含字段：
- 批次、方案（Audio/ASR）、Run ID
- 学生数、成功数、失败数、成功率
- 总Tokens、输入Tokens、输出Tokens、平均Tokens/学生
- 处理时间（秒）
- A/B/C等级分布
- 错误数

### Sheet 2: 错误详情
包含字段：
- 批次、Run ID、学生
- 题号、时间戳、题目
- 期望答案、实际回答
- 错误类型、成绩

错误类型包括：
- `NO_ANSWER`: 学生未回答
- `MEANING_ERROR`: 语义错误
- 其他类型...

### Sheet 3: 批次汇总
包含字段：
- 批次名称
- Audio运行数、ASR运行数、总运行数
- Audio总学生数、ASR总学生数

## 🔍 关键发现

### Token使用情况
- Audio版本和ASR版本的token使用量差异
- 平均每学生的token消耗
- 输入/输出token比例

### 成功率对比
- Audio方案的成功率
- ASR方案的成功率
- 失败原因分析

### 错误类型分布
- 123条错误记录中的错误类型统计
- 不同批次的错误模式
- 学生答题质量分析

### 处理时间
- Audio版本的处理时间
- ASR版本的处理时间
- 批量处理效率

## 📁 生成的文件

1. **对比报告（Excel）**
   - 主报告: `reports/audio_vs_asr_comparison_FINAL.xlsx`
   - 时间戳版: `reports/audio_vs_asr_comparison_20260107_052804.xlsx`

2. **Fetch结果（JSON）**
   - `fetch_results_20260107_052259.json`

3. **批次状态报告（文本）**
   - `reports/batch_summary_20260107_050258.txt`

## 💡 使用建议

1. **查看对比数据**: 打开 `audio_vs_asr_comparison_FINAL.xlsx` 查看详细对比
2. **分析错误**: 在"错误详情"sheet中筛选特定批次或错误类型
3. **评估效率**: 对比不同方案的token使用和处理时间
4. **质量评估**: 分析成绩分布和错误模式

## 🔄 后续操作

如需重新生成报告：
```bash
uv run python generate_comparison_report.py
```

如需再次fetch批次结果：
```bash
HTTPS_PROXY=http://127.0.0.1:7890 uv run python fetch_all_pending.py
```

如需检查批次状态：
```bash
HTTPS_PROXY=http://127.0.0.1:7890 uv run python check_batch_status.py
```

---

**生成工具**: `generate_comparison_report.py`
**数据来源**: `/Users/damien/Desktop/Venture/quickfire_workflow/archive`
