# -*- coding: utf-8 -*-
"""
三方 ASR 横向对比（FunASR / Qwen ASR / 豆包）

对比三家 ASR 在教师-学生音频场景下的转写效果和说话人分离能力。
控制变量：相同音频、相同 context/热词、说话人分离均指定 2 人。

使用方法：
    uv run python .claude/skills/qwen-asr-context/scripts/asr_compare.py \
        --audio real_test/Batch/Student.mp3 \
        --qwen-archive archive/Batch/Student/2_qwen_asr.json \
        --output docs/asr_compare_xxx
"""

import argparse
import json
import os
import sys
import time
import uuid
import requests
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

import oss2
import dashscope
from dashscope.audio.asr import Transcription
from dotenv import load_dotenv

# ASR context（控制变量 - 三者共享相同的上下文描述）
DEFAULT_CONTEXT = (
    "这是一段中英文混合的语音录音。英语教育场景（抽背单词），"
    "录音中有老师和学生交替说话。内容涉及英文单词、中文释义。"
    "请原样转写，听到什么语言就写什么语言，不要翻译。"
    "即使音量小或语速快，也要尽量识别完整，不要遗漏。"
)


def load_env():
    """加载环境变量（从项目根目录 scripts/.env）"""
    # 向上查找 scripts/.env
    candidate_dirs = [
        Path.cwd(),
        Path.cwd() / "scripts",
        Path(__file__).resolve().parent.parent.parent.parent.parent / "scripts",
    ]
    for d in candidate_dirs:
        env_path = d / ".env" if d.name == "scripts" else d / "scripts" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            break

    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope.api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")


def upload_to_oss(local_path: Path) -> str:
    """上传音频到 OSS，返回签名 URL（有效期 1 小时）"""
    access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "").strip()
    access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "").strip()
    endpoint = os.getenv("OSS_ENDPOINT", "oss-cn-shanghai.aliyuncs.com").strip()
    bucket_name = os.getenv("OSS_BUCKET_NAME", "quickfire-audio").strip()

    if not access_key_id or not access_key_secret:
        raise ValueError("OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET 未设置")

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, f"https://{endpoint}", bucket_name)

    # ASCII-only key 避免签名问题
    stem = local_path.stem.encode("ascii", "replace").decode()
    oss_key = f"asr_compare/{stem}_{int(time.time())}.mp3"
    bucket.put_object_from_file(oss_key, str(local_path))

    signed_url = bucket.sign_url("GET", oss_key, 3600, slash_safe=True)
    print(f"  已上传: {oss_key}")
    print(f"  签名 URL: {signed_url[:80]}...")
    return signed_url


# ============================================================
# 1. FunASR（说话人分离）
# ============================================================

def run_funasr(oss_url: str) -> dict:
    """
    FunASR 转写，开启说话人分离（2人）

    参数:
        diarization_enabled=True  开启说话人分离
        speaker_count=2           指定 2 个说话人
    """
    print("\n" + "=" * 60)
    print("▶  FunASR（说话人分离 speaker_count=2）")
    print("=" * 60)

    task_response = Transcription.async_call(
        model="fun-asr",
        file_urls=[oss_url],
        language_hints=["zh", "en"],
        diarization_enabled=True,
        speaker_count=2,
    )

    task_id = task_response.output.task_id
    print(f"  任务已提交, task_id: {task_id}")

    # 轮询等待
    while True:
        resp = Transcription.fetch(task=task_id)
        status = resp.output.task_status
        print(f"  状态: {status}")
        if status in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(3)

    result = {"provider": "funasr", "raw_response": None, "transcripts": []}

    if resp.status_code == HTTPStatus.OK:
        for item in resp.output.results:
            if item.get("subtask_status") == "SUCCEEDED":
                url = item.get("transcription_url", "")
                if url:
                    full = requests.get(url).json()
                    result["raw_response"] = full
                    result["transcripts"] = full.get("transcripts", [])
                    print(f"  转写成功，sentences 数: "
                          f"{sum(len(t.get('sentences', [])) for t in result['transcripts'])}")
            else:
                print(f"  子任务失败: {item.get('code')} - {item.get('message')}")
    else:
        print(f"  任务失败: {resp.code} - {resp.message}")

    return result


