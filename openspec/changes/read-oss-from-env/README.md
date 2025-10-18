# Change Proposal: 从 .env 读取 OSS 配置到 FunASR 工作流

**Change ID:** `read-oss-from-env`
**Status:** ✅ 提案已验证通过
**Created:** 2025-10-18
**Last Updated:** 2025-10-18

---

## 📋 快速概览

### 问题
- 用户运行 FunASR 工作流时需要手动输入 `--oss-region`、`--oss-bucket` 等参数
- `.env` 文件中已配置这些参数，但工作流未充分利用
- 用户无法提前验证 OSS 凭证是否有效

### 解决方案
- ✅ 自动从 `.env` 读取 OSS 配置
- ✅ 支持命令行参数覆盖（灵活性最大）
- ✅ 在工作流启动前验证 OSS 凭证
- ✅ 完全向后兼容

### 收益
- 🎯 简化用户操作，提高开发效率
- 🔐 早期验证凭证，快速失败（fail fast）
- 📝 遵循 12-Factor 应用原则
- ✨ 改善用户体验

---

## 📂 文件结构

```
openspec/changes/read-oss-from-env/
├── proposal.md              # 提案文档（背景、目标、范围）
├── tasks.md                 # 任务清单（具体实现任务分解）
├── design.md                # 设计文档（架构、实现细节、权衡）
├── specs/
│   └── evaluation-workflow/
│       └── spec.md          # 规范文档（需求、场景、接口变更）
└── README.md                # 本文件
```

---

## 🎯 核心需求

### 1. OSS 参数智能加载
- **参数来源优先级**：命令行 > .env > 默认值
- **自动读取**：`.env` 中 `OSS_BUCKET_NAME`、`OSS_REGION`、`OSS_ENDPOINT` 等
- **灵活覆盖**：支持命令行参数完全覆盖 .env 配置

### 2. 工作流启动前凭证验证
- **验证时机**：工作流启动的第 1.5 步（验证参数之后）
- **验证内容**：OSS 凭证有效性、权限、连接性
- **失败处理**：提供诊断建议，快速失败

### 3. 增强控制台输出
- **配置来源显示**：清晰标注每个参数来自哪里（.env 或命令行）
- **验证结果显示**：凭证验证成功/失败的明确提示
- **诊断建议**：验证失败时提供具体故障排查步骤

### 4. 向后兼容
- **Qwen ASR**：完全不受影响
- **现有脚本**：继续正常运行
- **现有工作流**：使用完整命令行参数的脚本无需修改

---

## 🔧 实现概要

### 新增函数

#### `load_env_config(env_path=".env") -> dict`
```python
# 从 .env 文件读取 OSS 配置
config = load_env_config()
# 返回: {'bucket': '...', 'region': '...', 'endpoint': '...'}
```

#### `verify_oss_credentials(region, bucket, endpoint=None) -> tuple[bool, str]`
```python
# 验证 OSS 凭证有效性
success, message = verify_oss_credentials("cn-shanghai", "my-bucket")
# 返回: (True, "✅ OSS 凭证验证通过") 或 (False, "❌ 验证失败: ...")
```

### 修改位置

**文件**：`scripts/workflow.py`

**修改点**：
1. 添加 `load_env_config()` 函数
2. 添加 `verify_oss_credentials()` 函数
3. 修改 `main()` 函数中的参数处理逻辑
4. 修改 `run_workflow()` 中 FunASR 模式的启动流程
5. 增强日志输出

---

## 💡 使用示例

### 场景 1：最简便（推荐）
```bash
# 前提：.env 中已配置
#   OSS_BUCKET_NAME=quickfire-audio
#   OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com

python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr

# 输出：
# ✓ OSS 配置来源：
#    Region: cn-shanghai (来自 .env)
#    Bucket: quickfire-audio (来自 .env)
# ✓ 验证 OSS 凭证...
# ✅ OSS 凭证验证通过
# ✓ 第2步：执行音频转写 (ASR)...
```

### 场景 2：命令行覆盖
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv \
  --asr-engine funasr \
  --oss-region cn-hangzhou  # 覆盖 .env

# 输出：
# ✓ OSS 配置来源：
#    Region: cn-hangzhou (来自命令行)  ← 注意来源
#    Bucket: quickfire-audio (来自 .env)
```

### 场景 3：Qwen ASR（不受影响）
```bash
python3 workflow.py \
  --audio-path ./audio/sample.mp3 \
  --qb-path ./data/qb.csv

# 完全相同的行为，不需要 OSS 参数
```

---

## ⚠️ 错误处理示例

### 错误 1：缺少必需参数
```
❌ 错误：使用 FunASR 模式必须指定以下参数：
   - OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)
   - OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)

