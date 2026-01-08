# -*- coding: utf-8 -*-
"""
scripts/common/archive.py - Archive 路径与元数据管理

提供统一的 archive 目录结构访问 API，供 main.py、annotator、asr 脚本共用。
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


def project_root() -> Path:
    """
    获取项目根目录

    Returns:
        项目根目录 Path 对象
    """
    # scripts/common/archive.py -> scripts/common -> scripts -> project_root
    return Path(__file__).parent.parent.parent.resolve()


def archive_batch_dir(archive_batch: str) -> Path:
    """
    获取 archive batch 目录路径

    Args:
        archive_batch: batch 名称（如 Zoe41900_2025-09-08）

    Returns:
        archive/{archive_batch}/ 目录 Path
    """
    return project_root() / "archive" / archive_batch


def student_dir(archive_batch: str, student_name: str) -> Path:
    """
    获取学生目录路径

    Args:
        archive_batch: batch 名称
        student_name: 学生名称

    Returns:
        archive/{archive_batch}/{student_name}/ 目录 Path
    """
    return archive_batch_dir(archive_batch) / student_name


def find_audio_file(student_directory: Path) -> Optional[Path]:
    """
    查找学生目录下的音频文件

    优先级顺序:
    1. 1_input_audio.* (任何支持格式)
    2. <StudentName>.* (匹配目录名)
    3. 第一个找到的音频文件
    4. 无则返回 None

    支持的格式: .mp3, .mp4, .wav, .m4a, .flac, .ogg

    Args:
        student_directory: 学生目录 Path

    Returns:
        音频文件 Path，未找到返回 None
    """
    audio_formats = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg'}

    # 优先级 1: 1_input_audio.*
    for audio_file in student_directory.glob('1_input_audio.*'):
        if audio_file.suffix.lower() in audio_formats:
            return audio_file

    # 优先级 2: <StudentName>.* (匹配目录名)
    student_name = student_directory.name
    for audio_file in student_directory.glob(f'{student_name}.*'):
        if audio_file.suffix.lower() in audio_formats:
            return audio_file

    # 优先级 3: 第一个音频文件
    for audio_file in student_directory.glob('*'):
        if audio_file.is_file() and audio_file.suffix.lower() in audio_formats:
            return audio_file

    return None


def load_metadata(archive_batch: str) -> Dict[str, Any]:
    """
    加载 archive/{batch}/metadata.json

    Args:
        archive_batch: batch 名称

    Returns:
        metadata 字典

    Raises:
        FileNotFoundError: metadata.json 不存在
    """
    metadata_path = archive_batch_dir(archive_batch) / "metadata.json"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json 不存在: {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_students(
    archive_batch: str,
    filter_name: Optional[str] = None
) -> List[str]:
    """
    列出 archive batch 下的所有学生

    Args:
        archive_batch: batch 名称
        filter_name: 可选的模糊匹配过滤器

    Returns:
        学生名称列表（已排序）
    """
    batch_dir = archive_batch_dir(archive_batch)

    if not batch_dir.exists():
        return []

    students = []
    excluded = {"reports", "_shared_context", "runs"}

    for item in sorted(batch_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name.startswith("_"):
            continue
        if item.name in excluded:
            continue

        if filter_name:
            if filter_name.lower() in item.name.lower():
                students.append(item.name)
        else:
            students.append(item.name)

    return students


def resolve_question_bank(
    archive_batch: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Path]:
    """
    根据 metadata 解析题库文件路径

    优先级：
    1. metadata.question_bank_path（新格式，指向 questionbank/）
    2. metadata.question_bank_file（旧格式，在 archive 目录下）
    3. metadata.progress 在 questionbank/ 中查找
    4. _shared_context/R*.json（向后兼容）

    Args:
        archive_batch: batch 名称
        metadata: 可选的 metadata 字典，未提供则自动加载

    Returns:
        题库文件 Path，未找到返回 None
    """
    root = project_root()
    batch_dir = archive_batch_dir(archive_batch)

    # 如果未提供 metadata，尝试加载
    if metadata is None:
        try:
            metadata = load_metadata(archive_batch)
        except FileNotFoundError:
            metadata = {}

    # 优先级 1: question_bank_path（新格式）
    qb_path_str = metadata.get("question_bank_path")
    if qb_path_str:
        qb_path = root / qb_path_str
        if qb_path.exists():
            return qb_path

    # 优先级 2: question_bank_file（旧格式）
    qb_file = metadata.get("question_bank_file")
    if qb_file:
        qb_path = batch_dir / qb_file
        if qb_path.exists():
            return qb_path

    # 优先级 3: progress 字段在 questionbank/ 中查找
    progress = metadata.get("progress")
    if progress:
        questionbank_dir = root / "questionbank"
        if questionbank_dir.exists():
            qb_path = questionbank_dir / f"{progress}.json"
            if qb_path.exists():
                return qb_path

    # Fallback: _shared_context/R*.json
    shared_context = batch_dir / "_shared_context"
    if shared_context.exists():
        for f in shared_context.glob("R*.json"):
            if f.is_file() and "vocabulary" not in f.name.lower():
                return f

    return None


def load_file_content(file_path: Union[str, Path]) -> str:
    """
    加载文件内容（UTF-8）

    Args:
        file_path: 文件路径

    Returns:
        文件内容字符串

    Raises:
        FileNotFoundError: 文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()
