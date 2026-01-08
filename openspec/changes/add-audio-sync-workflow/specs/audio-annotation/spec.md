## ADDED Requirements
### Requirement: Synchronous Audio Annotation
系统 SHALL 支持在同步流程中直接使用音频文件进行评分，并生成与现有评分一致的 JSON 输出。

#### Scenario: Run sync audio annotation
- **WHEN** 用户在主流程中选择音频模式
- **THEN** 系统读取 `1_input_audio.*` 并返回评分 JSON

### Requirement: Audio Mode Metrics
系统 SHALL 记录同步音频模式的 token 消耗与关键耗时信息。

#### Scenario: Metrics recorded
- **WHEN** 同步音频评测完成
- **THEN** 结果中包含 token 使用量与耗时字段
