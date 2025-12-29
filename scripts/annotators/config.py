# -*- coding: utf-8 -*-
"""
scripts/annotators/config.py - Annotator 配置

集中管理 annotator 相关的默认配置。
"""

import os

# 默认 annotator 模型
DEFAULT_ANNOTATOR = "gemini-3-pro-preview"

# 默认最大输出 token 数
# - Gemini 3 系列支持更大的输出（文档示例为 64k out），cards 任务输出较长时需要提高上限。
# - 非 Gemini 3 模型若不支持这么大的输出上限，请在调用处显式传入 max_output_tokens。
DEFAULT_MAX_OUTPUT_TOKENS = 16384
GEMINI3_MAX_OUTPUT_TOKENS = 64000

# HTTP 超时配置（毫秒）
# - Gemini 3 系列 max_output_tokens=64000 时生成时间较长，需要更长超时
# - Google API 要求最小 timeout 为 10000ms (10秒)
# - 可通过环境变量 GEMINI_HTTP_TIMEOUT 覆盖（单位：毫秒）
DEFAULT_HTTP_TIMEOUT = int(os.getenv("GEMINI_HTTP_TIMEOUT", "600000"))  # 默认 10 分钟 (600秒)

# 中转站配置
# - 设置 GEMINI_RELAY_BASE_URL 和 GEMINI_RELAY_API_KEY 使用第三方中转站
# - 不设置则使用官方 GEMINI_API_KEY
GEMINI_RELAY_BASE_URL = os.getenv("GEMINI_RELAY_BASE_URL", None)
GEMINI_RELAY_API_KEY = os.getenv("GEMINI_RELAY_API_KEY", None)

# 重试配置
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 5  # 秒

# 可用的 Gemini 模型列表
AVAILABLE_GEMINI_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
