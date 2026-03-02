#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按班级批量分类 ASR 片段类型（grammar / vocabulary）。

流程：
  1. 每个班级发起一次 API 调用，把所有学生的转录文本按片段编号组合成一个 prompt
  2. 模型返回每个片段的类型（{片段号: 类型}）
  3. 每个学生生成独立的输出 JSON，包含转录路径、预测类型、ground truth 及正误
  4. 与学生目录下的 metadata.json（已标注的答案）对比准确率

目录结构：
  two_output/<班级>/<学生>/<片段号>/2_qwen_asr.txt
  two_output/<班级>/<学生>/metadata.json  ← ground truth（已标注的答案）

输出：
  two_output/<班级>/<学生>/classification_<model>.json  ← 每学生一份
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

DEFAULT_MODEL = "qwen3.5-plus"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ---------------------------------------------------------------------------
# .env 加载
# ---------------------------------------------------------------------------

def load_env(env_file: Optional[str] = None) -> None:
    here = Path(__file__).parent.resolve()
    candidates = [Path(env_file)] if env_file else []
    for parent in [here, here.parent]:
        candidates.append(parent / ".env")
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            return


# ---------------------------------------------------------------------------
# 数据读取
# ---------------------------------------------------------------------------

def seg_sort_key(s: str) -> Tuple:
    """统一排序键，避免 int 与 str 混比。"""
    return (0, int(s)) if s.isdigit() else (1, s)


def find_asr_file(segment_dir: Path) -> Optional[Path]:
    """返回 2_qwen_asr.txt 或 2_qwen_asr.json 的路径（优先 .txt）。"""
    for name in ("2_qwen_asr.txt", "2_qwen_asr.json"):
        p = segment_dir / name
        if p.exists():
            return p
    return None


def read_asr_text(asr_path: Optional[Path]) -> str:
    if asr_path is None:
        return ""
    try:
        raw = asr_path.read_text(encoding="utf-8").strip()
        if asr_path.suffix == ".json":
            data = json.loads(raw)
            if isinstance(data, dict):
                return (data.get("text") or data.get("transcript") or "").strip()
            if isinstance(data, list):
                return " ".join(x.get("text", "") for x in data if isinstance(x, dict)).strip()
        return raw
    except Exception:
        return ""


def load_metadata(student_dir: Path) -> Dict[str, str]:
    """返回 {片段号: 类型} —— 已标注的 ground truth。"""
    f = student_dir / "metadata.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return {
            str(k): v["type"]
            for k, v in data.get("segments", {}).items()
            if isinstance(v, dict) and v.get("type") in ("grammar", "vocabulary")
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 收集班级数据
# ---------------------------------------------------------------------------

def collect_class_data(class_dir: Path, student_filter: Optional[str] = None):
    """
    返回：
      student_data: {
        student_name: {
          seg: {asr_path: Path|None, asr_text: str, ground_truth: str}
        }
      }
      segments_index: {seg: [(student_name, asr_text), ...]}  ← 用于构建 prompt
    """
    student_data: Dict[str, Dict] = {}
    segments_index: Dict[str, List] = {}

    for student_dir in sorted(p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if student_filter and student_filter.lower() not in student_dir.name.lower():
            continue
        metadata = load_metadata(student_dir)
        if not metadata:
            continue
        student_segs = {}
        for seg, truth in metadata.items():
            asr_path = find_asr_file(student_dir / seg)
            asr_text = read_asr_text(asr_path)
            student_segs[seg] = {
                "asr_path": asr_path,
                "asr_text": asr_text,
                "ground_truth": truth,
            }
            segments_index.setdefault(seg, []).append((student_dir.name, asr_text))
        student_data[student_dir.name] = student_segs

    return student_data, segments_index


# ---------------------------------------------------------------------------
# Prompt & API
# ---------------------------------------------------------------------------

def load_system_prompt() -> str:
    """从 prompts/asr_classifier/system.md 加载，找不到则使用内嵌备用。"""
    here = Path(__file__).parent.resolve()
    prompt_path = here.parent / "prompts" / "asr_classifier" / "system.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "你是口语快反课程的智能分类器。快反课只有两种片段类型：grammar 和 vocabulary。"
        '仅输出 JSON：{"片段号": "类型", ...}，不要输出其他内容。'
    )


def build_messages_class(class_name: str, segments_index: Dict[str, List]) -> List[Dict]:
    """班级模式：所有学生的文本合并，一次 API 调用。"""
    lines = [f"以下是 {class_name} 的课堂片段转录：\n"]
    for seg in sorted(segments_index.keys(), key=seg_sort_key):
        lines.append(f"【片段 {seg}】")
        for student_name, asr_text in segments_index[seg]:
            text = asr_text or "（无转录文本）"
            lines.append(f"学生 {student_name}：{text}")
        lines.append("")
    return [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": "\n".join(lines)},
    ]


def build_messages_student(student_name: str, segs: Dict) -> List[Dict]:
    """学生模式：单个学生的文本，一次 API 调用。"""
    lines = [f"以下是 {student_name} 的课堂片段转录：\n"]
    for seg in sorted(segs.keys(), key=seg_sort_key):
        text = segs[seg]["asr_text"] or "（无转录文本）"
        lines.append(f"【片段 {seg}】")
        lines.append(text)
        lines.append("")
    return [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": "\n".join(lines)},
    ]


