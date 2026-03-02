"""
Qwen3-ASR 音频转写系统 - 支持多种输入模式

【输入来源】
1. Archive 批处理模式（推荐）：
   - 目录结构：archive/{class_code}_{date}/{student}/1_input_audio.*
   - 题库来源：archive/{class_code}_{date}/metadata.json -> question_bank_file
   - 命令：python3 qwen_asr.py --archive-batch Zoe41900_2025-09-08

2. backend_input 模式：
   - 文件格式：{ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3
   - 例如：Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
   - 题库自动从 questionbank/ 目录查找

3. 旧模式：archive/<dataset>/<student>/ 目录结构（向后兼容）
   - 音频来源：archive/<dataset>/<student>/1_input_audio.* 或 <StudentName>.*
   - 使用函数：process_student() / process_dataset()

【输出结构】
- Archive 模式：输出到 archive/{class}_{date}/{student}/2_qwen_asr.json
- backend_input 模式：输出到 asr/{学生名字}.json + asr/{学生名字}_metadata.json

【命令行用法】
  # Archive 批处理模式（推荐）
  python3 qwen_asr.py --archive-batch Zoe41900_2025-09-08  # 处理整个班级
  python3 qwen_asr.py --archive-batch Zoe41900_2025-09-08 --student Oscar  # 单个学生

  # backend_input 模式
  python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3  # 单个文件
  python3 qwen_asr.py --class Abby61000 --date 2025-10-30  # 批量处理
  python3 qwen_asr.py --all  # 处理所有文件

  # 旧模式（向后兼容）
  python3 qwen_asr.py --dataset Zoe51530-9.8  # 转写指定数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # 转写单个学生
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 确保项目根目录在 Python path 中
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 统一加载环境变量
from scripts.common.env import load_env
load_env()

# 导入公共工具函数
from scripts.common.naming import parse_backend_input_mp3_name
from scripts.common.archive import find_audio_file as _find_audio_file_common, resolve_question_bank

# 导入 ASR Provider（核心转写逻辑已抽取到 scripts/asr/qwen.py）
from scripts.asr.qwen import QwenASRProvider


# ===== 数据集和学生发现辅助函数 =====

def parse_dataset_name(dataset_name: str) -> Tuple[str, str]:
    """
    解析数据集名称为课程代码和日期。

    格式: CourseName-Date (例如: Zoe51530-9.8)

    Args:
        dataset_name: 数据集名称

    Returns:
        (course_code, date) 元组

    Raises:
        ValueError: 格式无效时
    """
    parts = dataset_name.rsplit('-', 1)
    if len(parts) != 2:
        raise ValueError(f"无效的数据集名称格式: {dataset_name}。应为: CourseName-Date (例如: Zoe51530-9.8)")

    course_code, date = parts
    if not course_code or not date:
        raise ValueError(f"无效的数据集名称: {dataset_name}")

    return course_code, date


def find_datasets() -> List[str]:
    """
    发现 archive 目录下的所有数据集。

    Returns:
        数据集名称列表 (例如: ["Zoe51530-9.8", "Zoe41900-9.8", ...])
    """
    project_root = Path(__file__).parent.parent
    archive_path = project_root / "archive"

    if not archive_path.exists():
        return []

    datasets = []
    for item in archive_path.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            datasets.append(item.name)

    return sorted(datasets)


def find_students_in_dataset(dataset_name: str) -> List[str]:
    """
    发现指定数据集中的所有学生。

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)

    Returns:
        学生名称列表
    """
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "archive" / dataset_name

    if not dataset_path.exists():
        return []

    students = []
    for student_dir in dataset_path.iterdir():
        if student_dir.is_dir() and not student_dir.name.startswith('_'):
            students.append(student_dir.name)

    return sorted(students)


def resolve_dataset_path(dataset_name: str) -> Path:
    """
    解析数据集名称为文件系统路径。

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)

    Returns:
        Path 对象指向 archive/<dataset_name>/

    Raises:
        ValueError: 数据集不存在时
    """
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "archive" / dataset_name

    if not dataset_path.exists():
        raise ValueError(f"数据集不存在: archive/{dataset_name}/")

    return dataset_path


def find_vocabulary_file(shared_context_dir: Path) -> Optional[Path]:
    """
    在 _shared_context 目录中自动查找题库文件。

    优先级顺序:
    1. vocabulary.json (标准词汇表)
    2. R*.json (JSON 格式题库)
    3. R*.csv (CSV 格式题库，如 R3-14.csv、R1-65.csv)
    4. 任何其他 .csv 文件
    5. 无则返回 None

    Args:
        shared_context_dir: _shared_context 目录路径

    Returns:
        词汇/题库文件 Path 对象，或 None
    """
    if not shared_context_dir.exists():
        return None

    # 优先级 1: vocabulary.json
    vocab_json = shared_context_dir / "vocabulary.json"
    if vocab_json.exists():
        return vocab_json

    # 优先级 2: R*.json
    for r_json in shared_context_dir.glob("R*.json"):
        if r_json.is_file():
            return r_json

    # 优先级 3: R*.csv (题库，如 R3-14.csv、R1-65.csv)
    r_csv_files = sorted(shared_context_dir.glob("R*.csv"))
    for r_csv in r_csv_files:
        if r_csv.is_file() and "vocabulary" not in r_csv.name.lower():
            return r_csv

    # 优先级 4: 任何 .csv
    for csv_file in shared_context_dir.glob("*.csv"):
        if csv_file.is_file() and "vocabulary" not in csv_file.name.lower():
            return csv_file

    return None


def find_audio_file(student_dir: Path) -> Optional[Path]:
    """
    发现学生目录中的音频文件。

    已迁移到 scripts.common.archive.find_audio_file，此函数为兼容性别名。
    """
    return _find_audio_file_common(student_dir)


def should_process(student_name: str) -> bool:
    """
    检查学生是否应该被处理（即是否已存在输出文件）。

    Args:
        student_name: 学生名称

    Returns:
        True 如果应该处理（文件不存在），False 如果应该跳过（文件存在）
    """
    project_root = Path(__file__).parent.parent
    asr_dir = project_root / "asr"
    output_file = asr_dir / f"{student_name}.json"
    return not output_file.exists()


def parse_audio_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    解析 backend_input 音频文件名。

    已迁移到 scripts.common.naming.parse_backend_input_mp3_name，此函数为兼容性别名。
    """
    return parse_backend_input_mp3_name(filename)


