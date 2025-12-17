# AUDIO_PIPELINE_PLAN：打通音频→ASR→Gemini→报告的完整流程

## 目标
实现从 `backend_input/` 音频文件经过 `qwen_asr` 转录，结合元数据及题库内容，经 `Gemini_annotation` 生成学生注释，最后输出按班级日期归类的综合报告 JSON。

---

## 1. 数据流分析

```
backend_input/{ClassCode}_{Date}_{QuestionBank}_{Student}.mp3
                              ↓
                        qwen_asr.py
                              ↓
            asr/{Student}.json + asr/{Student}_metadata.json
                              ↓
                    合并数据 + 题库加载 + 上下文打印
                              ↓
                   Gemini_annotation.py
                              ↓
    products/backend_annotation/{ClassCode}_{Date}/
                ├── {Student}.json (学生注释)
                ├── {Student}_llm_prompt_log.txt (完整提示词日志)
                ├── report.json (班级级聚合报告)
                └── ...
```

### 关键点
- **输入来源**：`backend_input/` 目录中按命名规则存储的音频文件
- **ASR输出**：保存至 `asr/` 目录，包含原始转录JSON和元数据JSON
- **合并阶段**：读取 metadata + ASR JSON，提取纯文本 `asr_text`
- **题库加载**：根据 metadata 的 `question_bank` 字段定位题库，加载并打印上下文
- **Gemini处理**：仅传入 `asr_text` 作为核心输入，避免冗余信息
- **最终输出**：按 class_code + date 组织的聚合报告JSON

---

## 2. 需修改的文件和函数

### 2.1 `scripts/qwen_asr.py`
- **检查项**：确保 `asr/{Student}_metadata.json` 完整包含：
  - `class_code`（班级代码）
  - `date`（处理日期）
  - `question_bank`（题库编码，如 R3-14-D4）
  - `student`（学生名字）
  - `audio_file`（原始音频文件名）
  - `processed_at`（处理时间戳）
- **可选增强**：新增生成 `asr/{Student}_payload.json` 文件，包含合并后的数据结构，便于调试

### 2.2 `scripts/Gemini_annotation.py`
**新增函数**：
- `load_asr_with_metadata(student_name: str, asr_dir: str) -> dict`
  - 读取 `{asr_dir}/{student_name}_metadata.json` 和 `{asr_dir}/{student_name}.json`
  - 提取 `asr_text = asr_json['output']['choices'][0]['message']['content'][0]['text']`
  - 返回合并的payload：`{"metadata": {...}, "asr_text": "...", "asr_raw": {...}}`

- `find_questionbank_by_metadata(metadata: dict) -> Path`
  - 使用 metadata 的 `question_bank` 字段定位题库文件
  - 优先级：精确匹配 → 前缀匹配 → fallback

- `print_question_bank_context(qb_path: Path, max_chars: int = 500)`
  - 加载题库JSON，打印文件名、条目数、字符长度
  - 打印前 N 字符的题库内容片段，帮助理解上下文

**修改现有函数**：
- `process_student_annotations()`：支持 `--source asr` 分支，从合并payload读取数据
- `extract_text_from_asr_json()`：保留但在新模式中被 `load_asr_with_metadata()` 取代
- `create_batch_report()`：使用 metadata 中的 class_code/date 作为包信息

**新增CLI参数**（保持向后兼容）：
```python
parser.add_argument('--source', choices=['archive', 'asr'], default='archive',
                    help='数据来源：archive=旧模式，asr=backend模式')
parser.add_argument('--asr-dir', type=str, default='asr',
                    help='ASR输出目录（仅当 --source asr 时）')
parser.add_argument('--class', type=str, dest='class_code',
                    help='班级代码（仅当 --source asr 时）')
parser.add_argument('--date', type=str,
                    help='日期（仅当 --source asr 时）')
parser.add_argument('--student', type=str,
                    help='学生名字（仅当 --source asr 时）')
parser.add_argument('--question-bank', type=str,
                    help='题库编码过滤（仅当 --source asr 时）')
parser.add_argument('--output-dir', type=str, default='products/backend_annotation',
                    help='输出目录根路径')
parser.add_argument('--dry-run', action='store_true',
                    help='仅输出计划，不执行实际处理')
```

