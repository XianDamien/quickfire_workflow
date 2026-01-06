# -*- coding: utf-8 -*-
"""
scripts/gemini_batch.py - Gemini Batch API 批量处理脚本

使用官方 SDK 直接调用 Gemini Batch API（绕过中转站），支持代理配置。

用法:
    # 推荐: 一键运行（提交 + 监听 + 回填）
    python3 scripts/gemini_batch.py run --archive-batch <name> [--students s1,s2,...]

    # 带超时的一键运行（超时后可用 fetch 恢复）
    python3 scripts/gemini_batch.py run --archive-batch <name> --timeout 600

    # 仅提交（不等待）
    python3 scripts/gemini_batch.py submit --archive-batch <name>

    # 获取结果并回填（用于恢复超时的 job）
    python3 scripts/gemini_batch.py fetch --manifest <path>

    # 查看 job 状态
    python3 scripts/gemini_batch.py status --job batches/xxx

    # 列出所有 jobs
    python3 scripts/gemini_batch.py list

输出:
    archive/{batch}/_batch_runs/{run_id}/
    ├── batch_input.jsonl      # 输入文件
    ├── batch_output.jsonl     # 原始输出
    └── batch_manifest.json    # 元信息（含处理时间等）

    archive/{batch}/{student}/runs/{model}/{run_id}/
    ├── prompt_log.txt         # 完整提示词日志（生成时保存）
    ├── 4_llm_annotation.json  # 回填的评分结果
    └── run_manifest.json      # 运行元数据
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
DEFAULT_POLL_INTERVAL = 30  # 秒
DEFAULT_TIMEOUT = 300000  # 毫秒 (5分钟)
COMPLETED_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


# ============================================================================
# SDK 客户端初始化（支持代理）
# ============================================================================

def create_client(
    proxy: Optional[str] = None,
    timeout_ms: int = DEFAULT_TIMEOUT,
) -> genai.Client:
    """
    创建带代理的 Gemini SDK 客户端

    Args:
        proxy: 代理地址，如 "socks5://127.0.0.1:7890"。
               如果为 None，从环境变量 HTTPS_PROXY/ALL_PROXY 读取
        timeout_ms: 超时时间（毫秒）

    Returns:
        genai.Client 实例
    """
    api_key = require_env("GEMINI_API_KEY")

    # 确定代理地址
    if proxy is None:
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("ALL_PROXY")

    http_options_kwargs: Dict[str, Any] = {
        "timeout": timeout_ms,
    }

    # 配置代理
    if proxy:
        print(f"🌐 使用代理: {proxy}")
        transport = httpx.HTTPTransport(proxy=proxy, retries=3)
        custom_client = httpx.Client(
            transport=transport,
            timeout=timeout_ms / 1000,  # httpx 使用秒
            follow_redirects=True,  # 重要：下载文件时需要跟随重定向
        )
        http_options_kwargs["httpx_client"] = custom_client
    else:
        print("⚠️  未配置代理，直连官方 API")

    http_options = types.HttpOptions(**http_options_kwargs)

    client = genai.Client(
        api_key=api_key,
        http_options=http_options
    )

    print(f"🔑 使用官方 SDK (Batch API)")
    return client


# ============================================================================
# JSONL 生成
# ============================================================================

def build_batch_request(
    archive_batch: str,
    student_name: str,
    run_id: str,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    为单个学生构建 batch request

    Args:
        archive_batch: batch 名称
        student_name: 学生名称
        run_id: 运行 ID
        model: 模型名称

    Returns:
        JSONL 行的字典格式
    """
    from scripts.common.archive import (
        student_dir,
        resolve_question_bank,
        load_metadata,
        load_file_content,
    )
    from scripts.common.hash import text_hash
    from scripts.contracts.asr_timestamp import extract_sentences_json

    # 加载 prompt loader
    prompt_dir = _PROJECT_ROOT / "prompts" / "annotation"
    sys.path.insert(0, str(_PROJECT_ROOT / "prompts"))
    from prompt_loader import PromptLoader, PromptContextBuilder

    prompt_loader = PromptLoader(str(prompt_dir))

    # 加载学生数据
    stu_dir = student_dir(archive_batch, student_name)
    qwen_asr_path = stu_dir / "2_qwen_asr.json"
    timestamp_path = stu_dir / "3_asr_timestamp.json"

    # 检查文件
    if not qwen_asr_path.exists():
        raise FileNotFoundError(f"未找到 ASR 文件: {qwen_asr_path}")
    if not timestamp_path.exists():
        raise FileNotFoundError(f"未找到时间戳文件: {timestamp_path}")

    # 加载 metadata 和题库
    try:
        metadata = load_metadata(archive_batch)
    except FileNotFoundError:
        metadata = {}

    question_bank_path = resolve_question_bank(archive_batch, metadata)
    if not question_bank_path:
        raise FileNotFoundError("未找到题库文件")

    # 加载内容
    question_bank_content = load_file_content(question_bank_path)
    asr_with_timestamp = extract_sentences_json(timestamp_path)

    # 提取纯文本 ASR
    with open(qwen_asr_path, "r", encoding="utf-8") as f:
        asr_data = json.load(f)
    asr_text = (
        asr_data.get("output", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", [{}])[0]
        .get("text", "")
    )

    # 构建 prompt 上下文
    prompt_context = PromptContextBuilder.build(
        question_bank_json=question_bank_content,
        student_asr_text=asr_text,
        dataset_name=archive_batch,
        student_name=student_name,
        student_asr_with_timestamp=asr_with_timestamp,
        metadata=prompt_loader.metadata
    )

    # 获取提示词
    system_instruction = prompt_loader.system_instruction
    full_prompt = prompt_loader.render_user_prompt(prompt_context)

    # 构建 key
    key = f"{archive_batch}:{student_name}:{run_id}"

    # 构建 request
    # 注意：Batch API 需要完整的 GenerateContentRequest 结构
    request = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": full_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
        }
    }

    # 添加 system instruction
    if system_instruction:
        request["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    return {
        "key": key,
        "request": request,
        # 额外信息用于保存 prompt_log
        "_prompt_info": {
            "full_prompt": full_prompt,
            "system_instruction": system_instruction,
            "prompt_version": prompt_loader.metadata.get("prompt_version", "unknown"),
            "question_bank_path": str(question_bank_path),
        }
    }


