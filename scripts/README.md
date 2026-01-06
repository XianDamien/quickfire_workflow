# Scripts 目录文档

## 目录概述

本目录包含 Quickfire 语音教学评估系统的核心处理脚本，实现从音频录制到自动评分的完整工作流。系统采用模块化设计，支持 DAG 驱动的批处理流程。

### 目录结构

```
scripts/
├── main.py                              # DAG 驱动的主入口脚本
├── process_new_recordings.py            # 新录音预处理工具
├── migrate_backend_input_to_archive.py  # 数据迁移工具
├── update_oss_urls.py                   # OSS URL 更新工具
├── qwen_audio.py                        # Qwen ASR 测试脚本
│
├── asr/                                 # ASR 转写模块
│   ├── __init__.py
│   ├── qwen.py                          # Qwen3-ASR Provider (文本转写)
│   └── funasr.py                        # FunASR Provider (时间戳转写)
│
├── annotators/                          # LLM 标注模块
│   ├── __init__.py
│   ├── base.py                          # Annotator 基础接口
│   ├── config.py                        # 配置文件
│   ├── gemini.py                        # Gemini Annotator 实现
│   └── qwen.py                          # Qwen Annotator 实现
│
├── common/                              # 通用工具模块
│   ├── __init__.py
│   ├── archive.py                       # Archive 路径与元数据管理
│   ├── env.py                           # 环境变量加载
│   ├── hash.py                          # 哈希工具
│   ├── naming.py                        # 命名解析工具
│   └── runs.py                          # Run 管理工具
│
├── contracts/                           # 数据契约与验证
│   ├── __init__.py
│   ├── asr_timestamp.py                 # ASR 时间戳数据格式
│   └── cards.py                         # 标注结果数据格式
│
└── _legacy/                             # 已废弃的旧脚本
    ├── qwen_asr.py
    ├── funasr.py
    └── Gemini_annotation.py
```

---

## 核心脚本说明

### 1. main.py - DAG 驱动的主入口

**功能**: 一键执行完整的音频处理和评估流程

**DAG 流程**:
```
audio → qwen_asr → timestamps → cards
```

**用法**:

```bash
# 完整流程（默认到 cards 阶段）
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08

# 指定学生
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar

# 只执行某个阶段
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --only qwen_asr

# 执行到某个阶段为止
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --until timestamps

# 指定 annotator 模型
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --annotator gemini-2.5-pro

# 强制重新处理
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --force

# 干运行（预览）
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --dry-run
```

**参数说明**:
- `--archive-batch`, `-b`: Archive 批次 ID（必需）
- `--student`, `-s`: 学生名字（支持模糊匹配）
- `--target`, `-t`: 目标阶段（默认: cards）
- `--only`: 只执行指定阶段
- `--until`: 执行到指定阶段为止
- `--annotator`, `-a`: LLM 模型（默认: gemini-2.5-pro）
- `--force`, `-f`: 强制重新处理
- `--dry-run`, `-n`: 干运行模式

**阶段说明**:
- **audio**: 检查音频文件是否存在
- **qwen_asr**: Qwen3-ASR 文本转写（输出: `2_qwen_asr.json`）
- **timestamps**: FunASR 时间戳转写（输出: `3_asr_timestamp.json`）
- **cards**: LLM 标注评分（输出: `runs/{annotator}/{run_id}/4_llm_annotation.json`）

**Provider 约束**:
- qwen_asr 阶段: 只能使用 Text provider (QwenASRProvider)
- timestamps 阶段: 只能使用 Timestamp provider (FunASRTimestampProvider)

---

### 2. process_new_recordings.py - 新录音预处理

**功能**:
1. MP4 转 MP3
2. 上传到 OSS
3. 创建 archive 目录结构和 metadata.json

**用法**:

编辑脚本中的源文件夹路径，然后执行:

```bash
python3 scripts/process_new_recordings.py
```

**输入**: 本地文件夹（格式: `{ClassCode}_{Date}_{Progress}`）

**输出**:
- `archive/{ClassCode}_{Date}/{Student}/1_input_audio.mp3`
- `archive/{ClassCode}_{Date}/metadata.json`

**依赖**:
- ffmpeg（用于音频转换）
- oss2（用于 OSS 上传）
- 环境变量: OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME

---

### 3. migrate_backend_input_to_archive.py - 数据迁移工具

**功能**: 将旧的 `backend_input/*.mp3` 迁移到新的 archive 目录结构

**用法**:

