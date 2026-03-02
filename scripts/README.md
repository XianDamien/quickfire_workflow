# Scripts 目录文档

## 目录定位

`scripts/` 是 Quickfire 的执行入口。

当前标准 workflow：

`预处理（视频转音频 + 重命名 + 上传 OSS） -> audio-asr（qwen3-asr）+ audio 输入 -> llm（gemini-3-pro-preview / qwen3-omni-flash）`

执行模式：
- 默认 `sync`（用于 prompt 调试、模型对比）
- 可切换 `batch`（批量生产）

---

## 关键脚本

### 1) 预处理阶段
- `upload_missing_audio_to_oss.py`
  - `preprocess`: 原始视频/音频 -> `archive/{batch}/{student}/1_input_audio.mp3`
  - `upload`: 上传音频到 OSS 并更新 `metadata.json`
  - `run`: 串联执行 `preprocess + upload`

### 2) 主流程阶段
- `main.py`
  - DAG: `audio -> qwen_asr -> cards`
  - `--exec-mode sync|batch`（默认 `sync`）

### 3) Batch 服务化
- `batch_server.py`: FastAPI 任务提交/轮询服务
- `test_batch_server.py`: Python 联调
- `test_batch_server.sh`: Shell 联调

### 4) 模块目录
- `asr/`: ASR provider（Qwen3-ASR）
- `annotators/`: LLM annotator（Gemini Audio / Qwen3 Omni）
- `common/`: 通用工具
- `contracts/`: 数据契约

---

## 推荐命令

### 预处理（推荐先执行）

```bash
# 一键：预处理 + 上传 OSS
uv run python scripts/upload_missing_audio_to_oss.py run \
  --archive-batch Zoe51530_2025-12-16 \
  --source-dir /path/to/raw_media \
  --progress 130-18-EC

# 仅预处理（转码 + 重命名）
uv run python scripts/upload_missing_audio_to_oss.py preprocess \
  --archive-batch Zoe51530_2025-12-16 \
  --source-dir /path/to/raw_media \
  --progress 130-18-EC
```

### 主流程（默认 sync）

```bash
# sync（默认）
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator gemini-3-pro-preview --exec-mode sync
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator qwen3-omni-flash --exec-mode sync

# 仅跑 ASR
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --only qwen_asr
```

### Batch

```bash
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --exec-mode batch
```
