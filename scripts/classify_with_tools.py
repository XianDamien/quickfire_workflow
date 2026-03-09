#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具调用版 ASR 分类器。

search_questionbank 工具：字对字精确匹配
  - 主要：搜索所有题库 JSON 的 question/answer 字段，英文字词精确命中
  - 辅助：中文关键词命中文件名（grammar 文件名中含主题词）
  - 返回匹配度最高的题库文件名

用法：
  uv run python scripts/classify_with_tools.py \
    --input-root /path/to/two_output \
    --qb-root /path/to/questionbank \
    --class Niko60900_2026-02-03
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
MAX_TOOL_ROUNDS = 8

# 搜索时排除的高频英文停词（课堂通用词，不具有区分度）
EN_STOPWORDS = {
    "yes", "no", "or", "and", "is", "the", "now", "you", "do", "to", "of",
    "in", "a", "an", "it", "he", "she", "we", "they", "his", "her", "your",
    "our", "what", "when", "where", "who", "why", "how", "can", "will", "has",
    "had", "have", "are", "was", "were", "be", "been", "go", "get", "like",
    "milk", "school", "noun", "adjective", "verb", "if", "then", "ok", "wh",
    "question", "sentence", "answer", "say", "call", "this", "that", "with",
    "from", "at", "by", "on", "for", "as", "so", "not", "but", "also",
}

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
# 题库索引构建
# ---------------------------------------------------------------------------

def build_questionbank_index(qb_root: Path) -> Dict[str, Dict]:
    """
    扫描 qb_root/grammar/*.json 和 qb_root/vocabulary/*.json，
    构建内容索引：
      {
        filename: {
          "category": "grammar" | "vocabulary",
          "path": Path,
          "en_words": set,    # 所有 question/answer 中的小写英文单词
          "zh_text": str,     # 所有 question/answer 拼成的中文文本
          "cards": list,      # 原始卡片数据
        }
      }
    """
    index: Dict[str, Dict] = {}
    for category in ("grammar", "vocabulary"):
        cat_dir = qb_root / category
        if not cat_dir.exists():
            continue
        for json_file in cat_dir.glob("*.json"):
            try:
                cards = json.loads(json_file.read_text(encoding="utf-8"))
                en_words: set = set()
                zh_parts: list = []
                for card in cards:
                    if not isinstance(card, dict):
                        continue
                    for field in ("question", "answer", "hint"):
                        text = card.get(field, "") or ""
                        # 英文词
                        words = re.findall(r"[a-zA-Z']{2,}", text.lower())
                        en_words.update(w for w in words if w not in EN_STOPWORDS)
                        # 中文片段
                        zh = re.sub(r"[a-zA-Z0-9\s\W]", "", text)
                        if zh:
                            zh_parts.append(zh)
                index[json_file.name] = {
                    "category": category,
                    "path": json_file,
                    "en_words": en_words,
                    "zh_text": "".join(zh_parts),
                    "cards": cards,
                }
            except Exception:
                continue
    return index


# ---------------------------------------------------------------------------
# 搜索实现（字对字精确匹配）
# ---------------------------------------------------------------------------

