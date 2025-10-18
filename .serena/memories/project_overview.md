# llm_api_queries 项目概览

## 核心定义
**英语发音作业评测系统**
- 基于：阿里云 DashScope Qwen LLM
- 功能：自动评分+结构化反馈
- 输入：学生音频 + ASR转写 + 题库
- 输出：JSON评分报告(A/B/C级)

## 系统架构
1. **文本模式** (qwen3.py) - 加载题库+ASR结果，调用Qwen Plus分析
2. **多模态模式** (captioner_qwen3.py) - 音频直接处理，生成ASR转写
3. **评分规则** - 硬编码在system_prompt中：
   - 错误类型：MEANING_ERROR | PRONUNCIATION_ERROR | UNCLEAR_PRONUNCIATION | SLOW_RESPONSE
   - 等级映射：A=0个MEANING_ERROR | B=1-2个 | C≥3个

## 技术栈
- Python 3.12.12
- dashscope 1.24.6 (阿里云SDK)
- openai 2.5.0 (兼容模式)
- 模型：qwen-plus (默认) | qwen3-omni-30b-a3b-captioner | qwen3-max | qwen3-omni-flash

## 模块结构
- `scripts/` → 两个评测脚本 (qwen3.py、captioner_qwen3.py)
- `data/` → 题库(CSV)、ASR结果(JSON/TXT)
- `.claude/` → 配置和指南

## 代码约定
- 语言：中文注释
- API Key：环境变量DASHSCOPE_API_KEY（禁止硬编码）
- 文件路径：相对路径 + file:// 前缀(多模态)
- 输出：直接打印API响应便于调试
- 时间戳：毫秒单位
- 说话人：spk0/spk1用于区分教师和学生

## 数据流
```
题库CSV + ASR文本 → Prompt构建(系统提示+题库+ASR数据)
        ↓
    Qwen Plus LLM
        ↓
JSON报告(final_grade_suggestion/mistake_count/annotations)
```
