# Tasks: 从 .env 读取 OSS 配置 (read-oss-from-env)

## Task Breakdown

### Phase 1: Core Infrastructure (2-3 tasks)

#### Task 1.1: 实现 .env 配置读取函数
- 在 `scripts/workflow.py` 中新增 `load_env_config()` 函数
- 读取 `.env` 文件中的 OSS 相关配置：`OSS_BUCKET_NAME`、`OSS_ENDPOINT`、`OSS_ACCESS_KEY_*`
- 返回配置字典：`{"bucket": "...", "region": "...", "endpoint": "..."}`
- 若 .env 不存在，返回空字典（不中断流程）
- **验证方式**：单元测试或手动测试

#### Task 1.2: 实现 OSS 凭证验证函数
- 在 `scripts/workflow.py` 中新增 `verify_oss_credentials()` 函数
- 接收 OSS 参数（region、bucket、endpoint）和凭证
- 尝试创建 OSS 客户端连接或执行轻量级测试操作（如 head_bucket）
- 返回验证结果（成功/失败）和错误信息
- 若验证失败，提供具体的故障排查建议
- **验证方式**：集成测试，实际连接 OSS

#### Task 1.3: 参数优先级处理
- 修改 `main()` 函数中的参数解析逻辑
- 实现优先级规则：`命令行参数 > .env 配置 > 默认值`
- 对于 FunASR 模式，若最终参数缺失则报错并退出
- 记录日志显示每个参数的来源（"来自命令行" 或 "来自 .env"）
- **验证方式**：手动测试各种参数组合

---

### Phase 2: Integration & Validation (2-3 tasks)

#### Task 2.1: 集成凭证验证到工作流启动阶段
- 修改 `run_workflow()` 函数，在第 1 步（验证输入参数）后添加凭证验证步骤
- 当 FunASR 模式且凭证验证失败时，立即输出错误提示并返回
- 验证成功时输出确认信息（如 "✅ OSS 凭证验证通过"）
- **验证方式**：集成测试，完整工作流运行

#### Task 2.2: 增强错误提示和日志
- 优化错误消息，提供具体的故障排查建议
- 在启动工作流时输出清晰的配置来源标识
- 例如输出：
  ```
  ✓ 第1步：验证输入参数...
    OSS 配置来源: .env 文件
    - Region: cn-shanghai (来自 .env)
    - Bucket: quickfire-audio (来自 .env)
  ✓ 验证 OSS 凭证...
    ✅ OSS 凭证验证通过
  ```
- **验证方式**：手动观察输出

#### Task 2.3: 命令行帮助和示例更新
- 更新 `argparse` 的帮助文本，说明 OSS 参数来源优先级
- 在 epilog 中添加新的使用示例，展示自动加载 .env 的行为
- 更新项目 CLAUDE.md，记录新的工作流执行方式
- **验证方式**：运行 `python3 workflow.py --help`，检查帮助文本

---

### Phase 3: Testing & Verification (2-3 tasks)

#### Task 3.1: 手动测试场景覆盖
- **场景 1**：.env 存在 OSS 配置，不传命令行参数 → 从 .env 读取
- **场景 2**：.env 存在，但通过 `--oss-region` 覆盖 → 使用命令行值
- **场景 3**：.env 不存在，必须提供命令行参数 → 使用命令行值
- **场景 4**：FunASR 模式，OSS 参数缺失 → 报错并退出
- **场景 5**：Qwen ASR 模式 → 不验证 OSS，工作流正常执行
- **验证方式**：逐一手动测试，记录结果

#### Task 3.2: 集成测试 - 完整工作流
- 使用实际音频文件和题库，运行完整工作流
- 验证从 .env 读取配置后，整个转写 → 评测 → 输出流程正常
- 检查最终报告格式和内容
- **验证方式**：执行 `python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv --asr-engine funasr` 并验证输出

#### Task 3.3: 向后兼容性验证
- 验证现有的 Qwen ASR 工作流无中断
- 验证通过完整命令行参数指定所有值仍可正常运行
- 验证单独运行 `qwen3.py`、`captioner_qwen3.py` 仍可用
- **验证方式**：运行现有测试脚本和命令

---

### Phase 4: Documentation & Finalization (1-2 tasks)

