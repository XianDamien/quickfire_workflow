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
VOCABULARY_MODEL = "paraformer-realtime-v2"  # DashScope ASR 模型


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


def load_questionbank(question_bank_path: str | Path) -> List[Dict]:
    """
    从指定路径加载题库文件

    Args:
        question_bank_path: 题库文件路径（可以是完整路径或题库代码）

    Returns:
        题库条目列表

    Raises:
        FileNotFoundError: 题库文件不存在
    """
    path = Path(question_bank_path)

    # 如果不是完整路径，尝试在 questionbank/ 目录查找
    if not path.exists():
        # 尝试作为题库代码处理
        questionbank_path_full = QUESTIONBANK_DIR / f"{question_bank_path}.json"
        if questionbank_path_full.exists():
            path = questionbank_path_full
        else:
            raise FileNotFoundError(
                f"题库文件不存在: {question_bank_path}\n"
                f"尝试路径: {path}, {questionbank_path_full}"
            )

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"已加载题库: {path.name}, 条目数: {len(data)}")
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
        model='paraformer-v2',  # 使用 paraformer-v2 模型
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
    vocabulary_id: Optional[str] = None,
    force: bool = False,
    oss_url: Optional[str] = None
) -> bool:
    """
    处理单个 archive 学生的音频转写（优先使用 OSS URL + Transcription API）

    Args:
        student_dir: 学生目录路径
        student_name: 学生名称
        vocabulary_id: 热词槽位 ID
        force: 是否强制重新处理
        oss_url: OSS URL（如果有的话，优先使用）

    Returns:
        True 成功，False 失败
    """
    # 检查是否需要处理
    if not force and not should_process_archive_student(student_dir):
        print(f"  ✓ {student_name}: 已处理过（跳过）")
        return True

    # 优先使用 OSS URL + Transcription API（支持 sentences）
    if oss_url:
        print(f"  ⟳ {student_name}: 使用 OSS URL 转写...")
        try:
            # 使用异步 Transcription API
            results = async_transcribe([oss_url], poll_interval=3, vocabulary_id=vocabulary_id)

            if results and len(results) > 0:
                result = results[0]
                sentences = []
                for transcript in result.get('transcripts', []):
                    sentences.extend(transcript.get('sentences', []))

                # Phase 1: 严格校验 - sentences 为空则视为失败
                if not sentences:
                    print(f"  ✗ {student_name}: 转写成功但 sentences 为空，不保存 3_asr_timestamp.json")
                    print(f"     原因: Transcription API 未返回句子级别的时间戳数据")
                    return False

                # 保存结果
                output_path = student_dir / "3_asr_timestamp.json"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                print(f"  ✓ {student_name}: 已保存到 3_asr_timestamp.json (sentences: {len(sentences)})")
                return True
            else:
                print(f"  ✗ {student_name}: Transcription API 未返回结果")
                return False

        except Exception as e:
            print(f"  ✗ {student_name}: OSS 转写失败 - {str(e)}")
            return False

    # Fallback: 本地文件 + Recognition API（可能没有 sentences）
    audio_file = find_archive_audio_file(student_dir)
    if not audio_file:
        print(f"  ⊘ {student_name}: 未找到音频文件且无 OSS URL")
        return False

    try:
        print(f"  ⟳ {student_name}: 使用本地文件转写 (可能无时间戳)...")

        # 检测音频采样率
        import subprocess
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
            model=VOCABULARY_MODEL,
            format=audio_file.suffix.lstrip('.'),
            sample_rate=detected_sample_rate,
            callback=None,
            vocabulary_id=vocabulary_id,
            language_hints=['zh', 'en']
        )

        result = recognition.call(str(audio_file))

        if result.status_code == HTTPStatus.OK:
            sentences = result.output.get('sentences', [])
            if not sentences:
                print(f"  ✗ {student_name}: Recognition API 不支持 sentences，需要 OSS URL")
                print(f"     请确保 metadata.json 中包含该学生的 oss_url")
                return False

            output = {
                'file_url': f'file://{audio_file}',
                'transcripts': [{
                    'channel_id': 0,
                    'transcript': result.output.get('text', ''),
                    'sentences': sentences
                }]
            }

            output_path = student_dir / "3_asr_timestamp.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"  ✓ {student_name}: 已保存到 3_asr_timestamp.json (sentences: {len(sentences)})")
            return True
        else:
            print(f"  ✗ {student_name}: 识别失败 - {result.code}: {result.message}")
            return False

    except Exception as e:
        print(f"  ✗ {student_name}: 错误 - {str(e)}")
        return False


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

    # 初始化热词
    vocabulary_id = None
    if use_hotwords:
        vocab_file = find_archive_vocabulary_file(archive_batch, metadata)
        if vocab_file:
            print(f"   📚 题库: {vocab_file.name}")
            try:
                # 加载题库并更新热词（使用完整路径）
                questionbank = load_questionbank(vocab_file)
                vocabulary = extract_vocabulary(questionbank)

                vocab_manager = VocabularySlotManager()
                vocab_manager.get_or_create_slot()
                vocab_manager.update_vocabulary(vocabulary)
                vocabulary_id = vocab_manager.vocabulary_id
            except Exception as e:
                print(f"   ⚠️  热词初始化失败: {e}")
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
            vocabulary_id=vocabulary_id,
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
