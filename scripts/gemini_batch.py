# -*- coding: utf-8 -*-
"""
scripts/gemini_batch.py - Gemini Batch API 批量处理脚本

使用官方 SDK 直接调用 Gemini Batch API（绕过中转站），支持代理配置。

用法:
    # 提交 batch job
    python3 scripts/gemini_batch.py submit --archive-batch <name> [--students s1,s2,...]

    # 获取结果并回填
    python3 scripts/gemini_batch.py fetch --manifest <path> [--poll-interval 30]

    # 或使用 job name 直接获取
    python3 scripts/gemini_batch.py fetch --job batches/xxx
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
        "request": request
    }


def generate_jsonl(
    archive_batch: str,
    students: List[str],
    run_id: str,
    output_path: Path,
    model: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:
    """
    生成 JSONL 输入文件

    Args:
        archive_batch: batch 名称
        students: 学生列表
        run_id: 运行 ID
        output_path: 输出文件路径
        model: 模型名称

    Returns:
        生成的请求列表（用于 manifest）
    """
    requests = []
    errors = []

    print(f"\n📝 生成 JSONL 文件: {output_path}")
    print(f"   学生数量: {len(students)}")

    with open(output_path, "w", encoding="utf-8") as f:
        for i, student in enumerate(students, 1):
            try:
                print(f"   [{i}/{len(students)}] {student}...", end=" ")
                req = build_batch_request(archive_batch, student, run_id, model)
                f.write(json.dumps(req, ensure_ascii=False) + "\n")
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

    # submit 命令
    submit_parser = subparsers.add_parser("submit", help="提交 batch job")
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
    if args.command == "submit":
        return cmd_submit(args)
    elif args.command == "fetch":
        return cmd_fetch(args)
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
