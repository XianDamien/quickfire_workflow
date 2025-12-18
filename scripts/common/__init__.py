# -*- coding: utf-8 -*-
"""
scripts/common - 共用工具模块

提供 archive 路径管理、hash 计算、runs 目录管理等共用功能。
"""

from .archive import (
    project_root,
    archive_batch_dir,
    student_dir,
    find_audio_file,
    load_metadata,
    list_students,
    resolve_question_bank,
)
from .hash import file_hash, text_hash
from .runs import new_run_id, ensure_run_dir, write_run_manifest

__all__ = [
    # archive
    "project_root",
    "archive_batch_dir",
    "student_dir",
    "find_audio_file",
    "load_metadata",
    "list_students",
    "resolve_question_bank",
    # hash
    "file_hash",
    "text_hash",
    # runs
    "new_run_id",
    "ensure_run_dir",
    "write_run_manifest",
]