```bash
# 迁移所有文件
python3 scripts/migrate_backend_input_to_archive.py

# 预览模式
python3 scripts/migrate_backend_input_to_archive.py --dry-run

# 只迁移指定班级
python3 scripts/migrate_backend_input_to_archive.py --class Zoe41900
```

**参数说明**:
- `--dry-run`: 预览模式，不实际执行
- `--class`: 只迁移指定班级
- `--move`: 移动文件而不是复制（删除源文件）

**输出**:
- `archive/{ClassCode}_{Date}/{Student}/1_input_audio.mp3`
- `archive/{ClassCode}_{Date}/{Student}/3_asr_timestamp.json`（如果存在）
- `archive/{ClassCode}_{Date}/metadata.json`

---

### 4. update_oss_urls.py - OSS URL 更新工具

**功能**: 从 CSV 文件读取 OSS URL 映射，更新到 metadata.json

**用法**:

```bash
# 更新 OSS URLs
python3 scripts/update_oss_urls.py /path/to/export_urls.csv

# 预览模式
python3 scripts/update_oss_urls.py /path/to/export_urls.csv --dry-run
```

**CSV 格式**:
```csv
object,url
audio%2FZoe41900_2025-09-08_R1-65-D5_Oscar.mp3,https://...
```

**参数说明**:
- `csv_file`: CSV 文件路径（必需）
- `--dry-run`: 预览模式，不实际修改文件

---

### 5. qwen_audio.py - Qwen ASR 测试脚本

**功能**: 测试 Qwen3-ASR 文件转写 API

**用法**: 编辑脚本中的配置后直接运行

```bash
python3 scripts/qwen_audio.py
```

**配置项**:
- `API_KEY`: DashScope API Key
- `AUDIO_URL`: 音频文件 URL

---

## 模块说明

### ASR 模块 (`asr/`)

#### qwen.py - Qwen3-ASR Provider

**功能**:
- Qwen3-ASR 语音转写（文本）
- 支持自定义词汇表/热词上下文
- 长音频自动分段并行处理
- 多种输入格式（本地文件、URL）

**核心类**: `QwenASRProvider`

**示例**:

```python
from scripts.asr.qwen import QwenASRProvider

provider = QwenASRProvider()
result = provider.transcribe_and_save_with_segmentation(
    input_audio_path="audio.mp3",
    output_dir="output/",
    vocabulary_path="vocab.json",
    segment_duration=180,
    max_workers=3
)
```

**特性**:
- 自动分段: 超过 180 秒的音频自动分割
- 并行处理: 使用线程池并行转写多个片段
- 热词优化: 支持题库热词上下文优化识别准确率
- 双语支持: 自动检测中英双语

**输出格式**: `2_qwen_asr.json` (Qwen API 响应格式)

---

#### funasr.py - FunASR Timestamp Provider

**功能**:
- FunASR 语音转写（带时间戳）
- 句子级别时间戳生成
- 基于题库的动态热词管理
- 异步批量转写

**核心类**: `FunASRTimestampProvider`

**示例**:

```python
from scripts.asr.funasr import FunASRTimestampProvider

provider = FunASRTimestampProvider()
result = provider.transcribe_with_timestamp(
    audio_url="https://...",
    vocabulary_path="vocab.json"
)
```

**特性**:
- 时间戳: 支持句子级和词级时间戳
- 热词管理: 自动从题库提取热词并管理热词槽位
- 语言检测: 自动检测中英文并标记
- OSS 优先: 优先使用 OSS URL，fallback 到本地文件

**输出格式**: `3_asr_timestamp.json`

```json
{
  "file_url": "https://...",
  "transcripts": [{
    "channel_id": 0,
    "transcript": "完整文本",
    "sentences": [{
      "begin_time": 0,
      "end_time": 1500,
      "text": "句子文本",
      "words": [{
        "begin_time": 0,
        "end_time": 500,
        "text": "词"
      }]
    }]
  }]
}
```

---

### 热词元数据日志

ASR 模块在处理过程中会保存使用的热词信息，用于调试和审计。

#### Qwen ASR 热词日志

**文件**: `2_qwen_asr_hotwords.json`

**位置**: `archive/{batch}/{student}/`

**格式**:

```json
{
  "vocabulary_path": "archive/Zoe41900_2025-09-08/_shared_context/R1-65.json",
  "hotwords": ["all", "both", "double", "each", "half", "not", "part", "一半", "不", ...],
  "count": 42,
  "sha256": "abc123...",
  "created_at": "2026-01-03T10:00:00Z",
  "provider": "qwen3-asr",
  "model": "qwen3-asr-flash"
}
```

