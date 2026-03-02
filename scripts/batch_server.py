# -*- coding: utf-8 -*-
"""
scripts/batch_server.py - Gemini Batch API 轮询服务端

提供批处理任务提交、状态查询、日志增量获取与结果查询接口。
"""

import json
import os
import sys
import threading
import time
import uuid
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

JOBS_ROOT = _PROJECT_ROOT / "backend_output" / "server_jobs"
LOG_FILE_NAME = "server.log"
JOB_FILE_NAME = "job.json"
DEFAULT_PROXY = "socks5://127.0.0.1:7890"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


class JobRequest(BaseModel):
    exec_mode: Optional[Literal["batch"]] = Field(default="batch", description="执行模式（当前仅支持 batch）")
    # 兼容旧字段：收到 mode=asr/audio 时自动映射为 exec_mode=batch 并告警
    mode: Optional[str] = Field(default=None, description="[已废弃] 旧字段，请改用 exec_mode")
    archive_batch: str = Field(..., description="Archive batch 名称")
    students: Optional[Union[List[str], str]] = Field(default=None, description="学生列表")
    model: Optional[str] = Field(default=None, description="模型名称")
    display_name: Optional[str] = Field(default=None, description="Job 显示名称")
    poll_interval: Optional[int] = Field(default=None, description="轮询间隔秒数")
    timeout: Optional[int] = Field(default=None, description="最大等待时间秒数")
    proxy: Optional[str] = Field(default=None, description="代理地址")


class JobResponse(BaseModel):
    job_id: str
    status: str


app = FastAPI(title="Gemini Batch Server")


# ============================================================================
# 工具函数
# ============================================================================


def _now_iso() -> str:
    return datetime.now().isoformat()


def _ensure_jobs_root() -> None:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)


def _job_dir(job_id: str) -> Path:
    return JOBS_ROOT / job_id


def _job_file(job_id: str) -> Path:
    return _job_dir(job_id) / JOB_FILE_NAME


