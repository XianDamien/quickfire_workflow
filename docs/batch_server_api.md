# Batch Server API 文档

FastAPI 批处理服务端，支持异步提交 Gemini Batch 任务并轮询结果。

## 快速开始

### 启动服务端

```bash
# 方式 1: 直接运行（推荐）
uv run python3 scripts/batch_server.py

# 方式 2: 使用 uvicorn（开发模式，自动重载）
uv run uvicorn scripts.batch_server:app --host 0.0.0.0 --port 8000 --reload

# 方式 3: 生产环境
uv run uvicorn scripts.batch_server:app --host 0.0.0.0 --port 8000 --workers 4
```

访问交互式 API 文档：http://127.0.0.1:8000/docs

### 运行测试

```bash
# 默认测试（ASR 模式）
bash scripts/test_batch_server.sh

# 自定义批次和模式
bash scripts/test_batch_server.sh Zoe61330_2025-12-15 audio
```

---

## API 接口

### 1. 健康检查

**GET** `/health`

**响应**：
```json
{
  "status": "ok"
}
```

---

### 2. 创建任务

**POST** `/jobs`

**请求体**：
```json
{
  "mode": "asr",                              // 必填: "asr" 或 "audio"
  "archive_batch": "Zoe61330_2025-12-15",    // 必填: 批次名称
  "students": ["Alice", "Bob"],               // 可选: 学生列表（数组或逗号分隔字符串）
  "model": "gemini-3-pro-preview",           // 可选: 模型名称
  "display_name": "test-run-1",              // 可选: 显示名称
  "poll_interval": 60,                        // 可选: 轮询间隔（秒）
  "timeout": 3600,                            // 可选: 最大等待时间（秒）
  "proxy": "http://127.0.0.1:7890"           // 可选: 代理地址
}
```

**响应**：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "queued"
}
```

**示例**：
```bash
# ASR 模式
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "asr",
    "archive_batch": "Zoe61330_2025-12-15"
  }'

# 音频模式（指定学生）
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "audio",
    "archive_batch": "Zoe61330_2025-12-15",
    "students": ["Alice", "Bob"],
    "proxy": "http://127.0.0.1:7890"
  }'
```

---

### 3. 列出任务

**GET** `/jobs?limit=20&offset=0`

**查询参数**：
- `limit`: 返回数量（1-100，默认 20）
- `offset`: 跳过数量（默认 0）

**响应**：
```json
{
  "total": 5,
  "limit": 20,
  "offset": 0,
  "jobs": [
    {
      "job_id": "a1b2c3d4e5f6",
      "status": "succeeded",
      "mode": "asr",
      "archive_batch": "Zoe61330_2025-12-15",
      "created_at": "2026-01-08T10:00:00",
      "started_at": "2026-01-08T10:00:01",
      "finished_at": "2026-01-08T10:05:30",
      "run_id": "20260108_100001_abc123"
    }
  ]
}
```

**示例**：
```bash
# 列出最近 10 个任务
curl "http://127.0.0.1:8000/jobs?limit=10"
```

---

### 4. 查询任务状态

**GET** `/jobs/{job_id}`

**响应**：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "mode": "asr",
  "archive_batch": "Zoe61330_2025-12-15",
  "status": "running",
  "created_at": "2026-01-08T10:00:00",
  "started_at": "2026-01-08T10:00:01",
  "elapsed_seconds": 120,
  "run_id": "20260108_100001_abc123",
  "manifest_path": "archive/Zoe61330_2025-12-15/_batch_runs/20260108_100001_abc123/batch_manifest.json"
}
```

**状态值**：
- `queued` - 已排队
- `running` - 运行中
- `succeeded` - 成功
- `failed` - 失败

**示例**：
```bash
curl http://127.0.0.1:8000/jobs/a1b2c3d4e5f6
```

---

### 5. 增量获取日志

**GET** `/jobs/{job_id}/logs?cursor=0&max_bytes=65536`

