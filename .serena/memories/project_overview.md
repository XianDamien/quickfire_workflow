# llm_api_queries 项目概览

## 核心定义
**英语发音作业评测系统**
- 基于：阿里云 DashScope Qwen LLM
- 功能：自动评分+结构化反馈
- 输入：学生音频 + ASR转写 + 题库
- 输出：JSON评分报告(A/B/C级)

## 系统架构
1. **ASR 转写** (qwen_asr.py) - Qwen3-ASR 音频转写，支持两种输入模式
   - 标准模式：archive/<dataset>/<student>/ 目录结构
   - ✨ 新增文件名模式：从 {班级}_{日期}_{进度}_{学生}.mp3 自动解析信息
2. **Gemini 评分** (Gemini_annotation.py) - 基于 Gemini LLM 的学生回答提取与评分
3. **评分规则** - Gemini LLM 负责：
   - 错误类型：NO_ANSWER | MEANING_ERROR
   - 等级映射：A=0个 | B=1-2个 | C≥3个

## 技术栈
- Python 3.12.12
- dashscope 1.24.6 (阿里云SDK)
- openai 2.5.0 (兼容模式)
- 模型：qwen-plus (默认) | qwen3-omni-30b-a3b-captioner | qwen3-max | qwen3-omni-flash

## 模块结构
- `scripts/main.py` → 一键入口，DAG 依赖驱动的批处理工具
- `scripts/qwen_asr.py` → Qwen ASR 音频转写（支持标准模式和文件名模式）
- `scripts/funasr.py` → FunASR 带时间戳转写（阿里云 DashScope）
- `scripts/Gemini_annotation.py` → Gemini 回答提取与评分
- `scripts/common/` → 公共工具模块
  - `env.py` → 统一环境变量加载（scripts/.env 优先）
  - `naming.py` → 统一命名解析（parse_backend_input_mp3_name 等）
  - `archive.py` → Archive 目录操作（find_audio_file 等）
  - `runs.py` → Run ID 管理
- `scripts/annotators/` → 可替换 LLM annotator 架构
  - `gemini.py` → Gemini 实现
  - `base.py` → 基类定义
- `prompts/prompt_loader.py` → Jinja2 提示词加载与渲染
- `prompts/annotation/` → 提示词模板（system.md + user.txt + metadata.json）
- `questionbank/` → 题库源文件（R*.json 格式）
- `.claude/` → 配置和指南

## 代码约定
- 语言：中文注释
- API Key：环境变量 DASHSCOPE_API_KEY 和 GEMINI_API_KEY（禁止硬编码）
- 文件路径：相对路径
- 输出：直接打印API响应便于调试
- 版本控制：提示词通过 git 追踪，metadata.json 记录版本信息
- 题库来源：统一使用 /questionbank/ 目录

## ✨ 新增功能：文件名解析模式

### 文件名格式
```
{班级}_{日期}_{进度}_{学生}.mp3
例如：Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
```

### 自动解析内容
- 班级：Abby61000
- 日期：2025-10-30
- 进度：R1-27-D2
- 学生：Benjamin

### 使用方式
```bash
python3 scripts/qwen_asr.py --file /path/to/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
python3 scripts/qwen_asr.py --file /path/to/audio.mp3 --output /path/to/output
```

### 输出文件
- 2_qwen_asr.json - 转写结果
- 2_qwen_asr_metadata.json - 元数据（包含班级、日期、进度、学生信息）

## 数据流
```
学生音频（1_input_audio.mp3）
    ↓
Qwen ASR 转写（2_qwen_asr.json）
    ↓
FunASR 时间戳转写（3_asr_timestamp.json）
    ↓
题库（/questionbank/R*.json）+ Jinja2 提示词模板
    ↓
Gemini LLM 回答提取与评分
    ↓
runs/{run_id}/4_llm_annotation.json（单学生结果）
    ↓
批量聚合
    ↓
reports/{run_id}/batch_annotation_report.json（班级级报告）
```

## 一键入口 main.py

### 使用方式
```bash
# 完整流程（默认 --target cards）
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08

# 指定学生
python3 scripts/main.py -b Zoe41900_2025-09-08 -s Oscar

# 干运行（预览命令）
python3 scripts/main.py -b Zoe41900_2025-09-08 --dry-run

# 执行到指定阶段
python3 scripts/main.py -b Zoe41900_2025-09-08 --until timestamps
```

### DAG 阶段
```
audio → qwen_asr → timestamps → cards
```
- `audio`: 检查音频文件存在
- `qwen_asr`: Qwen ASR 转写
- `timestamps`: FunASR 时间戳转写
- `cards`: Gemini LLM 评分
