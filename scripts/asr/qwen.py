# -*- coding: utf-8 -*-
"""
scripts/asr/qwen.py - Qwen3-ASR Provider

提供 Qwen3-ASR 语音转写功能，支持：
- 自定义词汇表/热词上下文
- 长音频自动分段并行处理
- 多种输入格式（本地文件、URL）

使用方法：
    from scripts.asr.qwen import QwenASRProvider

    provider = QwenASRProvider()
    result = provider.transcribe_and_save_with_segmentation(
        input_audio_path="audio.mp3",
        output_dir="output/",
        vocabulary_path="vocab.json"
    )
"""

import os
import json
import subprocess
import tempfile
import shutil
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import dashscope


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
                                "emotion": "neutral",
                                "language": "auto",
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
    """Qwen3-ASR provider for audio transcription with custom vocabulary.

    提供 Qwen3-ASR 语音转写功能，支持：
    - 自定义词汇表/热词上下文优化识别
    - 长音频自动分段并行处理
    - 多种输入格式（本地文件、URL）

    Attributes:
        api_key: DashScope API 密钥
        model: 使用的 ASR 模型名称

    Example:
        >>> provider = QwenASRProvider()
        >>> result = provider.transcribe_audio("audio.mp3", vocabulary_path="vocab.json")
    """

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
    def _sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _preview_text(text: str, max_len: int = 300) -> str:
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        head = text[: max_len // 2].rstrip()
        tail = text[-max_len // 2 :].lstrip()
        return f"{head} … {tail}"

    @staticmethod
    def load_vocabulary(vocab_path: str) -> List[Dict[str, str]]:
        """
        从 JSON 文件加载词汇表（题库格式）。

        支持格式:
        - JSON: [{"question": "...", "answer": "...", "hint": "..."}, ...]

        Args:
            vocab_path: 词汇表文件路径 (.json)

        Returns:
            词条列表 [{"question": "英文", "answer": "中文释义", "hint": "词性"}, ...]

        Raises:
            ValueError: 文件格式不支持时
        """
        file_ext = os.path.splitext(vocab_path)[1].lower()

        if file_ext == '.json':
            # JSON 格式
            with open(vocab_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            # 处理题库列表格式
            if isinstance(data, list):
                vocabulary = []
                for item in data:
                    if isinstance(item, dict):
                        entry = {}
                        # 提取 question, answer, hint
                        if "question" in item:
                            entry["question"] = item["question"].strip()
                        elif "问题" in item:
                            entry["question"] = item["问题"].strip()

                        if "answer" in item:
                            entry["answer"] = item["answer"].strip()
                        elif "答案" in item:
                            entry["answer"] = item["答案"].strip()

                        if "hint" in item:
                            entry["hint"] = item["hint"].strip()
                        elif "提示" in item:
                            entry["hint"] = item["提示"].strip()

                        # 只添加包含必要字段的条目
                        if "question" in entry and "answer" in entry:
                            vocabulary.append(entry)

                return vocabulary
            else:
                # 如果是字典格式，尝试转换为列表格式
                vocabulary = []
                for key, values in data.items():
                    if isinstance(values, list) and len(values) >= 2:
                        entry = {
                            "question": values[0].strip() if len(values) > 0 else "",
                            "answer": values[1].strip() if len(values) > 1 else "",
                            "hint": values[2].strip() if len(values) > 2 else ""
                        }
                        if entry["question"] and entry["answer"]:
                            vocabulary.append(entry)
                return vocabulary

        else:
            raise ValueError(f"不支持的文件格式: {file_ext}。仅支持 .json")

    @staticmethod
    def build_context_text(vocabulary: List[Dict[str, str]]) -> str:
        """
        从词汇表构建 ASR 上下文文本以优化识别。

        Qwen3-ASR 通过 System Message 中的上下文文本，可显著提升
        特定领域词汇（如人名、地名、产品术语）的识别准确率。

        格式：纯词汇列表，逗号分隔
        例如："not, double, half, part, both, all, each, 不, 双倍的, 一半, ..."

        注意：使用纯词汇列表格式而非结构化模板，避免 ASR 将上下文
        当作"期望输出格式"而非"可能出现的词汇"。

        适用场景：小孩子发音不清晰，只要大概意思到了就能识别。

        限制: 上下文总长度 ≤ 10000 Token

        Args:
            vocabulary: 词条列表 [{"question": "英文", "answer": "中文", "hint": "词性"}, ...]

        Returns:
            纯词汇列表文本，用于 ASR 识别优化
        """
        context_words = QwenASRProvider.build_context_words(vocabulary)
        if not context_words:
            return ""
        return ", ".join(context_words)

    @staticmethod
    def build_context_words(vocabulary: List[Dict[str, str]]) -> List[str]:
        """从题库词条提取热词（去重+排序）。"""
        if not vocabulary:
            return []

        words = set()
        separators = ["、", "，", "/", "／", "；", ";", "｜", "|"]

        def split_and_add(text: str):
            if not text:
                return
            normalized = text
            for sep in separators:
                normalized = normalized.replace(sep, ",")
            for part in normalized.split(","):
                part = part.strip()
                if part:
                    words.add(part)

        for item in vocabulary:
            if not isinstance(item, dict):
                continue
            split_and_add(item.get("question", ""))
            split_and_add(item.get("answer", ""))

        return sorted(words)

    def _build_run_meta(
        self,
        *,
        audio_path: str,
        vocabulary_path: Optional[str],
        language: Optional[str],
        enable_itn: bool,
        context_words: List[str],
        segment_duration: Optional[int] = None,
        segment_count: Optional[int] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        context_text = ", ".join(context_words or [])
        return {
            "provider": "qwen3-asr",
            "requested_model": self.model,
            "language": language or "auto",
            "enable_itn": enable_itn,
            "audio_path": audio_path,
            "vocabulary_path": vocabulary_path,
            "context": {
                "delimiter": ", ",
                "words_count": len(context_words or []),
                "words": context_words or [],
                "text_sha256": self._sha256_text(context_text),
                "text_preview": self._preview_text(context_text),
            },
            "segmentation": {
                "segment_duration": segment_duration,
                "segment_count": segment_count,
                "max_workers": max_workers,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _print_run_inputs(self, meta: Dict[str, Any]) -> None:
        context = meta.get("context", {}) if isinstance(meta, dict) else {}
        print(f"   🤖 ASR 模型: {meta.get('requested_model')}")
        if meta.get("vocabulary_path"):
            print(f"   📚 题库: {meta.get('vocabulary_path')}")
        print(
            f"   🔥 Context 热词数: {context.get('words_count', 0)} "
            f"(sha256={str(context.get('text_sha256', ''))[:12]}...)"
        )
        preview = context.get("text_preview")
        if preview:
            print(f"   🧩 Context 预览: {preview}")

    def transcribe_audio(
        self,
        audio_path: str,
        vocabulary_path: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        system_context_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Qwen3-ASR with optional vocabulary context.

        Args:
            audio_path: Path or URL to audio file
            vocabulary_path: Optional path to vocabulary JSON file for context
            language: Optional language code (e.g., "zh" for Chinese)
            enable_itn: Enable inverse text normalization

        Returns:
            Response dictionary with transcription results
        """
        # Build vocabulary context if provided (pure word list format)
        # Note: Using comma-separated word list instead of structured template
        # to avoid ASR treating context as "expected output format".
        # This helps recognize unclear pronunciation from children.
        system_context = system_context_override or ""
        if not system_context and vocabulary_path and os.path.exists(vocabulary_path):
            vocab = self.load_vocabulary(vocabulary_path)
            system_context = self.build_context_text(vocab)

        # Build ASR options
        asr_options = {
            "enable_itn": enable_itn,
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
        log_inputs: bool = True,
        meta_override: Optional[Dict[str, Any]] = None,
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
        context_words: List[str] = []
        if vocabulary_path and os.path.exists(vocabulary_path):
            try:
                vocab = self.load_vocabulary(vocabulary_path)
                context_words = self.build_context_words(vocab)
            except Exception:
                context_words = []

        meta = meta_override or self._build_run_meta(
            audio_path=input_audio_path,
            vocabulary_path=vocabulary_path,
            language=language,
            enable_itn=False,
            context_words=context_words,
        )
        if log_inputs:
            self._print_run_inputs(meta)

        # Transcribe audio
        response = self.transcribe_audio(
            audio_path=input_audio_path,
            vocabulary_path=vocabulary_path,
            language=language,
            enable_itn=False,
            system_context_override=", ".join(context_words) if context_words else None,
        )

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        if isinstance(response, dict):
            response["qf_meta"] = meta

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
            context_words: List[str] = []
            if vocabulary_path and os.path.exists(vocabulary_path):
                try:
                    vocab = self.load_vocabulary(vocabulary_path)
                    context_words = self.build_context_words(vocab)
                except Exception:
                    context_words = []

            meta = self._build_run_meta(
                audio_path=input_audio_path,
                vocabulary_path=vocabulary_path,
                language=language,
                enable_itn=False,
                context_words=context_words,
                segment_duration=segment_duration,
                segment_count=len(segment_files),
                max_workers=max_workers,
            )
            self._print_run_inputs(meta)

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
                    log_inputs=False,
                    meta_override=meta,
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
                            enable_itn=False,
                            system_context_override=", ".join(context_words) if context_words else None,
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
                if isinstance(final_response, dict):
                    final_response["qf_meta"] = meta

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
