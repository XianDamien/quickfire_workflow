# Gemini Batch 模式调研与落地计划（仅计划，暂不执行）

## 背景与目标

当前标注阶段使用同步 Gemini 调用（`client.models.generate_content`），在“整班/大批量”场景下存在吞吐与成本压力。目标是在**批量处理**时切换到 Gemini **Batch API**（异步、可延迟取回），同时保留**单个学生**的同步模式，便于开发期快速调试与小规模运行。

本计划仅描述调研结论与实施路线；后续执行前再进入实现阶段。

## 约束与决策（已确认）

1. **可接受两阶段流程**：先提交 batch（上传/创建 job），再在稍后取回并回填结果。
2. **批量默认 batch 模式**，但由于仍处开发阶段：通过 CLI 提供一个“特殊命令”显式启动 batch；单学生仍可走同步模式。
3. 依赖补齐：在 `pyproject.toml` 增加 `google-genai` 依赖（实现阶段会确认版本与方法签名）。
4. **回填自动完成**，并**记录时间**（每个学生 run 的 started/finished/duration）。

## 当前实现盘点（关键调用点）

- 同步 Gemini 调用封装：`scripts/Gemini_annotation.py` 的 `call_gemini_api()` 内调用 `client.models.generate_content(...)` 并含重试逻辑。
- 编排入口：`scripts/main.py` 的 `run_annotation()` 目前按学生调用 `Gemini_annotation.py --student ...` 子进程执行。
- 产物/契约参考：`docs/pipeline_artifact_contracts.md` 描述了 `run_manifest.json`（含 timing 字段）以及 `annotations[*].card_timestamp` 严格校验等要求。

## Batch API 关键能力（调研结论）

基于 `docs/batch_api.md`：

- Batch API 适合大规模、非实时任务，SLO 目标 24 小时，通常更快。
- 两种提交方式：
  - inline：总请求体 < 20MB，适合小批量。
  - input file：上传 JSONL（单文件最大 2GB），适合大批量（推荐）。
- 作业生命周期：需要轮询状态（pending/running/succeeded/failed/cancelled/expired）。
- 取回结果：成功后下载结果文件（JSONL），逐行解析；每行可能是 response 或 error。

## 中转站兼容性现状与选择

现有中转站仅对 `:generateContent` 返回正常响应，但 `:batchGenerateContent` 路由返回 404，说明当前中转站**未实现 Gemini Developer Batch API**。同时 Batch API 还依赖文件上传/下载端点，因此无法“只补一条路由”解决。

**解决方案（二选一）**：

1. **中转站补齐兼容层**：完整实现并代理 Gemini Developer Batch API 相关端点与鉴权映射，至少包含：
   - `POST /v1beta/models/{model}:batchGenerateContent`
   - `GET /v1beta/{batches/...}`
   - `POST /upload/v1beta/files`（resumable 上传）
   - `GET /download/v1beta/{file}:download`
   - （可选）`POST /v1beta/{batches/...}:cancel`、`DELETE /v1beta/{batches/...}`
2. **直接调用官方接口**：绕过中转站，使用官方 SDK 或 REST 调用 `generativelanguage.googleapis.com` 完成 Batch API；同步调用可继续保留走中转站。

## 建议方案概述

### 总体策略

- **批量（整班/多学生）**：使用 **Batch API + JSONL 输入文件**。
- **单学生**：保留现有同步调用链路，便于快速反馈与排错。
- **开发期安全阀**：batch 模式通过一个新增 CLI 命令显式触发；不替换现有默认流程，避免破坏现有使用方式。

### 为什么优先选 JSONL 输入文件

- 每个学生的 prompt 可能包含：题库 + ASR 文本 + 时间戳文本 + 模板渲染，长度不稳定。
- inline 方式受 20MB 总体限制，容易踩阈值；JSONL 文件可到 2GB，更符合“整班/大批量”形态。

## CLI 设计（建议）

新增一个独立脚本入口（建议：`scripts/gemini_batch.py`），避免与现有 `scripts/main.py` 的同步链路耦合过深。

### 命令 1：submit（提交 batch）

建议参数：

- `--archive-batch <name>`：必填
- `--students <name1,name2,...>`：可选；缺省表示扫描 batch 下所有学生目录
- `--annotator <model>`：默认 `gemini-2.5-pro`
- `--display-name <str>`：可选（便于控制台/日志识别）
- `--out <path>`：可选；将本次 batch 的 manifest（job_name、run_id、input 文件信息等）落盘

submit 阶段输出：

