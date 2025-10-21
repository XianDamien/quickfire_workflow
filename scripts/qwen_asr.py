"""
Qwen3-ASR provider for audio transcription with vocabulary context.
Uses custom vocabulary from manifest to improve ASR accuracy.

支持命令行批量转写功能：
  python3 qwen_asr.py                                    # 转写所有数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8            # 转写指定数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # 转写单个学生
"""

import os
import sys
import json
import argparse
import dashscope
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

load_dotenv()


class QwenASRProvider:
    """Qwen3-ASR provider for audio transcription with custom vocabulary."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Qwen ASR provider.

        Args:
            api_key: DashScope API key. If None, uses DASHSCOPE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        self.model = "qwen3-asr-flash"

    @staticmethod
    def load_vocabulary(vocab_path: str) -> Dict[str, list]:
        """
        Load vocabulary from JSON file.
        Handles UTF-8 BOM if present.

        Args:
            vocab_path: Path to vocabulary JSON file

        Returns:
            Dictionary with vocabulary entries
        """
        with open(vocab_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

    @staticmethod
    def build_context_text(vocabulary: Dict[str, list]) -> str:
        """
        Build context text from vocabulary for ASR optimization.

        Args:
            vocabulary: Dictionary with vocabulary entries

        Returns:
            Formatted context text for ASR
        """
        # Extract English terms and Chinese meanings
        terms = []
        for key, values in vocabulary.items():
            if isinstance(values, list) and len(values) >= 2:
                chinese_term = values[0]
                english_term = values[1]
                terms.append(f"{chinese_term}({english_term})")

        # Create context string
        context = "Domain vocabulary: " + ", ".join(terms)
        return context

    def transcribe_audio(
        self,
        audio_path: str,
        vocabulary_path: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        enable_lid: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Qwen3-ASR with optional vocabulary context.

        Args:
            audio_path: Path or URL to audio file
            vocabulary_path: Optional path to vocabulary JSON file for context
            language: Optional language code (e.g., "zh" for Chinese)
            enable_itn: Enable inverse text normalization
            enable_lid: Enable language identification

        Returns:
            Response dictionary with transcription results
        """
        # Build vocabulary context if provided
        system_context = ""
        if vocabulary_path and os.path.exists(vocabulary_path):
            vocab = self.load_vocabulary(vocabulary_path)
            system_context = self.build_context_text(vocab)

        # Build ASR options
        asr_options = {
            "enable_itn": enable_itn,
            "enable_lid": enable_lid,
        }
        if language:
            asr_options["language"] = language

        # Build messages
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "text": system_context if system_context else "You are an ASR assistant. Transcribe the audio accurately."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {"audio": audio_path}
                ]
            }
        ]

        # Call ASR API
        response = dashscope.MultiModalConversation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            result_format="message",
            asr_options=asr_options
        )

        return response

    def transcribe_and_save(
        self,
        input_audio_path: str,
        output_dir: str,
        vocabulary_path: Optional[str] = None,
        output_filename: str = "5_qwen_asr_output.json",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio and save results to file.

        Args:
            input_audio_path: Path or URL to input audio
            output_dir: Directory to save output files
            vocabulary_path: Optional path to vocabulary JSON file
            output_filename: Name of output JSON file
            language: Optional language code

        Returns:
            Response dictionary with transcription results
        """
        # Transcribe audio
        response = self.transcribe_audio(
            audio_path=input_audio_path,
            vocabulary_path=vocabulary_path,
            language=language,
        )

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Save response
        output_path = os.path.join(output_dir, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        print(f"ASR transcription saved to: {output_path}")
        return response


def process_all_students():
    """Process all student audio files in archive directory."""
    # Set up paths
    project_root = Path(__file__).parent.parent
    archive_path = project_root / "archive"

    # Find all course folders
    course_folders = sorted([d for d in archive_path.iterdir() if d.is_dir() and not d.name.startswith("_")])

    print(f"Found {len(course_folders)} course folders")

    # Create provider
    provider = QwenASRProvider()

    total_processed = 0
    total_skipped = 0

    for course_folder in course_folders:
        print(f"\n{'='*60}")
        print(f"Processing course: {course_folder.name}")
        print(f"{'='*60}")

        # Find vocabulary file for this course
        shared_context = course_folder / "_shared_context"
        vocab_file = None

        if shared_context.exists():
            # Look for vocabulary.json first, then CSV files
            vocab_json = shared_context / "vocabulary.json"
            if vocab_json.exists():
                vocab_file = str(vocab_json)
            else:
                # Find first CSV file
                csv_files = list(shared_context.glob("*.csv"))
                if csv_files:
                    vocab_file = str(csv_files[0])

        # Find all student folders
        student_folders = sorted([d for d in course_folder.iterdir() if d.is_dir() and not d.name.startswith("_")])

        for student_folder in student_folders:
            input_audio = student_folder / "1_input_audio.mp3"

            # Check if audio file exists
            if not input_audio.exists():
                print(f"  ⊘ {student_folder.name}: No audio file found")
                total_skipped += 1
                continue

            output_filename = "2_qwen_asr.json"
            output_path = student_folder / output_filename

            # Skip if already processed
            if output_path.exists():
                print(f"  ✓ {student_folder.name}: Already processed (skipping)")
                total_skipped += 1
                continue

            try:
                print(f"  ⟳ {student_folder.name}: Processing audio...")

                # Transcribe with vocabulary context
                response = provider.transcribe_and_save(
                    input_audio_path=str(input_audio),
                    output_dir=str(student_folder),
                    vocabulary_path=vocab_file,
                    output_filename=output_filename,
                    language="zh",  # Chinese language
                )

                print(f"  ✓ {student_folder.name}: Saved to {output_filename}")
                total_processed += 1

            except Exception as e:
                print(f"  ✗ {student_folder.name}: Error - {str(e)}")
                total_skipped += 1

    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"Processed: {total_processed}, Skipped: {total_skipped}")
    print(f"{'='*60}")


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


def find_audio_file(student_dir: Path) -> Optional[Path]:
    """
    发现学生目录中的音频文件。

    优先级顺序:
    1. 1_input_audio.* (任何格式)
    2. <StudentName>.* (匹配目录名)
    3. 第一个找到的音频文件
    4. 无则返回 None

    支持的格式: .mp3, .mp4, .wav, .m4a, .flac, .ogg

    Args:
        student_dir: 学生目录路径

    Returns:
        音频文件 Path 对象，或 None
    """
    audio_formats = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg'}

    # 优先级 1: 1_input_audio.*
    for audio_file in student_dir.glob('1_input_audio.*'):
        if audio_file.suffix.lower() in audio_formats:
            return audio_file

    # 优先级 2: <StudentName>.*
    student_name = student_dir.name
    for audio_file in student_dir.glob(f'{student_name}.*'):
        if audio_file.suffix.lower() in audio_formats:
            return audio_file

    # 优先级 3: 第一个音频文件
    for audio_file in student_dir.glob('*'):
        if audio_file.is_file() and audio_file.suffix.lower() in audio_formats:
            return audio_file

    return None


def should_process(student_dir: Path) -> bool:
    """
    检查学生是否应该被处理（即是否已存在输出文件）。

    Args:
        student_dir: 学生目录路径

    Returns:
        True 如果应该处理（文件不存在），False 如果应该跳过（文件存在）
    """
    output_file = student_dir / "2_qwen_asr.json"
    return not output_file.exists()


# ===== 处理函数 =====

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
        if not should_process(student_dir):
            print(f"  ✓ {student_name}: 已处理过（跳过）")
            return 0

        # 创建 ASR 提供者
        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误：{str(e)}")
            return 1

        # 查找词汇文件（如果存在）
        shared_context = student_dir.parent / "_shared_context"
        vocab_file = None
        if shared_context.exists():
            vocab_json = shared_context / "vocabulary.json"
            if vocab_json.exists():
                vocab_file = str(vocab_json)
            else:
                csv_files = list(shared_context.glob("*.csv"))
                if csv_files:
                    vocab_file = str(csv_files[0])

        # 转写并保存
        print(f"  ⟳ {student_name}: 处理音频...")
        response = provider.transcribe_and_save(
            input_audio_path=str(audio_file),
            output_dir=str(student_dir),
            vocabulary_path=vocab_file,
            output_filename="2_qwen_asr.json",
            language="zh",
        )

        print(f"  ✓ {student_name}: 已保存到 2_qwen_asr.json")
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

        # 创建 ASR 提供者
        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误：{str(e)}")
            return 0, 0

        # 查找词汇文件
        shared_context = dataset_path / "_shared_context"
        vocab_file = None
        if shared_context.exists():
            vocab_json = shared_context / "vocabulary.json"
            if vocab_json.exists():
                vocab_file = str(vocab_json)
            else:
                csv_files = list(shared_context.glob("*.csv"))
                if csv_files:
                    vocab_file = str(csv_files[0])

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
            if not should_process(student_dir):
                print(f"  ✓ {student_name}: 已处理过（跳过）")
                total_skipped += 1
                continue

            # 转写并保存
            try:
                print(f"  ⟳ {student_name}: 处理音频...")
                response = provider.transcribe_and_save(
                    input_audio_path=str(audio_file),
                    output_dir=str(student_dir),
                    vocabulary_path=vocab_file,
                    output_filename="2_qwen_asr.json",
                    language="zh",
                )

                print(f"  ✓ {student_name}: 已保存到 2_qwen_asr.json")
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
    主入口点 - 支持 CLI 参数的批量转写。

    用法:
        python3 qwen_asr.py                                    # 转写所有数据集
        python3 qwen_asr.py --dataset Zoe51530-9.8            # 转写指定数据集
        python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # 转写单个学生
    """
    parser = argparse.ArgumentParser(
        description='Qwen ASR 批量转写工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 转写所有数据集和学生
  python3 qwen_asr.py

  # 转写指定数据集中的所有学生
  python3 qwen_asr.py --dataset Zoe51530-9.8

  # 转写指定学生
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar

  # 显示帮助
  python3 qwen_asr.py --help
        """
    )

    parser.add_argument(
        '--dataset',
        type=str,
        help='数据集名称 (例如: Zoe51530-9.8)。格式: CourseName-Date'
    )

    parser.add_argument(
        '--student',
        type=str,
        help='学生名称 (例如: Oscar)。需要指定 --dataset'
    )

    parser.add_argument(
        '--api-key',
        type=str,
        help='DashScope API 密钥 (可选，默认从 DASHSCOPE_API_KEY 环境变量读取)'
    )

    args = parser.parse_args()

    # 验证参数依赖关系
    if args.student and not args.dataset:
        parser.error("错误: --student 需要指定 --dataset")

    # 获取 API 密钥
    api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 DASHSCOPE_API_KEY 环境变量或通过 --api-key 传递")
        sys.exit(1)

    # 根据参数执行相应的处理
    try:
        if args.student:
            # 处理单个学生
            exit_code = process_student(args.dataset, args.student, api_key=api_key)
            sys.exit(exit_code)
        elif args.dataset:
            # 处理整个数据集
            processed, skipped = process_dataset(args.dataset, api_key=api_key)
            sys.exit(0 if (processed > 0 or skipped > 0) else 1)
        else:
            # 处理所有数据集（后向兼容）
            process_all_students()
            sys.exit(0)
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