def search_questionbank_impl(asr_text: str, qb_index: Dict[str, Dict], top_k: int = 3) -> str:
    """
    精确内容匹配：
      1. 从 ASR 提取英文单词集合（过滤停词）→ 匹配 vocabulary 文件 question/answer
      2. 从 ASR 提取中文关键短语 → 匹配 grammar 文件名和内容
      3. 按得分降序，返回 top_k 结果
    """
    # 提取 ASR 英文词（去停词）
    asr_en = set(re.findall(r"[a-zA-Z']{2,}", asr_text.lower()))
    asr_en -= EN_STOPWORDS

    # 提取 ASR 中文（连续汉字短语，≥2字）
    asr_zh_phrases = re.findall(r"[\u4e00-\u9fff]{2,}", asr_text)

    results: List[Tuple[float, str, str]] = []  # (score, category, filename)

    for filename, info in qb_index.items():
        score = 0.0

        # ── 英文词精确命中（字对字）──────────────────────────────────────
        if asr_en and info["en_words"]:
            overlap = asr_en & info["en_words"]
            # 命中词数 / 文件总词数（避免大文件虚高）
            precision = len(overlap) / max(len(info["en_words"]), 1)
            recall = len(overlap) / max(len(asr_en), 1)
            f1 = 2 * precision * recall / max(precision + recall, 1e-9)
            score += f1 * 60  # 主要分

        # ── 中文短语命中文件名（grammar 专用）────────────────────────────
        fname_lower = filename.lower()
        for phrase in asr_zh_phrases:
            if len(phrase) >= 3 and phrase in filename:
                score += len(phrase) * 4  # 越长的短语匹配越可信

        # ── 中文短语命中文件内容 ──────────────────────────────────────────
        for phrase in asr_zh_phrases:
            if len(phrase) >= 2 and phrase in info["zh_text"]:
                score += len(phrase) * 1.5

        if score > 0:
            results.append((score, info["category"], filename))

    results.sort(key=lambda x: -x[0])
    top = results[:top_k]

    if not top:
        return "未找到匹配的题库文件（ASR 内容与题库无重叠）"

    lines = []
    for score, cat, fname in top:
        lines.append(f"[{cat}] {fname}  (score={score:.1f})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 数据读取
# ---------------------------------------------------------------------------

def seg_sort_key(s: str) -> Tuple:
    return (0, int(s)) if s.isdigit() else (1, s)


def find_asr_file(segment_dir: Path) -> Optional[Path]:
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


def collect_class_data(class_dir: Path, student_filter: Optional[str] = None) -> Dict[str, Dict]:
    student_data: Dict[str, Dict] = {}
    for student_dir in sorted(p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if student_filter and student_filter.lower() not in student_dir.name.lower():
            continue
        metadata = load_metadata(student_dir)
        if not metadata:
            continue
        student_segs = {}
        for seg, truth in metadata.items():
            asr_path = find_asr_file(student_dir / seg)
            student_segs[seg] = {
                "asr_path": asr_path,
                "asr_text": read_asr_text(asr_path),
                "ground_truth": truth,
            }
        student_data[student_dir.name] = student_segs
    return student_data


# ---------------------------------------------------------------------------
# 工具定义 & 调用
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_questionbank",
            "description": (
                "在题库中精确搜索与 ASR 内容匹配的题库文件。"
                "工具会对 ASR 文本中的英文单词和中文短语做字对字精确匹配，"
                "返回匹配度最高的题库文件名（含 grammar/vocabulary 分类）。"
                "当你无法仅凭 ASR 文本判断片段类型时，调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asr_text": {
                        "type": "string",
                        "description": "该片段的 ASR 转录文本（全文或前几句均可）",
                    }
                },
                "required": ["asr_text"],
            },
        },
    }
]


def call_api_with_tools(
    model: str,
    messages: List[Dict],
    qb_index: Dict[str, Dict],
    temperature: float = 0.1,
    verbose: bool = False,
) -> Dict:
    """
    多轮工具调用循环，直到模型输出最终分类 JSON。
    返回 {predictions: {seg: type}, tool_calls_count: int} 或 {error: str}。
    """
    client = OpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url=DASHSCOPE_BASE_URL,
    )

    msgs = list(messages)
    tool_calls_count = 0

    for _ in range(MAX_TOOL_ROUNDS + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=TOOLS,
                tool_choice="auto",
                temperature=temperature,
            )
        except Exception as e:
            return {"error": str(e)}

        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            # 追加 assistant 消息（含 tool_calls）
            msgs.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_calls_count += 1
                try:
                    fn_args = json.loads(tc.function.arguments)
                except Exception:
                    fn_args = {}

                asr_query = fn_args.get("asr_text", "")
                result = search_questionbank_impl(asr_query, qb_index)

                if verbose:
                    # 只显示 asr 前 40 字
                    preview = asr_query[:40].replace("\n", " ")
                    print(f"    [工具] search_questionbank({preview!r}...)")
                    for line in result.splitlines():
                        print(f"           {line}")

                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue

        # 无工具调用 → 最终 JSON
        content = msg.content or ""
        raw = re.sub(r"^```(?:json)?\s*", "", content.strip())
        raw = re.sub(r"\s*```$", "", raw)
        try:
            predictions = json.loads(raw)
            if isinstance(predictions, dict):
                valid = {str(k): v for k, v in predictions.items() if v in ("grammar", "vocabulary")}
                return {"predictions": valid, "tool_calls_count": tool_calls_count}
        except Exception:
            pass
        return {"error": f"无法解析最终响应: {raw[:300]}"}

    return {"error": f"超过最大工具调用轮数 ({MAX_TOOL_ROUNDS})"}


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------

