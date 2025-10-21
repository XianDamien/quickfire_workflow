# scripts/CLAUDE.md - 评测引擎模块

## 模块职责
- `qwen_asr.py` → **批量音频转写工具**（推荐使用），支持 CLI 参数化处理，自动跳过已处理文件
- `workflow.py` → **统一工作流入口**（推荐使用）, 端到端集成音频转写 + 评测评分
- `qwen3.py` → 主评测引擎，文本模式，加载题库+ASR数据，调用Qwen Plus生成评分报告（可单独导入模块）
- `captioner_qwen3.py` → 音频转写辅助工具，多模态模式，接收音频文件路径，输出ASR转写（可单独导入模块）

---

# qwen_asr.py - Qwen ASR 批量转写工具

## 功能概述

支持灵活的命令行参数化批量音频转写，自动发现数据集和学生，实现幂等处理（已转写文件自动跳过）。

**关键特性**:
- ✅ 按数据集/学生选择性处理
- ✅ 自动去重（已存在 2_qwen_asr.json 则跳过）
- ✅ 清晰的进度报告
- ✅ 完全向后兼容
- ✅ 错误自动恢复

## 快速使用

### 处理所有数据集（向后兼容）
```bash
python3 scripts/qwen_asr.py
```
处理 `archive/` 下所有数据集中的所有学生。

### 处理特定数据集中的所有学生
```bash
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8
```
只处理 `archive/Zoe51530-9.8/` 下的所有学生。

### 处理单个学生
```bash
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Alvin
```
只处理 `archive/Zoe51530-9.8/Alvin/` 下的音频。

### 自定义 API Key
```bash
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --api-key sk-xxxxx
```

### 显示帮助
```bash
python3 scripts/qwen_asr.py --help
```

## 数据集格式

数据集名称格式: `<CourseName>-<Date>` (例如: `Zoe51530-9.8`)

目录结构:
```
archive/
├── Zoe51530-9.8/
│   ├── Alvin/
│   │   ├── 1_input_audio.mp3 (输入)
│   │   ├── 2_qwen_asr.json (输出 - 新)
│   │   └── ...
│   ├── Kevin/
│   │   ├── 1_input_audio.mp3
│   │   ├── 2_qwen_asr.json
│   │   └── ...
│   └── _shared_context/
│       ├── vocabulary.json (可选词汇表)
│       └── *.csv (题库文件)
└── Zoe41900-9.8/
    └── ...
```

## 输出文件

所有转写结果保存为 `2_qwen_asr.json`，位于学生目录中：
- **文件名**: `2_qwen_asr.json`（标准化命名）
- **位置**: `archive/<DATASET>/<STUDENT>/2_qwen_asr.json`
- **格式**: JSON（Qwen ASR API 原始响应）

## 音频文件发现

脚本自动按优先级查找学生音频文件：
1. `1_input_audio.*` (任何格式: .mp3, .mp4, .wav, .m4a, .flac, .ogg)
2. `<StudentName>.*` (例如: Alvin.mp3)
3. 第一个找到的音频文件
4. 无则跳过该学生

## 去重逻辑

如果学生目录已存在 `2_qwen_asr.json` 文件，则自动跳过该学生，无需重复转写。支持安全的重新运行。

## 可调用函数

### 导入和使用

```python
from scripts.qwen_asr import (
    QwenASRProvider,
    find_datasets,
    find_students_in_dataset,
    find_audio_file,
    should_process,
    process_student,
    process_dataset,
    process_all_students
)

# 发现可用数据集
datasets = find_datasets()

# 发现数据集中的学生
students = find_students_in_dataset("Zoe51530-9.8")

# 处理单个学生
exit_code = process_student("Zoe51530-9.8", "Alvin")

# 处理整个数据集
processed, skipped = process_dataset("Zoe51530-9.8")

# 处理所有数据集（向后兼容）
process_all_students()
```

## 环境变量

### 必需
```bash
export DASHSCOPE_API_KEY="sk-xxxxx"  # 阿里云 DashScope API 密钥
```

## 错误处理

