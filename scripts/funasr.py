"""
FunASR 异步语音转写脚本
使用阿里云 DashScope API 进行批量音频转写
支持基于题库的动态热词管理
"""
from http import HTTPStatus
from dashscope.audio.asr import Transcription, VocabularyService, Recognition
import dashscope
import os
import json
import time
import re
import requests
import argparse
from pathlib import Path
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
from typing import List, Dict, Optional

# 加载 .env 文件
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 北京地域 URL
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / 'asr_timestamp'

# 题库目录
QUESTIONBANK_DIR = Path(__file__).parent.parent / 'questionbank'

# 热词配置
VOCABULARY_PREFIX = "qf"  # quickfire 前缀
VOCABULARY_MODEL = "fun-asr-2025-11-07"  # 与转写模型一致


def get_filename_from_url(url: str) -> str:
    """从 URL 中提取文件名（不含扩展名）"""
    parsed = urlparse(url)
    filename = unquote(Path(parsed.path).stem)
    return filename


def parse_audio_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    解析音频文件名: {ClassCode}_{Date}_{QuestionBank}_{Student}.mp3

    Args:
        filename: 文件名（不含扩展名）

    Returns:
        解析结果字典，包含 class_code, date, question_bank, student
        解析失败返回 None
    """
    # 匹配格式: ClassCode_Date_QuestionBank_Student
    # 例如: Zoe41900_2025-09-08_R1-65-D5_Oscar
    pattern = r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)_(.+)$'
    match = re.match(pattern, filename)

    if match:
        return {
            'class_code': match.group(1),
            'date': match.group(2),
            'question_bank': match.group(3),
            'student': match.group(4)
        }
    return None


def load_questionbank(question_bank_code: str) -> List[Dict]:
    """
    从题库目录加载指定的题库文件

    Args:
        question_bank_code: 题库代码，如 R1-65-D5

    Returns:
        题库条目列表

    Raises:
        FileNotFoundError: 题库文件不存在
    """
    questionbank_path = QUESTIONBANK_DIR / f"{question_bank_code}.json"

    if not questionbank_path.exists():
        raise FileNotFoundError(
            f"题库文件不存在: {questionbank_path}\n"
            f"期望路径: questionbank/{question_bank_code}.json"
        )

    with open(questionbank_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"已加载题库: {question_bank_code}.json, 条目数: {len(data)}")
    return data


def extract_vocabulary(questionbank: List[Dict]) -> List[Dict[str, any]]:
    """
    从题库提取热词列表

    Args:
        questionbank: 题库条目列表

    Returns:
        热词列表，格式: [{"text": "word", "weight": 4, "lang": "zh"}, ...]
    """
    vocabulary = []
    seen = set()  # 去重

    def add_word(text: str):
        """添加单个词到热词列表"""
        text = text.strip()
        if text and text not in seen:
            seen.add(text)
            vocabulary.append({"text": text, "weight": 4, "lang": "zh"})

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

    def __init__(self):
        self.service = VocabularyService()
        self.vocabulary_id = None

    def get_or_create_slot(self) -> str:
        """
        获取或创建热词槽位
        优先复用已有的槽位，没有则创建新的

        Returns:
            vocabulary_id
        """
        try:
            # 优先查找指定前缀的槽位
            existing = self.service.list_vocabularies(prefix=VOCABULARY_PREFIX)
            if existing:
                self.vocabulary_id = existing[0]['vocabulary_id']
                print(f"复用热词槽位 (prefix={VOCABULARY_PREFIX}): {self.vocabulary_id}")
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
                prefix=VOCABULARY_PREFIX,
                target_model=VOCABULARY_MODEL,
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


def fetch_transcription_result(transcription_url: str) -> dict:
    """通过 HTTP 获取转写结果 JSON"""
    response = requests.get(transcription_url)
    response.raise_for_status()
    return response.json()


def extract_transcript(result: dict) -> dict:
    """提取 text 字段和时间戳，返回简化的结果"""
    transcripts = []

    if 'transcripts' in result:
        for item in result['transcripts']:
            # 提取句子级别的时间戳
            sentences = []
            for sent in item.get('sentences', []):
                sentences.append({
                    'begin_time': sent.get('begin_time', 0),
                    'end_time': sent.get('end_time', 0),
                    'text': sent.get('text', '')
                })

            transcripts.append({
                'channel_id': item.get('channel_id', 0),
                'transcript': item.get('text', ''),  # API 返回的字段名是 text
                'sentences': sentences  # 带时间戳的句子列表
            })

    return {
        'file_url': result.get('file_url', ''),
        'transcripts': transcripts
    }


def recognize_with_vocabulary(
    audio_file: str,
    vocabulary_id: str,
    audio_format: str = 'mp3',
    sample_rate: int = 16000
) -> dict:
    """
    使用热词进行同步语音识别

    Args:
        audio_file: 本地音频文件路径
        vocabulary_id: 热词槽位 ID
        audio_format: 音频格式 (mp3, wav, etc.)
        sample_rate: 采样率

    Returns:
        识别结果
    """
    recognition = Recognition(
        model=VOCABULARY_MODEL,
        format=audio_format,
        sample_rate=sample_rate,
        callback=None,
        vocabulary_id=vocabulary_id,
        language_hints=['zh', 'en']
    )

    result = recognition.call(audio_file)

    # 解析结果
    if result.status_code == HTTPStatus.OK:
        return {
            'file_path': audio_file,
            'transcript': result.output.get('text', ''),
            'sentences': result.output.get('sentences', [])
        }
    else:
        raise Exception(f"识别失败: {result.code} - {result.message}")


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
            questionbank = load_questionbank(qb_code)
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
        model='fun-asr-2025-11-07',
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


def main():
    parser = argparse.ArgumentParser(description='FunASR 异步语音转写（支持动态热词）')
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
