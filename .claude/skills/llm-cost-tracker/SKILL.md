---
name: llm-cost-tracker
description: >
  Track and report LLM API token usage, elapsed time, and cost for model evaluation tasks.
  This skill should be used after running any LLM-based script (annotator, classifier, matcher, etc.)
  to extract usage data from output JSON files, calculate costs based on model pricing, and generate
  a cost analysis report in cost_analysis/. Triggers include: "统计token", "算一下消耗",
  "cost analysis", "token用量", "成本分析", or after any batch model run completes.
---

# LLM Cost Tracker

每次跑模型任务后，提取 token 用量和耗时，生成成本分析报告。

## 触发时机

- 任何 LLM 脚本批量运行完成后
- 用户问"消耗了多少 token"、"花了多少钱"
- 模型评估/对比测试后需要记录成本

## 工作流程

### Step 1: 定位结果文件

从 `two_output/<班级>/<学生>/` 下找到对应的输出 JSON 文件。常见文件名模式：
- `qb_match_<model>.json` — 题库匹配结果
- `4_llm_annotation.json` — 标注结果
- `classify_<model>.json` — 分类结果

提取其中的 `usage` 字段：
```json
{
  "usage": {
    "input_tokens": 11175,
    "output_tokens": 23129,
    "elapsed_s": 426.35
  }
}
```

若 `usage` 在 segments 内部，逐片段累加。

### Step 2: 汇总数据

用 Python 一行脚本提取全部学生的用量，示例：

```bash
for s in <students>; do
  python3 -c "
import json
d = json.loads(open('two_output/<class>/$s/<result_file>').read())
u = d.get('usage', {})
print(f'$s: in={u.get(\"input_tokens\",0)} out={u.get(\"output_tokens\",0)} t={u.get(\"elapsed_s\",0)}s')
"
done
```

汇总为表格：各学生 input/output/total tokens + 耗时。

### Step 3: 查询模型定价

常用模型定价参考（元/百万 tokens，0-128K 阶梯）：

| 模型 | 输入 | 输出（非思考） | 输出（思考） | 来源 |
|------|------|-------------|------------|------|
| qwen3.5-plus | 0.8 | 4.8 | 4.8 | [阿里云百炼](https://help.aliyun.com/zh/model-studio/model-pricing) |
| qwen-plus | 0.8 | 2.0 | 8.0 | 同上 |
| qwen3-max | 2.0 | 16.0 | 16.0 | 同上 |
| gemini-2.5-flash | $0.15/M in, $3.50/M out | — | — | [Google AI](https://ai.google.dev/pricing) |
| gemini-2.0-flash | $0.10/M in, $0.40/M out | — | — | 同上 |

> 定价可能更新，每次生成报告前确认最新价格。
> Gemini 价格需乘以汇率（约 7.0）转为人民币。
> Batch API 通常享 50% 折扣。

### Step 4: 计算成本

```
费用 = input_tokens × 输入单价/1M + output_tokens × 输出单价/1M
```

### Step 5: 生成报告

写入 `cost_analysis/<task>_cost_analysis.md`，包含以下章节：

1. **元信息** — 日期、模型、任务脚本、测试数据范围
2. **各学生用量表** — input/output/total tokens + 耗时
3. **汇总** — 总 tokens、每片段平均、串行/并行耗时
4. **定价** — 模型、阶梯、单价来源
5. **成本计算** — 本次测试费用 + 单人/每片段费用
6. **规模估算** — 按 20人/50人/400人 外推日费用、月费用
7. **与其他任务对比**（可选） — 与已有报告横向比较

### 报告命名规范

```
cost_analysis/<task_name>_cost_analysis.md
```

示例：
- `qb_match_cost_analysis.md`
- `annotation_gemini_cost_analysis.md`
- `asr_classify_cost_analysis.md`

## 已有报告索引

| 文件 | 任务 | 模型 | 日期 |
|------|------|------|------|
| `成本计算最终版_汇率6.98.md` | Gemini 标注 | gemini-2.5-flash | 2026-01-10 |
| `qb_match_cost_analysis.md` | 题库匹配 | qwen3.5-plus | 2026-03-05 |

## 脚本中的 usage 记录规范

为确保本 skill 能提取数据，LLM 脚本输出 JSON 应包含 `usage` 字段：

```python
import time

t0 = time.monotonic()
resp = client.chat.completions.create(...)
elapsed = time.monotonic() - t0

usage = {
    "input_tokens": resp.usage.prompt_tokens,
    "output_tokens": resp.usage.completion_tokens,
    "elapsed_s": round(elapsed, 2),
}
```

多轮调用时逐次累加 tokens，elapsed_s 取整段总耗时。
