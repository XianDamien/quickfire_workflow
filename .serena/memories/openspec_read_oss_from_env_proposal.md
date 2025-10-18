# OpenSpec 提案总结：从 .env 读取 OSS 配置

## 提案信息
- **Change ID**: read-oss-from-env
- **状态**: ✅ 验证通过（openspec validate read-oss-from-env --strict）
- **创建时间**: 2025-10-18
- **文档总量**: 1341 行

## 核心需求（5 项修改）

### 1. OSS 参数智能加载 (MODIFIED)
- 优先级：命令行 > .env > 默认值
- 自动读取 OSS_BUCKET_NAME、OSS_REGION、OSS_ENDPOINT
- 支持灵活覆盖

### 2. 工作流启动前凭证验证 (MODIFIED)
- 在第 1.5 步验证 OSS 凭证
- 失败时提供诊断建议
- 早期失败策略

### 3. .env 文件格式与映射 (MODIFIED)
- 支持完整配置格式
- 支持部分配置格式
- 自动推断 region

### 4. 增强控制台输出 (MODIFIED)
- 显示参数来源（.env 或命令行）
- 显示验证结果和诊断建议

### 5. 向后兼容性 (MODIFIED)
- Qwen ASR 不受影响
- 现有脚本继续正常运行

## 关键函数

### load_env_config(env_path=".env") -> dict
读取 .env 文件中的 OSS 配置
- 输入：.env 文件路径（可选）
- 输出：配置字典 {bucket, region, endpoint}
- 异常处理：不存在时返回空字典

### verify_oss_credentials(region, bucket, endpoint=None) -> tuple
验证 OSS 凭证有效性
- 使用 head_bucket() 进行轻量级验证
- 返回 (success, message)
- 失败时提供具体诊断建议

## 实现范围

**修改文件**：scripts/workflow.py（唯一需要修改的文件）

**修改点**：
1. 新增 load_env_config() 函数
2. 新增 verify_oss_credentials() 函数
3. 修改 main() 参数处理逻辑
4. 修改 run_workflow() 凭证验证步骤
5. 增强日志输出

## 参数优先级实现

```python
# 在 main() 中实现
oss_region = args.oss_region or env_config.get('region') or None
oss_bucket = args.oss_bucket or env_config.get('bucket') or None
oss_endpoint = args.oss_endpoint or env_config.get('endpoint') or None
```

## 任务规划（8-9小时）

- Phase 1: 核心函数（2.5h）
  - Task 1.1: .env 读取函数
  - Task 1.2: 凭证验证函数
  - Task 1.3: 参数优先级处理

- Phase 2: 集成与验证（1.5h）
  - Task 2.1: 集成凭证验证
  - Task 2.2: 增强日志
  - Task 2.3: 更新帮助文本

- Phase 3: 测试验证（3h）
  - Task 3.1-3.3: 各种场景测试

- Phase 4: 文档整理（1h）
  - Task 4.1-4.2: 文档和最终验证

## 文件清单

```
openspec/changes/read-oss-from-env/
├── proposal.md              # 提案文档（背景、目标、范围）
├── tasks.md                 # 任务清单（具体实现任务分解）
├── design.md                # 设计文档（架构、实现细节、权衡）
├── specs/
│   └── evaluation-workflow/
│       └── spec.md          # 规范文档（需求、场景、接口变更）
├── README.md                # 提案概览和快速参考
```

## 向后兼容性

✅ 完全兼容：
- Qwen ASR 不受影响
- 现有脚本继续运行
- 使用完整命令行参数的脚本无需修改

## 验证状态

✅ proposal.md - 背景目标明确
✅ tasks.md - 任务分解完整
✅ design.md - 架构实现完整
✅ specs/evaluation-workflow/spec.md - 所有需求包含 MUST/SHALL
✅ openspec validate --strict - 无错误

## 使用示例

### 最简便（推荐）
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr
# 自动从 .env 读取 OSS 配置
```

### 命令行覆盖
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou  # 覆盖 .env
```

### Qwen ASR（不受影响）
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv
# 完全相同的行为
```
