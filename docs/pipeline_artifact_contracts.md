# 流程产物契约（Artifact Contracts / Schema）

本文件用于把现有流程的每一步“标准化成可替换的节点（node）”，并为每个落盘产物定义**明确契约（schema）**，用于：
- 可靠编排（缺依赖就失败，不做 fallback）
- 可观测（字段齐全、错误清晰）
- 可复现（run 级别的 manifest + 输入/代码/Prompt/模型版本可追溯）
- A/B 测试（同一上游产物下，仅替换标注模型/Prompt/参数）

数据集目录与命名的基础约定请先读：`docs/dataset_conventions.md`（本文件在其之上补充“字段级契约”）。

---

## 0) 术语与约定

### 0.1 标识符
- `dataset_id`: `{class_code}_{date}`（例：`Zoe41900_2025-09-08`）
- `student`: 学生目录名（例：`Oscar`）
- `file_id`: `{class_code}_{date}_{progress}_{student}`（例：`Zoe41900_2025-09-08_R1-65-D5_Oscar`）
- `run_id`: 一次下游标注运行的唯一 ID（例：`20251218_120059_a7214dd`）
- `annotator_name`: 标注器/下游节点名（**直接使用代码里调用的模型名称**，厂商+版本）（例：`gemini-2.5-pro`）

### 0.2 Schema 版本
- 每个 JSON 产物（除“原始 API 原样响应”外）都 SHOULD 包含 `schema_version`（整数递增）。
- 对于“原始响应落盘”（例如 Qwen 原始 JSON），允许没有 `schema_version`，但必须在 run manifest 里记录其 hash 与来源。

### 0.3 时间戳单位与格式
- FunASR `begin_time/end_time`：**毫秒（ms）**（best practice + 代码按 ms 处理）。
- `card_timestamp`：字符串 `MM:SS`（本项目音频通常为几分钟，**不需要 `HH:MM:SS`**）。

---

## 1) 目录分层（稳定产物 vs 实验产物）

参考 `docs/dataset_conventions.md`，本文件建议把**稳定上游产物**与**可多次实验的下游产物**分层，避免覆盖：

### 1.1 稳定上游产物（建议保持在 archive 下）
```
archive/{dataset_id}/
  metadata.json
archive/{dataset_id}/{student}/
  1_input_audio.mp3
  2_qwen_asr.json
  3_asr_timestamp.json
```

### 1.2 下游实验产物（建议按 annotator_name + run_id 分层）
```
archive/{dataset_id}/{student}/runs/{annotator_name}/{run_id}/
  cards.json                # 或保持兼容：4_llm_annotation.json
  prompt_log.txt            # 完整渲染后的 prompt
  run_manifest.json         # 复现信息（强制）
```

> 兼容现状：当前代码为 `archive/{dataset_id}/{student}/runs/{run_id}/...`；后续可迁移为多层目录，但第一阶段可以先保留旧路径并新增新路径。

---

## 2) Node（可替换节点）定义（v0）

每个 node 必须声明：
- `node_id`（稳定字符串）
- 输入依赖（存在性 + schema 校验）
- 输出产物（文件路径 + schema_version）
- 失败策略（缺依赖/字段缺失：**直接失败**，错误可读）

### 2.1 Node 列表（与现有脚本对齐）
1. `ingest_audio`
2. `qwen_asr_text`
3. `funasr_timestamp`
4. `annotate_cards`（Gemini/LLM）

---

## 3) 产物契约（Schema）

### 3.0 `archive/{dataset_id}/metadata.json`（批次权威索引；上游稳定产物）
- **类型**：JSON
- **契约目标**：承载“从文件名/输入索引提取的音频元信息”，作为 archive 批次内样本的权威索引（班级+日期聚合）。
- **路径示例**：`archive/Zoe70930_2025-11-14/metadata.json`

