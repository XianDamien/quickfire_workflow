# 后端接口协议文档

**版本**: v2.0
**更新日期**: 2026-01-06

## 概述

Quickfire 英语发音评测系统通过**文件系统接口**与后端对接。后端负责准备输入数据，系统处理后输出结构化评分结果。

```
后端准备数据 → Quickfire 处理 → 后端获取结果
     ↓               ↓                ↓
  音频+题库     ASR → LLM评分      JSON结果
```

---

## 1. 接口模式

### 1.1 输入/输出约定

| 方向 | 格式 | 位置 |
|------|------|------|
| 后端 → 系统 | 音频文件 + JSON | `archive/{batch_id}/` |
| 系统 → 后端 | JSON 评分结果 | `archive/{batch_id}/{student}/runs/*/4_llm_annotation.json` |

### 1.2 批次标识 (batch_id)

格式: `{ClassCode}_{Date}`

示例:
- `Zoe51530_2025-12-16`
- `Niko60900_2025-10-12`

---

## 2. 后端需要提供的数据

### 2.1 目录结构

```
archive/{batch_id}/
├── metadata.json                          # 必须：批次元数据
├── _shared_context/
│   └── {progress_id}.json                 # 必须：题库文件
├── {StudentName1}/
│   └── 1_input_audio.mp3                  # 必须：学生音频
├── {StudentName2}/
│   └── 1_input_audio.mp3
└── ...
```

### 2.2 metadata.json (必须)

```json
{
  "schema_version": 1,
  "dataset_id": "Zoe51530_2025-12-16",
  "class_code": "Zoe51530",
  "date": "2025-12-16",
  "progress": "130-18-EC",
  "question_bank_path": "_shared_context/130-18-EC.json",
  "items": [
    {
      "file_id": "Zoe51530_2025-12-16_130-18-EC_Qihang",
      "student": "Qihang",
      "local_path": "archive/Zoe51530_2025-12-16/Qihang/1_input_audio.mp3",
      "oss_url": "https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/..."
    }
  ],
  "created_at": "2025-12-16T10:00:00Z",
  "updated_at": "2025-12-16T10:00:00Z"
}
```

**字段说明**:

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `schema_version` | int | 是 | 固定为 `1` |
| `dataset_id` | string | 是 | 批次唯一标识，与目录名一致 |
| `class_code` | string | 是 | 班级代码 |
| `date` | string | 是 | 日期 (YYYY-MM-DD) |
| `progress` | string | 是 | 课程进度标识，对应题库文件名 |
| `question_bank_path` | string | 是 | 题库文件相对路径 |
| `items` | array | 是 | 学生列表 |
| `items[].file_id` | string | 是 | 唯一文件标识 |
| `items[].student` | string | 是 | 学生姓名（对应目录名） |
| `items[].local_path` | string | 否 | 本地音频路径 |
| `items[].oss_url` | string | 否 | OSS 音频 URL |

### 2.3 题库文件 (必须)

位置: `archive/{batch_id}/_shared_context/{progress}.json`

```json
[
  {
    "question": "celebrate",
    "answer": "庆祝",
    "hint": ""
  },
  {
    "question": "cent, cent",
    "answer": "一分钱，一美分",
    "hint": ""
  },
  {
    "question": "center",
    "answer": "中心",
    "hint": ""
  }
]
```

**字段说明**:

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `question` | string | 是 | 英文题目（老师会念出） |
| `answer` | string | 是 | 标准答案（中文） |
| `hint` | string | 否 | 提示信息（可为空） |

### 2.4 学生音频 (必须)

位置: `archive/{batch_id}/{student}/1_input_audio.mp3`

**支持格式**: MP3, MP4, WAV, M4A, FLAC, OGG

**音频内容**: 学生听老师念题后的完整回答录音

**时长限制**: 无限制（系统自动分段处理长音频）

---

## 3. 系统输出给后端的数据

### 3.1 核心输出：评分结果

位置: `archive/{batch_id}/{student}/runs/{annotator}/{run_id}/4_llm_annotation.json`

```json
{
  "student_name": "Qihang",
  "final_grade_suggestion": "A",
  "mistake_count": {
    "errors": 0
  },
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
    },
    {
      "card_index": 2,
      "card_timestamp": "00:05",
      "question": "cent",
      "expected_answer": "一分钱，一美分",
      "related_student_utterance": {
        "detected_text": "一分钱，美分",
        "issue_type": null
      }
    },
    {
      "card_index": 3,
      "card_timestamp": "00:10",
      "question": "center",
      "expected_answer": "中心",
      "related_student_utterance": {
        "detected_text": "",
        "issue_type": "NO_ANSWER"
      }
    }
  ],
  "_metadata": {
    "model": "gemini-3-pro-preview",
    "run_id": "20260106_002923_eb28926",
    "git_commit": "eb28926",
    "timestamp": "2026-01-06T09:35:45.691265",
    "source": "batch_api"
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `student_name` | string | 学生姓名 |
| `final_grade_suggestion` | string | 最终成绩: `A` / `B` / `C` |
| `mistake_count.errors` | int | 错误总数 |
| `annotations` | array | 逐题评注列表 |
| `annotations[].card_index` | int | 题目序号 (1-based) |
| `annotations[].card_timestamp` | string | 题目出现时间 (MM:SS) |
| `annotations[].question` | string | 题目内容 |
| `annotations[].expected_answer` | string | 标准答案 |
| `annotations[].related_student_utterance.detected_text` | string | 学生回答 |
| `annotations[].related_student_utterance.issue_type` | string | 错误类型 |
| `_metadata` | object | 处理元数据 |

**错误类型 (issue_type)**:

| 值 | 含义 |
|------|------|
| `null` | 正确 |
| `NO_ANSWER` | 学生未作答 |
| `MEANING_ERROR` | 答案意思错误 |

**评分规则**:

| 成绩 | 条件 |
|------|------|
| A | 错误数 = 0 |
| B | 错误数 = 1-2 |
| C | 错误数 >= 3 |

### 3.2 中间产物（可选获取）

| 文件 | 位置 | 说明 |
|------|------|------|
| ASR 转写 | `{student}/2_qwen_asr.json` | 语音转文本原始结果 |
| 热词日志 | `{student}/2_qwen_asr_hotwords.json` | ASR 使用的热词 |
| 时间戳 | `{student}/3_asr_timestamp.json` | 带时间戳的转写 |
| 提示词日志 | `runs/.../prompt_log.txt` | LLM 输入的完整提示词 |
| 运行元数据 | `runs/.../run_metadata.json` | 运行配置和状态 |

---

## 4. 处理流程

### 4.1 执行命令

```bash
# 处理整个批次
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16