**查询参数**：
- `cursor`: 日志游标（字节偏移，默认 0）
- `max_bytes`: 单次读取字节数（1-1048576，默认 65536）

**响应**：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "running",
  "cursor": 0,
  "next_cursor": 1024,
  "logs": "[2026-01-08T10:00:01] 🚀 任务开始\n...",
  "has_more": true
}
```

**轮询模式**：
```bash
# 初始请求
curl "http://127.0.0.1:8000/jobs/a1b2c3d4e5f6/logs?cursor=0"

# 使用返回的 next_cursor 继续轮询
curl "http://127.0.0.1:8000/jobs/a1b2c3d4e5f6/logs?cursor=1024"
```

**完整日志示例**：
```bash
# 获取完整日志（使用 jq 提取）
curl "http://127.0.0.1:8000/jobs/a1b2c3d4e5f6/logs?cursor=0&max_bytes=1048576" | jq -r '.logs'
```

---

### 6. 获取结果

**GET** `/jobs/{job_id}/result`

**响应**（成功）：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "run_id": "20260108_100001_abc123",
  "status": "succeeded",
  "manifest_path": "archive/Zoe61330_2025-12-15/_batch_runs/20260108_100001_abc123/batch_manifest.json",
  "token_usage": {
    "prompt_tokens": 12345,
    "thoughts_tokens": 6789,
    "completion_tokens": 1234,
    "total_tokens": 20368
  },
  "statistics": {
    "students_count": 5,
    "success_count": 5,
    "failure_count": 0
  },
  "timing": {
    "audio_upload_time_seconds": 12.5,
    "jsonl_upload_time_seconds": 0.8,
    "upload_time_seconds": 13.3,
    "submit_time_seconds": 1.2,
    "api_processing_time_seconds": 45.6,
    "download_time_seconds": 0.5,
    "total_processing_time_seconds": 60.6,
    "poll_count": 5
  }
}
```

**响应**（任务未完成）：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "running",
  "message": "任务未完成"
}
```

**示例**：
```bash
curl http://127.0.0.1:8000/jobs/a1b2c3d4e5f6/result | jq '.'
```

---

## 使用场景

### 场景 1: 异步提交并轮询结果

```bash
# 1. 提交任务
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"asr","archive_batch":"Zoe61330_2025-12-15"}')

JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 2. 轮询日志直到完成
CURSOR=0
while true; do
  sleep 5
  LOG_RESPONSE=$(curl -s "http://127.0.0.1:8000/jobs/$JOB_ID/logs?cursor=$CURSOR")
  STATUS=$(echo "$LOG_RESPONSE" | jq -r '.status')
  CURSOR=$(echo "$LOG_RESPONSE" | jq -r '.next_cursor')

  echo "Status: $STATUS, Cursor: $CURSOR"

  if [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

# 3. 获取结果
curl -s "http://127.0.0.1:8000/jobs/$JOB_ID/result" | jq '.'
```

### 场景 2: 批量提交多个任务

```bash
# 提交 3 个音频测试任务
for i in 1 2 3; do
  curl -X POST http://127.0.0.1:8000/jobs \
    -H 'Content-Type: application/json' \
    -d "{
      \"mode\": \"audio\",
      \"archive_batch\": \"Zoe61330_2025-12-15\",
      \"display_name\": \"audio-test-$i\",
      \"proxy\": \"http://127.0.0.1:7890\"
    }"
  sleep 2
done

# 查看所有任务
curl "http://127.0.0.1:8000/jobs?limit=10" | jq '.jobs'
```

### 场景 3: 监控任务进度

```bash
JOB_ID="a1b2c3d4e5f6"

# 实时查看状态和经过时间
watch -n 5 "curl -s http://127.0.0.1:8000/jobs/$JOB_ID | jq '{status, elapsed_seconds, run_id}'"

