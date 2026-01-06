#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Independent ASR gatekeeper: compare Qwen ASR text with question bank content
and output a single status (有问题 / 无问题).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dashscope

from prompts.prompt_loader import PromptLoader
from scripts.common.env import load_env


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def extract_message_text(message_content: Any) -> str:
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


def load_qwen_asr_text(asr_path: Path) -> str:
    try:
        data = json.loads(read_text_file(asr_path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid ASR JSON: {asr_path}") from exc

    content = (
        data.get("output", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return extract_message_text(content)


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...(truncated)"


def build_question_bank_summary(
    question_bank_path: Path,
    max_items: int,
    max_chars: int
) -> Tuple[str, Optional[int]]:
    raw_text = read_text_file(question_bank_path)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return truncate_text(raw_text, max_chars), None

    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if isinstance(data.get("items"), list):
            items = data["items"]
        elif isinstance(data.get("cards"), list):
            items = data["cards"]

    if items is None:
        return truncate_text(raw_text, max_chars), None

    lines = []
    for idx, item in enumerate(items[:max_items], start=1):
        if not isinstance(item, dict):
            lines.append(f"{idx}. {item}")
            continue
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        h = (item.get("hint") or "").strip()
        parts = []
        if q:
            parts.append(f"Q: {q}")
        if a:
            parts.append(f"A: {a}")
        if h:
            parts.append(f"Hint: {h}")
        if not parts:
            parts.append(json.dumps(item, ensure_ascii=False))
        lines.append(f"{idx}. " + " | ".join(parts))

    summary = "\n".join(lines)
    return truncate_text(summary, max_chars), len(items)


def call_qwen(
    model: str,
    system_text: str,
    user_text: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
    verbose: bool
) -> Tuple[str, float]:
    dashscope.api_key = api_key
    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    start_time = time.time()
    response = dashscope.Generation.call(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        result_format="message"
    )
    elapsed_ms = (time.time() - start_time) * 1000

    if response.status_code != 200:
        error_msg = f"DashScope error {response.status_code}"
        if hasattr(response, "message"):
            error_msg += f": {response.message}"
        raise RuntimeError(error_msg)

    content = response.output.choices[0].message.content
    text = extract_message_text(content)
    if verbose:
        sys.stderr.write(f"LLM raw response: {text}\n")
    return text, elapsed_ms


def normalize_status(text: str) -> Optional[str]:
    stripped = text.strip()
    if "无问题" in stripped:
        return "无问题"
    if "有问题" in stripped:
        return "有问题"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ASR gatekeeper: validate ASR vs question bank with LLM."
    )
    parser.add_argument("--qwen-asr", required=True, help="Path to 2_qwen_asr.json")
    parser.add_argument("--question-bank", required=True, help="Path to question bank file")
    parser.add_argument("--model", default="qwen-max", help="DashScope model name")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument(
        "--prompt-dir",
        default=None,
        help="Prompt directory (default: prompts/asr_gatekeeper)"
    )
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env()
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")

    asr_text = load_qwen_asr_text(Path(args.qwen_asr))
    question_bank_summary, item_count = build_question_bank_summary(
        Path(args.question_bank),
        max_items=args.max_items,
        max_chars=args.max_chars
    )

    prompt_dir = (
        Path(args.prompt_dir)
        if args.prompt_dir
        else PROJECT_ROOT / "prompts" / "asr_gatekeeper"
    )
    loader = PromptLoader(prompt_dir=str(prompt_dir))
    context = {
        "question_bank_item_count": item_count if item_count is not None else "unknown",
        "question_bank_summary": question_bank_summary,
        "asr_text": asr_text,
        "asr_char_count": len(asr_text),
        "asr_word_count": len(asr_text.split()),
    }
    user_text = loader.render_user_prompt(context)
    system_text = loader.system_instruction

    if args.show_prompt:
        print(system_text)
        print("\n" + "=" * 80 + "\n")
        print(user_text)
        return 0

    if args.verbose:
        sys.stderr.write(f"Model: {args.model}\n")
        sys.stderr.write(f"Prompt dir: {prompt_dir}\n")

    raw_text, _ = call_qwen(
        model=args.model,
        system_text=system_text,
        user_text=user_text,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        api_key=api_key,
        verbose=args.verbose
    )

    status = normalize_status(raw_text)
    if status is None:
        if args.verbose:
            sys.stderr.write("Unexpected output; defaulting to 有问题.\n")
        status = "有问题"

    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