def _log_file(job_id: str) -> Path:
    return _job_dir(job_id) / LOG_FILE_NAME


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _load_job(job_id: str) -> Dict[str, Any]:
    path = _job_file(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_job(job_id: str, data: Dict[str, Any]) -> None:
    _write_json_atomic(_job_file(job_id), data)


def _normalize_students(value: Optional[Union[List[str], str]]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [s for s in value if s]
    if isinstance(value, str):
        parts = [s.strip() for s in value.split(",")]
        return [s for s in parts if s]
    return None


def _extract_run_id(line: str) -> Optional[str]:
    if "Run ID:" not in line:
        return None
    return line.split("Run ID:", 1)[1].strip().split()[0]


def _extract_manifest_path(line: str) -> Optional[str]:
    if "batch_manifest.json" not in line:
        return None
    return line.strip().split()[-1]


def _build_command(job: Dict[str, Any]) -> List[str]:
    archive_batch = job["archive_batch"]
    script_path = _PROJECT_ROOT / "scripts" / "gemini_batch_audio.py"

    cmd = ["uv", "run", "python3", "-u", str(script_path), "run", "--archive-batch", archive_batch]

    if job.get("students"):
        cmd.extend(["--students", ",".join(job["students"])])
    if job.get("model"):
        cmd.extend(["--model", job["model"]])
    if job.get("display_name"):
        cmd.extend(["--display-name", job["display_name"]])
    if job.get("poll_interval"):
        cmd.extend(["--poll-interval", str(job["poll_interval"])])
    if job.get("timeout"):
        cmd.extend(["--timeout", str(job["timeout"])])
    if job.get("proxy"):
        cmd.extend(["--proxy", job["proxy"]])

    return cmd


def _append_log(job_id: str, message: str) -> None:
    log_path = _log_file(job_id)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message)
        if not message.endswith("\n"):
            f.write("\n")


def _run_job(job_id: str) -> None:
    job = _load_job(job_id)
    job["status"] = STATUS_RUNNING
    job["started_at"] = _now_iso()
    _save_job(job_id, job)

    _append_log(job_id, f"[{_now_iso()}] 🚀 任务开始")

    cmd = _build_command(job)
    job["command"] = cmd
    _save_job(job_id, job)

    _append_log(job_id, f"[{_now_iso()}] 命令: {' '.join(cmd)}")

    run_id: Optional[str] = None
    manifest_path: Optional[str] = None

    try:
        with subprocess.Popen(
            cmd,
            cwd=str(_PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as proc:
            job["pid"] = proc.pid
            _save_job(job_id, job)

            if proc.stdout:
                for line in proc.stdout:
                    _append_log(job_id, line.rstrip("\n"))
                    if not run_id:
                        run_id = _extract_run_id(line)
                        if run_id:
                            job["run_id"] = run_id
                            _save_job(job_id, job)
                    if not manifest_path:
                        manifest_path = _extract_manifest_path(line)
                        if manifest_path:
                            job["manifest_path"] = manifest_path
                            _save_job(job_id, job)

            exit_code = proc.wait()
    except Exception as e:
        _append_log(job_id, f"[{_now_iso()}] ❌ 执行异常: {e}")
        exit_code = 1

    if run_id and not manifest_path:
        guessed_manifest = (
            _PROJECT_ROOT
            / "archive"
            / job["archive_batch"]
            / "_batch_runs"
            / run_id
            / "batch_manifest.json"
        )
        if guessed_manifest.exists():
            manifest_path = str(guessed_manifest)
            job["manifest_path"] = manifest_path

    job["exit_code"] = exit_code
    job["finished_at"] = _now_iso()
    job["status"] = STATUS_SUCCEEDED if exit_code == 0 else STATUS_FAILED
    _save_job(job_id, job)

    _append_log(job_id, f"[{_now_iso()}] ✅ 任务结束 (exit_code={exit_code})")


# ============================================================================
# API
# ============================================================================


@app.post("/jobs", response_model=JobResponse)
def create_job(payload: JobRequest) -> JobResponse:
    _ensure_jobs_root()

    # 兼容旧字段 mode=asr/audio → exec_mode=batch
    if payload.mode and payload.mode in ("asr", "audio"):
        import warnings
        warnings.warn(
            f"⚠️ 字段 mode='{payload.mode}' 已废弃，请改用 exec_mode='batch'",
            DeprecationWarning,
            stacklevel=1,
        )

    job_id = uuid.uuid4().hex
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    students = _normalize_students(payload.students)
    proxy = payload.proxy
    if proxy is None:
        proxy = DEFAULT_PROXY

    job = {
        "job_id": job_id,
        "exec_mode": "batch",
        "archive_batch": payload.archive_batch,
        "students": students,
        "model": payload.model,
        "display_name": payload.display_name,
        "poll_interval": payload.poll_interval,
        "timeout": payload.timeout,
        "proxy": proxy,
        "status": STATUS_QUEUED,
        "created_at": _now_iso(),
    }

    _save_job(job_id, job)
    _append_log(job_id, f"[{_now_iso()}] ✅ 任务已创建")

    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()

    return JobResponse(job_id=job_id, status=STATUS_QUEUED)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = _load_job(job_id)
    elapsed_seconds = None
    if job.get("started_at") and not job.get("finished_at"):
        try:
            started_at = datetime.fromisoformat(job["started_at"])
            elapsed_seconds = int(time.time() - started_at.timestamp())
        except Exception:
            elapsed_seconds = None

    return {
        **job,
        "elapsed_seconds": elapsed_seconds,
    }


@app.get("/jobs/{job_id}/logs")
def get_logs(
    job_id: str,
    cursor: int = Query(0, ge=0, description="日志游标（字节偏移）"),
    max_bytes: int = Query(65536, ge=1, le=1024 * 1024, description="单次读取字节数"),
) -> Dict[str, Any]:
    job = _load_job(job_id)
    log_path = _log_file(job_id)

    if not log_path.exists():
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "cursor": cursor,
            "next_cursor": cursor,
            "logs": "",
            "has_more": False,
        }

    file_size = log_path.stat().st_size
    if cursor > file_size:
        cursor = file_size

    with open(log_path, "rb") as f:
        f.seek(cursor)
        data = f.read(max_bytes)
        next_cursor = f.tell()

    has_more = next_cursor < file_size
    logs = data.decode("utf-8", errors="replace")

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "cursor": cursor,
        "next_cursor": next_cursor,
        "logs": logs,
        "has_more": has_more,
    }


@app.get("/jobs")
def list_jobs(
    limit: int = Query(20, ge=1, le=100, description="返回任务数量"),
    offset: int = Query(0, ge=0, description="跳过任务数量"),
) -> Dict[str, Any]:
    """列出所有任务"""
    _ensure_jobs_root()

    job_dirs = sorted(JOBS_ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    total = len(job_dirs)

    jobs = []
    for job_dir in job_dirs[offset : offset + limit]:
        if not job_dir.is_dir():
            continue
        job_file = job_dir / JOB_FILE_NAME
        if not job_file.exists():
            continue

        with open(job_file, "r", encoding="utf-8") as f:
            job = json.load(f)
            jobs.append(
                {
                    "job_id": job.get("job_id"),
                    "status": job.get("status"),
                    "exec_mode": job.get("exec_mode", job.get("mode", "batch")),
                    "archive_batch": job.get("archive_batch"),
                    "created_at": job.get("created_at"),
                    "started_at": job.get("started_at"),
                    "finished_at": job.get("finished_at"),
                    "run_id": job.get("run_id"),
                }
            )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": jobs,
    }


@app.get("/health")
def health_check() -> Dict[str, str]:
    """健康检查"""
    return {"status": "ok"}


@app.get("/jobs/{job_id}/result")
def get_result(job_id: str) -> Dict[str, Any]:
    job = _load_job(job_id)
    status = job.get("status")

    if status not in {STATUS_SUCCEEDED, STATUS_FAILED}:
        return {
            "job_id": job_id,
            "status": status,
            "message": "任务未完成",
        }

    manifest_path = job.get("manifest_path")
    if not manifest_path:
        return {
            "job_id": job_id,
            "status": status,
            "message": "未找到 manifest 路径",
        }

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        return {
            "job_id": job_id,
            "status": status,
            "manifest_path": manifest_path,
            "message": "manifest 文件不存在",
        }

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    timing = manifest.get("timing", {})
    token_usage = manifest.get("token_usage", {})
    statistics = manifest.get("statistics", {})

    return {
        "job_id": job_id,
        "run_id": job.get("run_id"),
        "status": status,
        "manifest_path": manifest_path,
        "token_usage": token_usage,
        "statistics": {
            "students_count": statistics.get("students_count"),
            "success_count": statistics.get("success_count"),
            "failure_count": statistics.get("failure_count"),
        },
        "timing": {
            "audio_upload_time_seconds": timing.get("audio_upload_time_seconds"),
            "jsonl_upload_time_seconds": timing.get("jsonl_upload_time_seconds"),
            "upload_time_seconds": timing.get("upload_time_seconds"),
            "submit_time_seconds": timing.get("submit_time_seconds"),
            "api_processing_time_seconds": timing.get("api_processing_time_seconds"),
            "download_time_seconds": timing.get("download_time_seconds"),
            "total_processing_time_seconds": timing.get("total_processing_time_seconds"),
            "poll_count": timing.get("poll_count"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("🚀 Gemini Batch Server 启动中...")
    print("📖 API 文档: http://127.0.0.1:8000/docs")
    print("💾 任务数据: backend_output/server_jobs/")
    print("")
    uvicorn.run(app, host="0.0.0.0", port=8000)