| 错误 | 处理方式 |
|------|--------|
| 数据集不存在 | 打印错误并退出 (code 1) |
| 学生目录不存在 | 打印错误并退出 (code 1) |
| 无音频文件 | 跳过该学生，继续处理 |
| API 调用失败 | 打印错误，跳过该学生，继续 |
| 无 API Key | 打印错误并退出 (code 1) |

## 示例输出

```
============================================================
处理数据集: Zoe51530-9.8
============================================================
  ⟳ Alvin: 处理音频...
  ✓ Alvin: 已保存到 2_qwen_asr.json
  ✓ Kevin: 已处理过（跳过）
  ⊘ Lesson: 未找到音频文件
  ✗ Phoebe: 错误 - API 超时

============================================================
处理完成！
处理: 1, 跳过: 3
============================================================
```

## 命令行参数

| 参数 | 说明 | 例子 |
|------|------|------|
| `--dataset` | 数据集名称 (可选) | `--dataset Zoe51530-9.8` |
| `--student` | 学生名称 (需要 --dataset) | `--student Alvin` |
| `--api-key` | DashScope API 密钥 (可选) | `--api-key sk-xxxxx` |
| `-h, --help` | 显示帮助 | `-h` |

## 返回码

- `0`: 成功或部分成功
- `1`: 致命错误（参数错误、API Key 缺失、数据集不存在等）

## 向后兼容性

✅ **完全向后兼容**

- 现有 `process_all_students()` 函数保持不变
- 现有 `QwenASRProvider` 类无任何改动
- 默认行为（无 CLI 参数）与之前完全相同



## qwen3.py 核心流程
```
1. 加载题库 (CSV) → load_qb()
2. 加载ASR结果 (JSON/TXT) → load_asr_data()
3. 构建Prompt: system_prompt + qb_prompt + asr_prompt
4. 调用dashscope.Generation.call(model="qwen-plus", messages=[...])
5. 输出JSON评分报告
```

## 数据结构
- **系统提示** (system_prompt): 评分规则、错误类型定义、评级逻辑
- **题库提示** (qb_prompt): "以下是题库:" + CSV内容
- **ASR提示** (asr_prompt): "以下是学生回答:" + ASR转写
- **输出** (JSON): {final_grade_suggestion, mistake_count, annotations[...]}

## captioner_qwen3.py 用法
```bash
python3 scripts/captioner_qwen3.py <audio_file_path>
```
- 接收命令行参数: 音频文件路径
- 调用dashscope.Generation.call(model="qwen3-omni-30b-a3b-captioner", ...)
- 返回多模态音频转写结果

## 关键变量
- `audio_file_path`: 学生作业音频（qwen3.py中暂未使用）
- `asr_filepath`: ASR转写结果文件路径
- `qb_filepath`: 题库CSV文件路径
- `system_prompt`: 长文本，定义所有评分规则和指示

## 常见修改
| 操作 | 位置 |
|-----|------|
| 更换LLM模型 | `model="qwen-plus"` 参数 |
| 修改评分规则 | `system_prompt` 变量内容 |
| 更改输入文件 | `asr_filepath`、`qb_filepath` 变量 |
| 启用流式输出 | `stream=True` 参数 |
| 启用深度思考 | `enable_thinking=True` 参数 |

## 文件路径约定
- 相对路径: `"./data/caption_result.txt"`
- 多模态音频: `"file://./audio/sample.mp3"`
- 题库路径: `"./data/R1-65(1).csv"`

## 依赖
- `dashscope` (1.24.6) - 阿里云SDK
- `json` - 内置JSON处理
- `csv` - 内置CSV处理
- 环境变量: `DASHSCOPE_API_KEY`

## 调试
- 脚本直接打印完整API响应，查看 `response.output` 获取结果
- 检查 `response.status_code` 确认请求状态
- 错误信息位于 `response.usage` 中

---

# workflow.py - 统一工作流程（支持多种 ASR 引擎）

## 功能概述
提供端到端的命令行工作流，自动执行：
1. 音频转写 (ASR) - 支持 Qwen 和 FunASR 两种引擎
2. 题库加载
3. 发音评测
4. JSON报告输出

## 快速使用

### 基础用法（Qwen ASR，输出到控制台）
```bash
python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv
```

### 指定输出文件（Qwen ASR）
```bash
python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv --output result.json
```

