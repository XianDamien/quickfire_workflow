#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASR Gatekeeper Anomaly Test Script

Tests 4 cases:
- Case A: StudentP1 (audio anomaly - teacher audio following)
- Case B: StudentP0 (audio anomaly - missing teacher audio)
- Case C: Benjamin (wrong questionbank - direction mismatch)
- Case D: Oscar (wrong questionbank - direction mismatch)

Runs with both qwen-plus and qwen3-max, validates JSON output.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dashscope

from prompts.prompt_loader import PromptLoader
from scripts.common.env import load_env
from scripts.common.asr import load_qwen_asr_text, extract_message_text


# Test case definitions
TEST_CASES = [
    {
        "id": "Case_A",
        "name": "StudentP1 (跟读老师音频)",
        "batch": "TestClass88888_2026-01-05",
        "student": "StudentP1",
        "questionbank": "questionbank/R1-26-D6.json",
        "expected": {"status": "FAIL", "issue_type": "AUDIO_ANOMALY"},
        "description": "跟读导致模式异常",
    },
    {
        "id": "Case_B",
        "name": "StudentP0 (未录到老师音频)",
        "batch": "TestClass99999_2026-01-05",
        "student": "StudentP0",
        "questionbank": "questionbank/R1-3-D6.json",
        "expected": {"status": "FAIL", "issue_type": "AUDIO_ANOMALY"},
        "description": "老师音频缺失",
    },
    {
        "id": "Case_C",
        "name": "Benjamin (错题库方向)",
        "batch": "Abby61000_2025-11-05",
        "student": "Benjamin",
        "questionbank": "questionbank/R1-27-D3.json",  # 故意错题库
        "expected": {"status": "FAIL", "issue_type": "WRONG_QUESTIONBANK"},
        "description": "题库方向互换 (应为D4实际D3)",
    },
    {
        "id": "Case_D",
        "name": "Oscar (错题库方向)",
        "batch": "Zoe41900_2025-09-08",
        "student": "Oscar",
        "questionbank": "questionbank/R1-65-D5.json",  # 故意错题库 (ASR是英翻中,这个是中翻英)
        "expected": {"status": "FAIL", "issue_type": "WRONG_QUESTIONBANK"},
        "description": "题库方向互换 (ASR为英翻中但题库为中翻英)",
    },
]

MODELS = ["qwen-plus", "qwen3-max"]


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...(truncated)"


def build_question_bank_json(
    question_bank_path: Path, max_items: int, max_chars: int
) -> Tuple[str, Optional[int]]:
    """Build question bank JSON string for prompt."""
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

    # Limit items
    if max_items > 0:
        items = items[:max_items]

    limited_data = items if isinstance(data, list) else {**data, "items": items}
    json_str = json.dumps(limited_data, ensure_ascii=False, indent=2)
    return truncate_text(json_str, max_chars), len(items)


def call_qwen_gatekeeper(
    model: str,
    system_text: str,
    user_text: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
) -> Tuple[str, float]:
    """Call Qwen API for gatekeeper task."""
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
        result_format="message",
    )
    elapsed_ms = (time.time() - start_time) * 1000

    if response.status_code != 200:
        error_msg = f"DashScope error {response.status_code}"
        if hasattr(response, "message"):
            error_msg += f": {response.message}"
        raise RuntimeError(error_msg)

    content = response.output.choices[0].message.content
    text = extract_message_text(content)
    return text, elapsed_ms


def parse_gatekeeper_output(raw_text: str) -> Dict[str, Optional[str]]:
    """Parse gatekeeper JSON output."""
    # Try to extract JSON from markdown code block
    text = raw_text.strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()

    try:
        result = json.loads(text)
        return {
            "status": result.get("status"),
            "issue_type": result.get("issue_type"),
            "raw": raw_text,
        }
    except json.JSONDecodeError:
        # Fallback: try to extract status manually
        status = None
        issue_type = None
        if "PASS" in text:
            status = "PASS"
        elif "FAIL" in text:
            status = "FAIL"
        if "WRONG_QUESTIONBANK" in text:
            issue_type = "WRONG_QUESTIONBANK"
        elif "AUDIO_ANOMALY" in text:
            issue_type = "AUDIO_ANOMALY"
        return {"status": status, "issue_type": issue_type, "raw": raw_text}