#### FunASR 热词日志

**文件**: `3_asr_timestamp_hotwords.json`

**位置**: `archive/{batch}/{student}/`

**格式**:

```json
{
  "vocabulary_path": "archive/Zoe41900_2025-09-08/_shared_context/R1-65.json",
  "hotwords": [
    {"text": "not", "weight": 4, "lang": "en"},
    {"text": "双倍的", "weight": 4, "lang": "zh"},
    ...
  ],
  "count": 42,
  "sha256": "def456...",
  "created_at": "2026-01-03T10:00:00Z",
  "provider": "fun-asr",
  "model": "fun-asr",
  "vocabulary_id": "vocab-20250103-xyz"
}
```

#### 用途

- **调试**: 验证 ASR 使用了正确的热词
- **审计**: 追踪热词变更历史
- **复现**: 使用相同热词重新运行转写
- **排查**: 热词配置问题的诊断入口

---

### Annotators 模块 (`annotators/`)

#### base.py - Annotator 基础接口

**功能**: 定义所有 annotator 的统一接口

**核心类**:
- `AnnotatorInput`: 输入数据结构
- `AnnotatorOutput`: 输出结果结构
- `BaseAnnotator`: 抽象基类

**数据结构**:

```python
@dataclass
class AnnotatorInput:
    archive_batch: str
    student_name: str
    question_bank_path: Path
    qwen_asr_path: Path
    asr_timestamp_path: Path
    run_id: Optional[str] = None
    verbose: bool = False
    force: bool = False
    # 延迟加载的内容
    question_bank_content: Optional[str] = None
    asr_text: Optional[str] = None
    asr_with_timestamp: Optional[str] = None

@dataclass
class AnnotatorOutput:
    success: bool
    error: Optional[str] = None
    student_name: str = ""
    final_grade: str = "C"
    mistake_count: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    run_id: str = ""
    run_dir: Optional[Path] = None
    model: str = "unknown"
    prompt_hash: str = ""
    response_time_ms: Optional[float] = None
```

---

#### gemini.py - Gemini Annotator

**功能**: 使用 Google Gemini API 进行学生回答标注和评分

**核心类**: `GeminiAnnotator`

**支持的模型**:
- gemini-2.5-pro (默认)
- gemini-2.0-flash
- gemini-3-pro-preview

**示例**:

```python
from scripts.annotators.gemini import GeminiAnnotator

annotator = GeminiAnnotator(
    model="gemini-2.5-pro",
    temperature=0.2,
    max_retries=5
)

output = annotator.annotate(input_data)
```

**特性**:
- 重试机制: 最多重试 5 次
- 响应时间追踪: 记录 API 响应时间
- 提示词管理: 自动加载和渲染提示词模板
- 校验机制: 严格校验输出格式和时间戳

**输出格式**: `runs/{annotator}/{run_id}/4_llm_annotation.json`

```json
{
  "student_name": "Oscar",
  "final_grade_suggestion": "A",
  "mistake_count": {
    "pronunciation": 2,
    "grammar": 0,
    "vocabulary": 1
  },
  "annotations": [{
    "question_number": 1,
    "question": "not",
    "student_answer": "not",
    "timestamp_range": [1000, 2500],
    "is_correct": true,
    "error_type": null
  }],
  "_metadata": {
    "model": "gemini-2.5-pro",
    "response_time_ms": 3245,
    "prompt_version": "v3.0",
    "run_id": "20250101_120000_abc123",
    "git_commit": "e2d253f...",
    "timestamp": "2025-01-01T12:00:00"
  }
}
```

---

#### qwen.py - Qwen Annotator

**功能**: 使用阿里云通义千问 API 进行学生回答标注和评分

**核心类**: `QwenAnnotator`

**支持的模型**:
- qwen-max (默认)
- qwen-max-latest
- qwen3-max

**示例**:

```python
from scripts.annotators.qwen import QwenAnnotator

annotator = QwenAnnotator(
    model="qwen-max",
    temperature=0.2,
    max_retries=5
)

output = annotator.annotate(input_data)
```

**使用命令行**:

```bash
# 使用 Qwen 模型进行评分
python scripts/main.py \
    --archive-batch Zoe51530_2025-09-08 \
    --student Stefan \
    --only cards \
    --annotator qwen-max

# 使用其他 Qwen 模型
python scripts/main.py \
    --archive-batch Zoe51530_2025-09-08 \
    --annotator qwen-max-latest
```

