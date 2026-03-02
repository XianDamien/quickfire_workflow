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
**quickfire_workflow**: 英语发音作业评测系统 | 阿里云 DashScope Qwen LLM + Google Gemini | Python 3.12.12

本项目主要用于 AI 模块的实验性研发与验证：新增并验证 AI 业务能力、开发迭代 agentic 工作流、对不同模型进行系统化评估与对比。

## 模块索引
- `scripts/annotators/` → 模块化评测引擎（base.py 抽象基类、qwen_omni.py、gemini_audio.py）
- `scripts/asr/` → ASR 转写模块（qwen.py、funasr.py）
- `scripts/gatekeeper/` → ASR 质检模块（base.py、qwen_plus.py）
- `scripts/common/` → 共享工具（env.py、naming.py、runs.py、asr.py、constants.py）
- `scripts/contracts/` → 数据契约（asr_timestamp.py、cards.py）
- `scripts/main.py` → 主入口
- `scripts/nocodb_questionbank.py` → NocoDB 题库管理
- `prompts/` → **Prompt 模板资产（受保护，禁止删除）**
- `docs/` → 项目文档

## ⚠️ 受保护资产：prompts/ 目录
**绝对禁止删除 `prompts/` 下的任何文本文件**，包括：
- `prompts/annotation/system.md`、`user_with_audio.md` — annotation 主 prompt
- `prompts/asr_context/system.md` — ASR 上下文 prompt
- `prompts/asr_gatekeeper/system.md`、`user.md` — ASR 质检 prompt
- `prompts/prompt_loader.py` — prompt 加载器（Python 源文件）
- 各子目录的 `metadata.json` — prompt 版本元数据

这些文件是评测系统的核心配置，丢失后系统无法正常运行。修改 prompt 时只能**编辑内容**，不得删除文件本身。归档旧版本请移至 `archived/` 子目录。

## 宪法原则

### 1. 系统架构
- **模块化 Annotator 模式**: `scripts/annotators/base.py` 定义抽象基类，各模型实现独立子类
- **ASR + Gatekeeper 管道**: ASR 转写 → 质检校验 → 评测标注
- **Prompt 模块化**: 系统提示 → 题库上下文 → ASR 数据（分离清晰）
- **结构化输出**: JSON 格式评分报告（final_grade_suggestion/mistake_count/annotations）

### 2. 评分规则（硬编码在 system_prompt）
- 错误类型: MEANING_ERROR | PRONUNCIATION_ERROR | UNCLEAR_PRONUNCIATION | SLOW_RESPONSE
- 等级映射: A=0个MEANING_ERROR | B=1-2个 | C≥3个

### 3. 代码约定
- **语言**: 中文注释和日志
- **API Key**: 环境变量（`DASHSCOPE_API_KEY`、`GEMINI_API_KEY`），禁止硬编码
- **文件路径**: 相对路径 + `file://` 前缀（多模态）
- **错误处理**: 直接输出 API 响应便于调试
- **DRY / KISS**: 不重复、保持简单

### 4. 支持的 LLM 模型
- `qwen-plus` (默认、文本分析)
- `qwen3-omni-30b-a3b-captioner` (音频处理)
- `qwen3-max`、`qwen3-omni-flash` (可选)
- `gemini-2.0-flash` / `gemini-2.5-flash` (音频直传标注)

### 5. 时间戳与说话人识别
- ASR 时间戳单位: 毫秒（milliseconds）
- 说话人标识: spk0/spk1 用于区分教师和学生

### 6. 实验端与生产后端的关系
- 本项目是**独立的实验端**，用于 prompt 调优、模型评估、工作流验证
- 生产后端是独立部署的服务，两者的 prompt/配置需要**手动同步**
- 当实验端验证通过某项改动后，需创建 Linear issue 通知后端团队同步更新
- 例如：`prompts/asr_context/system.md` 的变更需后端在其 ASR 调用的 system message 中同步

## 快速命令
```bash
python scripts/main.py  # 主入口
```

## 详细指南
查看 `scripts/README.md` 和 `docs/` 获取模块级文档。
