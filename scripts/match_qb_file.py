#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_qb_file.py - 三步法匹配 ASR 片段对应的具体题库文件

流程（每个片段）：
  1. LLM 将 ASR 文本解析为结构化 [{question, answer}, ...] 列表
     （快反课每道题答案出现两次：学生先答、教师录音再确认；取完整答案）
  2. 用 Q/A 内容搜索题库：
     - grammar / vocabulary 各自预建 {normalized_question → [文件名]} 索引
     - 精确匹配提取的 question 字段，返回所有命中文件及匹配题数
  3. 题目数量过滤：|file_entries - parsed_qa_count| ≤ tolerance
     所有通过的候选交给 LLM 最终判断
  4. LLM 通过 function calling 阅读候选内容，提交最终匹配

输出：
  two_output/<班级>/<学生>/qb_match_<model>.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from openai import OpenAI


DEFAULT_MODEL = "qwen3.5-plus"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
COUNT_TOLERANCE = 3   # 题目数量允许偏差


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
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            return


# ---------------------------------------------------------------------------
# ASR 文本提取
# ---------------------------------------------------------------------------

def extract_asr_text(asr_path: Path) -> str:
    try:
        raw = asr_path.read_text(encoding="utf-8").strip()
        if asr_path.suffix == ".json":
            data = json.loads(raw)
            if isinstance(data, dict):
                choices = data.get("output", {}).get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", [])
                    if content and isinstance(content, list):
                        return content[0].get("text", "").strip()
                return (data.get("text") or data.get("transcript") or "").strip()
        return raw
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 文本标准化（用于索引 key）
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """去掉首尾空白和末尾标点，英文小写。"""
    text = text.strip()
    text = re.sub(r"[\s？。，、\?,\.!！]+$", "", text).strip()
    return re.sub(r"[a-zA-Z]+", lambda m: m.group().lower(), text)


# ---------------------------------------------------------------------------
# Step 1：LLM 解析 ASR → 结构化 Q/A
# ---------------------------------------------------------------------------

_PARSE_SYSTEM = """你是快反课堂 ASR 转录解析助手。

快反课堂互动规律：
- 教师逐题提问，学生尝试回答（第一次，可能不完整）
- 随后播放教师预录音频给出标准答案（第二次，答案更完整准确）
- 因此每道题的答案通常出现两次，取后一次或更完整的那次

任务：将 ASR 转录解析为结构化题目列表。

grammar 类型（语法题）：
- question：教师的提问原文（保留原始措辞，去末尾问号）
- answer：标准答案
- 示例：{"question": "问一个东西是什么，用哪个词", "answer": "What"}

vocabulary 类型（词汇题）：
- question：原始单词本身（英文或中文，不加任何修饰语）
- answer：对应的翻译/释义
- 示例：{"question": "kid", "answer": "小孩"}
- ❌ 错误：{"question": "单词 kid 的中文释义是什么", ...}

通用规则：
- 跳过开场白、过渡语、与题目无关的内容
- 输出仅返回 JSON 数组，不要包含其他文字"""


