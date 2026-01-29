# -*- coding: utf-8 -*-
"""
scripts/gemini_batch_audio.py - Gemini Batch API 音频版批量处理脚本

直接将原始音频文件作为 multimodal 输入，让 Gemini 直接听音频进行评分。
用于对比 ASR 时间戳方案与音频直接输入方案的效果。

用法:
    uv run python scripts/gemini_batch_audio.py submit --archive-batch <name>
    uv run python scripts/gemini_batch_audio.py fetch --manifest <path>
    uv run python scripts/gemini_batch_audio.py run --archive-batch <name>

对比基准:
    uv run python scripts/gemini_batch.py run --archive-batch <name>  # ASR 版本
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 加载环境变量
from scripts.common.env import load_env, require_env
load_env()

import httpx
from google import genai
from google.genai import types


# ============================================================================
# 配置常量
# ============================================================================

DEFAULT_MODEL = "gemini-3-pro-preview"
DEFAULT_POLL_INTERVAL = 30
DEFAULT_TIMEOUT = 300000  # 毫秒
COMPLETED_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}

# 音频版 prompt 模板
AUDIO_PROMPT_TEMPLATE = "user_with_audio.md"

# 音频输出标识
AUDIO_SUFFIX = ".audio"

# 统一错误码
ERROR_API = "api_error"
ERROR_INVALID_KEY = "invalid_key"
ERROR_NO_RESPONSE = "no_response"
ERROR_EXTRACT_FAILED = "extract_failed"
ERROR_JSON_PARSE_FAILED = "json_parse_failed"
ERROR_VALIDATION_FAILED = "validation_failed"
ERROR_INVALID_GRADE = "invalid_grade"
ERROR_SAVE_FAILED = "save_failed"


def audio_run_dir_name(run_id: str) -> str:
    return f"{run_id}{AUDIO_SUFFIX}"


def audio_annotator_name(model: str) -> str:
    return f"{model}{AUDIO_SUFFIX}"


# ============================================================================
# SDK 客户端初始化（支持代理）
# ============================================================================

def create_client(
    proxy: Optional[str] = None,
    timeout_ms: int = DEFAULT_TIMEOUT,
) -> genai.Client:
    """创建带代理的 Gemini SDK 客户端"""
    api_key = require_env("GEMINI_API_KEY")

    if proxy is None:
        proxy = (
            os.getenv("HTTPS_PROXY")
            or os.getenv("ALL_PROXY")
            or os.getenv("HTTP_PROXY")
            or os.getenv("PROXY")
        )
        if not proxy:
            proxy = "socks5://127.0.0.1:7890"

    http_options_kwargs: Dict[str, Any] = {"timeout": timeout_ms}

    if proxy:
        print(f"  使用代理: {proxy}")
        transport = httpx.HTTPTransport(proxy=proxy, retries=3)
        custom_client = httpx.Client(
            transport=transport,
            timeout=timeout_ms / 1000,
            follow_redirects=True,
        )
        http_options_kwargs["httpx_client"] = custom_client

    http_options = types.HttpOptions(**http_options_kwargs)

    return genai.Client(api_key=api_key, http_options=http_options)


# ============================================================================
# 音频文件上传
# ============================================================================

def upload_audio_files(
    client: genai.Client,
    archive_batch: str,
    students: List[str],
) -> Dict[str, str]:
    """
    批量上传音频文件到 Gemini File API

    Returns:
        Dict[student_name, file_uri] 映射
    """
    from scripts.common.archive import student_dir

    file_map = {}
    errors = []

    print(f"\n  上传音频文件...")

    for i, student in enumerate(students, 1):
        stu_dir = student_dir(archive_batch, student)
        audio_path = stu_dir / "1_input_audio.mp3"

        if not audio_path.exists():
            print(f"   [{i}/{len(students)}] {student}: 无音频文件")
            errors.append(student)
            continue

        try:
            print(f"   [{i}/{len(students)}] {student}...", end=" ", flush=True)
            uploaded = client.files.upload(
                file=str(audio_path),
                config=types.UploadFileConfig(
                    display_name=f"{archive_batch}-{student}-audio",
                    mime_type="audio/mpeg"
                )
            )
            # 使用完整的 uri 而不是 name
            # uri 格式: https://generativelanguage.googleapis.com/v1beta/files/xxx
            file_map[student] = uploaded.uri
            print(f"ok ({uploaded.name})")
        except Exception as e:
            print(f"failed: {e}")
            errors.append(student)

    if errors:
        print(f"\n   {len(errors)} 个学生上传失败: {errors}")

    return file_map


# ============================================================================
# 构建音频版请求
# ============================================================================

def build_audio_request(
    archive_batch: str,
    student_name: str,
    run_id: str,
    audio_file_uri: str,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    为单个学生构建音频版 batch request

    使用 multimodal 请求，同时传入音频文件和文本 prompt
    """
    from scripts.common.archive import (
        student_dir,
        resolve_question_bank,
        load_metadata,
        load_file_content,
    )

    # 加载 prompt loader
    prompt_dir = _PROJECT_ROOT / "prompts" / "annotation"
    sys.path.insert(0, str(_PROJECT_ROOT / "prompts"))
    from jinja2 import Environment

    # 加载学生数据
    stu_dir = student_dir(archive_batch, student_name)
    qwen_asr_path = stu_dir / "2_qwen_asr.json"

    if not qwen_asr_path.exists():
        raise FileNotFoundError(f"未找到 ASR 文件: {qwen_asr_path}")

    # 加载 metadata 和题库
    try:
        metadata = load_metadata(archive_batch)
    except FileNotFoundError:
        metadata = {}

    question_bank_path = resolve_question_bank(archive_batch, metadata)
    if not question_bank_path:
        raise FileNotFoundError("未找到题库文件")

    question_bank_content = load_file_content(question_bank_path)

    # 提取纯文本 ASR（仅保留文本，过滤元数据）
    from scripts.common.asr import extract_qwen_asr_text
    with open(qwen_asr_path, "r", encoding="utf-8") as f:
        asr_data = json.load(f)

    # 检查 ASR 是否成功
    if asr_data.get("status_code") != 200 or asr_data.get("output") is None:
        error_msg = asr_data.get("message", "ASR 失败")
        raise ValueError(f"ASR 失败: {error_msg}")

    asr_text = extract_qwen_asr_text(asr_data)

    # 加载音频版 prompt 模板
    audio_template_path = prompt_dir / AUDIO_PROMPT_TEMPLATE
    if not audio_template_path.exists():
        raise FileNotFoundError(f"未找到音频版模板: {audio_template_path}")

    with open(audio_template_path, "r", encoding="utf-8") as f:
        template_text = f.read()

    # 加载 system prompt
    system_path = prompt_dir / "system.md"
    system_instruction = ""
    if system_path.exists():
        with open(system_path, "r", encoding="utf-8") as f:
            system_instruction = f.read().strip()

    # 渲染模板
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_text)

    # 音频作为 multimodal part 传入，模板中的占位符用说明文字
    full_prompt = template.render(
        question_bank_json=question_bank_content,
        student_asr_text=asr_text,
        student_input_audio="[音频文件已作为附件传入，请直接读取分析]",
    )

    # 构建 multimodal request
    # 音频作为第一个 part，文本作为第二个 part
    request = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "fileData": {
                            "fileUri": audio_file_uri,
                            "mimeType": "audio/mpeg"
                        }
                    },
                    {"text": full_prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
        }
    }

    if system_instruction:
        request["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    # 加载 prompt 版本信息
    metadata_path = prompt_dir / "metadata.json"
    prompt_version = "unknown"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            prompt_metadata = json.load(f)
            prompt_version = prompt_metadata.get("prompt_version", "unknown")

    return {
        "key": f"{archive_batch}:{student_name}:{run_id}",
        "request": request,
        # 额外信息用于保存 prompt_log
        "_prompt_info": {
            "full_prompt": full_prompt,
            "system_instruction": system_instruction,
            "prompt_version": prompt_version,
            "question_bank_path": str(question_bank_path),
            "audio_file_uri": audio_file_uri,
        }
    }


# ============================================================================
# 生成 JSONL
# ============================================================================

def generate_jsonl(
    archive_batch: str,
    students: List[str],
    run_id: str,
    audio_file_map: Dict[str, str],
    output_path: Path,
    model: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:
    """
    生成音频版 JSONL 输入文件，同时为每个学生保存 prompt_log.txt

    Args:
        archive_batch: batch 名称
        students: 学生列表
        run_id: 运行 ID
        audio_file_map: 学生->音频文件URI映射
        output_path: 输出文件路径
        model: 模型名称

    Returns:
        生成的请求列表（用于 manifest）
    """
    from scripts.common.runs import ensure_run_dir, get_git_commit

    requests = []
    errors = []

    print(f"\n  生成 JSONL 文件: {output_path.name}")

    git_commit = get_git_commit(short=False)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, student in enumerate(students, 1):
            if student not in audio_file_map:
                print(f"   [{i}/{len(students)}] {student}: 跳过（无音频）")
                continue

            try:
                print(f"   [{i}/{len(students)}] {student}...", end=" ")
                req = build_audio_request(
                    archive_batch=archive_batch,
                    student_name=student,
                    run_id=run_id,
                    audio_file_uri=audio_file_map[student],
                    model=model,
                )

                # 写入 JSONL（不包含 _prompt_info）
                jsonl_entry = {"key": req["key"], "request": req["request"]}
                f.write(json.dumps(jsonl_entry, ensure_ascii=False) + "\n")

                # 保存 prompt_log.txt 到学生 run 目录
                prompt_info = req.get("_prompt_info", {})
                if prompt_info:
                    stu_run_dir = ensure_run_dir(
                        archive_batch=archive_batch,
                        student_name=student,
                        annotator_name=audio_annotator_name(model),
                        run_id=run_id,
                    )
                    prompt_log_path = stu_run_dir / "prompt_log.txt"
                    with open(prompt_log_path, "w", encoding="utf-8") as pf:
                        pf.write("=== Batch Audio API 完整提示词日志 ===\n\n")
                        pf.write(f"生成时间: {datetime.now().isoformat()}\n")
                        pf.write(f"Run ID: {run_id}\n")
                        pf.write(f"Model: {model}\n")
                        pf.write(f"Git Commit: {git_commit}\n")
                        pf.write(f"Student: {student}\n")
                        pf.write(f"Archive Batch: {archive_batch}\n")
                        pf.write(f"Prompt Version: {prompt_info.get('prompt_version', 'unknown')}\n")
                        pf.write(f"Question Bank: {prompt_info.get('question_bank_path', 'unknown')}\n")
                        pf.write(f"Audio File URI: {prompt_info.get('audio_file_uri', 'unknown')}\n")
                        pf.write(f"User Prompt 长度: {len(prompt_info.get('full_prompt', ''))} 字符\n")
                        pf.write(f"System Instruction 长度: {len(prompt_info.get('system_instruction', ''))} 字符\n")
                        pf.write(f"\n{'='*60}\n")
                        pf.write("System Instruction:\n")
                        pf.write(f"{'='*60}\n\n")
                        pf.write(prompt_info.get("system_instruction", "") or "(无)")
                        pf.write(f"\n\n{'='*60}\n")
                        pf.write("User Prompt:\n")
                        pf.write(f"{'='*60}\n\n")
                        pf.write(prompt_info.get("full_prompt", ""))

                requests.append({
                    "key": req["key"],
                    "student_name": student,
                    "audio_file": audio_file_map[student],
                })
                print("ok")
            except Exception as e:
                print(f"failed: {e}")
                errors.append({"student": student, "error": str(e)})

    print(f"\n  成功生成 {len(requests)} 条请求")
    return requests


# ============================================================================
# Submit 命令
# ============================================================================

def cmd_submit(args: argparse.Namespace) -> int:
    """提交音频 batch job（不等待结果）"""
    from scripts.common.archive import archive_batch_dir, list_students
    from scripts.common.runs import new_run_id

    archive_batch = args.archive_batch
    model = args.model or DEFAULT_MODEL

    # 确定学生列表
    if args.students:
        students = [s.strip() for s in args.students.split(",")]
    else:
        students = list_students(archive_batch)

    if not students:
        print(f"  未找到学生: {archive_batch}")
        return 1

    print(f"\n{'='*60}")
    print(f"  Gemini Batch API - 音频版 (submit)")
    print(f"{'='*60}")
    print(f"  Batch: {archive_batch}")
    print(f"  Model: {model}")
    print(f"  学生: {len(students)} 人")

    run_started_at = datetime.now()
    run_id = new_run_id()
    print(f"  Run ID: {run_id}")

    # 准备输出目录
    batch_path = archive_batch_dir(archive_batch)
    run_dir = batch_path / "_batch_runs" / audio_run_dir_name(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    # ========== Phase 1: 上传音频 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 1: 上传音频文件")
    print(f"{'─'*60}")

    client = create_client(proxy=args.proxy)

    upload_start = time.time()
    audio_file_map = upload_audio_files(client, archive_batch, students)
    upload_time = time.time() - upload_start

    print(f"\n  上传完成: {len(audio_file_map)}/{len(students)} ({upload_time:.1f}s)")

    if not audio_file_map:
        print("  没有可用的音频文件，终止")
        return 1

    # ========== Phase 2: 生成 JSONL ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 2: 生成 JSONL")
    print(f"{'─'*60}")

    jsonl_path = run_dir / "batch_input.jsonl"
    requests = generate_jsonl(
        archive_batch=archive_batch,
        students=students,
        run_id=run_id,
        audio_file_map=audio_file_map,
        output_path=jsonl_path,
        model=model,
    )

    if not requests:
        print("  没有有效的请求，终止")
        return 1

    # ========== Phase 3: 上传 JSONL 并提交 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 3: 提交 Batch Job")
    print(f"{'─'*60}")

    print(f"  上传 JSONL...")
    jsonl_upload_start = time.time()
    try:
        uploaded_jsonl = client.files.upload(
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=f"audio-batch-{archive_batch}-{run_id}",
                mime_type="jsonl"
            )
        )
        jsonl_upload_time = time.time() - jsonl_upload_start
        print(f"  ok: {uploaded_jsonl.name} ({jsonl_upload_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    display_name = args.display_name or f"audio-{archive_batch}-{run_id}"
    print(f"  创建 Batch Job ({display_name})...")

    submit_start = time.time()
    try:
        batch_job = client.batches.create(
            model=model,
            src=uploaded_jsonl.name,
            config={"display_name": display_name},
        )
        submit_time = time.time() - submit_start
        print(f"  ok: {batch_job.name} ({submit_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    submitted_at = datetime.now()
    state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)

    manifest = {
        "archive_batch": archive_batch,
        "run_id": run_id,
        "model": model,
        "mode": "audio",
        "job_name": batch_job.name,
        "display_name": display_name,
        "input_file": uploaded_jsonl.name,
        "submitted_at": submitted_at.isoformat(),
        "state": state,
        "requests": requests,
        "students_count": len(students),
        "audio_files": audio_file_map,
        "timing": {
            "started_at": run_started_at.isoformat(),
            "submitted_at": submitted_at.isoformat(),
            "audio_upload_time_seconds": round(upload_time, 2),
            "jsonl_upload_time_seconds": round(jsonl_upload_time, 2),
            "submit_time_seconds": round(submit_time, 2),
        },
    }

    manifest_path = run_dir / "batch_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n  Manifest: {manifest_path}")
    print(f"  Fetch 命令: uv run python scripts/gemini_batch_audio.py fetch --manifest {manifest_path}")

    return 0


# ============================================================================
# Fetch 命令
# ============================================================================

def cmd_fetch(args: argparse.Namespace) -> int:
    """获取音频 batch job 结果并回填"""
    from scripts.common.runs import ensure_run_dir, write_run_manifest, get_git_commit
    from scripts.contracts.cards import validate_cards, parse_api_response

    manifest = None
    manifest_path = None
    job_name = None

    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"  Manifest 文件不存在: {manifest_path}")
            return 1
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        job_name = manifest["job_name"]
        print(f"  从 Manifest 加载: {manifest_path}")
    elif args.job:
        job_name = args.job
        print(f"  使用 Job Name: {job_name}")
    else:
        print("  必须指定 --manifest 或 --job")
        return 1

    client = create_client(proxy=args.proxy)

    poll_interval = args.poll_interval or DEFAULT_POLL_INTERVAL
    timeout = args.timeout

    print(f"\n{'─'*60}")
    print(f"  等待 Batch Job 完成")
    print(f"{'─'*60}")
    print(f"  Job: {job_name}")

    poll_start_time = time.time()
    poll_count = 0

    while True:
        batch_job = client.batches.get(name=job_name)
        state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
        elapsed = time.time() - poll_start_time
        poll_count += 1

        print(f"  [{elapsed:.0f}s] {state}")

        if state in COMPLETED_STATES:
            break

        if timeout and elapsed > timeout:
            print(f"\n  超时 ({timeout}s)")
            return 1

        time.sleep(poll_interval)

    api_processing_time = time.time() - poll_start_time
    final_state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
    print(f"\n  Job 完成: {final_state} ({api_processing_time:.1f}s)")

    if final_state != "JOB_STATE_SUCCEEDED":
        print(f"  Job 未成功")
        return 1

    if not batch_job.dest or not batch_job.dest.file_name:
        print("  无结果文件")
        return 1

    result_file_name = batch_job.dest.file_name
    print(f"  下载: {result_file_name}")

    download_start = time.time()
    try:
        result_content = client.files.download(file=result_file_name)
        result_text = result_content.decode("utf-8")
        download_time = time.time() - download_start
        print(f"  ok ({download_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    if manifest_path:
        raw_result_path = manifest_path.parent / "batch_output.jsonl"
        with open(raw_result_path, "w", encoding="utf-8") as f:
            f.write(result_text)

    results = []
    for line in result_text.strip().split("\n"):
        if line.strip():
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    success_count = 0
    fail_count = 0
    grade_distribution = {"A": 0, "B": 0, "C": 0}
    student_results = []
    total_tokens = {
        "prompt_tokens": 0,
        "thoughts_tokens": 0,
        "candidates_tokens": 0,
        "total_tokens": 0,
    }

    model = manifest.get("model", DEFAULT_MODEL) if manifest else DEFAULT_MODEL

    for result in results:
        key = result.get("key", "")
        parts = key.split(":")
        if len(parts) != 3:
            fail_count += 1
            continue

        archive_batch_key, student_name, run_id_key = parts

        usage = result.get("response", {}).get("usageMetadata", {})
        total_tokens["prompt_tokens"] += usage.get("promptTokenCount", 0)
        total_tokens["thoughts_tokens"] += usage.get("thoughtsTokenCount", 0)
        total_tokens["candidates_tokens"] += usage.get("candidatesTokenCount", 0)
        total_tokens["total_tokens"] += usage.get("totalTokenCount", 0)

        if "error" in result:
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_API})
            continue

        response = result.get("response", {})
        if not response:
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_NO_RESPONSE})
            continue

        try:
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("无候选结果")
            content = candidates[0].get("content", {})
            parts_list = content.get("parts", [])
            if not parts_list:
                raise ValueError("无内容")
            raw_text = parts_list[0].get("text", "")
        except Exception as e:
            print(f"   ✗ {student_name}: 提取响应失败 - {e}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_EXTRACT_FAILED})
            continue

        parsed = parse_api_response(raw_text)
        if parsed.get("_parse_error"):
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_JSON_PARSE_FAILED})
            continue

        annotations = parsed["annotations"]
        final_grade = parsed["final_grade_suggestion"]
        mistake_count = parsed["mistake_count"]

        is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
        if not is_valid:
            print(f"   ✗ {student_name}: 校验失败 ({len(invalid_items)} 无效项)")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_VALIDATION_FAILED})
            continue

        if final_grade not in ["A", "B", "C"]:
            print(f"   ✗ {student_name}: 无效评分 {final_grade}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_INVALID_GRADE})
            continue

        try:
            annotator_name = audio_annotator_name(model)
            stu_run_dir = ensure_run_dir(
                archive_batch=archive_batch_key,
                student_name=student_name,
                annotator_name=annotator_name,
                run_id=run_id_key,
            )

            annotation_result = {
                "student_name": student_name,
                "final_grade_suggestion": final_grade,
                "mistake_count": mistake_count,
                "annotations": annotations,
                "ink": "normal",  # Batch API 模式下默认为 normal（未运行 gatekeeper）
                "_metadata": {
                    "model": model,
                    "mode": "audio",
                    "batch_job": job_name,
                    "run_id": run_id_key,
                    "git_commit": get_git_commit(short=False),
                    "timestamp": datetime.now().isoformat(),
                    "source": "batch_api_audio",
                }
            }

            annotation_path = stu_run_dir / "4_llm_annotation.json"
            with open(annotation_path, "w", encoding="utf-8") as f:
                json.dump(annotation_result, f, ensure_ascii=False, indent=2)

            write_run_manifest(
                run_dir=stu_run_dir,
                annotator_name=annotator_name,
                run_id=run_id_key,
                archive_batch=archive_batch_key,
                student_name=student_name,
                prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / "user_with_audio.md",
                prompt_hash="batch_audio",
                model=model,
                extra={"mode": "audio"},
            )

            success_count += 1
            grade_distribution[final_grade] += 1
            student_results.append({
                "student": student_name,
                "status": "success",
                "grade": final_grade,
                "mistake_count": mistake_count,
            })

        except Exception as e:
            print(f"   ✗ {student_name}: 保存失败 - {e}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_SAVE_FAILED})

    if manifest and manifest_path:
        manifest["mode"] = "audio"
        manifest["fetched_at"] = datetime.now().isoformat()
        manifest["result_file"] = result_file_name
        manifest["final_state"] = final_state
        manifest["statistics"] = {
            "students_count": manifest.get("students_count", len(student_results)),
            "success_count": success_count,
            "fail_count": fail_count,
            "grade_distribution": grade_distribution,
        }
        manifest["token_usage"] = total_tokens
        manifest["student_results"] = student_results

        timing = manifest.get("timing", {})
        timing.update({
            "fetched_at": datetime.now().isoformat(),
            "api_processing_time_seconds": round(api_processing_time, 2),
            "download_time_seconds": round(download_time, 2),
            "poll_count": poll_count,
        })
        manifest["timing"] = timing

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        _generate_batch_report(
            run_dir=manifest_path.parent,
            archive_batch=manifest.get("archive_batch", ""),
            model=model,
            run_id=manifest.get("run_id", ""),
            results=results,
            student_results=student_results,
            grade_distribution=grade_distribution,
            total_tokens=total_tokens,
            manifest=manifest,
        )

    print(f"\n  回填完成: 成功 {success_count} 失败 {fail_count}")
    return 0 if fail_count == 0 else 1


# ============================================================================
# Run 命令
# ============================================================================

def cmd_run(args: argparse.Namespace) -> int:
    """一键运行：上传音频 → 生成 JSONL → 提交 batch → 等待 → 回填"""
    from scripts.common.archive import archive_batch_dir, list_students
    from scripts.common.runs import (
        new_run_id,
        ensure_run_dir,
        write_run_manifest,
        get_git_commit,
    )
    from scripts.contracts.cards import validate_cards, parse_api_response

    archive_batch = args.archive_batch
    model = args.model or DEFAULT_MODEL
    poll_interval = args.poll_interval or DEFAULT_POLL_INTERVAL
    timeout = args.timeout

    # 确定学生列表
    if args.students:
        students = [s.strip() for s in args.students.split(",")]
    else:
        students = list_students(archive_batch)

    if not students:
        print(f"  未找到学生: {archive_batch}")
        return 1

    print(f"\n{'='*60}")
    print(f"  Gemini Batch API - 音频版")
    print(f"{'='*60}")
    print(f"  Batch: {archive_batch}")
    print(f"  Model: {model}")
    print(f"  学生: {len(students)} 人")

    run_start_time = time.time()
    run_started_at = datetime.now()

    run_id = new_run_id()
    print(f"  Run ID: {run_id}")

    # 准备输出目录
    batch_path = archive_batch_dir(archive_batch)
    run_dir = batch_path / "_batch_runs" / audio_run_dir_name(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    # ========== Phase 1: 上传音频 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 1: 上传音频文件")
    print(f"{'─'*60}")

    client = create_client(proxy=args.proxy)

    upload_start = time.time()
    audio_file_map = upload_audio_files(client, archive_batch, students)
    upload_time = time.time() - upload_start

    print(f"\n  上传完成: {len(audio_file_map)}/{len(students)} ({upload_time:.1f}s)")

    if not audio_file_map:
        print("  没有可用的音频文件，终止")
        return 1

    # ========== Phase 2: 生成 JSONL ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 2: 生成 JSONL")
    print(f"{'─'*60}")

    jsonl_path = run_dir / "batch_input.jsonl"
    requests = generate_jsonl(
        archive_batch=archive_batch,
        students=students,
        run_id=run_id,
        audio_file_map=audio_file_map,
        output_path=jsonl_path,
        model=model,
    )

    if not requests:
        print("  没有有效的请求，终止")
        return 1

    # ========== Phase 3: 上传 JSONL 并提交 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 3: 提交 Batch Job")
    print(f"{'─'*60}")

    print(f"  上传 JSONL...")
    jsonl_upload_start = time.time()
    try:
        uploaded_jsonl = client.files.upload(
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=f"audio-batch-{archive_batch}-{run_id}",
                mime_type="jsonl"
            )
        )
        jsonl_upload_time = time.time() - jsonl_upload_start
        print(f"  ok: {uploaded_jsonl.name} ({jsonl_upload_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    display_name = args.display_name or f"audio-{archive_batch}-{run_id}"
    print(f"  创建 Batch Job ({display_name})...")

    submit_start = time.time()
    try:
        batch_job = client.batches.create(
            model=model,
            src=uploaded_jsonl.name,
            config={"display_name": display_name},
        )
        submit_time = time.time() - submit_start
        print(f"  ok: {batch_job.name} ({submit_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    job_name = batch_job.name
    submitted_at = datetime.now()

    # ========== Phase 4: 等待完成 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 4: 等待完成")
    print(f"{'─'*60}")

    poll_start_time = time.time()
    poll_count = 0

    while True:
        batch_job = client.batches.get(name=job_name)
        state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
        elapsed = time.time() - poll_start_time
        poll_count += 1

        print(f"  [{elapsed:.0f}s] {state}")

        if state in COMPLETED_STATES:
            break

        if timeout and elapsed > timeout:
            print(f"\n  超时 ({timeout}s)")
            return 1

        time.sleep(poll_interval)

    api_processing_time = time.time() - poll_start_time
    completed_at = datetime.now()

    final_state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
    print(f"\n  Job 完成: {final_state} ({api_processing_time:.1f}s)")

    if final_state != "JOB_STATE_SUCCEEDED":
        print(f"  Job 未成功")
        return 1

    # ========== Phase 5: 下载并回填 ==========
    print(f"\n{'─'*60}")
    print(f"  Phase 5: 下载并回填")
    print(f"{'─'*60}")

    if not batch_job.dest or not batch_job.dest.file_name:
        print("  无结果文件")
        return 1

    result_file_name = batch_job.dest.file_name
    print(f"  下载: {result_file_name}")

    download_start = time.time()
    try:
        result_content = client.files.download(file=result_file_name)
        result_text = result_content.decode("utf-8")
        download_time = time.time() - download_start
        print(f"  ok ({download_time:.1f}s)")
    except Exception as e:
        print(f"  failed: {e}")
        return 1

    # 保存原始结果
    raw_result_path = run_dir / "batch_output.jsonl"
    with open(raw_result_path, "w", encoding="utf-8") as f:
        f.write(result_text)

    # 解析并回填
    results = []
    for line in result_text.strip().split("\n"):
        if line.strip():
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    success_count = 0
    fail_count = 0
    grade_distribution = {"A": 0, "B": 0, "C": 0}
    student_results = []
    total_tokens = {
        "prompt_tokens": 0,
        "thoughts_tokens": 0,
        "candidates_tokens": 0,
        "total_tokens": 0,
    }

    for result in results:
        key = result.get("key", "")
        parts = key.split(":")
        if len(parts) != 3:
            fail_count += 1
            continue

        archive_batch_key, student_name, run_id_key = parts

        # Token 统计
        usage = result.get("response", {}).get("usageMetadata", {})
        total_tokens["prompt_tokens"] += usage.get("promptTokenCount", 0)
        total_tokens["thoughts_tokens"] += usage.get("thoughtsTokenCount", 0)
        total_tokens["candidates_tokens"] += usage.get("candidatesTokenCount", 0)
        total_tokens["total_tokens"] += usage.get("totalTokenCount", 0)

        if "error" in result:
            print(f"   {student_name}: error - {result['error']}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_API})
            continue

        response = result.get("response", {})
        if not response:
            print(f"   ✗ {student_name}: 无响应")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_NO_RESPONSE})
            continue

        try:
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("无候选结果")
            content = candidates[0].get("content", {})
            parts_list = content.get("parts", [])
            if not parts_list:
                raise ValueError("无内容")
            raw_text = parts_list[0].get("text", "")
        except Exception as e:
            print(f"   ✗ {student_name}: 提取响应失败 - {e}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_EXTRACT_FAILED})
            continue

        parsed = parse_api_response(raw_text)
        if parsed.get("_parse_error"):
            print(f"   ✗ {student_name}: JSON 解析失败")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_JSON_PARSE_FAILED})
            continue

        annotations = parsed["annotations"]
        final_grade = parsed["final_grade_suggestion"]
        mistake_count = parsed["mistake_count"]

        is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
        if not is_valid:
            print(f"   ✗ {student_name}: 校验失败 ({len(invalid_items)} 无效项)")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_VALIDATION_FAILED})
            continue

        if final_grade not in ["A", "B", "C"]:
            print(f"   ✗ {student_name}: 无效评分 {final_grade}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_INVALID_GRADE})
            continue

        # 保存到 run 目录
        try:
            annotator_name = audio_annotator_name(model)  # 区分音频版
            stu_run_dir = ensure_run_dir(
                archive_batch=archive_batch_key,
                student_name=student_name,
                annotator_name=annotator_name,
                run_id=run_id,
            )

            annotation_result = {
                "student_name": student_name,
                "final_grade_suggestion": final_grade,
                "mistake_count": mistake_count,
                "annotations": annotations,
                "ink": "normal",  # Batch API 模式下默认为 normal（未运行 gatekeeper）
                "_metadata": {
                    "model": model,
                    "mode": "audio",
                    "batch_job": job_name,
                    "run_id": run_id,
                    "git_commit": get_git_commit(short=False),
                    "timestamp": datetime.now().isoformat(),
                    "source": "batch_api_audio",
                }
            }

            annotation_path = stu_run_dir / "4_llm_annotation.json"
            with open(annotation_path, "w", encoding="utf-8") as f:
                json.dump(annotation_result, f, ensure_ascii=False, indent=2)

            write_run_manifest(
                run_dir=stu_run_dir,
                annotator_name=annotator_name,
                run_id=run_id,
                archive_batch=archive_batch_key,
                student_name=student_name,
                prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / "user_with_audio.md",
                prompt_hash="batch_audio",
                model=model,
                extra={"mode": "audio"},
            )

            print(f"   {student_name}: {final_grade} ({mistake_count})")
            success_count += 1
            grade_distribution[final_grade] += 1
            student_results.append({
                "student": student_name,
                "status": "success",
                "grade": final_grade,
                "mistake_count": mistake_count,
            })

        except Exception as e:
            print(f"   ✗ {student_name}: 保存失败 - {e}")
            fail_count += 1
            student_results.append({"student": student_name, "status": "error", "error": ERROR_SAVE_FAILED})

    # 保存 manifest
    run_end_time = time.time()
    total_processing_time = run_end_time - run_start_time

    manifest = {
        "archive_batch": archive_batch,
        "run_id": run_id,
        "model": model,
        "mode": "audio",  # 标记为音频版
        "job_name": job_name,
        "display_name": display_name,
        "input_file": uploaded_jsonl.name,
        "result_file": result_file_name,
        "final_state": final_state,
        "timing": {
            "started_at": run_started_at.isoformat(),
            "submitted_at": submitted_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "fetched_at": datetime.now().isoformat(),
            "audio_upload_time_seconds": round(upload_time, 2),
            "jsonl_upload_time_seconds": round(jsonl_upload_time, 2),
            "submit_time_seconds": round(submit_time, 2),
            "api_processing_time_seconds": round(api_processing_time, 2),
            "download_time_seconds": round(download_time, 2),
            "total_processing_time_seconds": round(total_processing_time, 2),
            "poll_count": poll_count,
        },
        "statistics": {
            "students_count": len(students),
            "success_count": success_count,
            "fail_count": fail_count,
            "grade_distribution": grade_distribution,
        },
        "token_usage": total_tokens,
        "audio_files": audio_file_map,
        "requests": requests,
        "student_results": student_results,
    }

    manifest_path = run_dir / "batch_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 打印汇总
    print(f"\n{'='*60}")
    print(f"  完成!")
    print(f"{'='*60}")
    print(f"\n  统计:")
    print(f"   学生: {len(students)}")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")
    print(f"\n  成绩分布:")
    print(f"   A: {grade_distribution['A']}")
    print(f"   B: {grade_distribution['B']}")
    print(f"   C: {grade_distribution['C']}")
    print(f"\n  Token:")
    print(f"   prompt: {total_tokens['prompt_tokens']:,}")
    print(f"   thoughts: {total_tokens['thoughts_tokens']:,}")
    print(f"   total: {total_tokens['total_tokens']:,}")
    print(f"\n  耗时:")
    print(f"   音频上传: {upload_time:.1f}s")
    print(f"   API处理: {api_processing_time:.1f}s")
    print(f"   总计: {total_processing_time:.1f}s")
    print(f"\n  输出:")
    print(f"   {manifest_path}")

    # 生成详细报告
    _generate_batch_report(
        run_dir=run_dir,
        archive_batch=archive_batch,
        model=model,
        run_id=run_id,
        results=results,
        student_results=student_results,
        grade_distribution=grade_distribution,
        total_tokens=total_tokens,
        manifest=manifest,
    )

    return 0 if fail_count == 0 else 1


# ============================================================================
# 报告生成
# ============================================================================

def _generate_batch_report(
    run_dir: Path,
    archive_batch: str,
    model: str,
    run_id: str,
    results: List[Dict[str, Any]],
    student_results: List[Dict[str, Any]],
    grade_distribution: Dict[str, int],
    total_tokens: Dict[str, int],
    manifest: Dict[str, Any],
) -> None:
    """
    生成班级批处理报告 (音频版)

    输出:
    - batch_report.json: 干净的汇总报告
    - students/: 每个学生的完整报告（含 annotations）
    """
    from scripts.contracts.cards import parse_api_response

    # 构建每个学生的详细信息（从原始结果提取 token 和 annotations）
    student_details = []
    student_full_data = {}  # 保存完整数据用于生成学生报告

    for result in results:
        key = result.get("key", "")
        parts = key.split(":")
        if len(parts) != 3:
            continue

        _, student_name, _ = parts
        usage = result.get("response", {}).get("usageMetadata", {})

        # 找到对应的 student_result
        student_result = next(
            (s for s in student_results if s.get("student") == student_name),
            {}
        )

        # 提取 annotations
        annotations = []
        try:
            response = result.get("response", {})
            candidates = response.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts_list = content.get("parts", [])
                if parts_list:
                    raw_text = parts_list[0].get("text", "")
                    parsed = parse_api_response(raw_text)
                    if not parsed.get("_parse_error"):
                        annotations = parsed.get("annotations", [])
        except Exception:
            pass

        token_usage = {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "thoughts_tokens": usage.get("thoughtsTokenCount", 0),
            "candidates_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        }

        detail = {
            "student_name": student_name,
            "status": student_result.get("status", "unknown"),
            "grade": student_result.get("grade"),
            "mistake_count": student_result.get("mistake_count"),
            "token_usage": token_usage,
        }

        # 添加错误信息
        if student_result.get("status") == "error":
            detail["error"] = student_result.get("error")

        student_details.append(detail)

        # 保存完整数据
        student_full_data[student_name] = {
            "annotations": annotations,
            "token_usage": token_usage,
            "grade": student_result.get("grade"),
            "mistake_count": student_result.get("mistake_count"),
            "status": student_result.get("status", "unknown"),
            "error": student_result.get("error"),
        }

    # 生成汇总报告
    report = {
        "batch_id": archive_batch,
        "model": model,
        "mode": "audio",
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        # 时间信息
        "timing": manifest.get("timing", {}),
        # 统计
        "summary": {
            "total_students": len(student_details),
            "success": sum(1 for s in student_details if s["status"] == "success"),
            "failed": sum(1 for s in student_details if s["status"] != "success"),
            "grade_distribution": grade_distribution,
        },
        # Token 使用
        "token_usage": {
            "total": total_tokens,
            "average_per_student": {
                "prompt_tokens": total_tokens["prompt_tokens"] // max(len(student_details), 1),
                "thoughts_tokens": total_tokens["thoughts_tokens"] // max(len(student_details), 1),
                "candidates_tokens": total_tokens["candidates_tokens"] // max(len(student_details), 1),
                "total_tokens": total_tokens["total_tokens"] // max(len(student_details), 1),
            }
        },
        # 学生详情（含错误信息）
        "students": sorted(student_details, key=lambda x: x["student_name"]),
    }

    # 保存汇总报告
    report_path = run_dir / "batch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告: {report_path}")

    # 为每个学生生成完整报告（包含 annotations 和错误详情）
    students_dir = run_dir / "students"
    students_dir.mkdir(exist_ok=True)

    for detail in student_details:
        student_name = detail["student_name"]
        full_data = student_full_data.get(student_name, {})

        student_report = {
            "student_name": student_name,
            "status": detail["status"],
            "final_grade_suggestion": detail.get("grade"),
            "mistake_count": detail.get("mistake_count"),
            "annotations": full_data.get("annotations", []),
            "_metadata": {
                "batch_id": archive_batch,
                "model": model,
                "mode": "audio",
                "run_id": run_id,
                "token_usage": detail["token_usage"],
                "generated_at": datetime.now().isoformat(),
                "source": "batch_api_audio",
            }
        }

        # 如果有错误，添加错误信息
        if detail["status"] == "error":
            student_report["error"] = detail.get("error")

        # 安全的文件名
        safe_name = student_name.replace(" ", "_").replace("/", "_")
        student_path = students_dir / f"{safe_name}.json"
        with open(student_path, "w", encoding="utf-8") as f:
            json.dump(student_report, f, ensure_ascii=False, indent=2)

    print(f"  学生报告: {students_dir}/ ({len(student_details)} 个)")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gemini Batch API 音频版 - 直接使用音频进行评分",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="一键运行")
    run_parser.add_argument("--archive-batch", required=True, help="Batch 名称")
    run_parser.add_argument("--students", help="学生列表（逗号分隔）")
    run_parser.add_argument("--model", default=DEFAULT_MODEL)
    run_parser.add_argument("--display-name", help="Job 显示名称")
    run_parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL)
    run_parser.add_argument("--timeout", type=int, help="最大等待秒数")
    run_parser.add_argument("--proxy", help="代理地址")

    submit_parser = subparsers.add_parser("submit", help="仅提交")
    submit_parser.add_argument("--archive-batch", required=True, help="Batch 名称")
    submit_parser.add_argument("--students", help="学生列表（逗号分隔）")
    submit_parser.add_argument("--model", default=DEFAULT_MODEL)
    submit_parser.add_argument("--display-name", help="Job 显示名称")
    submit_parser.add_argument("--proxy", help="代理地址")

    fetch_parser = subparsers.add_parser("fetch", help="获取结果并回填")
    fetch_parser.add_argument("--manifest", help="Manifest 路径")
    fetch_parser.add_argument("--job", help="Batch Job 名称")
    fetch_parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL)
    fetch_parser.add_argument("--timeout", type=int, help="最大等待秒数")
    fetch_parser.add_argument("--proxy", help="代理地址")

    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args)
    if args.command == "submit":
        return cmd_submit(args)
    if args.command == "fetch":
        return cmd_fetch(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
