"""
FunASR 异步语音转写脚本
使用阿里云 DashScope API 进行批量音频转写
支持基于题库的动态热词管理

【输入来源】
1. Archive 批处理模式（推荐）：
   - 目录结构：archive/{class_code}_{date}/{student}/1_input_audio.*
   - 题库来源：archive/{class_code}_{date}/metadata.json -> question_bank_file
   - 输出：archive/{class}_{date}/{student}/3_asr_timestamp.json

2. URL 模式（原有）：
   - 输入：音频文件 URL 列表
   - 输出：asr_timestamp/{filename}.json

【命令行用法】
  # Archive 批处理模式（推荐）
  python3 funasr.py --archive-batch Zoe41900_2025-09-08
  python3 funasr.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # URL 模式（原有）
  python3 funasr.py <url1> <url2> ...
  python3 funasr.py --hotwords <url1> <url2> ...
"""

import os
import json
import time
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional

import dashscope

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
from scripts.common.archive import find_audio_file as _find_audio_file_common

# 导入 ASR Provider（核心转写逻辑已抽取到 scripts/asr/funasr.py）
from scripts.asr.funasr import (
    FunASRTimestampProvider,
    VocabularySlotManager,
    async_transcribe,
    get_filename_from_url,
    load_questionbank,
    extract_vocabulary,
)

# 北京地域 URL
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / 'asr_timestamp'

# 题库目录
QUESTIONBANK_DIR = Path(__file__).parent.parent / 'questionbank'


def parse_audio_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    解析音频文件名: {ClassCode}_{Date}_{QuestionBank}_{Student}.mp3

    已迁移到 scripts.common.naming.parse_backend_input_mp3_name，此函数为兼容性别名。
    """
    result = parse_backend_input_mp3_name(filename + ".mp3")
    if result:
        # 保持原有返回格式兼容性（student 而非 student_name）
        return {
            'class_code': result['class_code'],
            'date': result['date'],
            'question_bank': result['question_bank'],
            'student': result['student_name']
        }
    return None


def find_questionbank_by_code(question_bank_code: str) -> Optional[Path]:
    """
    在 questionbank/ 目录中查找题库文件

    Args:
        question_bank_code: 题库代码（如 R1-65-D5）

    Returns:
        题库文件路径，或 None
    """
    # 精确匹配
    exact = QUESTIONBANK_DIR / f"{question_bank_code}.json"
    if exact.exists():
        return exact

    # 前缀匹配
    for f in sorted(QUESTIONBANK_DIR.glob(f"{question_bank_code}*.json")):
        if f.is_file():
            return f

    return None


def transcribe_with_hotwords(
    file_urls: List[str],
    vocab_manager: VocabularySlotManager,
    poll_interval: int = 5
) -> List[dict]:
    """
    带热词的批量转写（按题库分组处理）

    Args:
        file_urls: 音频文件 URL 列表
        vocab_manager: 热词槽位管理器
        poll_interval: 轮询间隔

    Returns:
        转写结果列表
    """
    # 按题库分组
    groups = {}  # question_bank_code -> [urls]
    ungrouped = []  # 无法解析的 URL

    for url in file_urls:
        filename = get_filename_from_url(url)
        parsed = parse_audio_filename(filename)

        if parsed:
            qb_code = parsed['question_bank']
            if qb_code not in groups:
                groups[qb_code] = []
            groups[qb_code].append(url)
        else:
            ungrouped.append(url)
            print(f"警告: 无法解析文件名 {filename}，将不使用热词")

    results = []

    # 按题库分组处理
    for qb_code, urls in groups.items():
        print(f"\n处理题库组: {qb_code} ({len(urls)} 个文件)")

        try:
            # 加载题库并更新热词
            qb_file = find_questionbank_by_code(qb_code)
            if qb_file:
                questionbank = load_questionbank(qb_file)
                vocabulary = extract_vocabulary(questionbank)
                vocab_manager.update_vocabulary(vocabulary)

            # 使用带热词的异步转写
            group_results = async_transcribe(
                urls, poll_interval,
                vocabulary_id=vocab_manager.vocabulary_id
            )
            results.extend(group_results)

        except FileNotFoundError as e:
            print(f"错误: {e}")
            # 无法加载题库时，不使用热词直接转写
            group_results = async_transcribe(urls, poll_interval)
            results.extend(group_results)

    # 处理无法分组的文件
    if ungrouped:
        print(f"\n处理未分组文件 ({len(ungrouped)} 个)")
        ungrouped_results = async_transcribe(ungrouped, poll_interval)
        results.extend(ungrouped_results)

    return results


def save_results(results: list[dict], output_dir: Path) -> None:
    """保存转写结果到文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        file_url = result.get('file_url', '')
        filename = get_filename_from_url(file_url)

        if not filename:
            filename = f"unknown_{int(time.time())}"

        output_path = output_dir / f"{filename}.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"已保存: {output_path}")