**特性**:
- API 来源: 阿里云 DashScope
- 重试机制: 最多重试 5 次
- 响应时间追踪: 记录 API 响应时间
- 提示词管理: 复用与 Gemini 相同的提示词模板
- 校验机制: 严格校验输出格式和时间戳

**环境变量**:
- `DASHSCOPE_API_KEY`: 阿里云 API 密钥（必需）

**输出格式**: 与 Gemini Annotator 完全一致

```json
{
  "student_name": "Stefan",
  "final_grade_suggestion": "A",
  "mistake_count": {
    "errors": 0
  },
  "annotations": [...],
  "_metadata": {
    "model": "qwen-max",
    "response_time_ms": 2145,
    ...
  }
}
```

---

### Common 模块 (`common/`)

#### archive.py - Archive 路径与元数据管理

**功能**: 提供统一的 archive 目录结构访问 API

**核心函数**:

```python
from scripts.common.archive import (
    project_root,           # 获取项目根目录
    archive_batch_dir,      # 获取 batch 目录
    student_dir,            # 获取学生目录
    find_audio_file,        # 查找音频文件
    load_metadata,          # 加载 metadata.json
    list_students,          # 列出所有学生
    resolve_question_bank,  # 解析题库路径
    load_file_content       # 加载文件内容
)
```

**音频文件查找优先级**:
1. `1_input_audio.*`（任何支持格式）
2. `<StudentName>.*`（匹配目录名）
3. 第一个找到的音频文件

**支持的音频格式**: `.mp3`, `.mp4`, `.wav`, `.m4a`, `.flac`, `.ogg`

**题库解析优先级**:
1. `metadata.question_bank_path`（指向 questionbank/）
2. `metadata.question_bank_file`（在 archive 目录下）
3. `metadata.progress` 在 questionbank/ 中查找
4. `_shared_context/R*.json`（向后兼容）

---

#### env.py - 环境变量加载

**功能**: 统一加载环境变量（.env 文件）

**用法**:

```python
from scripts.common.env import load_env

load_env()  # 自动查找 scripts/.env
```

**环境变量**:
- `DASHSCOPE_API_KEY`: 阿里云 DashScope API Key
- `GEMINI_API_KEY`: Google Gemini API Key
- `OSS_ACCESS_KEY_ID`: OSS Access Key ID
- `OSS_ACCESS_KEY_SECRET`: OSS Access Key Secret
- `OSS_ENDPOINT`: OSS Endpoint
- `OSS_BUCKET_NAME`: OSS Bucket 名称
- `OSS_PUBLIC_BASE_URL`: OSS 公开访问 URL

---

#### hash.py - 哈希工具

**功能**: 计算文件和文本的 SHA256 哈希值

**核心函数**:

```python
from scripts.common.hash import file_hash, text_hash

# 文件哈希
hash_value = file_hash("path/to/file", prefix=True)
# 返回: "sha256:abc123..."

# 文本哈希
hash_value = text_hash("some text", prefix=False)
# 返回: "abc123..."
```

---

#### naming.py - 命名解析工具

**功能**: 解析文件名和 batch ID

**核心函数**:

```python
from scripts.common.naming import (
    parse_backend_input_mp3_name,
    parse_archive_batch_id,
    extract_progress_from_questionbank,
    build_file_id
)

# 解析音频文件名
parsed = parse_backend_input_mp3_name("Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3")
# 返回: {
#   "class_code": "Zoe41900",
#   "date": "2025-09-08",
#   "question_bank": "R1-65-D5",
#   "student_name": "Oscar"
# }
```

---

#### runs.py - Run 管理工具

**功能**: 管理 runs 目录结构和元数据

**核心函数**:

```python
from scripts.common.runs import (
    new_run_id,           # 生成新的 run_id
    ensure_run_dir,       # 确保 run 目录存在
    write_run_manifest,   # 写入 run manifest
    get_git_commit        # 获取 Git commit
)

# 生成 run_id
run_id = new_run_id()
# 返回: "20250101_120000_abc123"

# 创建 run 目录
run_dir = ensure_run_dir(
    archive_batch="Zoe41900_2025-09-08",
    student_name="Oscar",
    annotator_name="gemini-2.5-pro",
    run_id=run_id
)
# 返回: archive/Zoe41900_2025-09-08/Oscar/runs/gemini-2.5-pro/20250101_120000_abc123/
```