def find_questionbank_file(question_bank_code: str) -> Optional[Path]:
    """
    在 questionbank/ 目录中查找题库文件，支持多级 fallback。
    """
    project_root = Path(__file__).parent.parent
    questionbank_dir = project_root / "questionbank"

    if not questionbank_dir.exists():
        return None

    exact = questionbank_dir / f"{question_bank_code}.json"
    if exact.exists():
        return exact

    for f in sorted(questionbank_dir.glob(f"{question_bank_code}*.json")):
        if f.is_file():
            return f

    parts = question_bank_code.rsplit('-', 1)
    if len(parts) == 2:
        prefix = parts[0]
        for f in sorted(questionbank_dir.glob(f"{prefix}-*.json")):
            if f.is_file():
                return f

    if '-' in question_bank_code:
        parts = question_bank_code.split('-')
        if len(parts) >= 2:
            short_code = f"{parts[0]}-{parts[1]}"
            short_file = questionbank_dir / f"{short_code}.json"
            if short_file.exists():
                return short_file

    return None


def discover_backend_files(
    class_code: Optional[str] = None,
    date: Optional[str] = None,
    student: Optional[str] = None,
    question_bank: Optional[str] = None
) -> List[Path]:
    """
    在 backend_input 目录中发现音频文件并按条件过滤。
    """
    project_root = Path(__file__).parent.parent
    backend_input_dir = project_root / "backend_input"

    if not backend_input_dir.exists():
        return []

    files: List[Path] = []
    for f in backend_input_dir.glob("*.mp3"):
        parsed = parse_audio_filename(f.name)
        if not parsed:
            continue

        if class_code and parsed["class_code"] != class_code:
            continue
        if date and parsed["date"] != date:
            continue
        if student and student.lower() not in parsed["student_name"].lower():
            continue
        if question_bank and parsed["question_bank"] != question_bank:
            continue

        files.append(f)

    return sorted(files)


