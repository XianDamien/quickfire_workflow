# -*- coding: utf-8 -*-
"""
scripts/common/runs.py - Runs 目录管理

提供 run_id 生成、run 目录创建、manifest 写入等功能。

Runs 目录结构：
    archive/{batch}/{student}/runs/{annotator_name}/{run_id}/
        ├── 4_llm_annotation.json  # 标注结果（唯一标准输出）
        ├── prompt_log.txt         # 完整提示词日志
        └── run_manifest.json      # 运行元数据
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .archive import project_root, student_dir, find_audio_file
from .hash import file_hash, text_hash


def get_git_commit(short: bool = True) -> str:
    """
    获取当前 git commit hash

    Args:
        short: 是否返回短 hash（7位）

    Returns:
        commit hash 字符串，获取失败返回 "unknown"
    """
    try:
        cmd = ["git", "rev-parse"]
        if short:
            cmd.append("--short")
        cmd.append("HEAD")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root(),
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def new_run_id() -> str:
    """
    生成唯一的 run_id

    格式: {timestamp}_{git_short}
    例如: 20251218_143022_a5cd771

    Returns:
        run_id 字符串
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    git_short = get_git_commit(short=True)
    return f"{timestamp}_{git_short}"


def ensure_run_dir(
    archive_batch: str,
    student_name: str,
    annotator_name: str,
    run_id: str
) -> Path:
    """
    确保 run 目录存在并返回路径

    Args:
        archive_batch: batch 名称
        student_name: 学生名称
        annotator_name: annotator 名称（如 gemini-2.5-pro）
        run_id: run ID

    Returns:
        run 目录 Path（已创建）
    """
    run_dir = student_dir(archive_batch, student_name) / "runs" / annotator_name / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_manifest(
    run_dir: Path,
    annotator_name: str,
    run_id: str,
    archive_batch: str,
    student_name: str,
    prompt_path: Optional[Path] = None,
    prompt_hash: Optional[str] = None,
    model: str = "unknown",
    extra: Optional[Dict[str, Any]] = None
) -> Path:
    """
    创建并写入 run_manifest.json

    Args:
        run_dir: run 目录 Path
        annotator_name: annotator 名称
        run_id: run ID
        archive_batch: batch 名称
        student_name: 学生名称
        prompt_path: 提示词文件路径（可选）
        prompt_hash: 提示词 hash（可选）
        model: 模型名称
        extra: 额外的元数据字段

    Returns:
        manifest 文件 Path
    """
    root = project_root()
    stu_dir = student_dir(archive_batch, student_name)

    manifest: Dict[str, Any] = {
        "run_id": run_id,
        "annotator_name": annotator_name,
        "model": model,
        "created_at": datetime.now().isoformat(),
        "code": {
            "git_commit": get_git_commit(short=False),
        },
        "inputs": {},
        "prompt": {}
    }

    # 记录输入文件的 hash
    audio_file = find_audio_file(stu_dir)
    if audio_file:
        manifest["inputs"]["audio"] = file_hash(audio_file)

    qwen_asr = stu_dir / "2_qwen_asr.json"
    if qwen_asr.exists():
        manifest["inputs"]["qwen_asr"] = file_hash(qwen_asr)

    timestamps = stu_dir / "3_asr_timestamp.json"
    if timestamps.exists():
        manifest["inputs"]["timestamps"] = file_hash(timestamps)

    # 题库 hash（从 _shared_context 查找）
    shared_ctx = stu_dir.parent / "_shared_context"
    if shared_ctx.exists():
        for qb in shared_ctx.glob("R*.json"):
            if "vocabulary" not in qb.name.lower():
                manifest["inputs"]["question_bank"] = file_hash(qb)
                break

    # prompt 信息
    if prompt_path:
        try:
            manifest["prompt"]["path"] = str(prompt_path.relative_to(root))
        except ValueError:
            manifest["prompt"]["path"] = str(prompt_path)

    if prompt_hash:
        manifest["prompt"]["hash"] = prompt_hash

    # 合并额外字段
    if extra:
        for k, v in extra.items():
            if k not in manifest:
                manifest[k] = v

    # 写入文件
    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest_path