---

### Contracts 模块 (`contracts/`)

#### asr_timestamp.py - ASR 时间戳数据格式

**功能**: 提取和验证 ASR 时间戳数据

**核心函数**:

```python
from scripts.contracts.asr_timestamp import extract_timestamp_text

# 提取带时间戳的文本
timestamp_text = extract_timestamp_text("path/to/3_asr_timestamp.json")
# 返回: "[0-1500ms] 句子一 [1500-3000ms] 句子二"
```

---

#### cards.py - 标注结果数据格式

**功能**: 验证和解析 LLM 标注结果

**核心函数**:

```python
from scripts.contracts.cards import validate_cards, parse_api_response

# 解析 API 响应
parsed = parse_api_response(raw_response)
# 返回: {
#   "annotations": [...],
#   "final_grade_suggestion": "A",
#   "mistake_count": {...}
# }

# 校验标注结果
is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
```

---

## 工作流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    Quickfire 工作流                          │
└─────────────────────────────────────────────────────────────┘

1. 新录音处理
   ┌──────────────┐
   │ 本地 MP4 文件 │
   └──────┬───────┘
          │ process_new_recordings.py
          ↓
   ┌──────────────┐     ┌───────────┐
   │  MP4 → MP3   │────→│ Upload OSS│
   └──────┬───────┘     └─────┬─────┘
          │                   │
          ↓                   ↓
   ┌──────────────────────────────────┐
   │ archive/{batch}/{student}/       │
   │   1_input_audio.mp3              │
   │ archive/{batch}/metadata.json    │
   └──────────────┬───────────────────┘
                  │
                  │ main.py --archive-batch {batch}
                  ↓

2. DAG 处理流程

   Stage: audio
   ┌──────────────────┐
   │ 检查音频文件存在  │
   └────────┬─────────┘
            │
            ↓
   Stage: qwen_asr (QwenASRProvider)
   ┌──────────────────┐
   │ Qwen3-ASR 转写   │
   │ - 热词优化        │
   │ - 自动分段        │
   │ - 并行处理        │
   └────────┬─────────┘
            │ 输出: 2_qwen_asr.json
            ↓
   Stage: timestamps (FunASRTimestampProvider)
   ┌──────────────────┐
   │ FunASR 时间戳转写 │
   │ - 句子级时间戳    │
   │ - 词级时间戳      │
   │ - 热词管理        │
   └────────┬─────────┘
            │ 输出: 3_asr_timestamp.json
            ↓
   Stage: cards (GeminiAnnotator)
   ┌──────────────────┐
   │ LLM 标注评分     │
   │ - 提取学生回答    │
   │ - 错误类型分析    │
   │ - 生成评分建议    │
   └────────┬─────────┘
            │ 输出: runs/{annotator}/{run_id}/4_llm_annotation.json
            ↓
   ┌──────────────────┐
   │  处理完成         │
   └──────────────────┘

3. 数据迁移（可选）
   ┌──────────────────┐
   │ backend_input/   │
   │   *.mp3          │
   └────────┬─────────┘
            │ migrate_backend_input_to_archive.py
            ↓
   ┌──────────────────┐
   │ archive/{batch}/ │
   └──────────────────┘
```

---

## 依赖关系

### Python 包依赖

```
dashscope>=1.14.0      # 阿里云 ASR API
google-genai>=1.0.0    # Google Gemini API
oss2>=2.18.0           # 阿里云 OSS
requests>=2.31.0       # HTTP 请求
python-dotenv>=1.0.0   # 环境变量加载
```

### 系统工具依赖

```
ffmpeg   # 音频转换和分割
ffprobe  # 音频元数据探测
```

### 安装依赖

```bash
# Python 包
pip install -r requirements.txt

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# 下载 ffmpeg 并添加到 PATH
```

---

## 环境变量配置

创建 `scripts/.env` 文件:

```bash
# DashScope (Qwen & FunASR)
DASHSCOPE_API_KEY=sk-xxxxx

# Google Gemini
GEMINI_API_KEY=AIzaSyxxxxx

