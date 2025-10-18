## ADDED Requirements

### Requirement: Unified Evaluation Workflow CLI
系统 SHALL 提供一个统一的命令行工作流入口，能够接收音频文件路径和题库路径，自动完成从音频转写到评测评分的端到端处理。

#### Scenario: 用户启动完整工作流
- **WHEN** 用户执行 `python3 scripts/workflow.py --audio-path <audio_file> --qb-path <qb_file>`
- **THEN** 系统自动执行音频转写，并将转写结果流转到评测评分
- **AND** 系统输出结构化的 JSON 评测报告

#### Scenario: 工作流处理成功
- **WHEN** 音频文件和题库文件都有效且存在
- **THEN** 系统完成以下步骤：
  1. 音频转写 - 调用 `qwen3-omni-30b-a3b-captioner` 模型处理音频
  2. 结果转换 - 将转写结果转换为 ASR JSON 格式
  3. 评测分析 - 调用 `qwen-plus` 模型进行评分
  4. 结果输出 - 输出最终评测报告（JSON 格式）

#### Scenario: 工作流错误处理
- **WHEN** 音频文件不存在或无效
- **THEN** 系统输出明确的错误信息并退出

- **WHEN** 题库文件不存在或格式错误
- **THEN** 系统输出明确的错误信息并退出

- **WHEN** API 调用失败
- **THEN** 系统输出 API 错误信息便于调试

### Requirement: Modularized Evaluation Engine
评测引擎 SHALL 以模块化方式设计，支持函数级别的复用和集成。

#### Scenario: 作为模块导入使用
- **WHEN** 其他脚本或工作流导入评测模块
- **THEN** 系统提供以下可调用的函数接口：
  - `evaluate_pronunciation(asr_data, qb_data, system_prompt)` - 执行评测分析
  - 返回结构化的 JSON 评测报告

#### Scenario: 保持向后兼容
- **WHEN** 用户直接执行 `python3 scripts/qwen3.py`（原有方式）
- **THEN** 系统继续支持原有行为，使用硬编码的文件路径

### Requirement: Modularized Audio Captioning
音频转写模块 SHALL 支持函数级别的调用和参数传递。

#### Scenario: 音频转写函数接口
- **WHEN** 工作流调用 `transcribe_audio(audio_path)` 函数
- **THEN** 系统返回转写结果（字符串或 JSON 格式）

#### Scenario: 保持独立可用性
- **WHEN** 用户直接执行 `python3 scripts/captioner_qwen3.py <audio_file>`（原有方式）
- **THEN** 系统继续支持原有行为，直接输出转写结果

### Requirement: System Prompt Configuration
系统提示 SHALL 硬编码在工作流中，便于统一管理和调整。

#### Scenario: 系统提示管理
- **WHEN** 用户需要修改评分规则或评测逻辑
- **THEN** 用户只需修改 `workflow.py` 中的 `SYSTEM_PROMPT` 常量
- **AND** 修改后的规则自动应用于所有评测

#### Scenario: 评分规则一致性
- **WHEN** 系统执行评测
- **THEN** 系统使用统一的 system_prompt，确保评分规则的一致性和可维护性

### Requirement: Command-Line Interface
命令行工作流 SHALL 提供清晰的参数接口和使用说明。

#### Scenario: 参数指定和验证
- **WHEN** 用户执行工作流命令
- **THEN** 系统支持以下参数：
  - `--audio-path` (必需) - 音频文件路径
  - `--qb-path` (必需) - 题库文件路径（CSV 格式）
  - `--output-path` (可选) - 输出报告路径（默认为 `stdout`）

#### Scenario: 帮助信息
- **WHEN** 用户执行 `python3 scripts/workflow.py --help`
- **THEN** 系统输出使用说明和示例

#### Scenario: 工作流输出
- **WHEN** 工作流完成所有步骤
- **THEN** 系统输出最终 JSON 评测报告到指定位置（默认为 stdout）