💡 解决方案：
   方案 1：创建 .env 文件并添加配置
           OSS_REGION=cn-hangzhou
           OSS_BUCKET_NAME=your-bucket
   方案 2：使用命令行参数
           --oss-region cn-hangzhou --oss-bucket your-bucket
```

### 错误 2：凭证验证失败
```
❌ OSS 凭证验证失败: AccessDenied

💡 诊断建议：
   - 检查 OSS 凭证权限（需要 GetBucketInfo 权限）
   - 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）
```

---

## 📊 实现规划

### Phase 1: Core Infrastructure (任务 1.1-1.3)
- 实现 .env 配置读取函数
- 实现 OSS 凭证验证函数
- 实现参数优先级处理逻辑
- **预期时间**：2.5 小时

### Phase 2: Integration & Validation (任务 2.1-2.3)
- 集成凭证验证到工作流启动阶段
- 增强错误提示和日志
- 更新命令行帮助文本
- **预期时间**：1.5 小时

### Phase 3: Testing & Verification (任务 3.1-3.3)
- 手动测试各种场景
- 集成测试完整工作流
- 验证向后兼容性
- **预期时间**：3 小时

### Phase 4: Documentation & Finalization (任务 4.1-4.2)
- 更新项目文档
- 最终验证和打包
- **预期时间**：1 小时

**总计**：约 8-9 小时

---

## ✅ 验证状态

```
✅ proposal.md         - 背景、目标、范围明确
✅ tasks.md            - 任务分解完整，可操作
✅ design.md           - 架构和实现细节完整
✅ specs/*/spec.md     - 所有需求包含 MUST/SHALL 语句和场景
✅ 提案通过严格验证    - openspec validate read-oss-from-env --strict ✓
```

---

## 🚀 后续步骤

### 1. 启动实现（开发阶段）
```bash
# 标记为 in_progress
openspec change read-oss-from-env --status in_progress

# 开发者按照 tasks.md 逐一实现任务
```

### 2. 代码审查
- 审查 `scripts/workflow.py` 修改
- 验证所有场景测试通过
- 检查文档更新

### 3. 部署和发布
```bash
# 标记为 complete 并归档
openspec archive read-oss-from-env
```

---

## 📚 相关文档

- **项目规范**：`openspec/specs/` - 已有规范 (ai-result-output, audio-transcription, evaluation-workflow)
- **项目指南**：`scripts/CLAUDE.md` - 模块级文档（将更新）
- **.env 配置**：`.env` - 当前配置文件（新增 OSS_REGION 字段说明）
- **存档提案**：`openspec/changes/archive/2025-10-18-add-funasr-integration/` - 前序 FunASR 集成

---

## 🔗 交叉引用

**本提案涉及的能力**：
- ✏️ **MODIFIED**：`evaluation-workflow` - OSS 参数处理增强
- ➕ **REFERENCES**：`audio-transcription` - FunASR 功能复用
- ➕ **REFERENCES**：`ai-result-output` - 评测规则保持不变

---

## 💬 讨论与决策

### 参数优先级（已决定）
- **选择**：命令行 > .env > 默认值
- **理由**：符合 UNIX 惯例，最大灵活性
- **备选**：.env 优先（弃用，降低灵活性）

### 凭证验证时机（已决定）
- **选择**：工作流启动的第 1.5 步
- **理由**：早期发现问题，快速失败
- **备选**：实际上传前验证（延迟验证，不如早期验证）

### 依赖选择（已决定）
- **选择**：手动解析 .env，不引入 `python-dotenv`
- **理由**：保持轻量级，避免依赖膨胀
- **备选**：引入 `python-dotenv` 库（更规范，但添加依赖）

---

## 📝 批准人签署

**提案创建者**：Claude Code (AI Assistant)
**创建时间**：2025-10-18
**提案状态**：✅ 验证通过，待实现

---

## 📌 注意事项

1. **.env 文件管理**：
   - `.env` 包含敏感信息（API密钥等），不应提交到版本控制
   - 建议创建 `.env.example` 作为模板供参考

2. **向后兼容性保证**：
   - 所有修改仅涉及 `scripts/workflow.py`，单独脚本不受影响
   - 现有 Qwen ASR 工作流完全不受影响
   - 使用完整命令行参数的脚本继续正常运行

3. **测试覆盖**：
   - tasks.md 中列出的所有场景需要手动验证
   - 建议后续补充单元测试和集成测试

4. **文档更新**：
   - 实现完成后需更新 `scripts/CLAUDE.md`
   - 补充 `.env` 配置说明和新的使用示例

---

**对此提案有任何问题？**
请查看 `proposal.md`、`design.md` 获取详细信息，或查看 `tasks.md` 了解具体实现步骤。
