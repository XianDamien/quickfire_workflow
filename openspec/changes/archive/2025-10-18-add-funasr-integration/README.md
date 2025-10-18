# FunASR 集成工作流提案 (add-funasr-integration)

## 快速导航

| 文档 | 用途 |
|------|------|
| `proposal.md` | 📋 提案摘要、目标、范围和风险评估 |
| `design.md` | 🏗️ 详细的技术设计和架构说明 |
| `tasks.md` | ✅ 16 个具体实现任务清单 |
| `specs/audio-transcription/spec.md` | 📚 新增能力规范：FunASR + OSS 上传 |
| `specs/evaluation-workflow/spec.md` | 📚 修改的能力规范：多引擎支持 |

## 提案一览

**名称**：集成 FunASR 工作流
**ID**：add-funasr-integration
**状态**：✅ 验证通过，待审核
**验证时间**：2025-10-18

### 核心需求

该提案解决了以下问题：
1. **单一转写引擎**：当前只支持 Qwen ASR
2. **本地文件不便**：FunASR 仅支持 OSS URL，需要手动上传
3. **工作流集成**：缺乏统一的多引擎工作流

### 提案的价值

- ✅ 灵活选择 ASR 引擎（Qwen 或 FunASR）
- ✅ 自动化本地文件 → OSS 上传流程
- ✅ 100% 向后兼容（默认 Qwen）
- ✅ 为未来集成其他引擎奠定基础

## 关键设计决策

### 1. 多模块设计

```
funasr_workflow.py (NEW)
├── upload_audio_to_oss()      # OSS 上传
├── transcribe_with_funasr()   # FunASR 调用 + 轮询
└── normalize_asr_output()     # 结果标准化

workflow.py (EXTENDED)
├── --asr-engine {qwen|funasr}
├── --oss-region (FunASR 模式必需)
├── --oss-bucket (FunASR 模式必需)
└── 自动选择转写路径

captioner_qwen3.py (REFACTORED)
└── transcribe_audio() 函数提取（便于复用）
```

### 2. 数据流

**Qwen 路径**（现有）：
```
Local Audio → Qwen ASR → Standard JSON → Evaluation
```

**FunASR 路径**（新增）：
```
Local Audio → OSS Upload → FunASR → Normalize → Evaluation
```

### 3. 异步任务处理

FunASR 使用异步 API：
- ✅ 提交任务后返回 task_id
- ✅ 轮询查询状态（最多 10 次，每次 2 秒）
- ✅ 处理 SUCCEEDED/FAILED 状态
- ⏱️ 超时控制：约 20 秒内完成

### 4. 格式标准化

两种引擎输出都转换为统一格式：

```json
{
  "sentences": [
    {
      "text": "英文单词",
      "speaker": "spk0",  // 教师 or 学生
      "start_time": 1000, // 毫秒
      "end_time": 2000,
      "word_timestamp": []
    }
  ]
}
```

## 实现路线图

### Phase 1: FunASR 核心模块 (2-3 小时)
- [ ] 创建 `funasr_workflow.py` 骨架
- [ ] 实现 `upload_audio_to_oss()`
- [ ] 实现 `transcribe_with_funasr()`
- [ ] 实现 `normalize_asr_output()`

### Phase 2: workflow.py 扩展 (1-2 小时)
- [ ] 添加新命令行参数
- [ ] 实现 ASR 引擎选择逻辑
- [ ] 参数验证和错误处理

### Phase 3: captioner_qwen3.py 重构 (0.5-1 小时)
- [ ] 提取 `transcribe_audio()` 函数
- [ ] 保持向后兼容

### Phase 4: 测试和文档 (1-2 小时)
- [ ] Qwen 模式回归测试
- [ ] FunASR 模式功能测试
- [ ] 参数验证测试
- [ ] 更新命令行帮助和文档

### Phase 5: 可观测性增强 (0.5-1 小时，可选)
- [ ] 添加详细日志
- [ ] 上传和转写进度显示

**总计**：5-9 小时

## 验证状态

```bash
$ openspec validate add-funasr-integration --strict
Change 'add-funasr-integration' is valid ✅
```

所有规范检查均通过：
- ✅ 规范文件结构正确
- ✅ 需求包含 SHALL/MUST 声明
- ✅ 每个需求至少有一个 Scenario
- ✅ 向后兼容性声明明确

## 命令行用法示例

### 现有用法（保持不变）
```bash
# Qwen ASR（默认）
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/R1-65(1).csv
```

### 新增 FunASR 用法
```bash
# FunASR（需要提供 OSS 参数）
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou \
  --oss-bucket your-bucket-name

# 可选：保留 OSS 文件
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou \
  --oss-bucket your-bucket-name \
  --keep-oss-file

# 可选：指定 OSS 端点
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/R1-65(1).csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou \
  --oss-bucket your-bucket-name \
  --oss-endpoint oss-cn-hangzhou.aliyuncs.com
```

## 环境配置

### 必需环境变量
```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxx"
```

### 可选环境变量（FunASR 模式）
```bash
# 作为默认值，可被 CLI 参数覆盖
export OSS_REGION="cn-hangzhou"
export OSS_BUCKET="my-bucket"
export OSS_ENDPOINT="oss-cn-hangzhou.aliyuncs.com"
```

## 错误处理策略

### 文件上传错误
- 文件不存在 → 清晰的错误提示
- 权限不足 → 检查 OSS 凭证建议
- 网络错误 → 自动重试 3 次

### 转写错误
- 任务提交失败 → 显示 API 错误信息
- 任务执行失败 → 显示 task_id 便于追踪
- 轮询超时 → TimeoutError（>20 秒）

### 格式转换错误
- 缺失字段 → 使用默认值（spk0 等）
- 时间戳异常 → 验证并日志警告

## 完全向后兼容

✅ 现有脚本无需修改：
- `workflow.py` 默认使用 Qwen
- `qwen3.py` 保持独立使用
- `captioner_qwen3.py` 保持独立使用
- 所有新参数都是可选的

## 相关文档

- [设计文档](./design.md) - 详细的技术实现方案
- [任务清单](./tasks.md) - 16 个具体实现任务
- [完整提案](./proposal.md) - 目标、范围和风险评估
- [音频转写规范](./specs/audio-transcription/spec.md)
- [工作流规范](./specs/evaluation-workflow/spec.md)

## 审核检查清单

在正式开始实现前，请确认：

- [ ] 提案目标明确且可行
- [ ] 设计文档充分说明了技术方案
- [ ] 16 个任务清单合理且可追踪
- [ ] 规范要求可以通过验收测试
- [ ] 向后兼容性得到保证
- [ ] 未来可扩展性已考虑（如新增其他 ASR 引擎）

## 后续工作

本提案审核通过后的实现步骤：

1. **获得审核批准**
2. **按 Phase 顺序执行任务** (详见 tasks.md)
3. **完成所有 16 个任务**
4. **执行完整工作流测试**
5. **提交 PR 并合并**
6. **归档此提案** (`openspec archive add-funasr-integration`)

---

**创建时间**：2025-10-18
**提案 ID**：add-funasr-integration
**验证状态**：✅ 通过
