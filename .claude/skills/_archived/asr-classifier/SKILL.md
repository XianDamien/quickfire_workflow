---
name: asr-classifier
description: 运行快反课程 ASR 片段类型分类器（grammar/vocabulary），对比 metadata.json 标注答案并输出准确率报告。当用户需要对 two_output/ 目录下的 ASR 转录文本进行类型分类、评估分类准确率、优化分类 prompt、或排查分类错误时使用此技能。
---

# ASR 片段类型分类器

对 `two_output/` 目录下的 ASR 转录文本自动分类为 `grammar`（语法快反）或 `vocabulary`（单词快反），并与 `metadata.json` 标注答案对比准确率。

## 核心文件

所有路径相对于项目根目录。

| 文件 | 说明 |
|------|------|
| `scripts/classify_asr_type.py` | 主脚本（唯一入口，从项目根运行） |
| `prompts/asr_classifier/system.md` | **分类器 prompt（权威来源）**，直接编辑即可迭代，无需改代码 |
| `prompts/asr_classifier/metadata.json` | prompt 版本号与 changelog |
| `two_output/<班级>/<学生>/metadata.json` | 标注答案（ground truth） |
| `two_output/<班级>/<学生>/classification_qwen3.5-plus.json` | 输出结果（每学生一份） |
| `skills/asr-classifier/references/error_patterns.md` | 已发现的边界案例及根因，优化 prompt 时参考 |

## 依赖与 API 调用方式

- **Python 包**: `openai`（非 `dashscope`）—— `qwen3.5-plus` 是多模态模型，必须通过 OpenAI 兼容接口调用
- **Base URL**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **API Key**: 环境变量 `DASHSCOPE_API_KEY`（从项目 `.env` 或脚本父目录 `.env` 自动加载）
- **Thinking 模式**: 默认 `enable_thinking=False`，通过 `extra_body={"enable_thinking": False}` 传递，避免额外 token 开销

## Prompt 路径解析

**权威 prompt 位置**：`prompts/asr_classifier/system.md`（项目根目录下）。

脚本通过 `Path(__file__).parent.resolve().parent / "prompts" / "asr_classifier" / "system.md"` 加载 prompt。`scripts/classify_asr_type.py` 从项目根运行时正确解析到 `prompts/asr_classifier/system.md`。skill 目录下的脚本副本仅供参考，运行时始终使用项目根的主脚本。

## Ground Truth 数据格式

`metadata.json`（每个学生目录下）：

```json
{
  "segments": {
    "2": {"type": "grammar"},
    "6": {"type": "vocabulary"}
  },
  "classified_at": "2026-03-02",
  "classified_by": "claude-sonnet"
}
```

`segments` 键为片段目录名（纯数字），值包含 `type` 字段（`grammar` 或 `vocabulary`）。`classified_at` 和 `classified_by` 为标注元信息。

## 运行命令

```bash
# 全量运行（每学生独立 API 调用，准确率 ~98-100%）
uv run python3 scripts/classify_asr_type.py --input-root two_output

# 常用过滤与控制参数
--class Zoe61330        # 只跑某个班级（子串匹配）
--student Apollo        # 只跑某个学生
--force                 # 覆盖已有结果重新运行
```

## 标准工作流

**1. 全量运行**
```bash
uv run python3 scripts/classify_asr_type.py --input-root two_output --force
```

**2. 查看错误**
```python
import json
from pathlib import Path

for f in Path("two_output").glob("*/*/classification_qwen3.5-plus.json"):
    data = json.loads(f.read_text())
    for seg, info in data["segments"].items():
        if not info["correct"]:
            print(f"{data['class']}/{data['student']}/片段{seg}")
            print(f"  预测={info['predicted']}  答案={info['ground_truth']}")
            print(f"  文件={info['asr_path']}")
```

**3. 优化 prompt**
- 编辑 `prompts/asr_classifier/system.md`
- 重跑 `--force` 对比准确率变化
- 更新 `prompts/asr_classifier/metadata.json` 中的版本号和 changelog

**4. 发现标注问题**
- 直接修改对应学生的 `metadata.json`
- 重跑该班级验证：`--class <班级名> --force`

## 输出 JSON 格式

```json
{
  "class": "Zoe61330_2026-02-01",
  "student": "Apollo",
  "model": "qwen3.5-plus",
  "accuracy": 1.0,
  "correct": 2,
  "total": 2,
  "segments": {
    "1": {
      "asr_path": "/full/path/to/1/2_qwen_asr.txt",
      "predicted": "grammar",
      "ground_truth": "grammar",
      "correct": true
    }
  }
}
```

## 排错要点

- **预测为 None**：片段目录名含特殊字符（如中文+空格 `新录音 668`），将目录名改为纯数字并同步更新 `metadata.json`
- **grammar 被批量误判为 vocabulary**：prompt 描述的边界不清晰，参考 `references/error_patterns.md` 补充类似案例
- **模型 400 url error**：`qwen3.5-plus` 必须通过 OpenAI 兼容接口（`https://dashscope.aliyuncs.com/compatible-mode/v1`），脚本已处理，不可用 `dashscope.Generation.call()`
- **跨学生准确率损失**：同一片段号在不同学生对应不同内容，每学生独立调用已消除此问题

## 准确率历史

| Prompt 版本 | 准确率 | 备注 |
|------------|--------|------|
| v1.0 | 76.2% | 初始版本（已废弃的班级模式） |
| v1.2 | 98-100% | 加入前缀/词性链规则 |