def process_backend_file(audio_file_path: str, api_key: Optional[str] = None) -> int:
    """
    处理单个 backend_input 音频文件。
    """
    try:
        project_root = Path(__file__).parent.parent
        audio_file = Path(audio_file_path)

        if not audio_file.exists():
            print(f"❌ 文件不存在: {audio_file}")
            return 1

        parsed = parse_audio_filename(audio_file.name)
        if not parsed:
            print(f"❌ 文件名格式无效: {audio_file.name}")
            print("   预期格式: {ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3")
            return 1

        student_name = parsed["student_name"]

        if not should_process(student_name):
            print(f"  ✓ {student_name}: 已处理过（跳过）")
            return 0

        qb_code = parsed["question_bank"]
        vocab_file = None
        qb_path = find_questionbank_file(qb_code)
        if qb_path:
            vocab_file = str(qb_path)
            print(f"   📚 题库: {qb_path.name}")
        else:
            print(f"   ⚠️  未找到题库: {qb_code}")

        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误: {str(e)}")
            return 1

        asr_dir = project_root / "asr"
        asr_dir.mkdir(parents=True, exist_ok=True)

        print(f"  ⟳ {student_name}: 处理音频...")
        provider.transcribe_and_save_with_segmentation(
            input_audio_path=str(audio_file),
            output_dir=str(asr_dir),
            vocabulary_path=vocab_file,
            output_filename=f"{student_name}.json",
            language="zh",
            segment_duration=180,
            max_workers=3,
        )

        metadata = {
            "class_code": parsed["class_code"],
            "date": parsed["date"],
            "question_bank": parsed["question_bank"],
            "student": student_name,
            "audio_file": audio_file.name,
            "processed_at": datetime.datetime.now().isoformat(),
        }

        metadata_file = asr_dir / f"{student_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  ✓ {student_name}: 已保存到 asr/{student_name}.json")
        return 0

    except Exception as e:
        print(f"  ✗ 处理失败: {str(e)}")
        return 1


def process_backend_files_batch(
    class_code: Optional[str] = None,
    date: Optional[str] = None,
    student: Optional[str] = None,
    question_bank: Optional[str] = None,
    api_key: Optional[str] = None
) -> Tuple[int, int]:
    """
    批量处理 backend_input 中的音频文件。
    """
    files = discover_backend_files(
        class_code=class_code,
        date=date,
        student=student,
        question_bank=question_bank
    )

    if not files:
        print("❌ 没有找到符合条件的音频文件")
        return 0, 0

    print(f"\n{'='*60}")
    print(f"处理 {len(files)} 个文件")
    print(f"{'='*60}\n")

    processed = 0
    skipped = 0

    for audio_file in files:
        exit_code = process_backend_file(str(audio_file), api_key=api_key)
        if exit_code == 0:
            processed += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"处理完成！处理: {processed}, 失败: {skipped}")
    print(f"{'='*60}")

    return processed, skipped


# ===== Archive 批处理模式 =====

def load_archive_metadata(archive_batch: str) -> Dict[str, Any]:
    """
    加载 archive/{class}_{date}/metadata.json

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）

    Returns:
        metadata 字典

    Raises:
        FileNotFoundError: metadata.json 不存在
    """
    project_root = Path(__file__).parent.parent
    metadata_path = project_root / "archive" / archive_batch / "metadata.json"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json 不存在: {metadata_path}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_archive_students(archive_batch: str) -> List[str]:
    """
    发现 archive/{class}_{date}/ 下的所有学生目录

    Args:
        archive_batch: 分组名称

    Returns:
        学生名称列表
    """
    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive" / archive_batch

    if not archive_dir.exists():
        return []

    students = []
    for item in archive_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            students.append(item.name)

    return sorted(students)


def find_archive_audio_file(student_dir: Path) -> Optional[Path]:
    """
    查找学生目录中的音频文件

    Args:
        student_dir: 学生目录路径

    Returns:
        音频文件路径，或 None
    """
    audio_formats = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg'}

    # 优先级 1: 1_input_audio.*
    for audio_file in student_dir.glob('1_input_audio.*'):
        if audio_file.suffix.lower() in audio_formats:
            return audio_file

    # 优先级 2: 任何音频文件
    for audio_file in student_dir.glob('*'):
        if audio_file.is_file() and audio_file.suffix.lower() in audio_formats:
            return audio_file

    return None


def should_process_archive_student(student_dir: Path) -> bool:
    """
    检查学生是否应该被处理（是否已存在 2_qwen_asr.json）

    Args:
        student_dir: 学生目录路径

    Returns:
        True 如果应该处理，False 如果应该跳过
    """
    output_file = student_dir / "2_qwen_asr.json"
    return not output_file.exists()