# ============================================================
# 2. Qwen ASR（加载已有结果）
# ============================================================

def load_qwen_asr(archive_path: Path) -> dict:
    """加载已有的 Qwen ASR 结果"""
    print("\n" + "=" * 60)
    print("▶  Qwen ASR（加载已有结果）")
    print("=" * 60)

    with open(archive_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 提取文本
    text = ""
    try:
        text = data["output"]["choices"][0]["message"]["content"][0]["text"]
    except (KeyError, IndexError):
        pass

    print(f"  已加载 archive 结果，文本长度: {len(text)}")
    return {"provider": "qwen_asr", "raw_response": data, "text": text}


# ============================================================
# 3. 豆包 / Volcengine ASR（说话人分离）
# ============================================================

def run_doubao(oss_url: str, context: str) -> dict:
    """
    豆包大模型语音识别，开启说话人分离

    - Endpoint: openspeech-direct.zijieapi.com
    - 状态码在 response headers (X-Api-Status-Code)
    """
    print("\n" + "=" * 60)
    print("▶  豆包 Volcengine ASR（说话人分离）")
    print("=" * 60)

    app_key = os.getenv("X-Api-App-Key")
    access_key = os.getenv("X-Api-Access-Key")

    if not app_key or not access_key:
        print("  X-Api-App-Key / X-Api-Access-Key 未设置，跳过豆包测试")
        return {"provider": "doubao", "error": "API Key 未配置", "raw_response": None}

    request_id = str(uuid.uuid4())

    submit_headers = {
        "X-Api-App-Key": app_key,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": "volc.bigasr.auc",
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }

    payload = {
        "user": {"uid": "quickfire_compare"},
        "audio": {
            "url": oss_url,
            "format": "mp3",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_speaker_info": True,
            "enable_punc": True,
            "enable_itn": True,
            "show_utterances": True,
            "corpus": {
                "context": context,
            },
        },
    }

    submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
    print(f"  提交任务, request_id: {request_id}")

    try:
        resp = requests.post(
            submit_url,
            data=json.dumps(payload),
            headers=submit_headers,
            timeout=30,
        )
        status_code = resp.headers.get("X-Api-Status-Code", "")
        message = resp.headers.get("X-Api-Message", "")
        x_tt_logid = resp.headers.get("X-Tt-Logid", "")
        print(f"  提交响应: code={status_code}, message={message}")

        if status_code != "20000000":
            return {
                "provider": "doubao",
                "error": f"提交失败: code={status_code} msg={message}",
                "raw_response": {"headers": dict(resp.headers)},
            }

        # 轮询查询结果
        query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"
        query_headers = {
            "X-Api-App-Key": app_key,
            "X-Api-Access-Key": access_key,
            "X-Api-Resource-Id": "volc.bigasr.auc",
            "X-Api-Request-Id": request_id,
            "X-Tt-Logid": x_tt_logid,
        }

        for attempt in range(120):  # 最多等 2 分钟
            time.sleep(1)
            query_resp = requests.post(
                query_url,
                data=json.dumps({}),
                headers=query_headers,
                timeout=30,
            )
            q_code = query_resp.headers.get("X-Api-Status-Code", "")

            if q_code == "20000000":
                print(f"  转写完成!")
                result_data = query_resp.json()
                return {
                    "provider": "doubao",
                    "raw_response": result_data,
                    "text": result_data.get("result", {}).get("text", ""),
                    "utterances": result_data.get("result", {}).get("utterances", []),
                }
            elif q_code in ("20000001", "20000002"):
                if attempt % 5 == 0:
                    print(f"  轮询 #{attempt + 1}: 处理中 (code={q_code})...")
                continue
            else:
                q_msg = query_resp.headers.get("X-Api-Message", "")
                print(f"  查询失败: code={q_code} msg={q_msg}")
                return {
                    "provider": "doubao",
                    "error": f"查询失败: code={q_code} msg={q_msg}",
                    "raw_response": {"headers": dict(query_resp.headers)},
                }

        return {"provider": "doubao", "error": "超时", "raw_response": None}

    except Exception as e:
        print(f"  豆包 ASR 异常: {e}")
        return {"provider": "doubao", "error": str(e), "raw_response": None}


# ============================================================
# 对比报告生成
# ============================================================

def extract_funasr_text_with_speakers(result: dict) -> list[dict]:
    """从 FunASR 结果提取带说话人标签的句子"""
    sentences = []
    for transcript in result.get("transcripts", []):
        for sent in transcript.get("sentences", []):
            sentences.append({
                "begin_time": sent.get("begin_time", 0),
                "end_time": sent.get("end_time", 0),
                "text": sent.get("text", ""),
                "speaker_id": sent.get("speaker_id", -1),
            })
    return sentences


def extract_doubao_text_with_speakers(result: dict) -> list[dict]:
    """从豆包结果提取带说话人标签的句子"""
    utterances = result.get("utterances", [])
    sentences = []
    for utt in utterances:
        additions = utt.get("additions", {})
        speaker_id = int(additions.get("speaker", -1)) if additions.get("speaker") else -1
        sentences.append({
            "begin_time": utt.get("start_time", 0),
            "end_time": utt.get("end_time", 0),
            "text": utt.get("text", ""),
            "speaker_id": speaker_id,
        })
    return sentences


def format_time(ms: int) -> str:
    """毫秒 → MM:SS.s"""
    s = ms / 1000
    m = int(s // 60)
    return f"{m:02d}:{s - m * 60:05.2f}"


def generate_report(
    funasr_result: dict,
    qwen_result: dict,
    doubao_result: dict,
    audio_path: str,
    context: str,
) -> str:
    """生成 Markdown 对比报告"""
    lines = [
        "# ASR 三方说话人分离对比报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**测试音频**: `{audio_path}`",
        f"**目标**: 对比三家 ASR 在教师-学生音频场景下的转写效果和说话人分离能力",
        "",
        "## 控制变量",
        "",
        f"- **Context**: {context[:80]}...",
        "- **说话人数**: 2（教师 + 学生）",
        "- **语言**: 中英混合",
        "",
    ]

    # --- Qwen ASR ---
    lines.extend([
        "## 1. Qwen ASR (qwen3-asr-flash)",
        "",
        "**特点**: 无说话人分离、无时间戳，纯文本输出",
        "",
        "```",
        qwen_result.get("text", "（无结果）"),
        "```",
        "",
    ])

    # --- FunASR ---
    lines.extend([
        "## 2. FunASR (fun-asr + diarization)",
        "",
        "**特点**: 句子级时间戳 + 说话人分离 (speaker_id)",
        "",
    ])

    funasr_sentences = extract_funasr_text_with_speakers(funasr_result)
    if funasr_sentences:
        speaker_ids = set(s["speaker_id"] for s in funasr_sentences)
        lines.append(f"**检测到 {len(speaker_ids)} 个说话人**: {sorted(speaker_ids)}")
        lines.append("")

        lines.append("| 时间 | Speaker | 文本 |")
        lines.append("|------|---------|------|")
        for s in funasr_sentences:
            t = f"{format_time(s['begin_time'])} - {format_time(s['end_time'])}"
            spk = f"spk{s['speaker_id']}" if s["speaker_id"] >= 0 else "?"
            lines.append(f"| {t} | {spk} | {s['text']} |")
        lines.append("")

        full_text = "".join(s["text"] for s in funasr_sentences)
        lines.extend([
            "**纯文本（合并）**:",
            "```",
            full_text,
            "```",
            "",
        ])
    else:
        lines.append("（无结果或 sentences 为空）\n")

    # --- 豆包 ---
    lines.extend([
        "## 3. 豆包 Volcengine ASR (bigmodel + speaker_info)",
        "",
        "**特点**: 句子级时间戳 + 说话人聚类",
        "",
    ])

    if doubao_result.get("error"):
        lines.append(f"**错误**: {doubao_result['error']}\n")
    else:
        doubao_sentences = extract_doubao_text_with_speakers(doubao_result)
        if doubao_sentences:
            speaker_ids = set(s["speaker_id"] for s in doubao_sentences)
            lines.append(f"**检测到 {len(speaker_ids)} 个说话人**: {sorted(speaker_ids)}")
            lines.append("")

            lines.append("| 时间 | Speaker | 文本 |")
            lines.append("|------|---------|------|")
            for s in doubao_sentences:
                t = f"{format_time(s['begin_time'])} - {format_time(s['end_time'])}"
                spk = f"spk{s['speaker_id']}" if s["speaker_id"] >= 0 else "?"
                lines.append(f"| {t} | {spk} | {s['text']} |")
            lines.append("")

            full_text = "".join(s["text"] for s in doubao_sentences)
            lines.extend([
                "**纯文本（合并）**:",
                "```",
                full_text,
                "```",
                "",
            ])
        elif doubao_result.get("text"):
            lines.extend([
                "```",
                doubao_result["text"],
                "```",
                "",
            ])
        else:
            lines.append("（无结果）\n")

    # --- 对比总结 ---
    lines.extend([
        "## 对比总结",
        "",
        "| 维度 | Qwen ASR | FunASR | 豆包 |",
        "|------|----------|--------|------|",
        "| 说话人分离 | 不支持 | speaker_id | speaker_info |",
        "| 时间戳 | 无 | 句子+词级 | 句子级 |",
        f"| 漏说检测 | 需人工 | 可按 speaker 过滤 | 可按 speaker 过滤 |",
        "",
        "## 下一步建议",
        "",
        "1. 对比三者的转写**完整度**（是否有漏词）",
        "2. 检查 FunASR/豆包的 speaker_id 是否正确区分了教师和学生",
        "3. 评估说话人分离对评测流程的实际价值",
        "",
    ])

    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="三方 ASR 横向对比（Qwen / FunASR / 豆包）"
    )
    parser.add_argument(
        "--audio", required=True,
        help="音频文件路径（mp3/wav）"
    )
    parser.add_argument(
        "--qwen-archive", required=True,
        help="已有 Qwen ASR 结果 JSON 路径（如 archive/.../2_qwen_asr.json）"
    )
    parser.add_argument(
        "--output", required=True,
        help="输出目录（保存 JSON 结果和 MD 报告）"
    )
    parser.add_argument(
        "--context",
        default=DEFAULT_CONTEXT,
        help="ASR context 文本（控制变量）"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    audio_path = Path(args.audio).resolve()
    qwen_archive = Path(args.qwen_archive).resolve()
    output_dir = Path(args.output).resolve()

    load_env()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"测试音频: {audio_path}")
    print(f"输出目录: {output_dir}")

    if not audio_path.exists():
        print(f"音频文件不存在: {audio_path}")
        sys.exit(1)

    if not qwen_archive.exists():
        print(f"Qwen ASR 结果不存在: {qwen_archive}")
        sys.exit(1)

    # Step 1: 上传音频到 OSS（FunASR 和豆包都需要 URL）
    print("\n上传音频到 OSS...")
    oss_url = upload_to_oss(audio_path)

    # Step 2: 串行运行三个 ASR（避免限流）
    qwen_result = load_qwen_asr(qwen_archive)
    funasr_result = run_funasr(oss_url)
    doubao_result = run_doubao(oss_url, args.context)

    # Step 3: 保存原始结果
    for name, result in [
        ("funasr_diarization", funasr_result),
        ("qwen_asr", qwen_result),
        ("doubao_asr", doubao_result),
    ]:
        path = output_dir / f"{name}_result.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n已保存: {path}")

    # Step 4: 生成对比报告
    report = generate_report(
        funasr_result, qwen_result, doubao_result,
        audio_path=str(audio_path), context=args.context,
    )
    report_path = output_dir / "compare_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n对比报告已生成: {report_path}")

    # 简要输出
    print("\n" + "=" * 60)
    print("三方 ASR 对比完成")
    print("=" * 60)

    qwen_text = qwen_result.get("text", "")
    funasr_sents = extract_funasr_text_with_speakers(funasr_result)
    funasr_text = "".join(s["text"] for s in funasr_sents)

    print(f"\n  Qwen ASR 文本长度:  {len(qwen_text)}")
    print(f"  FunASR 文本长度:    {len(funasr_text)}")
    print(f"  FunASR 句子数:      {len(funasr_sents)}")
    if funasr_sents:
        speakers = set(s["speaker_id"] for s in funasr_sents)
        print(f"  FunASR 说话人数:    {len(speakers)} ({sorted(speakers)})")


if __name__ == "__main__":
    main()
