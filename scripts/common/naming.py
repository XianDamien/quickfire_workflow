# -*- coding: utf-8 -*-
"""
scripts/common/naming.py - 统一命名解析

处理 backend_input 音频文件名和 archive batch ID 的解析。
"""

import re
from typing import Optional, Dict


def parse_backend_input_mp3_name(filename: str) -> Optional[Dict[str, str]]:
    """
    解析 backend_input 音频文件名。

    格式: {ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3
    示例: Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

    也支持分段文件后缀（如 *_1.mp3, *_2.mp3），会自动移除。

    Args:
        filename: 音频文件名（不含路径）

    Returns:
        包含解析字段的字典，或 None 如果格式不匹配

        返回字段:
        - class_code: 班级代码（如 Abby61000）
        - date: 日期（如 2025-10-30）
        - question_bank: 题库代码（如 R1-27-D2）
        - student_name: 学生名字（如 Benjamin）
        - filename: 原始文件名
    """
    # 移除数字后缀（用于分段文件，如 *_1.mp3）
    base_name = re.sub(r'_\d+\.mp3$', '.mp3', filename)

    pattern = r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)_(.+)\.mp3$'
    match = re.match(pattern, base_name)

    if not match:
        return None

    class_code, date, question_bank, student_name = match.groups()

    return {
        "class_code": class_code,
        "date": date,
        "question_bank": question_bank,
        "student_name": student_name,
        "filename": filename
    }


def parse_archive_batch_id(batch_id: str) -> Optional[Dict[str, str]]:
    """
    解析 archive batch ID。

    格式: {ClassCode}_{Date}
    示例: Zoe41900_2025-09-08

    Args:
        batch_id: batch 名称

    Returns:
        包含解析字段的字典，或 None 如果格式不匹配

        返回字段:
        - class_code: 班级代码（如 Zoe41900）
        - date: 日期（如 2025-09-08）
    """
    pattern = r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})$'
    match = re.match(pattern, batch_id)

    if not match:
        return None

    class_code, date = match.groups()

    return {
        "class_code": class_code,
        "date": date
    }


def extract_progress_from_questionbank(question_bank_code: str) -> str:
    """
    从题库代码提取进度信息。

    例如: "R1-27-D2" -> "R1-27"
    例如: "R3-14-D4" -> "R3-14"

    Args:
        question_bank_code: 题库代码

    Returns:
        进度字符串，提取失败则返回原代码
    """
    match = re.match(r'([A-Z]\d+-\d+)', question_bank_code)
    if match:
        return match.group(1)
    return question_bank_code


def build_file_id(class_code: str, date: str, question_bank: str, student_name: str) -> str:
    """
    构建标准文件 ID。

    格式: {ClassCode}_{Date}_{QuestionBank}_{StudentName}
    示例: Zoe41900_2025-09-08_R1-65-D5_Oscar

    Args:
        class_code: 班级代码
        date: 日期
        question_bank: 题库代码
        student_name: 学生名字

    Returns:
        文件 ID 字符串
    """
    return f"{class_code}_{date}_{question_bank}_{student_name}"
