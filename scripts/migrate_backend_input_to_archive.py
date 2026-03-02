#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移脚本：将 backend_input/*.mp3 迁移到新的 archive/{class_code}_{date}/ 目录结构

【目录结构】（符合 docs/dataset_conventions.md）
archive/{class_code}_{date}/
├── metadata.json           # 班级元数据（含 items[] 数组）
├── {student}/
│   ├── 1_input_audio.mp3   # 原始音频
│   ├── 2_qwen_asr.json     # Qwen ASR 转写结果（后续生成）
│   ├── 3_asr_timestamp.json# FunASR 带时间戳转写（后续生成）
│   └── runs/
│       └── {run_id}/
│           ├── 4_llm_annotation.json
│           ├── 4_llm_prompt_log.txt
│           └── run_metadata.json
└── reports/
    └── {run_id}/
        └── batch_annotation_report.json

【metadata.json 结构】
{
  "schema_version": 1,
  "dataset_id": "Zoe41900_2025-09-08",
  "class_code": "Zoe41900",
  "date": "2025-09-08",
  "progress": "R1-65-D5",
  "question_bank_path": "questionbank/R1-65-D5.json",
  "items": [
    {
      "file_id": "Zoe41900_2025-09-08_R1-65-D5_Oscar",
      "student": "Oscar",
      "local_path": "archive/Zoe41900_2025-09-08/Oscar/1_input_audio.mp3",
      "oss_url": null
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}

【命令行用法】
  python3 migrate_backend_input_to_archive.py                # 迁移所有文件
  python3 migrate_backend_input_to_archive.py --dry-run      # 预览迁移（不实际执行）
  python3 migrate_backend_input_to_archive.py --class Zoe41900  # 只迁移指定班级
"""

import os
import sys
import json
import re
import shutil
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

# 确保项目根目录在 Python path 中
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 导入公共工具函数
from scripts.common.naming import parse_backend_input_mp3_name


def parse_audio_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    解析 backend_input 音频文件名。

    已迁移到 scripts.common.naming.parse_backend_input_mp3_name，此函数为兼容性别名。
    """
    return parse_backend_input_mp3_name(filename)


def find_questionbank_file(question_bank_code: str, questionbank_dir: Path) -> Optional[Path]:
    """
    在 questionbank/ 目录中查找题库文件。

    Args:
        question_bank_code: 题库代码（如 R1-27-D2）
        questionbank_dir: questionbank 目录路径

    Returns:
        题库文件路径，或 None
    """
    if not questionbank_dir.exists():
        return None

    # 精确匹配
    exact = questionbank_dir / f"{question_bank_code}.json"
    if exact.exists():
        return exact

    # 前缀匹配
    for f in sorted(questionbank_dir.glob(f"{question_bank_code}*.json")):
        if f.is_file():
            return f

    return None


def extract_progress_from_qb(question_bank_code: str) -> str:
    """
    从题库代码提取进度信息。

    例如: "R1-27-D2" -> "R1-27"

    Args:
        question_bank_code: 题库代码

    Returns:
        进度字符串
    """
    match = re.match(r'([A-Z]\d+-\d+)', question_bank_code)
    if match:
        return match.group(1)
    return question_bank_code


def discover_backend_files(backend_input_dir: Path, class_code: Optional[str] = None) -> Dict[str, Dict]:
    """
    扫描 backend_input 目录，按 {class_code}_{date} 分组。

    Args:
        backend_input_dir: backend_input 目录路径
        class_code: 可选的班级代码过滤

    Returns:
        {"{class_code}_{date}": {"progress": "...", "students": {student_name: file_path}}}
    """
    groups = {}

    for mp3_file in backend_input_dir.glob("*.mp3"):
        parsed = parse_audio_filename(mp3_file.name)
        if not parsed:
            print(f"  ⚠️  跳过无法解析的文件: {mp3_file.name}")
            continue

        # 应用班级过滤
        if class_code and parsed["class_code"] != class_code:
            continue

        # 创建分组键
        group_key = f"{parsed['class_code']}_{parsed['date']}"

        if group_key not in groups:
            groups[group_key] = {
                "class_code": parsed["class_code"],
                "date": parsed["date"],
                "progress": extract_progress_from_qb(parsed["question_bank"]),
                "question_bank": parsed["question_bank"],
                "students": {}
            }

        # 校验同一分组的 progress 是否一致
        expected_progress = extract_progress_from_qb(parsed["question_bank"])
        if groups[group_key]["progress"] != expected_progress:
            print(f"  ⚠️  警告: {group_key} 中发现不一致的题库")
            print(f"       已有: {groups[group_key]['question_bank']}")
            print(f"       新的: {parsed['question_bank']}")

        # 添加学生
        student_name = parsed["student_name"]
        if student_name not in groups[group_key]["students"]:
            groups[group_key]["students"][student_name] = mp3_file

    return groups


def find_asr_timestamp_file(student_name: str, class_code: str, date: str,
                            question_bank: str, asr_timestamp_dir: Path) -> Optional[Path]:
    """
    查找学生对应的 asr_timestamp 文件。

    Args:
        student_name: 学生名称
        class_code: 班级代码
        date: 日期
        question_bank: 题库代码
        asr_timestamp_dir: asr_timestamp 目录

    Returns:
        asr_timestamp 文件路径，或 None
    """
    if not asr_timestamp_dir.exists():
        return None

    # 构造预期的文件名
    expected_name = f"{class_code}_{date}_{question_bank}_{student_name}.json"
    expected_file = asr_timestamp_dir / expected_name

    if expected_file.exists():
        return expected_file

    # 尝试模糊匹配
    pattern = f"*_{student_name}.json"
    for f in asr_timestamp_dir.glob(pattern):
        if f.is_file():
            return f

    return None


def migrate_group(
    group_key: str,
    group_data: Dict,
    archive_dir: Path,
    questionbank_dir: Path,
    asr_timestamp_dir: Path,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    迁移单个分组（班级+日期）到 archive 目录。

    符合 docs/dataset_conventions.md 规范：
    - 不复制题库文件，使用 question_bank_path 指向 questionbank/
    - metadata.json 包含 items[] 数组

    Args:
        group_key: 分组键（如 "Zoe41900_2025-09-08"）
        group_data: 分组数据
        archive_dir: archive 目录路径
        questionbank_dir: questionbank 目录路径
        asr_timestamp_dir: asr_timestamp 目录路径
        dry_run: 是否为预览模式

    Returns:
        (成功数, 跳过数)
    """
    class_code = group_data["class_code"]
    date = group_data["date"]
    progress = group_data["progress"]
    question_bank = group_data["question_bank"]
    students = group_data["students"]

    print(f"\n📁 处理分组: {group_key}")
    print(f"   班级: {class_code}, 日期: {date}, 进度: {progress}")
    print(f"   学生数: {len(students)}")

    # 创建目标目录
    target_dir = archive_dir / group_key

    if dry_run:
        print(f"   [预览] 将创建目录: {target_dir}")
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    # 检查题库文件是否存在（不复制，只记录路径）
    qb_source = find_questionbank_file(question_bank, questionbank_dir)
    qb_path = None
    if qb_source:
        # 使用相对于项目根目录的路径
        qb_path = f"questionbank/{qb_source.name}"
        if dry_run:
            print(f"   [预览] 题库路径: {qb_path}")
        else:
            print(f"   ✓ 题库路径: {qb_path}")
    else:
        print(f"   ⚠️  未找到题库文件: {question_bank}")

    # 迁移学生文件并收集 items
    items = []
    success_count = 0
    skip_count = 0

    for student_name, audio_source in students.items():
        student_dir = target_dir / student_name
        audio_target = student_dir / "1_input_audio.mp3"

        # 构建 file_id
        file_id = f"{class_code}_{date}_{question_bank}_{student_name}"

        # 检查是否已存在
        if audio_target.exists():
            print(f"      ⊘ {student_name}: 已存在（跳过）")
            skip_count += 1
            # 仍然添加到 items（用于更新 metadata）
            items.append({
                "file_id": file_id,
                "student": student_name,
                "local_path": f"archive/{group_key}/{student_name}/1_input_audio.mp3",
                "oss_url": None  # 需要后续填充
            })
            continue

        if dry_run:
            print(f"      [预览] {student_name}: {audio_source.name} -> 1_input_audio.mp3")
        else:
            student_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(audio_source, audio_target)
            print(f"      ✓ {student_name}: 已迁移音频")

        # 添加到 items
        items.append({
            "file_id": file_id,
            "student": student_name,
            "local_path": f"archive/{group_key}/{student_name}/1_input_audio.mp3",
            "oss_url": None  # 需要后续填充
        })

        # 迁移 asr_timestamp 文件（如果存在）
        asr_ts_source = find_asr_timestamp_file(
            student_name, class_code, date, question_bank, asr_timestamp_dir
        )
        if asr_ts_source:
            asr_ts_target = student_dir / "3_asr_timestamp.json"
            if dry_run:
                print(f"         [预览] 迁移 asr_timestamp: {asr_ts_source.name}")
            else:
                shutil.copy2(asr_ts_source, asr_ts_target)
                print(f"         ✓ 迁移 asr_timestamp")

        success_count += 1

    # 创建符合规范的 metadata.json
    now = datetime.now().isoformat()
    metadata = {
        "schema_version": 1,
        "dataset_id": group_key,
        "class_code": class_code,
        "date": date,
        "progress": question_bank,  # 使用完整的题库码作为 progress
        "question_bank_path": qb_path,
        "items": items,
        "created_at": now,
        "updated_at": now,
        "notes": "migrated from backend_input"
    }

    metadata_path = target_dir / "metadata.json"
    if dry_run:
        print(f"   [预览] 创建 metadata.json (含 {len(items)} 个学生)")
    else:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"   ✓ 创建 metadata.json (含 {len(items)} 个学生)")

    return success_count, skip_count


def main():
    parser = argparse.ArgumentParser(
        description='迁移 backend_input 到 archive 目录结构',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际执行迁移'
    )

    parser.add_argument(
        '--class',
        dest='class_code',
        type=str,
        help='只迁移指定班级（如 Zoe41900）'
    )

    parser.add_argument(
        '--move',
        action='store_true',
        help='移动文件而不是复制（删除源文件）'
    )

    args = parser.parse_args()

    # 设置路径
    project_root = Path(__file__).parent.parent
    backend_input_dir = project_root / "backend_input"
    archive_dir = project_root / "archive"
    questionbank_dir = project_root / "questionbank"
    asr_timestamp_dir = project_root / "asr_timestamp"

    if not backend_input_dir.exists():
        print(f"❌ backend_input 目录不存在: {backend_input_dir}")
        sys.exit(1)

    print("=" * 60)
    print("🚀 迁移 backend_input 到 archive 目录结构")
    print("=" * 60)

    if args.dry_run:
        print("⚠️  预览模式 - 不会实际执行任何操作")

    if args.class_code:
        print(f"🔍 只迁移班级: {args.class_code}")

    # 扫描文件
    print("\n📂 扫描 backend_input 目录...")
    groups = discover_backend_files(backend_input_dir, args.class_code)

    if not groups:
        print("❌ 没有找到可迁移的文件")
        sys.exit(0)

    print(f"   找到 {len(groups)} 个分组")

    # 执行迁移
    total_success = 0
    total_skip = 0

    for group_key, group_data in sorted(groups.items()):
        success, skip = migrate_group(
            group_key,
            group_data,
            archive_dir,
            questionbank_dir,
            asr_timestamp_dir,
            dry_run=args.dry_run
        )
        total_success += success
        total_skip += skip

    # 总结
    print("\n" + "=" * 60)
    print("📊 迁移统计")
    print("=" * 60)
    print(f"   分组数: {len(groups)}")
    print(f"   成功迁移: {total_success}")
    print(f"   跳过（已存在）: {total_skip}")

    if args.dry_run:
        print("\n💡 这是预览模式，移除 --dry-run 执行实际迁移")


if __name__ == "__main__":
    main()
