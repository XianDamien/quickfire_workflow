#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py - ASR 分类 + 题库匹配统一入口

子命令：
  classify  — 分类片段类型（grammar/vocabulary）
  match     — 匹配具体题库文件
  all       — 顺序执行 classify → match

用法：
  uv run python .agents/skills/asr-pipeline/scripts/pipeline.py classify --class X --student Y
  uv run python .agents/skills/asr-pipeline/scripts/pipeline.py match --class X --student Y
  uv run python .agents/skills/asr-pipeline/scripts/pipeline.py all --class X --student Y
"""

import argparse
import sys
from pathlib import Path

# 路径 bootstrap
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parents[3]
for _p in [str(_SCRIPTS_DIR), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="ASR 片段分类 + 题库匹配 Pipeline",
    )

    # 共享参数（parent parser）
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--input-root", default="two_output",
                        help="ASR 输出根目录（默认 two_output，递归发现班级目录）")
    parent.add_argument("--class", dest="class_filter",
                        help="班级名称过滤（子串匹配；支持 R1/<class>、R2/<class>、130/<class> 相对路径）")
    parent.add_argument("--student", dest="student_filter",
                        help="学生名称过滤（子串匹配）")
    parent.add_argument("--model", default="gemini-3.1-flash-lite-preview",
                        help="LLM 模型（默认 gemini-3.1-flash-lite-preview）")
    parent.add_argument("--force", action="store_true",
                        help="覆盖已有结果")

    sub = parser.add_subparsers(dest="command", required=True)

    # classify 子命令
    p_classify = sub.add_parser("classify", parents=[parent],
                                help="分类片段类型（grammar/vocabulary）")
    p_classify.add_argument("--temperature", type=float, default=0.1,
                            help="模型温度（默认 0.1）")

    # match 子命令
    p_match = sub.add_parser("match", parents=[parent],
                             help="匹配具体题库文件")
    p_match.add_argument("--qb-root", default="questionbank",
                         help="题库根目录（默认 questionbank）")
    p_match.add_argument("--tolerance", type=int, default=3,
                         help="题目数量过滤允许偏差（默认 ±3）")
    p_match.add_argument("--eval-only", action="store_true",
                         help="仅评估输出，不回写 metadata.json")

    # all 子命令
    p_all = sub.add_parser("all", parents=[parent],
                           help="顺序执行 classify → match")
    p_all.add_argument("--temperature", type=float, default=0.1,
                       help="分类模型温度（默认 0.1）")
    p_all.add_argument("--qb-root", default="questionbank",
                       help="题库根目录（默认 questionbank）")
    p_all.add_argument("--tolerance", type=int, default=3,
                       help="题目数量过滤允许偏差（默认 ±3）")
    p_all.add_argument("--eval-only", action="store_true",
                       help="仅评估输出，不回写 metadata.json")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 加载环境变量（所有子命令共用）
    from shared import load_env  # noqa: E402
    load_env()

    if args.command == "classify":
        from classify import run_classify  # noqa: E402
        return run_classify(args)

    elif args.command == "match":
        from match import run_match  # noqa: E402
        return run_match(args)

    elif args.command == "all":
        print("=" * 60)
        print("[Pipeline] 分类 + 匹配（合并流程，2 次 LLM 调用/片段）")
        print("=" * 60)
        print("  分类已合并到匹配步骤中，无需单独运行 classify。\n")
        from match import run_match  # noqa: E402
        return run_match(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