def process_archive_student(
    archive_batch: str,
    student_name: str,
    vocabulary_path: Optional[str] = None,
    api_key: Optional[str] = None,
    force: bool = False
) -> int:
    """
    处理单个 archive 学生的 ASR 转写

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）
        student_name: 学生名称
        vocabulary_path: 词汇表路径
        api_key: API 密钥
        force: 是否强制重新处理

    Returns:
        0 成功，1 错误
    """
    project_root = Path(__file__).parent.parent
    student_dir = project_root / "archive" / archive_batch / student_name

    if not student_dir.exists():
        print(f"  ✗ {student_name}: 目录不存在")
        return 1

    # 检查是否需要处理
    if not force and not should_process_archive_student(student_dir):
        print(f"  ✓ {student_name}: 已处理过（跳过）")
        return 0

    # 查找音频文件
    audio_file = find_archive_audio_file(student_dir)
    if not audio_file:
        print(f"  ⊘ {student_name}: 未找到音频文件")
        return 1

    try:
        # 创建 ASR 提供者
        provider = QwenASRProvider(api_key=api_key)

        # 转写并保存到学生目录
        print(f"  ⟳ {student_name}: 处理音频...")
        provider.transcribe_and_save_with_segmentation(
            input_audio_path=str(audio_file),
            output_dir=str(student_dir),
            vocabulary_path=vocabulary_path,
            output_filename="2_qwen_asr.json",
            language="zh",
            segment_duration=180,
            max_workers=3,
        )

        print(f"  ✓ {student_name}: 已保存到 2_qwen_asr.json")
        return 0

    except Exception as e:
        print(f"  ✗ {student_name}: 错误 - {str(e)}")
        return 1


def process_archive_batch(
    archive_batch: str,
    student_name: Optional[str] = None,
    api_key: Optional[str] = None,
    force: bool = False
) -> Tuple[int, int]:
    """
    批量处理 archive/{class}_{date}/ 下的所有学生

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）
        student_name: 可选的单个学生名称
        api_key: API 密钥
        force: 是否强制重新处理

    Returns:
        (成功数, 跳过/失败数)
    """
    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive" / archive_batch

    if not archive_dir.exists():
        print(f"❌ Archive 目录不存在: {archive_dir}")
        return 0, 0

    print(f"\n{'='*60}")
    print(f"📁 Archive 批处理: {archive_batch}")
    print(f"{'='*60}")

    # 加载 metadata
    try:
        metadata = load_archive_metadata(archive_batch)
        print(f"   班级: {metadata.get('class_code', 'N/A')}")
        print(f"   日期: {metadata.get('date', 'N/A')}")
        print(f"   进度: {metadata.get('progress', 'N/A')}")
    except FileNotFoundError as e:
        print(f"⚠️  {e}")
        metadata = {}

    # 查找题库文件（统一使用 common/archive.py 的 resolve_question_bank）
    vocab_file = resolve_question_bank(archive_batch, metadata)
    if vocab_file:
        print(f"   📚 题库: {vocab_file.name}")
    else:
        print(f"   ⚠️  未找到题库文件")

    # 获取学生列表
    if student_name:
        students = [student_name]
    else:
        students = find_archive_students(archive_batch)

    if not students:
        print("   ⊘ 未找到任何学生")
        return 0, 0

    print(f"   👥 学生数: {len(students)}")

    # 处理学生
    processed = 0
    skipped = 0

    for student in students:
        exit_code = process_archive_student(
            archive_batch,
            student,
            vocabulary_path=str(vocab_file) if vocab_file else None,
            api_key=api_key,
            force=force
        )
        if exit_code == 0:
            processed += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"✅ 处理完成！成功: {processed}, 跳过/失败: {skipped}")
    print(f"{'='*60}")

    return processed, skipped


# ===== 旧模式处理函数（向后兼容） =====