#### Task 4.1: 更新项目文档
- 更新 `scripts/CLAUDE.md`，补充 FunASR 模式的 .env 配置说明
- 更新 `openspec/changes/read-oss-from-env/IMPLEMENTATION.md`（如需要）
- 记录参数优先级规则
- 提供故障排查指南
- **验证方式**：文档审查

#### Task 4.2: 总结和交接
- 运行 `openspec validate read-oss-from-env --strict` 验证提案一致性
- 准备提案演讲/演示材料
- 打包最终代码和文档
- **验证方式**：openspec 命令行工具

---

## Task Dependencies

```
Task 1.1 (读取.env)
Task 1.2 (验证凭证) ──→ Task 2.1 (集成到工作流)
Task 1.3 (参数优先级) ──→ Task 2.1 & Task 2.2 (增强日志)
                    ↓
                Task 2.3 (更新帮助文本)
                    ↓
                Task 3.x (测试)
                    ↓
                Task 4.x (文档)
```

## Parallelizable Tasks

- Task 1.1、Task 1.2、Task 1.3 可并行实现（各自独立）
- Task 2.2、Task 2.3 可并行准备（等待 Task 2.1 完成）
- Task 3.1、Task 3.2、Task 3.3 需顺序执行（各自验证不同场景）

## Estimated Effort

| 任务 | 难度 | 预期时间 |
|------|------|----------|
| Task 1.1 | 简单 | 30 分钟 |
| Task 1.2 | 中等 | 1 小时 |
| Task 1.3 | 中等 | 1 小时 |
| Task 2.1 | 中等 | 45 分钟 |
| Task 2.2 | 简单 | 30 分钟 |
| Task 2.3 | 简单 | 30 分钟 |
| Task 3.1 | 简单 | 1 小时 |
| Task 3.2 | 中等 | 1.5 小时 |
| Task 3.3 | 简单 | 1 小时 |
| Task 4.1 | 简单 | 30 分钟 |
| Task 4.2 | 简单 | 30 分钟 |
| **总计** | - | **~8-9 小时** |

## Acceptance Criteria

- [x] 所有任务完成且通过验证
  - [x] Task 1.1: load_env_config() 函数实现完成
  - [x] Task 1.2: verify_oss_credentials() 函数实现完成
  - [x] Task 1.3: 参数优先级处理逻辑实现完成
  - [x] Task 2.1: 凭证验证集成到 run_workflow() 完成
  - [x] Task 2.2: 增强错误提示和日志输出完成
  - [x] Task 2.3: 更新命令行帮助文本和示例完成
  - [x] Task 3.1-3.3: 手动测试和向后兼容性验证通过
  - [x] Task 4.1: 更新项目文档完成
  - [x] Task 4.2: OpenSpec 验证通过
- [x] `openspec validate read-oss-from-env --strict` 无错误
- [x] 完整工作流测试通过（Qwen 和 FunASR 两种模式）
- [x] 文档完整且清晰
- [x] 无向后兼容性破坏

## Implementation Summary

### 核心实现

1. **load_env_config()** (workflow.py:147-190)
   - 从 .env 文件读取 OSS 配置参数
   - 支持 OSS_BUCKET_NAME、OSS_REGION、OSS_ENDPOINT
   - 优雅处理文件不存在的情况

2. **verify_oss_credentials()** (workflow.py:193-256)
   - 验证 OSS 凭证有效性
   - 使用 head_bucket 进行轻量级测试
   - 提供详细的诊断建议

3. **main() 参数优先级处理** (workflow.py:453-586)
   - 实现优先级：命令行参数 > .env 配置 > 默认值
   - 参数缺失时提供清晰的错误提示
   - 显示参数来源信息

4. **run_workflow() 凭证验证** (workflow.py:313-319)
   - 在 FunASR 模式第 1.5 步进行凭证验证
   - 验证失败时立即退出

### 文档更新

- `scripts/CLAUDE.md`: 添加 .env 配置说明、参数优先级、故障排除指南
- `.env`: 添加 OSS_REGION=cn-shanghai 配置

### 测试结果

✅ 场景 1：.env 存在，自动读取 OSS 配置
✅ 场景 2：命令行参数正确覆盖 .env 配置
✅ 场景 3：.env 不存在返回空字典
✅ 场景 4：参数缺失时显示清晰错误提示
✅ 场景 5：Qwen ASR 模式不受影响
✅ OpenSpec 一致性验证通过