def generate_jsonl(
    archive_batch: str,
    students: List[str],
    run_id: str,
    output_path: Path,
    model: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:
    """
    生成 JSONL 输入文件，同时为每个学生保存 prompt_log.txt

    Args:
        archive_batch: batch 名称
        students: 学生列表
        run_id: 运行 ID
        output_path: 输出文件路径
        model: 模型名称

    Returns:
        生成的请求列表（用于 manifest）
    """
    from scripts.common.runs import ensure_run_dir, get_git_commit

    requests = []
    errors = []

    print(f"\n📝 生成 JSONL 文件: {output_path}")
    print(f"   学生数量: {len(students)}")

    git_commit = get_git_commit(short=False)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, student in enumerate(students, 1):
            try:
                print(f"   [{i}/{len(students)}] {student}...", end=" ")
                req = build_batch_request(archive_batch, student, run_id, model)

                # 写入 JSONL（不包含 _prompt_info）
                jsonl_entry = {"key": req["key"], "request": req["request"]}
                f.write(json.dumps(jsonl_entry, ensure_ascii=False) + "\n")

                # 保存 prompt_log.txt 到学生的 run 目录
                prompt_info = req.get("_prompt_info", {})
                if prompt_info:
                    stu_run_dir = ensure_run_dir(
                        archive_batch=archive_batch,
                        student_name=student,
                        annotator_name=model,
                        run_id=run_id,
                    )
                    prompt_log_path = stu_run_dir / "prompt_log.txt"
                    with open(prompt_log_path, "w", encoding="utf-8") as pf:
                        pf.write("=== Batch API 完整提示词日志 ===\n\n")
                        pf.write(f"生成时间: {datetime.now().isoformat()}\n")
                        pf.write(f"Run ID: {run_id}\n")
                        pf.write(f"Model: {model}\n")
                        pf.write(f"Git Commit: {git_commit}\n")
                        pf.write(f"Student: {student}\n")
                        pf.write(f"Archive Batch: {archive_batch}\n")
                        pf.write(f"Prompt Version: {prompt_info.get('prompt_version', 'unknown')}\n")
                        pf.write(f"Question Bank: {prompt_info.get('question_bank_path', 'unknown')}\n")
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
                })
                print("✓")
            except Exception as e:
                print(f"✗ {e}")
                errors.append({"student": student, "error": str(e)})

    if errors:
        print(f"\n⚠️  {len(errors)} 个学生生成失败:")
        for err in errors[:5]:
            print(f"   - {err['student']}: {err['error']}")

    print(f"\n✅ 成功生成 {len(requests)} 条请求")
    return requests


# ============================================================================
# Submit 命令
# ============================================================================

def cmd_submit(args: argparse.Namespace) -> int:
    """
    提交 batch job

    流程:
    1. 扫描学生目录
    2. 生成 JSONL 文件
    3. 上传到 File API
    4. 创建 batch job
    5. 保存 manifest
    """
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
        print(f"❌ 未找到学生: {archive_batch}")
        return 1

    print(f"📦 Batch: {archive_batch}")
    print(f"🤖 Model: {model}")
    print(f"👥 学生: {len(students)} 人")

    # 生成 run_id
    run_id = new_run_id()
    print(f"🆔 Run ID: {run_id}")

    # 准备输出目录
    batch_path = archive_batch_dir(archive_batch)
    batch_runs_dir = batch_path / "_batch_runs"
    batch_runs_dir.mkdir(parents=True, exist_ok=True)

    run_dir = batch_runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 生成 JSONL
    jsonl_path = run_dir / "batch_input.jsonl"
    requests = generate_jsonl(
        archive_batch=archive_batch,
        students=students,
        run_id=run_id,
        output_path=jsonl_path,
        model=model,
    )

    if not requests:
        print("❌ 没有有效的请求，终止")
        return 1

    # 创建客户端
    client = create_client(proxy=args.proxy)

    # 上传文件
    print(f"\n📤 上传 JSONL 文件...")
    try:
        uploaded_file = client.files.upload(
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=f"batch-{archive_batch}-{run_id}",
                mime_type="jsonl"
            )
        )
        print(f"   ✓ 上传成功: {uploaded_file.name}")
    except Exception as e:
        print(f"   ✗ 上传失败: {e}")
        return 1

    # 创建 batch job
    display_name = args.display_name or f"{archive_batch}-{run_id}"
    print(f"\n🚀 创建 Batch Job...")
    print(f"   display_name: {display_name}")

    try:
        batch_job = client.batches.create(
            model=model,
            src=uploaded_file.name,
            config={"display_name": display_name},
        )
        print(f"   ✓ Job 创建成功: {batch_job.name}")
    except Exception as e:
        print(f"   ✗ Job 创建失败: {e}")
        return 1

    # 保存 manifest
    manifest = {
        "archive_batch": archive_batch,
        "run_id": run_id,
        "model": model,
        "job_name": batch_job.name,
        "display_name": display_name,
        "input_file": uploaded_file.name,
        "submitted_at": datetime.now().isoformat(),
        "state": batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state),
        "requests": requests,
        "students_count": len(requests),
    }

    manifest_path = run_dir / "batch_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n📋 Manifest 已保存: {manifest_path}")
    print(f"\n✅ Batch Job 已提交!")
    print(f"   Job Name: {batch_job.name}")
    print(f"   Manifest: {manifest_path}")
    print(f"\n💡 使用以下命令获取结果:")
    print(f"   python3 scripts/gemini_batch.py fetch --manifest {manifest_path}")

    return 0


