# Proposal: 集成 FunASR 工作流 (add-funasr-integration)

## Summary

集成 FunASR（阿里云官方 ASR 服务）到评测系统工作流中，支持用户将本地音频文件上传到 OSS，然后调用 FunASR 进行语音转写。此变更提供两条 ASR 路径选择（Qwen ASR 和 FunASR），增强系统的音频处理能力。

## Why

**问题**：
- 当前系统仅支持 Qwen 多模态模型的 ASR 转写，缺乏灵活性
- FunASR 是阿里云官方专业 ASR 服务，可能在特定场景（如中文/英文混合、口音识别）提供更好效果
- 本地音频文件无法直接使用 FunASR（仅支持 OSS 文件 URL），用户体验不佳
- 用户需要手动上传文件再调用转写，流程繁琐

**价值**：
- 提供多种 ASR 引擎选择，满足不同场景需求
- 自动化本地文件上传流程，简化用户操作
- 保持向后兼容，零迁移成本
- 为未来的 ASR 引擎集成（如 Whisper、其他服务）提供基础

## Goals

1. **多源 ASR 支持**：让用户可以选择使用 FunASR 或 Qwen ASR 进行转写
2. **本地文件上传**：实现本地文件 → OSS 的自动化流程
3. **统一工作流入口**：通过扩展现有 `workflow.py`，支持 `--asr-engine` 参数切换转写引擎
4. **可观测性**：输出每个阶段的状态和结果，便于调试

## Scope

### In-Scope
- 实现 `upload_audio_to_oss()` 可重用函数（与 `upload_oss.py` 逻辑一致）
- 实现 `transcribe_with_funasr()` 函数，调用 FunASR 生成 ASR 结果
- 扩展 `workflow.py` 支持 `--asr-engine` 参数（默认值：`qwen`）
- 修改 `captioner_qwen3.py` 导出 `transcribe_audio()` 函数，便于 `workflow.py` 调用
- 增加命令行帮助文档和使用示例

### Out-of-Scope
- 修改现有 `qwen3.py` 评测引擎逻辑
- 修改 ASR 结果格式或统一 FunASR/Qwen 的输出结构（留给后续优化）
- 性能优化或缓存层
- 单元测试框架的引入

## Dependencies

- 现有模块：`qwen3.py`、`captioner_qwen3.py`
- 外部 API：DashScope (Qwen ASR + FunASR)、OSS
- 环境变量：`DASHSCOPE_API_KEY`、`OSS_REGION`、`OSS_BUCKET`、`OSS_ENDPOINT`（可选）

## Risks & Mitigations

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| FunASR 异步任务超时 | 转写失败，影响工作流 | 实现超时控制和重试机制（10次轮询，每次间隔2秒） |
| OSS 上传权限不足 | 无法将文件上传到 OSS | 提示用户检查 AWS 凭证和桶权限 |
| ASR 引擎返回格式差异 | 下游评测模块可能不兼容 | FunASR 结果会转换为通用格式（与 Qwen 兼容） |

## Success Criteria

1. ✅ `workflow.py --asr-engine funasr` 命令成功转写本地音频
2. ✅ 输出结果与现有 Qwen 转写结果格式一致
3. ✅ 支持本地文件自动上传到 OSS
4. ✅ 工作流完整运行（转写 → 评测 → 报告）无中断
5. ✅ 向后兼容：默认使用 Qwen，现有脚本继续工作

## Affected Capabilities

- `evaluation-workflow` - 工作流现在支持多种 ASR 引擎
- 新建 `audio-transcription` 能力规范（支持 FunASR）

## Not Affected

- 评分规则（`ai-result-output` 规范不变）
- 题库加载和数据格式
- 现有单独脚本的使用方式

## What Changes

### Capabilities

#### ADDED: audio-transcription
- 新增能力：音频转写（支持多引擎）
- 支持 FunASR 引擎
- 支持本地文件上传到 OSS
- 提供标准化输出格式

#### MODIFIED: evaluation-workflow
- 扩展工作流以支持多种 ASR 引擎
- 新增 `--asr-engine` 参数
- 保持完整向后兼容性

### Modules

#### ADDED: scripts/funasr_workflow.py
- 新增模块，包含 3 个核心函数
- upload_audio_to_oss()
- transcribe_with_funasr()
- normalize_asr_output()

#### MODIFIED: scripts/workflow.py
- 扩展命令行参数
- 添加 ASR 引擎选择逻辑
- 支持参数验证和错误处理

#### MODIFIED: scripts/captioner_qwen3.py
- 重构以提取可重用函数
- transcribe_audio() 函数导出
- 保持现有脚本兼容性

### CLI Interface

#### New Parameters
- `--asr-engine {qwen|funasr}` (default: qwen)
- `--oss-region REGION` (required if funasr)
- `--oss-bucket BUCKET` (required if funasr)
- `--oss-endpoint ENDPOINT` (optional)
- `--keep-oss-file` (optional flag)
