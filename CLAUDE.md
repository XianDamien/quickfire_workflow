<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md - 项目架构导航

## 项目概览
**llm_api_queries**: 英语发音作业评测系统 | 阿里云 DashScope Qwen LLM | Python 3.12.12

## 模块索引
- `scripts/` → 核心评测引擎（qwen3.py）及音频转写（captioner_qwen3.py）
- `data/` → 题库（CSV）、ASR 转写结果（JSON/TXT）
- `.claude/` → 子模块配置指南

## 宪法原则

### 1. 系统架构
- **文本 + 多模态混合处理**: qwen3.py 用文本模式、captioner_qwen3.py 用多模态
- **Prompt 模块化**: 系统提示 → 题库上下文 → ASR 数据（分离清晰）
- **结构化输出**: JSON 格式评分报告（final_grade_suggestion/mistake_count/annotations）

### 2. 评分规则（硬编码在 system_prompt）
- 错误类型: MEANING_ERROR | PRONUNCIATION_ERROR | UNCLEAR_PRONUNCIATION | SLOW_RESPONSE
- 等级映射: A=0个MEANING_ERROR | B=1-2个 | C≥3个

### 3. 代码约定
- **语言**: 中文注释和日志
- **API Key**: 环保变量 `DASHSCOPE_API_KEY`，禁止硬编码
- **文件路径**: 相对路径 + `file://` 前缀（多模态）
- **错误处理**: 直接输出 API 响应便于调试

### 4. 支持的 LLM 模型
- `qwen-plus` (默认、文本分析)
- `qwen3-omni-30b-a3b-captioner` (音频处理)
- `qwen3-max`、`qwen3-omni-flash` (可选)

### 5. 时间戳与说话人识别
- ASR 时间戳单位: 毫秒（milliseconds）
- 说话人标识: spk0/spk1 用于区分教师和学生

## 快速命令
```bash
export DASHSCOPE_API_KEY="sk-xxxxx"
python3 scripts/qwen3.py                    # 主评测
python3 scripts/captioner_qwen3.py <audio>  # 音频转写
```

## 详细指南
查看 `scripts/CLAUDE.md` 和 `data/CLAUDE.md` 获取模块级文档。
- make it DRY(Don't Repeat Yourself), keep it simple stupid (KISS)