# ============================================================================
# Fetch 命令
# ============================================================================

def cmd_fetch(args: argparse.Namespace) -> int:
    """
    获取 batch job 结果并回填

    流程:
    1. 加载 manifest 或直接使用 job name
    2. 轮询 job 状态
    3. 下载结果文件
    4. 解析并回填到各学生目录
    """
    from scripts.common.archive import student_dir
    from scripts.common.runs import ensure_run_dir, write_run_manifest, get_git_commit
    from scripts.contracts.cards import validate_cards, parse_api_response

    # 确定 job name 和 manifest
    manifest = None
    job_name = None

    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"❌ Manifest 文件不存在: {manifest_path}")
            return 1
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        job_name = manifest["job_name"]
        print(f"📋 从 Manifest 加载: {manifest_path}")
    elif args.job:
        job_name = args.job
        print(f"🔗 使用 Job Name: {job_name}")
    else:
        print("❌ 必须指定 --manifest 或 --job")
        return 1

    # 创建客户端
    client = create_client(proxy=args.proxy)

    # 轮询状态
    poll_interval = args.poll_interval or DEFAULT_POLL_INTERVAL
    timeout = args.timeout

    print(f"\n⏳ 等待 Job 完成...")
    print(f"   Job: {job_name}")
    print(f"   轮询间隔: {poll_interval}s")

    start_time = time.time()
    batch_job = client.batches.get(name=job_name)

    while True:
        state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
        elapsed = time.time() - start_time

        print(f"   [{elapsed:.0f}s] 状态: {state}")

        if state in COMPLETED_STATES:
            break

        if timeout and elapsed > timeout:
            print(f"\n⚠️  超时 ({timeout}s)，停止等待")
            print(f"   当前状态: {state}")
            print(f"   稍后可重新运行 fetch 命令继续等待")
            return 1

        time.sleep(poll_interval)
        batch_job = client.batches.get(name=job_name)

    # 检查最终状态
    final_state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
    print(f"\n🏁 Job 完成: {final_state}")

    if final_state != "JOB_STATE_SUCCEEDED":
        print(f"❌ Job 未成功完成")
        if hasattr(batch_job, "error") and batch_job.error:
            print(f"   错误: {batch_job.error}")
        return 1

    # 下载结果
    if not batch_job.dest or not batch_job.dest.file_name:
        print("❌ 未找到结果文件")
        return 1

    result_file_name = batch_job.dest.file_name
    print(f"\n📥 下载结果文件: {result_file_name}")

    try:
        result_content = client.files.download(file=result_file_name)
        result_text = result_content.decode("utf-8")
    except Exception as e:
        print(f"   ✗ 下载失败: {e}")
        return 1

    # 解析结果
    print(f"\n📊 解析结果...")

    results = []
    errors = []

    for line_num, line in enumerate(result_text.strip().split("\n"), 1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            results.append(parsed)
        except json.JSONDecodeError as e:
            errors.append({"line": line_num, "error": str(e)})

    print(f"   总行数: {len(results)}")
    if errors:
        print(f"   解析错误: {len(errors)} 行")

    # 回填结果
    print(f"\n📝 回填结果到学生目录...")

    # 构建 key -> request 映射
    key_to_info = {}
    if manifest:
        for req in manifest.get("requests", []):
            key_to_info[req["key"]] = req

    success_count = 0
    fail_count = 0

    for result in results:
        key = result.get("key", "")

        # 解析 key: {archive_batch}:{student_name}:{run_id}
        parts = key.split(":")
        if len(parts) != 3:
            print(f"   ⚠️  无效 key: {key}")
            fail_count += 1
            continue

        archive_batch, student_name, run_id = parts

        # 检查响应
        if "error" in result:
            print(f"   ✗ {student_name}: {result['error']}")
            fail_count += 1
            continue

        response = result.get("response", {})
        if not response:
            print(f"   ✗ {student_name}: 无响应")
            fail_count += 1
            continue

        # 提取文本
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
            continue

        # 解析 JSON 响应
        parsed = parse_api_response(raw_text)
        if parsed.get("_parse_error"):
            print(f"   ✗ {student_name}: JSON 解析失败")
            fail_count += 1
            continue

        annotations = parsed["annotations"]
        final_grade = parsed["final_grade_suggestion"]
        mistake_count = parsed["mistake_count"]

        # 校验
        is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
        if not is_valid:
            print(f"   ✗ {student_name}: 校验失败 ({len(invalid_items)} 无效项)")
            fail_count += 1
            continue

        if final_grade not in ["A", "B", "C"]:
            print(f"   ✗ {student_name}: 无效评分 {final_grade}")
            fail_count += 1
            continue

        # 保存到 run 目录
        try:
            # 使用 manifest 中的 model，否则使用默认值
            model = manifest.get("model", DEFAULT_MODEL) if manifest else DEFAULT_MODEL

            run_dir = ensure_run_dir(
                archive_batch=archive_batch,
                student_name=student_name,
                annotator_name=model,
                run_id=run_id,
            )

            # 保存 4_llm_annotation.json
            annotation_result = {
                "student_name": student_name,
                "final_grade_suggestion": final_grade,
                "mistake_count": mistake_count,
                "annotations": annotations,
                "_metadata": {
                    "model": model,
                    "batch_job": job_name,
                    "run_id": run_id,
                    "git_commit": get_git_commit(short=False),
                    "timestamp": datetime.now().isoformat(),
                    "source": "batch_api",
                }
            }

            annotation_path = run_dir / "4_llm_annotation.json"
            with open(annotation_path, "w", encoding="utf-8") as f:
                json.dump(annotation_result, f, ensure_ascii=False, indent=2)

            # 写入 run_manifest
            write_run_manifest(
                run_dir=run_dir,
                annotator_name=model,
                run_id=run_id,
                archive_batch=archive_batch,
                student_name=student_name,
                prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / "user.md",
                prompt_hash="batch",
                model=model,
            )

            print(f"   ✓ {student_name}: {final_grade} → runs/{model}/{run_id}/")
            success_count += 1

        except Exception as e:
            print(f"   ✗ {student_name}: 保存失败 - {e}")
            fail_count += 1

    # 更新 manifest
    if manifest and args.manifest:
        manifest["fetched_at"] = datetime.now().isoformat()
        manifest["result_file"] = result_file_name
        manifest["final_state"] = final_state
        manifest["success_count"] = success_count
        manifest["fail_count"] = fail_count

        with open(args.manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 汇总
    print(f"\n✅ 回填完成!")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")

    return 0 if fail_count == 0 else 1


# ============================================================================
# Run 命令 (submit + watch + fetch 一体化)
# ============================================================================

def cmd_run(args: argparse.Namespace) -> int:
    """
    一键运行：提交 batch job，自动监听，完成后回填结果

    流程:
    1. 扫描学生目录
    2. 生成 JSONL 文件
    3. 上传到 File API
    4. 创建 batch job
    5. 轮询等待完成
    6. 下载并回填结果
    7. 保存完整的 manifest（含处理时间元信息）
    """
    from scripts.common.archive import archive_batch_dir, list_students, student_dir
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
        print(f"❌ 未找到学生: {archive_batch}")
        return 1

    print(f"\n{'='*60}")
    print(f"🚀 Gemini Batch API - 一键运行模式")
    print(f"{'='*60}")
    print(f"📦 Batch: {archive_batch}")
    print(f"🤖 Model: {model}")
    print(f"👥 学生: {len(students)} 人")
    print(f"⏱️  轮询间隔: {poll_interval}s")
    if timeout:
        print(f"⏰ 超时: {timeout}s")

    # 记录开始时间
    run_start_time = time.time()
    run_started_at = datetime.now()

    # 生成 run_id
    run_id = new_run_id()
    print(f"🆔 Run ID: {run_id}")

    # 准备输出目录
    batch_path = archive_batch_dir(archive_batch)
    batch_runs_dir = batch_path / "_batch_runs"
    batch_runs_dir.mkdir(parents=True, exist_ok=True)

    run_dir = batch_runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ========== Phase 1: 生成 JSONL ==========
    print(f"\n{'─'*60}")
    print(f"📝 Phase 1: 生成 JSONL 文件")
    print(f"{'─'*60}")

    jsonl_path = run_dir / "batch_input.jsonl"
    requests = generate_jsonl(
        archive_batch=archive_batch,
        students=students,
        run_id=run_id,
        output_path=jsonl_path,
        model=model,
    )

    if not requests:
        print("❌ 没有有效的请求，终止")
        return 1

    # ========== Phase 2: 上传并提交 ==========
    print(f"\n{'─'*60}")
    print(f"📤 Phase 2: 上传并提交 Batch Job")
    print(f"{'─'*60}")

    # 创建客户端
    client = create_client(proxy=args.proxy)

    # 上传文件
    print(f"   上传 JSONL 文件...")
    upload_start = time.time()
    try:
        uploaded_file = client.files.upload(
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=f"batch-{archive_batch}-{run_id}",
                mime_type="jsonl"
            )
        )
        upload_time = time.time() - upload_start
        print(f"   ✓ 上传成功: {uploaded_file.name} ({upload_time:.1f}s)")
    except Exception as e:
        print(f"   ✗ 上传失败: {e}")
        return 1

    # 创建 batch job
    display_name = args.display_name or f"{archive_batch}-{run_id}"
    print(f"   创建 Batch Job (display_name: {display_name})...")

    submit_start = time.time()
    try:
        batch_job = client.batches.create(
            model=model,
            src=uploaded_file.name,
            config={"display_name": display_name},
        )
        submit_time = time.time() - submit_start
        print(f"   ✓ Job 创建成功: {batch_job.name} ({submit_time:.1f}s)")
    except Exception as e:
        print(f"   ✗ Job 创建失败: {e}")
        return 1

    job_name = batch_job.name
    submitted_at = datetime.now()

    # ========== Phase 3: 轮询等待 ==========
    print(f"\n{'─'*60}")
    print(f"⏳ Phase 3: 等待 Batch Job 完成")
    print(f"{'─'*60}")
    print(f"   Job: {job_name}")

    poll_start_time = time.time()
    poll_count = 0

    while True:
        batch_job = client.batches.get(name=job_name)
        state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
        elapsed = time.time() - poll_start_time
        poll_count += 1

        # 显示进度
        progress_info = f"[{elapsed:.0f}s | 第{poll_count}次轮询]"
        print(f"   {progress_info} 状态: {state}")

        if state in COMPLETED_STATES:
            break

        if timeout and elapsed > timeout:
            print(f"\n⚠️  超时 ({timeout}s)，停止等待")
            # 保存部分 manifest 供后续恢复
            _save_partial_manifest(
                run_dir=run_dir,
                archive_batch=archive_batch,
                run_id=run_id,
                model=model,
                job_name=job_name,
                display_name=display_name,
                input_file=uploaded_file.name,
                submitted_at=submitted_at,
                requests=requests,
                state=state,
            )
            print(f"   已保存部分 manifest，可使用 fetch 命令继续")
            return 1

        time.sleep(poll_interval)

    api_processing_time = time.time() - poll_start_time
    completed_at = datetime.now()

    # 检查最终状态
    final_state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
    print(f"\n🏁 Job 完成: {final_state} (API处理时间: {api_processing_time:.1f}s)")

    if final_state != "JOB_STATE_SUCCEEDED":
        print(f"❌ Job 未成功完成")
        if hasattr(batch_job, "error") and batch_job.error:
            print(f"   错误: {batch_job.error}")
        return 1

    # ========== Phase 4: 下载并回填 ==========
    print(f"\n{'─'*60}")
    print(f"📥 Phase 4: 下载并回填结果")
    print(f"{'─'*60}")

    if not batch_job.dest or not batch_job.dest.file_name:
        print("❌ 未找到结果文件")
        return 1

    result_file_name = batch_job.dest.file_name
    print(f"   下载结果文件: {result_file_name}")

    download_start = time.time()
    try:
        result_content = client.files.download(file=result_file_name)
        result_text = result_content.decode("utf-8")
        download_time = time.time() - download_start
        print(f"   ✓ 下载成功 ({download_time:.1f}s)")
    except Exception as e:
        print(f"   ✗ 下载失败: {e}")
        return 1

    # 保存原始结果
    raw_result_path = run_dir / "batch_output.jsonl"
    with open(raw_result_path, "w", encoding="utf-8") as f:
        f.write(result_text)
    print(f"   ✓ 原始结果已保存: {raw_result_path.name}")

    # 解析结果
    print(f"\n   📊 解析结果...")
    results = []
    parse_errors = []

    for line_num, line in enumerate(result_text.strip().split("\n"), 1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            results.append(parsed)
        except json.JSONDecodeError as e:
            parse_errors.append({"line": line_num, "error": str(e)})

    print(f"   总行数: {len(results)}")
    if parse_errors:
        print(f"   解析错误: {len(parse_errors)} 行")

    # 回填结果
    print(f"\n   📝 回填结果到学生目录...")

    key_to_info = {req["key"]: req for req in requests}
    success_count = 0
    fail_count = 0
    grade_distribution = {"A": 0, "B": 0, "C": 0}
    student_results = []

    for result in results:
        key = result.get("key", "")
        parts = key.split(":")
        if len(parts) != 3:
            print(f"      ⚠️  无效 key: {key}")
            fail_count += 1
            continue

        archive_batch_key, student_name, run_id_key = parts

        # 检查响应
        if "error" in result:
            print(f"      ✗ {student_name}: {result['error']}")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": result["error"],
            })
            continue

        response = result.get("response", {})
        if not response:
            print(f"      ✗ {student_name}: 无响应")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": "no_response",
            })
            continue

        # 提取文本
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
            print(f"      ✗ {student_name}: 提取响应失败 - {e}")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": f"extract_failed: {e}",
            })
            continue

        # 解析 JSON 响应
        parsed = parse_api_response(raw_text)
        if parsed.get("_parse_error"):
            print(f"      ✗ {student_name}: JSON 解析失败")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": "json_parse_failed",
            })
            continue

        annotations = parsed["annotations"]
        final_grade = parsed["final_grade_suggestion"]
        mistake_count = parsed["mistake_count"]

        # 校验
        is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
        if not is_valid:
            print(f"      ✗ {student_name}: 校验失败 ({len(invalid_items)} 无效项)")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": f"validation_failed: {len(invalid_items)} invalid items",
            })
            continue

        if final_grade not in ["A", "B", "C"]:
            print(f"      ✗ {student_name}: 无效评分 {final_grade}")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": f"invalid_grade: {final_grade}",
            })
            continue

        # 保存到 run 目录
        try:
            stu_run_dir = ensure_run_dir(
                archive_batch=archive_batch_key,
                student_name=student_name,
                annotator_name=model,
                run_id=run_id,
            )

            annotation_result = {
                "student_name": student_name,
                "final_grade_suggestion": final_grade,
                "mistake_count": mistake_count,
                "annotations": annotations,
                "_metadata": {
                    "model": model,
                    "batch_job": job_name,
                    "run_id": run_id,
                    "git_commit": get_git_commit(short=False),
                    "timestamp": datetime.now().isoformat(),
                    "source": "batch_api",
                }
            }

            annotation_path = stu_run_dir / "4_llm_annotation.json"
            with open(annotation_path, "w", encoding="utf-8") as f:
                json.dump(annotation_result, f, ensure_ascii=False, indent=2)

            write_run_manifest(
                run_dir=stu_run_dir,
                annotator_name=model,
                run_id=run_id,
                archive_batch=archive_batch_key,
                student_name=student_name,
                prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / "user.md",
                prompt_hash="batch",
                model=model,
            )

            # prompt_log.txt 已在 generate_jsonl 时保存

            print(f"      ✓ {student_name}: {final_grade} ({mistake_count} mistakes)")
            success_count += 1
            grade_distribution[final_grade] += 1
            student_results.append({
                "student": student_name,
                "status": "success",
                "grade": final_grade,
                "mistake_count": mistake_count,
            })

        except Exception as e:
            print(f"      ✗ {student_name}: 保存失败 - {e}")
            fail_count += 1
            student_results.append({
                "student": student_name,
                "status": "error",
                "error": f"save_failed: {e}",
            })

    # ========== Phase 5: 保存完整 Manifest ==========
    run_end_time = time.time()
    total_processing_time = run_end_time - run_start_time

    manifest = {
        "archive_batch": archive_batch,
        "run_id": run_id,
        "model": model,
        "job_name": job_name,
        "display_name": display_name,
        "input_file": uploaded_file.name,
        "result_file": result_file_name,
        "final_state": final_state,
        # 时间信息
        "timing": {
            "started_at": run_started_at.isoformat(),
            "submitted_at": submitted_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "fetched_at": datetime.now().isoformat(),
            "upload_time_seconds": round(upload_time, 2),
            "submit_time_seconds": round(submit_time, 2),
            "api_processing_time_seconds": round(api_processing_time, 2),
            "download_time_seconds": round(download_time, 2),
            "total_processing_time_seconds": round(total_processing_time, 2),
            "poll_count": poll_count,
        },
        # 统计信息
        "statistics": {
            "students_count": len(students),
            "success_count": success_count,
            "fail_count": fail_count,
            "grade_distribution": grade_distribution,
        },
        # 详细结果
        "requests": requests,
        "student_results": student_results,
    }

    manifest_path = run_dir / "batch_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ========== 打印汇总 ==========
    print(f"\n{'='*60}")
    print(f"✅ Batch 处理完成!")
    print(f"{'='*60}")
    print(f"\n📊 统计信息:")
    print(f"   学生总数: {len(students)}")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")
    print(f"\n📈 成绩分布:")
    print(f"   A: {grade_distribution['A']} 人")
    print(f"   B: {grade_distribution['B']} 人")
    print(f"   C: {grade_distribution['C']} 人")
    print(f"\n⏱️  时间信息:")
    print(f"   总耗时: {total_processing_time:.1f}s ({total_processing_time/60:.1f}min)")
    print(f"   API处理时间: {api_processing_time:.1f}s")
    print(f"   上传时间: {upload_time:.1f}s")
    print(f"   下载时间: {download_time:.1f}s")
    print(f"\n📁 输出文件:")
    print(f"   Manifest: {manifest_path}")
    print(f"   原始结果: {raw_result_path}")

    return 0 if fail_count == 0 else 1


