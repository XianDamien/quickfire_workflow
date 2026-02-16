# Scripts 目录文档

## 目录定位

`scripts/` 是 Quickfire 的执行与评测入口目录。

当前约定：
- 统一主入口：`scripts/main.py`
- 统一音频输入进行 LLM 评测
- 第一阶段以 `sync` 为主（用于 prompt 调试与模型对比）
- 重点模型对比：`gemini-*` vs `qwen3-omni-flash`

---

## 功能分类（按功能 + 内容）

### 1) 主流程编排（Core Pipeline）

- `main.py`：统一 DAG 主入口（`audio -> qwen_asr -> cards`）
- `gemini_batch_audio.py`：Batch 主实现（统一音频直传）

> 说明：当前日常测试推荐 `main.py --exec-mode sync`。

### 2) 模型评估与结果分析（Evaluation）

- `compare_annotators.py`：对比不同 annotator 输出
- `compare_asr_audio.py`：对比 ASR 路径与音频直传路径
- `consolidate_grades.py`：整合评分结果到统一报表

### 3) 数据运维与治理（Data Ops）

- `migrate_backend_input_to_archive.py`：历史输入迁移到 archive 结构
- `upload_missing_audio_to_oss.py`：补传 OSS URL
- `add_audio_duration.py`：补充音频时长
- `cleanup_deprecated_runs.py`：清理过时 runs

### 4) 服务化与联调（Service & Debug）

- `batch_server.py`：Batch API 服务端（FastAPI）
- `test_batch_server.py`：服务端 API 联调脚本
- `test_batch_server.sh`：Shell 版联调脚本

### 5) 支撑模块（Shared Modules）

- `asr/`：ASR provider（Qwen/FunASR）
- `annotators/`：LLM annotator（Gemini / Qwen Omni）
- `common/`：公共工具（env、archive、runs、hash 等）
- `contracts/`：数据契约校验（cards / asr timestamp）

### 6) 停用/历史（Deprecated）

- `_legacy/`：历史脚本，仅供追溯，不再纳入主流程
- `gatekeeper/`：停用能力，不纳入当前主流程

---

## 推荐命令（sync first）

### 主流程（推荐）

```bash
# sync：默认模式（推荐用于 prompt 调试和模型对比）
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --student Qihang --annotator gemini-3-pro-preview --exec-mode sync
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --student Qihang --annotator qwen3-omni-flash --exec-mode sync

# 仅跑 ASR
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --only qwen_asr

# 干运行
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --dry-run
```

### Batch（后续阶段）

```bash
# 推荐统一使用单一 batch 状态（音频直传）
uv run python scripts/main.py --archive-batch Zoe51530_2025-12-16 --exec-mode batch
```

### 兼容入口

```bash
# 兼容脚本（内部转调 main.py）
uv run python test_qwen_omni.py --archive-batch Zoe51530_2025-12-16 --student Qihang
```

---

## 待清理项（下一轮）

1. 从 `main.py` 删除未使用的 gatekeeper / timestamps 残留逻辑。
2. 评估并下线 `annotators/qwen.py`（文本模式）以完成“统一音频输入”。
3. 按需删除 `_legacy/*.py`，并同步清理 docs 中旧引用。
