# Comparing Models Command

根据用户提供的 batch_id 和多个 annotator/模式，运行评分 pipeline 并生成对比报告。

## 工作流程

### 方式 1: 使用命令行（同步，适合快速测试）

1. **验证输入**
   - 检查 batch_id 是否存在于 `archive/` 目录
   - 验证所有 annotator 是否合法（支持的 annotator: gemini-3-pro-preview, qwen-max, qwen3-max）

2. **检查前置条件**
   - 确认所有学生都有 ASR 数据（`2_qwen_asr.json`）
   - 如果缺失，提示用户先运行：
     ```bash
     uv run python3 scripts/main.py --archive-batch <batch_id> --only qwen_asr
     uv run python3 scripts/main.py --archive-batch <batch_id> --only timestamps
     ```

3. **运行评分 pipeline**
   - 对每个 annotator 运行 cards 阶段：
     ```bash
     uv run python3 scripts/main.py \
       --archive-batch <batch_id> \
       --annotator <annotator> \
       --only cards
     ```
   - 记录每次运行的 run_id

4. **生成对比报告**
   - 使用 `compare_asr_audio.py` 生成 Excel 对比报告
   - 或使用其他对比工具分析结果

### 方式 2: 使用 Batch Server（异步，适合长时间运行）

**推荐用于**：
- 需要同时提交多个测试任务
- 任务运行时间较长（10-20 分钟）
- 需要轮询日志和结果

**工作流程**：

1. **启动服务端**（如果还未启动）
   ```bash
   # 新终端窗口运行
   uv run python3 scripts/batch_server.py
   ```

2. **提交对比任务**
   ```bash
   # 提交 ASR 方案任务
   curl -X POST http://127.0.0.1:8000/jobs \
     -H 'Content-Type: application/json' \
     -d '{
       "mode": "asr",
       "archive_batch": "<batch_id>",
       "model": "gemini-3-pro-preview"
     }'

   # 提交音频方案任务
   curl -X POST http://127.0.0.1:8000/jobs \
     -H 'Content-Type: application/json' \
     -d '{
       "mode": "audio",
       "archive_batch": "<batch_id>",
       "display_name": "audio-test-1",
       "proxy": "http://127.0.0.1:7890"
     }'
   ```

3. **查看所有任务**
   ```bash
   curl http://127.0.0.1:8000/jobs | jq '.jobs'
   ```

4. **轮询单个任务状态和日志**
   ```bash
   # 查询状态
   curl http://127.0.0.1:8000/jobs/{job_id} | jq '.'

   # 增量获取日志
   curl "http://127.0.0.1:8000/jobs/{job_id}/logs?cursor=0" | jq -r '.logs'
   ```

5. **获取结果（包含 token、timing、statistics）**
   ```bash
   curl http://127.0.0.1:8000/jobs/{job_id}/result | jq '.'
   ```

6. **生成对比报告**
   ```bash
   # 使用返回的 run_id 生成对比
   uv run python3 scripts/compare_asr_audio.py <batch_id> <run_id1> <run_id2> ...
   ```

## 示例

### 示例 1: 命令行对比多个 Annotator

用户输入：
```
对比 Zoe61330_2025-12-15 使用 gemini-3-pro-preview 和 qwen-max
```

执行：
```bash
# 检查 ASR 数据
ls archive/Zoe61330_2025-12-15/*/2_qwen_asr.json

# 运行 gemini-3-pro-preview
uv run python3 scripts/main.py \
  --archive-batch Zoe61330_2025-12-15 \
  --annotator gemini-3-pro-preview \
  --only cards

# 运行 qwen-max
uv run python3 scripts/main.py \
  --archive-batch Zoe61330_2025-12-15 \
  --annotator qwen-max \
  --only cards

# 收集 run_id 并提示用户如何生成对比报告
uv run python3 scripts/compare_asr_audio.py Zoe61330_2025-12-15 <run_id1> <run_id2>
```

### 示例 2: Batch Server 对比 ASR vs 音频

用户输入：
```
对比 Zoe61330_2025-12-15 的 ASR 方案和音频方案
```

执行：
```bash
# 1. 启动服务端（如果未启动）
uv run python3 scripts/batch_server.py &

# 2. 提交 ASR 方案
ASR_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "asr",
    "archive_batch": "Zoe61330_2025-12-15"
  }')
ASR_JOB_ID=$(echo "$ASR_RESPONSE" | jq -r '.job_id')

# 3. 提交音频方案
AUDIO_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "audio",
    "archive_batch": "Zoe61330_2025-12-15",
    "display_name": "audio-test-1",
    "proxy": "http://127.0.0.1:7890"
  }')
AUDIO_JOB_ID=$(echo "$AUDIO_RESPONSE" | jq -r '.job_id')

# 4. 查看所有任务
curl http://127.0.0.1:8000/jobs | jq '.jobs[] | {job_id, status, mode}'

# 5. 等待完成后获取结果
curl http://127.0.0.1:8000/jobs/$ASR_JOB_ID/result | jq '.run_id'
curl http://127.0.0.1:8000/jobs/$AUDIO_JOB_ID/result | jq '.run_id'

# 6. 生成对比报告
uv run python3 scripts/compare_asr_audio.py Zoe61330_2025-12-15 <asr_run_id> <audio_run_id>
```

