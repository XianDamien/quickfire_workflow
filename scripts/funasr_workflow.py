"""
FunASR 工作流模块

集成阿里云 FunASR 服务，支持：
1. 本地文件上传到 OSS
2. FunASR 异步转写
3. 结果标准化处理

依赖：
- dashscope (阿里云官方 SDK)
- alibabacloud_oss_v2 (阿里云 OSS SDK)
- 环境变量：DASHSCOPE_API_KEY, OSS_REGION (可选), OSS_BUCKET (可选)
"""

import json
import os
import time
from http import HTTPStatus
from pathlib import Path

import dashscope
from dashscope.audio.asr import Transcription

# 延迟导入 OSS SDK，以支持仅 Qwen 模式
try:
    import alibabacloud_oss_v2 as oss
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False


def upload_audio_to_oss(local_path, region, bucket, endpoint=None, keep_file=False):
    """
    将本地音频文件上传到阿里云 OSS

    Args:
        local_path (str): 本地音频文件路径
        region (str): OSS 区域（如 cn-hangzhou）
        bucket (str): OSS 桶名称
        endpoint (str, optional): OSS 端点，默认为 None 使用默认端点
        keep_file (bool, optional): 转写完成后是否保留文件，默认 False

    Returns:
        tuple: (oss_url, status_code, file_key)
            - oss_url (str): 上传文件的 OSS URL
            - status_code (int): HTTP 状态码
            - file_key (str): 文件在 OSS 中的 key

    Raises:
        FileNotFoundError: 本地文件不存在
        ImportError: 缺少 alibabacloud_oss_v2 依赖
        Exception: OSS 上传失败
    """
    # 检查 OSS 依赖
    if not OSS_AVAILABLE:
        raise ImportError(
            "缺少 alibabacloud_oss_v2 依赖。请安装：\n"
            "  pip install alibabacloud_oss_v2"
        )

    # 验证本地文件是否存在
    if not Path(local_path).exists():
        raise FileNotFoundError(f"本地文件不存在: {local_path}")

    # 从环境变量读取 OSS 凭证
    # 优先级：ALIBABA_CLOUD_* → OSS_* → 不存在
    access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')

    # 如果标准环境变量不存在，尝试读取 OSS_* 格式的变量
    if not access_key_id or not access_key_secret:
        access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
        access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')

    if not access_key_id or not access_key_secret:
        raise ValueError(
            "OSS 凭证缺失。请设置以下环境变量之一：\n"
            "  1. ALIBABA_CLOUD_ACCESS_KEY_ID + ALIBABA_CLOUD_ACCESS_KEY_SECRET\n"
            "  2. OSS_ACCESS_KEY_ID + OSS_ACCESS_KEY_SECRET（在 .env 文件中）"
        )

    # 使用静态凭证提供器
    credentials_provider = oss.credentials.StaticCredentialsProvider(access_key_id, access_key_secret)
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = region

    if endpoint:
        cfg.endpoint = endpoint

    # 创建 OSS 客户端
    client = oss.Client(cfg)

    # 生成 OSS key（使用文件名）
    file_name = Path(local_path).name
    file_key = f"audio/{file_name}"  # 存储在 audio/ 前缀下

    print(f"   📤 正在上传文件到 OSS: {file_key}")

    try:
        # 上传文件
        result = client.put_object_from_file(
            oss.PutObjectRequest(
                bucket=bucket,
                key=file_key
            ),
            local_path
        )

        # 构建 OSS URL
        # 注意：这里需要根据实际的 OSS 配置调整 URL 格式
        oss_url = f"https://{bucket}.oss-{region}.aliyuncs.com/{file_key}"

        print(f"   ✅ 上传完成 (状态码: {result.status_code})")
        print(f"   📍 OSS URL: {oss_url}")

        return oss_url, result.status_code, file_key

    except Exception as e:
        raise Exception(f"OSS 上传失败: {str(e)}")


