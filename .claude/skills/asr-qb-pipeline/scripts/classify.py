# -*- coding: utf-8 -*-
"""
classify.py - ASR 片段类型分类（grammar / vocabulary）

从 scripts/classify_asr_type.py 提取的分类专属逻辑。
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# 路径 bootstrap（确保 shared 模块可被导入）
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in [str(_SCRIPTS_DIR), str(_SCRIPTS_DIR.parents[3])]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pydantic import BaseModel, Field

from shared import (  # noqa: E402
    VALID_TYPES,
    _PROJECT_ROOT,
    find_asr_file,
    iter_class_dirs,
    load_metadata_types,
    read_asr_text,
    seg_sort_key,
    setup_clients,
)


# ---------------------------------------------------------------------------
# Pydantic 模型 — Gemini 结构化输出
# ---------------------------------------------------------------------------

class SegmentClassification(BaseModel):
    """单个片段的分类结果。"""
    segment_id: str = Field(description="片段编号")
    type: str = Field(description="分类类型: grammar 或 vocabulary")


class ClassificationResult(BaseModel):
    """所有片段的分类结果。"""
    segments: list[SegmentClassification] = Field(description="各片段分类结果列表")


# ---------------------------------------------------------------------------
# Prompt 加载
# ---------------------------------------------------------------------------

def load_system_prompt() -> str:
    """从 prompts/asr_classifier/system.md 加载，找不到则使用内嵌备用。"""
    prompt_path = _PROJECT_ROOT / "prompts" / "asr_classifier" / "system.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    print(f"⚠️  未找到 prompt 文件: {prompt_path}，使用简化备用 prompt", file=sys.stderr)
    return (
        "你是口语快反课程的智能分类器。快反课只有两种片段类型：grammar 和 vocabulary。"
        '仅输出 JSON：{"片段号": "类型", ...}，不要输出其他内容。'
    )


# ---------------------------------------------------------------------------
# 消息构建
# ---------------------------------------------------------------------------

def build_messages(student_name: str, segs: Dict) -> List[Dict]:
    """构建单个学生的分类请求消息。"""
    lines = [f"以下是 {student_name} 的课堂片段转录：\n"]
    for seg in sorted(segs, key=seg_sort_key):
        text = segs[seg]["asr_text"] or "（无转录文本）"
        lines.append(f"【片段 {seg}】")
        lines.append(text)
        lines.append("")
    return [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": "\n".join(lines)},
    ]


# ---------------------------------------------------------------------------
# API 调用 — DashScope
# ---------------------------------------------------------------------------

def call_api_dashscope(
    client, model: str, messages: List[Dict], temperature: float = 0.1,
) -> Dict:
    """
    通过 OpenAI 兼容接口调用 DashScope。
    返回 {predictions: {seg: type}} 或 {error: str}。
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            extra_body={"enable_thinking": False},
        )
        content = response.choices[0].message.content
    except Exception as e:
        return {"error": str(e)}

    raw = re.sub(r"^```(?:json)?\s*", "", content.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        predictions = json.loads(raw)
        if isinstance(predictions, dict):
            valid = {str(k): v for k, v in predictions.items() if v in VALID_TYPES}
            return {"predictions": valid}
    except Exception:
        pass
    return {"error": f"无法解析响应: {raw[:300]}"}


# ---------------------------------------------------------------------------
# API 调用 — Gemini
# ---------------------------------------------------------------------------

def call_api_gemini(
    gemini_client, model: str, messages: list[dict], temperature: float = 0.1,
) -> dict:
    """通过 Gemini 官方 SDK 调用分类，使用结构化 JSON 输出。"""
    prompt = "\n\n".join(m["content"] for m in messages)
    try:
        resp = gemini_client.models.generate_content(
            model=model,
            contents=[prompt],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ClassificationResult.model_json_schema(),
                "temperature": temperature,
            },
        )
        raw = resp.text or ""
        parsed = json.loads(raw)
        predictions = {}
        for item in parsed.get("segments", []):
            seg_id = str(item.get("segment_id", ""))
            seg_type = item.get("type", "")
            if seg_id and seg_type in VALID_TYPES:
                predictions[seg_id] = seg_type
        return {"predictions": predictions}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 结果写入
# ---------------------------------------------------------------------------

def write_student_result(
    class_dir: Path, student_name: str, segs: Dict,
    predictions: Dict[str, str], model: str,
) -> Tuple[int, int]:
    """写入单个学生的分类结果，返回 (total, correct)。"""
    out_path = class_dir / student_name / f"classification_{model}.json"
    seg_results = {}
    s_total = s_correct = 0

    for seg in sorted(segs, key=seg_sort_key):
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
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "correct": s_correct,
        "total": s_total,
        "segments": seg_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    acc_str = f"{accuracy:.1%}" if accuracy is not None else "N/A"
    marks = " ".join(
        f"{seg}={'✓' if seg_results[seg]['correct'] else '✗'}"
        for seg in sorted(seg_results, key=seg_sort_key)
    )
    print(f"  {student_name}: {acc_str} ({s_correct}/{s_total})  {marks}")
    return s_total, s_correct


# ---------------------------------------------------------------------------
# 数据收集
# ---------------------------------------------------------------------------

def collect_class_data(class_dir: Path, student_filter=None) -> Dict[str, Dict]:
    """
    返回 student_data: {
      student_name: {
        seg: {asr_path: Path|None, asr_text: str, ground_truth: str}
      }
    }
    """
    student_data: Dict[str, Dict] = {}

    for student_dir in sorted(
        p for p in class_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ):
        if student_filter and student_filter.lower() not in student_dir.name.lower():
            continue
        metadata = load_metadata_types(student_dir)
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
        student_data[student_dir.name] = student_segs

    return student_data


# ---------------------------------------------------------------------------
# 子命令入口
# ---------------------------------------------------------------------------

def run_classify(args) -> int:
    """分类子命令主逻辑。"""
    client, gemini_client, use_gemini = setup_clients(args.model)

    input_root = Path(args.input_root).resolve()
    if not input_root.exists():
        print(f"错误: 目录不存在: {input_root}", file=sys.stderr)
        return 1

    class_dirs = iter_class_dirs(input_root, args.class_filter)
    if not class_dirs:
        print("未找到班级目录")
        return 1

    grand_total = grand_correct = 0

    for class_dir in class_dirs:
        print(f"\n[班级] {class_dir.name}  模型: {args.model}")

        student_data = collect_class_data(class_dir, args.student_filter)
        if not student_data:
            print("  ⚠️  无有效学生数据，跳过")
            continue

        for student_name, segs in student_data.items():
            out_path = class_dir / student_name / f"classification_{args.model}.json"
            if out_path.exists() and not args.force:
                print(f"  [跳过] {student_name}  (--force 重新运行)")
                continue

            seg_list = sorted(segs, key=seg_sort_key)
            print(f"  {student_name}  片段: {seg_list}", end="  ", flush=True)

            messages = build_messages(student_name, segs)
            if use_gemini:
                result = call_api_gemini(gemini_client, args.model, messages, temperature=args.temperature)
            else:
                result = call_api_dashscope(client, args.model, messages, temperature=args.temperature)
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
