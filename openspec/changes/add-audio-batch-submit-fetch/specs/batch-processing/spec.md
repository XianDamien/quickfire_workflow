## ADDED Requirements

### Requirement: Audio batch supports submit/fetch
系统 SHALL 为音频批处理提供 `submit` 和 `fetch` 能力，以支持先提交后统一拉取结果。

#### Scenario: Submit then fetch
- **WHEN** 用户提交音频 batch
- **THEN** 生成可用于后续 `fetch` 的 manifest 信息
- **AND** `fetch` 完成后回填学生结果与报告

### Requirement: Output alignment across modes
系统 SHALL 统一 ASR 与音频的输出结构与字段，确保报告与统计一致。

#### Scenario: Audio run outputs match ASR outputs
- **WHEN** 音频 batch 完成并拉取
- **THEN** 输出包含 `batch_manifest.json`、`batch_report.json`、`students/` 与 `4_llm_annotation.json`
- **AND** `token_usage` 在所有路径中可用

### Requirement: Audio output is distinguishable
系统 SHALL 为音频方案输出添加 `.audio` 标识以区分方案。

#### Scenario: Audio output label
- **WHEN** 输出音频方案结果
- **THEN** 产出带 `.audio` 标识的输出路径或标识字段

### Requirement: Comparison report is simplified
系统 SHALL 将 ASR vs 音频对比报告精简为 2 个 sheet：核心指标与错误详情。

#### Scenario: Generate simplified comparison report
- **WHEN** 生成对比报告
- **THEN** 输出仅包含核心指标与错误详情两个 sheet

### Requirement: Proxy defaults when not configured
系统 SHALL 在未显式配置代理时，默认使用 `http://127.0.0.1:7890`。

#### Scenario: Default proxy is applied
- **WHEN** 用户未提供 `--proxy` 且未设置相关环境变量
- **THEN** 请求使用 `http://127.0.0.1:7890` 作为代理