def _save_partial_manifest(
    run_dir: Path,
    archive_batch: str,
    run_id: str,
    model: str,
    job_name: str,
    display_name: str,
    input_file: str,
    submitted_at: datetime,
    requests: List[Dict[str, Any]],
    state: str,
) -> None:
    """保存部分 manifest（用于超时时恢复）"""
    manifest = {
        "archive_batch": archive_batch,
        "run_id": run_id,
        "model": model,
        "job_name": job_name,
        "display_name": display_name,
        "input_file": input_file,
        "submitted_at": submitted_at.isoformat(),
        "state": state,
        "requests": requests,
        "students_count": len(requests),
        "_status": "partial",
        "_note": "Job 未完成，可使用 fetch --manifest 继续",
    }
    manifest_path = run_dir / "batch_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"   Manifest: {manifest_path}")


# ============================================================================
# Status 命令
# ============================================================================

def cmd_status(args: argparse.Namespace) -> int:
    """查询 batch job 状态"""
    client = create_client(proxy=args.proxy)

    job_name = args.job
    print(f"\n📊 查询 Job 状态: {job_name}")

    try:
        batch_job = client.batches.get(name=job_name)
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return 1

    state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)

    print(f"\n状态信息:")
    print(f"  Name: {batch_job.name}")
    print(f"  State: {state}")

    if hasattr(batch_job, "display_name") and batch_job.display_name:
        print(f"  Display Name: {batch_job.display_name}")

    if hasattr(batch_job, "create_time") and batch_job.create_time:
        print(f"  Created: {batch_job.create_time}")

    if state == "JOB_STATE_SUCCEEDED" and batch_job.dest:
        print(f"  Result File: {batch_job.dest.file_name}")

    if hasattr(batch_job, "error") and batch_job.error:
        print(f"  Error: {batch_job.error}")

    return 0