### 2.3 `prompts/prompt_loader.py`
**修改 `PromptContextBuilder`**：
- 扩展 `build()` 方法接收新参数：
  ```python
  @staticmethod
  def build(question_bank_json: str,
            student_asr_text: str,
            dataset_name: str,
            student_name: str,
            metadata: dict = None,
            class_code: str = None,
            date: str = None,
            question_bank_code: str = None) -> dict:
  ```
- 在上下文中添加元数据信息，便于Gemini理解学生身份和班级信息

### 2.4 （可选）新增脚本 `scripts/backend_pipeline.py`
一键执行端到端流程：
```bash
python3 scripts/backend_pipeline.py --class Abby61000 --date 2025-10-30 \
    --question-bank R1-27-D2 --workers 5 --verbose
```
功能：
1. 扫描 `backend_input/` 查找匹配条件的音频文件
2. 调用 `qwen_asr.py` 转录
3. 调用 `Gemini_annotation.py --source asr` 处理
4. 汇总报告到指定输出目录

---

## 3. 具体实现步骤

### 3.1 数据预处理阶段
```python
# 新函数：扫描asr目录，按class/date/question_bank分组
def discover_asr_data(asr_dir: str, class_filter=None, date_filter=None) -> dict:
    """
    返回结构：
    {
        "class_code_date": [
            {
                "student": "Benjamin",
                "metadata_path": "asr/Benjamin_metadata.json",
                "asr_path": "asr/Benjamin.json",
                "metadata": {...}
            },
            ...
        ]
    }
    """
```

### 3.2 合并数据阶段
```python
def load_asr_with_metadata(student_name: str, asr_dir: str) -> dict:
    """
    合并metadata和ASR文件
    返回 {
        "metadata": {...class, date, question_bank, student...},
        "asr_text": "simple形容词。简单的。...",
        "asr_raw": {...完整ASR JSON响应...}
    }
    """
```

### 3.3 题库加载与日志阶段
```python
def process_student_annotations(class_code: str, date: str, student_name: str,
                               asr_dir: str, output_dir: str, verbose=False):
    # 1. 加载合并数据
    payload = load_asr_with_metadata(student_name, asr_dir)

    # 2. 定位题库文件
    question_bank_path = find_questionbank_by_metadata(payload['metadata'])

    # 3. 打印题库上下文
    if verbose:
        print_question_bank_context(question_bank_path)

    # 4. 加载题库内容
    question_bank = load_file_content(str(question_bank_path))

    # 5. 构建Gemini输入（仅传asr_text）
    prompt_context = PromptContextBuilder.build(
        question_bank_json=question_bank,
        student_asr_text=payload['asr_text'],
        dataset_name=f"{class_code}_{date}",
        student_name=student_name,
        metadata=payload['metadata'],
        class_code=class_code,
        date=date,
        question_bank_code=payload['metadata']['question_bank']
    )

    # 6. 调用Gemini API
    result = call_gemini_api(...)

    # 7. 保存结果到output_dir
    ...
```

### 3.4 输出阶段
**目录结构**：
```
products/backend_annotation/
└── Abby61000_2025-10-30/
    ├── Benjamin/
    │   ├── 4_llm_annotation.json
    │   └── 4_llm_prompt_log.txt
    ├── Dana/
    │   ├── 4_llm_annotation.json
    │   └── 4_llm_prompt_log.txt
    └── report.json (班级级汇总)
```

**report.json 格式**：
```json
{
  "package_info": {
    "package_id": "Abby61000_2025-10-30",
    "class_label": "Abby61000",
    "date": "2025-10-30",
    "question_bank": "R1-27-D2",
    "processing_timestamp": "2025-12-04T12:34:56.789Z"
  },
  "student_reports": [
    {
      "student_name": "Benjamin",
      "final_grade_suggestion": "A",
      "mistake_count": {...},
      "annotations": [...]
    },
    ...
  ]
}
```

