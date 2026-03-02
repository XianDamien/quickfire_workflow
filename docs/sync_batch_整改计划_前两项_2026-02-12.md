# Sync/Batch 整改计划（仅前两项，2026-02-12）

> 范围约束：
> - 只做前两项：
>   1) 对外语义统一为 `sync` / `batch`
>   2) 清理遗留 `asr/audio` 执行模式分支
> - 不做第 3 项：暂不改 `qwen_asr` 作为前置依赖

## 计划范围

- 只做：
  1. 对外唯一执行模式：`sync`、`batch`
  2. 清理遗留 `asr/audio` 执行模式分支
- 不做：
  - 不改 `audio -> qwen_asr -> cards` 这条 DAG

## 执行计划（建议顺序）

### Step 1：定义兼容策略（先定规则）

- 对外唯一模式：`sync`、`batch`
- 老字段 `mode=asr/audio`：短期兼容映射，打印弃用告警；下个版本删除
- 输出简短迁移说明（给后端/调用方）

### Step 2：主入口语义收口（`scripts/main.py`）

- 保持 `--exec-mode {sync,batch}` 为唯一主参数
- `--batch/--batch-audio` 继续兼容但标为 deprecated（或按决策直接删除）
- 日志与 `--help` 文案统一为 `sync/batch`，不再出现 “asr/audio 模式”说法

### Step 3：服务端 API 收口（`scripts/batch_server.py`）

- `JobRequest` 从 `mode=asr/audio` 改为 `exec_mode=batch`（或 `mode=batch`，二选一）
- `_build_command` 去掉 `gemini_batch.py` 分支，固定走 `gemini_batch_audio.py`
- 对旧请求值 `asr/audio` 做兼容映射 + 明确告警（避免线上调用立刻失败）

### Step 4：联调脚本同步（`scripts/test_batch_server.py`、`scripts/test_batch_server.sh`）

- 参数改为与服务端一致（`exec_mode=batch` 或新字段）
- 默认值从 `asr` 改为 `batch`
- 帮助信息、示例命令同步更新

### Step 5：文档收口（`README.md`、`scripts/README.md`、`docs/backend-integration.md`）

- 执行模式只写 `sync/batch`
- 删除/替换 “asr/audio mode” 的调用示例
- 明确：当前 batch 为“直接音频输入 LLM”路径

### Step 6：验收

- `python3 scripts/main.py --help` 仅体现 `sync/batch`
- `POST /jobs` 新字段正常；旧 `asr/audio` 仍可兼容（并告警）
- `rg -n "mode.*asr|mode.*audio|if .*== \"asr\"" scripts/` 仅剩非执行模式语义内容（如 ASR 阶段名）
- dry-run 跑通：
  - `main.py --exec-mode sync --dry-run`
  - `main.py --exec-mode batch --dry-run`

## 交付原则

- 先兼容、后下线：避免中断现有实验与调用方
- 所有变更以“对外接口稳定”为优先
- 文档、CLI、服务端参数语义保持一致