def process_student(dataset_name: str, student_name: str, api_key: Optional[str] = None) -> int:
    """
    处理单个学生的音频转写。

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)
        student_name: 学生名称 (例如: Alvin)
        api_key: DashScope API 密钥 (可选，默认从环境变量读取)

    Returns:
        0 成功，1 错误
    """
    try:
        # 构造学生目录路径
        project_root = Path(__file__).parent.parent
        student_dir = project_root / "archive" / dataset_name / student_name

        # 验证学生目录是否存在
        if not student_dir.exists():
            print(f"❌ 错误：学生目录不存在: {student_dir}/")
            return 1

        # 查找音频文件
        audio_file = find_audio_file(student_dir)
        if not audio_file:
            print(f"  ⊘ {student_name}: 未找到音频文件")
            return 0

        # 检查是否应该处理
        if not should_process(student_name):
            print(f"  ✓ {student_name}: 已处理过（跳过）")
            return 0

        # 创建 ASR 提供者
        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误：{str(e)}")
            return 1

        # 创建输出目录
        project_root = Path(__file__).parent.parent
        asr_dir = project_root / "asr"
        asr_dir.mkdir(parents=True, exist_ok=True)

        # 查找词汇文件（优先级：vocabulary.json > R*.json > R*.csv > *.csv）
        shared_context = student_dir.parent / "_shared_context"
        vocab_file = None
        if shared_context.exists():
            vocab_path = find_vocabulary_file(shared_context)
            if vocab_path:
                vocab_file = str(vocab_path)
                print(f"   📚 题库: {vocab_path.name}")

        # 转写并保存（支持长音频分段处理）
        print(f"  ⟳ {student_name}: 处理音频...")
        response = provider.transcribe_and_save_with_segmentation(
            input_audio_path=str(audio_file),
            output_dir=str(asr_dir),
            vocabulary_path=vocab_file,
            output_filename=f"{student_name}.json",
            language="zh",
            segment_duration=180,  # 3 分钟
            max_workers=3,
        )

        # 保存元数据
        class_code = None
        record_date = None
        try:
            class_code, record_date = parse_dataset_name(dataset_name)
        except ValueError:
            pass

        metadata = {
            "dataset": dataset_name,
            "student": student_name,
            "audio_file": audio_file.name,
            "processed_at": str(datetime.datetime.now().isoformat()),
        }

        if class_code:
            metadata["class_code"] = class_code
        if record_date:
            metadata["date"] = record_date
        if vocab_file:
            metadata["question_bank"] = Path(vocab_file).stem

        metadata_file = asr_dir / f"{student_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  ✓ {student_name}: 已保存到 asr/{student_name}.json")
        return 0

    except Exception as e:
        print(f"  ✗ {student_name}: 错误 - {str(e)}")
        return 1


def process_dataset(dataset_name: str, api_key: Optional[str] = None) -> Tuple[int, int]:
    """
    处理整个数据集中的所有学生。

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)
        api_key: DashScope API 密钥 (可选，默认从环境变量读取)

    Returns:
        (processed_count, skipped_count) 元组
    """
    try:
        # 验证数据集
        dataset_path = resolve_dataset_path(dataset_name)

        print(f"\n{'='*60}")
        print(f"处理数据集: {dataset_name}")
        print(f"{'='*60}")

        class_code = None
        record_date = None
        try:
            class_code, record_date = parse_dataset_name(dataset_name)
        except ValueError:
            pass

        # 创建 ASR 提供者
        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误：{str(e)}")
            return 0, 0

        # 查找词汇文件（优先级：vocabulary.json > R*.json > R*.csv > *.csv）
        shared_context = dataset_path / "_shared_context"
        vocab_file = None
        if shared_context.exists():
            vocab_path = find_vocabulary_file(shared_context)
            if vocab_path:
                vocab_file = str(vocab_path)
                print(f"   📚 题库: {vocab_path.name}")

        # 发现并处理所有学生
        student_names = find_students_in_dataset(dataset_name)
        total_processed = 0
        total_skipped = 0

        for student_name in student_names:
            student_dir = dataset_path / student_name

            # 查找音频文件
            audio_file = find_audio_file(student_dir)
            if not audio_file:
                print(f"  ⊘ {student_name}: 未找到音频文件")
                total_skipped += 1
                continue

            # 检查是否应该处理
            if not should_process(student_name):
                print(f"  ✓ {student_name}: 已处理过（跳过）")
                total_skipped += 1
                continue

            # 创建输出目录
            project_root = Path(__file__).parent.parent
            asr_dir = project_root / "asr"
            asr_dir.mkdir(parents=True, exist_ok=True)

            # 转写并保存（支持长音频分段处理）
            try:
                print(f"  ⟳ {student_name}: 处理音频...")
                response = provider.transcribe_and_save_with_segmentation(
                    input_audio_path=str(audio_file),
                    output_dir=str(asr_dir),
                    vocabulary_path=vocab_file,
                    output_filename=f"{student_name}.json",
                    language="zh",
                    segment_duration=180,  # 3 分钟
                    max_workers=3,
                )

                # 保存元数据
                metadata = {
                    "dataset": dataset_name,
                    "student": student_name,
                    "audio_file": audio_file.name,
                    "processed_at": str(datetime.datetime.now().isoformat()),
                }

                if class_code:
                    metadata["class_code"] = class_code
                if record_date:
                    metadata["date"] = record_date
                if vocab_file:
                    metadata["question_bank"] = Path(vocab_file).stem

                metadata_file = asr_dir / f"{student_name}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)

                print(f"  ✓ {student_name}: 已保存到 asr/{student_name}.json")
                total_processed += 1

            except Exception as e:
                print(f"  ✗ {student_name}: 错误 - {str(e)}")
                total_skipped += 1

        print(f"\n{'='*60}")
        print(f"处理完成！")
        print(f"处理: {total_processed}, 跳过: {total_skipped}")
        print(f"{'='*60}")

        return total_processed, total_skipped

    except ValueError as e:
        print(f"❌ 错误：{str(e)}")
        return 0, 0


