# -*- coding: utf-8 -*-
"""
scripts/annotators - Annotator 模块

提供可替换的 LLM annotator 实现。

用法:
    from scripts.annotators import get_annotator

    # 获取默认 Gemini audio annotator
    annotator = get_annotator("gemini-3.1-pro-preview")

    # 处理单个学生
    result = annotator.run_archive_student(
        archive_batch="Zoe41900_2025-09-08",
        student_name="Oscar",
        run_dir=run_dir
    )

支持的 annotator:
    - gemini-3.1-pro-preview (默认，音频模式)
    - gemini-2.5-pro
    - gemini-2.0-flash
    - qwen3-omni-flash (Qwen3-Omni 音频模式)
    - (预留) openai:gpt-4.1
"""

from typing import Dict, Type
from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput
from .config import DEFAULT_ANNOTATOR

# Annotator 注册表
_REGISTRY: Dict[str, Type[BaseAnnotator]] = {}


def register_annotator(name: str, cls: Type[BaseAnnotator]) -> None:
    """
    注册 annotator 类

    Args:
        name: annotator 名称
        cls: annotator 类
    """
    _REGISTRY[name] = cls


def get_annotator(name: str = None, **kwargs) -> BaseAnnotator:
    """
    获取 annotator 实例

    Args:
        name: annotator 名称，支持:
            - gemini-3.1-pro-preview (默认)
            - gemini-2.5-pro
            - gemini-2.0-flash
            - qwen3-omni-flash
            - openai:model-name (预留)
        **kwargs: 传递给 annotator 构造函数的参数

    Returns:
        BaseAnnotator 实例

    Raises:
        ValueError: 不支持的 annotator
    """
    # 使用默认值
    if name is None:
        name = DEFAULT_ANNOTATOR

    # 解析 provider:model 格式
    if ":" in name:
        provider, model = name.split(":", 1)
    else:
        # 默认推断 provider
        if name.startswith("gemini"):
            provider = "gemini"
            model = name
        elif name.startswith("gpt") or name.startswith("openai"):
            provider = "openai"
            model = name.replace("openai-", "")
        elif name.startswith("qwen"):
            provider = "qwen"
            model = name
        else:
            provider = name
            model = name

    # Gemini 系列（统一走音频 annotator）
    if provider == "gemini":
        from .gemini_audio import GeminiAudioAnnotator

        # 规范化模型名称
        if model in ["gemini", "gemini-pro"]:
            model = DEFAULT_ANNOTATOR

        return GeminiAudioAnnotator(model=model, name_override=name, **kwargs)

    # OpenAI 系列 (预留)
    if provider == "openai":
        raise NotImplementedError(
            f"OpenAI annotator 尚未实现: {name}\n"
            f"预留接口，待后续实现"
        )

    # Qwen 系列
    if provider == "qwen":
        # Qwen3-Omni 系列
        if "omni" in model:
            from .qwen_omni import Qwen3OmniAnnotator
            return Qwen3OmniAnnotator(model=model, **kwargs)

        raise ValueError(
            f"不支持的 Qwen 模型: {name}\n"
            f"可用的 Qwen annotator: qwen3-omni-flash"
        )

    # 检查注册表
    if name in _REGISTRY:
        return _REGISTRY[name](**kwargs)

    raise ValueError(
        f"不支持的 annotator: {name}\n"
        f"可用的 annotator: gemini-3.1-pro-preview, gemini-2.5-pro, gemini-2.0-flash, qwen3-omni-flash"
    )


def list_annotators() -> list:
    """
    列出所有可用的 annotator

    Returns:
        annotator 名称列表
    """
    builtin = [
        "gemini-3.1-pro-preview",  # 默认
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "qwen3-omni-flash",
    ]
    custom = list(_REGISTRY.keys())
    return builtin + custom


__all__ = [
    "BaseAnnotator",
    "AnnotatorInput",
    "AnnotatorOutput",
    "get_annotator",
    "register_annotator",
    "list_annotators",
]
