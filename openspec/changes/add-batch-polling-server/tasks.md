## 1. Implementation
- [x] 1.1 新增 FastAPI 服务端入口与启动脚本
- [x] 1.2 定义任务模型与状态流转（queued/running/succeeded/failed）
- [x] 1.3 实现任务后台执行与 stdout/stderr 捕获
- [x] 1.4 实现日志增量接口（基于偏移量游标）
- [x] 1.5 实现任务状态与结果查询接口
- [x] 1.6 增加本地持久化目录（任务状态、日志）
- [x] 1.7 更新 `pyproject.toml` 依赖（fastapi、uvicorn）
- [x] 1.8 更新 README 使用说明与示例请求
