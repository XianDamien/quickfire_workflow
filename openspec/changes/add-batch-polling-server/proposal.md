# Change: Add FastAPI batch polling server for Gemini batch jobs

## Why
当前批处理只能通过 CLI 运行，缺少服务化能力，无法在提交后持续输出日志并支持长时间轮询。需要一个服务端来统一管理任务、日志和结果，以支持 10-20 分钟的长任务。

## What Changes
- 新增 FastAPI 服务端，提供批处理任务提交、状态查询、日志轮询与结果获取接口
- 支持两种执行模式：ASR 文本版（`scripts/gemini_batch.py`）与音频版（`scripts/gemini_batch_audio.py`）
- 任务后台异步执行，实时收集并按增量提供日志
- 新增任务状态与日志持久化目录（便于排查与复查）
- 增加 FastAPI/uvicorn 运行依赖

## Impact
- Affected specs: `batch-job-server`
- Affected code: 新增服务端模块；可能调整 batch 脚本以便复用/捕获输出；更新 `pyproject.toml` 依赖与 README 使用说明