# 实时查看最新日志
CURSOR=0
while true; do
  sleep 3
  LOG=$(curl -s "http://127.0.0.1:8000/jobs/$JOB_ID/logs?cursor=$CURSOR")
  NEW_LOGS=$(echo "$LOG" | jq -r '.logs')
  CURSOR=$(echo "$LOG" | jq -r '.next_cursor')
  STATUS=$(echo "$LOG" | jq -r '.status')

  if [ -n "$NEW_LOGS" ]; then
    echo "$NEW_LOGS"
  fi

  [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ] && break
done
```

---

## 数据存储

任务数据存储在 `backend_output/server_jobs/{job_id}/` 目录：

```
backend_output/server_jobs/
└── a1b2c3d4e5f6/
    ├── job.json       # 任务元数据
    └── server.log     # 任务日志
```

**job.json 示例**：
```json
{
  "job_id": "a1b2c3d4e5f6",
  "mode": "asr",
  "archive_batch": "Zoe61330_2025-12-15",
  "status": "succeeded",
  "created_at": "2026-01-08T10:00:00",
  "started_at": "2026-01-08T10:00:01",
  "finished_at": "2026-01-08T10:05:30",
  "run_id": "20260108_100001_abc123",
  "manifest_path": "archive/Zoe61330_2025-12-15/_batch_runs/20260108_100001_abc123/batch_manifest.json",
  "command": ["python3", "-u", "scripts/gemini_batch.py", "run", "--archive-batch", "Zoe61330_2025-12-15"],
  "exit_code": 0,
  "pid": 12345
}
```

---

## 错误处理

### 任务不存在
```bash
$ curl http://127.0.0.1:8000/jobs/invalid_id
{
  "detail": "任务不存在"
}
```

### Manifest 文件缺失
```bash
$ curl http://127.0.0.1:8000/jobs/a1b2c3d4e5f6/result
{
  "job_id": "a1b2c3d4e5f6",
  "status": "failed",
  "message": "未找到 manifest 路径"
}
```

---

## 性能建议

1. **日志轮询**：使用 `cursor` 增量获取日志，避免重复读取
2. **轮询间隔**：建议 3-5 秒间隔，避免过于频繁
3. **任务清理**：定期清理 `backend_output/server_jobs/` 中的旧任务
4. **并发限制**：当前使用线程池，可根据需要调整并发数

---

## 与原有工具对比

| 特性 | 命令行工具 | Batch Server API |
|------|-----------|-----------------|
| 执行方式 | 同步阻塞 | 异步后台 |
| 日志查看 | 实时输出 | 增量轮询 |
| 多任务 | 需手动管理 | 自动并发 |
| 结果获取 | 直接输出 | API 接口 |
| 适用场景 | 本地测试 | 生产环境、自动化 |

---

## 后续扩展

可选的增强功能：

1. **任务取消** - `DELETE /jobs/{job_id}`
2. **任务重试** - `POST /jobs/{job_id}/retry`
3. **Webhook 通知** - 任务完成后回调
4. **任务优先级** - 支持任务队列优先级
5. **CORS 支持** - 允许前端跨域调用
6. **认证授权** - API Key 或 JWT 认证
7. **任务调度** - 定时任务、批量调度

---

---

## 常见问题

### Q1: 为什么要使用 `uv run`？

项目使用 `uv` 管理依赖，`uv run` 确保：
- 自动使用项目虚拟环境
- 依赖版本与 `pyproject.toml` 一致
- 避免全局 Python 环境污染

### Q2: 服务端如何确保使用正确的环境？

服务端内部执行任务时使用 `uv run python3`，确保子任务也运行在正确的虚拟环境中。

### Q3: 可以在后台运行服务端吗？

```bash
# 使用 nohup 后台运行
nohup uv run python3 scripts/batch_server.py > server.log 2>&1 &

# 或使用 systemd（生产环境推荐）
# 创建 /etc/systemd/system/batch-server.service
```

---

**文档版本**: 2026-01-08
**作者**: Claude Code
**环境管理**: uv
