"""
FunASR 异步语音转写脚本
使用阿里云 DashScope API 进行批量音频转写
"""
from http import HTTPStatus
from dashscope.audio.asr import Transcription
import dashscope
import os
import json
import time
import requests
import argparse
from pathlib import Path
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 北京地域 URL
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / 'asr_timestamp'


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


def async_transcribe(file_urls: list[str], poll_interval: int = 5) -> list[dict]:
    """
    异步提交转写任务并轮询获取结果

    Args:
        file_urls: 音频文件 URL 列表
        poll_interval: 轮询间隔（秒）

    Returns:
        转写结果列表
    """
    print(f"提交 {len(file_urls)} 个文件进行转写...")

    # 异步提交任务
    # sensevoice-v1 模型支持多语言，默认自动检测
    # 使用 language_hints 参数指定 zh 和 en 可避免识别出日语等
    task_response = Transcription.async_call(
        model='fun-asr-2025-11-07',
        file_urls=file_urls, # 中英混合，避免识别出日语等
        language_hints=['zh','en']
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
    parser = argparse.ArgumentParser(description='FunASR 异步语音转写')
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

    args = parser.parse_args()

    # 如果没有提供 URL，使用示例 URL
    file_urls = args.file_urls or [
        'https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/Zoe41900_2025-09-08_R1-65-D5_Oscar.mp3',
        'https://quickfire-audio.oss-cn-shanghai.aliyuncs.com/audio/Zoe51530_2025-09-08_R3-14-D4_Alvin.mp3'
    ]

    print(f"输出目录: {args.output}")
    print("-" * 50)

    # 执行转写
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
