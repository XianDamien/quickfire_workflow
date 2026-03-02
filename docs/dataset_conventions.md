# 数据集与目录规范（用于批量模型测试 / Prompt 微调）

目标：
- **一键批处理**：音频 → Qwen ASR → FunASR 时间戳 ASR → Gemini 标注 → 聚合报告
- **中间件可见**：关键中间产物全部落盘、可回看
- **Prompt 微调友好**：只改 prompt 时尽量不重跑 ASR，只新增本次 run 输出

---

## 1) 题库索引（不复制文件）

题库统一从项目根目录的 `questionbank/` 读取：
- 题库码：`progress`（例：`R1-65-D5`）
- 题库路径规则：`questionbank/{progress}.json`

数据集只需要记录 `progress`（以及可选的显式路径），运行时按规则加载题库。

---

## 2) 输入目录规范（backend_input）

### 2.1 音频文件命名（强约束）

```
{class_code}_{date}_{progress}_{student}.mp3
```

- `class_code`：班级代码（例：`Zoe41900`）
- `date`：日期（固定 `YYYY-MM-DD`）
- `progress`：题库码/进度（例：`R1-65-D5`）
- `student`：学生名（建议只用字母数字、空格、连字符；保持一致）

允许同一学生同一批次多段音频：

```
{class_code}_{date}_{progress}_{student}_{part}.mp3
```

其中 `part` 为整数（例：`_1`、`_2`）。

### 2.2 输入索引（统一写入 metadata，不使用 manifest）

由于 FunASR 依赖阿里云 OSS URL，建议在 `backend_input/metadata.json` 里统一维护每个音频的元信息（本地路径、OSS URL、题库码等），避免脚本散落地推断与拼接。

> 约定：`backend_input/metadata.json` 作为 `backend_input/` 的权威索引；后续 ingest 阶段从这里生成/更新各数据集的 metadata。

建议结构（示例）：

```json
{
  "schema_version": 1,
  "items": [
    {
      "file_id": "Zoe41900_2025-09-08_R1-65-D5_Oscar",
      "class_code": "Zoe41900",
      "date": "2025-09-08",
      "progress": "R1-65-D5",
      "student": "Oscar",
      "local_path": "backend_input/Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3",
      "oss_url": "https://.../Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3"
    }
  ]
}
```

---

## 3) 数据集目录规范（archive：班级 + 日期两层）

数据集根目录（使用下划线）：

```
archive/{class_code}_{date}/
```

建议结构：

```
archive/{class_code}_{date}/
  metadata.json
  {student}/
    1_input_audio.mp3
    2_qwen_asr.json
    3_asr_timestamp.json
    runs/
      {run_id}/
        4_llm_annotation.json
        4_llm_prompt_log.txt
        run_metadata.json
  reports/
    {run_id}/
      batch_annotation_report.json
      errors.jsonl
```

### 3.1 数据集 metadata.json（单文件承载全部元信息；不使用 manifest）

约定：`archive/{class_code}_{date}/metadata.json` 是该批次的**唯一权威元信息文件**，包含：
- 批次信息（班级、日期、progress、题库路径）
- 批次内所有样本（学生、音频本地路径、OSS URL、可选分段信息）

建议结构（示例）：

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
      "oss_url": "https://.../Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3"
    }
  ],
  "created_at": "2025-12-18T00:00:00+08:00",
  "updated_at": "2025-12-18T00:00:00+08:00",
  "notes": ""
}
```

**约束：**
- 同一个 `archive/{class}_{date}` 下 `progress` 必须唯一（你已确认）。
- `items[*].student` 建议与学生目录名完全一致，避免聚合错位。

---

## 4) 中间件与输出（必须可见）

### 4.1 1_input_audio.mp3
- 原始音频（本地），不可覆盖；若替换请新增音频并更新 metadata 中对应条目。

### 4.2 2_qwen_asr.json（Qwen 转写）
- 保存 **Qwen API 原始响应 JSON**（排错最方便）。
- 下游从中提取纯文本作为 `student_asr_text`。

### 4.3 3_asr_timestamp.json（FunASR 带时间戳转写）
- JSON 结构建议对齐 `asr_timestamp/Zoe41900_2025-09-08_R1-65-D5_Oscar.json`：
  - `file_url`
  - `transcripts[].transcript`
  - `transcripts[].sentences[].begin_time/end_time/text`
- 下游在进入 prompt 前转换为 `student_asr_with_timestamp` 文本块（例如将 `begin_time(ms)` 转 `MM:SS` 并逐行拼接）。

### 4.4 runs/{run_id}/4_llm_annotation.json（Gemini 输出）
- `run_id` 用于区分不同 prompt/模型参数，避免覆盖（适合“只微调 prompt”的测试）。
- 输出结构必须严格符合 `prompts/annotation/user.md` 的 JSON 示例。

### 4.5 runs/{run_id}/run_metadata.json（建议强制）
建议至少记录：
- `run_id`
- `git_commit`
- `model`
- `prompt_path`（如 `prompts/annotation/user.md`）
- `prompt_hash`（对渲染后的完整 prompt 文本做 hash）
- `created_at`

---

## 5) 一键流程（阶段化，可跳过/可复跑）

建议拆成 4 阶段，每阶段都“存在则跳过”，支持 `--force-*` 重跑：

1. **ingest**
   - 从 `backend_input/metadata.json` 按 `{class_code}_{date}` 分组
   - 生成/更新 `archive/{class}_{date}/metadata.json`
   - 将音频复制/链接到 `archive/{class}_{date}/{student}/1_input_audio.mp3`
2. **qwen_asr**
   - 生成 `2_qwen_asr.json`
3. **funasr_timestamp**
   - 用 `archive/.../metadata.json` 中的 `oss_url` 生成 `3_asr_timestamp.json`
4. **gemini_annotate**
   - 题库：按 `progress` → `questionbank/{progress}.json`
   - 三输入：题库 + Qwen 纯文本 + 时间戳 ASR 文本块
   - 输出：`runs/{run_id}/4_llm_annotation.json` + 聚合 `reports/{run_id}/batch_annotation_report.json`