### 示例 3: Batch Server 批量提交多次测试

用户输入：
```
提交 Zoe61330_2025-12-15 的 3 次 ASR 测试和 3 次音频测试
```

执行：
```bash
# 1. 启动服务端
uv run python3 scripts/batch_server.py &

# 2. 批量提交 ASR 测试
for i in 1 2 3; do
  curl -X POST http://127.0.0.1:8000/jobs \
    -H 'Content-Type: application/json' \
    -d "{
      \"mode\": \"asr\",
      \"archive_batch\": \"Zoe61330_2025-12-15\",
      \"display_name\": \"asr-test-$i\"
    }"
  sleep 2
done

# 3. 批量提交音频测试
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

# 4. 监控所有任务
watch -n 10 "curl -s http://127.0.0.1:8000/jobs | jq '.jobs[] | {job_id, status, mode, display_name}'"

# 5. 所有任务完成后，收集 run_id 生成对比报告
curl http://127.0.0.1:8000/jobs | jq -r '.jobs[] | .run_id' | grep -v null
```

---

## ASR vs 音频方案对比测试（命令行方式）

**注意**：推荐使用 Batch Server 方式（见示例 2 和 3），更适合长时间运行的对比测试。

### 前置准备

```bash
# 安装依赖
uv sync

# 设置环境变量
export GEMINI_API_KEY=<your_api_key>
export HTTPS_PROXY=http://127.0.0.1:7890
```

### 方案 A: ASR + 文本方案

```bash
# 运行完整流程（如果还没有 ASR 数据）
uv run python3 scripts/main.py \
  --archive-batch <batch_id> \
  --annotator gemini-3-pro-preview

# 或只运行评分阶段（如果已有 ASR 数据）
uv run python3 scripts/main.py \
  --archive-batch <batch_id> \
  --annotator gemini-3-pro-preview \
  --only cards
```

### 方案 B: 音频直传方案

```bash
# 提交音频批处理任务
GEMINI_API_KEY=<your_api_key> \
HTTPS_PROXY=http://127.0.0.1:7890 \
uv run python3 scripts/gemini_batch_audio.py submit \
  --archive-batch <batch_id> \
  --display-name "audio-test-1"

# 拉取结果（使用 submit 输出的 manifest 路径）
uv run python3 scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json
```

### 生成对比报告

```bash
# 对比多个运行结果
uv run python3 scripts/compare_asr_audio.py <batch_id> <run_id1> <run_id2> [run_id3] ...

# 示例：对比 1 个 ASR 测试和 3 个音频测试
uv run python3 scripts/compare_asr_audio.py \
  Zoe61330_2025-12-15 \
  002933 \
  110826 \
  192906 \
  200220
```

**输出**：
- Excel 文件：`archive/<batch_id>/comparison_report_<run_ids>.xlsx`
- 包含 2 个工作表：
  1. **核心指标**：成功率、Token 消耗、处理时间、失败学生数等
  2. **错误详情**：逐条错误题目明细（issue_type != null）

### 关键指标

对比时关注以下指标：

**可靠性指标**
- 成功率（成功学生数 / 总学生数）
- 失败模式（哪些学生失败，原因是什么）

**成本指标**
- Total Tokens（总 Token 消耗）
- Thoughts Tokens（思考 Token，通常占大头）
- Prompt Tokens（输入 Token）
- 处理时间（秒）

**质量指标**
- 成绩分布（A/B/C 的比例）
- 错误检测的细节（是否有漏检或误检）

### 查看测试结果

**命令行快速查看**：
```bash
# 查看单个运行的关键指标
jq '{
  run_id: .run_id,
  mode: .mode,
  success: "\(.statistics.success_count)/\(.statistics.students_count)",
  total_tokens: .token_usage.total_tokens,
  thoughts_tokens: .token_usage.thoughts_tokens,
  processing_time: .timing.api_processing_time_seconds
}' archive/<batch_id>/_batch_runs/<run_id>/batch_manifest.json

# 列出所有运行记录
ls -lt archive/<batch_id>/_batch_runs/ | head

# 生成包含所有 archive 数据的总表
uv run python3 scripts/consolidate_grades.py
```

