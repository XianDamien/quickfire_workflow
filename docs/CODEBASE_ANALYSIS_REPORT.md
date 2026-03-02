# 代码库功能分析报告

*由 Codex 生成于 2025-12-03*

## Python 脚本一览

### 1. `scripts/qwen_asr.py` - 批量/单文件音频转写

**核心功能**：
- 批量/单文件音频转写
- 音频分段处理（ffmpeg/ffprobe）
- 并行转写与结果合并
- 题库热词注入
- 数据集/学生遍历

**主要函数**：
- `split_audio()` - 长音频分段
- `merge_json_results()` - 合并分段转写结果
- `QwenASRProvider.transcribe_*()` - Qwen ASR 调用
- `process_audio_file()` - ✨ 新增：从文件名解析信息处理单个文件
- `parse_audio_filename()` - ✨ 新增：从文件名解析班级、日期、进度、学生
- `process_student()` - 处理单个学生
- `process_dataset()` - 处理整个数据集
- `process_all_students()` - 批量处理所有数据集

**输入**：
- 标准：`archive/<dataset>/<student>/1_input_audio.*`
- ✨ 新增：`--file` 参数指定 `{班级}_{日期}_{进度}_{学生}.mp3`
- 可选题库热词：
  - `archive/<dataset>/_shared_context/` 内 vocab/json/csv
  - `questionbank/` 下 R*.json/csv

**输出**：
- 转写 JSON：`2_qwen_asr.json`（标准 Qwen message 格式）
- 元数据：`2_qwen_asr_metadata.json`（✨ 新增）
- 长音频自动在临时目录分段并合并

**依赖**：
- `dashscope` (Qwen3-ASR, 多模态对话)
- `ffmpeg/ffprobe` (音频处理)
- `dotenv` (加载 DASHSCOPE_API_KEY)
- `ThreadPoolExecutor` (并发处理)

**CLI 参数**：
- `--dataset` / `--student` - 标准模式（archive 目录结构）
- ✨ `--file` - 新增：单文件模式（文件名解析）
- ✨ `--output` - 新增：指定输出目录（与 --file 配合）
- `--api-key` - 可选指定 API 密钥

---

### 2. `scripts/Gemini_annotation.py` - 学生回答提取与评分

**核心功能**：
- 基于 Gemini 的学生回答提取
- 自动评分（A/B/C级）
- 支持并行处理
- 批量报告生成

**主要函数**：
- `call_gemini_api()` - Gemini API 调用（含重试/截断兜底）
- `process_student_annotations()` - 处理单个学生
- `process_dataset_with_parallel()` - 并行处理整个数据集
- `process_all_students()` - 批量处理所有数据集
- `create_batch_report()` - 生成批量报告

**输入**：
- 题库：
  - 优先级 1：学生目录 `current_qb.json`
  - 优先级 2：`questionbank/` 下 R*.json（优先R3-14-D4, 其次R1-65, 最后任意R*.json）
- ASR 结果：优先级 `2_qwen_asr.json`
- 提示词模板：
  - `prompts/annotation/system.md` (系统指令)
  - `prompts/annotation/user.txt` (Jinja2 模板)
  - `prompts/annotation/metadata.json` (元数据)
- 环境变量：`GEMINI_API_KEY`

**输出**：
- 学生注解：`4_llm_annotation.json`
  ```json
  {
    "final_grade_suggestion": "A",
    "mistake_count": 0,
    "annotations": [...]
  }
  ```
- 提示词日志：`4_llm_prompt_log.txt` (git commit + 元数据 + 渲染提示词)
- 批量报告：`batch_annotation_report.json` (所有学生聚合)

**依赖**：
- `google-genai` (genai.Client, types.GenerateContentConfig)
- `prompts/prompt_loader.py` (Jinja2 渲染)
- `dotenv`
- 并发线程池
- JSON 截断/安全过滤兜底

**CLI 参数**：
- `--dataset` / `--student` - 指定数据集/学生
- `--workers` - 并发线程数
- `--verbose` - 详细输出
- `--force` - 强制重新处理

---

### 3. `prompts/prompt_loader.py` - 提示词加载与渲染

**核心功能**：
- 加载提示词模板
- Jinja2 渲染
- 版本管理（git 追踪）

**主要类**：
- `PromptLoader` - 加载和管理提示词
- `PromptContextBuilder` - 构建模板上下文
- `PromptArtifacts` - 数据容器

**输入**：
- 提示目录：默认 `prompts/annotation/`
- 必需文件：
  - `system.md` - 系统指令
  - `user.txt` - Jinja2 模板（要求上下文键）
  - `metadata.json` - 元数据
- 模板上下文键（必需）：
  - `question_bank_json` - 题库内容
  - `student_asr_text` - 学生转写文本
  - `dataset_name` - 数据集名称
  - `student_name` - 学生名称
