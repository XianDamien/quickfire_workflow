# -*- coding: utf-8 -*-
"""
scripts/common/gemini.py - Gemini 客户端共享工具

提供 Gemini API 客户端创建（含代理）、模型检测、用量提取。
供 classify_asr_type.py 和 match_qb_file.py 共用。
"""

import os

GEMINI_DEFAULT_TIMEOUT_MS = 120000


def is_gemini_model(model: str) -> bool:
    return model.startswith("gemini")


def create_gemini_client(timeout_ms: int = GEMINI_DEFAULT_TIMEOUT_MS):
    """创建 Gemini 客户端（官方 SDK + 代理直连）。"""
    import httpx
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 未设置")

    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("ALL_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("PROXY")
        or "socks5://127.0.0.1:7890"
    )

    print(f"  [代理] {proxy}")
    transport = httpx.HTTPTransport(proxy=proxy, retries=3)
    custom_client = httpx.Client(
        transport=transport,
        timeout=timeout_ms / 1000,
        follow_redirects=True,
    )

    return genai.Client(
        api_key=api_key,
        http_options={"timeout": timeout_ms, "httpxClient": custom_client},
    )


def extract_gemini_usage(resp) -> dict:
    """从 Gemini 响应中提取 token 用量。"""
    um = getattr(resp, "usage_metadata", None)
    if not um:
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
    }
