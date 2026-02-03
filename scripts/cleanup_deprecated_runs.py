#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 archive 中过时和不完整的标注 runs

备份目标: archive_source/deprecated_runs_20260202/{class}_{date}/{student}/{annotator}/{run_id}/
删除范围:
  1. 过时模型 runs (gemini-2.5-pro, gemini-2.5-flash, gemini-3-flash-preview, qwen-max, qwen3-max, gemini-2.0-flash.audio)
  2. 时间戳格式 runs (直接以 2025/2026 开头的 run 目录, 非模型名组织)
  3. 不完整 audio runs (仅有 prompt_log.txt 或空目录, 无 4_llm_annotation.json)
  4. _batch_runs 中过时模型的批次
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

ARCHIVE_ROOT = Path(__file__).parent.parent / "archive"
BACKUP_ROOT = Path(__file__).parent.parent / "archive_source" / "deprecated_runs_20260202"

# 过时模型
DEPRECATED_MODELS = {
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash.audio",
    "gemini-3-flash-preview",
    "qwen-max",
    "qwen3-max",
}


def backup_and_remove(src: Path, backup_rel: str, dry_run: bool) -> bool:
    """备份到 BACKUP_ROOT/backup_rel 然后删除原始目录"""
    dst = BACKUP_ROOT / backup_rel
    if dry_run:
        print(f"  [DRY] {src} -> {dst}")
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    shutil.rmtree(src)
    return True


def clean_deprecated_model_runs(dry_run: bool) -> int:
    """清理过时模型的 runs 目录"""
    count = 0
    for batch_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not batch_dir.is_dir() or batch_dir.name.startswith("_"):
            continue
        batch_name = batch_dir.name  # e.g. Zoe41900_2025-09-08

        for student_dir in sorted(batch_dir.iterdir()):
            if not student_dir.is_dir() or student_dir.name.startswith("_"):
                continue
            runs_dir = student_dir / "runs"
            if not runs_dir.exists():
                continue

            for annotator_dir in sorted(runs_dir.iterdir()):
                if not annotator_dir.is_dir():
                    continue
                if annotator_dir.name in DEPRECATED_MODELS:
                    rel = f"{batch_name}/{student_dir.name}/runs/{annotator_dir.name}"
                    backup_and_remove(annotator_dir, rel, dry_run)
                    count += 1
                    print(f"  [-] {rel}")
    return count


def clean_timestamp_runs(dry_run: bool) -> int:
    """清理时间戳格式 runs (直接以日期开头, 没有模型名层级)"""
    count = 0
    for batch_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not batch_dir.is_dir() or batch_dir.name.startswith("_"):
            continue
        batch_name = batch_dir.name

        for student_dir in sorted(batch_dir.iterdir()):
            if not student_dir.is_dir() or student_dir.name.startswith("_"):
                continue
            runs_dir = student_dir / "runs"
            if not runs_dir.exists():
                continue

            for item in sorted(runs_dir.iterdir()):
                if not item.is_dir():
                    continue
                # 时间戳格式: 20251218_120059_a7214dd
                if item.name[:4] in ("2025", "2026") and "_" in item.name:
                    rel = f"{batch_name}/{student_dir.name}/runs/{item.name}"
                    backup_and_remove(item, rel, dry_run)
                    count += 1
                    print(f"  [-] {rel}")
    return count


def clean_incomplete_audio_runs(dry_run: bool) -> int:
    """清理不完整的 audio runs (无 4_llm_annotation.json)"""
    audio_annotators = {
        "gemini-3-pro-preview.audio",
        "gemini-3-pro-preview_audio",
        "gemini-audio",
        "gemini-2.0-flash.audio",
    }
    count = 0

    for batch_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not batch_dir.is_dir() or batch_dir.name.startswith("_"):
            continue
        batch_name = batch_dir.name

        for student_dir in sorted(batch_dir.iterdir()):
            if not student_dir.is_dir() or student_dir.name.startswith("_"):
                continue
            runs_dir = student_dir / "runs"
            if not runs_dir.exists():
                continue

            for annotator_dir in sorted(runs_dir.iterdir()):
                if not annotator_dir.is_dir():
                    continue
                if annotator_dir.name not in audio_annotators:
                    continue
                # 已在 deprecated_models 中处理的跳过
                if annotator_dir.name in DEPRECATED_MODELS:
                    continue

                for run_dir in sorted(annotator_dir.iterdir()):
                    if not run_dir.is_dir():
                        continue
                    annotation = run_dir / "4_llm_annotation.json"
                    if not annotation.exists():
                        rel = f"{batch_name}/{student_dir.name}/runs/{annotator_dir.name}/{run_dir.name}"
                        backup_and_remove(run_dir, rel, dry_run)
                        count += 1
                        print(f"  [-] {rel} (incomplete)")

                # 如果 annotator 目录下没有 run 了, 删除空目录
                if annotator_dir.exists() and not any(annotator_dir.iterdir()):
                    if not dry_run:
                        annotator_dir.rmdir()
                    print(f"  [-] {batch_name}/{student_dir.name}/runs/{annotator_dir.name}/ (empty)")
    return count


def clean_deprecated_batch_runs(dry_run: bool) -> int:
    """清理 _batch_runs 中过时模型的批次"""
    count = 0
    for batch_dir in sorted(ARCHIVE_ROOT.iterdir()):
        if not batch_dir.is_dir() or batch_dir.name.startswith("_"):
            continue
        batch_name = batch_dir.name
        batch_runs_dir = batch_dir / "_batch_runs"
        if not batch_runs_dir.exists():
            continue

        for run_dir in sorted(batch_runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "batch_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                model = manifest.get("model", "")
                if model in DEPRECATED_MODELS:
                    rel = f"{batch_name}/_batch_runs/{run_dir.name}"
                    backup_and_remove(run_dir, rel, dry_run)
                    count += 1
                    print(f"  [-] {rel} (model={model})")
            except (json.JSONDecodeError, OSError):
                pass
    return count


def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    if dry_run:
        print("=== DRY RUN (不会实际操作) ===\n")
    else:
        print(f"=== 备份目录: {BACKUP_ROOT} ===\n")

    print(f"[1/4] 清理过时模型 runs...")
    c1 = clean_deprecated_model_runs(dry_run)
    print(f"  共 {c1} 个\n")

    print(f"[2/4] 清理时间戳格式 runs...")
    c2 = clean_timestamp_runs(dry_run)
    print(f"  共 {c2} 个\n")

    print(f"[3/4] 清理不完整 audio runs...")
    c3 = clean_incomplete_audio_runs(dry_run)
    print(f"  共 {c3} 个\n")

    print(f"[4/4] 清理过时模型 _batch_runs...")
    c4 = clean_deprecated_batch_runs(dry_run)
    print(f"  共 {c4} 个\n")

    total = c1 + c2 + c3 + c4
    print(f"{'='*60}")
    print(f"总计清理: {total} 项")
    if not dry_run:
        print(f"备份位置: {BACKUP_ROOT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
