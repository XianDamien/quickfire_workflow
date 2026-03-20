#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_qb_file.py - 两步法匹配 ASR 片段对应的具体题库文件

流程（每个片段，2 次 LLM 调用）：
  1. LLM 分类 + 解析合并调用：判断 grammar/vocabulary 并解析为 [{question, answer}, ...]
  2. 用 Q/A 内容搜索题库索引（精确匹配 question 字段）+ 题目数量过滤
  3. LLM 通过 function calling 阅读候选内容，提交最终匹配

输出：
  - 更新 metadata.json：写入 qb_file + 用量统计
  - 详细结果：qb_match_<model>.json
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field


DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
COUNT_TOLERANCE = 3


# ---------------------------------------------------------------------------
# 工具函数
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


def normalize(text: str) -> str:
    """去掉首尾空白和末尾标点，英文小写。"""
    text = text.strip()
    text = re.sub(r"[\s？。，、\?,\.!！]+$", "", text).strip()
    return re.sub(r"[a-zA-Z]+", lambda m: m.group().lower(), text)


def extract_usage(resp) -> dict:
    """从 OpenAI 响应中提取 token 用量。"""
    u = getattr(resp, "usage", None)
    if not u:
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": getattr(u, "prompt_tokens", 0) or getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "completion_tokens", 0) or getattr(u, "output_tokens", 0) or 0,
    }


def merge_usage(a: dict, b: dict) -> dict:
    return {
        "input_tokens": a.get("input_tokens", 0) + b.get("input_tokens", 0),
        "output_tokens": a.get("output_tokens", 0) + b.get("output_tokens", 0),
    }


# ---------------------------------------------------------------------------
# Gemini 支持
# ---------------------------------------------------------------------------

from scripts.common.gemini import (
    is_gemini_model,
    create_gemini_client,
    extract_gemini_usage,
)


# Pydantic 模型 — 结构化输出

class QAPairModel(BaseModel):
    question: str = Field(description="教师提问原文或原始单词")
    answer: str = Field(description="标准答案或释义")


class ClassifyAndParseResult(BaseModel):
    """合并分类 + Q/A 解析的结构化输出。"""
    type: str = Field(description="片段类型: grammar 或 vocabulary")
    items: list[QAPairModel] = Field(description="解析出的题目列表")


# ---------------------------------------------------------------------------
# Step 1：LLM 分类 + 解析 ASR → { type, qa_pairs }（合并为 1 次调用）
# ---------------------------------------------------------------------------

_CLASSIFY_AND_PARSE_SYSTEM = """你是快反课堂 ASR 转录分类与解析助手。

## 任务
对 ASR 转录同时完成两个任务：
1. **分类**：判断片段类型（grammar 或 vocabulary）
2. **解析**：提取结构化题目列表

## 分类规则

### grammar（知识/语法快反）
以语法规则或语言结构为教学核心：
- 代词/限定词辨析：both / all / neither / either 等用法规则
- 介词固定搭配：in a hurry / on duty / by accident 等
- 后缀构词规律：-er / -or / -tion / -ity / -ment / -ness 等
- 前缀构词规律：dis- / un- / im- / ir- / re- 等
- 动词→名词转换、词性完整转换链
- 句型结构、时态、从句、语态

### vocabulary（单词快反）
以单词记忆为教学核心，搭配创意联想记忆法：
- 谐音、故事、趣味联想帮助记忆单词词义
- 老师报单词，学生说中文意思
- 典型标志：出现"提示"二字 + 创意联想故事、谐音口诀

### 核心判断原则
看教学目的，不看表面形式：
- 教加前缀/后缀的构词规律 → grammar
- 教词性转换的语法规则 → grammar
- 教前缀规律（dis-/un- 等）→ grammar
- 记住单词词义 + 联想记忆故事/谐音口诀 → vocabulary

## Q/A 解析规则

快反课堂互动规律：
- 教师逐题提问，学生尝试回答（第一次，可能不完整）
- 随后播放教师预录音频给出标准答案（第二次，答案更完整准确）
- 因此每道题的答案通常出现两次，取后一次或更完整的那次

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
- 跳过开场白、过渡语、与题目无关的内容"""