def transcribe_with_funasr(oss_url, max_retries=10, retry_interval=2):
    """
    使用 FunASR 转写 OSS 中的音频文件

    Args:
        oss_url (str): OSS 中音频文件的 URL
        max_retries (int, optional): 最多轮询次数，默认 10 次
        retry_interval (int, optional): 轮询间隔（秒），默认 2 秒

    Returns:
        dict: FunASR 转写结果

    Raises:
        Exception: 转写失败或超时
    """
    print(f"   🎯 提交 FunASR 异步任务...")

    # 设置 API Key
    api_key = os.getenv('DASHSCOPE_API_KEY')
    if not api_key:
        raise ValueError("未设置环境变量 DASHSCOPE_API_KEY")

    # 提交异步转写任务
    response = Transcription.async_call(
        api_key=api_key,
        model='fun-asr',
        file_urls=[oss_url]
    )

    if response.status_code != HTTPStatus.OK:
        raise Exception(f"提交 FunASR 任务失败: {response.message}")

    task_id = response.output.task_id
    print(f"   📋 任务 ID: {task_id}")
    print(f"   ⏳ 开始轮询转写结果（最多 {max_retries} 次，间隔 {retry_interval} 秒）...")

    # 轮询任务状态
    for attempt in range(1, max_retries + 1):
        print(f"   [{attempt}/{max_retries}] 检查任务状态...")
        time.sleep(retry_interval)

        status_response = Transcription.fetch(
            api_key=api_key,
            task=task_id
        )

        task_status = status_response.output.task_status
        print(f"        状态: {task_status}")

        if task_status == 'SUCCEEDED':
            print(f"   ✅ 转写完成（耗时 {attempt * retry_interval} 秒）")
            return status_response.output

        elif task_status == 'FAILED':
            error_msg = status_response.output.error_message if hasattr(status_response.output, 'error_message') else "未知错误"
            raise Exception(f"FunASR 转写失败: {error_msg}")

    raise Exception(f"转写超时：轮询 {max_retries} 次后仍未完成，请稍后查询任务 ID: {task_id}")