def call_api(model: str, messages: List[Dict], temperature: float = 0.1, thinking: bool = False) -> Dict:
    """
    通过 OpenAI 兼容接口调用 DashScope（支持 Qwen3.5 系列多模态模型）。
    返回 {predictions: {seg: type}} 或 {error: str}。
    """
    client = OpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url=DASHSCOPE_BASE_URL,
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            extra_body={"enable_thinking": thinking},
        )
        content = response.choices[0].message.content
    except Exception as e:
        return {"error": str(e)}

    raw = re.sub(r"^```(?:json)?\s*", "", content.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        predictions = json.loads(raw)
        if isinstance(predictions, dict):
            valid = {str(k): v for k, v in predictions.items() if v in ("grammar", "vocabulary")}
            return {"predictions": valid}
    except Exception:
        pass
    return {"error": f"无法解析响应: {raw[:300]}"}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def write_student_result(
    class_dir: Path, student_name: str, segs: Dict,
    predictions: Dict[str, str], model: str, mode: str = "student"
) -> Tuple[int, int]:
    """写入单个学生的分类结果，返回 (total, correct)。"""
    out_path = class_dir / student_name / f"classification_{model}.json"
    seg_results = {}
    s_total = s_correct = 0

    for seg in sorted(segs.keys(), key=seg_sort_key):
        entry = segs[seg]
        predicted = predictions.get(seg)
        ground_truth = entry["ground_truth"]
        is_correct = predicted == ground_truth
        asr_path = entry["asr_path"]
        seg_results[seg] = {
            "asr_path": str(asr_path) if asr_path else None,
            "predicted": predicted,
            "ground_truth": ground_truth,
            "correct": is_correct,
        }
        s_total += 1
        if is_correct:
            s_correct += 1

    accuracy = s_correct / s_total if s_total > 0 else None
    out_path.write_text(json.dumps({
        "class": class_dir.name,
        "student": student_name,
        "model": model,
        "mode": mode,
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "correct": s_correct,
        "total": s_total,
        "segments": seg_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    acc_str = f"{accuracy:.1%}" if accuracy is not None else "N/A"
    marks = " ".join(
        f"{seg}={'✓' if seg_results[seg]['correct'] else '✗'}"
        for seg in sorted(seg_results.keys(), key=seg_sort_key)
    )
    print(f"  {student_name}: {acc_str} ({s_correct}/{s_total})  {marks}")
    return s_total, s_correct


def main() -> int:
    parser = argparse.ArgumentParser(description="分类 ASR 片段类型（grammar/vocabulary）并与 metadata 对比准确率")
    parser.add_argument("--input-root", default="two_output")
    parser.add_argument("--class", dest="class_filter", help="班级名称过滤（子串）")
    parser.add_argument("--student", dest="student_filter", help="学生名称过滤（子串）")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--force", action="store_true", help="覆盖已有结果")
    parser.add_argument(
        "--mode", choices=["class", "student"], default="class",
        help="class: 每班一次 API 调用（快，有跨学生干扰）；student: 每学生一次 API 调用（准，成本略高）",
    )
    args = parser.parse_args()

    load_env()
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("错误: 未找到 DASHSCOPE_API_KEY", file=sys.stderr)
        return 1

    input_root = Path(args.input_root).resolve()
    if not input_root.exists():
        print(f"错误: 目录不存在: {input_root}", file=sys.stderr)
        return 1

    class_dirs = sorted(p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if args.class_filter:
        class_dirs = [p for p in class_dirs if args.class_filter.lower() in p.name.lower()]
    if not class_dirs:
        print("未找到班级目录")
        return 1

    grand_total = grand_correct = 0

    for class_dir in class_dirs:
        print(f"\n[班级] {class_dir.name}  模型: {args.model}  模式: {args.mode}")

        student_data, segments_index = collect_class_data(class_dir, args.student_filter)
        if not student_data:
            print("  ⚠️  无有效学生数据，跳过")
            continue

        # ── 班级模式：一次 API 调用，所有学生共享预测结果 ──────────────────
        if args.mode == "class":
            all_segs = sorted(segments_index.keys(), key=seg_sort_key)
            total_texts = sum(len(v) for v in segments_index.values())
            print(f"  片段: {all_segs}  学生: {list(student_data.keys())}  共 {total_texts} 条")

            if not args.force:
                existing = [s for s in student_data
                            if (class_dir / s / f"classification_{args.model}.json").exists()]
                if len(existing) == len(student_data):
                    print(f"  [跳过] 所有学生已有结果  (--force 重新运行)")
                    continue

            messages = build_messages_class(class_dir.name, segments_index)
            result = call_api(args.model, messages, temperature=args.temperature)
            if "error" in result:
                print(f"  ❌ API 错误: {result['error']}")
                continue

            predictions = result["predictions"]
            print(f"  模型预测: {predictions}")

            for student_name, segs in student_data.items():
                out_path = class_dir / student_name / f"classification_{args.model}.json"
                if out_path.exists() and not args.force:
                    continue
                t, c = write_student_result(class_dir, student_name, segs, predictions, args.model, mode="class")
                grand_total += t
                grand_correct += c

        # ── 学生模式：每个学生单独一次 API 调用 ────────────────────────────
        else:
            for student_name, segs in student_data.items():
                out_path = class_dir / student_name / f"classification_{args.model}.json"
                if out_path.exists() and not args.force:
                    print(f"  [跳过] {student_name}  (--force 重新运行)")
                    continue

                seg_list = sorted(segs.keys(), key=seg_sort_key)
                print(f"  {student_name}  片段: {seg_list}", end="  ", flush=True)

                messages = build_messages_student(student_name, segs)
                result = call_api(args.model, messages, temperature=args.temperature)
                if "error" in result:
                    print(f"❌ {result['error']}")
                    continue

                predictions = result["predictions"]
                t, c = write_student_result(class_dir, student_name, segs, predictions, args.model)
                grand_total += t
                grand_correct += c

    if grand_total > 0:
        print(f"\n[汇总] 总准确率 {grand_correct/grand_total:.1%}  ({grand_correct}/{grand_total})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