# 阿里云 OSS
OSS_ACCESS_KEY_ID=LTAI5xxxxx
OSS_ACCESS_KEY_SECRET=xxxxx
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_BUCKET_NAME=quickfire-audio
OSS_PUBLIC_BASE_URL=https://quickfire-audio.oss-cn-shanghai.aliyuncs.com
```

---

## 数据约定

### Archive 目录结构

符合 `docs/dataset_conventions.md` 规范:

```
archive/{ClassCode}_{Date}/
├── metadata.json                    # 班级元数据
├── {Student}/
│   ├── 1_input_audio.mp3           # 原始音频
│   ├── 2_qwen_asr.json             # Qwen ASR 转写结果
│   ├── 2_qwen_asr_hotwords.json    # Qwen ASR 热词元数据
│   ├── 3_asr_timestamp.json        # FunASR 带时间戳转写
│   ├── 3_asr_timestamp_hotwords.json # FunASR 热词元数据
│   └── runs/
│       └── {annotator}/
│           └── {run_id}/
│               ├── 4_llm_annotation.json
│               ├── prompt_log.txt
│               └── run_metadata.json
└── reports/
    └── {run_id}/
        └── batch_annotation_report.json
```

### metadata.json 格式

```json
{
  "schema_version": 1,
  "dataset_id": "Zoe41900_2025-09-08",
  "class_code": "Zoe41900",
  "date": "2025-09-08",
  "progress": "R1-65-D5",
  "question_bank_path": "questionbank/R1-65-D5.json",
  "items": [
    {
      "file_id": "Zoe41900_2025-09-08_R1-65-D5_Oscar",
      "student": "Oscar",
      "local_path": "archive/Zoe41900_2025-09-08/Oscar/1_input_audio.mp3",
      "oss_url": "https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/..."
    }
  ],
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-01-01T12:00:00"
}
```

---

## 常见问题

### Q: 如何添加新的 annotator?

1. 在 `annotators/` 目录创建新文件
2. 继承 `BaseAnnotator` 类
3. 实现 `annotate()` 方法
4. 在 `annotators/__init__.py` 注册
5. 在 `annotators/config.py` 添加配置

### Q: 如何处理长音频文件?

Qwen ASR Provider 自动处理:
- 超过 180 秒自动分段
- 并行处理各段
- 自动合并结果

可通过参数调整:

```python
provider.transcribe_and_save_with_segmentation(
    input_audio_path="long_audio.mp3",
    segment_duration=300,  # 5 分钟分段
    max_workers=5          # 5 个并行线程
)
```

### Q: 如何自定义热词?

题库文件格式:

```json
[
  {
    "question": "not, double, half",
    "answer": "不, 双倍的, 一半",
    "hint": "adv"
  }
]
```

系统自动提取所有 question 和 answer 字段作为热词。

### Q: 如何调试 LLM 输出?

1. 使用 `--verbose` 查看完整提示词:

```bash
python3 scripts/main.py --archive-batch {batch} --verbose
```

2. 查看 `prompt_log.txt`:

```
runs/{annotator}/{run_id}/prompt_log.txt
```

3. 校验失败时查看原始输出:

```
runs/{annotator}/{run_id}/raw_api_output_debug.txt
```

### Q: 如何处理 API 超时或失败?

系统内置重试机制:
- Gemini Annotator: 最多重试 5 次
- 每次重试间隔 5 秒
- 可通过参数调整:

```python
annotator = GeminiAnnotator(
    max_retries=10,
    retry_delay=10
)
```

---

## 开发指南

### 添加新的处理阶段

1. 在 `main.py` 的 `DAG_STAGES` 添加阶段名
2. 实现 `run_{stage}()` 函数
3. 在 `run_stage()` 添加分支处理
4. 实现 `check_stage_complete()` 检查逻辑

### 模块化原则

- ASR 模块: 只负责语音转文字
- Annotator 模块: 只负责标注评分
- Common 模块: 提供通用工具函数
- Contracts 模块: 定义数据格式和验证

### 代码风格

- 使用 Type Hints
- 遵循 PEP 8
- 函数文档使用 Google Style
- 错误处理使用 try-except

---

## 性能优化

### 并行处理

- Qwen ASR: 自动并行处理音频片段
- 批量处理: 使用 `ThreadPoolExecutor`

### 缓存机制

- 热词槽位复用: 避免重复创建
- 跳过已处理: 检查输出文件是否存在（除非 `--force`）

### 资源管理

- 临时文件自动清理
- 音频分段后及时删除
- API 连接池复用

---

## 更新日志

### 2025-01-01
- 重构为模块化架构
- 添加 DAG 驱动的主入口
- 统一 Provider 接口
- 改进错误处理和日志

### 2024-12-19
- 迁移到 archive 目录结构
- 添加 metadata.json 支持
- 实现 runs 目录管理

---

## 许可证

内部项目，保留所有权利。
