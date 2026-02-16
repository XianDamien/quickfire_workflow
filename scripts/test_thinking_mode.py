#!/usr/bin/env python3
"""
对比测试 Qwen3-Omni Flash 的思考模式 vs 非思考模式

用法:
    python3 scripts/test_thinking_mode.py --thinking -s Yiyi
    python3 scripts/test_thinking_mode.py --no-thinking -s Yiyi
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common.env import load_env
load_env()


def make_run_id(thinking: bool) -> str:
    """生成带思考模式标记的唯一 run_id"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "thinking" if thinking else "baseline"
    return f"{ts}_{suffix}"


def main():
    parser = argparse.ArgumentParser(description="Qwen3-Omni 思考模式对比测试")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--thinking", action="store_true", help="启用思考模式")
    group.add_argument("--no-thinking", action="store_true", help="不启用思考模式")

    parser.add_argument("--batch", "-b", type=str, default="Zoe51530_2025-12-16")
    parser.add_argument("--student", "-s", type=str, required=True)
    args = parser.parse_args()

    enable_thinking = args.thinking
    mode_label = "thinking=ON" if enable_thinking else "thinking=OFF"
    print(f"\n{'='*60}")
    print(f"  Qwen3-Omni Flash 测试 [{mode_label}]")
    print(f"  batch={args.batch}  student={args.student}")
    print(f"{'='*60}\n")

    from scripts.annotators import get_annotator
    from scripts.common.runs import ensure_run_dir

    run_id = make_run_id(enable_thinking)
    run_dir = ensure_run_dir(args.batch, args.student, "qwen3-omni-flash", run_id)

    overall_start = time.time()
    annotator = get_annotator("qwen3-omni-flash", enable_thinking=enable_thinking)

    result = annotator.run_archive_student(
        archive_batch=args.batch,
        student_name=args.student,
        run_dir=run_dir,
        force=True,
        verbose=True,
    )

    overall_time = time.time() - overall_start

    print(f"\n{'='*60}")
    print(f"  结果摘要 [{mode_label}]")
    print(f"{'='*60}")
    print(f"  成功: {result.success}")
    if result.error:
        print(f"  错误: {result.error}")
    if result.final_grade:
        print(f"  评分: {result.final_grade}")
    if result.response_time_ms:
        print(f"  API 响应时间: {result.response_time_ms:.0f}ms ({result.response_time_ms/1000:.2f}s)")
    print(f"  总耗时: {overall_time:.2f}s")

    if result.run_dir:
        annotation_path = result.run_dir / "4_llm_annotation.json"
        if annotation_path.exists():
            with open(annotation_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("_metadata", {})
            usage = meta.get("token_usage", {})
            print(f"\n  Token 明细:")
            print(f"    prompt_tokens:     {usage.get('prompt_tokens', '?')}")
            print(f"    completion_tokens: {usage.get('completion_tokens', '?')}")
            print(f"    total_tokens:      {usage.get('total_tokens', '?')}")
            if "reasoning_tokens" in usage:
                print(f"    reasoning_tokens:  {usage['reasoning_tokens']}")
            print(f"    enable_thinking:   {meta.get('enable_thinking', '?')}")

        thinking_path = result.run_dir / "thinking_content.txt"
        if thinking_path.exists():
            thinking = thinking_path.read_text()
            print(f"\n  思考内容: {len(thinking)} 字符")
            print(f"  前 300 字符:\n{'─'*40}")
            print(thinking[:300])
            print(f"{'─'*40}")

        print(f"\n  输出目录: {result.run_dir}")
    print()


if __name__ == "__main__":
    main()
