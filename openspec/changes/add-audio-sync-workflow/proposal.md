# Change: Add synchronous audio annotation workflow

## Why
当前音频直连评分仅支持 Batch 方式，排队时间不可控。需要在主流程中加入同步音频模式，用于快速试跑与验证，缩短结果产出时间。

## What Changes
- 新增同步音频评测能力，将音频直接传入 Gemini 并生成评分结果
- 在 `scripts/main.py` 增加可选的同步音频 annotator（非 batch）
- 保持输出 JSON 结构与现有评分结果一致
- 记录同步模式的 token 消耗与耗时

## Impact
- Affected specs: `audio-annotation`
- Affected code: `scripts/main.py`、`scripts/annotators/`（新增音频 annotator）