---

## 4. 新的命令行使用示例

### 4.1 转录阶段（qwen_asr）
```bash
# 转录所有backend_input文件
python3 scripts/qwen_asr.py --all

# 转录特定班级特定日期的文件
python3 scripts/qwen_asr.py --class Abby61000 --date 2025-10-30

# 转录特定班级特定题库的文件
python3 scripts/qwen_asr.py --class Abby61000 --question-bank R1-27-D2
```

### 4.2 标注阶段（Gemini）
```bash
# 处理特定班级日期的所有学生（新asr模式）
python3 scripts/Gemini_annotation.py \
  --source asr \
  --class Abby61000 \
  --date 2025-10-30 \
  --workers 5 \
  --verbose \
  --output-dir products/backend_annotation

# 处理单个学生
python3 scripts/Gemini_annotation.py \
  --source asr \
  --class Abby61000 \
  --date 2025-10-30 \
  --student Benjamin \
  --verbose

# 按题库过滤处理
python3 scripts/Gemini_annotation.py \
  --source asr \
  --class Abby61000 \
  --date 2025-10-30 \
  --question-bank R1-27-D2 \
  --output-dir products/backend_annotation

# 干跑（仅输出计划，不执行）
python3 scripts/Gemini_annotation.py \
  --source asr \
  --class Abby61000 \
  --date 2025-10-30 \
  --dry-run
```

### 4.3 完整端到端流程（可选orchestrator）
```bash
# 一键执行：转录 + 标注 + 汇总
python3 scripts/backend_pipeline.py \
  --class Abby61000 \
  --date 2025-10-30 \
  --question-bank R1-27-D2 \
  --workers 5 \
  --verbose
```

### 4.4 向后兼容（旧archive模式）
```bash
# 仍然支持旧的数据集处理
python3 scripts/Gemini_annotation.py \
  --source archive \
  --dataset Zoe51530-9.8 \
  --student Oscar
```

---

## 5. 验证清单

- [ ] qwen_asr 输出的 metadata 包含所有必要字段
- [ ] asr/{StudentName}.json 的 asr_text 提取正确
- [ ] find_questionbank_by_metadata 能正确定位题库
- [ ] 题库上下文打印显示正确
- [ ] Gemini 仅接收 asr_text 作为输入
- [ ] 4_llm_annotation.json 生成正确
- [ ] 4_llm_prompt_log.txt 包含完整的系统指令和用户提示词
- [ ] report.json 按班级日期正确聚合
- [ ] 新CLI参数正确解析
- [ ] 向后兼容性：旧archive模式仍可用
- [ ] 完整端到端测试：backend_input音频 → report.json

---

## 6. 实现优先级

| 步骤 | 优先级 | 描述 |
|------|--------|------|
| 1 | 🔴 高 | 修改Gemini_annotation支持--source asr模式 |
| 2 | 🔴 高 | 实现load_asr_with_metadata合并函数 |
| 3 | 🔴 高 | 实现find_questionbank_by_metadata题库定位 |
| 4 | 🟠 中 | 添加题库上下文打印功能 |
| 5 | 🟠 中 | 扩展CLI参数和帮助文档 |
| 6 | 🟡 低 | 开发backend_pipeline.py流水线脚本 |
| 7 | 🟡 低 | 生成asr_payload.json调试文件 |

---

## 7. 关键改进点

✅ **清晰的数据流**：backend_input → asr合并 → 题库加载 → Gemini → report

✅ **精简的Gemini输入**：仅传asr_text，减少token消耗

✅ **可见的中间过程**：打印加载的题库上下文，帮助调试

✅ **按班级日期组织**：最终报告易于检索和聚合

✅ **向后兼容**：保持旧archive模式可用

✅ **灵活的CLI**：支持各种过滤和定制选项

---

**创建日期**：2025-12-04
**制定者**：Codex (gpt-5.1-codex-max)
**状态**：待实现
