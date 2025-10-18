# Specification: 工作流配置读取与验证 (evaluation-workflow)

## Overview

扩展 `evaluation-workflow` 规范，支持从 `.env` 文件自动读取 OSS 配置，并在工作流启动前进行凭证验证。

## MODIFIED Requirements

### Requirement: OSS 参数智能加载

工作流 **SHALL** 支持从 .env 文件自动读取 OSS 配置参数，参数来源优先级遵循：**命令行参数 > .env 文件 > 默认值**

#### Scenario: 用户不提供命令行参数，工作流自动从 .env 读取配置

**Given:**
- `.env` 文件中配置了 `OSS_BUCKET_NAME` 和 `OSS_ENDPOINT`
- 用户运行 `python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv --asr-engine funasr`
- 未提供 `--oss-region` 和 `--oss-bucket` 参数

**When:**
- 工作流启动

**Then:**
- 自动从 `.env` 读取 `OSS_BUCKET_NAME` 和 `OSS_ENDPOINT`
- 工作流继续执行
- 控制台输出显示参数来源为 ".env"

#### Scenario: 用户通过命令行参数覆盖 .env 配置

**Given:**
- `.env` 中配置了 `OSS_REGION=cn-shanghai`
- 用户运行 `python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv --asr-engine funasr --oss-region cn-hangzhou`

**When:**
- 工作流启动

**Then:**
- 使用命令行参数 `cn-hangzhou`，而非 `.env` 中的 `cn-shanghai`
- 控制台输出显示参数来源为 "命令行"

#### Scenario: 必需参数缺失时提示错误

**Given:**
- `.env` 文件不存在或未配置 OSS 参数
- 用户运行 FunASR 工作流但未提供 `--oss-region` 和 `--oss-bucket`

**When:**
- 工作流启动

**Then:**
- 输出清晰的错误信息，列出缺失的参数
- 提供解决方案（如何配置 .env 或使用命令行参数）
- 工作流退出，返回非零状态码

---

### Requirement: 工作流启动前进行 OSS 凭证验证

在执行 FunASR 转写前，工作流 **MUST** 验证 OSS 凭证的有效性，确保用户配置正确。

#### Scenario: OSS 凭证有效

**Given:**
- `.env` 中配置了正确的 `OSS_BUCKET_NAME`、`OSS_ENDPOINT`
- 环境变量中配置了有效的 `ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- 用户运行 FunASR 工作流

**When:**
- 工作流启动，进入凭证验证阶段

**Then:**
- 验证通过，输出 "✅ OSS 凭证验证通过"
- 工作流继续执行转写和评测

#### Scenario: OSS 凭证无效或权限不足

**Given:**
- 凭证信息不正确或权限不足
- 用户运行 FunASR 工作流

**When:**
- 工作流启动，进入凭证验证阶段

**Then:**
- 验证失败，输出错误信息和诊断建议
- 工作流立即退出，不继续执行
- 用户可根据提示修正配置

#### Scenario: 缺少 OSS SDK 依赖

**Given:**
- 用户尝试运行 FunASR 工作流
- 但未安装 `alibabacloud_oss_v2` 依赖

**When:**
- 凭证验证阶段

**Then:**
- 输出提示，告知用户需要安装 `pip install alibabacloud_oss_v2`
- 工作流退出

---

### Requirement: .env 文件格式与映射

工作流 **SHALL** 支持以下 `.env` 配置格式，自动读取 OSS 相关参数。

#### Scenario: .env 中配置完整 OSS 参数

**Given:**
- `.env` 文件中配置如下：
  ```env
  OSS_BUCKET_NAME=quickfire-audio
  OSS_REGION=cn-shanghai
  OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
  ```

**When:**
- 工作流调用 `load_env_config()`

**Then:**
- 返回配置字典：
  ```python
  {
    'bucket': 'quickfire-audio',
    'region': 'cn-shanghai',
    'endpoint': 'oss-cn-shanghai.aliyuncs.com'
  }
  ```

#### Scenario: .env 中仅配置 endpoint，region 自动推断

**Given:**
- `.env` 文件中配置如下：
  ```env
  OSS_BUCKET_NAME=quickfire-audio
  OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
  ```
- 工作流不从 `.env` 读取 `OSS_REGION`

**When:**
- 工作流调用 `load_env_config()`

**Then:**
- 返回配置字典：
  ```python
  {
    'bucket': 'quickfire-audio',
    'endpoint': 'oss-cn-hangzhou.aliyuncs.com'
  }
  ```
- region 由 endpoint 推断（后续如需要可支持）

---

### Requirement: 增强控制台输出

工作流 **MUST** 在启动时输出配置来源和验证结果，提高透明度。

#### Scenario: 显示 OSS 配置来源

**Given:**
- 用户运行 FunASR 工作流
- 从 .env 读取了部分参数，命令行提供了其他参数

**When:**
- 工作流启动，参数校验阶段

**Then:**
- 控制台输出清晰的参数表，标注每个参数的来源：
  ```
  ✓ OSS 配置来源：
     Region: cn-shanghai (来自 .env)
     Bucket: quickfire-audio (来自 .env)
     Endpoint: oss-cn-shanghai.aliyuncs.com (来自 .env)
  ```
  或
  ```
  ✓ OSS 配置来源：
     Region: cn-hangzhou (来自命令行)
     Bucket: my-bucket (来自命令行)
  ```

#### Scenario: 显示验证结果

**Given:**
- 工作流进行凭证验证

**When:**
- 验证完成

**Then:**
- 输出验证结果：
  - 成功：`✅ OSS 凭证验证通过`
  - 失败：
    ```
    ❌ OSS 凭证验证失败: AccessDenied
    💡 诊断建议：
       - 检查 OSS 凭证权限（需要 GetBucketInfo 权限）
       - 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）
    ```

---

### Requirement: Qwen ASR 模式不受影响

修改 **MUST** 确保 Qwen ASR 工作流不受影响。

#### Scenario: 使用 Qwen ASR，不需要 OSS 参数

**Given:**
- 用户运行 `python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv --asr-engine qwen` 或省略 `--asr-engine`

**When:**
- 工作流启动

**Then:**
- 不进行 OSS 参数验证
- 不进行凭证验证
- 直接执行 Qwen 多模态转写
- 工作流逻辑完全不变

---

## CLI Interface Changes

### Command
```bash
python3 workflow.py \
  --audio-path <path> \
  --qb-path <path> \
  [--output <path>] \
  [--asr-engine qwen|funasr] \
  [--oss-region <region>] \
  [--oss-bucket <bucket>] \
  [--oss-endpoint <endpoint>] \
  [--keep-oss-file] \
  [--api-key <key>]
