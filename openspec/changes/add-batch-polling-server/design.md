## Context
- 现有 `scripts/gemini_batch.py` 与 `scripts/gemini_batch_audio.py` 具备提交+轮询+回填的完整流程
- 需求是将批处理能力服务化，并支持客户端以轮询方式获取日志与结果
- 任务可运行 10-20 分钟，需要后台执行与可观测性

## Goals / Non-Goals
- Goals:
  - 提供 FastAPI 服务端，支持任务提交、状态、日志增量与结果查询
  - 兼容 ASR 文本版与音频版两套脚本
  - 日志输出与接口返回保持中文
- Non-Goals:
  - 不改动评分 prompt 内容
  - 不引入外部消息队列或分布式调度
  - 不保证服务重启后的任务恢复

## Decisions
- Decision: 使用 FastAPI + uvicorn 提供 HTTP API
  - Why: 轻量、易于集成、支持长任务与异步处理

- Decision: 后台任务使用线程执行脚本逻辑
  - Why: 避免阻塞请求线程，保持实现简单

- Decision: 日志与状态写入本地目录 `backend_output/server_jobs/{job_id}/`
  - Why: 方便排查，支持增量读取（基于文件偏移量游标）

- Decision: 通过脚本入口执行任务，并捕获 stdout/stderr
  - Why: 复用现有稳定逻辑，减少重复实现

## Risks / Trade-offs
- 长任务导致线程资源占用 → 限制并发数并在文档中提示
- 捕获 stdout 可能导致输出格式依赖 → 在实现中保持原样并记录原始日志

## Migration Plan
- 新增服务端模块与依赖
- 添加运行说明与示例请求
- 不影响现有 CLI 使用方式

## Open Questions
- 是否需要为任务并发数设置上限与队列策略？
- 是否需要任务结果的结构化摘要接口（除 manifest 路径外）？
