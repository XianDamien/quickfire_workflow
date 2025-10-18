# Design Document: FunASR 集成工作流

## Architecture Overview

### 核心模块关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    workflow.py (扩展)                       │
│  --asr-engine [qwen|funasr]                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────────┐      ┌──────────────────┐
│  Qwen ASR 路径    │      │  FunASR 路径     │
├───────────────────┤      ├──────────────────┤
│ transcribe_audio()│      │ 本地文件 → OSS   │
│ (captioner_qwen  │      │     上传        │
│      .py)         │      │        ↓         │
│                   │      │ FunASR 异步     │
│ 返回 JSON/文本    │      │  转写 + 轮询    │
└─────────┬─────────┘      └────────┬────────┘
          │                         │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │   ASR 结果标准化        │
          │  (统一为 JSON 格式)     │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │  题库加载 + 评测        │
          │ (qwen3.py 保持不变)     │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │   JSON 评分报告         │
          └─────────────────────────┘
```

### 文件结构

```
scripts/
├── workflow.py                    (扩展：支持 --asr-engine 参数)
├── captioner_qwen3.py            (重构：提取 transcribe_audio() 函数)
├── qwen3.py                      (保持不变)
├── upload_oss.py                 (保持不变，作为可选独立脚本)
└── funasr_workflow.py (NEW)      (新建：包含 FunASR 转写逻辑)
   └── 核心函数：
       - upload_audio_to_oss()      # 本地文件上传
       - transcribe_with_funasr()   # FunASR 转写
       - normalize_asr_output()     # ASR 结果标准化
```

## Detailed Component Design

### 1. funasr_workflow.py (New Module)

**职责**：
- 处理本地文件 → OSS 上传
- 调用 FunASR 异步转写
- 轮询查询任务状态
- 将 FunASR 输出转换为统一格式

**关键函数**：

#### `upload_audio_to_oss(local_path, region, bucket, endpoint=None, api_key=None)`
- 功能：上传本地音频到 OSS
- 参数：
  - `local_path`: 本地音频文件路径
  - `region`: OSS 区域代码（e.g., "cn-hangzhou"）
  - `bucket`: OSS 桶名
  - `endpoint`: OSS 端点（可选，自动生成）
  - `api_key`: DASHSCOPE 密钥（用于凭证）
- 返回：`{"oss_url": "...", "status_code": 200}`
- 异常处理：
  - 文件不存在：抛出 `FileNotFoundError`
  - 上传失败：抛出 `RuntimeError` 含错误信息

#### `transcribe_with_funasr(oss_url, api_key=None, max_retries=10, retry_interval=2)`
- 功能：调用 FunASR 进行异步转写
- 参数：
  - `oss_url`: OSS 公网 URL
  - `api_key`: DASHSCOPE_API_KEY
  - `max_retries`: 最大轮询次数
  - `retry_interval`: 轮询间隔（秒）
- 返回：
  ```json
  {
    "task_id": "xxx",
    "status": "SUCCEEDED",
    "result": {
      "sentences": [
        {"speaker": "spk0", "text": "...", "start_time": 0, "end_time": 1000}
      ]
    }
  }
  ```
- 异常处理：
  - 异步任务失败：抛出带任务 ID 的异常
  - 超时（轮询次数过多）：抛出 `TimeoutError`

#### `normalize_asr_output(funasr_result)`
- 功能：将 FunASR 输出转换为项目标准格式（与 Qwen 兼容）
- 参数：FunASR 返回的原始结果
- 返回：标准化的 JSON 字符串（与 `captioner_qwen3.py` 输出格式一致）

### 2. captioner_qwen3.py (Refactoring)

**修改**：提取 `transcribe_audio()` 函数便于复用

**当前状态**：
```python
from dashscope.audio.asr import Transcription

# 直接调用，返回原始响应
response = Transcription.async_call(...)
```

**目标重构**：
```python
def transcribe_audio(audio_path, api_key=None, model='qwen3-omni-30b-a3b-captioner'):
    """
    转写音频（Qwen 多模态模式）

    Args:
        audio_path: 本地音频文件路径或 file:// URL
        api_key: DASHSCOPE_API_KEY
        model: 转写模型（默认 qwen3-omni-30b-a3b-captioner）

    Returns:
        str: JSON 格式的转写结果
    """
    # 现有逻辑...
    return json.dumps(result, ensure_ascii=False)
```

### 3. workflow.py (Extension)

**新增参数**：
```bash
--asr-engine {qwen|funasr}      # 选择转写引擎（默认：qwen）
--oss-region REGION              # OSS 区域（FunASR 模式下必需）
--oss-bucket BUCKET              # OSS 桶名（FunASR 模式下必需）
--oss-endpoint ENDPOINT           # OSS 端点（可选，自动生成）
--keep-oss-file                  # 转写后不删除 OSS 文件（可选）
```

**工作流修改**：

```python
# 伪代码
if args.asr_engine == "qwen":
    asr_result = transcribe_audio(audio_path, api_key)
elif args.asr_engine == "funasr":
    oss_url = upload_audio_to_oss(audio_path, args.oss_region, args.oss_bucket, ...)
    asr_result = transcribe_with_funasr(oss_url, api_key)
    # 可选：清理 OSS 文件
else:
    raise ValueError("不支持的 ASR 引擎")

# 后续流程保持不变
evaluation_result = evaluate_pronunciation(asr_result, qb_data, api_key)
```

## Data Format Specifications

### FunASR 原始输出

```json
{
  "task_id": "abc123",
  "task_status": "SUCCEEDED",
  "output": {
    "result": [
      {
        "text": "...",
        "speaker": "spk0",
        "sentence_id": 0,
        "start_time": 0,
        "end_time": 1000,
        "timestamps": [...]
      }
    ]
  }
}
```

### 标准化格式（与 Qwen 兼容）

```json
{
  "sentences": [
    {
      "text": "...",
      "speaker": "spk0",
      "start_time": 0,
      "end_time": 1000,
      "word_timestamp": []
    }
  ]
}
```

## Error Handling Strategy

### 上传阶段
- **文件不存在**：立即失败，给出明确提示
- **权限不足**：检查 OSS 凭证和桶配置
- **网络错误**：重试 3 次后失败

### 转写阶段
- **任务提交失败**：抛出异常，显示 API 错误
- **异步任务失败**：捕获 `task_status == 'FAILED'` 并输出错误日志
- **轮询超时**：设置最大轮询次数（10 次，共约 20 秒）

### 格式转换
- **字段缺失**：默认值处理（如 speaker 默认 "spk0"）
- **时间戳异常**：验证并调整

## Backward Compatibility

✅ **完全向后兼容**：
- `workflow.py` 不指定 `--asr-engine` 时默认使用 `qwen`
- `qwen3.py` 和 `captioner_qwen3.py` 可单独使用（逻辑不变）
- 现有调用方式（命令行、模块导入）继续工作

## Testing Strategy

### 手动测试检查清单
1. ✅ Qwen 模式：运行现有工作流，确保无回归
2. ✅ FunASR 模式：
   - 本地文件上传成功
   - 转写结果格式正确
   - 工作流完整运行
3. ✅ 参数验证：缺少必需参数时给出清晰提示
4. ✅ 异常处理：网络错误、权限错误时的行为

## Open Questions

1. 是否需要 FunASR 的输出结果缓存？
2. OSS 文件转写后是否应自动删除，或由用户决定？
3. FunASR 轮询的重试次数和间隔是否需要可配置？
