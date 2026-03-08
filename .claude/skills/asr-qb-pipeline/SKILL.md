---
name: asr-qb-pipeline
description: ASR 片段分类 + 题库文件匹配全流程。对 two_output/ 下的 ASR 转录文本先分类（grammar/vocabulary），再匹配对应题库文件。当用户需要分类 ASR 片段、匹配题库文件、运行分类+匹配全流程、评估准确率、对比模型效果时使用此技能。触发词包括"分类"、"匹配题库"、"classify"、"match qb"、"跑全流程"、"pipeline"。
---

# ASR 片段分类 + 题库匹配 Pipeline

两步流水线：**分类**（grammar/vocabulary）→ **匹配**（具体题库文件）。

## 模型选择

| 模型 | 推荐度 | 说明 |
|------|--------|------|
| `gemini-3.1-flash-lite-preview` | **首选** | 速度快 ~22x，token 少 ~70%，准确率持平 |
| `qwen3.5-plus` | 备选 | 稳定但慢，DashScope API |

两个脚本均默认使用 `gemini-3.1-flash-lite-preview`。通过 `--model` 切换。

## 核心脚本

| 脚本 | 功能 | API |
|------|------|-----|
| `scripts/classify_asr_type.py` | Step 1: 分类片段类型 | Gemini / DashScope |
| `scripts/match_qb_file.py` | Step 2: 匹配题库文件 | Gemini / DashScope |

## Step 1: 分类片段类型

将 ASR 转录文本分类为 `grammar` 或 `vocabulary`。

```bash
# 单个学生
uv run python scripts/classify_asr_type.py --student Jean --class Niko60900_2026-02-03

# 全班
uv run python scripts/classify_asr_type.py --class Niko60900_2026-02-03 --force

# 用 qwen 备选
uv run python scripts/classify_asr_type.py --model qwen3.5-plus --force
```

**输出**: `two_output/<class>/<student>/classification_<model>.json`

**Prompt**: `prompts/asr_classifier/system.md`（权威来源，可直接编辑迭代）

## Step 2: 匹配题库文件

将已分类的片段匹配到具体题库 JSON 文件（`questionbank/grammar/*.json` 或 `vocabulary/*.json`）。

```bash
# 单个学生
uv run python scripts/match_qb_file.py --student Jean --class Niko60900_2026-02-03

# 全班
uv run python scripts/match_qb_file.py --class Niko60900_2026-02-03 --force

# 调整题目数量容差
uv run python scripts/match_qb_file.py --tolerance 5
```

**输出**: 更新 `metadata.json`（写入 `qb_file`）+ `qb_match_<model>.json`

### 匹配流程

1. LLM 将 ASR 文本解析为结构化 Q/A 列表（Gemini 用 structured JSON output）
2. Q/A 内容搜索题库倒排索引（grammar 521+ / vocabulary 692+ 文件）
3. 题目数量过滤（默认 ±3）
4. LLM function calling 读取候选文件内容，提交最终匹配

## 并行运行（推荐）

Step 2 串行跑全班非常慢。**按学生拆分为并行进程**：

**Claude Code 中**：对每个学生启动后台 Bash 任务：

```
Bash(run_in_background=true): uv run python scripts/match_qb_file.py --student Lucy --class Zoe41900_2026-02-04 --force
Bash(run_in_background=true): uv run python scripts/match_qb_file.py --student Rico --class Zoe41900_2026-02-04 --force
# ... 所有学生同一消息中并行发出
```

**Shell 中**：
```bash
for student in Lucy Rico Youyou; do
  uv run python scripts/match_qb_file.py --student $student --class Zoe41900_2026-02-04 --force &
done
wait
```

## 数据格式

### metadata.json

```json
{
  "ground_truth": {
    "2/2_qwen_asr.json": {"type": "grammar", "qb_file": "R024-5W基础知识.json"},
    "6/2_qwen_asr.json": {"type": "vocabulary", "qb_file": "V1-27-D2.json"}
  },
  "qb_matched_at": "2026-03-08T10:30:00Z",
  "qb_matched_by": "gemini-3.1-flash-lite-preview",
  "qb_match_usage": {"input_tokens": 8898, "output_tokens": 1498, "elapsed_s": 19.63}
}
```

旧格式（`segments` 键）也兼容。

## 前置条件

- ASR 转录已完成（`<seg>/2_qwen_asr.json` 或 `.txt` 存在）
- Step 2 需要 Step 1 的分类结果（metadata.json 含 `type` 字段）
- `questionbank/grammar/` 和 `questionbank/vocabulary/` 目录存在
- 环境变量：`GEMINI_API_KEY`（首选）或 `DASHSCOPE_API_KEY`（备选）

## 已验证效果

### 分类准确率

| 模型 | 准确率 |
|------|--------|
| gemini-3.1-flash-lite-preview | 100% (Jean 4/4) |
| qwen3.5-plus | 98-100% |

### 题库匹配准确率（Jean 4 片段）

| 模型 | 准确率 | 总耗时 | 总 tokens |
|------|--------|--------|----------|
| gemini-3.1-flash-lite-preview | **100%** | **19.63s** | **10,396** |
| qwen3.5-plus | 100% | 426.35s | 34,304 |

## 排错要点

- **SSL 超时**: 代理不稳定，重试即可
- **API key expired**: 更新 `.env` 和 `scripts/.env` 中的 `GEMINI_API_KEY`
- **预测为 None**: 片段目录名含特殊字符，改为纯数字并同步 metadata.json
- **grammar 被误判**: 编辑 `prompts/asr_classifier/system.md` 补充边界案例