建议结构（对齐 `docs/dataset_conventions.md`，并作为契约固定下来）：
```json
{
  "schema_version": 1,
  "dataset_id": "Zoe70930_2025-11-14",
  "class_code": "Zoe70930",
  "date": "2025-11-14",
  "progress": "R1-46-D6",
  "question_bank_path": "questionbank/R1-46-D6.json",
  "items": [
    {
      "file_id": "Zoe70930_2025-11-14_R1-46-D6_Yoyo",
      "student": "Yoyo",
      "local_path": "archive/Zoe70930_2025-11-14/Yoyo/1_input_audio.mp3",
      "oss_url": "https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/Zoe70930_2025-11-14_R1-46-D6_Yoyo.mp3"
    }
  ],
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>",
  "notes": ""
}
```

- **强约束**：
  - `dataset_id/class_code/date/progress/question_bank_path` 必须存在且一致
  - `items[*].file_id/student/local_path/oss_url` 必须存在
  - 同一 `dataset_id` 下 `progress` 必须唯一（你已确认）

---

### 3.1 `1_input_audio.mp3`（原始音频）
- **类型**：二进制音频
- **契约重点**：
  - 文件必须存在
  - hash（sha256）必须被记录在 `run_manifest.json`（或 `archive/{dataset_id}/metadata.json`）中
- **备注**：
  - 不强制为音频增加 sidecar；音频的可复现关键索引信息优先进入 `archive/{dataset_id}/metadata.json` + `run_manifest.json`。

---

### 3.2 `2_qwen_asr.json`（Qwen ASR 原始响应落盘；以当前 qwen_asr 为准）
- **类型**：JSON（原样响应）
- **来源**：`scripts/qwen_asr.py`
- **契约重点（下游读取路径）**：
  - 下游提取 ASR 文本的默认路径为：
    - `output.choices[0].message.content[0].text`（字符串）
  - 若该字段为空或不存在：应视为 **上游产物不合格**（node 失败）
- **允许**：附加字段（例如分段转写合并信息），不影响下游读取
- **建议（后续增强，非第一阶段强制）**：
  - 新增归一化产物 `2_asr_text.json`（见 3.3），把“下游稳定使用的字段”固定化，避免强耦合原始 API 结构变化。

---

### 3.3 `2_asr_text.json`（可选：归一化 ASR 文本契约）
> 第一阶段可不生成；如果要做“可替换 ASR 模型”，强烈建议补上这一层契约。

```json
{
  "schema_version": 1,
  "artifact_type": "asr_text",
  "file_id": "<file_id>",
  "text": "<full_transcript_text>",
  "meta": {
    "produced_by": {
      "node_id": "qwen_asr_text",
      "engine": "qwen",
      "model": "<TODO>",
      "params": {}
    },
    "inputs": [
      { "path": "2_qwen_asr.json", "sha256": "<TODO>" }
    ],
    "created_at": "<ISO8601>",
    "git_commit": "<TODO>"
  }
}
```

---

### 3.4 `3_asr_timestamp.json`（FunASR 时间戳输出；以当前 funasr 为准）
- **类型**：JSON（简化结构）
- **来源**：`scripts/funasr.py`
- **契约（当前代码期望形态）**：
```json
{
  "file_url": "file://... 或 https://...",
  "transcripts": [
    {
      "channel_id": 0,
      "transcript": "<全文文本>",
      "sentences": [
        {
          "begin_time": 1234,
          "end_time": 2345,
          "text": "..."
        }
      ]
    }
  ]
}
```

- **强约束（annotate_cards 的硬依赖）**：
  - 文件必须存在
  - `transcripts[0].sentences` 必须存在且非空
  - `begin_time/end_time/text` 必须齐全，且 `begin_time/end_time` 为整数（ms）
  - `begin_time <= end_time`

> 关键要求：**LLM 标注 node 必须强依赖该文件**。缺失就直接失败并给出清晰错误；禁止把“(无时间戳数据)”喂给模型导致静默产出 `null`。

---

### 3.5 `cards.json`（下游标注产物；现状为 `4_llm_annotation.json`）
- **类型**：JSON（结构化标注结果）
- **来源**：`scripts/Gemini_annotation.py`（或未来其它 annotator）
- **契约目标**：把“标注结果”与“复现信息”解耦：结果写 `cards.json`，复现写 `run_manifest.json`。

