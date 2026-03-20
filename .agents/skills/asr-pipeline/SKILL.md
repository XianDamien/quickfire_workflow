---
name: asr-pipeline
description: ASR 片段分类 + 题库文件匹配全流程。对 two_output/ 下的 ASR 转录文本先分类（grammar/vocabulary），再匹配对应题库文件。当用户需要分类 ASR 片段、匹配题库文件、运行分类+匹配全流程、评估准确率、对比模型效果、或用已有 metadata 作为金标准回归验证时使用此技能。触发词包括"分类"、"匹配题库"、"classify"、"match qb"、"跑全流程"、"pipeline"、"gold standard"、"金标准"。
---

# ASR 片段分类 + 题库匹配 Pipeline

合并流水线：每个片段 **2 次 LLM 调用** 完成 **分类 + Q/A 解析 + 题库匹配**。

## 调用架构

```
ASR 文本 → [LLM 调用 1: 分类 + Q/A 解析] → { type, qa_pairs }
                                              ↓
                              [纯算法: 索引搜索 + 题数过滤] → 候选列表
                                              ↓
                      [LLM 调用 2: function calling 最终判定] → qb_file
```

## 模型选择

| 模型 | 推荐度 | 说明 |
|------|--------|------|
| `gemini-3.1-flash-lite-preview` | **首选** | 速度快 ~22x，token 少 ~70%，准确率持平 |
| `qwen3.5-plus` | 备选 | 稳定但慢，DashScope API |

默认使用 `gemini-3.1-flash-lite-preview`。通过 `--model` 切换。

## 核心脚本

| 脚本 | 功能 | 说明 |
|------|------|------|
| `.agents/skills/asr-pipeline/scripts/pipeline.py` | 统一入口 | `classify / match / all` 三个子命令 |
| `.agents/skills/asr-pipeline/scripts/match.py` | 分类 + 匹配（合并流程） | 主逻辑，2 次 LLM/片段 |
| `.agents/skills/asr-pipeline/scripts/classify.py` | 独立分类（批量验证） | 可选，用于单独评估分类准确率 |

## 主流程：分类 + 匹配（推荐）

`match.py` 已将分类和 Q/A 解析合并为 1 次 LLM 调用，无需先运行 classify。

```bash
# ⚠️ 必须加 PYTHONPATH=. 否则报 ModuleNotFoundError: No module named 'scripts'
# 单个学生
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --student Jean --class Niko60900_2026-02-03

# 全班（推荐，一次处理班内所有学生）
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Niko60900_2026-02-03 --force

# 调整题目数量容差
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Niko60900_2026-02-03 --tolerance 5

# 金标准评估：只输出结果，不回写 metadata
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Zoe41900_2026-02-04 --force --eval-only
```

**输出**: `qb_match_<model>.json`；默认会更新 `metadata.json`，加 `--eval-only` 时不会回写。

### 匹配流程（每片段 2 次 LLM 调用）

1. **LLM 调用 1**：分类（grammar/vocabulary）+ 解析为结构化 Q/A 列表（1 次 structured output）
2. **纯算法**：Q/A 内容搜索题库倒排索引（521 grammar + 692 vocabulary 文件）+ 题目数量过滤（±3）
3. **LLM 调用 2**：function calling 读取候选文件内容，提交最终匹配

## 独立分类（可选）

仅用于批量验证分类准确率，不影响匹配流程。

```bash
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py classify --class Niko60900_2026-02-03 --force
```

**输出**: `two_output/<class>/<student>/classification_<model>.json`

**Prompt**: `prompts/asr_classifier/system.md`（权威来源，可直接编辑迭代）

## 目录递归原则

- 支持两种班级布局：`two_output/<class>/<student>/...` 和 `two_output/<bucket>/<class>/<student>/...`
- 目前约定的上一级分桶目录可以是 `R1/`、`R2/`、`130/`
- pipeline 通过递归查找 `metadata.json` 反推真实班级目录，不再把 `R1` / `R2` / `130` 误判成班级本身
- `--class` 过滤匹配的是相对路径，所以既可以传 `Zoe41900_2026-02-04`，也可以传 `130/Zoe51530_2026-02-03`

示例：

```bash
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class R1/SomeClass --force
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class R2/SomeClass --force
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class 130/Zoe51530_2026-02-03 --force
```

## 并行运行（推荐）

串行跑全班非常慢。推荐两种并行策略：

### 策略 A：按班级批量 + 主 agent 后台任务（最简单）

`--class` 不指定 `--student` 时会自动遍历班内所有学生（内部串行）。多个班级同时后台运行：

```
# 每次并行 5 个班级（Claude Code 单条消息发出）
Bash(run_in_background=true): PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Niko60900_2026-02-03 --force
Bash(run_in_background=true): PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Niko60900_2026-02-04 --force
Bash(run_in_background=true): PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Zoe41900_2026-02-02 --force
Bash(run_in_background=true): PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Zoe41900_2026-02-04 --force
Bash(run_in_background=true): PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class Zoe51530_2026-02-03 --force
```

### 策略 B：按班级派 subagent（context: fork，隔离性更强）

每个班级启动一个独立子 agent，子 agent 内部并行跑所有学生（后台 Bash），完成后汇报匹配结果：

```
Agent(run_in_background=true, prompt="处理班级 Niko60900_2026-02-03，学生 Jean/Kyle/Nemo/Yiyi/Zoe，
  同一条消息并行发出 5 个后台 Bash：
  PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --student <name> --class Niko60900_2026-02-03 --force
  等所有任务完成后读取各学生 metadata.json，返回 {type, qb_file} 汇总供主 agent 做一致性检查")
```

> **注意**：subagent 中的 Bash 后台任务不会继承主 agent 的工作目录，必须显式在命令里加 `PYTHONPATH=.`（或用 `cd /path/to/project &&`），否则报 `ModuleNotFoundError: No module named 'scripts'`。

**Shell 中（学生粒度并行）**：
```bash
for student in Lucy Rico Youyou; do
  PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --student $student --class Zoe41900_2026-02-04 --force &
done
wait
```

## 轻量模型上下文

若 `metadata.json` 中存在班级阶段字段：

```json
{
  "class_stage_code": "R2",
  "class_stage_label": "小初衔接",
  "class_stage_range": "R060-R102"
}
```

pipeline 会把这类信息作为**弱先验**传给轻量级 LLM（如 `gemini-3.1-flash-lite-preview`），帮助它在边界模糊时更稳地判断；若与转写内容冲突，仍以转写本身为准。

## 当前金标准

当前可直接拿来回归验证的班级：

- `two_output/R2/Zoe41900_2026-02-04`
- `two_output/R1/Zoe70930_2026-02-02`

推荐命令：

```bash
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class R2/Zoe41900_2026-02-04 --force --eval-only
PYTHONPATH=. uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class R1/Zoe70930_2026-02-02 --force --eval-only
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
- metadata.json 中有片段条目（`type` 字段作为 ground truth 用于评估，分类由 LLM 自动完成）
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
- **找不到 ASR 文件**: 新版 pipeline 已兼容“数字目录”和“题库名目录”，若仍失败，先检查子目录里是否存在 `2_qwen_asr.txt/json`
- **grammar 被误判**: 合并 prompt 中的分类规则来自 `prompts/asr_classifier/system.md`，可参考该文件补充边界案例
