# -*- coding: utf-8 -*-
"""
scripts/annotators/config.py - Annotator 配置

集中管理 annotator 相关的默认配置。

============================================================================
  项目模型规范
============================================================================
  整个项目统一使用 Gemini 音频标注（模型为 Gemini 3 Pro Preview）。

  - Annotator 名称: gemini-3-pro-preview
  - 模型名称: gemini-3-pro-preview
  - 原因: 该模型在音频理解和多语言标注任务上表现最优
  - 注意: 测试时可临时使用其他模型，但生产环境必须使用此模型
============================================================================
"""

import os

# ============================================================================
# 默认 annotator 模型 (项目强制规范)
# ============================================================================
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

# 可用的 Qwen3-Omni 模型列表
AVAILABLE_QWEN3_OMNI_MODELS = [
    "qwen3-omni-flash",
]

# 模型最大输出 token 上限映射
# - 键可以是完整模型名或前缀，按最长匹配原则
# - 用于在初始化 annotator 时自动限制 max_output_tokens
MODEL_MAX_OUTPUT_TOKENS = {
    # Qwen 系列（阿里云 DashScope API 限制: 1-8192）
    "qwen-max": 8192,
    "qwen-max-latest": 8192,
    "qwen3-max": 8192,
    "qwen": 8192,  # 默认 Qwen 系列

    # Qwen3-Omni 系列（最大输出: 16,384 Token）
    "qwen3-omni-flash": 16384,
    "qwen3-omni": 16384,  # 前缀匹配

    # Gemini 3 系列（支持更大输出）
    "gemini-3-": 64000,

    # Gemini 2.5 系列
    "gemini-2.5-": 16384,

    # Gemini 2.0 系列
    "gemini-2.0-": 16384,

    # Gemini 默认
    "gemini-": 16384,
}

# Qwen3-Omni 文件限制配置
QWEN3_OMNI_LIMITS = {
    "qwen3-omni-flash": {
        "max_file_size_mb": 100,
        "max_duration_minutes": 20,
        "max_context_tokens": 65536,  # 最大上下文长度
        "max_input_tokens": 49152,     # 最大输入限制（非思考模式）
        "max_output_tokens": 16384,    # 最大输出限制
    }
}


def get_max_output_tokens(model: str, default: int = None) -> int:
    """
    根据模型名称获取最大输出 token 上限

    按最长前缀匹配原则查找，确保精确匹配优先于模糊匹配。

    示例:
        >>> get_max_output_tokens("qwen-max")
        8192
        >>> get_max_output_tokens("gemini-3-pro-preview")
        64000
        >>> get_max_output_tokens("gemini-2.5-pro")
        16384
        >>> get_max_output_tokens("unknown-model")
        16384  # DEFAULT_MAX_OUTPUT_TOKENS

    Args:
        model: 模型名称
        default: 默认值（如果未找到匹配）。如果为 None，使用 DEFAULT_MAX_OUTPUT_TOKENS

    Returns:
        最大输出 token 数
    """
    if default is None:
        default = DEFAULT_MAX_OUTPUT_TOKENS

    # 按键长度降序排列，确保最长匹配优先
    sorted_keys = sorted(MODEL_MAX_OUTPUT_TOKENS.keys(), key=len, reverse=True)

    for key in sorted_keys:
        if model.startswith(key):
            return MODEL_MAX_OUTPUT_TOKENS[key]

    return default


def clamp_max_output_tokens(model: str, requested: int) -> int:
    """
    限制 max_output_tokens 在模型支持的范围内

    如果请求的 token 数超过模型上限，自动降低到模型上限。

    Args:
        model: 模型名称
        requested: 请求的 max_output_tokens

    Returns:
        限制后的 max_output_tokens（不超过模型上限）
    """
    model_max = get_max_output_tokens(model)

    if requested > model_max:
        return model_max

    return requested