def normalize_asr_output(funasr_result):
    """
    将 FunASR 的输出结果转换为标准格式（与 Qwen ASR 兼容）

    FunASR 的输出为两阶段过程：
    1. 初始响应包含 metadata（transcription_url）
    2. 需要从 transcription_url 获取实际转写结果

    原始响应格式：
    {
        "task_id": "xxx",
        "task_status": "SUCCEEDED",
        "results": [
            {
                "file_url": "...",
                "transcription_url": "...",  // 需要下载此 URL 获取实际结果
                "subtask_status": "SUCCEEDED"
            }
        ]
    }

    transcription_url 返回的格式：
    {
        "results": [
            {
                "channel_id": 0,
                "text": "...",
                "sentences": [...]
            }
        ]
    }

    标准格式（JSON 数组）：
    [
        {
            "speaker": "spk0",
            "text": "...",
            "start_time": xxx,  // 毫秒
            "end_time": xxx,    // 毫秒
            "word_timestamp": [...]
        }
    ]

    Args:
        funasr_result (dict): FunASR 的原始输出

    Returns:
        str: 标准化的 JSON 字符串（与 Qwen ASR 格式一致）
    """
    import urllib.request

    print("   🔄 正在标准化 FunASR 输出...")

    try:
        normalized = []

        # 直接访问 results 属性（不使用 vars，因为这可能是数据类）
        results = getattr(funasr_result, 'results', None)
        print(f"   📋 FunASR.results 条目数: {len(results) if results else 0}")

        # 检查结果结构
        if not results:
            print("   ⚠️  警告：FunASR 结果为空或格式异常")
            return json.dumps([], ensure_ascii=False)

        # 遍历每个转写任务的结果
        for result in results:
            # result 可能是字典或对象，兼容两种情况
            if isinstance(result, dict):
                transcription_url = result.get('transcription_url', None)
            else:
                transcription_url = getattr(result, 'transcription_url', None)

            if not transcription_url:
                print(f"   ⚠️  结果缺少 transcription_url，跳过")
                print(f"   📋 结果内容: {result}")
                continue

            print(f"   📥 下载转写结果: {transcription_url[:80]}...")
            try:
                # 下载转写结果 JSON
                with urllib.request.urlopen(transcription_url) as response:
                    transcription_data = json.loads(response.read().decode('utf-8'))

                # 获取转写结果中的 transcripts 列表（FunASR 返回 transcripts 而不是 results）
                transcription_results = transcription_data.get('transcripts', [])
                print(f"   ✅ 获得 {len(transcription_results)} 个转写通道")

                # 处理每个转写结果
                for transcription_item in transcription_results:
                    channel_id = transcription_item.get('channel_id', 0)
                    text = transcription_item.get('text', '')

                    # 获取句子级别的时间戳
                    sentences = transcription_item.get('sentences', [])

                    if sentences:
                        for sentence in sentences:
                            sentence_text = sentence.get('text', '')  # FunASR 使用 'text' 而不是 'content'
                            # FunASR 使用 begin_time 和 end_time，而不是 start_time 和 end_time
                            start_time = sentence.get('begin_time', 0)
                            end_time = sentence.get('end_time', 0)

                            entry = {
                                "speaker": f"spk{channel_id}",
                                "text": sentence_text,
                                "start_time": int(start_time),
                                "end_time": int(end_time),
                                "word_timestamp": []
                            }

                            # 如果存在词级信息，可以添加（可选）
                            words = sentence.get('words', [])
                            if words:
                                entry["word_timestamp"] = [
                                    {
                                        "word": w.get('text', ''),
                                        "start": int(w.get('begin_time', 0)),
                                        "end": int(w.get('end_time', 0))
                                    }
                                    for w in words
                                ]

                            normalized.append(entry)
                    else:
                        # 如果没有句子信息，使用整体文本
                        if text:
                            entry = {
                                "speaker": f"spk{channel_id}",
                                "text": text,
                                "start_time": 0,
                                "end_time": 0,
                                "word_timestamp": []
                            }
                            normalized.append(entry)

            except Exception as e:
                print(f"   ❌ 下载/解析转写结果失败: {str(e)}")
                continue

        print(f"   ✅ 标准化完成 ({len(normalized)} 条转写结果)")
        return json.dumps(normalized, ensure_ascii=False)

    except Exception as e:
        raise Exception(f"标准化 FunASR 输出失败: {str(e)}")


# ===== 测试和调试函数 =====

def test_upload_to_oss(audio_path, region, bucket):
    """
    测试上传功能

    用法：
        python3 -c "from funasr_workflow import test_upload_to_oss; test_upload_to_oss('./audio/sample.mp3', 'cn-hangzhou', 'your-bucket')"
    """
    try:
        oss_url, status, key = upload_audio_to_oss(audio_path, region, bucket)
        print(f"\n✅ 上传成功！")
        print(f"   URL: {oss_url}")
        print(f"   Key: {key}")
        print(f"   Status: {status}")
        return oss_url
    except Exception as e:
        print(f"\n❌ 上传失败: {str(e)}")
        return None


def test_transcribe(oss_url):
    """
    测试转写功能

    用法：
        python3 -c "from funasr_workflow import test_transcribe; result = test_transcribe('https://...'); print(result)"
    """
    try:
        result = transcribe_with_funasr(oss_url)
        print(f"\n✅ 转写成功！")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except Exception as e:
        print(f"\n❌ 转写失败: {str(e)}")
        return None


def test_normalize(funasr_result):
    """
    测试标准化功能

    用法：
        from funasr_workflow import test_normalize
        # 假设 result 是从 transcribe_with_funasr 获得的结果对象
        normalized = test_normalize(result)
        print(normalized)
    """
    try:
        normalized_str = normalize_asr_output(funasr_result)
        print(f"\n✅ 标准化成功！")
        print(normalized_str)
        return normalized_str
    except Exception as e:
        print(f"\n❌ 标准化失败: {str(e)}")
        return None
