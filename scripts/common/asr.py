# -*- coding: utf-8 -*-
"""
scripts/common/asr.py - ASR parsing helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union


def extract_message_text(message_content: Any) -> str:
    """
    Extract plain text from Qwen-style message content.

    Supports both list-of-parts and string formats. Ignores non-text metadata.
    """
    if isinstance(message_content, list):
        parts = []
        for item in message_content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
    if isinstance(message_content, str):
        return message_content.strip()
    return ""


def extract_qwen_asr_text(asr_data: Dict[str, Any]) -> str:
    """
    Extract plain transcript text from Qwen ASR JSON output.
    """
    if not isinstance(asr_data, dict):
        return ""

    output = asr_data.get("output")
    if isinstance(output, dict):
        choices = output.get("choices", [])
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                content = message.get("content", "")
                text = extract_message_text(content)
                if text:
                    return text

        output_text = output.get("text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

    fallback_text = asr_data.get("text")
    if isinstance(fallback_text, str):
        return fallback_text.strip()
    return ""


def load_qwen_asr_text(path: Union[str, Path]) -> str:
    """
    Load a Qwen ASR JSON file and return plain transcript text.
    """
    file_path = Path(path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return extract_qwen_asr_text(data)
