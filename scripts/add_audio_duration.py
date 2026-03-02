#!/usr/bin/env python3
"""
为所有学生的 metadata.json 添加音频时长信息，并生成统计报告
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


def get_audio_duration(audio_path: str) -> float:
    """
    使用 ffprobe 获取音频时长（秒）

    Args:
        audio_path: 音频文件路径

    Returns:
        音频时长（秒），如果失败返回 0.0
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"⚠️  无法获取音频时长: {audio_path} - {e}", file=sys.stderr)
        return 0.0


def format_duration(seconds: float) -> str:
    """
    将秒数格式化为 MM:SS 格式

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def process_metadata(metadata_path: Path, dry_run: bool = False) -> Tuple[int, float, List[Dict]]:
    """
    处理单个 metadata.json 文件，添加音频时长信息

    Args:
        metadata_path: metadata.json 文件路径
        dry_run: 是否为试运行（不实际修改文件）

    Returns:
        (处理的学生数, 总时长, 学生详情列表)
    """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    modified = False
    student_count = 0
    total_duration = 0.0
    student_details = []

    for item in metadata.get('items', []):
        local_path = item.get('local_path')
        if not local_path:
            continue

        # 构建完整路径
        # local_path 是相对于项目根目录的路径，如 "archive/Abby61000_2025-11-05/Benjamin/1_input_audio.mp3"
        audio_path = Path(local_path)

        if not audio_path.exists():
            print(f"⚠️  音频文件不存在: {audio_path}")
            continue

        # 获取音频时长
        duration = get_audio_duration(str(audio_path))

        # 更新 metadata
        if 'duration_seconds' not in item or item['duration_seconds'] != duration:
            item['duration_seconds'] = round(duration, 2)
            modified = True

        student_count += 1
        total_duration += duration

        student_details.append({
            'student': item.get('student', 'Unknown'),
            'duration_seconds': round(duration, 2),
            'duration_formatted': format_duration(duration)
        })

    # 保存修改后的 metadata
    if modified and not dry_run:
        metadata['updated_at'] = datetime.now().isoformat()
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"✅ 已更新: {metadata_path}")
    elif modified:
        print(f"🔍 [试运行] 将更新: {metadata_path}")

    return student_count, total_duration, student_details


def main():
    """主函数"""
    archive_dir = Path('archive')

    if not archive_dir.exists():
        print("❌ archive 目录不存在")
        sys.exit(1)

    # 询问是否为试运行
    print("是否进行试运行（不实际修改文件）？[y/N]: ", end='')
    dry_run = input().strip().lower() == 'y'

    if dry_run:
        print("\n🔍 试运行模式 - 不会修改任何文件\n")
    else:
        print("\n✏️  正式运行模式 - 将修改 metadata.json 文件\n")

    # 收集所有统计数据
    all_stats = []
    total_students = 0
    total_duration = 0.0

    # 遍历所有班级目录
    class_dirs = sorted([d for d in archive_dir.iterdir() if d.is_dir()])

    for class_dir in class_dirs:
        metadata_path = class_dir / 'metadata.json'

        if not metadata_path.exists():
            print(f"⚠️  跳过（无 metadata.json）: {class_dir.name}")
            continue

        try:
            student_count, duration, student_details = process_metadata(metadata_path, dry_run)

            if student_count > 0:
                all_stats.append({
                    'class_dir': class_dir.name,
                    'student_count': student_count,
                    'total_duration': duration,
                    'students': student_details
                })

                total_students += student_count
                total_duration += duration

        except Exception as e:
            print(f"❌ 处理失败: {class_dir.name} - {e}")

    # 生成统计报告
    report_path = Path('audio_duration_stats.md')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 音频时长统计报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        # 总体统计
        f.write("## 总体统计\n\n")
        f.write(f"- **总班级数**: {len(all_stats)}\n")
        f.write(f"- **总学生数**: {total_students}\n")
        f.write(f"- **总音频时长**: {format_duration(total_duration)} ({total_duration:.2f} 秒)\n")

        avg_per_student = total_duration / total_students if total_students > 0 else 0
        f.write(f"- **平均时长/学生**: {format_duration(avg_per_student)} ({avg_per_student:.2f} 秒)\n\n")

        # 按班级统计
        f.write("## 按班级统计\n\n")
        f.write("| 班级 | 学生数 | 总时长 | 平均时长 |\n")
        f.write("|------|--------|--------|----------|\n")

        for stat in all_stats:
            avg_duration = stat['total_duration'] / stat['student_count']
            f.write(f"| {stat['class_dir']} | {stat['student_count']} | "
                   f"{format_duration(stat['total_duration'])} | "
                   f"{format_duration(avg_duration)} |\n")

        # 详细信息
        f.write("\n## 详细信息\n\n")

        for stat in all_stats:
            f.write(f"### {stat['class_dir']}\n\n")
            f.write("| 学生 | 音频时长 |\n")
            f.write("|------|----------|\n")

            for student in stat['students']:
                f.write(f"| {student['student']} | {student['duration_formatted']} |\n")

            f.write(f"\n**小计**: {stat['student_count']} 个学生，总时长 {format_duration(stat['total_duration'])}\n\n")

    print(f"\n{'='*60}")
    print(f"✅ 统计报告已生成: {report_path}")
    print(f"{'='*60}\n")
    print(f"📊 总体统计:")
    print(f"   - 总班级数: {len(all_stats)}")
    print(f"   - 总学生数: {total_students}")
    print(f"   - 总音频时长: {format_duration(total_duration)} ({total_duration:.2f} 秒)")

    avg_per_student = total_duration / total_students if total_students > 0 else 0
    print(f"   - 平均时长/学生: {format_duration(avg_per_student)}")
    print()


if __name__ == '__main__':
    main()
