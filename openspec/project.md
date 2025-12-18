# Project Context

## Purpose
**llm_api_queries** 是一个英语发音作业评测系统，使用 Qwen ASR 进行音频转写，并使用 Google Gemini 对学生的英语口语作业进行自动化评分和反馈。

核心功能：
- 自动化口语作业评测（基于 ASR 转写结果）
- 音频文件转写（使用 Qwen ASR）
- 结构化评分报告生成（JSON 格式）
- 批量处理学生作业
- 错误类型分析（NO_ANSWER、MEANING_ERROR）
- 处理时间统计（ASR 和 LLM）

## Tech Stack
- **Python 3.13** - 主要开发语言（与 `pyproject.toml` 的 `requires-python >= 3.13` 保持一致）
- **Google Gemini API** - LLM 服务提供商（用于评分和分析）
- **阿里云 Qwen ASR** - 音频转写服务
  - `qwen-asr` 模型 - 音频转文字
- **Jinja2** - Prompt 模板引擎
- **JSON** - 数据交换和配置格式（题库、ASR 输出、评分结果）
- **ThreadPoolExecutor** - 并行处理多个学生作业

## Project Conventions

### Code Style
- **注释和日志语言**: 强制使用中文
- **API 密钥管理**:
  - Gemini API: 使用环境变量 `GEMINI_API_KEY`
  - Qwen ASR: 使用环境变量 `DASHSCOPE_API_KEY`
  - 严禁硬编码任何 API 密钥
- **文件路径**: 使用相对路径
- **错误处理**: 直接输出 API 响应内容以便调试
- **命名规范**:
  - Python 蛇形命名（snake_case）
  - 常量全大写（NO_ANSWER, MEANING_ERROR）

### Architecture Patterns

#### 核心工作流程
1. **输入来源**: 所有音频文件统一来自 `backend_input/` 目录
2. **文件命名格式**: `{班级}_{日期}_{题库编号}_{学生名}.mp3`
   - 例如: `Zoe41900_2025-11-20_R1-38-D3_Kevin.mp3`
   - 从文件名解析题库信息（如 `R1-38-D3`）
3. **ASR 转写**: 使用 `qwen_asr.py` 将音频转为文本
   - 输出: `{学生目录}/2_qwen_asr.json`
4. **题库查找**: 根据文件名中的题库编号在 `/questionbank` 查找对应的 JSON 题库
5. **Gemini 评分**: 使用 `Gemini_annotation.py` 批量处理
   - 输入: 题库 JSON + ASR 转写文本
   - 使用 Jinja2 模板渲染 prompt
   - 输出: `{学生目录}/4_llm_annotation.json` + `batch_annotation_report.json`
6. **日志记录**: 记录每次输入的 system prompt 和 user prompt 的最终文本
7. **时间统计**: 打印 ASR 和 LLM 的处理时间

#### Prompt 模块化设计
- **System Prompt**: `prompts/annotation/system.md`
  - 定义评分规则和标准
  - 说明【问题】-【停顿】-【答案】的固定模式
  - 定义 A/B/C 评级标准
- **User Prompt**: `prompts/annotation/user.txt`
  - 使用 Jinja2 模板变量: `{{ question_bank_json }}`, `{{ student_asr_text }}`
  - 提供题库和学生转写文本
  - 定义 JSON 输出格式

#### 结构化输出
所有评测结果必须以严格的 JSON 格式返回，包含：
- `final_grade_suggestion` - 最终等级（A/B/C）
- `mistake_count.errors` - 错误统计
- `annotations` - 详细批注数组
  - `card_index` - 题目索引
  - `question` - 问题内容
  - `expected_answer` - 标准答案
  - `related_student_utterance.detected_text` - 学生回答
  - `related_student_utterance.issue_type` - 错误类型（NO_ANSWER/MEANING_ERROR）

### Testing Strategy
- **严格约束**:
  - 禁止 mock 任何 ASR 数据，只使用 `backend_input/` 里的真实音频文件
  - 禁止绕过音频测试，禁止做无意义的测试
  - 如果无法解决问题，输出详细的错误报告，而不是 mock 假数据让测试通过
- **测试流程**:
  1. 从 `backend_input/` 选择真实音频文件
  2. 运行 Qwen ASR 转写
  3. 运行 Gemini 评分
  4. 验证输出的 JSON 格式和评分逻辑