def main():
    """
    主入口点 - 支持三种模式：
    1. Archive 批处理模式（推荐）：处理 archive/{class}_{date}/ 结构
    2. backend_input 模式：处理 backend_input 目录中的文件
    3. 旧模式：处理 archive/<dataset>/<student>/ 结构（向后兼容）
    """
    parser = argparse.ArgumentParser(
        description='Qwen ASR 批量转写工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # Archive 批处理模式（推荐）
  python3 qwen_asr.py --archive-batch Zoe41900_2025-09-08
  python3 qwen_asr.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # backend_input 模式 - 单个文件
  python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

  # backend_input 模式 - 批量处理
  python3 qwen_asr.py --class Abby61000 --date 2025-10-30
  python3 qwen_asr.py --all

  # 旧模式 - 向后兼容
  python3 qwen_asr.py --dataset Zoe51530-9.8
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
        """
    )

    parser.add_argument(
        'input_file',
        nargs='?',
        default=None,
        help='单个音频文件路径 (例如: backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3)'
    )

    # Archive 批处理模式参数
    parser.add_argument(
        '--archive-batch',
        type=str,
        help='Archive 批处理模式 (例如: Zoe41900_2025-09-08)'
    )

    parser.add_argument('--class', dest='class_code', help='班级代码 (例如: Abby61000)')
    parser.add_argument('--date', help='日期 (例如: 2025-10-30)')
    parser.add_argument('--student', help='学生名字 (支持模糊匹配)')
    parser.add_argument('--question-bank', help='题库代码 (例如: R1-27-D2)')
    parser.add_argument('--all', action='store_true', help='处理 backend_input 中的所有文件')
    parser.add_argument('--force', action='store_true', help='强制重新处理已处理过的学生')

    # 旧模式参数（向后兼容）
    parser.add_argument(
        '--dataset',
        type=str,
        help='数据集名称 (例如: Zoe51530-9.8)。格式: CourseName-Date'
    )

    parser.add_argument(
        '--api-key',
        type=str,
        help='DashScope API 密钥 (可选，默认从 DASHSCOPE_API_KEY 环境变量读取)'
    )

    args = parser.parse_args()

    # 获取 API 密钥
    api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 DASHSCOPE_API_KEY 环境变量或通过 --api-key 传递")
        sys.exit(1)

    try:
        # Archive 批处理模式（推荐）
        if args.archive_batch:
            processed, skipped = process_archive_batch(
                args.archive_batch,
                student_name=args.student,
                api_key=api_key,
                force=args.force
            )
            sys.exit(0 if (processed > 0 or skipped > 0) else 1)

        # 旧模式处理（向后兼容）
        if args.dataset:
            if args.student:
                exit_code = process_student(args.dataset, args.student, api_key=api_key)
                sys.exit(exit_code)

            processed, skipped = process_dataset(args.dataset, api_key=api_key)
            sys.exit(0 if (processed > 0 or skipped > 0) else 1)

        # backend_input 模式：单文件
        if args.input_file:
            exit_code = process_backend_file(args.input_file, api_key=api_key)
            sys.exit(exit_code)

        # backend_input 模式：批量
        if args.all or args.class_code or args.date or args.question_bank:
            processed, skipped = process_backend_files_batch(
                class_code=args.class_code,
                date=args.date,
                student=args.student,
                question_bank=args.question_bank,
                api_key=api_key
            )
            sys.exit(0 if (processed > 0 or skipped > 0) else 1)

        # 无参数时显示帮助
        parser.print_help()
        sys.exit(1)

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
