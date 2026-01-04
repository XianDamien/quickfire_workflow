#!/usr/bin/env python3
"""
Quickfire 一键入口 - DAG 依赖驱动的批处理工具

DAG 节点与依赖:
    audio → qwen_asr → timestamps → cards

Provider 约束:
    - qwen_asr (text) 阶段: 只能使用 Text provider (QwenASRProvider)
    - timestamps 阶段: 只能使用 Timestamp provider (FunASRTimestampProvider)

用法:
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target cards
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar --target cards
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --only qwen_asr
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --until timestamps
    python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target cards --annotator gemini-2.5-pro
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

# 项目根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive"

# 确保项目根目录在 Python path 中
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 统一加载环境变量（最早调用，确保后续 import 能拿到 key）
from scripts.common.env import load_env
load_env()

# DAG 节点定义（顺序即依赖顺序）
DAG_STAGES = ["audio", "qwen_asr", "timestamps", "cards"]


# 使用 common 模块的共用函数
from scripts.common.runs import get_git_commit, new_run_id
from scripts.common.hash import file_hash
from scripts.common.archive import find_audio_file as _find_audio_file, resolve_question_bank


def find_audio_file(student_dir: Path) -> Optional[Path]:
    """查找学生目录下的音频文件（兼容包装）"""
    return _find_audio_file(student_dir)


def check_stage_complete(student_dir: Path, stage: str) -> bool:
    """
    检查某个阶段是否已完成

    注意: cards 阶段始终返回 False，因为每次运行都应该生成新的 run
    用于对比不同模型或不同 prompt 版本的结果
    """
    if stage == "audio":
        return find_audio_file(student_dir) is not None
    elif stage == "qwen_asr":
        return (student_dir / "2_qwen_asr.json").exists()
    elif stage == "timestamps":
        return (student_dir / "3_asr_timestamp.json").exists()
    elif stage == "cards":
        # cards 阶段：始终返回 False，每次都生成新的 run
        # 这样可以支持多次运行来对比不同模型/prompt 的效果
        # 如果真的想跳过，使用 --only qwen_asr 或 --until timestamps
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


def load_batch_metadata(archive_batch: str) -> Dict[str, Any]:
    """
    加载 archive/{batch}/metadata.json

    Args:
        archive_batch: 分组名称

    Returns:
        metadata 字典，加载失败返回空字典
    """
    metadata_path = ARCHIVE_DIR / archive_batch / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def get_student_oss_url(metadata: Dict[str, Any], student_name: str) -> Optional[str]:
    """
    从 metadata 中获取学生的 OSS URL

    Args:
        metadata: batch metadata
        student_name: 学生名称

    Returns:
        OSS URL 或 None
    """
    for item in metadata.get('items', []):
        if item.get('student') == student_name:
            return item.get('oss_url')
    return None


def run_qwen_asr(
    archive_batch: str,
    student_name: str,
    force: bool = False,
    dry_run: bool = False
) -> bool:
    """
    执行 qwen_asr (text) 阶段

    使用 Text provider: QwenASRProvider
    输出: 2_qwen_asr.json

    Args:
        archive_batch: 批次名称
        student_name: 学生名称
        force: 是否强制重新处理
        dry_run: 是否只打印不执行

    Returns:
        True=成功, False=失败
    """
    student_dir = ARCHIVE_DIR / archive_batch / student_name

    # 查找音频文件
    audio_file = find_audio_file(student_dir)
    if not audio_file:
        print(f"  [✗] 缺少音频文件: {student_dir}/1_input_audio.*")
        return False

    # 加载 metadata 获取题库
    metadata = load_batch_metadata(archive_batch)
    vocab_file = resolve_question_bank(archive_batch, metadata)

    # 输出路径
    output_file = student_dir / "2_qwen_asr.json"

    if dry_run:
        print(f"  [dry-run] qwen_asr 阶段")
        print(f"    音频路径: {audio_file}")
        print(f"    题库路径: {vocab_file or '(无)'}")
        print(f"    输出路径: {output_file}")
        print(f"    Provider: QwenASRProvider (Text)")
        return True

    print(f"  [执行] qwen_asr -> {student_name}")

    try:
        # 直接调用 Text provider
        from scripts.asr.qwen import QwenASRProvider

        provider = QwenASRProvider()
        provider.transcribe_and_save_with_segmentation(
            input_audio_path=str(audio_file),
            output_dir=str(student_dir),
            vocabulary_path=str(vocab_file) if vocab_file else None,
            output_filename="2_qwen_asr.json",
            language=None,  # 不指定语言，让 ASR 自动检测多语种
            segment_duration=180,
            max_workers=3,
        )

        print(f"  [✓] qwen_asr 完成 -> 2_qwen_asr.json")
        return True

    except Exception as e:
        print(f"  [✗] qwen_asr 失败: {e}")
        return False


def run_timestamps(
    archive_batch: str,
    student_name: str,
    force: bool = False,
    dry_run: bool = False
) -> bool:
    """
    执行 timestamps 阶段

    使用 Timestamp provider: FunASRTimestampProvider
    输出: 3_asr_timestamp.json

    Args:
        archive_batch: 批次名称
        student_name: 学生名称
        force: 是否强制重新处理
        dry_run: 是否只打印不执行

    Returns:
        True=成功, False=失败
    """
    student_dir = ARCHIVE_DIR / archive_batch / student_name

    # 查找音频文件
    audio_file = find_audio_file(student_dir)
    if not audio_file:
        print(f"  [✗] 缺少音频文件: {student_dir}/1_input_audio.*")
        return False

    # 加载 metadata 获取题库和 OSS URL
    metadata = load_batch_metadata(archive_batch)
    vocab_file = resolve_question_bank(archive_batch, metadata)
    oss_url = get_student_oss_url(metadata, student_name)

    # 输出路径
    output_file = student_dir / "3_asr_timestamp.json"

    if dry_run:
        print(f"  [dry-run] timestamps 阶段")
        print(f"    音频路径: {audio_file}")
        print(f"    题库路径: {vocab_file or '(无)'}")
        print(f"    OSS URL: {oss_url or '(无)'}")
        print(f"    输出路径: {output_file}")
        print(f"    Provider: FunASRTimestampProvider (Timestamp)")
        return True

    print(f"  [执行] timestamps -> {student_name}")

    try:
        # 直接调用 Timestamp provider
        from scripts.asr.funasr import FunASRTimestampProvider

        provider = FunASRTimestampProvider()
        success = provider.transcribe_and_save(
            audio_source=str(audio_file),
            output_dir=student_dir,
            student_name=student_name,
            vocabulary_path=str(vocab_file) if vocab_file else None,
            output_filename="3_asr_timestamp.json",
            oss_url=oss_url,
            force=force
        )

        if success:
            print(f"  [✓] timestamps 完成 -> 3_asr_timestamp.json")
            return True
        else:
            print(f"  [✗] timestamps 失败")
            return False

    except Exception as e:
        print(f"  [✗] timestamps 失败: {e}")
        return False


def run_stage(stage: str, archive_batch: str, student_name: str,
              force: bool = False, annotator: str = None,
              dry_run: bool = False, annotator_kwargs: dict = None) -> tuple:
    """
    执行单个阶段

    Returns:
        (success: bool, error_msg: Optional[str])
    """
    student_dir = ARCHIVE_DIR / archive_batch / student_name

    # 检查是否需要执行
    if not force and check_stage_complete(student_dir, stage):
        print(f"  [跳过] {stage} 已完成")
        return True, None

    if stage == "audio":
        # audio 阶段只检查，不执行
        if find_audio_file(student_dir):
            print(f"  [✓] audio 已存在")
            return True, None
        else:
            error_msg = f"缺少音频文件: {student_dir}/1_input_audio.*"
            print(f"  [✗] {error_msg}")
            return False, error_msg

    elif stage == "qwen_asr":
        # Text provider: QwenASRProvider
        success = run_qwen_asr(archive_batch, student_name, force, dry_run)
        return (success, None) if success else (False, "qwen_asr 失败")

    elif stage == "timestamps":
        # Timestamp provider: FunASRTimestampProvider
        success = run_timestamps(archive_batch, student_name, force, dry_run)
        return (success, None) if success else (False, "timestamps 失败")

    elif stage == "cards":
        return run_annotation(archive_batch, student_name, annotator, force, dry_run, annotator_kwargs)

    return False, "未知阶段"


def run_annotation(archive_batch: str, student_name: str,
                   annotator: str, force: bool, dry_run: bool,
                   annotator_kwargs: dict = None) -> tuple:
    """
    执行标注阶段，输出到分层 runs 目录
    输出: archive/{dataset_id}/{student}/runs/{annotator_name}/{run_id}/4_llm_annotation.json

    使用模块化 annotator 调用，不再依赖 subprocess。

    Returns:
        (success: bool, error_msg: Optional[str])
    """
    from scripts.annotators import get_annotator
    from scripts.common.runs import ensure_run_dir

    student_dir = ARCHIVE_DIR / archive_batch / student_name
    run_id = new_run_id()

    # 目标目录: runs/{annotator_name}/{run_id}/
    run_dir = ensure_run_dir(archive_batch, student_name, annotator, run_id)

    if dry_run:
        print(f"  [dry-run] 会创建: {run_dir}/4_llm_annotation.json")
        return True, None

    print(f"  [执行] annotator={annotator} --archive-batch {archive_batch} --student {student_name}")

    try:
        # 获取 annotator 实例（传入配置参数）
        kwargs = annotator_kwargs or {}
        impl = get_annotator(annotator, **kwargs)

        # 调用标注
        result = impl.run_archive_student(
            archive_batch=archive_batch,
            student_name=student_name,
            run_dir=run_dir,
            force=force,
            verbose=False
        )

        if result.success:
            print(f"  [✓] cards 完成 -> {run_dir.relative_to(PROJECT_ROOT)}/4_llm_annotation.json")
            return True, None
        else:
            error_msg = f"annotation 失败: {result.error}"
            print(f"  [✗] {error_msg}")
            return False, error_msg

    except NotImplementedError as e:
        error_msg = str(e)
        print(f"  [✗] {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"annotation 异常: {e}"
        print(f"  [✗] {error_msg}")
        return False, error_msg


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

    # 从配置获取默认 annotator
    from scripts.annotators.config import DEFAULT_ANNOTATOR

    parser.add_argument(
        '--annotator', '-a',
        type=str,
        default=DEFAULT_ANNOTATOR,
        help=f'标注模型 (默认: {DEFAULT_ANNOTATOR})'
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

    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='继续处理其他学生即使某个学生失败（默认：严格失败模式）'
    )

    # Gemini 参数配置
    parser.add_argument(
        '--max-output-tokens',
        type=int,
        help='LLM 最大输出 tokens（默认：Gemini 3 系列 64000，其他 16384）'
    )

    parser.add_argument(
        '--max-retries',
        type=int,
        help='API 调用最大重试次数（默认：5）'
    )

    parser.add_argument(
        '--retry-delay',
        type=int,
        help='API 调用重试延迟（秒，默认：5）'
    )

    parser.add_argument(
        '--http-timeout',
        type=int,
        help='HTTP 请求超时（毫秒，默认：600000 即 10 分钟，最小 10000，可通过环境变量 GEMINI_HTTP_TIMEOUT 设置）'
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

    # 构建 annotator 参数
    annotator_kwargs = {}
    if args.max_output_tokens is not None:
        annotator_kwargs['max_output_tokens'] = args.max_output_tokens
    if args.max_retries is not None:
        annotator_kwargs['max_retries'] = args.max_retries
    if args.retry_delay is not None:
        annotator_kwargs['retry_delay'] = args.retry_delay
    if args.http_timeout is not None:
        annotator_kwargs['http_timeout'] = args.http_timeout

    print(f"=" * 60)
    print(f"Quickfire Pipeline")
    print(f"=" * 60)
    print(f"Archive: {args.archive_batch}")
    print(f"学生数: {len(students)}")
    print(f"阶段: {' → '.join(stages)}")
    print(f"Annotator: {args.annotator}")
    if annotator_kwargs:
        print(f"Annotator 参数:")
        for k, v in annotator_kwargs.items():
            print(f"  - {k}: {v}")
    if args.force:
        print(f"模式: 强制重新处理")
    if args.dry_run:
        print(f"模式: 干运行")
    if args.continue_on_error:
        print(f"模式: 继续处理模式（单个学生失败不影响后续）")
    else:
        print(f"模式: 严格失败模式（任何失败立即停止）")
    print(f"=" * 60)
    print()

    # 统计
    success_count = 0
    fail_count = 0
    failed_students = []  # 收集失败的学生信息

    # 处理每个学生
    for student_name, student_dir in students:
        print(f"[{student_name}]")

        # 执行每个阶段
        student_success = True
        failure_info = None
        for stage in stages:
            success, error_msg = run_stage(
                stage, args.archive_batch, student_name,
                force=args.force, annotator=args.annotator,
                dry_run=args.dry_run, annotator_kwargs=annotator_kwargs
            )
            if not success:
                student_success = False
                failure_info = {
                    'student': student_name,
                    'stage': stage,
                    'error': error_msg or '未知错误'
                }

                if args.continue_on_error:
                    # 继续模式：记录失败，继续下一个学生
                    print(f"  [跳过] {stage} 失败，继续处理其他学生")
                    break  # 跳过该学生的剩余阶段
                else:
                    # 严格模式：立即停止
                    print(f"  [停止] 严格失败模式：{stage} 失败，停止处理")
                    print()
                    print(f"=" * 60)
                    print(f"错误: 学生 '{student_name}' 在阶段 '{stage}' 失败")
                    print(f"错误详情: {error_msg}")
                    print(f"已处理: {success_count} 成功, {fail_count + 1} 失败")
                    print(f"=" * 60)
                    sys.exit(1)

        if student_success:
            success_count += 1
            print(f"  [完成] 所有阶段成功")
        else:
            fail_count += 1
            if failure_info:
                failed_students.append(failure_info)
        print()

    # 总结
    print(f"=" * 60)
    print(f"完成: {success_count} 成功, {fail_count} 失败")
    print(f"=" * 60)

    # 如果有失败的学生，显示失败列表
    if failed_students:
        print()
        print(f"失败的学生列表:")
        print(f"-" * 60)
        for info in failed_students:
            print(f"  - {info['student']} ({info['stage']}): {info['error']}")
        print(f"-" * 60)

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
