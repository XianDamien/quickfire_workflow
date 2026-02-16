# Sync/Batch 现状审查（2026-02-12）

## 审查结论

- 截至当前工作区状态，整体是“过渡完成一半”：主入口已统一，但旧路径与文档仍明显残留。
- `if batch_mode == "asr"` 不在 `scripts/main.py`，当前在服务端分流里：`scripts/batch_server.py:129`。

## 按 Phase 对照

### Phase 1（主入口）

- 基本完成。DAG 入口已是 `scripts/main.py:44`；兼容壳仍保留 `test_qwen_omni.py:20`、`test_qwen_omni.py:42`。

### Phase 2（sync/batch 分层）

- 部分完成。`--exec-mode` 已有 `sync/batch`：`scripts/main.py:617`；batch 走 `gemini_batch_audio`：`scripts/main.py:775`。
- 但 batch server 仍保留 `asr/audio` 双模：`scripts/batch_server.py:40`、`scripts/batch_server.py:129`。

### Phase 3（Qwen 统一 qwen_omni）

- 未完成。`qwen_omni` 已接入：`scripts/annotators/__init__.py:115`。
- 但文本 Qwen 仍在主注册路径：`scripts/annotators/__init__.py:120`、`scripts/annotators/config.py:59`、`scripts/annotators/__init__.py:150`。

### Phase 4（清理 legacy/gatekeeper）

- 未完成。`scripts/_legacy/*` 仍在（且标记 Archived）：`scripts/_legacy/README.md:3`。
- `main.py` 仍有 gatekeeper/timestamps 残留函数与分支：`scripts/main.py:204`、`scripts/main.py:302`、`scripts/main.py:408`、`scripts/main.py:415`。

### Phase 5（文档对齐）

- 部分完成。`README.md` 与 `scripts/README.md` 已无旧脚本名。
- 但 `docs/` 仍有多个文件引用 `qwen_asr.py/Gemini_annotation.py`，且 `docs/backend-integration.md` 仍写 `gatekeeper` 流程与 `qwen-max`：`docs/backend-integration.md:327`、`docs/backend-integration.md:321`、`docs/backend-integration.md:345`。

## 验收项状态（第5节）

- `sync + qwen_omni` 路径可达（dry-run 通过）。
- `batch + qwen_omni` 目前没有显式拦截/报错；主流程会把 `--annotator qwen3-omni-flash` 直接传给 Gemini batch 脚本，存在运行时失败风险：`scripts/main.py:780` + `scripts/gemini_batch_audio.py:891`。
- `cost/latency/accuracy`：latency/accuracy（成绩分布、错误数）有；cost 仅有 token 数据，未统一成本字段。

## 口径修正（与你最新确认一致）

- 对外执行模式应只有两种：`sync` 和 `batch`。
- `asr/audio` 属于遗留内部字段/脚本分支，不应再作为对外执行模式语义。