建议 v1 结构（字段名尽量兼容现有输出）：
```json
{
  "schema_version": 1,
  "artifact_type": "cards",
  "file_id": "<file_id>",
  "student_name": "<student>",
  "final_grade_suggestion": "A|B|C",
  "mistake_count": { "errors": 0 },
  "annotations": [
    {
      "card_index": 1,
      "card_timestamp": "00:17",
      "question": "...",
      "expected_answer": "...",
      "related_student_utterance": {
        "detected_text": "..." ,
        "issue_type": "NO_ANSWER|MEANING_ERROR|null"
      }
    }
  ],
  "meta": {
    "run_id": "<run_id>",
    "annotator_name": "<annotator_name>",
    "inputs": [
      { "path": "2_qwen_asr.json", "sha256": "<TODO>" },
      { "path": "3_asr_timestamp.json", "sha256": "<TODO>" },
      { "path": "questionbank/<progress>.json", "sha256": "<TODO>" }
    ]
  }
}
```

- **强约束**：
  - `annotations[*].card_timestamp` **不允许为 `null`**（开发阶段严格，无法估算就直接失败）
  - `meta.annotator_name` 必须与代码实际调用的 `model` 字符串一致（例如 `gemini-2.5-pro`）

---

## 4) run_manifest.json（运行记录与可复现性）

每次下游标注运行必须生成一个 `run_manifest.json`（或在当前文件名 `run_metadata.json` 基础上扩展并改名）。

**最低要求字段**（v1 草案，留空可填）：
```json
{
  "schema_version": 1,
  "run_id": "<run_id>",
  "annotator_name": "<annotator_name>",
  "status": "success|error",
  "timing": {
    "started_at": "<ISO8601>",
    "finished_at": "<ISO8601>",
    "duration_ms": 0
  },
  "code": {
    "git_commit": "<commit>",
    "dirty": false
  },
  "models": {
    "qwen_asr": { "model": "<TODO>", "params": {} },
    "funasr": { "model": "<TODO>", "params": {} },
    "annotator": { "provider": "gemini", "model": "<TODO>", "params": { "temperature": 0.2 } }
  },
  "prompt": {
    "dir": "prompts/annotation",
    "system_path": "prompts/annotation/system.md",
    "user_path": "prompts/annotation/user.md",
    "rendered_prompt_sha256": "<TODO>",
    "prompt_metadata": {}
  },
  "inputs": {
    "audio": { "path": "1_input_audio.mp3", "sha256": "<TODO>" },
    "asr_raw": { "path": "2_qwen_asr.json", "sha256": "<TODO>" },
    "asr_timestamp": { "path": "3_asr_timestamp.json", "sha256": "<TODO>" },
    "question_bank": { "path": "questionbank/<progress>.json", "sha256": "<TODO>" }
  },
  "cache": {
    "hit": false,
    "reason": ""
  },
  "errors": []
}
```

---

## 5) 开发期“无 fallback”规范（强制）

### 5.1 强依赖规则（必须失败）
`annotate_cards` node：
- 缺 `3_asr_timestamp.json` → 直接失败（错误信息包含：缺哪个文件、建议先跑哪个 node）
- 有文件但 `sentences` 为空/字段缺失 → 直接失败（指出缺失字段路径）
- 禁止向 Prompt 注入“(无时间戳数据)”占位文本

### 5.2 字段存在性校验（必须失败）
- 任何产物缺少“下游依赖字段”都应视为上游失败，不能静默继续。

---

## 6) 需要你确认/补全的关键点（留空）

## 6) 已确认的关键点（决定）

1. `card_timestamp`：只用 `MM:SS`
2. FunASR `begin_time/end_time`：按 **ms** 作为契约标准
3. 若任何题目无法给出 `card_timestamp`：**严格失败**
4. `annotator_name`：直接使用代码里调用的模型名称（厂商+版本），例如 `gemini-2.5-pro`
5. 不需要为音频增加 `1_input_audio.meta.json` sidecar（暂不强制）
