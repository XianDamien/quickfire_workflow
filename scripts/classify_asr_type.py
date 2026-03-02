#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classify ASR text into grammar/vocabulary using Qwen models.

Input layout (default):
  two_output/<class>/<student>/<video_stem>/2_qwen_asr.txt

Output per class:
  two_output/<class>/classification_<model>.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root in path
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import dashscope

from scripts.common.env import load_env
from scripts.common.asr import load_qwen_asr_text


SUPPORTED_MODELS = ["qwen3.5-plus", "qwen-long"]


def iter_asr_items(
    input_root: Path,
    class_filter: Optional[str] = None,
    student_filter: Optional[str] = None,
) -> Dict[str, List[Dict[str, str]]]:
    result: Dict[str, List[Dict[str, str]]] = {}

    if not input_root.exists():
        return result

    for class_dir in sorted([p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith(".")]):
        if class_filter and class_filter.lower() not in class_dir.name.lower():
            continue

        items: List[Dict[str, str]] = []
        for student_dir in sorted([p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]):
            if student_filter and student_filter.lower() not in student_dir.name.lower():
                continue

            for video_dir in sorted([p for p in student_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]):
                asr_txt = video_dir / "2_qwen_asr.txt"
                asr_json = video_dir / "2_qwen_asr.json"
                if asr_txt.exists() or asr_json.exists():
                    items.append(
                        {
                            "student": student_dir.name,
                            "video": video_dir.name,
                            "asr_txt": str(asr_txt) if asr_txt.exists() else "",
                            "asr_json": str(asr_json) if asr_json.exists() else "",
                        }
                    )

        if items:
            result[class_dir.name] = items

    return result


def build_prompts(asr_text: str) -> List[Dict[str, str]]:
    system = (
        "你是口语快反课程的分类器。只需要判断类型：\n"
        "- grammar: 知识/语法快反\n"
        "- vocabulary: 单词快反\n"
        "只输出 JSON，格式必须是：{\"type\":\"grammar\"} 或 {\"type\":\"vocabulary\"}。\n"
        "不要输出其他字段、解释或多余文本。"
    )
    user = f"以下是学生转录文本，请判断类型：\n\n{asr_text}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def extract_response_text(response) -> str:
    """
    Extract text from dashscope response (message format).
    Supports both object-style and dict-style.
    """
    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")

    # text result_format
    if output is not None:
        if isinstance(output, dict):
            text = output.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        else:
            text = getattr(output, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()

    choices = None
    if isinstance(output, dict):
        choices = output.get("choices")
    else:
        choices = getattr(output, "choices", None)

    if choices:
        choice = choices[0]
        message = getattr(choice, "message", None) if not isinstance(choice, dict) else choice.get("message")
        if message is None:
            return ""
        content = getattr(message, "content", None) if not isinstance(message, dict) else message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
    return ""


def parse_type_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    # Try direct JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            t = data.get("type")
            if t in ("grammar", "vocabulary"):
                return t
    except Exception:
        pass

    # Try to extract JSON object from text
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                t = data.get("type")
                if t in ("grammar", "vocabulary"):
                    return t
        except Exception:
            pass

    lowered = text.lower()
    if "grammar" in lowered and "vocabulary" not in lowered:
        return "grammar"
    if "vocabulary" in lowered and "grammar" not in lowered:
        return "vocabulary"
    return None


def load_asr_text(item: Dict[str, str]) -> str:
    if item.get("asr_txt"):
        with open(item["asr_txt"], "r", encoding="utf-8") as f:
            return f.read().strip()
    if item.get("asr_json"):
        return load_qwen_asr_text(item["asr_json"])
    return ""


def classify_text(model: str, asr_text: str, temperature: float = 0.2) -> Dict[str, str]:
    messages = build_prompts(asr_text)
    response = dashscope.Generation.call(
        model=model,
        messages=messages,
        temperature=temperature,
        result_format="text",
    )
    status = getattr(response, "status_code", None)
    if status is None and isinstance(response, dict):
        status = response.get("status_code")
    if status is not None and status != 200:
        err_msg = getattr(response, "message", None)
        if err_msg is None and isinstance(response, dict):
            err_msg = response.get("message")
        return {"type": "error", "error": str(err_msg) if err_msg else f"status_code={status}"}
    text = extract_response_text(response)
    label = parse_type_from_text(text)
    if not label:
        return {"type": "error", "raw": text}
    return {"type": label}


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify ASR text into grammar/vocabulary")
    parser.add_argument("--input-root", default="two_output", help="Root directory with ASR outputs")
    parser.add_argument("--class", dest="class_filter", help="Filter class name (substring match)")
    parser.add_argument("--student", dest="student_filter", help="Filter student name (substring match)")
    parser.add_argument("--model", action="append", help="Model name (can pass multiple). Default: qwen3.5-plus & qwen-long")
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between API calls")
    args = parser.parse_args()

    load_env()
    # dashscope will read env internally, but set explicitly if present
    if "DASHSCOPE_API_KEY" in os.environ:
        dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

    models = args.model or SUPPORTED_MODELS
    for model in models:
        if model not in SUPPORTED_MODELS:
            print(f"⚠️  未在默认列表中的模型: {model}")

    input_root = Path(args.input_root)
    class_items = iter_asr_items(input_root, args.class_filter, args.student_filter)
    if not class_items:
        print(f"未找到可分类的 ASR 输出: {input_root}")
        return 1

    for class_name, items in class_items.items():
        class_dir = input_root / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for model in models:
            output_path = class_dir / f"classification_{model}.json"
            if output_path.exists() and not args.force:
                print(f"[跳过] 已存在: {output_path}")
                continue

            results = []
            print(f"\n[分类] 班级 {class_name} - 模型 {model} - 共 {len(items)} 个视频")

            for idx, item in enumerate(items, 1):
                asr_text = load_asr_text(item)
                if not asr_text:
                    results.append(
                        {
                            "student": item["student"],
                            "video": item["video"],
                            "type": "error",
                            "error": "empty_asr",
                        }
                    )
                    continue

                print(f"  ({idx}/{len(items)}) {item['student']}/{item['video']}")
                try:
                    res = classify_text(model, asr_text)
                    out = {
                        "student": item["student"],
                        "video": item["video"],
                        "type": res.get("type", "error"),
                    }
                    if "raw" in res:
                        out["raw"] = res["raw"]
                    if "error" in res:
                        out["error"] = res["error"]
                    results.append(out)
                except Exception as e:
                    results.append(
                        {
                            "student": item["student"],
                            "video": item["video"],
                            "type": "error",
                            "error": str(e),
                        }
                    )

                if args.sleep and args.sleep > 0:
                    time.sleep(args.sleep)

            payload = {
                "class": class_name,
                "model": model,
                "items": results,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"✅ 输出: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