def load_system_prompt() -> str:
    here = Path(__file__).parent.resolve()
    prompt_path = here.parent / "prompts" / "asr_classifier" / "system.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "你是口语快反课程的智能分类器。快反课只有两种片段类型：grammar 和 vocabulary。"
        '仅输出 JSON：{"片段号": "类型", ...}，不要输出其他内容。'
    )


TOOL_HINT = """
你有 search_questionbank 工具可用：传入某片段的 ASR 文本，工具会在题库中做精确内容匹配，返回最可能对应的题库文件名（含分类）。
当 ASR 开头无法判断类型，或内容模棱两可时，调用此工具辅助判断。
最终输出格式：{"片段号": "grammar"|"vocabulary", ...}，不输出其他内容。
"""


def build_messages(student_name: str, segs: Dict) -> List[Dict]:
    lines = [f"以下是学生 {student_name} 各片段的 ASR 转录：\n"]
    for seg in sorted(segs.keys(), key=seg_sort_key):
        text = segs[seg]["asr_text"] or "（无转录文本）"
        lines.append(f"【片段 {seg}】")
        lines.append(text)
        lines.append("")
    return [
        {"role": "system", "content": load_system_prompt() + "\n\n" + TOOL_HINT},
        {"role": "user", "content": "\n".join(lines)},
    ]


# ---------------------------------------------------------------------------
# 结果写入
# ---------------------------------------------------------------------------