### 使用 FunASR 引擎（从 .env 自动读取 OSS 配置 - 推荐）
```bash
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr
```
**说明**：OSS 配置（region、bucket、endpoint）自动从 `.env` 文件读取

### 使用 FunASR 引擎（命令行参数覆盖 .env）
```bash
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr --oss-region cn-hangzhou --oss-bucket your-bucket
```

### FunASR 引擎（带自定义端点）
```bash
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr --oss-region cn-hangzhou --oss-bucket your-bucket \
  --oss-endpoint oss-cn-hangzhou.aliyuncs.com
```

## 命令行参数

### 必需参数
| 参数 | 说明 |
|------|------|
| `--audio-path` | 音频文件路径（相对或绝对路径，支持 file:// 前缀） |
| `--qb-path` | 题库CSV文件路径 |

### 可选参数（通用）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--output` | 无（输出到控制台） | 输出文件路径 |
| `--api-key` | 环境变量 `DASHSCOPE_API_KEY` | DashScope API密钥 |
| `--asr-engine` | `qwen` | ASR 引擎选择（qwen/funasr） |

### FunASR 专用参数
| 参数 | 必需 | 说明 |
|------|------|------|
| `--oss-region` | 否（可从 .env 读取） | OSS 区域（如 cn-hangzhou）。优先级：命令行 > .env 文件 |
| `--oss-bucket` | 否（可从 .env 读取） | OSS 桶名称。优先级：命令行 > .env 文件 |
| `--oss-endpoint` | 否 | OSS 端点（如 oss-cn-hangzhou.aliyuncs.com）。可选，优先级：命令行 > .env 文件 |
| `--keep-oss-file` | 否 | 转写完成后是否保留 OSS 文件（默认删除） |

**参数优先级说明**：
- 优先级：命令行参数 > .env 文件配置 > 默认值
- .env 配置示例：
  ```env
  OSS_REGION=cn-shanghai
  OSS_BUCKET_NAME=quickfire-audio
  OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
  ```

## 工作流程图

### Qwen ASR 模式
```
┌─────────────────┐
│  输入参数验证   │
└────────┬────────┘
         │
┌────────▼────────────────────────────┐
│   Qwen 多模态音频转写 (ASR)          │
│   (captioner_qwen3.transcribe_audio) │
└────────┬────────────────────────────┘
         │
┌────────▼────────┐
│   加载题库      │ (qwen3.load_qb)
└────────┬────────┘
         │
┌────────▼────────┐
│   执行评测      │ (qwen3.evaluate_pronunciation)
│   生成报告      │
└────────┬────────┘
         │
┌────────▼────────┐
│   输出结果      │ (文件或控制台)
└─────────────────┘
```

### FunASR 模式
```
┌──────────────────────────────────┐
│  加载 .env 配置                   │
│  参数优先级处理                   │
│  (命令行 > .env > 默认值)        │
└────────┬─────────────────────────┘
         │
┌────────▼──────────────────┐
│  验证 OSS 凭证            │
│  (verify_oss_credentials)│
└────────┬──────────────────┘
         │
┌────────▼──────────────────┐
│   上传音频到 OSS          │
│   (upload_audio_to_oss)   │
└────────┬──────────────────┘
         │
┌────────▼──────────────────────┐
│   FunASR 异步转写            │
│   (transcribe_with_funasr)    │
└────────┬──────────────────────┘
         │
┌────────▼──────────────────────┐
│   标准化转写结果              │
│   (normalize_asr_output)      │
└────────┬──────────────────────┘
         │
┌────────▼────────┐
│   加载题库      │ (qwen3.load_qb)
└────────┬────────┘
         │
┌────────▼────────┐
│   执行评测      │ (qwen3.evaluate_pronunciation)
│   生成报告      │
└────────┬────────┘
         │
┌────────▼────────┐
│   输出结果      │ (文件或控制台)
└─────────────────┘
```

## 核心函数（模块化复用）

### workflow.py 新增函数（Phase 1: 核心基础设施）

#### `load_env_config(env_path: str = ".env") -> dict`
从 .env 文件读取 OSS 相关配置

**功能**：
- 自动加载 .env 文件中的 OSS 配置参数
- 支持读取：OSS_BUCKET_NAME、OSS_REGION、OSS_ENDPOINT
- .env 不存在时返回空字典（不中断流程）

