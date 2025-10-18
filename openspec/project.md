# Project Context

## Purpose
**llm_api_queries** 是一个英语发音作业评测系统，使用阿里云 DashScope Qwen LLM 系列模型对学生的英语口语作业进行自动化评分和反馈。

核心功能：
- 自动化口语作业评测（基于 ASR 转写结果）
- 音频文件转写（多模态音频处理）
- 结构化评分报告生成（JSON 格式）
- 多维度错误分析（发音、语义、流利度）

## Tech Stack
- **Python 3.12.12** - 主要开发语言
- **阿里云 DashScope API** - LLM 服务提供商
- **Qwen 模型系列**:
  - `qwen-plus` - 默认文本分析模型
  - `qwen3-omni-30b-a3b-captioner` - 音频处理和转写
  - `qwen3-max` / `qwen3-omni-flash` - 可选高级模型
- **JSON** - 数据交换和配置格式
- **CSV** - 题库存储格式

## Project Conventions

### Code Style
- **注释和日志语言**: 强制使用中文
- **API 密钥管理**: 必须使用环境变量 `DASHSCOPE_API_KEY`，严禁硬编码
- **文件路径**: 使用相对路径，多模态文件需添加 `file://` 前缀
- **错误处理**: 直接输出 API 响应内容以便调试
- **命名规范**:
  - Python 蛇形命名（snake_case）
  - 常量全大写（MEANING_ERROR, PRONUNCIATION_ERROR）

### Architecture Patterns
- **混合处理模式**:
  - `qwen3.py` - 纯文本模式处理评测逻辑
  - `captioner_qwen3.py` - 多模态模式处理音频转写
- **Prompt 模块化设计**:
  1. 系统提示（System Prompt）- 定义评分规则和标准
  2. 题库上下文（Question Bank Context）- 提供标准答案
  3. ASR 数据（Student Response）- 学生实际表现
- **结构化输出**: 所有评测结果必须以 JSON 格式返回，包含：
  - `final_grade_suggestion` - 最终等级（A/B/C）
  - `mistake_count` - 错误统计
  - `annotations` - 详细批注

### Testing Strategy
- 目前无正式测试框架
- 手动测试通过运行脚本验证输出
- 建议未来添加单元测试和集成测试

### Git Workflow
- 当前未配置 Git（项目目录不是 Git 仓库）
- 建议建立 Git 管理和版本控制

## Domain Context

### 评分规则体系
评分系统基于错误类型分类：
- **MEANING_ERROR** - 语义错误（最严重）
- **PRONUNCIATION_ERROR** - 发音错误
- **UNCLEAR_PRONUNCIATION** - 发音不清晰
- **SLOW_RESPONSE** - 响应速度慢

### 等级映射标准
- **A 级**: 0 个 MEANING_ERROR
- **B 级**: 1-2 个 MEANING_ERROR
- **C 级**: ≥3 个 MEANING_ERROR

### 时间戳与说话人识别
- **时间戳单位**: 毫秒（milliseconds）
- **说话人标识**:
  - `spk0` - 教师
  - `spk1` - 学生

## Important Constraints

### 技术约束
- 必须使用阿里云 DashScope API（无备选方案）
- Python 版本固定为 3.12.12
- API 调用需要网络连接和有效的 API Key

### 业务约束
- 评分标准固化在 system_prompt 中，需修改代码才能调整
- 评分结果的准确性依赖于 ASR 转写质量
- 多模态音频处理对文件格式和路径有特定要求

### 安全约束
- API Key 敏感信息必须通过环境变量管理
- 不得在代码库中提交密钥信息

## External Dependencies

### 阿里云 DashScope API
- **用途**: LLM 模型调用和音频转写
- **认证**: 环境变量 `DASHSCOPE_API_KEY`
- **文档**: https://dashscope.aliyun.com/
- **模型端点**: 通过 SDK 自动管理

### 数据依赖
- **题库文件**: `data/*.csv` - 标准答案和题目
- **ASR 转写结果**: `data/*.json` 或 `data/*.txt` - 学生语音转写
- **音频文件**: 支持多种格式（具体格式需通过多模态 API 文档确认）
