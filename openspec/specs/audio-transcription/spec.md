# audio-transcription Specification

## Purpose
支持多源音频转写能力，允许用户选择不同的 ASR 引擎（Qwen 或 FunASR），提供灵活的音频处理方案。

## Requirements

### Requirement: Multi-Engine Audio Transcription
系统 SHALL 支持多种 ASR 引擎选择，包括 Qwen 多模态和 FunASR 专业服务。

#### Scenario: 选择 Qwen ASR
- **WHEN** 用户执行工作流时指定 `--asr-engine qwen` 或不指定（默认）
- **THEN** 系统使用 Qwen 多模态模型进行音频转写
- **AND** 直接处理本地文件，无需上传

#### Scenario: 选择 FunASR 引擎
- **WHEN** 用户执行工作流时指定 `--asr-engine funasr`
- **THEN** 系统要求用户提供 OSS 配置参数（region 和 bucket）
- **AND** 系统自动上传音频到 OSS，调用 FunASR 进行异步转写

### Requirement: Local File Upload to OSS
系统 SHALL 支持本地音频文件自动上传到阿里云 OSS。

#### Scenario: 上传文件到 OSS
- **WHEN** 用户选择 FunASR 引擎并提供有效的本地音频文件
- **THEN** 系统自动将文件上传到指定 OSS bucket
- **AND** 返回可访问的 OSS URL

#### Scenario: 上传错误处理
- **WHEN** OSS 凭证不正确或权限不足
- **THEN** 系统输出清晰的错误信息和诊断建议

### Requirement: FunASR Async Task Management
系统 SHALL 支持 FunASR 异步任务的提交和轮询。

#### Scenario: 异步转写任务提交
- **WHEN** 系统获得 OSS URL
- **THEN** 系统提交异步转写任务到 FunASR
- **AND** 获得任务 ID

#### Scenario: 任务轮询和完成
- **WHEN** 任务已提交
- **THEN** 系统定期轮询任务状态（最多 10 次，间隔 2 秒）
- **AND** 当任务完成时返回转写结果
- **OR** 当任务失败时输出错误信息

#### Scenario: 任务超时
- **WHEN** 任务轮询超过最大次数仍未完成
- **THEN** 系统提示用户稍后查询，并显示任务 ID

### Requirement: ASR Output Normalization
系统 SHALL 将不同 ASR 引擎的输出统一为标准格式。

#### Scenario: 格式标准化
- **WHEN** FunASR 返回转写结果
- **THEN** 系统转换为标准 JSON 格式
- **AND** 与 Qwen ASR 输出格式一致
- **AND** 包括时间戳、说话人标识等信息

#### Scenario: 时间戳处理
- **WHEN** 系统标准化 ASR 结果
- **THEN** 系统处理时间戳（单位：毫秒）
- **AND** 提取词级时间戳信息

### Requirement: Modularity and Reusability
音频转写函数 SHALL 以模块化方式设计，支持独立复用。

#### Scenario: 函数级导入和调用
- **WHEN** 其他脚本或工作流导入音频转写函数
- **THEN** 系统提供以下可调用的函数接口：
  - `transcribe_audio(audio_path, api_key)` - 使用 Qwen 转写
  - `upload_audio_to_oss(local_path, region, bucket)` - 上传文件
  - `transcribe_with_funasr(oss_url)` - 使用 FunASR 转写
  - `normalize_asr_output(funasr_result)` - 标准化输出

### Requirement: Backward Compatibility
系统 SHALL 保持对现有脚本的向后兼容。

#### Scenario: 独立脚本执行
- **WHEN** 用户直接执行 `python3 scripts/captioner_qwen3.py <audio>`
- **THEN** 系统继续支持原有行为，不受新 ASR 引擎选择的影响

#### Scenario: 默认 Qwen 引擎
- **WHEN** 工作流未明确指定 ASR 引擎
- **THEN** 系统自动使用 Qwen（向后兼容）

### Requirement: Error Handling and Diagnostics
系统 SHALL 提供清晰的错误处理和诊断建议。

#### Scenario: OSS 错误诊断
- **WHEN** 文件上传失败
- **THEN** 系统输出诊断信息，包括：
  - OSS region 和 bucket 验证提示
  - 权限检查建议
  - 环境变量配置提示

#### Scenario: 转写超时处理
- **WHEN** FunASR 转写超时
- **THEN** 系统显示任务 ID，允许用户稍后查询

### Requirement: Observable Workflow
系统 SHALL 提供详细的日志输出便于调试。

#### Scenario: 上传进度显示
- **WHEN** 文件上传到 OSS
- **THEN** 系统显示：
  - 上传文件 key
  - HTTP 状态码
  - 最终 OSS URL

#### Scenario: 转写进度显示
- **WHEN** FunASR 异步任务执行
- **THEN** 系统显示：
  - 当前轮询次数和最大次数
  - 任务状态
  - 完成时间或超时提示

#### Scenario: 结果标准化进度
- **WHEN** 系统标准化转写结果
- **THEN** 系统显示转写条目数和标准化状态