def run_test_case(
    case: Dict,
    model: str,
    api_key: str,
    prompt_dir: Path,
    max_items: int,
    max_chars: int,
    temperature: float,
    max_tokens: int,
    verbose: bool,
) -> Dict:
    """Run gatekeeper test for one case."""
    # Build paths
    asr_path = (
        PROJECT_ROOT / "archive" / case["batch"] / case["student"] / "2_qwen_asr.json"
    )
    qb_path = PROJECT_ROOT / case["questionbank"]

    if not asr_path.exists():
        return {
            "case_id": case["id"],
            "model": model,
            "error": f"ASR file not found: {asr_path}",
        }
    if not qb_path.exists():
        return {
            "case_id": case["id"],
            "model": model,
            "error": f"Question bank not found: {qb_path}",
        }

    # Load ASR text
    asr_text = load_qwen_asr_text(asr_path)

    # Build question bank JSON
    qb_json, item_count = build_question_bank_json(qb_path, max_items, max_chars)

    # Load prompts
    loader = PromptLoader(prompt_dir=str(prompt_dir))
    context = {
        "question_bank_json": qb_json,
        "student_asr_text": asr_text,
    }
    user_text = loader.render_user_prompt(context)
    system_text = loader.system_instruction

    if verbose:
        print(f"\n{'='*60}")
        print(f"Case: {case['id']} | Model: {model}")
        print(f"ASR: {asr_path}")
        print(f"QB: {qb_path}")
        print(f"{'='*60}\n")

    # Call API
    try:
        raw_output, elapsed_ms = call_qwen_gatekeeper(
            model=model,
            system_text=system_text,
            user_text=user_text,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )
    except Exception as e:
        return {
            "case_id": case["id"],
            "model": model,
            "error": str(e),
        }

    # Parse output
    parsed = parse_gatekeeper_output(raw_output)

    return {
        "case_id": case["id"],
        "case_name": case["name"],
        "model": model,
        "expected": case["expected"],
        "actual": {"status": parsed["status"], "issue_type": parsed["issue_type"]},
        "raw_output": parsed["raw"],
        "elapsed_ms": round(elapsed_ms, 2),
        "match": (
            parsed["status"] == case["expected"]["status"]
            and parsed["issue_type"] == case["expected"]["issue_type"]
        ),
    }


def print_results_table(results: List[Dict]):
    """Print results in a formatted table."""
    print("\n" + "=" * 120)
    print(f"{'Case':<12} {'Model':<15} {'Expected':<30} {'Actual':<30} {'Match':<8} {'Time(ms)':<10}")
    print("=" * 120)

    for r in results:
        if "error" in r:
            print(f"{r['case_id']:<12} {r['model']:<15} ERROR: {r['error']}")
            continue

        exp_str = f"{r['expected']['status']} / {r['expected']['issue_type']}"
        act_str = f"{r['actual']['status']} / {r['actual']['issue_type']}"
        match_str = "✓" if r["match"] else "✗"
        time_str = f"{r['elapsed_ms']:.0f}"

        print(
            f"{r['case_id']:<12} {r['model']:<15} {exp_str:<30} {act_str:<30} {match_str:<8} {time_str:<10}"
        )

    print("=" * 120)


