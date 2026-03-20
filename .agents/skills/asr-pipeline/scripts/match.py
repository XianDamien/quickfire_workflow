# -*- coding: utf-8 -*-
"""
match.py - 两步法匹配 ASR 片段对应的具体题库文件

流程（每个片段，2 次 LLM 调用）：
  1. LLM 分类 + 解析合并调用：判断 grammar/vocabulary 并解析为 [{question, answer}, ...]
  2. 用 Q/A 内容搜索题库索引（精确匹配 question 字段）+ 题目数量过滤
  3. LLM 通过 function calling 阅读候选内容，提交最终匹配

输出：
  - 更新 metadata.json：写入 qb_file + 用量统计
  - 详细结果：qb_match_<model>.json
"""

import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 路径 bootstrap（确保 shared 模块可被导入）
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in [str(_SCRIPTS_DIR), str(_SCRIPTS_DIR.parents[3])]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from openai import OpenAI
from pydantic import BaseModel, Field

from shared import (  # noqa: E402
    COUNT_TOLERANCE,
    DASHSCOPE_BASE_URL,
    _PROJECT_ROOT,
    build_seg_dir_map,
    extract_usage,
    format_class_stage_context,
    grammar_qb_in_stage,
    get_class_display_name,
    iter_class_dirs,
    iter_student_dirs,
    infer_class_stage,
    load_metadata_raw,
    load_segments,
    merge_usage,
    normalize,
    read_asr_text,
    seg_key_to_num,
    setup_clients,
)
from scripts.common.gemini import extract_gemini_usage  # noqa: E402


# ---------------------------------------------------------------------------
# Pydantic 模型 — 结构化输出
# ---------------------------------------------------------------------------

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
    client: OpenAI, model: str, asr_text: str, stage_info: Optional[dict] = None,
) -> tuple[str, list[dict], dict]:
    """
    DashScope 版：分类 + 解析合并为 1 次调用。
    返回 (seg_type, qa_pairs, usage)。
    """
    stage_hint = format_class_stage_context(stage_info)
    user_content = (
        f"班级阶段参考：{stage_hint}。这只是弱先验，只在转写内容模糊时参考；若和转写冲突，以转写内容为准。\n\n"
        if stage_hint else ""
    ) + f"ASR 转录：\n{asr_text}"

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


