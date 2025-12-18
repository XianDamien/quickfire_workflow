# -*- coding: utf-8 -*-
"""
scripts/contracts/cards.py - Cards 输出校验

提供 LLM 输出的 cards/annotations 结构校验功能。
"""

import re
from typing import List, Dict, Any, Tuple, Optional


def validate_card_timestamp(timestamp: Any) -> bool:
    """
    校验 card_timestamp 格式是否为 MM:SS

    Args:
        timestamp: 时间戳值

    Returns:
        True 如果格式有效，False 否则
    """
    if not timestamp or timestamp is None:
        return False
    if not isinstance(timestamp, str):
        return False

    # 匹配 M:SS 或 MM:SS 格式
    return bool(re.match(r"^\d{1,2}:\d{2}$", timestamp.strip()))


def validate_cards(
    annotations: Any,
    strict_timestamp: bool = True
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    校验 annotations 列表

    Args:
        annotations: LLM 返回的 annotations 列表
        strict_timestamp: 是否严格校验 card_timestamp（Phase 1 默认 True）

    Returns:
        (is_valid, invalid_items) 元组
        - is_valid: 是否全部有效
        - invalid_items: 无效项列表，每项包含 index, card_index, reason
    """
    invalid_items: List[Dict[str, Any]] = []

    # 基本类型检查
    if not isinstance(annotations, list):
        return False, [{"index": -1, "reason": "annotations 不是列表"}]

    if len(annotations) == 0:
        return False, [{"index": -1, "reason": "annotations 为空列表"}]

    # 逐项校验
    for idx, annotation in enumerate(annotations):
        if not isinstance(annotation, dict):
            invalid_items.append({
                "index": idx,
                "reason": f"annotation 不是字典: {type(annotation).__name__}"
            })
            continue

        # 校验必要字段
        card_index = annotation.get("card_index")
        if card_index is None:
            invalid_items.append({
                "index": idx,
                "card_index": "N/A",
                "reason": "缺少 card_index"
            })

        # 严格模式下校验 card_timestamp
        if strict_timestamp:
            card_ts = annotation.get("card_timestamp")
            if not validate_card_timestamp(card_ts):
                invalid_items.append({
                    "index": idx,
                    "card_index": card_index,
                    "card_timestamp": card_ts,
                    "reason": f"card_timestamp 无效或为 null: {repr(card_ts)}"
                })

    return len(invalid_items) == 0, invalid_items


def parse_api_response(raw_response: str) -> Dict[str, Any]:
    """
    解析 API 响应，清理并转换为 Python 对象

    Args:
        raw_response: API 原始响应字符串

    Returns:
        解析后的字典，包含 annotations, final_grade_suggestion, mistake_count
    """
    import json

    # 清理响应
    result = raw_response.strip()
    if "```json" in result:
        result = result.replace("```json", "").replace("```", "").strip()

    # 解析 JSON
    try:
        api_result = json.loads(result)
    except json.JSONDecodeError:
        return {
            "annotations": [],
            "final_grade_suggestion": "C",
            "mistake_count": {"errors": 0},
            "_parse_error": True
        }

    # 处理不同的响应格式
    if isinstance(api_result, dict):
        return {
            "annotations": api_result.get("annotations", []),
            "final_grade_suggestion": api_result.get("final_grade_suggestion", "C"),
            "mistake_count": api_result.get("mistake_count", {"errors": 0})
        }
    elif isinstance(api_result, list):
        # 旧格式：直接是列表
        return {
            "annotations": api_result,
            "final_grade_suggestion": "C",
            "mistake_count": {"errors": 0}
        }
    else:
        return {
            "annotations": [],
            "final_grade_suggestion": "C",
            "mistake_count": {"errors": 0},
            "_parse_error": True
        }