- 可选键：`guidance`, `metadata`

**输出**：
- `PromptLoader.system_instruction` - 系统指令字符串
- `PromptLoader.metadata` - 元数据字典
- `render_user_prompt(context)` - 渲染后的用户提示词

**依赖**：
- `jinja2` (模板引擎)
- `json` (元数据解析)

---

## 脚本间数据流转

### ASR 阶段 (qwen_asr.py)
```
输入音频
    ↓
遍历 archive/<dataset>/<student>/
    ↓
选择音频文件：
  1. 1_input_audio.*
  2. <StudentName>.*
  3. 第一个找到的音频
    ↓
查找题库热词（_shared_context 或 questionbank）
    ↓
Qwen3-ASR 转写
    ↓
长音频：分段 → 并行转写 → 合并
    ↓
输出：2_qwen_asr.json + 2_qwen_asr_metadata.json
```

### 注解阶段 (Gemini_annotation.py)
```
读取 2_qwen_asr.json + 题库
    ↓
PromptLoader 渲染提示词：
  - 加载 system.md + user.txt
  - 注入 question_bank_json + student_asr_text
    ↓
Gemini LLM 调用
    ↓
提取学生回答 + 评分
    ↓
输出：4_llm_annotation.json + 4_llm_prompt_log.txt
    ↓
聚合所有学生结果
    ↓
输出：batch_annotation_report.json
```

### 目录约定
```
archive/
├── <dataset>/
│   ├── _shared_context/        # 可选：词汇/题库来源（旧）
│   └── <student>/
│       ├── 1_input_audio.*     # 输入音频
│       ├── 2_qwen_asr.json     # ASR 输出
│       ├── 2_qwen_asr_metadata.json  # 元数据（新）
│       ├── 4_llm_annotation.json     # Gemini 输出
│       └── 4_llm_prompt_log.txt      # 提示词日志

questionbank/                    # 备用题库源
├── R1-27-D2*.json
├── R1-65*.json
└── R*.json

prompts/
└── annotation/
    ├── system.md               # 系统指令
    ├── user.txt                # Jinja2 模板
    └── metadata.json           # 元数据
```

---

## 核心架构说明

### 1. 两阶段流水线
```
学生音频 (1_input_audio.mp3)
    ↓ (Qwen ASR)
转写文本 (2_qwen_asr.json)
    ↓ (Gemini LLM)
智能评分 (4_llm_annotation.json)
    ↓ (聚合)
批量报告 (batch_annotation_report.json)
```

### 2. 目录驱动的批处理
- 数据集与学生的层级命名决定处理范围
- CLI 统一管理全量/单数据集/单学生入口
- ✨ 新增：文件名模式处理 (无需目录结构)

### 3. 模板与版本控制
- 提示词文件与元数据集中于 `prompts/annotation/`
- `PromptLoader` 确保系统指令、用户模板、元数据一致
- Git 历史作为唯一版本记录

### 4. 可扩展点
- ASR 分段参数（时长 180s、线程数 3）
- 题库热词来源（_shared_context 或 questionbank）
- Gemini 并发度与 verbose/force 控制
- 异常兜底路径（MAX_TOKENS、安全过滤、空响应）

---

## 最新功能更新 (2025-12-03)

### qwen_asr.py 新增功能

**功能**：从文件名自动解析班级、日期、进度、学生信息

**文件名格式**：
```
{班级}_{日期}_{进度}_{学生}.mp3
例如：Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
```

**解析结果**：
- 班级：`Abby61000`
- 日期：`2025-10-30`
- 进度：`R1-27-D2`
- 学生：`Benjamin`

**使用命令**：
```bash
# 基础用法
python3 scripts/qwen_asr.py --file /path/to/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

# 指定输出目录
python3 scripts/qwen_asr.py --file /path/to/audio.mp3 --output /path/to/output

# 指定 API 密钥
python3 scripts/qwen_asr.py --file /path/to/audio.mp3 --api-key YOUR_KEY
```

**输出文件**：
- `2_qwen_asr.json` - 转写结果
- `2_qwen_asr_metadata.json` - 元数据（包含班级、日期、进度、学生信息）

**优势**：
- ✅ 无需目录结构
- ✅ 直接处理单个音频文件
- ✅ 自动从文件名提取元信息
- ✅ 支持任意输出目录

---

## 环境要求

- Python 3.x
- DashScope API Key (DASHSCOPE_API_KEY)
- Gemini API Key (GEMINI_API_KEY)
- ffmpeg/ffprobe (音频处理)
- 依赖包：
  - dashscope
  - google-genai
  - jinja2
  - python-dotenv
  - pathlib (内置)
  - concurrent.futures (内置)