**使用示例**：
```python
from workflow import load_env_config

config = load_env_config()  # 加载当前目录的 .env
print(config)  # {'bucket': 'quickfire-audio', 'region': 'cn-shanghai', ...}
```

#### `verify_oss_credentials(region: str, bucket: str, endpoint: str = None) -> tuple[bool, str]`
验证 OSS 凭证和参数的有效性

**功能**：
- 检查环境变量中的阿里云凭证（ALIBABA_CLOUD_ACCESS_KEY_*）
- 尝试连接 OSS 进行轻量级验证（head_bucket）
- 返回验证结果和详细的诊断信息

**使用示例**：
```python
from workflow import verify_oss_credentials

success, message = verify_oss_credentials(
    region='cn-shanghai',
    bucket='quickfire-audio',
    endpoint='oss-cn-shanghai.aliyuncs.com'
)
if success:
    print("✅ 凭证有效")
else:
    print(f"❌ {message}")  # 输出诊断建议
```

**诊断信息示例**：
```
❌ OSS 凭证验证失败: Access Denied

💡 诊断建议：
   - 检查 OSS 凭证权限（需要 GetBucketInfo 权限）
   - 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）
```

### 可导入的函数

#### qwen3.py
```python
from qwen3 import load_asr_data, load_qb, evaluate_pronunciation

# 加载ASR数据
asr_data = load_asr_data("path/to/asr.txt")

# 加载题库
qb_data = load_qb("path/to/qb.csv")

# 执行评测
result = evaluate_pronunciation(asr_data, qb_data, api_key="...", model="qwen-plus")
```

#### captioner_qwen3.py
```python
from captioner_qwen3 import transcribe_audio

# 转写音频 (Qwen 多模态)
asr_result = transcribe_audio("path/to/audio.mp3", api_key="...")
```

#### funasr_workflow.py（新增）
```python
from funasr_workflow import upload_audio_to_oss, transcribe_with_funasr, normalize_asr_output

# 上传音频到 OSS
oss_url, status, key = upload_audio_to_oss("path/to/audio.mp3", region="cn-hangzhou", bucket="your-bucket")

# FunASR 异步转写
funasr_result = transcribe_with_funasr(oss_url)

# 标准化输出
normalized_json = normalize_asr_output(funasr_result)
```

## 何时使用各种 ASR 引擎

| 场景 | 推荐引擎 | 原因 |
|------|--------|------|
| 快速单音频转写 | Qwen | 直接处理本地文件，无需上传 |
| 批量处理 | Qwen 或 FunASR | 两者都支持，FunASR 异步特性可能更高效 |
| 中文/口音识别 | FunASR | 专业 ASR 服务，针对复杂语音优化 |
| 生产环境 | FunASR | 阿里云官方服务，SLA 保证 |

## 环境变量配置

### 必需
```bash
export DASHSCOPE_API_KEY="sk-xxxxx"  # 阿里云 DashScope API 密钥
```

### FunASR 模式需要
```bash
# 方案 1：使用阿里云凭证（推荐）
export ALIBABA_CLOUD_ACCESS_KEY_ID="xxxxx"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="xxxxx"

# 方案 2：使用阿里云 credentials 文件
# ~/.alibabacloud/credentials (JSON 格式)
```

## 向后兼容性
- ✅ 原脚本保持独立可用性
- ✅ `qwen3.py` 仍可直接运行：`python3 qwen3.py`
- ✅ `captioner_qwen3.py` 仍可直接运行：`python3 captioner_qwen3.py <audio>`
- ✅ 不指定 `--asr-engine` 时自动使用 Qwen（向后兼容）
- ✅ 所有函数已提取为可重用模块

## 故障排除

### OSS 凭证缺失（FunASR 模式）
**症状**：
```
❌ 错误：使用 FunASR 模式必须指定以下参数：
   - OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)
   - OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)
```

**解决方案**：
1. 创建或更新 `.env` 文件：
   ```env
   OSS_REGION=cn-shanghai
   OSS_BUCKET_NAME=your-bucket-name
   OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
   ```