# ===== Archive 批处理模式 =====

def load_archive_metadata(archive_batch: str) -> Dict:
    """
    加载 archive/{class}_{date}/metadata.json

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）

    Returns:
        metadata 字典
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

    已迁移到 scripts.common.archive.find_audio_file，此函数为兼容性别名。
    """
    return _find_audio_file_common(student_dir)


def find_archive_vocabulary_file(archive_batch: str, metadata: Dict) -> Optional[Path]:
    """
    根据 metadata 查找题库文件

    符合 dataset_conventions.md 规范：
    - 优先使用 question_bank_path（指向 questionbank/ 目录）
    - Fallback: 使用 progress 字段在 questionbank/ 中查找
    - Fallback: question_bank_file（旧格式）

    Args:
        archive_batch: 分组名称
        metadata: metadata.json 内容

    Returns:
        题库文件路径，或 None
    """
    project_root = Path(__file__).parent.parent

    # 优先级 1: question_bank_path（新格式，指向 questionbank/）
    qb_path_str = metadata.get("question_bank_path")
    if qb_path_str:
        qb_path = project_root / qb_path_str
        if qb_path.exists():
            return qb_path

    # 优先级 2: 使用 progress 在 questionbank/ 中查找
    progress = metadata.get("progress")
    if progress:
        qb_file = find_questionbank_by_code(progress)
        if qb_file:
            return qb_file

    # Fallback: question_bank_file（旧格式，相对于 archive 目录）
    archive_dir = project_root / "archive" / archive_batch
    qb_file_old = metadata.get("question_bank_file")
    if qb_file_old:
        qb_path = archive_dir / qb_file_old
        if qb_path.exists():
            return qb_path

    return None


def should_process_archive_student(student_dir: Path) -> bool:
    """
    检查学生是否应该被处理（是否已存在 3_asr_timestamp.json）

    Args:
        student_dir: 学生目录路径

    Returns:
        True 如果应该处理，False 如果应该跳过
    """
    output_file = student_dir / "3_asr_timestamp.json"
    return not output_file.exists()


def process_archive_student_local(
    student_dir: Path,
    student_name: str,
    vocabulary_path: Optional[str] = None,
    force: bool = False,
    oss_url: Optional[str] = None
) -> bool:
    """
    处理单个 archive 学生的音频转写（使用 FunASRTimestampProvider）

    Args:
        student_dir: 学生目录路径
        student_name: 学生名称
        vocabulary_path: 题库文件路径
        force: 是否强制重新处理
        oss_url: OSS URL（如果有的话，优先使用）

    Returns:
        True 成功，False 失败
    """
    # 检查是否需要处理
    if not force and not should_process_archive_student(student_dir):
        print(f"  ✓ {student_name}: 已处理过（跳过）")
        return True

    # 创建 provider
    provider = FunASRTimestampProvider()

    # 查找音频文件（作为 fallback）
    audio_file = find_archive_audio_file(student_dir)
    audio_source = str(audio_file) if audio_file else ""

    # 使用 provider 进行转写
    return provider.transcribe_and_save(
        audio_source=audio_source,
        output_dir=student_dir,
        student_name=student_name,
        vocabulary_path=vocabulary_path,
        output_filename="3_asr_timestamp.json",
        oss_url=oss_url,
        force=force
    )


