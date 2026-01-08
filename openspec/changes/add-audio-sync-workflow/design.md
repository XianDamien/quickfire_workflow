## Context
- 现有同步主流程（`scripts/main.py`）仅支持文本 ASR 转写后的 annotator
- 音频直连模式目前仅存在于 batch 脚本中
- 需要在同步流程中支持音频直连以缩短验证周期

## Goals / Non-Goals
- Goals:
  - 新增同步音频 annotator，直接读取 `1_input_audio.*`
  - 与现有评分输出结构保持一致
  - 记录 token 与耗时信息
- Non-Goals:
  - 不替换或修改现有 batch 逻辑
  - 不更改评分 prompt 内容

## Decisions
- Decision: 新增一个独立的音频 annotator（例如 `gemini-audio`）
  - Why: 与文本 annotator 解耦，便于在 main 中切换

- Decision: 主流程通过参数切换同步 audio annotator
  - Why: 保持 CLI 简洁，兼容现有参数模式

## Risks / Trade-offs
- 同步音频调用成本更高 → 用于测试/小规模验证
- 音频时长较长时调用耗时不可控 → 需要在文档中提示

## Migration Plan
- 新增 annotator 文件与 main 参数
- 补充 README 使用示例

## Open Questions
- 是否复用 batch 的音频 prompt 模板，或需要专用模板文件？
