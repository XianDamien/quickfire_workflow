# -*- coding: utf-8 -*-
"""
shared.py - ASR 分类 + 题库匹配 Pipeline 共享基础设施

从 classify.py 和 match.py 提取的公共代码。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# 路径设置：确保 project root 和 scripts 目录均在 sys.path 中
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parents[3]  # .agents/skills/asr-pipeline/scripts → project root
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
CLASS_STAGE_RULES = (
    {"code": "R1", "label": "小学阶段", "range": "R001-R047", "start": 1, "end": 47},
    {"code": "R2", "label": "小初衔接", "range": "R060-R102", "start": 60, "end": 102},
    {"code": "R3", "label": "初中阶段", "range": "R120-R150", "start": 120, "end": 150},
)


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


def build_seg_dir_map(student_dir: Path, segments: dict) -> dict[str, Path]:
    """建立 seg_num → 实际子目录路径 的映射。

    优先级：
    1. 数字目录名（如 `2/`）
    2. 与 metadata.qb_file 同名的目录（去掉 `.json`）
    3. 学生目录下按名称排序的其余 ASR 子目录
    """
    seg_keys = sorted(segments.keys(), key=lambda k: seg_key_to_num(k))
    mapping: dict[str, Path] = {}
    used_dirs: set[Path] = set()

    all_subdirs = sorted(
        (
            p for p in student_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".") and find_asr_file(p)
        ),
        key=lambda p: p.name,
    )

    for seg_key in seg_keys:
        seg_num = seg_key_to_num(seg_key)
        seg_info = segments.get(seg_key, {}) if isinstance(segments, dict) else {}
        preferred_dirs: list[Path] = []

        num_dir = student_dir / seg_num
        if num_dir.is_dir() and find_asr_file(num_dir):
            preferred_dirs.append(num_dir)

        qb_file = seg_info.get("qb_file") if isinstance(seg_info, dict) else None
        if qb_file:
            qb_dir = student_dir / Path(qb_file).stem
            if qb_dir.is_dir() and find_asr_file(qb_dir):
                preferred_dirs.append(qb_dir)

        for candidate in preferred_dirs:
            if candidate not in used_dirs:
                mapping[seg_num] = candidate
                used_dirs.add(candidate)
                break

        if seg_num in mapping:
            continue

        for subdir in all_subdirs:
            if subdir in used_dirs:
                continue
            mapping[seg_num] = subdir
            used_dirs.add(subdir)
            break

    return mapping


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
        f"{k}/2_qwen_asr.json": {"type": v["type"], "qb_file": v.get("qb_file")}
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


def infer_class_stage(raw_meta: dict, student_dir: Optional[Path] = None) -> Optional[dict]:
    """从 metadata 或目录名中推断班级阶段（R1/R2/R3）。"""
    explicit_code = raw_meta.get("class_stage_code")
    explicit_label = raw_meta.get("class_stage_label")
    explicit_range = raw_meta.get("class_stage_range")
    if explicit_code:
        for rule in CLASS_STAGE_RULES:
            if rule["code"] != explicit_code:
                continue
            return {
                "code": explicit_code,
                "label": explicit_label or rule["label"],
                "range": explicit_range or rule["range"],
            }

    candidates: list[str] = []

    for section_name in ("ground_truth", "segments"):
        section = raw_meta.get(section_name, {})
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, dict) and value.get("qb_file"):
                    candidates.append(str(value["qb_file"]))

    if student_dir is not None:
        candidates.extend(
            p.name for p in student_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
        for parent in student_dir.parents:
            if re.fullmatch(r"\d{3}", parent.name):
                candidates.append(parent.name)

    matched_rules: dict[str, dict] = {}
    for item in candidates:
        match = re.search(r"\bR(\d{3})\b", Path(item).stem)
        if match:
            r_number = int(match.group(1))
        elif re.fullmatch(r"\d{3}", item):
            r_number = int(item)
        else:
            continue
        for rule in CLASS_STAGE_RULES:
            if rule["start"] <= r_number <= rule["end"]:
                matched_rules[rule["code"]] = {
                    "code": rule["code"],
                    "label": rule["label"],
                    "range": rule["range"],
                }
                break

    if len(matched_rules) == 1:
        return next(iter(matched_rules.values()))
    return None


def format_class_stage_context(stage_info: Optional[dict]) -> str:
    """将班级阶段信息格式化为可注入提示词的短文本。"""
    if not stage_info:
        return ""
    return f"{stage_info['code']}（{stage_info['label']}，编号范围 {stage_info['range']}）"


def grammar_qb_in_stage(filename: str, stage_info: Optional[dict]) -> bool:
    """判断 grammar 题库文件是否属于指定阶段范围。"""
    if not stage_info:
        return True
    match = re.match(r"^R(\d{3})\b", Path(filename).stem)
    if not match:
        return True
    r_number = int(match.group(1))
    for rule in CLASS_STAGE_RULES:
        if rule["code"] != stage_info.get("code"):
            continue
        return rule["start"] <= r_number <= rule["end"]
    return True


def get_class_display_name(class_dir: Path, input_root: Optional[Path] = None) -> str:
    """返回班级显示名；若在分桶目录下则保留相对路径。"""
    if input_root:
        try:
            return class_dir.relative_to(input_root).as_posix()
        except ValueError:
            pass
    return class_dir.name


# ---------------------------------------------------------------------------
# 目录遍历
# ---------------------------------------------------------------------------

def iter_class_dirs(input_root: Path, class_filter: Optional[str] = None):
    """递归遍历真实班级目录，兼容平铺和上一级分桶目录。"""
    dirs = sorted(
        {
            meta_path.parent.parent
            for meta_path in input_root.rglob("metadata.json")
            if len(meta_path.relative_to(input_root).parts) >= 3
        },
        key=lambda p: get_class_display_name(p, input_root).lower(),
    )
    if class_filter:
        needle = class_filter.lower()
        dirs = [
            p for p in dirs
            if needle in get_class_display_name(p, input_root).lower()
        ]
    return dirs


def iter_student_dirs(class_dir: Path, student_filter: Optional[str] = None):
    """遍历学生目录，要求目录下存在 metadata.json。"""
    dirs = sorted(
        p for p in class_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "metadata.json").exists()
    )
    if student_filter:
        dirs = [p for p in dirs if student_filter.lower() in p.name.lower()]
    return dirs


# ---------------------------------------------------------------------------
# 文本规范化
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """删除空白和标点，只保留中英文与数字，英文转小写。"""
    text = text.strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


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
