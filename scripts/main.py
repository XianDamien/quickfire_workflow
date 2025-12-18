#!/usr/bin/env python3
"""
Quickfire 一键入口 - DAG 依赖驱动的批处理工具

DAG 节点与依赖:
    audio → qwen_asr → timestamps → cards

用法:
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target cards
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar --target cards
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --only qwen_asr
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --until timestamps
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target cards --annotator gemini-2.5-pro
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

# 项目根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive"

# 虚拟环境 Python 路径
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

# DAG 节点定义（顺序即依赖顺序）
DAG_STAGES = ["audio", "qwen_asr", "timestamps", "cards"]


def get_python_executable() -> str:
    """获取 Python 可执行文件路径（优先使用虚拟环境）"""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def get_git_commit() -> str:
    """获取当前 git commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_file_hash(file_path: Path) -> str:
    """计算文件的 sha256 hash（前16位）"""
    if not file_path.exists():
        return "missing"
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()[:16]}"


def find_audio_file(student_dir: Path) -> Optional[Path]:
    """查找学生目录下的音频文件"""
    for ext in [".mp3", ".wav", ".m4a", ".flac", ".ogg"]:
        audio_file = student_dir / f"1_input_audio{ext}"
        if audio_file.exists():
            return audio_file
    return None


def check_stage_complete(student_dir: Path, stage: str) -> bool:
    """检查某个阶段是否已完成"""
    if stage == "audio":
        return find_audio_file(student_dir) is not None
    elif stage == "qwen_asr":
        return (student_dir / "2_qwen_asr.json").exists()
    elif stage == "timestamps":
        return (student_dir / "3_asr_timestamp.json").exists()
    elif stage == "cards":
        # cards 阶段：检查 runs/ 目录下是否有 cards.json
        runs_dir = student_dir / "runs"
        if not runs_dir.exists():
            return False
        # 查找任意 annotator 下的 cards.json
        for annotator_dir in runs_dir.iterdir():
            if annotator_dir.is_dir():
                for run_dir in annotator_dir.iterdir():
                    if run_dir.is_dir() and (run_dir / "cards.json").exists():
                        return True
        return False
    return False


def get_students(archive_batch: str, student_filter: Optional[str] = None) -> List[Tuple[str, Path]]:
    """获取学生列表"""
    batch_dir = ARCHIVE_DIR / archive_batch
    if not batch_dir.exists():
        print(f"错误: Archive 目录不存在: {batch_dir}")
        sys.exit(1)

    students = []
    for item in sorted(batch_dir.iterdir()):
        if item.is_dir() and not item.name.startswith('.') and item.name not in ["reports", "_shared_context"]:
            if student_filter:
                # 模糊匹配
                if student_filter.lower() in item.name.lower():
                    students.append((item.name, item))
            else:
                students.append((item.name, item))

    return students


