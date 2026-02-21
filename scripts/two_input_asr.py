#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch ASR for two_input/ using existing QwenASRProvider (with context).

Input layout:
  two_input/<class>/<student>/*.mp4

Output layout (default):
  two_output/<class>/<student>/<video_stem>/
    ├── 2_qwen_asr.json
    ├── 2_qwen_asr.txt
    └── 2_qwen_asr_context.json (auto-saved by provider)
"""

import argparse
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Ensure project root in path
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.common.env import load_env
from scripts.common.asr import extract_qwen_asr_text
from scripts.asr.qwen import QwenASRProvider


AUDIO_EXTS = {".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg"}


def iter_input_videos(
    input_root: Path,
    class_filter: Optional[str] = None,
    student_filter: Optional[str] = None,
) -> Iterable[Tuple[str, str, Path]]:
    if not input_root.exists():
        return []

    classes = sorted([p for p in input_root.iterdir() if p.is_dir() and not p.name.startswith(".")])
    for class_dir in classes:
        if class_filter and class_filter.lower() not in class_dir.name.lower():
            continue
        students = sorted([p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])
        for student_dir in students:
            if student_filter and student_filter.lower() not in student_dir.name.lower():
                continue
            files = sorted([p for p in student_dir.iterdir() if p.is_file()])
            for file_path in files:
                if file_path.suffix.lower() in AUDIO_EXTS:
                    yield (class_dir.name, student_dir.name, file_path)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text_file(path: Path, text: str) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")


def write_error(output_dir: Path, error: Exception) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    err_path = output_dir / "error.json"
    payload = {
        "error": str(error),
        "traceback": traceback.format_exc(),
    }
    with open(err_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def extract_audio(
    input_video: Path,
    output_audio: Path,
    ffmpeg_bin: Optional[str] = None,
) -> None:
    """
    Extract audio track from video to a compact MP3 file.

    Uses mono 16kHz with low bitrate to reduce file size.
    """
    ffmpeg_path = ffmpeg_bin or shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("未找到 ffmpeg，请先安装或通过 --ffmpeg-bin 指定路径")

    output_audio.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(output_audio),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 转码失败: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch ASR for two_input videos")
    parser.add_argument("--input-root", default="two_input", help="Input root directory")
    parser.add_argument("--output-root", default="two_output", help="Output root directory")
    parser.add_argument("--class", dest="class_filter", help="Filter class name (substring match)")
    parser.add_argument("--student", dest="student_filter", help="Filter student name (substring match)")
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists")
    parser.add_argument("--rebuild-audio", action="store_true", help="Rebuild extracted audio even if exists")
    parser.add_argument("--ffmpeg-bin", help="Path to ffmpeg executable (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions only")
    args = parser.parse_args()

    load_env()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)

    videos = list(iter_input_videos(input_root, args.class_filter, args.student_filter))
    if not videos:
        print(f"未找到可处理的视频: {input_root}")
        return 1

    print(f"发现 {len(videos)} 个视频待处理")

    try:
        provider = QwenASRProvider()
    except Exception as e:
        print(f"❌ 无法初始化 QwenASRProvider: {e}")
        return 1

    total = 0
    skipped = 0
    failed = 0

    for class_name, student_name, file_path in videos:
        video_stem = file_path.stem
        output_dir = output_root / class_name / student_name / video_stem
        output_json = output_dir / "2_qwen_asr.json"
        output_txt = output_dir / "2_qwen_asr.txt"
        output_audio = output_dir / "_audio.mp3"

        if output_json.exists() and not args.force:
            print(f"[跳过] 已存在: {output_json}")
            skipped += 1
            continue

        print(f"[处理] {class_name}/{student_name}/{file_path.name}")

        if args.dry_run:
            print(f"  -> {output_json}")
            total += 1
            continue

        try:
            # Extract audio first to avoid oversized multimodal input
            if args.rebuild_audio or not output_audio.exists():
                extract_audio(file_path, output_audio, ffmpeg_bin=args.ffmpeg_bin)

            provider.transcribe_and_save_with_segmentation(
                input_audio_path=str(output_audio),
                output_dir=str(output_dir),
                vocabulary_path=None,
                output_filename="2_qwen_asr.json",
                language=None,
                segment_duration=180,
                max_workers=3,
            )

            # Write plain text
            with open(output_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            asr_text = extract_qwen_asr_text(data)
            write_text_file(output_txt, asr_text)

            total += 1
        except Exception as e:
            print(f"  [失败] {file_path}: {e}")
            write_error(output_dir, e)
            failed += 1

    print(f"\n完成: 成功 {total}, 跳过 {skipped}, 失败 {failed}")
    return 0 if total > 0 or skipped > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