def write_student_result(
    class_dir: Path,
    student_name: str,
    segs: Dict,
    predictions: Dict[str, str],
    model: str,
    tool_calls_count: int,
) -> Dict[str, Tuple[int, int]]:
    """写入结果，返回 {type: (total, correct)}。"""
    out_path = class_dir / student_name / f"classification_tools_{model}.json"
    seg_results = {}
    type_stats: Dict[str, Tuple[int, int]] = {"grammar": (0, 0), "vocabulary": (0, 0)}

    for seg in sorted(segs.keys(), key=seg_sort_key):
        entry = segs[seg]
        predicted = predictions.get(seg)
        ground_truth = entry["ground_truth"]
        is_correct = predicted == ground_truth
        seg_results[seg] = {
            "asr_path": str(entry["asr_path"]) if entry["asr_path"] else None,
            "predicted": predicted,
            "ground_truth": ground_truth,
            "correct": is_correct,
        }
        if ground_truth in type_stats:
            t, c = type_stats[ground_truth]
            type_stats[ground_truth] = (t + 1, c + (1 if is_correct else 0))

    total = sum(t for t, _ in type_stats.values())
    correct = sum(c for _, c in type_stats.values())
    acc = correct / total if total > 0 else None

    out_path.write_text(json.dumps({
        "class": class_dir.name,
        "student": student_name,
        "model": model,
        "mode": "tool_calling",
        "tool_calls_count": tool_calls_count,
        "accuracy": round(acc, 4) if acc is not None else None,
        "correct": correct,
        "total": total,
        "type_stats": {k: {"total": t, "correct": c} for k, (t, c) in type_stats.items()},
        "segments": seg_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    acc_str = f"{acc:.1%}" if acc is not None else "N/A"
    marks = " ".join(
        f"{seg}={'✓' if seg_results[seg]['correct'] else '✗'}({seg_results[seg]['ground_truth'][0]})"
        for seg in sorted(seg_results.keys(), key=seg_sort_key)
    )
    vt, vc = type_stats["vocabulary"]
    vocab_acc = f"{vc}/{vt}" if vt > 0 else "—"
    print(f"  {student_name}: 总{acc_str}({correct}/{total})  vocab={vocab_acc}  tools={tool_calls_count}  {marks}")

    return type_stats


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="工具调用版 ASR 分类器（字对字精确搜索）")
    parser.add_argument("--input-root", default="two_output")
    parser.add_argument("--qb-root", default="/Users/damien/Desktop/Venture/quickfire_workflow/questionbank",
                        help="题库根目录（含 grammar/ 和 vocabulary/ 子目录）")
    parser.add_argument("--class", dest="class_filter")
    parser.add_argument("--student", dest="student_filter")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="显示每次工具调用详情")
    args = parser.parse_args()

    load_env()
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("错误: 未找到 DASHSCOPE_API_KEY", file=sys.stderr)
        return 1

    # 构建题库索引
    qb_root = Path(args.qb_root)
    print(f"正在建立题库索引：{qb_root}")
    qb_index = build_questionbank_index(qb_root)
    grammar_cnt = sum(1 for v in qb_index.values() if v["category"] == "grammar")
    vocab_cnt = sum(1 for v in qb_index.values() if v["category"] == "vocabulary")
    print(f"索引完成：grammar={grammar_cnt} 文件，vocabulary={vocab_cnt} 文件")

    input_root = Path(args.input_root)
    if not input_root.is_absolute():
        input_root = Path(__file__).parent.parent / args.input_root
    if not input_root.exists():
        print(f"错误: 目录不存在: {input_root}", file=sys.stderr)
        return 1

    class_dirs = sorted(p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if args.class_filter:
        class_dirs = [p for p in class_dirs if args.class_filter.lower() in p.name.lower()]
    if not class_dirs:
        print("未找到班级目录")
        return 1

    grand: Dict[str, Tuple[int, int]] = {"grammar": (0, 0), "vocabulary": (0, 0)}

    for class_dir in class_dirs:
        print(f"\n[班级] {class_dir.name}  模型={args.model}")
        student_data = collect_class_data(class_dir, args.student_filter)
        if not student_data:
            print("  ⚠️  无有效学生数据，跳过")
            continue

        class_stats: Dict[str, Tuple[int, int]] = {"grammar": (0, 0), "vocabulary": (0, 0)}

        for student_name, segs in student_data.items():
            out_path = class_dir / student_name / f"classification_tools_{args.model}.json"
            if out_path.exists() and not args.force:
                print(f"  [跳过] {student_name}")
                continue

            messages = build_messages(student_name, segs)
            result = call_api_with_tools(
                args.model, messages, qb_index,
                temperature=args.temperature,
                verbose=args.verbose,
            )
            if "error" in result:
                print(f"  ❌ {student_name}: {result['error']}")
                continue

            type_stats = write_student_result(
                class_dir, student_name, segs,
                result["predictions"], args.model,
                result.get("tool_calls_count", 0),
            )
            for typ in ("grammar", "vocabulary"):
                t, c = class_stats[typ]
                dt, dc = type_stats[typ]
                class_stats[typ] = (t + dt, c + dc)

        # 班级小结（vocabulary 专项）
        vt, vc = class_stats["vocabulary"]
        gt_t, gt_c = class_stats["grammar"]
        all_t, all_c = vt + gt_t, vc + gt_c
        if all_t > 0:
            print(f"\n  [班级] 总体 {all_c/all_t:.1%}({all_c}/{all_t})", end="")
            if vt > 0:
                print(f"  vocabulary {vc/vt:.1%}({vc}/{vt})", end="")
            if gt_t > 0:
                print(f"  grammar {gt_c/gt_t:.1%}({gt_c}/{gt_t})", end="")
            print()

        for typ in ("grammar", "vocabulary"):
            t, c = grand[typ]
            dt, dc = class_stats[typ]
            grand[typ] = (t + dt, c + dc)

    # 全局汇总
    vt, vc = grand["vocabulary"]
    gt_t, gt_c = grand["grammar"]
    all_t, all_c = vt + gt_t, vc + gt_c
    print("\n" + "=" * 50)
    if all_t > 0:
        print(f"[全局] 总体    {all_c/all_t:.1%} ({all_c}/{all_t})")
    if vt > 0:
        print(f"[全局] vocab   {vc/vt:.1%} ({vc}/{vt})")
    if gt_t > 0:
        print(f"[全局] grammar {gt_c/gt_t:.1%} ({gt_c}/{gt_t})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