def generate_report(results: List[Dict], output_path: Path):
    """Generate detailed markdown report."""
    lines = [
        "# ASR Gatekeeper 音频异常测试报告",
        "",
        f"**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**测试用例数**: {len(TEST_CASES)}",
        f"**测试模型**: {', '.join(MODELS)}",
        "",
        "## 测试结果汇总",
        "",
    ]

    # Summary table
    total_tests = len(results)
    passed = sum(1 for r in results if r.get("match"))
    failed = total_tests - passed

    lines.extend(
        [
            f"- 总测试数: {total_tests}",
            f"- 通过: {passed}",
            f"- 失败: {failed}",
            f"- 通过率: {(passed/total_tests*100):.1f}%",
            "",
            "## 详细结果",
            "",
        ]
    )

    # Group by case
    for case in TEST_CASES:
        case_results = [r for r in results if r.get("case_id") == case["id"]]
        lines.extend(
            [
                f"### {case['id']}: {case['name']}",
                "",
                f"**描述**: {case['description']}",
                f"**批次**: {case['batch']}",
                f"**学生**: {case['student']}",
                f"**题库**: {case['questionbank']}",
                "",
                "| Model | Expected | Actual | Match | Time(ms) |",
                "|-------|----------|--------|-------|----------|",
            ]
        )

        for r in case_results:
            if "error" in r:
                lines.append(f"| {r['model']} | - | ERROR | ✗ | - |")
                lines.append(f"\n**Error**: {r['error']}\n")
                continue

            exp = f"{r['expected']['status']}/{r['expected']['issue_type']}"
            act = f"{r['actual']['status']}/{r['actual']['issue_type']}"
            match = "✓" if r["match"] else "✗"
            lines.append(
                f"| {r['model']} | {exp} | {act} | {match} | {r['elapsed_ms']:.0f} |"
            )

        # Show raw output for failed cases
        failed_cases = [r for r in case_results if not r.get("match")]
        if failed_cases:
            lines.extend(["", "**失败详情**:", ""])
            for r in failed_cases:
                lines.extend(
                    [
                        f"**{r['model']}**:",
                        "```",
                        r["raw_output"],
                        "```",
                        "",
                    ]
                )

        lines.append("")

    report = "\n".join(lines)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n详细报告已保存至: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ASR gatekeeper anomaly tests on 4 cases with 2 models."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=MODELS,
        help=f"Models to test (default: {MODELS})",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=[c["id"] for c in TEST_CASES],
        help="Case IDs to run (default: all)",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument(
        "--prompt-dir",
        default=None,
        help="Prompt directory (default: prompts/asr_gatekeeper)",
    )
    parser.add_argument(
        "--output",
        default="docs/comparison_test/asr_gatekeeper_test_results.md",
        help="Output report path",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env()
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")

    prompt_dir = (
        Path(args.prompt_dir)
        if args.prompt_dir
        else PROJECT_ROOT / "prompts" / "asr_gatekeeper"
    )

    # Filter cases
    cases_to_run = [c for c in TEST_CASES if c["id"] in args.cases]
    if not cases_to_run:
        print(f"No matching cases found for: {args.cases}")
        return 1

    print(f"运行测试: {len(cases_to_run)} cases × {len(args.models)} models")
    print(f"Prompt dir: {prompt_dir}")

    # Run tests
    results = []
    for case in cases_to_run:
        for model in args.models:
            print(f"\n[{case['id']}] {model}...", end=" ", flush=True)
            result = run_test_case(
                case=case,
                model=model,
                api_key=api_key,
                prompt_dir=prompt_dir,
                max_items=args.max_items,
                max_chars=args.max_chars,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                verbose=args.verbose,
            )
            results.append(result)
            if "error" in result:
                print(f"ERROR: {result['error']}")
            elif result["match"]:
                print(f"✓ ({result['elapsed_ms']:.0f}ms)")
            else:
                print(f"✗ ({result['elapsed_ms']:.0f}ms)")

    # Print summary
    print_results_table(results)

    # Generate report
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_report(results, output_path)

    # Return exit code based on pass/fail
    failed_count = sum(1 for r in results if not r.get("match"))
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
