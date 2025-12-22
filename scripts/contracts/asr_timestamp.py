# -*- coding: utf-8 -*-
"""
scripts/contracts/asr_timestamp.py - ASR 时间戳结构校验与提取

提供 3_asr_timestamp.json 的结构校验和文本提取功能。
"""

import json
from pathlib import Path
from typing import Union, Dict, Any, List


def validate_asr_timestamp(data: Dict[str, Any]) -> List[str]:
    """
    校验 3_asr_timestamp.json 结构

    Args:
        data: 解析后的 JSON 数据

    Returns:
        错误列表，空列表表示校验通过
    """
    errors: List[str] = []

    # 校验 transcripts
    transcripts = data.get("transcripts")
    if not transcripts:
        errors.append("缺少 transcripts 字段")
        return errors

    if not isinstance(transcripts, list):
        errors.append(f"transcripts 应为列表，实际为 {type(transcripts).__name__}")
        return errors

    # 校验至少有一个有效的 transcript
    has_valid_transcript = False
    for i, transcript in enumerate(transcripts):
        if not isinstance(transcript, dict):
            errors.append(f"transcripts[{i}] 应为字典")
            continue

        sentences = transcript.get("sentences")
        if not sentences or not isinstance(sentences, list):
            continue

        for j, sentence in enumerate(sentences):
            if not isinstance(sentence, dict):
                errors.append(f"transcripts[{i}].sentences[{j}] 应为字典")
                continue

            # 校验必要字段
            begin_time = sentence.get("begin_time")
            end_time = sentence.get("end_time")
            text = sentence.get("text")

            if begin_time is None:
                errors.append(f"transcripts[{i}].sentences[{j}] 缺少 begin_time")
            elif not isinstance(begin_time, int):
                errors.append(f"transcripts[{i}].sentences[{j}].begin_time 应为 int(ms)")

            if end_time is None:
                errors.append(f"transcripts[{i}].sentences[{j}] 缺少 end_time")
            elif not isinstance(end_time, int):
                errors.append(f"transcripts[{i}].sentences[{j}].end_time 应为 int(ms)")

            if text is None:
                errors.append(f"transcripts[{i}].sentences[{j}] 缺少 text")

            # 如果有有效的 sentence
            if begin_time is not None and end_time is not None and text:
                has_valid_transcript = True

    if not has_valid_transcript:
        errors.append("没有有效的 sentences 数据")

    return errors


def extract_timestamp_text(
    file_path: Union[str, Path],
    strict: bool = True
) -> str:
    """
    从 3_asr_timestamp.json 提取带时间戳的文本

    输入格式 (FunASR 输出):
    {
        "file_url": "...",
        "transcripts": [{
            "channel_id": 0,
            "transcript": "全文文本",
            "sentences": [
                {"begin_time": 1000, "end_time": 2000, "text": "文本片段"},
                ...
            ]
        }]
    }

    输出格式 (用于 Prompt):
    00:01 文本片段1
    00:02 文本片段2
    ...

    Args:
        file_path: 3_asr_timestamp.json 文件路径
        strict: 严格模式，校验失败时抛异常（默认 True）

    Returns:
        带时间戳的文本（MM:SS 格式）

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
        ValueError: 结构校验失败（strict=True 时）
    """
    path = Path(file_path)

    # 读取文件
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 严格模式下进行校验
    if strict:
        errors = validate_asr_timestamp(data)
        if errors:
            raise ValueError(
                f"3_asr_timestamp.json 结构无效:\n"
                f"  - " + "\n  - ".join(errors) + f"\n"
                f"文件: {path}"
            )

    # 提取文本
    lines: List[str] = []
    transcripts = data.get("transcripts", [])

    for transcript in transcripts:
        sentences = transcript.get("sentences", [])
        if not isinstance(sentences, list):
            continue

        for sentence in sentences:
            begin_time_ms = sentence.get("begin_time")
            text = sentence.get("text", "")

            if begin_time_ms is None or not isinstance(begin_time_ms, int):
                continue

            text = text.strip() if text else ""
            if not text:
                continue

            # 将毫秒转换为 MM:SS 格式
            total_seconds = begin_time_ms // 1000
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            timestamp = f"{minutes:02d}:{seconds:02d}"
            lines.append(f"{timestamp} {text}")

    result = "\n".join(lines)

    # 严格模式下检查结果非空
    if strict and not result.strip():
        raise ValueError(
            f"3_asr_timestamp.json 解析后为空，说明 sentences 无有效内容\n"
            f"文件: {path}"
        )

    return result


def extract_sentences_json(
    file_path: Union[str, Path],
    strict: bool = True
) -> str:
    """
    从 3_asr_timestamp.json 提取完整的 sentences 数组（JSON 格式）

    这个函数用于 FunASR 等需要完整时间戳信息的场景，包含：
    - sentence 级别的 begin_time, end_time, text
    - words 级别的详细时间戳数组

    输入格式 (FunASR 输出):
    {
        "file_url": "...",
        "transcripts": [{
            "channel_id": 0,
            "transcript": "全文文本",
            "sentences": [
                {
                    "begin_time": 1000,
                    "end_time": 2000,
                    "text": "文本片段",
                    "words": [
                        {"begin_time": 1000, "end_time": 1500, "text": "文本"},
                        {"begin_time": 1500, "end_time": 2000, "text": "片段"}
                    ]
                },
                ...
            ]
        }]
    }

    输出格式 (JSON 字符串):
    返回 sentences 数组的 JSON 字符串，保留所有时间戳信息

    Args:
        file_path: 3_asr_timestamp.json 文件路径
        strict: 严格模式，校验失败时抛异常（默认 True）

    Returns:
        sentences 数组的 JSON 字符串（格式化，带缩进）

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
        ValueError: 结构校验失败（strict=True 时）
    """
    path = Path(file_path)

    # 读取文件
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 严格模式下进行校验
    if strict:
        errors = validate_asr_timestamp(data)
        if errors:
            raise ValueError(
                f"3_asr_timestamp.json 结构无效:\n"
                f"  - " + "\n  - ".join(errors) + f"\n"
                f"文件: {path}"
            )

    # 提取所有 sentences
    all_sentences: List[Dict[str, Any]] = []
    transcripts = data.get("transcripts", [])

    for transcript in transcripts:
        sentences = transcript.get("sentences", [])
        if not isinstance(sentences, list):
            continue

        # 保留完整的 sentence 结构（包括 words 数组）
        all_sentences.extend(sentences)

    # 严格模式下检查结果非空
    if strict and not all_sentences:
        raise ValueError(
            f"3_asr_timestamp.json 没有有效的 sentences 数据\n"
            f"文件: {path}"
        )

    # 返回格式化的 JSON 字符串
    return json.dumps(all_sentences, ensure_ascii=False, indent=2)
