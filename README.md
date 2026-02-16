# Quickfire 英语发音评测系统

自动化学生英语发音作业评估系统：预处理 → ASR 转写 + 音频输入 → LLM 评分 → 结构化反馈。

## 系统架构

```
原始视频/音频 → 预处理(转码+重命名+OSS) → Qwen ASR + Audio Input → LLM 评分 → 评分结果
      ↓                    ↓                   ↓                   ↓
  source media      1_input_audio.mp3     2_qwen_asr.json    4_llm_annotation.json
```

**DAG Pipeline**: `audio → qwen_asr → cards`

**当前策略**:
- 预处理阶段独立执行：`scripts/upload_missing_audio_to_oss.py`
- 统一使用音频输入进行 LLM 评测
- 先以 `sync` 模式进行 prompt 调试与模型对比
- 主流程入口为 `scripts/main.py`

## 快速开始

### 安装

```bash
# 安装依赖
uv sync

# 系统依赖
brew install ffmpeg  # macOS
```

### 配置

创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=sk-xxx      # 阿里云 Qwen API
GEMINI_API_KEY=AIzaSy...      # Google Gemini API
```

### 运行

```bash
# 预处理 + 上传 OSS（一键）
uv run python scripts/upload_missing_audio_to_oss.py run \
  --archive-batch Zoe51530_2025-12-16 \
  --source-dir /path/to/raw_media \
  --progress 130-18-EC

# 仅预处理（视频转音频 + 重命名）
uv run python scripts/upload_missing_audio_to_oss.py preprocess \
  --archive-batch Zoe51530_2025-12-16 \
  --source-dir /path/to/raw_media \
  --progress 130-18-EC

# 处理整个批次
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16

# 处理单个学生
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --student Qihang

# 预览模式
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --dry-run

# 指定评分模型（sync）
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator gemini-3-pro-preview --exec-mode sync
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator qwen3-omni-flash --exec-mode sync

# 只运行 ASR 阶段
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --only qwen_asr

# Qwen3-Omni 兼容测试入口（内部转调 main.py）
uv run python test_qwen_omni.py --archive-batch Zoe51530_2025-12-16 --student Qihang
```

## 批处理服务端（FastAPI）

适用于提交后持续轮询日志与结果的长任务（10-20 分钟）。

### 启动服务

```bash
uv run python scripts/batch_server.py
```

### 提交任务

```bash
curl -X POST http://127.0.0.1:8000/jobs \\
  -H 'Content-Type: application/json' \\
  -d '{
    "exec_mode": "batch",
    "archive_batch": "Zoe51530_2025-12-16",
    "students": ["Qihang"]
  }'
```

默认代理：`socks5://127.0.0.1:7890`。如需自定义，请在请求中传 `proxy` 字段。

```bash
curl -X POST http://127.0.0.1:8000/jobs \\
  -H 'Content-Type: application/json' \\
  -d '{
    "exec_mode": "batch",
    "archive_batch": "Zoe51530_2025-12-16",
    "students": ["Qihang"],
    "proxy": "socks5://127.0.0.1:7890"
  }'
```

### 轮询日志

```bash
curl "http://127.0.0.1:8000/jobs/{job_id}/logs?cursor=0"
```

### 获取结果（包含 token 消耗与耗时）

```bash
curl "http://127.0.0.1:8000/jobs/{job_id}/result"
```

## 数据结构

### 输入目录

```
quickfire_workflow/
├── questionbank/
│   └── {progress}.json              # 题库文件（全局共享）
└── archive/{batch_id}/
    ├── metadata.json                # 批次元数据
    ├── {Student1}/
    │   └── 1_input_audio.mp3        # 学生音频
    └── {Student2}/
        └── 1_input_audio.mp3
```

### 输出结果

```
archive/{batch_id}/{Student}/
├── 2_qwen_asr.json                  # ASR 转写 + token/时间统计
├── 2_qwen_asr_context.json          # ASR context + 题库引用
└── runs/{annotator}/{run_id}/
    ├── 4_llm_annotation.json        # 评分结果
    ├── prompt_log.txt               # 完整 LLM prompt
    └── run_manifest.json            # 输入文件 hash + git commit
```

**关键追踪数据** (用于迭代优化):
- ASR: `usage.seconds`, `usage.audio_tokens`, `qf_meta.vocabulary_path`
- LLM: `_metadata.timestamp`, `run_manifest.inputs` (输入文件 hash)

### 评分结果格式

```json
{
  "student_name": "Qihang",
  "final_grade_suggestion": "A",
  "mistake_count": { "errors": 0 },
  "annotations": [
    {
      "card_index": 1,
      "card_timestamp": "00:01",
      "question": "celebrate",
      "expected_answer": "庆祝",
      "related_student_utterance": {
        "detected_text": "庆祝",
        "issue_type": null
      }
    }
  ]
}
```

**评分规则**: A (0 错误) / B (1-2 错误) / C (3+ 错误)

**错误类型**: `null` (正确) / `NO_ANSWER` (未作答) / `MEANING_ERROR` (意思错误)

## 模块说明

| 模块 | 说明 |
|------|------|
| `scripts/upload_missing_audio_to_oss.py` | 预处理（视频转音频/重命名）+ OSS 上传 |
| `scripts/main.py` | DAG 主入口 |
| `scripts/asr/qwen.py` | Qwen3-ASR (自动分段长音频) |
| `scripts/annotators/` | LLM 评分器 (Gemini/Qwen Omni) |
| `scripts/common/` | 通用工具 |

## 支持的模型

| 评分器 | 模型 | 输入方式 |
|--------|------|---------|
| Gemini Audio | `gemini-3-pro-preview` (默认), `gemini-2.5-pro`, `gemini-2.0-flash` | 音频直传 |
| Qwen3-Omni | `qwen3-omni-flash` | 音频直传 (OpenAI 兼容) |

## 命令参数

| 参数 | 说明 |
|------|------|
| `--archive-batch` | 批次 ID (必须) |
| `--student` | 指定学生 |
| `--annotator` | 评分模型 |
| `--exec-mode` | 执行模式: `sync` / `batch` |
| `--batch` | `--exec-mode batch` 的兼容简写 |
| `--only` | 只运行指定阶段: `audio`, `qwen_asr`, `cards` |
| `--until` | 运行到指定阶段为止 |
| `--dry-run` | 预览模式 |
| `--force` | 强制重新处理 |

## 性能

| 指标 | 数值 |
|------|------|
| ASR 速度 | ~6-7 分钟/学生 |
| 评分速度 | ~2-3 分钟/学生 |
| 长音频 | 自动分段并行处理 |
| 重试 | 5 次，间隔 5 秒 |

## 后端集成

详见 [后端接口协议文档](docs/backend-integration.md)

**后端需提供**:
- `questionbank/{progress}.json` - 题库（全局共享）
- `archive/{batch_id}/metadata.json` - 批次元数据
- `archive/{batch_id}/{student}/1_input_audio.mp3` - 学生音频

**系统输出**:
- `4_llm_annotation.json` - 评分结果 (成绩 A/B/C + 逐题详情)

## 开发

```bash
# 安装开发依赖
uv sync

# 运行测试（使用真实音频，禁止 mock）
uv run python scripts/main.py --archive-batch TestBatch --dry-run
```

## 依赖

- Python 3.12+
- ffmpeg / ffprobe
- dashscope (阿里云 Qwen)
- google-genai (Google Gemini)

---

**版本**: 2.1.0
**更新**: 2026-02-16
