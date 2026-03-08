---
name: qb-file-matcher
description: >
  Match ASR audio segment transcriptions to their corresponding question bank files.
  This skill should be used when identifying which specific question bank file
  (grammar or vocabulary) corresponds to a given classroom recording segment.
  Triggers include: "匹配题库", "match qb file", "找题库文件", "题库匹配",
  or when processing ASR segments that need question bank association.
---

# QB File Matcher

Match ASR 片段转录到对应的题库文件（grammar/*.json 或 vocabulary/*.json）。

## 核心脚本

`scripts/match_qb_file.py` — 三步法自动匹配

### 流程

1. **LLM 解析 ASR → 结构化 Q/A 列表**
   - grammar: 提取 `{question: "教师提问原文", answer: "标准答案"}`
   - vocabulary: 提取 `{question: "原始单词", answer: "释义"}`
   - 答案通常出现两次（学生先答 + 教师预录音频确认），取完整版

2. **Q/A 内容搜索题库索引**
   - 启动时预加载所有题库文件，构建 `{normalized_question → [文件名]}` 倒排索引
   - grammar 521+ 文件、vocabulary 692+ 文件，索引构建约需数秒
   - 用解析出的 question 精确匹配索引，统计各文件命中次数

3. **题目数量过滤**
   - 保留 `|file_entries - parsed_qa_count| ≤ tolerance`（默认 ±3）的候选
   - 所有通过过滤的候选交给 LLM

4. **LLM function calling 最终判断**
   - 工具：`read_qb_file`（查看候选内容）、`submit_answer`（提交匹配结果）
   - LLM 对比 Q/A 列表与候选文件内容，确认最佳匹配

### 输出

- 更新 `metadata.json`：写入 `qb_file` 字段 + `qb_matched_at`/`qb_matched_by`/`qb_match_usage`
- 详细结果：`qb_match_<model>.json`（含 parsed_qa、usage、reason）

## 使用方法

```bash
# 单个学生
uv run python scripts/match_qb_file.py --student Jean --class Niko60900_2026-02-03

# 全班（可并行多进程）
uv run python scripts/match_qb_file.py --class Niko60900_2026-02-03

# 覆盖已有结果
uv run python scripts/match_qb_file.py --student Jean --force

# 调整题目数量容差
uv run python scripts/match_qb_file.py --tolerance 5
```

### 并行运行（推荐）

脚本本身是串行处理片段的，单个学生含 3-4 个片段、每片段需 2 次 LLM 调用，串行跑全班非常慢。**必须按学生拆分为并行进程。**

**Claude Code 中运行**：对每个学生启动独立的后台 Bash 任务（`run_in_background: true`），所有学生同时执行：

```
# 对每个学生分别启动后台 Bash 任务，示例：
Bash(run_in_background=true): uv run python scripts/match_qb_file.py --student Lucy --class Zoe41900_2026-02-04 --force
Bash(run_in_background=true): uv run python scripts/match_qb_file.py --student Rico --class Zoe41900_2026-02-04 --force
Bash(run_in_background=true): uv run python scripts/match_qb_file.py --student Youyou --class Zoe41900_2026-02-04 --force
# ... 所有学生在同一条消息中并行发出，然后用 TaskOutput 收集结果
```

**Shell 中运行**：
```bash
for student in Lucy Rico Youyou; do
  uv run python scripts/match_qb_file.py --student $student --class Zoe41900_2026-02-04 --force &
done
wait
```

> **注意**：每个进程会独立构建题库索引（~数秒），但 LLM 调用是主要耗时项，并行收益远大于索引重复开销。

## 数据格式

### metadata.json（输入/输出）

旧格式（分类后、匹配前）：
```json
{
  "segments": {
    "2": {"type": "grammar"},
    "6": {"type": "vocabulary"}
  }
}
```

匹配后更新为：
```json
{
  "segments": {
    "2": {"type": "grammar", "qb_file": "R024-5W基础知识.json"},
    "6": {"type": "vocabulary", "qb_file": "V1-27-D2.json"}
  },
  "qb_matched_at": "2026-03-05T10:30:00Z",
  "qb_matched_by": "qwen3.5-plus",
  "qb_match_usage": {
    "input_tokens": 12345,
    "output_tokens": 678,
    "elapsed_s": 45.2
  }
}
```

新格式（ground_truth，含评估用 qb_file）：
```json
{
  "ground_truth": {
    "2/2_qwen_asr.json": {"type": "grammar", "qb_file": "R024-5W基础知识.json"}
  }
}
```

## 前置条件

- ASR 转录已完成（`<seg>/2_qwen_asr.json` 存在）
- 片段类型已分类（metadata.json 含 `type` 字段）— 使用 `classify_asr_type.py`
- `questionbank/grammar/` 和 `questionbank/vocabulary/` 目录存在
- 环境变量 `DASHSCOPE_API_KEY` 已配置

## 已验证效果

Jean 验证集（4 个片段，含 ground_truth）：**100% 准确率 (4/4)**

| 片段 | 类型 | ASR解析 | 搜索命中 | 预测结果 |
|------|------|--------|---------|---------|
| 2 | grammar | 12题 | 1文件 | R024-5W基础知识.json ✓ |
| 3 | grammar | 7题 | 2文件 | R024-对划线部分提问-基础知识.json ✓ |
| 4 | grammar | 8题 | 2文件 | R024-特殊疑问句基础知识.json ✓ |
| 6 | vocabulary | 7题 | 10文件 | V1-27-D2.json ✓ |

同班其他学生（Kyle/Nemo/Yiyi/Zoe）预测结果与 Jean 一致，符合同课同题预期。
