# -*- coding: utf-8 -*-
"""
scripts/annotators/config.py - Annotator 配置

集中管理 annotator 相关的默认配置。
"""

# 默认 annotator 模型
DEFAULT_ANNOTATOR = "gemini-3-pro-preview"

# 默认最大输出 token 数
# - Gemini 3 系列支持更大的输出（文档示例为 64k out），cards 任务输出较长时需要提高上限。
# - 非 Gemini 3 模型若不支持这么大的输出上限，请在调用处显式传入 max_output_tokens。
DEFAULT_MAX_OUTPUT_TOKENS = 16384
GEMINI3_MAX_OUTPUT_TOKENS = 64000

# 可用的 Gemini 模型列表
AVAILABLE_GEMINI_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
