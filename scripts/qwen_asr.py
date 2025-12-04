"""
Qwen3-ASR 音频转写系统 - 支持多种输入模式

【输入来源】
1. 标准模式：基于 archive/<dataset>/<student>/ 目录结构
   - 音频来源：archive/<dataset>/<student>/1_input_audio.* 或 <StudentName>.*
   - 使用函数：process_student() / process_dataset()

【输出结构】
统一输出到项目根目录的 asr/ 目录：
- asr/{学生名字}.json：Qwen ASR 转写结果（标准 API 响应格式）
- asr/{学生名字}_metadata.json：元数据（数据集、学生、音频文件、处理时间）

【命令行用法】
  python3 qwen_asr.py                                    # 转写所有数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8            # 转写指定数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # 转写单个学生
"""

import os
import sys
import json
import csv
import argparse
import subprocess
import tempfile
import shutil
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import dashscope
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

load_dotenv()


# ===== 音频处理辅助函数 =====

def get_audio_duration(audio_path: str) -> float:
    """
    获取音频文件时长（秒）。

    使用 ffprobe 探测音频时长。

    Args:
        audio_path: 音频文件路径

    Returns:
        时长（秒），获取失败返回 0

    Raises:
        Exception: ffprobe 不可用时
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'json', audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except FileNotFoundError:
        print("⚠️  warning: ffprobe not found, cannot split long audio files")
        return 0
    except Exception as e:
        print(f"⚠️  无法获取音频时长: {e}")
        return 0


def split_audio(audio_path: str, segment_duration: int = 180) -> List[str]:
    """
    将音频文件分割成指定长度的片段。

    如果音频时长小于等于 segment_duration，直接返回原文件。
    否则使用 ffmpeg 分割音频。

    Args:
        audio_path: 原始音频文件路径
        segment_duration: 每段时长（秒），默认 180 秒（3分钟）

    Returns:
        分割后的音频文件路径列表。如果无法分割，返回 [audio_path]

    Note:
        需要安装 ffmpeg。临时文件存储在系统临时目录。
    """
    try:
        duration = get_audio_duration(audio_path)

        # 如果音频时长不超过 segment_duration，直接返回
        if duration == 0 or duration <= segment_duration:
            print(f"   ℹ️  音频时长 {duration:.1f}s，无需分割")
            return [audio_path]

        print(f"   ℹ️  音频时长 {duration:.1f}s，超过 {segment_duration}s，准备分割...")

        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix='qwen_asr_segments_')
        segment_files = []
        segment_count = int(duration // segment_duration) + (1 if duration % segment_duration > 0 else 0)

        print(f"   📂 临时目录: {temp_dir}")
        print(f"   ✂️  分割成 {segment_count} 段...")

        for i in range(segment_count):
            start_time = i * segment_duration
            output_file = os.path.join(temp_dir, f"segment_{i:03d}.mp3")

            # 确定本段时长（最后一段可能更短）
            this_segment_duration = min(segment_duration, duration - start_time)

            cmd = [
                'ffmpeg', '-i', audio_path,
                '-ss', str(start_time),
                '-t', str(this_segment_duration),
                '-c', 'copy',
                '-y',  # 覆盖输出文件
                output_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(output_file):
                segment_files.append(output_file)
                segment_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
                print(f"      ✓ 片段 {i+1}/{segment_count}: {output_file} ({segment_size:.1f}MB)")
            else:
                print(f"      ✗ 片段 {i+1} 创建失败: {result.stderr}")
                # 分割失败，返回原文件
                shutil.rmtree(temp_dir, ignore_errors=True)
                return [audio_path]

        return segment_files

    except FileNotFoundError:
        print("⚠️  ffmpeg not found, cannot split audio files")
        return [audio_path]
    except Exception as e:
        print(f"❌ 音频分割失败: {e}")
        return [audio_path]


def cleanup_audio_segments(segment_files: List[str]) -> None:
    """
    清理分割的音频临时文件。

    Args:
        segment_files: 音频文件路径列表
    """
    try:
        # 获取第一个文件所在的临时目录
        if segment_files and len(segment_files) > 0:
            temp_dir = os.path.dirname(segment_files[0])
            if 'qwen_asr_segments' in temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"   🧹 已清理临时文件: {temp_dir}")
    except Exception as e:
        print(f"⚠️  清理临时文件失败: {e}")


def merge_transcription_results(results: List[Dict[str, Any]]) -> str:
    """
    合并多个音频片段的转写结果文本。

    Args:
        results: 转写结果列表，每个结果是 Qwen API 响应

    Returns:
        合并后的转写文本（不包含任何标点或间隔）
    """
    if not results:
        return ""

    texts = []
    for i, result in enumerate(results):
        try:
            # 从 API 响应中提取文本
            text = None

            if isinstance(result, dict):
                # 标准 API 响应格式
                if "output" in result and isinstance(result["output"], dict):
                    output = result["output"]

                    # 从 choices 中提取文本
                    if "choices" in output and output["choices"]:
                        choice = output["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            content_list = choice["message"]["content"]
                            if isinstance(content_list, list) and content_list:
                                text = content_list[0].get("text", "")
                            elif isinstance(content_list, str):
                                text = content_list

            if text:
                texts.append(str(text))
        except Exception as e:
            pass  # 忽略错误，继续处理下一个片段

    # 直接连接，不添加任何间隔或标点
    merged_text = "".join(texts)
    return merged_text


def merge_json_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并多个音频片段的 JSON 转写结果。

    Args:
        results: JSON 结果列表，每个结果是 Qwen API 响应

    Returns:
        合并后的标准 Qwen API 响应格式（与单个音频响应一致）
    """
    if not results:
        return {
            "status_code": 200,
            "request_id": "",
            "code": "",
            "message": "",
            "output": {
                "text": None,
                "finish_reason": None,
                "choices": []
            }
        }

    if len(results) == 1:
        return results[0]

    # 按 segment_idx 排序确保顺序正确
    sorted_results = sorted(results, key=lambda x: x.get("segment_idx", 0))

    # 合并所有段的文本
    merged_text = merge_transcription_results(sorted_results)

    # 从第一个结果获取元数据（request_id, usage 等）
    first_result = sorted_results[0]
    request_id = first_result.get("request_id", "")
    usage = first_result.get("usage", {})

    # 合并后的标准响应格式
    merged = {
        "status_code": 200,
        "request_id": request_id,
        "code": "",
        "message": "",
        "output": {
            "text": None,
            "finish_reason": None,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "text": merged_text
                            }
                        ],
                        "annotations": [
                            {
                                "language": "zh",
                                "type": "audio_info"
                            }
                        ]
                    }
                }
            ],
            "audio": None
        },
        "usage": usage
    }

    return merged


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
        从 JSON 或 CSV 文件加载词汇表。
        
        支持格式:
        - JSON: [{"问题": "...", "答案": "..."}, ...] 或 {"key": ["中文", "English", ...], ...}
        - CSV: 第1列=中文, 第2列=English (跳过表头)
        
        Args:
            vocab_path: 词汇表文件路径 (.json 或 .csv)
        
        Returns:
            词汇字典 {index: [问题, 答案]} 或 {index: [中文, English, ...]}
        
        Raises:
            ValueError: 文件格式不支持时
        """
        file_ext = os.path.splitext(vocab_path)[1].lower()
        
        if file_ext == '.json':
            # JSON 格式
            with open(vocab_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # 处理不同的 JSON 格式
            if isinstance(data, list):
                # 题库格式：[{"问题": "...", "答案": "..."}, ...]
                vocabulary = {}
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        # 优先使用 "问题" 和 "答案"
                        if "问题" in item and "答案" in item:
                            vocabulary[str(idx)] = [
                                item["问题"].strip(),
                                item["答案"].strip()
                            ]
                        # 否则使用前两个可用的值
                        else:
                            values = list(item.values())
                            if len(values) >= 2:
                                vocabulary[str(idx)] = [
                                    str(values[0]).strip(),
                                    str(values[1]).strip()
                                ]
                return vocabulary
            else:
                # 传统字典格式：{"key": ["中文", "English", ...], ...}
                return data
        
        elif file_ext == '.csv':
            # CSV 格式（题库）
            vocabulary = {}
            with open(vocab_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过表头
                
                for idx, row in enumerate(reader):
                    if len(row) >= 2:
                        # row[0]=中文, row[1]=English
                        vocabulary[str(idx)] = [row[0].strip(), row[1].strip()]
            
            return vocabulary
        
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}。仅支持 .json 和 .csv")

    @staticmethod
    def build_context_text(vocabulary: Dict[str, list]) -> str:
        """
        从词汇表构建 ASR 上下文文本以优化识别。
        
        Qwen3-ASR 通过 System Message 中的上下文文本，可显著提升
        特定领域词汇（如人名、地名、产品术语）的识别准确率。
        
        支持的上下文类型：
        - 热词列表 (分隔符任意，如逗号、分号等)
        - 任意长度的段落或篇章
        - 词表与段落的混合内容
        - 无关/无意义文本（容错性高）
        
        限制: 上下文总长度 ≤ 10000 Token
        
        Args:
            vocabulary: 词汇字典 {key: [中文, English, ...]}
        
        Returns:
            格式化的上下文文本，用于 ASR 识别优化
        """
        if not vocabulary:
            return ""
        
        # 提取中文和英文术语
        terms = []
        for key, values in vocabulary.items():
            if isinstance(values, list) and len(values) >= 2:
                chinese_term = values[0].strip()
                english_term = values[1].strip()
                
                # 双语术语对：中文(English)
                if chinese_term and english_term:
                    terms.append(f"{chinese_term}({english_term})")
        
        if not terms:
            return ""
        
        # 构建上下文文本
        # 格式: "Domain vocabulary: 术语1, 术语2, 术语3, ..."
        # Qwen3-ASR 对分隔符容错性极高，支持多种格式
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

    def transcribe_and_save_with_segmentation(
        self,
        input_audio_path: str,
        output_dir: str,
        vocabulary_path: Optional[str] = None,
        output_filename: str = "2_qwen_asr.json",
        language: Optional[str] = None,
        segment_duration: int = 180,
        max_workers: int = 3,
    ) -> Dict[str, Any]:
        """
        转写音频并保存结果，支持长音频自动分段并行处理。

        如果音频时长超过 segment_duration，自动分割并使用线程池并行转写。

        Args:
            input_audio_path: 输入音频路径
            output_dir: 输出目录
            vocabulary_path: 可选的词汇表路径
            output_filename: 输出文件名
            language: 可选的语言代码
            segment_duration: 分段时长（秒），默认 180（3分钟）
            max_workers: 并行线程数，默认 3

        Returns:
            转写结果字典

        Note:
            如果音频需要分段，最终结果会包含 merged=True 和 segment_count 字段。
        """
        print(f"🎙️  开始转写音频: {input_audio_path}")

        # 获取音频时长
        duration = get_audio_duration(input_audio_path)
        print(f"   📊 音频时长: {duration:.1f} 秒")

        # 检查是否需要分段
        segment_files = split_audio(input_audio_path, segment_duration)

        try:
            if len(segment_files) == 1:
                # 无需分段，直接转写
                print("   ▶️  无需分段，直接转写...")

                # 转换为 file:// URL 格式（如果是本地文件）
                seg_path = segment_files[0]
                if not seg_path.startswith("file://") and not seg_path.startswith("http"):
                    abs_path = os.path.abspath(seg_path)
                    seg_path = f"file://{abs_path}"

                response = self.transcribe_and_save(
                    input_audio_path=seg_path,
                    output_dir=output_dir,
                    vocabulary_path=vocabulary_path,
                    output_filename=output_filename,
                    language=language,
                )
                return response
            else:
                # 需要分段并行处理
                print(f"   ⚙️  启动并行转写（{max_workers} 线程）...")

                # 使用线程池并行转写各段
                segment_results = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_segment = {}

                    for i, seg_file in enumerate(segment_files):
                        # 转换为 file:// URL 格式（多模态 API 需要）
                        abs_path = os.path.abspath(seg_file)
                        audio_url = f"file://{abs_path}"

                        future = executor.submit(
                            self.transcribe_audio,
                            audio_path=audio_url,
                            vocabulary_path=vocabulary_path,
                            language=language,
                        )
                        future_to_segment[future] = (i, seg_file, audio_url)

                    for future in as_completed(future_to_segment):
                        segment_idx, seg_file, audio_url = future_to_segment[future]
                        try:
                            result = future.result()
                            segment_results.append((segment_idx, result))
                            print(f"   ✓ 片段 {segment_idx+1}/{len(segment_files)} 转写完成")
                        except Exception as e:
                            print(f"   ✗ 片段 {segment_idx+1} 转写失败: {e}")

                # 按顺序排序结果
                segment_results.sort(key=lambda x: x[0])
                results = [result for _, result in segment_results]

                # 合并结果
                print("   🔀 合并转写结果...")

                # 为每个结果添加 segment_idx（用于排序）
                for i, result in enumerate(results):
                    result["segment_idx"] = i

                # 生成标准格式的合并响应
                final_response = merge_json_results(results)

                # 保存结果
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_filename)

                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(final_response, f, ensure_ascii=False, indent=2)

                print(f"   ✅ 转写完成！结果已保存到: {output_path}")

                return final_response

        finally:
            # 清理临时文件
            if len(segment_files) > 1:
                cleanup_audio_segments(segment_files)


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
        metadata = {
            "dataset": dataset_name,
            "student": student_name,
            "audio_file": audio_file.name,
            "processed_at": str(datetime.datetime.now().isoformat()),
        }

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