# ============================================================================
# Cancel 命令
# ============================================================================

def cmd_cancel(args: argparse.Namespace) -> int:
    """取消 batch job"""
    client = create_client(proxy=args.proxy)

    job_name = args.job
    print(f"\n🛑 取消 Job: {job_name}")

    try:
        client.batches.cancel(name=job_name)
        print("✅ 已发送取消请求")
    except Exception as e:
        print(f"❌ 取消失败: {e}")
        return 1

    return 0


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
    生成班级批处理报告

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

        student_details.append({
            "student_name": student_name,
            "status": student_result.get("status", "unknown"),
            "grade": student_result.get("grade"),
            "mistake_count": student_result.get("mistake_count"),
            "token_usage": token_usage,
        })

        # 保存完整数据
        student_full_data[student_name] = {
            "annotations": annotations,
            "token_usage": token_usage,
            "grade": student_result.get("grade"),
            "mistake_count": student_result.get("mistake_count"),
            "status": student_result.get("status", "unknown"),
        }

    # 生成汇总报告
    report = {
        "batch_id": archive_batch,
        "model": model,
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        # 时间信息
        "timing": {
            "submitted_at": manifest.get("submitted_at"),
            "fetched_at": manifest.get("fetched_at"),
        },
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
        # 学生详情
        "students": sorted(student_details, key=lambda x: x["student_name"]),
    }

    # 保存汇总报告
    report_path = run_dir / "batch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 为每个学生生成完整报告（包含 annotations）
    students_dir = run_dir / "students"
    students_dir.mkdir(exist_ok=True)

    for detail in student_details:
        student_name = detail["student_name"]
        full_data = student_full_data.get(student_name, {})

        student_report = {
            "student_name": student_name,
            "final_grade_suggestion": detail.get("grade"),
            "mistake_count": detail.get("mistake_count"),
            "annotations": full_data.get("annotations", []),
            "_metadata": {
                "batch_id": archive_batch,
                "model": model,
                "run_id": run_id,
                "status": detail["status"],
                "token_usage": detail["token_usage"],
                "generated_at": datetime.now().isoformat(),
                "source": "batch_api",
            }
        }

        # 安全的文件名
        safe_name = student_name.replace(" ", "_").replace("/", "_")
        student_path = students_dir / f"{safe_name}.json"
        with open(student_path, "w", encoding="utf-8") as f:
            json.dump(student_report, f, ensure_ascii=False, indent=2)