# 处理单个学生
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16 --student Qihang

# 预览（不实际执行）
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16 --dry-run

# 指定评分模型
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16 --annotator qwen-max
```

### 4.2 处理阶段

```
audio → qwen_asr → gatekeeper → cards
  ↓         ↓           ↓          ↓
检查音频   ASR转写    质检门禁    LLM评分
```

| 阶段 | 输出文件 | 说明 |
|------|----------|------|
| `audio` | - | 检查音频文件存在 |
| `qwen_asr` | `2_qwen_asr.json` | Qwen3-ASR 转写 |
| `gatekeeper` | - | ASR 质量检查（可选） |
| `cards` | `4_llm_annotation.json` | LLM 评分注解 |

### 4.3 支持的评分模型

| 模型 | 说明 |
|------|------|
| `gemini-3-pro-preview` | 默认，Google Gemini |
| `gemini-2.5-pro` | Google Gemini |
| `qwen-max` | 阿里云 Qwen |
| `qwen3-max` | 阿里云 Qwen3 |

---

## 5. 集成示例

### 5.1 后端准备数据流程

```python
# 1. 创建批次目录
batch_id = f"{class_code}_{date}"
batch_dir = f"archive/{batch_id}"
os.makedirs(batch_dir, exist_ok=True)
os.makedirs(f"{batch_dir}/_shared_context", exist_ok=True)

# 2. 保存题库
question_bank = [
    {"question": "celebrate", "answer": "庆祝", "hint": ""},
    {"question": "cent", "answer": "一分钱", "hint": ""},
]
with open(f"{batch_dir}/_shared_context/{progress}.json", "w") as f:
    json.dump(question_bank, f, ensure_ascii=False, indent=2)

# 3. 保存学生音频
for student in students:
    student_dir = f"{batch_dir}/{student['name']}"
    os.makedirs(student_dir, exist_ok=True)
    # 下载/复制音频到 {student_dir}/1_input_audio.mp3

# 4. 创建元数据
metadata = {
    "schema_version": 1,
    "dataset_id": batch_id,
    "class_code": class_code,
    "date": date,
    "progress": progress,
    "question_bank_path": f"_shared_context/{progress}.json",
    "items": [
        {
            "file_id": f"{batch_id}_{progress}_{s['name']}",
            "student": s["name"],
            "local_path": f"archive/{batch_id}/{s['name']}/1_input_audio.mp3",
        }
        for s in students
    ],
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
}
with open(f"{batch_dir}/metadata.json", "w") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
```

### 5.2 后端获取结果流程

```python
import json
import glob

def get_batch_results(batch_id: str) -> list:
    """获取批次所有学生的评分结果"""
    results = []

    # 查找所有学生的最新评分结果
    pattern = f"archive/{batch_id}/*/runs/*/*/4_llm_annotation.json"
    for path in glob.glob(pattern):
        with open(path) as f:
            annotation = json.load(f)

        results.append({
            "student": annotation["student_name"],
            "grade": annotation["final_grade_suggestion"],
            "errors": annotation["mistake_count"]["errors"],
            "details": annotation["annotations"],
            "model": annotation["_metadata"]["model"],
            "processed_at": annotation["_metadata"]["timestamp"],
        })

    return results

# 使用示例
results = get_batch_results("Zoe51530_2025-12-16")
for r in results:
    print(f"{r['student']}: {r['grade']} ({r['errors']} errors)")
```

---

## 6. 性能参数

| 指标 | 数值 |
|------|------|
| ASR 处理速度 | ~6-7 分钟/学生 |
| LLM 评分速度 | ~2-3 分钟/学生 |
| 支持音频时长 | 无限制（自动分段） |
| 并行处理 | 支持 |
| 重试次数 | 5 次 |
| 重试间隔 | 5 秒 |

---

## 7. 错误处理

### 7.1 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `metadata.json not found` | 缺少元数据文件 | 创建 metadata.json |
| `question bank not found` | 题库文件路径错误 | 检查 question_bank_path |
| `1_input_audio.mp3 not found` | 音频文件缺失 | 上传学生音频 |
| `API rate limit` | API 请求过快 | 等待重试，系统自动处理 |

### 7.2 重新处理

```bash
# 强制重新处理（覆盖已有结果）
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16 --force

# 只重新运行 ASR
python3 scripts/main.py --archive-batch Zoe51530_2025-12-16 --only qwen_asr --force
```

---

## 8. 联系方式

如有接口问题，请联系开发团队。
