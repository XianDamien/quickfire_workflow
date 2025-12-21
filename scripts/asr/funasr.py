# -*- coding: utf-8 -*-
"""
scripts/asr/funasr.py - FunASR Timestamp Provider

提供 FunASR 语音转写功能，支持：
- 句子级别时间戳生成（sentences）
- 基于题库的动态热词管理
- 异步批量转写

使用方法：
    from scripts.asr.funasr import FunASRTimestampProvider

    provider = FunASRTimestampProvider()
    result = provider.transcribe_with_timestamp(
        audio_url="https://...",
        vocabulary_path="vocab.json"
    )

时间戳提取：
    from scripts.contracts.asr_timestamp import extract_timestamp_text

    timestamp_text = extract_timestamp_text("path/to/3_asr_timestamp.json")
"""

import os
import json
import re
import time
import subprocess
import requests
from http import HTTPStatus
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, unquote

import dashscope
from dashscope.audio.asr import Transcription, VocabularyService, Recognition


# 默认配置
VOCABULARY_PREFIX = "qf"  # quickfire 前缀
VOCABULARY_MODEL = "fun-asr"  # DashScope ASR 模型


def get_filename_from_url(url: str) -> str:
    """从 URL 中提取文件名（不含扩展名）"""
    parsed = urlparse(url)
    filename = unquote(Path(parsed.path).stem)
    return filename


def fetch_transcription_result(transcription_url: str) -> dict:
    """通过 HTTP 获取转写结果 JSON"""
    response = requests.get(transcription_url)
    response.raise_for_status()
    return response.json()


def extract_transcript(result: dict) -> dict:
    """提取 text 字段和时间戳，返回简化的结果（包含词级别时间戳）"""
    transcripts = []

    if 'transcripts' in result:
        for item in result['transcripts']:
            # 提取句子级别的时间戳（包含词级别）
            sentences = []
            for sent in item.get('sentences', []):
                sentence_data = {
                    'begin_time': sent.get('begin_time', 0),
                    'end_time': sent.get('end_time', 0),
                    'text': sent.get('text', '')
                }
                # 提取词级别时间戳（如果存在）
                if 'words' in sent:
                    sentence_data['words'] = [
                        {
                            'begin_time': word.get('begin_time', 0),
                            'end_time': word.get('end_time', 0),
                            'text': word.get('text', '')
                        }
                        for word in sent.get('words', [])
                    ]
                sentences.append(sentence_data)

            transcripts.append({
                'channel_id': item.get('channel_id', 0),
                'transcript': item.get('text', ''),  # API 返回的字段名是 text
                'sentences': sentences  # 带时间戳的句子列表（含词级别）
            })

    return {
        'file_url': result.get('file_url', ''),
        'transcripts': transcripts
    }