def parse_asr_to_qa(client: OpenAI, model: str, asr_text: str, seg_type: str) -> list[dict]:
    """
    调用 LLM 将 ASR 文本解析为 [{question, answer}, ...] 列表。
    失败时返回空列表。
    """
    type_hint = (
        "（grammar 类型：中文提问 → 英文语法答案）"
        if seg_type == "grammar"
        else "（vocabulary 类型：英文单词 → 中文释义）"
    )
    user_content = f"片段类型：{seg_type} {type_hint}\n\nASR 转录：\n{asr_text}"

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _PARSE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or ""
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [
                {"question": str(item.get("question", "")).strip(),
                 "answer": str(item.get("answer", "")).strip()}
                for item in parsed
                if isinstance(item, dict) and item.get("question")
            ]
    except Exception as e:
        print(f"      [parse_asr_to_qa 失败] {e}", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# Step 2：题库索引 + Q/A 搜索
# ---------------------------------------------------------------------------

class QuestionBankIndex:
    """
    预加载所有题库文件，构建 {normalized_question → [文件名]} 索引。
    grammar 和 vocabulary 分别建索引。
    """

    def __init__(self, qb_root: Path):
        self.grammar_dir = qb_root / "grammar"
        self.vocab_dir = qb_root / "vocabulary"

        # {normalized_q → [filenames]}
        self._grammar_q_index: dict[str, list[str]] = defaultdict(list)
        self._vocab_q_index: dict[str, list[str]] = defaultdict(list)

        # {filename → entries}
        self._grammar_entries: dict[str, list[dict]] = {}
        self._vocab_entries: dict[str, list[dict]] = {}

        self._build()

    def _build(self):
        print("  [索引] 加载 grammar 题库...", end="", flush=True)
        for f in self.grammar_dir.glob("*.json"):
            try:
                entries = json.loads(f.read_text(encoding="utf-8"))
                self._grammar_entries[f.name] = entries
                for entry in entries:
                    nq = normalize(entry.get("question", ""))
                    if nq:
                        self._grammar_q_index[nq].append(f.name)
            except Exception:
                continue
        print(f" {len(self._grammar_entries)} 个文件")

        print("  [索引] 加载 vocabulary 题库...", end="", flush=True)
        for f in self.vocab_dir.glob("*.json"):
            try:
                entries = json.loads(f.read_text(encoding="utf-8"))
                self._vocab_entries[f.name] = entries
                for entry in entries:
                    nq = normalize(entry.get("question", ""))
                    if nq:
                        self._vocab_q_index[nq].append(f.name)
            except Exception:
                continue
        print(f" {len(self._vocab_entries)} 个文件")

    def search_by_qa(self, qa_pairs: list[dict], seg_type: str) -> list[tuple[str, int]]:
        """
        用解析出的 Q/A 对搜索题库。
        对每道题的 question 做精确匹配（normalized），
        统计各文件命中次数，返回 [(filename, match_count)] 降序。
        """
        index = self._grammar_q_index if seg_type == "grammar" else self._vocab_q_index
        counts: dict[str, int] = defaultdict(int)
        for qa in qa_pairs:
            nq = normalize(qa.get("question", ""))
            for fname in index.get(nq, []):
                counts[fname] += 1
        return sorted(counts.items(), key=lambda x: -x[1])

    def filter_by_count(
        self,
        candidates: list[tuple[str, int]],
        n_qa: int,
        seg_type: str,
        tolerance: int = COUNT_TOLERANCE,
    ) -> list[tuple[str, int]]:
        """
        保留 entries 数量与 n_qa 接近（±tolerance）的候选。
        返回 [(filename, entry_count)] 按 match_count 原顺序。
        """
        result = []
        for fname, match_count in candidates:
            n_entries = len(self._grammar_entries.get(fname, []) if seg_type == "grammar"
                           else self._vocab_entries.get(fname, []))
            if abs(n_entries - n_qa) <= tolerance:
                result.append((fname, n_entries))
        return result

    def load_entries(self, filename: str, seg_type: str) -> list[dict]:
        if seg_type == "grammar":
            return self._grammar_entries.get(filename, [])
        return self._vocab_entries.get(filename, [])

    def all_filenames(self, seg_type: str) -> list[str]:
        if seg_type == "grammar":
            return list(self._grammar_entries.keys())
        return list(self._vocab_entries.keys())


# ---------------------------------------------------------------------------
# Step 3+4：LLM 工具调用最终判断
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_qb_file",
            "description": "读取指定题库文件的全部题目和答案，用于与已解析的 Q/A 对比确认",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "题库文件名（含 .json），例如 R024-5W基础知识.json"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "提交最终匹配的题库文件名（确认后调用，只调用一次）",
            "parameters": {
                "type": "object",
                "properties": {
                    "qb_file": {"type": "string", "description": "最终匹配的题库文件名"},
                    "reason": {"type": "string", "description": "一句话说明匹配依据"}
                },
                "required": ["qb_file", "reason"]
            }
        }
    }
]

_MATCH_SYSTEM = """你是快反课题库匹配专家。

已知：
- ASR 转录已被解析为结构化 Q/A 列表（每道题：question + answer）
- 候选题库文件已通过 Q/A 内容匹配和题目数量初步筛选

你的任务：
1. 查看候选列表（含各文件命中题数和总题数）
2. 调用 read_qb_file 查看最可能候选的完整题目
3. 与解析出的 Q/A 列表对比，确认最佳匹配
4. 调用 submit_answer 提交结果

每次只提交一个最终答案。"""