# ============================================================================
# Fetch-All 命令
# ============================================================================

def cmd_fetch_all(args: argparse.Namespace) -> int:
    """
    批量获取所有 pending 的 batch job 结果

    扫描所有 _batch_runs 目录，找到状态为 pending 的 manifest，
    检查实际状态并回填完成的结果。
    """
    from scripts.common.archive import student_dir
    from scripts.common.runs import ensure_run_dir, write_run_manifest, get_git_commit
    from scripts.contracts.cards import validate_cards, parse_api_response

    archive_root = Path(args.archive_root) if args.archive_root else _PROJECT_ROOT / "archive"

    print(f"\n{'='*60}")
    print(f"🔍 批量获取 Batch Job 结果")
    print(f"{'='*60}")
    print(f"📁 扫描目录: {archive_root}")

    # 扫描所有 manifest
    manifests = list(archive_root.rglob("batch_manifest.json"))
    print(f"📋 找到 {len(manifests)} 个 manifest\n")

    if not manifests:
        print("没有找到任何 batch manifest")
        return 0

    # 创建客户端
    client = create_client(proxy=args.proxy)

    # 统计
    total_jobs = len(manifests)
    succeeded_jobs = 0
    failed_jobs = 0
    pending_jobs = 0
    already_fetched = 0

    for i, manifest_path in enumerate(sorted(manifests), 1):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        archive_batch = manifest.get("archive_batch", "N/A")
        job_name = manifest.get("job_name")
        run_id = manifest.get("run_id")
        model = manifest.get("model", DEFAULT_MODEL)
        local_state = manifest.get("state", "N/A")
        run_dir = manifest_path.parent

        print(f"[{i}/{total_jobs}] {archive_batch} ({manifest.get('students_count', 0)}人)")
        print(f"    Run ID: {run_id}")

        # 检查是否已经获取过
        has_output = (run_dir / "batch_output.jsonl").exists()
        if not args.force and has_output and manifest.get("fetched_at"):
            print(f"    ✓ 已获取过，跳过")
            already_fetched += 1
            continue

        # 如果有 fetched_at 但没有 output 文件，标记需要重新下载
        if manifest.get("fetched_at") and not has_output:
            print(f"    ⚠️  缺少 batch_output.jsonl，重新下载")

        if not job_name:
            print(f"    ⚠️  无 job_name，跳过")
            failed_jobs += 1
            continue

        # 查询实际状态
        try:
            batch_job = client.batches.get(name=job_name)
            actual_state = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)
        except Exception as e:
            print(f"    ✗ 查询失败: {e}")
            failed_jobs += 1
            continue

        print(f"    状态: {actual_state}")

        if actual_state not in COMPLETED_STATES:
            print(f"    ⏳ 仍在处理中...")
            pending_jobs += 1
            # 更新 manifest 中的状态
            manifest["state"] = actual_state
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            continue

        if actual_state != "JOB_STATE_SUCCEEDED":
            print(f"    ✗ Job 未成功: {actual_state}")
            failed_jobs += 1
            manifest["state"] = actual_state
            manifest["final_state"] = actual_state
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            continue

        # 下载结果
        if not batch_job.dest or not batch_job.dest.file_name:
            print(f"    ✗ 无结果文件")
            failed_jobs += 1
            continue

        result_file_name = batch_job.dest.file_name
        print(f"    📥 下载结果: {result_file_name}")

        try:
            result_content = client.files.download(file=result_file_name)
            result_text = result_content.decode("utf-8")
        except Exception as e:
            print(f"    ✗ 下载失败: {e}")
            failed_jobs += 1
            continue

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

        for result in results:
            key = result.get("key", "")
            parts = key.split(":")
            if len(parts) != 3:
                fail_count += 1
                continue

            archive_batch_key, student_name, run_id_key = parts

            if "error" in result:
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": result["error"]})
                continue

            response = result.get("response", {})
            if not response:
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": "no_response"})
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
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": f"extract_failed: {e}"})
                continue

            parsed = parse_api_response(raw_text)
            if parsed.get("_parse_error"):
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": "json_parse_failed"})
                continue

            annotations = parsed["annotations"]
            final_grade = parsed["final_grade_suggestion"]
            mistake_count = parsed["mistake_count"]

            is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
            if not is_valid:
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": f"validation_failed"})
                continue

            if final_grade not in ["A", "B", "C"]:
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": f"invalid_grade: {final_grade}"})
                continue

            # 保存到学生 run 目录
            try:
                stu_run_dir = ensure_run_dir(
                    archive_batch=archive_batch_key,
                    student_name=student_name,
                    annotator_name=model,
                    run_id=run_id,
                )

                annotation_result = {
                    "student_name": student_name,
                    "final_grade_suggestion": final_grade,
                    "mistake_count": mistake_count,
                    "annotations": annotations,
                    "_metadata": {
                        "model": model,
                        "batch_job": job_name,
                        "run_id": run_id,
                        "git_commit": get_git_commit(short=False),
                        "timestamp": datetime.now().isoformat(),
                        "source": "batch_api",
                    }
                }

                annotation_path = stu_run_dir / "4_llm_annotation.json"
                with open(annotation_path, "w", encoding="utf-8") as f:
                    json.dump(annotation_result, f, ensure_ascii=False, indent=2)

                write_run_manifest(
                    run_dir=stu_run_dir,
                    annotator_name=model,
                    run_id=run_id,
                    archive_batch=archive_batch_key,
                    student_name=student_name,
                    prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / "user.md",
                    prompt_hash="batch",
                    model=model,
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
                fail_count += 1
                student_results.append({"student": student_name, "status": "error", "error": f"save_failed: {e}"})

        # 计算 token 统计
        total_tokens = {
            "prompt_tokens": 0,
            "thoughts_tokens": 0,
            "candidates_tokens": 0,
            "total_tokens": 0,
        }
        for result in results:
            usage = result.get("response", {}).get("usageMetadata", {})
            total_tokens["prompt_tokens"] += usage.get("promptTokenCount", 0)
            total_tokens["thoughts_tokens"] += usage.get("thoughtsTokenCount", 0)
            total_tokens["candidates_tokens"] += usage.get("candidatesTokenCount", 0)
            total_tokens["total_tokens"] += usage.get("totalTokenCount", 0)

        # 更新 manifest
        manifest["state"] = actual_state
        manifest["final_state"] = actual_state
        manifest["result_file"] = result_file_name
        manifest["fetched_at"] = datetime.now().isoformat()
        manifest["statistics"] = {
            "success_count": success_count,
            "fail_count": fail_count,
            "grade_distribution": grade_distribution,
        }
        manifest["token_usage"] = total_tokens
        manifest["student_results"] = student_results

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 生成班级报告
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

        print(f"    ✓ 回填完成: {success_count}成功, {fail_count}失败")
        print(f"    📈 成绩: A={grade_distribution['A']} B={grade_distribution['B']} C={grade_distribution['C']}")
        print(f"    🔢 Token: {total_tokens['total_tokens']:,} (prompt: {total_tokens['prompt_tokens']:,})")
        succeeded_jobs += 1

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 汇总")
    print(f"{'='*60}")
    print(f"   总计: {total_jobs} 个 jobs")
    print(f"   已获取: {already_fetched}")
    print(f"   本次成功: {succeeded_jobs}")
    print(f"   仍在处理: {pending_jobs}")
    print(f"   失败: {failed_jobs}")

    return 0


# ============================================================================
# List 命令
# ============================================================================

def cmd_list(args: argparse.Namespace) -> int:
    """列出 batch jobs"""
    client = create_client(proxy=args.proxy)

    print(f"\n📋 列出 Batch Jobs...")

    try:
        # SDK 可能有 list 方法
        if hasattr(client.batches, "list"):
            jobs = list(client.batches.list())
            if not jobs:
                print("   (无 batch jobs)")
                return 0

            print(f"   找到 {len(jobs)} 个 jobs:\n")
            for job in jobs[:20]:  # 最多显示 20 个
                state = job.state.name if hasattr(job.state, "name") else str(job.state)
                display_name = getattr(job, "display_name", "N/A")
                print(f"   {job.name}")
                print(f"      Display: {display_name}")
                print(f"      State: {state}")
                print()
        else:
            print("   SDK 不支持 list 方法")
            return 1

    except Exception as e:
        print(f"❌ 列出失败: {e}")
        return 1

    return 0


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gemini Batch API 批量处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run 命令 (推荐使用)
    run_parser = subparsers.add_parser(
        "run",
        help="一键运行：提交 → 监听 → 回填 (推荐)"
    )
    run_parser.add_argument(
        "--archive-batch", required=True,
        help="Archive batch 名称"
    )
    run_parser.add_argument(
        "--students",
        help="学生列表（逗号分隔），不指定则处理全部"
    )
    run_parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"模型名称 (默认: {DEFAULT_MODEL})"
    )
    run_parser.add_argument(
        "--display-name",
        help="Job 显示名称"
    )
    run_parser.add_argument(
        "--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"轮询间隔秒数 (默认: {DEFAULT_POLL_INTERVAL})"
    )
    run_parser.add_argument(
        "--timeout", type=int,
        help="最大等待时间秒数（超时后保存 manifest 可恢复）"
    )
    run_parser.add_argument(
        "--proxy",
        help="代理地址，如 socks5://127.0.0.1:7890"
    )

    # submit 命令 (仅提交，不等待)
    submit_parser = subparsers.add_parser("submit", help="仅提交 batch job（不等待）")
    submit_parser.add_argument(
        "--archive-batch", required=True,
        help="Archive batch 名称"
    )
    submit_parser.add_argument(
        "--students",
        help="学生列表（逗号分隔），不指定则处理全部"
    )
    submit_parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"模型名称 (默认: {DEFAULT_MODEL})"
    )
    submit_parser.add_argument(
        "--display-name",
        help="Job 显示名称"
    )
    submit_parser.add_argument(
        "--proxy",
        help="代理地址，如 socks5://127.0.0.1:7890"
    )

    # fetch 命令
    fetch_parser = subparsers.add_parser("fetch", help="获取结果并回填")
    fetch_parser.add_argument(
        "--manifest",
        help="Manifest 文件路径"
    )
    fetch_parser.add_argument(
        "--job",
        help="Job name (如 batches/xxx)"
    )
    fetch_parser.add_argument(
        "--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"轮询间隔秒数 (默认: {DEFAULT_POLL_INTERVAL})"
    )
    fetch_parser.add_argument(
        "--timeout", type=int,
        help="最大等待时间秒数"
    )
    fetch_parser.add_argument(
        "--proxy",
        help="代理地址"
    )

    # status 命令
    status_parser = subparsers.add_parser("status", help="查询 job 状态")
    status_parser.add_argument(
        "--job", required=True,
        help="Job name"
    )
    status_parser.add_argument(
        "--proxy",
        help="代理地址"
    )

    # cancel 命令
    cancel_parser = subparsers.add_parser("cancel", help="取消 job")
    cancel_parser.add_argument(
        "--job", required=True,
        help="Job name"
    )
    cancel_parser.add_argument(
        "--proxy",
        help="代理地址"
    )

    # fetch-all 命令
    fetch_all_parser = subparsers.add_parser(
        "fetch-all",
        help="批量获取所有 pending 的 job 结果"
    )
    fetch_all_parser.add_argument(
        "--archive-root",
        help="Archive 根目录（默认: archive/）"
    )
    fetch_all_parser.add_argument(
        "--force", action="store_true",
        help="强制重新下载所有已完成的 job（即使已获取过）"
    )
    fetch_all_parser.add_argument(
        "--proxy",
        help="代理地址"
    )

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出 jobs")
    list_parser.add_argument(
        "--proxy",
        help="代理地址"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    if args.command == "run":
        return cmd_run(args)
    elif args.command == "submit":
        return cmd_submit(args)
    elif args.command == "fetch":
        return cmd_fetch(args)
    elif args.command == "fetch-all":
        return cmd_fetch_all(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "cancel":
        return cmd_cancel(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