def run_stage(stage: str, archive_batch: str, student_name: str,
              force: bool = False, annotator: str = "gemini-2.5-pro",
              dry_run: bool = False) -> bool:
    """
    执行单个阶段
    返回: True=成功, False=失败
    """
    student_dir = ARCHIVE_DIR / archive_batch / student_name

    # 检查是否需要执行
    if not force and check_stage_complete(student_dir, stage):
        print(f"  [跳过] {stage} 已完成")
        return True

    if stage == "audio":
        # audio 阶段只检查，不执行
        if find_audio_file(student_dir):
            print(f"  [✓] audio 已存在")
            return True
        else:
            print(f"  [✗] 缺少音频文件: {student_dir}/1_input_audio.*")
            return False

    elif stage == "qwen_asr":
        cmd = [
            get_python_executable(), str(SCRIPT_DIR / "qwen_asr.py"),
            "--archive-batch", archive_batch,
            "--student", student_name
        ]
        if force:
            cmd.append("--force")

        if dry_run:
            print(f"  [dry-run] {' '.join(cmd)}")
            return True

        print(f"  [执行] qwen_asr.py --archive-batch {archive_batch} --student {student_name}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(f"  [✗] qwen_asr 失败 (exit code: {result.returncode})")
            return False
        print(f"  [✓] qwen_asr 完成")
        return True

    elif stage == "timestamps":
        cmd = [
            get_python_executable(), str(SCRIPT_DIR / "funasr.py"),
            "--archive-batch", archive_batch,
            "--student", student_name
        ]
        if force:
            cmd.append("--force")

        if dry_run:
            print(f"  [dry-run] {' '.join(cmd)}")
            return True

        print(f"  [执行] funasr.py --archive-batch {archive_batch} --student {student_name}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(f"  [✗] funasr (timestamps) 失败 (exit code: {result.returncode})")
            return False
        print(f"  [✓] timestamps 完成")
        return True

    elif stage == "cards":
        return run_annotation(archive_batch, student_name, annotator, force, dry_run)

    return False


def run_annotation(archive_batch: str, student_name: str,
                   annotator: str, force: bool, dry_run: bool) -> bool:
    """
    执行标注阶段，输出到分层 runs 目录
    输出: archive/{dataset_id}/{student}/runs/{annotator_name}/{run_id}/cards.json
    """
    student_dir = ARCHIVE_DIR / archive_batch / student_name
    git_commit = get_git_commit()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{git_commit}"

    # 目标目录: runs/{annotator_name}/{run_id}/
    annotator_dir = student_dir / "runs" / annotator
    run_dir = annotator_dir / run_id

    if dry_run:
        print(f"  [dry-run] 会创建: {run_dir}/cards.json")
        return True

    # 调用 Gemini annotation 脚本
    # 目前只支持 gemini，后续可扩展
    if annotator.startswith("gemini"):
        cmd = [
            get_python_executable(), str(SCRIPT_DIR / "Gemini_annotation.py"),
            "--archive-batch", archive_batch,
            "--student", student_name
        ]
        if force:
            cmd.append("--force")

        print(f"  [执行] Gemini_annotation.py --archive-batch {archive_batch} --student {student_name}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)

        if result.returncode != 0:
            print(f"  [✗] annotation 失败 (exit code: {result.returncode})")
            return False

        # 迁移输出到分层目录
        # Gemini_annotation.py 输出到 runs/{run_id}/4_llm_annotation.json
        # 我们需要把它移动/复制到 runs/{annotator}/{run_id}/cards.json
        legacy_runs = student_dir / "runs"
        if legacy_runs.exists():
            # 找到最新的 run 目录（不在 annotator 子目录下）
            latest_run = None
            latest_time = None
            for item in legacy_runs.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # 跳过 annotator 子目录
                    if item.name in ["gemini-2.5-pro", "gemini-2.0-flash", "openai"]:
                        continue
                    # 检查是否有 4_llm_annotation.json
                    if (item / "4_llm_annotation.json").exists():
                        try:
                            mtime = item.stat().st_mtime
                            if latest_time is None or mtime > latest_time:
                                latest_time = mtime
                                latest_run = item
                        except:
                            pass

            if latest_run and (latest_run / "4_llm_annotation.json").exists():
                # 创建目标目录
                run_dir.mkdir(parents=True, exist_ok=True)

                # 复制并重命名文件
                src_annotation = latest_run / "4_llm_annotation.json"
                dst_cards = run_dir / "cards.json"
                shutil.copy2(src_annotation, dst_cards)

                # 复制其他文件
                for src_file in ["4_llm_prompt_log.txt", "run_metadata.json"]:
                    src = latest_run / src_file
                    if src.exists():
                        dst_name = src_file.replace("4_llm_prompt_log.txt", "prompt_log.txt")
                        shutil.copy2(src, run_dir / dst_name)

                # 更新 run_manifest.json（增强版 metadata）
                manifest = create_run_manifest(
                    student_dir, run_id, annotator,
                    run_dir / "prompt_log.txt" if (run_dir / "prompt_log.txt").exists() else None
                )
                with open(run_dir / "run_manifest.json", "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)

                print(f"  [✓] cards 完成 -> {run_dir.relative_to(PROJECT_ROOT)}/cards.json")
                return True

        # 如果没找到输出，报错
        print(f"  [✗] annotation 输出未找到")
        return False

    else:
        print(f"  [✗] 不支持的 annotator: {annotator}")
        return False


def create_run_manifest(student_dir: Path, run_id: str, annotator: str,
                        prompt_log_path: Optional[Path]) -> dict:
    """创建 run_manifest.json"""
    manifest = {
        "run_id": run_id,
        "annotator_name": annotator,
        "created_at": datetime.now().isoformat(),
        "code": {
            "git_commit": get_git_commit(),
        },
        "inputs": {},
        "prompt": {}
    }

    # 记录输入文件的 hash
    audio_file = find_audio_file(student_dir)
    if audio_file:
        manifest["inputs"]["audio"] = get_file_hash(audio_file)

    qwen_asr = student_dir / "2_qwen_asr.json"
    if qwen_asr.exists():
        manifest["inputs"]["qwen_asr"] = get_file_hash(qwen_asr)

    timestamps = student_dir / "3_asr_timestamp.json"
    if timestamps.exists():
        manifest["inputs"]["timestamps"] = get_file_hash(timestamps)

    # 题库 hash
    shared_ctx = student_dir.parent / "_shared_context"
    if shared_ctx.exists():
        for qb in shared_ctx.glob("R*.json"):
            if "vocabulary" not in qb.name.lower():
                manifest["inputs"]["question_bank"] = get_file_hash(qb)
                break

    # prompt hash
    prompt_path = PROJECT_ROOT / "prompts" / "annotation" / "user.md"
    if prompt_path.exists():
        manifest["prompt"]["path"] = str(prompt_path.relative_to(PROJECT_ROOT))
        manifest["prompt"]["hash"] = get_file_hash(prompt_path)

    return manifest


def resolve_stages(target: Optional[str], only: Optional[str], until: Optional[str],
                   target_is_default: bool = True) -> List[str]:
    """
    解析要执行的阶段列表

    --target cards: 执行所有阶段直到 cards（包括）
    --only qwen_asr: 只执行 qwen_asr
    --until timestamps: 执行到 timestamps 为止（包括）
    """
    if only:
        if only not in DAG_STAGES:
            print(f"错误: 无效的阶段 '{only}'，可选: {', '.join(DAG_STAGES)}")
            sys.exit(1)
        return [only]

    # --until 优先级高于默认的 --target
    if until:
        end_stage = until
    elif target and not target_is_default:
        end_stage = target
    elif until:
        end_stage = until
    else:
        end_stage = target or "cards"

    if end_stage not in DAG_STAGES:
        print(f"错误: 无效的阶段 '{end_stage}'，可选: {', '.join(DAG_STAGES)}")
        sys.exit(1)

    end_idx = DAG_STAGES.index(end_stage)
    return DAG_STAGES[:end_idx + 1]


def main():
    parser = argparse.ArgumentParser(
        description='Quickfire 一键入口 - DAG 依赖驱动的批处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 完整流程（默认 --target cards）
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08

  # 指定学生
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # 只执行某个阶段
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --only qwen_asr

  # 执行到某个阶段
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --until timestamps

  # 指定 annotator
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --annotator gemini-2.5-pro

  # 强制重新处理
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --force

  # 干运行（不实际执行）
  python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --dry-run

DAG 阶段: audio → qwen_asr → timestamps → cards
        """
    )

    parser.add_argument(
        '--archive-batch', '-b',
        type=str,
        required=True,
        help='Archive 批处理 ID (例如: Zoe41900_2025-09-08)'
    )

    parser.add_argument(
        '--student', '-s',
        type=str,
        help='学生名字 (支持模糊匹配，不指定则处理所有学生)'
    )

    parser.add_argument(
        '--target', '-t',
        type=str,
        default='cards',
        choices=DAG_STAGES,
        help='目标阶段，执行所有依赖阶段 (默认: cards)'
    )

    parser.add_argument(
        '--only',
        type=str,
        choices=DAG_STAGES,
        help='只执行指定阶段（跳过依赖检查）'
    )

    parser.add_argument(
        '--until',
        type=str,
        choices=DAG_STAGES,
        help='执行到指定阶段为止（包括）'
    )

    parser.add_argument(
        '--annotator', '-a',
        type=str,
        default='gemini-2.5-pro',
        help='标注模型 (默认: gemini-2.5-pro)'
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='强制重新处理已完成的阶段'
    )

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='干运行，只显示要执行的命令'
    )

    args = parser.parse_args()

    # 检测 --target 是否是用户显式设置的
    # 如果 --until 被设置，它应该优先于默认的 --target
    target_is_default = '--target' not in sys.argv and '-t' not in sys.argv

    # 解析要执行的阶段
    stages = resolve_stages(args.target, args.only, args.until, target_is_default)

    # 获取学生列表
    students = get_students(args.archive_batch, args.student)
    if not students:
        print(f"错误: 没有找到学生" + (f" (filter: {args.student})" if args.student else ""))
        sys.exit(1)

    print(f"=" * 60)
    print(f"Quickfire Pipeline")
    print(f"=" * 60)
    print(f"Archive: {args.archive_batch}")
    print(f"学生数: {len(students)}")
    print(f"阶段: {' → '.join(stages)}")
    print(f"Annotator: {args.annotator}")
    if args.force:
        print(f"模式: 强制重新处理")
    if args.dry_run:
        print(f"模式: 干运行")
    print(f"=" * 60)
    print()

    # 统计
    success_count = 0
    fail_count = 0

    # 处理每个学生
    for student_name, student_dir in students:
        print(f"[{student_name}]")

        # 执行每个阶段
        student_success = True
        for stage in stages:
            success = run_stage(
                stage, args.archive_batch, student_name,
                force=args.force, annotator=args.annotator,
                dry_run=args.dry_run
            )
            if not success:
                student_success = False
                fail_count += 1
                print(f"  [停止] 严格失败模式：{stage} 失败，停止处理")
                # 严格失败模式：错一个就停
                print()
                print(f"=" * 60)
                print(f"错误: 学生 '{student_name}' 在阶段 '{stage}' 失败")
                print(f"已处理: {success_count} 成功, {fail_count} 失败")
                print(f"=" * 60)
                sys.exit(1)

        if student_success:
            success_count += 1
            print(f"  [完成] 所有阶段成功")
        print()

    # 总结
    print(f"=" * 60)
    print(f"完成: {success_count} 成功, {fail_count} 失败")
    print(f"=" * 60)

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