def agentic_match(
    client: OpenAI,
    model: str,
    asr_text: str,
    qa_pairs: list[dict],
    candidates: list[tuple[str, int]],   # (filename, entry_count)
    seg_type: str,
    index: QuestionBankIndex,
    max_turns: int = 8,
) -> dict:
    """
    返回 {"qb_file": str, "reason": str, "tool_calls": int}
    或   {"error": str}
    """
    qa_text = "\n".join(
        f"  {i+1}. Q: {qa['question']}  →  A: {qa['answer']}"
        for i, qa in enumerate(qa_pairs)
    )
    candidate_lines = "\n".join(
        f"  {i+1}. {fname}（共 {n} 题）"
        for i, (fname, n) in enumerate(candidates)
    )

    user_content = f"""【已解析的 Q/A 列表（共 {len(qa_pairs)} 题）】
{qa_text}

【片段类型】{seg_type}

【候选题库文件（已通过 Q/A 内容匹配 + 题数过滤）】
{candidate_lines}

请通过工具调用确认并提交最匹配的题库文件。"""

    messages = [
        {"role": "system", "content": _MATCH_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    tool_call_count = 0

    for _ in range(max_turns):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                temperature=0.1,
            )
        except Exception as e:
            return {"error": str(e)}

        msg = resp.choices[0].message
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            return {"error": "LLM 未调用工具就停止了"}

        for tc in msg.tool_calls:
            tool_call_count += 1
            fn = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            if fn == "read_qb_file":
                filename = args.get("filename", "")
                entries = index.load_entries(filename, seg_type)
                if entries:
                    body = "\n".join(
                        f"  Q: {e.get('question', '?')}  →  A: {e.get('answer', '?')}"
                        for e in entries
                    )
                    tool_result = f"【{filename}】共 {len(entries)} 题：\n{body}"
                else:
                    tool_result = f"文件不存在或内容为空: {filename}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

            elif fn == "submit_answer":
                return {
                    "qb_file": args.get("qb_file", ""),
                    "reason": args.get("reason", ""),
                    "tool_calls": tool_call_count,
                }

    return {"error": f"超过最大轮次 ({max_turns})"}


# ---------------------------------------------------------------------------
# 元数据加载
# ---------------------------------------------------------------------------

def load_metadata(student_dir: Path) -> dict:
    """返回 {"2/2_qwen_asr.json": {"type": ..., "qb_file": ...}, ...}"""
    f = student_dir / "metadata.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        gt = data.get("ground_truth", {})
        return {
            k: v for k, v in gt.items()
            if isinstance(v, dict) and v.get("type") and v.get("qb_file")
        }
    except Exception:
        return {}


def seg_key_to_num(seg_key: str) -> str:
    return seg_key.split("/")[0]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="三步法匹配 ASR 片段对应的题库文件")
    parser.add_argument("--input-root", default="two_output")
    parser.add_argument("--qb-root", default="questionbank")
    parser.add_argument("--class", dest="class_filter")
    parser.add_argument("--student", dest="student_filter")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tolerance", type=int, default=COUNT_TOLERANCE,
                        help="题目数量过滤允许偏差（默认 ±3）")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_env()
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("错误: 未找到 DASHSCOPE_API_KEY", file=sys.stderr)
        return 1

    input_root = Path(args.input_root).resolve()
    qb_root = Path(args.qb_root).resolve()
    for p, name in [(input_root, "input_root"), (qb_root, "qb_root")]:
        if not p.exists():
            print(f"错误: {name} 不存在: {p}", file=sys.stderr)
            return 1

    print("[初始化] 构建题库索引...")
    index = QuestionBankIndex(qb_root)

    client = OpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url=DASHSCOPE_BASE_URL,
    )

    class_dirs = sorted(p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if args.class_filter:
        class_dirs = [p for p in class_dirs if args.class_filter.lower() in p.name.lower()]

    grand_total = grand_correct = 0

    for class_dir in class_dirs:
        for student_dir in sorted(p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if args.student_filter and args.student_filter.lower() not in student_dir.name.lower():
                continue

            metadata = load_metadata(student_dir)
            if not metadata:
                continue

            out_path = student_dir / f"qb_match_{args.model}.json"
            if out_path.exists() and not args.force:
                print(f"  [跳过] {class_dir.name}/{student_dir.name}  (用 --force 重新运行)")
                continue

            print(f"\n[学生] {class_dir.name}/{student_dir.name}  ({len(metadata)} 个片段)")
            seg_results = {}

            for seg_key, gt_info in sorted(metadata.items()):
                seg_num = seg_key_to_num(seg_key)
                seg_type = gt_info["type"]
                gt_qb_file = gt_info["qb_file"]

                # 读取 ASR 文本
                asr_path = None
                for suffix in ("2_qwen_asr.json", "2_qwen_asr.txt"):
                    p = student_dir / seg_num / suffix
                    if p.exists():
                        asr_path = p
                        break

                asr_text = extract_asr_text(asr_path) if asr_path else ""
                if not asr_text:
                    print(f"    片段 {seg_num}: 无 ASR 文本，跳过")
                    continue

                print(f"    片段 {seg_num} [{seg_type}]:")

                # Step 1: LLM 解析 ASR → Q/A 列表
                qa_pairs = parse_asr_to_qa(client, args.model, asr_text, seg_type)
                print(f"      解析出 {len(qa_pairs)} 道题: "
                      + str([qa["question"][:15] + "…" for qa in qa_pairs[:3]]))

                if not qa_pairs:
                    print("      ❌ ASR 解析失败，跳过")
                    seg_results[seg_key] = {
                        "seg_type": seg_type, "predicted": None,
                        "ground_truth": gt_qb_file, "correct": False,
                        "error": "ASR 解析失败",
                    }
                    grand_total += 1
                    continue

                # Step 2: Q/A 内容搜索题库
                search_results = index.search_by_qa(qa_pairs, seg_type)
                gt_match_count = next((n for f, n in search_results if f == gt_qb_file), 0)
                print(f"      Q/A 搜索命中 {len(search_results)} 个文件  "
                      f"(GT '{gt_qb_file}' 命中 {gt_match_count}/{len(qa_pairs)} 题)")

                # Step 3: 题目数量过滤
                filtered = index.filter_by_count(search_results, len(qa_pairs), seg_type, args.tolerance)
                gt_in_filtered = any(f == gt_qb_file for f, _ in filtered)
                print(f"      数量过滤（±{args.tolerance}）后: {len(filtered)} 个候选  "
                      f"GT {'✓' if gt_in_filtered else '✗'}")

                # Fallback：过滤后无候选 → 用搜索结果前5
                if not filtered:
                    print("      ⚠ 无候选通过数量过滤，使用 Q/A 搜索前 5")
                    filtered = [
                        (fname, len(index.load_entries(fname, seg_type)))
                        for fname, _ in search_results[:5]
                    ]

                # Step 4: LLM 最终判断
                result = agentic_match(
                    client, args.model, asr_text, qa_pairs,
                    filtered, seg_type, index,
                )

                if "error" in result:
                    print(f"      ❌ {result['error']}")
                    seg_results[seg_key] = {
                        "seg_type": seg_type, "predicted": None,
                        "ground_truth": gt_qb_file, "correct": False,
                        "gt_in_filtered_candidates": gt_in_filtered,
                        "parsed_qa_count": len(qa_pairs),
                        "error": result["error"],
                    }
                    grand_total += 1
                    continue

                predicted = result["qb_file"]
                is_correct = predicted == gt_qb_file
                print(f"      {'✓' if is_correct else '✗'} 预测: {predicted}  "
                      f"[{result.get('tool_calls', 0)} 次工具调用]")
                print(f"        理由: {result.get('reason', '')[:80]}")

                seg_results[seg_key] = {
                    "seg_type": seg_type,
                    "predicted": predicted,
                    "ground_truth": gt_qb_file,
                    "correct": is_correct,
                    "gt_in_filtered_candidates": gt_in_filtered,
                    "parsed_qa_count": len(qa_pairs),
                    "gt_search_match_count": gt_match_count,
                    "reason": result.get("reason", ""),
                    "tool_calls": result.get("tool_calls", 0),
                    "parsed_qa": qa_pairs,
                }
                grand_total += 1
                if is_correct:
                    grand_correct += 1

            # 写结果
            correct = sum(1 for v in seg_results.values() if v.get("correct"))
            total = len(seg_results)
            accuracy = correct / total if total > 0 else None
            out_path.write_text(
                json.dumps({
                    "class": class_dir.name, "student": student_dir.name,
                    "model": args.model,
                    "accuracy": round(accuracy, 4) if accuracy is not None else None,
                    "correct": correct, "total": total,
                    "segments": seg_results,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            acc_str = f"{accuracy:.1%}" if accuracy is not None else "N/A"
            print(f"  → 准确率 {acc_str} ({correct}/{total})  写入 {out_path.name}")

    if grand_total > 0:
        print(f"\n[汇总] qb_file 匹配准确率: {grand_correct/grand_total:.1%}  ({grand_correct}/{grand_total})")
    else:
        print("\n[汇总] 无有效数据")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
