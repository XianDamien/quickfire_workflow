# -*- coding: utf-8 -*-
"""
scripts/common/env.py - 统一环境变量加载

按优先级加载 .env 文件:
1. scripts/.env（最高优先级）
2. 项目根 .env
3. 现有环境变量（不覆盖）

用法:
    from scripts.common.env import load_env
    load_env()  # 在脚本入口最早调用
"""

import os
from pathlib import Path
from typing import Optional

# 标记是否已加载
_env_loaded = False


def load_env(force: bool = False) -> bool:
    """
    统一加载环境变量

    按优先级加载 .env 文件:
    1. scripts/.env（最高优先级，开发环境密钥）
    2. 项目根 .env（次优先级）
    3. 现有环境变量（不覆盖）

    Args:
        force: 是否强制重新加载（默认 False，已加载则跳过）

    Returns:
        True 如果成功加载了至少一个 .env 文件
    """
    global _env_loaded

    if _env_loaded and not force:
        return True

    from dotenv import load_dotenv

    # 计算路径
    # scripts/common/env.py -> scripts/common -> scripts -> project_root
    script_dir = Path(__file__).parent.parent.resolve()
    project_root = script_dir.parent.resolve()

    scripts_env = script_dir / ".env"
    root_env = project_root / ".env"

    loaded = False

    # 优先级 1: scripts/.env（不覆盖现有环境变量）
    if scripts_env.exists():
        load_dotenv(scripts_env, override=False)
        loaded = True

    # 优先级 2: 项目根 .env（不覆盖现有环境变量）
    if root_env.exists():
        load_dotenv(root_env, override=False)
        loaded = True

    _env_loaded = True
    return loaded


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    获取环境变量，确保已加载 .env

    Args:
        key: 环境变量名
        default: 默认值

    Returns:
        环境变量值，或默认值
    """
    load_env()
    return os.getenv(key, default)


def require_env(key: str) -> str:
    """
    获取必需的环境变量，不存在则抛出异常

    Args:
        key: 环境变量名

    Returns:
        环境变量值

    Raises:
        ValueError: 环境变量未设置
    """
    load_env()
    value = os.getenv(key)
    if not value:
        raise ValueError(f"环境变量 {key} 未设置。请检查 scripts/.env 或项目根 .env 文件")
    return value