2. 或通过命令行参数指定：
   ```bash
   python3 workflow.py ... --oss-region cn-shanghai --oss-bucket your-bucket
   ```

### OSS 凭证验证失败
**症状**：
```
❌ OSS 凭证验证失败: Access Denied

💡 诊断建议：
   - 检查 OSS 凭证权限（需要 GetBucketInfo 权限）
   - 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）
```

**解决方案**：
1. 确保环境变量已设置：
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
   ```

2. 或使用阿里云凭证文件（~/.alibabacloud/credentials）

3. 确认凭证有以下权限：
   - oss:GetBucketInfo
   - oss:PutObject
   - oss:DeleteObject

### FunASR 上传失败
```
❌ 上传失败: OSS 上传失败
💡 诊断建议：
   - 检查 OSS 区域和桶名称是否正确
   - 验证 OSS 凭证权限（需要 PutObject 权限）
   - 检查环境变量是否配置（ALIBABA_CLOUD_*）
```

### FunASR 转写超时
```
❌ 转写超时：轮询 10 次后仍未完成
   请稍后查询任务 ID: task-xxxxx
```

---

# funasr_workflow.py - FunASR 工作流模块（新增）

## 功能概述
集成阿里云 FunASR 服务，提供以下功能：
1. 本地音频文件上传到 OSS
2. FunASR 异步转写任务提交和轮询
3. 结果标准化处理（转换为通用格式）

## 核心函数

### `upload_audio_to_oss(local_path, region, bucket, endpoint=None, keep_file=False)`
上传本地音频到阿里云 OSS

**参数**：
- `local_path` (str): 本地音频文件路径
- `region` (str): OSS 区域（如 cn-hangzhou）
- `bucket` (str): OSS 桶名称
- `endpoint` (str, optional): OSS 端点，默认使用默认端点
- `keep_file` (bool, optional): 转写后是否保留文件，默认 False

**返回**：
- `(oss_url, status_code, file_key)` - OSS URL、HTTP 状态码、文件 key

**示例**：
```python
from funasr_workflow import upload_audio_to_oss

oss_url, status, key = upload_audio_to_oss(
    "./audio/sample.mp3",
    region="cn-hangzhou",
    bucket="my-bucket"
)
print(f"上传完成: {oss_url}")
```

### `transcribe_with_funasr(oss_url, max_retries=10, retry_interval=2)`
使用 FunASR 转写 OSS 中的音频

**参数**：
- `oss_url` (str): OSS 中音频文件的 URL
- `max_retries` (int, optional): 最多轮询次数，默认 10 次
- `retry_interval` (int, optional): 轮询间隔（秒），默认 2 秒

**返回**：
- FunASR 转写结果对象

**示例**：
```python
from funasr_workflow import transcribe_with_funasr

result = transcribe_with_funasr("https://my-bucket.oss-cn-hangzhou.aliyuncs.com/audio/sample.mp3")
print(f"转写完成: {result.task_id}")
```

### `normalize_asr_output(funasr_result)`
将 FunASR 输出转换为标准格式（与 Qwen ASR 兼容）

**参数**：
- `funasr_result` (dict): FunASR 的原始输出

**返回**：
- 标准化的 JSON 字符串

**标准格式**：
```json
[
  {
    "speaker": "spk0",
    "text": "hello world",
    "start_time": 0,
    "end_time": 1500,
    "word_timestamp": [
      {"word": "hello", "start": 0, "end": 500},
      {"word": "world", "start": 800, "end": 1500}
    ]
  }
]
```

## 依赖

```
dashscope >= 1.24.6
alibabacloud_oss_v2 >= 0.3.0
```

## 使用示例

### 完整工作流
```python
from funasr_workflow import upload_audio_to_oss, transcribe_with_funasr, normalize_asr_output
import json

# 1. 上传
oss_url, _, _ = upload_audio_to_oss(
    "./audio/sample.mp3",
    region="cn-hangzhou",
    bucket="my-bucket"
)

# 2. 转写
funasr_result = transcribe_with_funasr(oss_url)

# 3. 标准化
normalized = normalize_asr_output(funasr_result)

# 4. 使用标准化结果
asr_data = json.loads(normalized)
print(f"转写了 {len(asr_data)} 条语句")
```