def process_archive_batch(
    archive_batch: str,
    student_name: Optional[str] = None,
    use_hotwords: bool = True,
    force: bool = False
) -> tuple:
    """
    批量处理 archive/{class}_{date}/ 下的所有学生

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）
        student_name: 可选的单个学生名称
        use_hotwords: 是否使用热词
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
    print(f"📁 FunASR Archive 批处理: {archive_batch}")
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

    # 查找题库文件
    vocab_file = None
    if use_hotwords:
        vocab_file = find_archive_vocabulary_file(archive_batch, metadata)
        if vocab_file:
            print(f"   📚 题库: {vocab_file.name}")
        else:
            print(f"   ⚠️  未找到题库文件，不使用热词")

    # 构建学生 -> OSS URL 映射
    student_oss_urls = {}
    for item in metadata.get('items', []):
        s = item.get('student')
        url = item.get('oss_url')
        if s and url:
            student_oss_urls[s] = url

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
    success_count = 0
    fail_count = 0

    for student in students:
        student_dir = archive_dir / student
        oss_url = student_oss_urls.get(student)  # 从 metadata 获取 OSS URL
        success = process_archive_student_local(
            student_dir,
            student,
            vocabulary_path=str(vocab_file) if vocab_file else None,
            force=force,
            oss_url=oss_url
        )
        if success:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"✅ 处理完成！成功: {success_count}, 跳过/失败: {fail_count}")
    print(f"{'='*60}")

    return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(
        description='FunASR 异步语音转写（支持动态热词）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # Archive 批处理模式（推荐）
  python3 funasr.py --archive-batch Zoe41900_2025-09-08
  python3 funasr.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # URL 模式（原有）
  python3 funasr.py <url1> <url2> ...
  python3 funasr.py --hotwords <url1> <url2> ...
        """
    )

    # Archive 批处理模式参数
    parser.add_argument(
        '--archive-batch',
        type=str,
        help='Archive 批处理模式 (例如: Zoe41900_2025-09-08)'
    )
    parser.add_argument(
        '--student',
        type=str,
        help='指定单个学生（仅在 --archive-batch 模式下有效）'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新处理已处理过的学生'
    )

    # URL 模式参数
    parser.add_argument(
        'file_urls',
        nargs='*',
        help='音频文件 URL 列表'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=OUTPUT_DIR,
        help=f'输出目录 (默认: {OUTPUT_DIR})'
    )
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=5,
        help='轮询间隔秒数 (默认: 5)'
    )
    parser.add_argument(
        '--hotwords',
        action='store_true',
        help='启用基于题库的动态热词功能'
    )

    args = parser.parse_args()

    # Archive 批处理模式
    if args.archive_batch:
        success, fail = process_archive_batch(
            args.archive_batch,
            student_name=args.student,
            use_hotwords=True,  # Archive 模式默认启用热词
            force=args.force
        )
        return 0 if (success > 0 or fail > 0) else 1

    # URL 模式
    # 如果没有提供 URL，使用示例 URL
    file_urls = args.file_urls or [
        'https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3',
        'https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/Zoe51530_2025-09-08_R3-14-D4_Alvin.mp3'
    ]

    print(f"输出目录: {args.output}")
    print(f"热词功能: {'启用' if args.hotwords else '禁用'}")
    print("-" * 50)

    # 执行转写
    if args.hotwords:
        # 初始化热词槽位管理器
        vocab_manager = VocabularySlotManager()
        vocab_manager.get_or_create_slot()
        print("-" * 50)

        # 使用带热词的转写
        results = transcribe_with_hotwords(
            file_urls,
            vocab_manager,
            poll_interval=args.interval
        )
    else:
        # 普通转写（无热词）
        results = async_transcribe(file_urls, poll_interval=args.interval)

    # 保存结果
    if results:
        save_results(results, args.output)
        print("-" * 50)
        print(f"完成！共处理 {len(results)} 个文件")
    else:
        print("没有成功的转写结果")


if __name__ == '__main__':
    main()
