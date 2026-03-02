#!/usr/bin/env python3
"""
List available batches and students for testing

Usage:
    python list_test_data.py
    python list_test_data.py --batch <batch-id>
"""

import argparse
from pathlib import Path
from datetime import datetime


def format_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def list_batches(archive_dir: Path):
    """List all available batches"""
    batches = []

    for item in sorted(archive_dir.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            # Count students
            student_count = sum(
                1 for x in item.iterdir()
                if x.is_dir() and not x.name.startswith('_') and x.name != 'metadata.json'
            )

            # Get metadata if exists
            metadata_path = item / 'metadata.json'
            has_metadata = metadata_path.exists()

            batches.append({
                'name': item.name,
                'students': student_count,
                'has_metadata': has_metadata,
                'path': item
            })

    if not batches:
        print("No batches found in archive/")
        return

    print("=" * 80)
    print("Available Test Batches")
    print("=" * 80)
    print()

    for batch in batches:
        print(f"  📦 {batch['name']}")
        print(f"     Students: {batch['students']}")
        print(f"     Metadata: {'✅' if batch['has_metadata'] else '❌'}")
        print()

    print(f"Total: {len(batches)} batches")
    print()


def list_students(archive_dir: Path, batch_id: str):
    """List all students in a batch"""
    batch_dir = archive_dir / batch_id

    if not batch_dir.exists():
        print(f"❌ Batch not found: {batch_id}")
        return

    students = []

    for item in sorted(batch_dir.iterdir()):
        if item.is_dir() and not item.name.startswith('_') and item.name != 'metadata.json':
            # Check for audio file
            audio_file = item / '1_input_audio.mp3'
            has_audio = audio_file.exists()
            audio_size = audio_file.stat().st_size if has_audio else 0

            # Check for ASR result
            asr_file = item / '2_qwen_asr.json'
            has_asr = asr_file.exists()

            # Count annotation runs
            runs_dir = item / 'runs'
            run_count = 0
            if runs_dir.exists():
                for annotator_dir in runs_dir.iterdir():
                    if annotator_dir.is_dir():
                        run_count += sum(1 for x in annotator_dir.iterdir() if x.is_dir())

            students.append({
                'name': item.name,
                'has_audio': has_audio,
                'audio_size': audio_size,
                'has_asr': has_asr,
                'runs': run_count,
                'path': item
            })

    if not students:
        print(f"No students found in batch: {batch_id}")
        return

    print("=" * 80)
    print(f"Students in {batch_id}")
    print("=" * 80)
    print()

    for student in students:
        print(f"  👤 {student['name']}")
        print(f"     Audio: {('✅ ' + format_size(student['audio_size'])) if student['has_audio'] else '❌'}")
        print(f"     ASR: {'✅' if student['has_asr'] else '❌'}")
        print(f"     Annotation runs: {student['runs']}")
        print()

    print(f"Total: {len(students)} students")
    print()

    # Summary
    with_audio = sum(1 for s in students if s['has_audio'])
    with_asr = sum(1 for s in students if s['has_asr'])

    print("Summary:")
    print(f"  Students with audio: {with_audio}/{len(students)}")
    print(f"  Students with ASR: {with_asr}/{len(students)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="List available batches and students for testing"
    )
    parser.add_argument(
        '--batch', '-b',
        type=str,
        help='Show students in specific batch'
    )

    args = parser.parse_args()

    # Find project root (script is in skills/quickfire-audio-test/scripts/)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent
    archive_dir = project_root / 'archive'

    if not archive_dir.exists():
        print(f"❌ Archive directory not found: {archive_dir}")
        return 1

    if args.batch:
        list_students(archive_dir, args.batch)
    else:
        list_batches(archive_dir)

    return 0


if __name__ == '__main__':
    exit(main())
