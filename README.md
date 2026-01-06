# Quickfire 英语发音评测系统

自动化学生英语发音作业评估系统：音频 → ASR 转写 → LLM 评分 → 结构化反馈。

## 系统架构

```
学生音频 → Qwen ASR → LLM 评分 → 评分结果
    ↓          ↓          ↓          ↓
1_input    2_qwen     gatekeeper  4_llm_
_audio.mp3 _asr.json   (质检)     annotation.json
```

**DAG Pipeline**: `audio → qwen_asr → gatekeeper → cards`

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
# 处理整个批次
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16

# 处理单个学生
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --student Qihang

# 预览模式
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --dry-run

# 指定评分模型
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator qwen-max

# 只运行 ASR 阶段
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --only qwen_asr
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
├── 2_qwen_asr.json                  # ASR 转写
├── 2_qwen_asr_hotwords.json         # 热词日志
└── runs/{annotator}/{run_id}/
    ├── 4_llm_annotation.json        # 评分结果
    ├── prompt_log.txt               # 提示词日志
    └── run_metadata.json            # 运行元数据
```

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
| `scripts/main.py` | DAG 主入口 |
| `scripts/asr/qwen.py` | Qwen3-ASR (自动分段长音频) |
| `scripts/asr/funasr.py` | FunASR 时间戳 |
| `scripts/annotators/` | LLM 评分器 (Gemini/Qwen) |
| `scripts/gatekeeper/` | ASR 质检门禁 |
| `scripts/common/` | 通用工具 |

## 支持的模型

| 评分器 | 模型 |
|--------|------|
| Gemini | `gemini-3-pro-preview`, `gemini-2.5-pro`, `gemini-2.0-flash` |
| Qwen | `qwen-max`, `qwen-max-latest`, `qwen3-max` |

## 命令参数

| 参数 | 说明 |
|------|------|
| `--archive-batch` | 批次 ID (必须) |
| `--student` | 指定学生 |
| `--annotator` | 评分模型 |
| `--only` | 只运行指定阶段: `audio`, `qwen_asr`, `gatekeeper`, `cards` |
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

**版本**: 2.0.0
**更新**: 2026-01-06