def classify_and_parse_gemini(
    client, model: str, asr_text: str, stage_info: Optional[dict] = None,
) -> tuple[str, list[dict], dict]:
    """Gemini 版：分类 + 解析合并为 1 次调用，使用 response_json_schema。"""
    stage_hint = format_class_stage_context(stage_info)
    prompt = f"""{_CLASSIFY_AND_PARSE_SYSTEM}

{"班级阶段参考：" + stage_hint + "。这只是弱先验，只在转写内容模糊时参考；若和转写冲突，以转写内容为准。\n" if stage_hint else ""}

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
# Step 2：题库索引 + Q/A 搜索
# ---------------------------------------------------------------------------

class QuestionBankIndex:
    def __init__(self, qb_root: Path):
        self.grammar_dir = qb_root / "grammar"
        self.vocab_dir = qb_root / "vocabulary"
        self._grammar_cache: dict[str, tuple[dict[str, list[str]], dict[str, list[dict]]]] = {}
        self._vocab_cache: tuple[dict[str, list[str]], dict[str, list[dict]]] | None = None

    def _build_index_store(self, files: list[Path], label: str) -> tuple[dict[str, list[str]], dict[str, list[dict]]]:
        print(f"  [索引] 加载 {label} 题库...", end="", flush=True)
        q_index: dict[str, list[str]] = defaultdict(list)
        entries_map: dict[str, list[dict]] = {}
        for f in files:
            try:
                entries = json.loads(f.read_text(encoding="utf-8"))
                entries_map[f.name] = entries
                for entry in entries:
                    nq = normalize(entry.get("question", ""))
                    if nq:
                        q_index[nq].append(f.name)
            except Exception:
                continue
        print(f" {len(entries_map)} 个文件")
        return q_index, entries_map

    def _grammar_cache_key(self, stage_info: Optional[dict]) -> str:
        if stage_info and stage_info.get("code"):
            return str(stage_info["code"])
        return "ALL"

    def _ensure_grammar_loaded(self, stage_info: Optional[dict]) -> tuple[dict[str, list[str]], dict[str, list[dict]]]:
        cache_key = self._grammar_cache_key(stage_info)
        if cache_key in self._grammar_cache:
            return self._grammar_cache[cache_key]

        files = sorted(self.grammar_dir.glob("*.json"))
        if stage_info:
            files = [f for f in files if grammar_qb_in_stage(f.name, stage_info)]
        label = f"grammar[{cache_key}]"
        self._grammar_cache[cache_key] = self._build_index_store(files, label)
        return self._grammar_cache[cache_key]

    def _ensure_vocab_loaded(self) -> tuple[dict[str, list[str]], dict[str, list[dict]]]:
        if self._vocab_cache is None:
            files = sorted(self.vocab_dir.glob("*.json"))
            self._vocab_cache = self._build_index_store(files, "vocabulary")
        return self._vocab_cache

    def search_by_qa(
        self, qa_pairs: list[dict], seg_type: str, stage_info: Optional[dict] = None,
    ) -> list[tuple[str, int]]:
        if seg_type == "grammar":
            idx, _entries = self._ensure_grammar_loaded(stage_info)
        else:
            idx, _entries = self._ensure_vocab_loaded()
        counts: dict[str, int] = defaultdict(int)
        for qa in qa_pairs:
            nq = normalize(qa.get("question", ""))
            for fname in idx.get(nq, []):
                counts[fname] += 1
        return sorted(counts.items(), key=lambda x: -x[1])

    def filter_by_count(
        self, candidates: list[tuple[str, int]], n_qa: int,
        seg_type: str, tolerance: int = COUNT_TOLERANCE, stage_info: Optional[dict] = None,
    ) -> list[tuple[str, int]]:
        if seg_type == "grammar":
            _idx, entries_map = self._ensure_grammar_loaded(stage_info)
        else:
            _idx, entries_map = self._ensure_vocab_loaded()
        result = []
        for fname, _match in candidates:
            n = len(entries_map.get(fname, []))
            if abs(n - n_qa) <= tolerance:
                result.append((fname, n))
        return result

    def filter_by_stage(
        self, candidates: list[tuple[str, int]], seg_type: str, stage_info: Optional[dict],
    ) -> list[tuple[str, int]]:
        if seg_type != "grammar" or not stage_info:
            return list(candidates)
        return [
            (fname, n) for fname, n in candidates
            if grammar_qb_in_stage(fname, stage_info)
        ]

    def load_entries(
        self, filename: str, seg_type: str, stage_info: Optional[dict] = None,
    ) -> list[dict]:
        if seg_type == "grammar":
            _idx, entries_map = self._ensure_grammar_loaded(stage_info)
            return entries_map.get(filename, [])
        _idx, entries_map = self._ensure_vocab_loaded()
        return entries_map.get(filename, [])


# ---------------------------------------------------------------------------
# Step 3+4：LLM 工具调用最终判断 — DashScope
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
    seg_type: str, index: QuestionBankIndex, stage_info: Optional[dict] = None,
    max_turns: int = 8,
) -> dict:
    """
    DashScope 版多轮 function calling 匹配。
    返回 {"qb_file", "reason", "tool_calls", "usage"} 或 {"error", "usage"}
    """
    qa_text = "\n".join(
        f"  {i+1}. Q: {qa['question']}  →  A: {qa['answer']}"
        for i, qa in enumerate(qa_pairs)
    )
    candidate_lines = "\n".join(
        f"  {i+1}. {fname}（共 {n} 题）"
        for i, (fname, n) in enumerate(candidates)
    )
    stage_hint = format_class_stage_context(stage_info)
    stage_block = (
        f"【班级阶段参考】{stage_hint}（仅作弱先验，若与转写或候选内容冲突，以内容本身为准）\n\n"
        if stage_hint else ""
    )
    user_content = f"""{stage_block}【已解析的 Q/A 列表（共 {len(qa_pairs)} 题）】
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
                entries = index.load_entries(filename, seg_type, stage_info=stage_info)
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
# Step 3+4：Gemini 版多轮 function calling 匹配
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
    seg_type: str, index: QuestionBankIndex, stage_info: Optional[dict] = None,
    max_turns: int = 8,
) -> dict:
    """
    Gemini 版多轮 function calling 匹配。
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
    stage_hint = format_class_stage_context(stage_info)
    stage_block = (
        f"【班级阶段参考】{stage_hint}（仅作弱先验，若与转写或候选内容冲突，以内容本身为准）\n\n"
        if stage_hint else ""
    )
    user_content = f"""{stage_block}【已解析的 Q/A 列表（共 {len(qa_pairs)} 题）】
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

        contents.append(candidate_resp.content)

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
                entries = index.load_entries(filename, seg_type, stage_info=stage_info)
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

        if tool_response_parts:
            contents.append(gt.Content(role="user", parts=tool_response_parts))

    elapsed = time.monotonic() - t0
    return {"error": f"超过最大轮次 ({max_turns})",
            "usage": {**total_usage, "elapsed_s": round(elapsed, 2)}}