**Batch Server API 查看**：
```bash
# 列出所有任务
curl http://127.0.0.1:8000/jobs | jq '.jobs[] | {job_id, status, mode, run_id}'

# 查看单个任务详情（包含 token、timing、statistics）
curl http://127.0.0.1:8000/jobs/{job_id}/result | jq '.'

# 快速查看关键指标
curl http://127.0.0.1:8000/jobs/{job_id}/result | jq '{
  run_id,
  status,
  success: "\(.statistics.success_count)/\(.statistics.students_count)",
  total_tokens: .token_usage.total_tokens,
  thoughts_tokens: .token_usage.thoughts_tokens,
  processing_time: .timing.api_processing_time_seconds,
  upload_time: .timing.upload_time_seconds
}'
```

---

## 常见问题

### Q1: 音频上传失败
**现象**: `Failed to upload audio file`

**解决**:
```bash
# 确认代理设置
echo $HTTPS_PROXY

# 如果为空，重新设置
export HTTPS_PROXY=http://127.0.0.1:7890
```

### Q2: ASR 方案找不到时间戳
**现象**: `No ASR timestamp found`

**解决**:
```bash
# 先运行 ASR 转写
uv run python3 scripts/main.py --archive-batch <batch_id> --only qwen_asr

# 再运行时间戳生成
uv run python3 scripts/main.py --archive-batch <batch_id> --only timestamps

# 最后运行评分
uv run python3 scripts/main.py --archive-batch <batch_id> --only cards
```

### Q3: 如何重新测试

**命令行方式**：
```bash
# 方案 A (ASR)：直接重新运行即可，会创建新的 run
uv run python3 scripts/main.py --archive-batch <batch_id> --only cards

# 方案 B (音频)：先提交，再拉取
GEMINI_API_KEY=<key> HTTPS_PROXY=http://127.0.0.1:7890 \
uv run python3 scripts/gemini_batch_audio.py submit \
  --archive-batch <batch_id> --display-name "retest"

uv run python3 scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch_id>/_batch_runs/<run_dir>.audio/batch_manifest.json
```

**Batch Server 方式**：
```bash
# 重新提交任务即可，服务端会创建新的 job_id
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "asr",
    "archive_batch": "<batch_id>"
  }'
```

### Q4: 如何监控长时间运行的任务

**Batch Server 实时监控**：
```bash
JOB_ID="your_job_id"

# 实时查看日志（自动滚动）
CURSOR=0
while true; do
  sleep 5
  LOGS=$(curl -s "http://127.0.0.1:8000/jobs/$JOB_ID/logs?cursor=$CURSOR")
  STATUS=$(echo "$LOGS" | jq -r '.status')
  CURSOR=$(echo "$LOGS" | jq -r '.next_cursor')
  NEW_CONTENT=$(echo "$LOGS" | jq -r '.logs')

  [ -n "$NEW_CONTENT" ] && echo "$NEW_CONTENT"

  if [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ]; then
    echo "任务完成: $STATUS"
    break
  fi
done

# 或使用 watch 命令查看状态
watch -n 10 "curl -s http://127.0.0.1:8000/jobs/$JOB_ID | jq '{status, elapsed_seconds}'"
```

### Q5: Batch Server vs 命令行，应该选哪个？

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 单次快速测试 | 命令行 | 简单直接 |
| 需要同时运行多个测试 | Batch Server | 异步并发，无需等待 |
| 任务运行时间 > 10 分钟 | Batch Server | 可轮询日志，不会阻塞 |
| 需要查看历史任务 | Batch Server | 提供任务列表和状态查询 |
| 自动化/CI/CD | Batch Server | RESTful API，易于集成 |

---

## 注意事项

- ⚠️ **使用真实音频文件，绝不模拟 ASR 数据**
- 每次运行会创建新的 run_id，确保测试结果可追溯
- 音频方案需要代理才能上传文件到 Google API
- 对比报告仅使用完整成功的运行记录
- 所有命令统一使用 `uv run python3`，确保虚拟环境一致

## 快速参考

### Batch Server 常用命令

```bash
# 启动服务
uv run python3 scripts/batch_server.py

# API 文档
open http://127.0.0.1:8000/docs

# 提交 ASR 任务
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"asr","archive_batch":"<batch_id>"}'

# 提交音频任务
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"mode":"audio","archive_batch":"<batch_id>","proxy":"http://127.0.0.1:7890"}'

# 查看所有任务
curl http://127.0.0.1:8000/jobs | jq '.jobs'

# 查看任务状态
curl http://127.0.0.1:8000/jobs/{job_id} | jq '.'

# 查看任务日志
curl "http://127.0.0.1:8000/jobs/{job_id}/logs?cursor=0" | jq -r '.logs'

# 获取任务结果
curl http://127.0.0.1:8000/jobs/{job_id}/result | jq '.'
```

### 相关文档

- 完整测试指南：`docs/how_to_test_comparison.md`
- Batch Server API 文档：`docs/batch_server_api.md`
- 测试脚本：`scripts/test_batch_server.sh`