- 创建 JSONL 输入文件（本地）
- 上传至 File API（得到 `files/...`）
- 创建 batch job（得到 `batches/...`）
- 写 batch manifest（强烈建议落盘，便于断点续跑）
- 为每个学生创建/预写 `run_manifest.json`（状态：pending；写入 started_at、batch job_name 等）

### 命令 2：fetch（取回并回填）

建议参数：

- `--job <batches/...>` 或 `--manifest <path>`：二选一
- `--poll-interval <sec>`：默认 30 秒
- `--timeout <sec>`：可选；防止一直等待
- `--retry-failed`：可选；自动收集失败项并生成一个“重试 batch”（仅生成 input，不一定自动提交）

fetch 阶段行为：

- 轮询 job 状态至 completed state
- 成功后下载结果文件（JSONL）
- 逐行解析并按 key 回填到每个学生 run 目录
- 更新每个学生 `run_manifest.json`：
  - `status=success|error`
  - `timing.finished_at`
  - `timing.duration_ms`
  - 记录 `batch.fetched_at`、`result_file_name`
  - 失败时写入 `errors[]`

## key 设计与结果映射

Batch JSONL 每行建议结构：

- `key`：用于回填定位（强烈建议可逆映射回学生与 run）
- `request`：一个合法的 `GenerateContentRequest`

建议 `key` 规范：

`{archive_batch}:{student_name}:{run_id}`

其中 `run_id` 建议与现有 run 目录命名一致（时间戳 + git commit），确保“同一批次”可复现、可重试、可回填。

## 产物回填（与现有目录结构对齐）

目标：回填后依旧满足当前工作流的产物结构与契约（尤其是 `card_timestamp` 严格校验）。

建议回填目录：

`archive/{archive_batch}/{student}/runs/{annotator_name}/{run_id}/`

写入内容（最小集合）：

- `cards.json`（或沿用现有 `4_llm_annotation.json` 再迁移为 cards.json；实现阶段确定一种即可）
- `prompt_log.txt`（可选；若 batch 不便逐条保存完整 prompt，可先只存 prompt 元信息/哈希）
- `run_manifest.json`（必须；见时间记录）

## 时间记录（你提出的“并记录下时间”）

遵循 `docs/pipeline_artifact_contracts.md` 的 `run_manifest.json.timing` 结构：

- `started_at`：在 submit 阶段写入（每个学生一个）
- `finished_at`：在 fetch 阶段写入（按该学生 response 落盘完成时刻）
- `duration_ms`：按上述两者计算（同一时钟源）

同时建议额外记录 batch 维度时间（便于排障与成本核算）：

- `batch.submitted_at`
- `batch.fetched_at`
- `batch.job_name`
- `batch.result_file_name`

## 错误处理与重试策略（建议）

- 逐行错误隔离：单条失败不影响整批回填；失败行写入 `run_manifest.json.errors[]`。
- 重试建议：
  - 对失败行生成“失败项重试 JSONL”，减少重复成本。
  - 对可判定为临时错误（429/5xx/超时）自动纳入重试；对内容安全/格式错误等不可重试错误仅记录。
- 过期处理：`JOB_STATE_EXPIRED` 时输出明确提示，并建议拆分更小批次重试。

## 分批与容量规划（建议）

按以下任一指标分片（实现阶段二选一或组合）：

- JSONL 文件字节数（接近 2GB 前切分）
- 学生数量（例如每 100/200 人一批）
- 预估 token/字符数（更精细但实现复杂）

## 与 OpenSpec 的关系（流程提示）

该变更属于“新增能力/新增运行模式”，建议在真正开始实现前按 OpenSpec 流程创建 change proposal，并在评审通过后再编码落地。

## 验收标准（建议）

1. batch submit 输出 job name 与本地 manifest，可断点续跑。
2. batch fetch 后每个学生 run 目录自动生成目标产物，并且 `run_manifest.json` 含 timing 三字段。
3. 保留单学生同步模式不受影响。
4. 对失败项有可追溯 key、错误信息与可选重试输入文件。

## 下一步（执行前需要你再确认）

1. 新增的“特殊命令”希望挂在现有 `scripts/main.py` 下（如 `--stage batch-cards`），还是独立脚本（如 `scripts/gemini_batch.py`）？
2. 回填产物以 `cards.json` 为准，还是继续以 `4_llm_annotation.json` 为主并在下游迁移？
3. prompt log：是否必须逐学生完整保存（可能很大），还是只保存 prompt 元信息 + sha256？
