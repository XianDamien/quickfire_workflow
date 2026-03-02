#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_qwen_omni.py - Qwen3-Omni 兼容测试入口

说明:
- 推荐统一使用 scripts/main.py 进行 sync 测试。
- 本脚本保留为兼容壳，会转调 main.py。

示例:
    uv run python test_qwen_omni.py --archive-batch Zoe61330_2025-12-15 --student Allen
"""

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen3-Omni 兼容测试入口（转调 scripts/main.py）")
    parser.add_argument("--archive-batch", "-b", required=True, help="Archive 批次 ID")
    parser.add_argument("--student", "-s", required=True, help="学生名称")
    parser.add_argument("--dry-run", "-n", action="store_true", help="只打印将执行的命令")
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "scripts/main.py",
        "--archive-batch",
        args.archive_batch,
        "--student",
        args.student,
        "--annotator",
        "qwen3-omni-flash",
        "--exec-mode",
        "sync",
    ]

    if args.dry_run:
        cmd.append("--dry-run")

    print("⚠️  test_qwen_omni.py 为兼容入口，建议直接使用 scripts/main.py")
    print("▶ 执行命令:")
    print("  " + " ".join(cmd))

    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