def _parse_classify_and_parse_response(parsed: dict) -> tuple[str, list[dict]]:
    """从 LLM 响应解析分类结果和 Q/A 列表。"""
    seg_type = parsed.get("type", "")
    if seg_type not in ("grammar", "vocabulary"):
        seg_type = ""
    items = parsed.get("items", [])
    qa = [
        {"question": str(item.get("question", "")).strip(),
         "answer": str(item.get("answer", "")).strip()}
        for item in items
        if isinstance(item, dict) and item.get("question")
    ]
    return seg_type, qa


def classify_and_parse(
    client: OpenAI, model: str, asr_text: str,
) -> tuple[str, list[dict], dict]:
    """
    DashScope 版：分类 + 解析合并为 1 次调用。
    返回 (seg_type, qa_pairs, usage)。
    """
    user_content = f"ASR 转录：\n{asr_text}"

    t0 = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _CLASSIFY_AND_PARSE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
        elapsed = time.monotonic() - t0
        usage = {**extract_usage(resp), "elapsed_s": round(elapsed, 2)}

        raw = resp.choices[0].message.content or ""
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            seg_type, qa = _parse_classify_and_parse_response(parsed)
            return seg_type, qa, usage
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"      [classify_and_parse 失败] {e}", file=sys.stderr)
        return "", [], {"input_tokens": 0, "output_tokens": 0, "elapsed_s": round(elapsed, 2)}
    return "", [], usage


# ---------------------------------------------------------------------------
# Step 2：题库索引 + Q/A 搜索
# ---------------------------------------------------------------------------

class QuestionBankIndex:
    def __init__(self, qb_root: Path):
        self.grammar_dir = qb_root / "grammar"
        self.vocab_dir = qb_root / "vocabulary"
        self._grammar_q_index: dict[str, list[str]] = defaultdict(list)
        self._vocab_q_index: dict[str, list[str]] = defaultdict(list)
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
        idx = self._grammar_q_index if seg_type == "grammar" else self._vocab_q_index
        counts: dict[str, int] = defaultdict(int)
        for qa in qa_pairs:
            nq = normalize(qa.get("question", ""))
            for fname in idx.get(nq, []):
                counts[fname] += 1
        return sorted(counts.items(), key=lambda x: -x[1])

    def filter_by_count(
        self, candidates: list[tuple[str, int]], n_qa: int,
        seg_type: str, tolerance: int = COUNT_TOLERANCE,
    ) -> list[tuple[str, int]]:
        result = []
        for fname, _match in candidates:
            n = len(self._grammar_entries.get(fname, []) if seg_type == "grammar"
                    else self._vocab_entries.get(fname, []))
            if abs(n - n_qa) <= tolerance:
                result.append((fname, n))
        return result

    def load_entries(self, filename: str, seg_type: str) -> list[dict]:
        if seg_type == "grammar":
            return self._grammar_entries.get(filename, [])
        return self._vocab_entries.get(filename, [])


# ---------------------------------------------------------------------------
# Step 3+4：LLM 工具调用最终判断
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_qb_file",
            "description": "读取指定题库文件的全部题目和答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "题库文件名（含 .json）"
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
            "description": "提交最终匹配的题库文件名（只调用一次）",
            "parameters": {
                "type": "object",
                "properties": {
                    "qb_file": {"type": "string", "description": "最终匹配的题库文件名"},
                    "reason": {"type": "string", "description": "一句话匹配依据"}
                },
                "required": ["qb_file", "reason"]
            }
        }
    }
]