def load_questionbank(question_bank_path: str | Path) -> List[Dict]:
    """
    从指定路径加载题库文件

    Args:
        question_bank_path: 题库文件路径

    Returns:
        题库条目列表

    Raises:
        FileNotFoundError: 题库文件不存在
    """
    path = Path(question_bank_path)

    if not path.exists():
        raise FileNotFoundError(f"题库文件不存在: {question_bank_path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"已加载题库: {path.name}, 条目数: {len(data)}")
    return data


def detect_lang(text: str) -> str:
    """
    检测文本是中文还是英文

    Args:
        text: 待检测文本

    Returns:
        "zh" 如果是中文，"en" 如果是英文
    """
    # 检查是否包含中文字符
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return "zh"
    return "en"


def extract_vocabulary(questionbank: List[Dict]) -> List[Dict[str, any]]:
    """
    从题库提取热词列表

    Args:
        questionbank: 题库条目列表

    Returns:
        热词列表，格式: [{"text": "word", "weight": 4, "lang": "zh|en"}, ...]
    """
    vocabulary = []
    seen = set()  # 去重

    def add_word(text: str):
        """添加单个词到热词列表"""
        text = text.strip()
        if text and text not in seen:
            seen.add(text)
            lang = detect_lang(text)
            vocabulary.append({"text": text, "weight": 4, "lang": lang})

    for item in questionbank:
        # 提取 question
        question = item.get('question', '').strip()
        if question:
            # 按顿号、逗号拆分
            for word in re.split(r'[、，,]', question):
                add_word(word)

        # 提取 answer
        answer = item.get('answer', '').strip()
        if answer:
            for word in re.split(r'[、，,]', answer):
                add_word(word)

    print(f"提取热词数: {len(vocabulary)} (去重后)")
    return vocabulary


class VocabularySlotManager:
    """热词槽位管理器，实现复用策略"""

    def __init__(self, prefix: str = VOCABULARY_PREFIX, model: str = VOCABULARY_MODEL):
        """
        初始化热词槽位管理器

        Args:
            prefix: 热词槽位前缀
            model: ASR 模型名称
        """
        self.service = VocabularyService()
        self.vocabulary_id = None
        self.prefix = prefix
        self.model = model

    def get_or_create_slot(self) -> str:
        """
        获取或创建热词槽位
        优先复用已有的槽位，没有则创建新的

        Returns:
            vocabulary_id
        """
        try:
            # 优先查找指定前缀的槽位
            existing = self.service.list_vocabularies(prefix=self.prefix)
            if existing:
                self.vocabulary_id = existing[0]['vocabulary_id']
                print(f"复用热词槽位 (prefix={self.prefix}): {self.vocabulary_id}")
                return self.vocabulary_id

            # 没有指定前缀的，复用任意现有槽位
            all_vocabs = self.service.list_vocabularies()
            if all_vocabs:
                self.vocabulary_id = all_vocabs[0]['vocabulary_id']
                print(f"复用现有热词槽位: {self.vocabulary_id}")
                return self.vocabulary_id

        except Exception as e:
            print(f"查询热词槽位失败: {e}")

        # 只有在完全没有槽位时才创建新的
        initial_vocab = [{"text": "初始化", "weight": 1, "lang": "zh"}]
        try:
            self.vocabulary_id = self.service.create_vocabulary(
                prefix=self.prefix,
                target_model=self.model,
                vocabulary=initial_vocab
            )
            print(f"创建新热词槽位: {self.vocabulary_id}")
            return self.vocabulary_id
        except Exception as e:
            print(f"创建热词槽位失败: {e}")
            raise

    def update_vocabulary(self, vocabulary: List[Dict]) -> None:
        """
        更新热词内容

        Args:
            vocabulary: 新的热词列表
        """
        if not self.vocabulary_id:
            raise ValueError("未初始化热词槽位，请先调用 get_or_create_slot()")

        try:
            self.service.update_vocabulary(self.vocabulary_id, vocabulary)
            print(f"已更新热词槽位 {self.vocabulary_id}，词数: {len(vocabulary)}")
        except Exception as e:
            print(f"更新热词失败: {e}")
            raise


def async_transcribe(
    file_urls: list[str],
    poll_interval: int = 5,
    vocabulary_id: str = None
) -> list[dict]:
    """
    异步提交转写任务并轮询获取结果

    Args:
        file_urls: 音频文件 URL 列表
        poll_interval: 轮询间隔（秒）
        vocabulary_id: 热词表 ID（可选）

    Returns:
        转写结果列表
    """
    print(f"提交 {len(file_urls)} 个文件进行转写...")
    if vocabulary_id:
        print(f"使用热词表: {vocabulary_id}")

    # 异步提交任务
    task_response = Transcription.async_call(
        model='fun-asr',  # 使用 fun-asr 模型
        file_urls=file_urls,
        vocabulary_id=vocabulary_id,  # 热词表 ID
        language_hints=['zh', 'en']
    )

    task_id = task_response.output.task_id
    print(f"任务已提交，task_id: {task_id}")

    # 轮询等待结果
    while True:
        transcribe_response = Transcription.fetch(task=task_id)
        status = transcribe_response.output.task_status

        print(f"任务状态: {status}")

        if status in ('SUCCEEDED', 'FAILED'):
            break

        time.sleep(poll_interval)

    # 处理结果
    results = []

    if transcribe_response.status_code == HTTPStatus.OK:
        for item in transcribe_response.output.results:
            file_url = item.get('file_url', '')
            subtask_status = item.get('subtask_status', '')

            if subtask_status == 'SUCCEEDED':
                transcription_url = item.get('transcription_url', '')
                if transcription_url:
                    try:
                        # 通过 HTTP 获取转写结果
                        full_result = fetch_transcription_result(transcription_url)
                        full_result['file_url'] = file_url
                        result = extract_transcript(full_result)
                        results.append(result)
                        print(f"✓ 成功获取: {get_filename_from_url(file_url)}")
                    except Exception as e:
                        print(f"✗ 获取结果失败 {file_url}: {e}")
            else:
                code = item.get('code', '')
                message = item.get('message', '')
                print(f"✗ 子任务失败 {file_url}: {code} - {message}")
    else:
        print(f"任务失败: {transcribe_response.code} - {transcribe_response.message}")

    return results


class FunASRTimestampProvider:
    """FunASR Timestamp Provider for audio transcription with sentence-level timestamps.

    提供 FunASR 语音转写功能，支持：
    - 句子级别时间戳生成（sentences）
    - 基于题库的动态热词管理
    - 异步批量转写

    Attributes:
        vocab_manager: 热词槽位管理器
        model: 使用的 ASR 模型名称

    Example:
        >>> provider = FunASRTimestampProvider()
        >>> result = provider.transcribe_with_timestamp(
        ...     audio_url="https://...",
        ...     vocabulary_path="vocab.json"
        ... )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        vocabulary_prefix: str = VOCABULARY_PREFIX,
        model: str = VOCABULARY_MODEL
    ):
        """
        初始化 FunASR Timestamp Provider

        Args:
            api_key: DashScope API key. If None, uses DASHSCOPE_API_KEY env var.
            vocabulary_prefix: 热词槽位前缀
            model: ASR 模型名称
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if self.api_key:
            dashscope.api_key = self.api_key

        self.model = model
        self.vocab_manager = VocabularySlotManager(prefix=vocabulary_prefix, model=model)
        self._vocabulary_initialized = False

    def _init_vocabulary(self, vocabulary_path: Optional[str] = None) -> Optional[str]:
        """
        初始化热词（懒加载）

        Args:
            vocabulary_path: 题库文件路径

        Returns:
            vocabulary_id 或 None
        """
        if not vocabulary_path:
            return None

        try:
            # 加载题库并更新热词
            questionbank = load_questionbank(vocabulary_path)
            vocabulary = extract_vocabulary(questionbank)

            self.vocab_manager.get_or_create_slot()
            self.vocab_manager.update_vocabulary(vocabulary)
            self._vocabulary_initialized = True

            return self.vocab_manager.vocabulary_id
        except Exception as e:
            print(f"热词初始化失败: {e}")
            return None

    def transcribe_with_timestamp(
        self,
        audio_url: str,
        vocabulary_path: Optional[str] = None,
        poll_interval: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        使用 OSS URL 进行转写并返回带时间戳的结果

        Args:
            audio_url: 音频文件 OSS URL
            vocabulary_path: 可选的题库文件路径
            poll_interval: 轮询间隔（秒）

        Returns:
            转写结果字典，包含 transcripts 和 sentences
            None 如果转写失败
        """
        # 初始化热词（如果提供了词汇表）
        vocabulary_id = None
        if vocabulary_path:
            vocabulary_id = self._init_vocabulary(vocabulary_path)

        # 使用异步 Transcription API
        results = async_transcribe(
            [audio_url],
            poll_interval=poll_interval,
            vocabulary_id=vocabulary_id
        )

        if results and len(results) > 0:
            return results[0]
        return None

    def transcribe_local_audio(
        self,
        audio_file: Path,
        vocabulary_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        使用本地音频文件进行转写（fallback，可能无时间戳）

        注意：Recognition API 可能不返回 sentences，建议优先使用 OSS URL。

        Args:
            audio_file: 本地音频文件路径
            vocabulary_path: 可选的题库文件路径

        Returns:
            转写结果字典
            None 如果转写失败
        """
        # 初始化热词（如果提供了词汇表）
        vocabulary_id = None
        if vocabulary_path:
            vocabulary_id = self._init_vocabulary(vocabulary_path)

        try:
            # 检测音频采样率
            try:
                ffprobe_result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                     '-show_entries', 'stream=sample_rate',
                     '-of', 'default=noprint_wrappers=1:nokey=1',
                     str(audio_file)],
                    capture_output=True, text=True, timeout=10
                )
                detected_sample_rate = int(ffprobe_result.stdout.strip())
            except Exception:
                detected_sample_rate = 16000

            recognition = Recognition(
                model=self.model,
                format=audio_file.suffix.lstrip('.'),
                sample_rate=detected_sample_rate,
                callback=None,
                vocabulary_id=vocabulary_id,
                language_hints=['zh', 'en']
            )

            result = recognition.call(str(audio_file))

            if result.status_code == HTTPStatus.OK:
                sentences = result.output.get('sentences', [])

                output = {
                    'file_url': f'file://{audio_file}',
                    'transcripts': [{
                        'channel_id': 0,
                        'transcript': result.output.get('text', ''),
                        'sentences': sentences
                    }]
                }

                return output
            else:
                print(f"识别失败: {result.code} - {result.message}")
                return None

        except Exception as e:
            print(f"本地音频转写失败: {e}")
            return None

    def transcribe_and_save(
        self,
        audio_source: str,
        output_dir: Path,
        student_name: str,
        vocabulary_path: Optional[str] = None,
        output_filename: str = "3_asr_timestamp.json",
        oss_url: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """
        转写音频并保存结果到文件

        Args:
            audio_source: 音频源（OSS URL 或本地文件路径）
            output_dir: 输出目录
            student_name: 学生名称（用于日志）
            vocabulary_path: 可选的题库文件路径
            output_filename: 输出文件名
            oss_url: 可选的 OSS URL（优先使用）
            force: 是否强制重新处理

        Returns:
            True 成功，False 失败
        """
        output_path = output_dir / output_filename

        # 检查是否需要处理
        if not force and output_path.exists():
            print(f"  ✓ {student_name}: 已处理过（跳过）")
            return True

        # 优先使用 OSS URL
        if oss_url:
            print(f"  ⟳ {student_name}: 使用 OSS URL 转写...")
            result = self.transcribe_with_timestamp(
                audio_url=oss_url,
                vocabulary_path=vocabulary_path
            )

            if result:
                sentences = []
                for transcript in result.get('transcripts', []):
                    sentences.extend(transcript.get('sentences', []))

                # 严格校验 - sentences 为空则视为失败
                if not sentences:
                    print(f"  ✗ {student_name}: 转写成功但 sentences 为空")
                    return False

                # 保存结果
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                print(f"  ✓ {student_name}: 已保存到 {output_filename} (sentences: {len(sentences)})")
                return True
            else:
                print(f"  ✗ {student_name}: Transcription API 未返回结果")
                return False

        # Fallback: 本地文件
        audio_file = Path(audio_source)
        if not audio_file.exists():
            print(f"  ⊘ {student_name}: 音频文件不存在且无 OSS URL")
            return False

        print(f"  ⟳ {student_name}: 使用本地文件转写 (可能无时间戳)...")
        result = self.transcribe_local_audio(
            audio_file=audio_file,
            vocabulary_path=vocabulary_path
        )

        if result:
            sentences = []
            for transcript in result.get('transcripts', []):
                sentences.extend(transcript.get('sentences', []))

            if not sentences:
                print(f"  ✗ {student_name}: Recognition API 不支持 sentences，需要 OSS URL")
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"  ✓ {student_name}: 已保存到 {output_filename} (sentences: {len(sentences)})")
            return True
        else:
            print(f"  ✗ {student_name}: 本地文件转写失败")
            return False
