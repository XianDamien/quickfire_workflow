# Change: Add model-eval analysis skill

## Why
分析模型评测结果的流程分散在多个脚本和报告里，需要统一成一个可复用的技能，降低重复沟通成本。

## What Changes
- 新增 `model-eval` 技能，用于仅分析已有评测结果
- 统一输出：Excel 报告 + 额外 summary
- 汇总相关脚本与报告的使用流程

## Impact
- Affected specs: `model-eval-skill`
- Affected code: `skills/model-eval/`
