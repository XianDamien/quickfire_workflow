# -*- coding: utf-8 -*-
"""
scripts/common/hash.py - SHA256 计算工具

提供文件和文本的 SHA256 hash 计算。
"""

import hashlib
from pathlib import Path
from typing import Union


def file_hash(file_path: Union[str, Path], prefix: bool = True, length: int = 16) -> str:
    """
    计算文件的 SHA256 hash

    Args:
        file_path: 文件路径
        prefix: 是否添加 "sha256:" 前缀
        length: hash 截取长度（默认前16位）

    Returns:
        hash 字符串，格式如 "sha256:abc123..." 或 "abc123..."
        如果文件不存在返回 "missing"
    """
    path = Path(file_path)
    if not path.exists():
        return "missing"

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    digest = hasher.hexdigest()[:length]
    return f"sha256:{digest}" if prefix else digest


def text_hash(text: str, prefix: bool = True, length: int = 16) -> str:
    """
    计算文本的 SHA256 hash

    Args:
        text: 文本内容
        prefix: 是否添加 "sha256:" 前缀
        length: hash 截取长度（默认前16位）

    Returns:
        hash 字符串，格式如 "sha256:abc123..." 或 "abc123..."
    """
    hasher = hashlib.sha256()
    hasher.update(text.encode("utf-8"))

    digest = hasher.hexdigest()[:length]
    return f"sha256:{digest}" if prefix else digest