_MATCH_SYSTEM = """你是快反课题库匹配专家。

已知：
- ASR 转录已被解析为结构化 Q/A 列表
- 候选题库文件已通过 Q/A 内容匹配和题目数量初步筛选

你的任务：
1. 查看候选列表（含各文件题数）
2. 调用 read_qb_file 查看最可能候选的完整题目
3. 与解析出的 Q/A 列表对比，确认最佳匹配
4. 调用 submit_answer 提交结果

每次只提交一个最终答案。"""


def agentic_match(
    client: OpenAI, model: str, asr_text: str,
    qa_pairs: list[dict], candidates: list[tuple[str, int]],
    seg_type: str, index: QuestionBankIndex, max_turns: int = 8,
) -> dict:
    """
    返回 {"qb_file", "reason", "tool_calls", "usage": {input_tokens, output_tokens, elapsed_s}}
    或 {"error", "usage"}
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
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    t0 = time.monotonic()

    for _ in range(max_turns):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS, temperature=0.1,
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            return {"error": str(e), "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}

        total_usage = merge_usage(total_usage, extract_usage(resp))
        msg = resp.choices[0].message

        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            elapsed = time.monotonic() - t0
            return {"error": "LLM 未调用工具就停止了",
                    "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}

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
                elapsed = time.monotonic() - t0
                return {
                    "qb_file": args.get("qb_file", ""),
                    "reason": args.get("reason", ""),
                    "tool_calls": tool_call_count,
                    "usage": {**total_usage, "elapsed_s": round(elapsed, 2)},
                }

    elapsed = time.monotonic() - t0
    return {"error": f"超过最大轮次 ({max_turns})",
            "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}


# ---------------------------------------------------------------------------
# Gemini 版 Step 1：分类 + 解析合并调用
# ---------------------------------------------------------------------------

def classify_and_parse_gemini(
    client, model: str, asr_text: str,
) -> tuple[str, list[dict], dict]:
    """Gemini 版：分类 + 解析合并为 1 次调用，使用 response_json_schema。"""
    prompt = f"""{_CLASSIFY_AND_PARSE_SYSTEM}

