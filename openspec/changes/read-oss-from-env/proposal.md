# Proposal: 从 .env 读取 OSS 配置到 FunASR 工作流 (read-oss-from-env)

## Summary

优化工作流启动体验，使 `workflow.py` 在使用 FunASR 模式时，自动从 `.env` 文件读取 OSS 配置参数（region、bucket、endpoint），避免用户每次运行都需要通过命令行参数输入。同时实现在工作流启动前进行 OSS 凭证有效性验证。

## Why

**现有问题**：
- 用户运行 FunASR 工作流时需要手动输入 `--oss-region`、`--oss-bucket` 等参数，操作繁琐
- `.env` 文件中已配置 OSS 参数，但工作流未充分利用
- 用户无法提前验证 OSS 凭证是否有效，导致工作流执行到上传阶段才发现错误
- 命令行冗长，降低用户体验

**价值**：
- 简化用户操作，提高开发效率
- 让 `.env` 配置充分发挥作用，遵循 12-Factor 应用原则
- 早期验证凭证，快速失败（fail fast），减少调试时间
- 支持灵活覆盖：命令行参数 > .env 文件 > 默认值（优先级递减）

## Goals

1. **自动读取 .env**：工作流启动时自动加载 OSS 配置（无需用户操作）
2. **灵活参数覆盖**：支持命令行参数覆盖 .env 配置，保留手动指定能力
3. **早期凭证验证**：在工作流开始前验证 OSS 凭证有效性，提前发现配置错误
4. **向后兼容**：保持现有命令行接口，支持用户已有的脚本和工作流

## Scope

### In-Scope
- 实现 `.env` 文件读取机制（使用 `python-dotenv` 或手动 parse）
- 修改 `run_workflow()` 函数，集成 OSS 参数从 .env 的读取逻辑
- 修改 CLI 参数处理，实现参数优先级（命令行 > .env > 默认值）
- 实现 OSS 凭证验证函数，在 FunASR 模式前置检查
- 完善错误提示和日志输出

### Out-of-Scope
- 修改 `funasr_workflow.py` 核心逻辑
- 修改评测引擎（`qwen3.py`）
- 引入新的第三方依赖（使用标准库或现有依赖）
- 其他 ASR 引擎的配置自动加载

## Dependencies

- 现有模块：`workflow.py`、`funasr_workflow.py`
- 标准库：`os`、`dotenv`（已在项目中或通过标准库实现）
- 环境变量：`.env` 文件（已存在）

## Risks & Mitigations

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| .env 文件不存在 | 工作流无法启动 | 提供明确错误提示，指导用户创建 .env 或通过命令行参数 |
| OSS 凭证过期 | 工作流执行到上传阶段才失败 | 在工作流启动前验证凭证有效性，早期发现问题 |
| 用户环境变量覆盖 | 意外行为 | 记录日志显示最终使用的配置来源（.env 或命令行） |
| 参数优先级混淆 | 用户困惑 | 清晰的文档和日志，显示每个参数的最终值 |

## Success Criteria

1. ✅ 执行 `python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv --asr-engine funasr` 时，自动从 .env 读取 OSS 参数
2. ✅ 通过命令行参数 `--oss-region` 可以覆盖 .env 配置
3. ✅ 工作流启动时验证 OSS 凭证，失败时提示明确的错误信息和解决建议
4. ✅ 控制台输出显示最终使用的 OSS 配置源（.env 或命令行）
5. ✅ 向后兼容：现有脚本和工作流继续正常运行
6. ✅ Qwen ASR 模式不受影响，工作流逻辑不变

## Affected Capabilities

- `evaluation-workflow` - 工作流参数处理方式改进
- 新增工作流启动前的凭证验证阶段

## Not Affected

- 评分规则（`ai-result-output`）
- FunASR 转写逻辑（`funasr_workflow.py`）
- 题库加载
- ASR 转写结果格式

## What Changes

### Capabilities

#### MODIFIED: evaluation-workflow
- OSS 参数现在支持从 .env 自动加载
- 新增工作流启动前的 OSS 凭证验证步骤
- 参数优先级：命令行 > .env > 默认值
- 支持灵活覆盖，向后兼容

### Modules

#### MODIFIED: scripts/workflow.py
- 新增 `load_env_config()` 函数，读取 `.env` 文件
- 新增 `verify_oss_credentials()` 函数，验证 OSS 凭证
- 修改 `main()` 函数处理参数优先级
- 修改 `run_workflow()` 的调用逻辑，集成凭证验证
- 增强日志输出，显示配置来源

### CLI Interface

#### MODIFIED Parameters
- `--oss-region` 不再是必需（FunASR 模式下）
- `--oss-bucket` 不再是必需（FunASR 模式下）
- `--oss-endpoint` 保持可选

#### New Logging
- 启动时输出 OSS 配置来源标识
- 凭证验证成功/失败的明确提示
- 最终使用的参数值

## Traceability

- 相关规范：`evaluation-workflow`
- 相关文件：`.env`、`scripts/workflow.py`
- 相关内存：`project_overview`、`commands_and_setup`
