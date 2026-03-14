# -*- coding: utf-8 -*-
"""
shared.py - ASR 分类 + 题库匹配 Pipeline 共享基础设施

从 classify_asr_type.py 和 match_qb_file.py 提取的公共代码。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# 路径设置：确保 project root 和 scripts 目录均在 sys.path 中
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parents[3]  # .claude/skills/asr-qb-pipeline/scripts → project root
for _p in [str(_SCRIPTS_DIR), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.common.gemini import is_gemini_model, create_gemini_client, extract_gemini_usage  # noqa: E402

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VALID_TYPES = ("grammar", "vocabulary")
COUNT_TOLERANCE = 3


# ---------------------------------------------------------------------------
# .env 加载
# ---------------------------------------------------------------------------

def load_env(env_file: Optional[str] = None) -> None:
    """加载 .env 文件中的环境变量（不覆盖已有值）。"""
    candidates = [Path(env_file)] if env_file else []
    # 从 project root 及 scripts/ 目录查找
    for parent in [_PROJECT_ROOT / "scripts", _PROJECT_ROOT]:
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
# 客户端初始化
# ---------------------------------------------------------------------------

def setup_clients(model: str) -> Tuple:
    """
    统一初始化 API 客户端。

    Returns:
        (client, gemini_client, use_gemini)
        - Gemini 模型: (None, gemini_client, True)
        - DashScope 模型: (openai_client, None, False)
    """
    from openai import OpenAI

    use_gemini = is_gemini_model(model)
    if use_gemini:
        if not os.environ.get("GEMINI_API_KEY"):
            print("错误: 未找到 GEMINI_API_KEY", file=sys.stderr)
            sys.exit(1)
        return None, create_gemini_client(), True
    else:
        if not os.environ.get("DASHSCOPE_API_KEY"):
            print("错误: 未找到 DASHSCOPE_API_KEY", file=sys.stderr)
            sys.exit(1)
        client = OpenAI(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url=DASHSCOPE_BASE_URL,
        )
        return client, None, False


# ---------------------------------------------------------------------------
# 排序 & 文件查找
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


# ---------------------------------------------------------------------------
# ASR 文本提取
# ---------------------------------------------------------------------------

def read_asr_text(asr_path: Optional[Path]) -> str:
    """
    读取 ASR 文件并提取纯文本。
    支持 .txt（直接返回）和 .json（解析 Qwen ASR 格式）。
    """
    if asr_path is None:
        return ""
    try:
        raw = asr_path.read_text(encoding="utf-8").strip()
        if asr_path.suffix == ".json":
            data = json.loads(raw)
            if isinstance(data, dict):
                # 优先走 scripts.common.asr 的解析逻辑
                from scripts.common.asr import extract_qwen_asr_text
                result = extract_qwen_asr_text(data)
                if result:
                    return result
                # 回退：简单字段
                return (data.get("text") or data.get("transcript") or "").strip()
            if isinstance(data, list):
                return " ".join(
                    x.get("text", "") for x in data if isinstance(x, dict)
                ).strip()
        return raw
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# metadata 处理
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
    gt = raw_meta.get("ground_truth", {})
    if gt:
        return {
            k: {"type": v["type"], "qb_file": v.get("qb_file")}
            for k, v in gt.items()
            if isinstance(v, dict) and v.get("type")
        }
    segs = raw_meta.get("segments", {})
    return {
        f"{k}/2_qwen_asr.json": {"type": v["type"], "qb_file": None}
        for k, v in segs.items()
        if isinstance(v, dict) and v.get("type")
    }


def load_metadata_types(student_dir: Path) -> Dict[str, str]:
    """
    返回 {片段号: 类型} —— 用于分类的 ground truth 对比。
    classify.py 使用。
    """
    raw = load_metadata_raw(student_dir)
    gt = raw.get("ground_truth", {})
    if gt:
        return {
            str(k).split("/")[0]: v["type"]
            for k, v in gt.items()
            if isinstance(v, dict) and v.get("type") in VALID_TYPES
        }
    return {
        str(k): v["type"]
        for k, v in raw.get("segments", {}).items()
        if isinstance(v, dict) and v.get("type") in VALID_TYPES
    }


# ---------------------------------------------------------------------------
# 目录遍历
# ---------------------------------------------------------------------------

def iter_class_dirs(input_root: Path, class_filter: Optional[str] = None):
    """遍历班级目录，支持子串过滤。"""
    dirs = sorted(
        p for p in input_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if class_filter:
        dirs = [p for p in dirs if class_filter.lower() in p.name.lower()]
    return dirs


def iter_student_dirs(class_dir: Path, student_filter: Optional[str] = None):
    """遍历学生目录，支持子串过滤。"""
    dirs = sorted(
        p for p in class_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if student_filter:
        dirs = [p for p in dirs if student_filter.lower() in p.name.lower()]
    return dirs


# ---------------------------------------------------------------------------
# 文本规范化
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """去掉首尾空白和末尾标点，英文小写。"""
    text = text.strip()
    text = re.sub(r"[\s？。，、\?,\.!！]+$", "", text).strip()
    return re.sub(r"[a-zA-Z]+", lambda m: m.group().lower(), text)


# ---------------------------------------------------------------------------
# Token 用量跟踪
# ---------------------------------------------------------------------------

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


def seg_key_to_num(seg_key: str) -> str:
    """从 seg_key（如 '2/2_qwen_asr.json'）提取片段编号。"""
    return seg_key.split("/")[0]
