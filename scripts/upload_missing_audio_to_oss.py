#!/usr/bin/env python3
"""
为缺少 OSS URL 的学生上传音频到 OSS
"""

import os
import json
from datetime import datetime
from pathlib import Path
import oss2
from dotenv import load_dotenv

# 加载环境变量
SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

# OSS配置
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "").strip()
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "").strip()
OSS_PUBLIC_BASE_URL = os.getenv("OSS_PUBLIC_BASE_URL", "").strip()

# 项目路径
PROJECT_ROOT = SCRIPT_DIR.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive"


def upload_to_oss(local_path: Path, oss_key: str) -> str:
    """上传文件到OSS，返回公开URL"""
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

    bucket.put_object_from_file(oss_key, str(local_path))

    return f"{OSS_PUBLIC_BASE_URL}/{oss_key}"


def create_or_update_metadata(batch_dir: Path, batch_id: str, student_name: str, oss_url: str, progress: str):
    """创建或更新 metadata.json"""
    metadata_path = batch_dir / "metadata.json"

    # 解析 batch_id
    parts = batch_id.split("_")
    class_code = parts[0]
    date = parts[1]

    if metadata_path.exists():
        # 更新已有 metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # 查找对应的 item
        found = False
        for item in metadata.get("items", []):
            if item["student"] == student_name:
                item["oss_url"] = oss_url
                found = True
                break

        if not found:
            # 添加新 item
            file_id = f"{batch_id}_{progress}_{student_name}"
            metadata.setdefault("items", []).append({
                "file_id": file_id,
                "student": student_name,
                "local_path": f"archive/{batch_id}/{student_name}/1_input_audio.mp3",
                "oss_url": oss_url
            })

        metadata["updated_at"] = datetime.now().isoformat()
    else:
        # 创建新 metadata
        file_id = f"{batch_id}_{progress}_{student_name}"
        metadata = {
            "schema_version": 1,
            "dataset_id": batch_id,
            "class_code": class_code,
            "date": date,
            "progress": progress,
            "question_bank_path": f"questionbank/{progress}.json",
            "items": [{
                "file_id": file_id,
                "student": student_name,
                "local_path": f"archive/{batch_id}/{student_name}/1_input_audio.mp3",
                "oss_url": oss_url
            }],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "notes": "OSS URL added by upload_missing_audio_to_oss.py"
        }

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata_path


def process_batch(batch_id: str, student_name: str, progress: str):
    """处理单个批次的学生"""
    batch_dir = ARCHIVE_DIR / batch_id
    student_dir = batch_dir / student_name
    audio_file = student_dir / "1_input_audio.mp3"

    if not audio_file.exists():
        print(f"  ❌ 音频文件不存在: {audio_file}")
        return False

    # 构造 file_id 和 OSS key
    file_id = f"{batch_id}_{progress}_{student_name}"
    oss_key = f"audio/{file_id}.mp3"

    print(f"  上传: {oss_key}")

    try:
        oss_url = upload_to_oss(audio_file, oss_key)
        print(f"  ✅ OSS URL: {oss_url}")

        # 更新 metadata.json
        metadata_path = create_or_update_metadata(batch_dir, batch_id, student_name, oss_url, progress)
        print(f"  ✅ 已更新 metadata: {metadata_path}")

        return True
    except Exception as e:
        print(f"  ❌ 上传失败: {e}")
        return False


def main():
    # 待处理的批次
    batches = [
        ("Zoe61330_2025-12-29", "Cici", "130-28-EC"),
        ("Zoe61330_2025-12-29", "Lucy", "130-28-EC"),
        ("Zoe61330_2025-12-29", "Apollo", "130-28-EC"),
        ("Zoe61330_2025-12-30", "Apollo", "130-27-EC"),
        ("Zoe61330_2025-12-30", "Jessie", "130-27-EC"),
        ("Zoe61330_2025-12-30", "Noreen", "130-27-EC"),
        ("Zoe61330_2025-12-30", "Cici", "130-27-EC"),
    ]

    print("="*60)
    print("上传缺失的音频文件到 OSS")
    print("="*60)

    success = 0
    failed = 0

    for batch_id, student_name, progress in batches:
        print(f"\n处理: {batch_id} / {student_name}")
        if process_batch(batch_id, student_name, progress):
            success += 1
        else:
            failed += 1

    print("\n" + "="*60)
    print("完成统计")
    print("="*60)
    print(f"  成功: {success}")
    print(f"  失败: {failed}")


if __name__ == "__main__":
    main()