ASR 转录：
{asr_text}"""

    t0 = time.monotonic()
    try:
        resp = client.models.generate_content(
            model=model,
            contents=[prompt],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ClassifyAndParseResult.model_json_schema(),
                "temperature": 0.1,
            },
        )
        elapsed = time.monotonic() - t0
        usage = {**extract_gemini_usage(resp), "elapsed_s": round(elapsed, 2)}

        raw = resp.text or ""
        parsed = json.loads(raw)
        seg_type, qa = _parse_classify_and_parse_response(parsed)
        return seg_type, qa, usage
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"      [classify_and_parse_gemini 失败] {e}", file=sys.stderr)
        return "", [], {"input_tokens": 0, "output_tokens": 0, "elapsed_s": round(elapsed, 2)}


# ---------------------------------------------------------------------------
# Gemini 版 Step 3+4：多轮 function calling 匹配
# ---------------------------------------------------------------------------

def _gemini_tool_declarations():
    """构建 Gemini function calling 工具声明。"""
    from google.genai import types as gt
    return [gt.Tool(function_declarations=[
        gt.FunctionDeclaration(
            name="read_qb_file",
            description="读取指定题库文件的全部题目和答案",
            parameters=gt.Schema(
                type=gt.Type.OBJECT,
                properties={
                    "filename": gt.Schema(
                        type=gt.Type.STRING,
                        description="题库文件名（含 .json）",
                    )
                },
                required=["filename"],
            ),
        ),
        gt.FunctionDeclaration(
            name="submit_answer",
            description="提交最终匹配的题库文件名（只调用一次）",
            parameters=gt.Schema(
                type=gt.Type.OBJECT,
                properties={
                    "qb_file": gt.Schema(type=gt.Type.STRING, description="最终匹配的题库文件名"),
                    "reason": gt.Schema(type=gt.Type.STRING, description="一句话匹配依据"),
                },
                required=["qb_file", "reason"],
            ),
        ),
    ])]


def match_gemini(
    client, model: str, asr_text: str,
    qa_pairs: list[dict], candidates: list[tuple[str, int]],
    seg_type: str, index: QuestionBankIndex, max_turns: int = 8,
) -> dict:
    """
    Gemini 版多轮 function calling 匹配。
    LLM 可调用 read_qb_file 查看候选内容，最终调用 submit_answer 提交结果。
    """
    from google.genai import types as gt

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

    tools = _gemini_tool_declarations()
    contents = [
        gt.Content(role="user", parts=[gt.Part.from_text(text=_MATCH_SYSTEM + "\n\n" + user_content)]),
    ]

    tool_call_count = 0
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    t0 = time.monotonic()

    for _ in range(max_turns):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=contents,
                config={"tools": tools, "temperature": 0.1},
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            return {"error": str(e), "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}

        total_usage = merge_usage(total_usage, extract_gemini_usage(resp))
        candidate_resp = resp.candidates[0] if resp.candidates else None
        if not candidate_resp or not candidate_resp.content or not candidate_resp.content.parts:
            elapsed = time.monotonic() - t0
            return {"error": "Gemini 返回空响应",
                    "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}

        # 将模型响应追加到 contents
        contents.append(candidate_resp.content)

        # 处理 function calls
        fn_parts = [p for p in candidate_resp.content.parts if p.function_call]
        if not fn_parts:
            elapsed = time.monotonic() - t0
            return {"error": "LLM 未调用工具就停止了",
                    "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}

        tool_response_parts = []
        for part in fn_parts:
            tool_call_count += 1
            fc = part.function_call
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}

            if fn_name == "read_qb_file":
                filename = fn_args.get("filename", "")
                entries = index.load_entries(filename, seg_type)
                if entries:
                    body = "\n".join(
                        f"  Q: {e.get('question', '?')}  →  A: {e.get('answer', '?')}"
                        for e in entries
                    )
                    tool_result = f"【{filename}】共 {len(entries)} 题：\n{body}"
                else:
                    tool_result = f"文件不存在或内容为空: {filename}"
                tool_response_parts.append(
                    gt.Part.from_function_response(name=fn_name, response={"result": tool_result})
                )

            elif fn_name == "submit_answer":
                elapsed = time.monotonic() - t0
                return {
                    "qb_file": fn_args.get("qb_file", ""),
                    "reason": fn_args.get("reason", ""),
                    "tool_calls": tool_call_count,
                    "usage": {**total_usage, "elapsed_s": round(elapsed, 2)},
                }

        # 将工具响应追加到 contents
        if tool_response_parts:
            contents.append(gt.Content(role="user", parts=tool_response_parts))

    elapsed = time.monotonic() - t0
    return {"error": f"超过最大轮次 ({max_turns})",
            "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}


# ---------------------------------------------------------------------------
# 元数据读写
# ---------------------------------------------------------------------------

def load_metadata_raw(student_dir: Path) -> dict:
    """原样读取 metadata.json。"""
    f = student_dir / "metadata.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_segments(raw_meta: dict) -> dict:
    """
    从原始 metadata 提取片段信息，返回统一结构：
      {"<seg_key>": {"type": str, "qb_file": str | None}, ...}
    """
    # 新格式优先
    gt = raw_meta.get("ground_truth", {})
    if gt:
        return {
            k: {"type": v["type"], "qb_file": v.get("qb_file")}
            for k, v in gt.items()
            if isinstance(v, dict) and v.get("type")
        }
    # 旧格式
    segs = raw_meta.get("segments", {})
    return {
        f"{k}/2_qwen_asr.json": {"type": v["type"], "qb_file": None}
        for k, v in segs.items()
        if isinstance(v, dict) and v.get("type")
    }


def update_metadata(student_dir: Path, raw_meta: dict, predictions: dict, model: str, total_usage: dict):
    """
    将预测结果写回 metadata.json。
    predictions: {seg_key: {"predicted": str, ...}}
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if "ground_truth" in raw_meta:
        # 新格式：更新 ground_truth 里的 qb_file
        for seg_key, pred_info in predictions.items():
            predicted = pred_info.get("predicted")
            if predicted and seg_key in raw_meta["ground_truth"]:
                raw_meta["ground_truth"][seg_key]["qb_file"] = predicted
    else:
        # 旧格式：更新 segments 里的 qb_file
        for seg_key, pred_info in predictions.items():
            predicted = pred_info.get("predicted")
            if not predicted:
                continue
            seg_num = seg_key.split("/")[0]
            if seg_num in raw_meta.get("segments", {}):
                raw_meta["segments"][seg_num]["qb_file"] = predicted

    # 记录匹配元信息
    raw_meta["qb_matched_at"] = now_str
    raw_meta["qb_matched_by"] = model
    raw_meta["qb_match_usage"] = total_usage

    meta_path = student_dir / "metadata.json"
    meta_path.write_text(json.dumps(raw_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seg_key_to_num(seg_key: str) -> str:
    return seg_key.split("/")[0]


def build_seg_dir_map(student_dir: Path, segments: dict) -> dict[str, Path]:
    """建立 seg_num → 实际子目录路径 的映射。

    优先匹配数字目录名，若不存在则按 ground_truth 中的顺序
    映射到学生目录下的子目录（排除非目录和以 . 开头的项）。
    """
    seg_nums = sorted(segments.keys(), key=lambda k: seg_key_to_num(k))
    mapping: dict[str, Path] = {}

    # 收集所有子目录（排除隐藏和非目录）
    all_subdirs = sorted(
        (p for p in student_dir.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name,
    )

    for seg_key in seg_nums:
        seg_num = seg_key_to_num(seg_key)
        num_dir = student_dir / seg_num
        if num_dir.is_dir():
            mapping[seg_num] = num_dir
        else:
            # 数字目录不存在，尝试找包含 ASR 文件的子目录
            for subdir in all_subdirs:
                if subdir in mapping.values():
                    continue  # 已被其他 seg 占用
                for suffix in ("2_qwen_asr.json", "2_qwen_asr.txt"):
                    if (subdir / suffix).exists():
                        mapping[seg_num] = subdir
                        break
                if seg_num in mapping:
                    break

    return mapping


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="两步法匹配 ASR 片段对应的题库文件")
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

    use_gemini = is_gemini_model(args.model)
    if use_gemini:
        if not os.environ.get("GEMINI_API_KEY"):
            print("错误: 未找到 GEMINI_API_KEY", file=sys.stderr)
            return 1
    else:
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

    if use_gemini:
        gemini_client = create_gemini_client()
        client = None
    else:
        client = OpenAI(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url=DASHSCOPE_BASE_URL,
        )
        gemini_client = None

    class_dirs = sorted(p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if args.class_filter:
        class_dirs = [p for p in class_dirs if args.class_filter.lower() in p.name.lower()]

    grand_total = grand_correct = 0

    for class_dir in class_dirs:
        for student_dir in sorted(p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if args.student_filter and args.student_filter.lower() not in student_dir.name.lower():
                continue

            raw_meta = load_metadata_raw(student_dir)
            segments = load_segments(raw_meta)
            if not segments:
                continue

            out_path = student_dir / f"qb_match_{args.model}.json"
            if out_path.exists() and not args.force:
                print(f"  [跳过] {class_dir.name}/{student_dir.name}  (用 --force 重新运行)")
                continue

            print(f"\n[学生] {class_dir.name}/{student_dir.name}  ({len(segments)} 个片段)")
            seg_results = {}
            student_usage = {"input_tokens": 0, "output_tokens": 0, "elapsed_s": 0.0}
            student_t0 = time.monotonic()

            # 建立 seg_num → 实际目录 映射（处理重命名目录）
            seg_dir_map = build_seg_dir_map(student_dir, segments)

            for seg_key, gt_info in sorted(segments.items()):
                seg_num = seg_key_to_num(seg_key)
                gt_type = gt_info.get("type")
                gt_qb_file = gt_info.get("qb_file")
                has_gt = gt_qb_file is not None

                # 读取 ASR 文本（使用映射后的实际目录）
                asr_path = None
                actual_dir = seg_dir_map.get(seg_num)
                if actual_dir:
                    for suffix in ("2_qwen_asr.json", "2_qwen_asr.txt"):
                        p = actual_dir / suffix
                        if p.exists():
                            asr_path = p
                            break

                asr_text = extract_asr_text(asr_path) if asr_path else ""
                if not asr_text:
                    print(f"    片段 {seg_num}: 无 ASR 文本，跳过")
                    continue

                # Step 1: 合并调用 — 分类 + Q/A 解析（1 次 LLM）
                if use_gemini:
                    predicted_type, qa_pairs, parse_usage = classify_and_parse_gemini(
                        gemini_client, args.model, asr_text,
                    )
                else:
                    predicted_type, qa_pairs, parse_usage = classify_and_parse(
                        client, args.model, asr_text,
                    )
                seg_type = predicted_type or gt_type or "grammar"
                type_correct = (predicted_type == gt_type) if (predicted_type and gt_type) else None
                type_tag = ""
                if gt_type and predicted_type:
                    type_tag = f" 分类{'✓' if type_correct else '✗ →' + predicted_type}"
                print(f"    片段 {seg_num} [{seg_type}]{type_tag}:")

                student_usage["input_tokens"] += parse_usage.get("input_tokens", 0)
                student_usage["output_tokens"] += parse_usage.get("output_tokens", 0)
                student_usage["elapsed_s"] += parse_usage.get("elapsed_s", 0)

                print(f"      解析出 {len(qa_pairs)} 道题: "
                      + str([qa["question"][:15] + "…" for qa in qa_pairs[:3]]))

                if not qa_pairs:
                    print("      ❌ ASR 解析失败，跳过")
                    seg_results[seg_key] = {
                        "seg_type": seg_type, "predicted_type": predicted_type,
                        "type_correct": type_correct, "predicted": None,
                        "ground_truth": gt_qb_file, "correct": None,
                        "error": "ASR 解析失败",
                        "usage": parse_usage,
                    }
                    if has_gt:
                        grand_total += 1
                    continue

                # Step 2: Q/A 内容搜索题库
                search_results = index.search_by_qa(qa_pairs, seg_type)
                if has_gt:
                    gt_match_count = next((n for f, n in search_results if f == gt_qb_file), 0)
                    print(f"      Q/A 搜索命中 {len(search_results)} 个文件  "
                          f"(GT '{gt_qb_file}' 命中 {gt_match_count}/{len(qa_pairs)} 题)")
                else:
                    gt_match_count = 0
                    print(f"      Q/A 搜索命中 {len(search_results)} 个文件")

                # Step 3: 题目数量过滤
                filtered = index.filter_by_count(search_results, len(qa_pairs), seg_type, args.tolerance)
                if has_gt:
                    gt_in_filtered = any(f == gt_qb_file for f, _ in filtered)
                    print(f"      数量过滤（±{args.tolerance}）后: {len(filtered)} 个候选  "
                          f"GT {'✓' if gt_in_filtered else '✗'}")
                else:
                    gt_in_filtered = None
                    print(f"      数量过滤（±{args.tolerance}）后: {len(filtered)} 个候选")

                if not filtered:
                    print("      ⚠ 无候选通过数量过滤，使用 Q/A 搜索前 5")
                    filtered = [
                        (fname, len(index.load_entries(fname, seg_type)))
                        for fname, _ in search_results[:5]
                    ]

                # Step 4: LLM 最终判断
                if use_gemini:
                    result = match_gemini(
                        gemini_client, args.model, asr_text, qa_pairs,
                        filtered, seg_type, index,
                    )
                else:
                    result = agentic_match(
                        client, args.model, asr_text, qa_pairs,
                        filtered, seg_type, index,
                    )
                match_usage = result.get("usage", {})
                student_usage["input_tokens"] += match_usage.get("input_tokens", 0)
                student_usage["output_tokens"] += match_usage.get("output_tokens", 0)
                student_usage["elapsed_s"] += match_usage.get("elapsed_s", 0)

                seg_usage = merge_usage(parse_usage, match_usage)
                seg_usage["elapsed_s"] = round(
                    parse_usage.get("elapsed_s", 0) + match_usage.get("elapsed_s", 0), 2
                )

                if "error" in result:
                    print(f"      ❌ {result['error']}")
                    seg_results[seg_key] = {
                        "seg_type": seg_type, "predicted_type": predicted_type,
                        "type_correct": type_correct, "predicted": None,
                        "ground_truth": gt_qb_file, "correct": None,
                        "gt_in_filtered_candidates": gt_in_filtered,
                        "parsed_qa_count": len(qa_pairs),
                        "error": result["error"],
                        "usage": seg_usage,
                    }
                    if has_gt:
                        grand_total += 1
                    continue

                predicted = result["qb_file"]
                is_correct = (predicted == gt_qb_file) if has_gt else None
                if has_gt:
                    print(f"      {'✓' if is_correct else '✗'} 预测: {predicted}  "
                          f"[{result.get('tool_calls', 0)} 次工具调用]")
                else:
                    print(f"      → 预测: {predicted}  "
                          f"[{result.get('tool_calls', 0)} 次工具调用]")
                print(f"        理由: {result.get('reason', '')[:80]}")

                seg_results[seg_key] = {
                    "seg_type": seg_type,
                    "predicted_type": predicted_type,
                    "type_correct": type_correct,
                    "predicted": predicted,
                    "ground_truth": gt_qb_file,
                    "correct": is_correct,
                    "gt_in_filtered_candidates": gt_in_filtered,
                    "parsed_qa_count": len(qa_pairs),
                    "gt_search_match_count": gt_match_count if has_gt else None,
                    "reason": result.get("reason", ""),
                    "tool_calls": result.get("tool_calls", 0),
                    "parsed_qa": qa_pairs,
                    "usage": seg_usage,
                }
                if has_gt:
                    grand_total += 1
                    if is_correct:
                        grand_correct += 1

            # 汇总该学生用量
            student_usage["elapsed_s"] = round(time.monotonic() - student_t0, 2)
            total_tokens = student_usage["input_tokens"] + student_usage["output_tokens"]

            # 更新 metadata.json
            update_metadata(student_dir, raw_meta, seg_results, args.model, student_usage)

            # 写详细结果
            evaluated = [v for v in seg_results.values() if v.get("correct") is not None]
            correct = sum(1 for v in evaluated if v["correct"])
            total_eval = len(evaluated)
            total_pred = len(seg_results)
            accuracy = correct / total_eval if total_eval > 0 else None
            out_path.write_text(
                json.dumps({
                    "class": class_dir.name, "student": student_dir.name,
                    "model": args.model,
                    "accuracy": round(accuracy, 4) if accuracy is not None else None,
                    "evaluated": total_eval, "predicted": total_pred,
                    "usage": student_usage,
                    "segments": seg_results,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if total_eval > 0:
                print(f"  → 准确率 {accuracy:.1%} ({correct}/{total_eval})  "
                      f"tokens={total_tokens}  耗时={student_usage['elapsed_s']}s")
            else:
                print(f"  → 预测 {total_pred} 个片段  "
                      f"tokens={total_tokens}  耗时={student_usage['elapsed_s']}s")
            print(f"    metadata.json 已更新")

    if grand_total > 0:
        print(f"\n[汇总] qb_file 匹配准确率: {grand_correct/grand_total:.1%}  ({grand_correct}/{grand_total})")
    else:
        print("\n[汇总] 预测完成（无 GT 可评估）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
