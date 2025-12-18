#!/usr/bin/env python3
"""
处理新录音文件：
1. MP4转MP3
2. 上传到OSS
3. 创建archive目录结构和metadata.json
"""

import os
import subprocess
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


def convert_mp4_to_mp3(input_path: Path, output_path: Path) -> bool:
    """使用ffmpeg将MP4转换为MP3"""
    try:
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vn",  # 不要视频
            "-acodec", "libmp3lame",
            "-ab", "192k",  # 比特率
            "-ar", "44100",  # 采样率
            "-y",  # 覆盖已存在文件
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ❌ ffmpeg错误: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"  ❌ 转换失败: {e}")
        return False


def upload_to_oss(local_path: Path, oss_key: str) -> str:
    """上传文件到OSS，返回公开URL"""
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

    bucket.put_object_from_file(oss_key, str(local_path))

    return f"{OSS_PUBLIC_BASE_URL}/{oss_key}"


def parse_folder_name(folder_name: str) -> dict:
    """
    解析文件夹名称，提取信息
    例如: Zoe61330_2025-12-15_130-26 -> class_code=Zoe61330, date=2025-12-15, progress=130-26
    progress直接使用原始格式，不做转换
    """
    parts = folder_name.split("_")
    if len(parts) >= 3:
        class_code = parts[0]
        date = parts[1]
        # 直接使用原始progress格式
        progress = parts[2]
        return {
            "class_code": class_code,
            "date": date,
            "progress": progress
        }
    return None


def process_source_folder(source_folder: Path):
    """处理单个源文件夹"""
    folder_name = source_folder.name
    info = parse_folder_name(folder_name)

    if not info:
        print(f"❌ 无法解析文件夹名称: {folder_name}")
        return

    class_code = info["class_code"]
    date = info["date"]
    progress = info["progress"]

    # 创建dataset_id
    dataset_id = f"{class_code}_{date}"

    print(f"\n{'='*60}")
    print(f"处理: {folder_name}")
    print(f"  班级: {class_code}")
    print(f"  日期: {date}")
    print(f"  进度: {progress}")
    print(f"{'='*60}")

    # 创建archive目录
    archive_dataset_dir = ARCHIVE_DIR / dataset_id
    archive_dataset_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有MP4文件
    mp4_files = list(source_folder.glob("*.mp4"))

    if not mp4_files:
        print(f"  ⚠️ 没有找到MP4文件")
        return

    print(f"  找到 {len(mp4_files)} 个MP4文件")

    items = []

    for mp4_file in mp4_files:
        # 提取学生名 (文件名去掉扩展名，首字母大写)
        student_name = mp4_file.stem
        # 规范化学生名：首字母大写
        student_name = student_name.capitalize()

        print(f"\n  处理学生: {student_name}")

        # 创建学生目录
        student_dir = archive_dataset_dir / student_name
        student_dir.mkdir(parents=True, exist_ok=True)

        # 转换后的MP3路径
        mp3_path = student_dir / "1_input_audio.mp3"

        # 1. MP4转MP3
        print(f"    转换 MP4 -> MP3...")
        if not convert_mp4_to_mp3(mp4_file, mp3_path):
            print(f"    ❌ 跳过此学生")
            continue
        print(f"    ✅ 转换完成: {mp3_path}")

        # 2. 上传到OSS
        file_id = f"{dataset_id}_{progress}_{student_name}"
        oss_key = f"audio/{file_id}.mp3"

        print(f"    上传到OSS: {oss_key}")
        try:
            oss_url = upload_to_oss(mp3_path, oss_key)
            print(f"    ✅ 上传完成: {oss_url}")
        except Exception as e:
            print(f"    ❌ 上传失败: {e}")
            continue

        # 记录item信息
        items.append({
            "file_id": file_id,
            "student": student_name,
            "local_path": f"archive/{dataset_id}/{student_name}/1_input_audio.mp3",
            "oss_url": oss_url
        })

    # 3. 创建metadata.json
    metadata = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "class_code": class_code,
        "date": date,
        "progress": progress,
        "question_bank_path": f"questionbank/{progress}.json",
        "items": items,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "notes": f"processed from {folder_name}"
    }

    metadata_path = archive_dataset_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 完成! metadata.json 已创建: {metadata_path}")
    print(f"   处理了 {len(items)} 个学生")


def main():
    # 要处理的源文件夹列表
    source_folders = [
        Path("/Users/damien/Downloads/Niko60900_2025-12-15_R1-20-D5"),
    ]

    print("开始处理录音文件...")
    print(f"Archive目录: {ARCHIVE_DIR}")

    for folder in source_folders:
        if folder.exists():
            process_source_folder(folder)
        else:
            print(f"❌ 文件夹不存在: {folder}")

    print("\n" + "="*60)
    print("全部处理完成!")


if __name__ == "__main__":
    main()
