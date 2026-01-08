## ADDED Requirements
### Requirement: Batch Job Submission
系统 SHALL 提供 HTTP 接口用于提交批处理任务，并支持 ASR 文本版与音频版两种模式。

#### Scenario: Submit audio batch job
- **WHEN** 客户端提交 `mode=audio` 且提供 `archive_batch`
- **THEN** 系统返回 `job_id` 且状态为 `queued`

### Requirement: Job Status Tracking
系统 SHALL 以异步方式执行任务，并在执行期间提供可查询的任务状态。

#### Scenario: Long running job
- **WHEN** 任务执行超过 10 分钟
- **THEN** 查询接口返回状态为 `running` 且包含已运行时长

### Requirement: Incremental Logs
系统 SHALL 提供日志增量查询接口，允许客户端通过游标获取新增日志内容。

#### Scenario: Poll logs with cursor
- **WHEN** 客户端携带上一次返回的游标请求日志
- **THEN** 系统仅返回该游标之后的新日志并提供新的游标

### Requirement: Result Retrieval
系统 SHALL 提供任务结果查询接口，在任务完成后返回 manifest 路径与执行摘要。

#### Scenario: Fetch result after completion
- **WHEN** 任务完成且状态为 `succeeded`
- **THEN** 系统返回 `manifest_path` 与基础摘要信息