- **手动测试命令**: 所有测试命令会直接提供给用户执行

### Git Workflow
- **分支管理**:
  - 主分支: `main`
  - 功能分支示例: `feature/questionbank-asr-processor`
- **Commit 约定**:
  - 中文提交信息
  - 格式: `{类型}({模块}): {描述}`
  - 示例: `feat(gemini-annotation): 支持灵活的题库文件名模式`

## Domain Context

### 评分规则体系

#### 音频处理模式
- **固定模式**: 【问题】-【停顿】-【答案】
  - 老师按照题库顺序读题目和答案
  - 学生在停顿期间尝试回答
  - 定位学生回答: 位于某个【问题】和对应【答案】之间的文本

#### 错误类型
- **NO_ANSWER** - 学生没有回答，或问题因为学生漏录不出现
  - 检测方式: 两次重复的答案，前一个为学生回答，后一个为教师答案
- **MEANING_ERROR** - 学生回答与标准答案不相关或意思错误
  - 检测方式: 检查学生回答是否与标准答案至少有一个词的意思相似

#### 等级映射标准
- **A 级**: 0 个 NO_ANSWER 和 MEANING_ERROR
- **B 级**: 1-2 个 NO_ANSWER / MEANING_ERROR
- **C 级**: ≥3 个 NO_ANSWER / MEANING_ERROR

#### 特殊处理
- 当错误超过 5 个时，需要花更长时间进行复核:
  - 是否定位学生回答的范围错误？
  - 两次重复的答案是否取的是前一次的答案作为学生回答？

### 时间戳与说话人识别
- **时间戳单位**: 毫秒（milliseconds）
- **说话人标识**:
  - `spk0` - 教师
  - `spk1` - 学生

## Important Constraints

### 技术约束
- Python 版本固定为 3.13（或满足 `requires-python >= 3.13`）
- 使用 Google Gemini API 进行评分
- 使用阿里云 Qwen ASR 进行音频转写
- API 调用需要网络连接和有效的 API Key

### 业务约束（严格）
- **Prompt 不可修改**: 未经用户同意，永远不允许改动 system prompt 和 user prompt
- **禁止 fallback**: 开发阶段，永远不允许进行多余的 fallback 机制
- **真实音频测试**: 每次修改完毕必须运行测试，且只能使用 `backend_input/` 里的真实音频文件
  - 禁止 mock 任何 ASR 数据
  - 禁止绕过音频测试
  - 禁止做无意义的测试
- **错误报告**: 如果无法解决问题，必须输出详细具体的错误报告，而不是 mock 假数据让测试通过
- **评分标准**: 评分规则固化在 system_prompt 和 user_prompt 中
- **评分准确性**: 结果的准确性依赖于 ASR 转写质量

### 安全约束
- API Key 敏感信息必须通过环境变量管理
  - `GEMINI_API_KEY` - Google Gemini API 密钥
  - `DASHSCOPE_API_KEY` - 阿里云 API 密钥
- 不得在代码库中提交密钥信息

## External Dependencies

### Google Gemini API
- **用途**: 学生作业的评分和分析
- **认证**: 环境变量 `GEMINI_API_KEY`
- **文档**: https://ai.google.dev/
- **用法**: 接收题库 JSON 和 ASR 转写文本，返回结构化的评分 JSON

### 阿里云 DashScope API
- **用途**: 音频转写（Qwen ASR）
- **认证**: 环境变量 `DASHSCOPE_API_KEY`
- **文档**: https://dashscope.aliyun.com/
- **模型**: Qwen ASR 模型

### 数据依赖
- **题库文件**: `/questionbank/` 目录中的 JSON 文件
  - 命名格式: `R{数字}-{数字}-D{数字}.json`
  - 示例: `R1-38-D3.json`, `R3-14-D4.json`
  - 包含 `question` 和 `answer` 字段
- **音频文件**: `backend_input/` 目录中的 MP3 文件
  - 格式: `{班级}_{日期}_{题库编号}_{学生名}.mp3`
  - 支持任意长度的音频
- **ASR 转写结果**: 学生目录中的 `2_qwen_asr.json`
- **评分输出**: 学生目录中的 `4_llm_annotation.json`
  - 格式: 严格的 JSON，包含 `final_grade_suggestion`, `mistake_count`, `annotations`
