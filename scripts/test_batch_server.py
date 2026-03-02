# -*- coding: utf-8 -*-
"""
scripts/test_batch_server.py - 批处理服务端测试脚本

提交任务后轮询日志，任务完成后拉取结果。
"""

import argparse
import json
import sys
import time
from typing import List, Optional

import httpx


TERMINAL_STATES = {"succeeded", "failed"}


def _parse_students(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


def _post_job(server: str, payload: dict) -> dict:
    url = f"{server}/jobs"
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def _poll_logs(server: str, job_id: str, poll_interval: int) -> None:
    cursor = 0
    with httpx.Client(timeout=60) as client:
        while True:
            resp = client.get(
                f"{server}/jobs/{job_id}/logs",
                params={"cursor": cursor},
            )
            resp.raise_for_status()
            data = resp.json()
            logs = data.get("logs", "")
            if logs:
                sys.stdout.write(logs)
                if not logs.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()
            cursor = data.get("next_cursor", cursor)
            status = data.get("status")
            if status in TERMINAL_STATES:
                print(f"[完成] 任务状态: {status}")
                break
            time.sleep(poll_interval)


def _fetch_result(server: str, job_id: str) -> dict:
    url = f"{server}/jobs/{job_id}/result"
    with httpx.Client(timeout=60) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="批处理服务端测试脚本")
    parser.add_argument("--archive-batch", required=True)
    parser.add_argument("--students", help="学生列表（逗号分隔）")
    parser.add_argument("--model")
    parser.add_argument("--display-name")
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--proxy")
    parser.add_argument("--server", default="http://127.0.0.1:8000")

    args = parser.parse_args()

    payload = {
        "exec_mode": "batch",
        "archive_batch": args.archive_batch,
        "students": _parse_students(args.students),
        "model": args.model,
        "display_name": args.display_name,
        "poll_interval": args.poll_interval,
        "timeout": args.timeout,
        "proxy": args.proxy,
    }

    print("提交任务...")
    job = _post_job(args.server, payload)
    job_id = job.get("job_id")
    if not job_id:
        print("❌ 未获取 job_id")
        return 1

    print(f"✅ 已提交: job_id={job_id}")
    print("开始轮询日志...")
    _poll_logs(args.server, job_id, args.poll_interval)

    print("拉取结果...")
    result = _fetch_result(args.server, job_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