# ---------------------------------------------------------------------------
# 元数据回写
# ---------------------------------------------------------------------------

def update_metadata(
    student_dir: Path,
    raw_meta: dict,
    predictions: dict,
    model: str,
    total_usage: dict,
    stage_info: Optional[dict] = None,
):
    """将预测结果写回 metadata.json。"""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if "ground_truth" in raw_meta:
        for seg_key, pred_info in predictions.items():
            predicted = pred_info.get("predicted")
            if predicted and seg_key in raw_meta["ground_truth"]:
                raw_meta["ground_truth"][seg_key]["qb_file"] = predicted
    else:
        for seg_key, pred_info in predictions.items():
            predicted = pred_info.get("predicted")
            if not predicted:
                continue
            seg_num = seg_key.split("/")[0]
            if seg_num in raw_meta.get("segments", {}):
                raw_meta["segments"][seg_num]["qb_file"] = predicted

    raw_meta["qb_matched_at"] = now_str
    raw_meta["qb_matched_by"] = model
    raw_meta["qb_match_usage"] = total_usage
    if stage_info:
        raw_meta.setdefault("class_stage_code", stage_info.get("code"))
        raw_meta.setdefault("class_stage_label", stage_info.get("label"))
        raw_meta.setdefault("class_stage_range", stage_info.get("range"))

    meta_path = student_dir / "metadata.json"
    meta_path.write_text(json.dumps(raw_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 子命令入口
# ---------------------------------------------------------------------------

def run_match(args) -> int:
    """匹配子命令主逻辑。"""
    client, gemini_client, use_gemini = setup_clients(args.model)

    input_root = Path(args.input_root).resolve()
    qb_root = Path(args.qb_root).resolve()
    for p, name in [(input_root, "input_root"), (qb_root, "qb_root")]:
        if not p.exists():
            print(f"错误: {name} 不存在: {p}", file=sys.stderr)
            return 1

    print("[初始化] 准备题库索引（按需加载）...")
    index = QuestionBankIndex(qb_root)

    class_dirs = iter_class_dirs(input_root, args.class_filter)

    grand_total = grand_correct = 0

    for class_dir in class_dirs:
        class_name = get_class_display_name(class_dir, input_root)
        for student_dir in iter_student_dirs(class_dir, args.student_filter):
            raw_meta = load_metadata_raw(student_dir)
            segments = load_segments(raw_meta)
            if not segments:
                continue

            out_path = student_dir / f"qb_match_{args.model}.json"
            if out_path.exists() and not args.force:
                print(f"  [跳过] {class_name}/{student_dir.name}  (用 --force 重新运行)")
                continue

            print(f"\n[学生] {class_name}/{student_dir.name}  ({len(segments)} 个片段)")
            seg_results = {}
            student_usage = {"input_tokens": 0, "output_tokens": 0, "elapsed_s": 0.0}
            student_t0 = time.monotonic()
            stage_info = infer_class_stage(raw_meta, student_dir)
            seg_dir_map = build_seg_dir_map(student_dir, segments)
            if stage_info:
                print(f"  [阶段] {format_class_stage_context(stage_info)}")

            for seg_key, gt_info in sorted(segments.items()):
                seg_num = seg_key_to_num(seg_key)
                gt_type = gt_info.get("type")
                gt_qb_file = gt_info.get("qb_file")
                has_gt = gt_qb_file is not None

                # 读取 ASR 文本
                asr_path = None
                actual_dir = seg_dir_map.get(seg_num)
                if actual_dir:
                    for suffix in ("2_qwen_asr.txt", "2_qwen_asr.json"):
                        p = actual_dir / suffix
                        if p.exists():
                            asr_path = p
                            break

                asr_text = read_asr_text(asr_path) if asr_path else ""
                if not asr_text:
                    print(f"    片段 {seg_num}: 无 ASR 文本，跳过")
                    continue

                # Step 1: 合并调用 — 分类 + Q/A 解析（1 次 LLM）
                if use_gemini:
                    predicted_type, qa_pairs, parse_usage = classify_and_parse_gemini(
                        gemini_client, args.model, asr_text, stage_info=stage_info,
                    )
                else:
                    predicted_type, qa_pairs, parse_usage = classify_and_parse(
                        client, args.model, asr_text, stage_info=stage_info,
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
                search_results = index.search_by_qa(qa_pairs, seg_type, stage_info=stage_info)
                if has_gt:
                    gt_match_count = next((n for f, n in search_results if f == gt_qb_file), 0)
                    print(f"      Q/A 搜索命中 {len(search_results)} 个文件  "
                          f"(GT '{gt_qb_file}' 命中 {gt_match_count}/{len(qa_pairs)} 题)")
                else:
                    gt_match_count = 0
                    print(f"      Q/A 搜索命中 {len(search_results)} 个文件")

                # Step 3: 题目数量过滤
                tolerance = getattr(args, 'tolerance', COUNT_TOLERANCE)
                filtered = index.filter_by_count(
                    search_results, len(qa_pairs), seg_type, tolerance, stage_info=stage_info,
                )
                filtered = index.filter_by_stage(filtered, seg_type, stage_info)
                if has_gt:
                    gt_in_filtered = any(f == gt_qb_file for f, _ in filtered)
                    print(f"      数量过滤（±{tolerance}）后: {len(filtered)} 个候选  "
                          f"GT {'✓' if gt_in_filtered else '✗'}")
                else:
                    gt_in_filtered = None
                    print(f"      数量过滤（±{tolerance}）后: {len(filtered)} 个候选")

                if not filtered:
                    print("      ⚠ 无候选通过数量过滤，使用 Q/A 搜索前 5")
                    filtered = [
                        (fname, len(index.load_entries(fname, seg_type, stage_info=stage_info)))
                        for fname, _ in search_results[:5]
                    ]

                stage_filtered = index.filter_by_stage(filtered, seg_type, stage_info)
                if seg_type == "grammar" and stage_info:
                    if stage_filtered:
                        filtered = stage_filtered
                        print(
                            f"      阶段过滤（{stage_info['code']} / {stage_info['range']}）后: "
                            f"{len(filtered)} 个候选"
                        )
                    else:
                        print(
                            f"      ⚠ 阶段过滤（{stage_info['code']} / {stage_info['range']}）后无候选，"
                            "回退到未做阶段过滤的候选"
                        )

                if not filtered:
                    print("      ❌ 题库候选为空，跳过")
                    seg_results[seg_key] = {
                        "seg_type": seg_type,
                        "predicted_type": predicted_type,
                        "type_correct": type_correct,
                        "predicted": None,
                        "ground_truth": gt_qb_file,
                        "correct": None,
                        "gt_in_filtered_candidates": gt_in_filtered,
                        "parsed_qa_count": len(qa_pairs),
                        "stage_info": stage_info,
                        "error": "题库候选为空",
                        "usage": parse_usage,
                    }
                    if has_gt:
                        grand_total += 1
                    continue

                # Step 4: LLM 最终判断
                if use_gemini:
                    result = match_gemini(
                        gemini_client, args.model, asr_text, qa_pairs,
                        filtered, seg_type, index, stage_info=stage_info,
                    )
                else:
                    result = agentic_match(
                        client, args.model, asr_text, qa_pairs,
                        filtered, seg_type, index, stage_info=stage_info,
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
                        "stage_info": stage_info,
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
                    "stage_info": stage_info,
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

            if getattr(args, "eval_only", False):
                print("    metadata.json 未改写（--eval-only）")
            else:
                update_metadata(
                    student_dir,
                    raw_meta,
                    seg_results,
                    args.model,
                    student_usage,
                    stage_info=stage_info,
                )

            # 写详细结果
            evaluated = [v for v in seg_results.values() if v.get("correct") is not None]
            correct = sum(1 for v in evaluated if v["correct"])
            total_eval = len(evaluated)
            total_pred = len(seg_results)
            accuracy = correct / total_eval if total_eval > 0 else None
            out_path.write_text(
                json.dumps({
                    "class": class_name, "student": student_dir.name,
                    "model": args.model,
                    "stage_info": stage_info,
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
            if not getattr(args, "eval_only", False):
                print(f"    metadata.json 已更新")

    if grand_total > 0:
        print(f"\n[汇总] qb_file 匹配准确率: {grand_correct/grand_total:.1%}  ({grand_correct}/{grand_total})")
    else:
        print("\n[汇总] 预测完成（无 GT 可评估）")

    return 0
