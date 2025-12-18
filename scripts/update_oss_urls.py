#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 archive metadata 中的 oss_url 字段

从 CSV 文件读取 OSS URL 映射，更新到对应的 metadata.json

【用法】
  python3 update_oss_urls.py /path/to/export_urls.csv
  python3 update_oss_urls.py /path/to/export_urls.csv --dry-run  # 预览模式
"""

import csv
import json
import re
import sys
import argparse
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime


def parse_object_path(object_path: str) -> dict | None:
    """
    解析 CSV 中的 object 路径

    格式: audio%2F{ClassCode}_{Date}_{QuestionBank}_{Student}.mp3

    Returns:
        {"class_code": ..., "date": ..., "question_bank": ..., "student": ...}
    """
    # URL 解码
    decoded = unquote(object_path)

    # 移除 "audio/" 前缀
    if decoded.startswith("audio/"):
        decoded = decoded[6:]

    # 移除 .mp3 后缀
    if decoded.endswith(".mp3"):
        decoded = decoded[:-4]

    # 解析文件名: {ClassCode}_{Date}_{QuestionBank}_{Student}
    # 注意: 学生名可能包含空格
    pattern = r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)_(.+)$'
    match = re.match(pattern, decoded)

    if not match:
        return None

    return {
        "class_code": match.group(1),
        "date": match.group(2),
        "question_bank": match.group(3),
        "student": match.group(4)
    }


def load_oss_mapping(csv_path: Path) -> dict:
    """
    从 CSV 加载 OSS URL 映射

    Returns:
        {"{class_code}_{date}": {"{student}": "oss_url", ...}, ...}
    """
    mapping = {}

    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 处理 BOM
        reader = csv.DictReader(f)
        for row in reader:
            object_path = row.get('object', '')
            url = row.get('url', '')

            if not object_path or not url:
                continue

            parsed = parse_object_path(object_path)
            if not parsed:
                continue

            # 创建分组键
            group_key = f"{parsed['class_code']}_{parsed['date']}"
            student = parsed['student']

            if group_key not in mapping:
                mapping[group_key] = {}

            mapping[group_key][student] = url

    return mapping


def update_metadata(archive_dir: Path, mapping: dict, dry_run: bool = False) -> tuple:
    """
    更新所有 metadata.json 中的 oss_url

    Returns:
        (更新数, 跳过数)
    """
    total_updated = 0
    total_skipped = 0

    for group_key, student_urls in mapping.items():
        metadata_path = archive_dir / group_key / "metadata.json"

        if not metadata_path.exists():
            print(f"  ⚠️  跳过 {group_key}: metadata.json 不存在")
            continue

        # 读取 metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        items = metadata.get("items", [])
        updated_count = 0

        for item in items:
            student = item.get("student", "")
            current_url = item.get("oss_url")

            # 只更新 oss_url 为 null 的项
            if current_url is not None:
                total_skipped += 1
                continue

            if student in student_urls:
                if dry_run:
                    print(f"  [预览] {group_key}/{student}: 将设置 oss_url")
                else:
                    item["oss_url"] = student_urls[student]
                updated_count += 1
                total_updated += 1

        # 更新时间戳并保存
        if updated_count > 0 and not dry_run:
            metadata["updated_at"] = datetime.now().isoformat()
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"  ✓ {group_key}: 更新了 {updated_count} 个 oss_url")
        elif updated_count > 0:
            print(f"  [预览] {group_key}: 将更新 {updated_count} 个 oss_url")

    return total_updated, total_skipped


def main():
    parser = argparse.ArgumentParser(
        description='更新 archive metadata 中的 oss_url'
    )
    parser.add_argument(
        'csv_file',
        type=str,
        help='包含 OSS URL 的 CSV 文件路径'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际修改文件'
    )

    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive"

    if not archive_dir.exists():
        print(f"❌ archive 目录不存在: {archive_dir}")
        sys.exit(1)

    print("=" * 60)
    print("🔗 更新 archive metadata 中的 oss_url")
    print("=" * 60)

    if args.dry_run:
        print("⚠️  预览模式 - 不会实际修改文件\n")

    # 加载 CSV 映射
    print(f"📂 读取 CSV: {csv_path}")
    mapping = load_oss_mapping(csv_path)
    print(f"   找到 {len(mapping)} 个分组的 URL 映射\n")

    # 更新 metadata
    print("📝 更新 metadata.json:")
    updated, skipped = update_metadata(archive_dir, mapping, args.dry_run)

    print("\n" + "=" * 60)
    print("📊 统计")
    print("=" * 60)
    print(f"   更新: {updated}")
    print(f"   跳过 (已有 oss_url): {skipped}")

    if args.dry_run:
        print("\n💡 这是预览模式，移除 --dry-run 执行实际更新")


if __name__ == "__main__":
    main()