```

### Parameters

#### Modified: --oss-region
- **原有**：仅当 `--asr-engine funasr` 时必需
- **修改后**：仅当 `--asr-engine funasr` 且 .env 未配置 `OSS_REGION` 时必需
- **来源优先级**：命令行 > .env

#### Modified: --oss-bucket
- **原有**：仅当 `--asr-engine funasr` 时必需
- **修改后**：仅当 `--asr-engine funasr` 且 .env 未配置 `OSS_BUCKET_NAME` 时必需
- **来源优先级**：命令行 > .env

#### Modified: --oss-endpoint
- **原有**：可选
- **修改后**：可选，来源优先级：命令行 > .env

#### Unchanged: --asr-engine, --output, --api-key, --keep-oss-file

---

## Error Handling

### Errors

#### Error: FunASR 模式下缺失 OSS 参数
```
错误码: 1
消息: ❌ 错误：使用 FunASR 模式必须指定以下参数：
      - OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)
      - OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)
解决方案: 配置 .env 或通过命令行参数指定
```

#### Error: OSS 凭证验证失败
```
错误码: 1
消息: ❌ OSS 凭证验证失败: AccessDenied
诊断建议: 检查凭证权限和环境变量配置
```

#### Error: OSS 依赖缺失
```
错误码: 1
消息: ❌ 缺少 alibabacloud_oss_v2 依赖
解决方案: pip install alibabacloud_oss_v2
```

---

## Backward Compatibility

✅ **完全向后兼容**

- 现有 Qwen ASR 工作流不受影响
- 现有 FunASR 工作流（使用完整命令行参数）继续正常运行
- 单独脚本（`qwen3.py`、`captioner_qwen3.py`）独立运行不受影响
- 新增功能仅在 FunASR 模式下生效

---

## Implementation Notes

### Files to Modify
- `scripts/workflow.py` - 新增函数、参数处理、验证逻辑

### Files to Create
- 无新文件（函数直接添加到 workflow.py）

### Configuration
- `.env` 文件使用现有配置，新增可选的 `OSS_REGION` 字段

### Dependencies
- 现有：`dashscope`、`alibabacloud_oss_v2`（可选，仅 FunASR 模式）
- 无新增第三方依赖

---

## Validation & Testing

### Validation Steps
1. ✅ 从 .env 读取 OSS 配置成功
2. ✅ 命令行参数覆盖 .env 配置
3. ✅ 缺失参数时正确报错
4. ✅ OSS 凭证验证通过/失败正确处理
5. ✅ Qwen ASR 模式不受影响
6. ✅ 向后兼容性验证

### Test Cases
- see `tasks.md` Phase 3 for detailed test scenarios

---

## Examples

### Example 1: 自动从 .env 读取（推荐用法）
```bash
# 前提：.env 中已配置 OSS_BUCKET_NAME 和 OSS_ENDPOINT
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr
```

### Example 2: 命令行参数覆盖 .env
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou \
  --oss-bucket another-bucket
```

### Example 3: 纯命令行参数（向后兼容）
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr \
  --oss-region cn-shanghai \
  --oss-bucket quickfire-audio \
  --oss-endpoint oss-cn-shanghai.aliyuncs.com
```

### Example 4: Qwen ASR（不受影响）
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv
  # 或明确指定
  # --asr-engine qwen
```
