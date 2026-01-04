# Quickfire Workflow 项目规范

## Prompt 管理规范
- 更新 prompt 文件后，必须同步更新对应的 `metadata.json`
- metadata.json 需包含：版本号、时间戳、关键变更说明
- 版本号格式：主版本.次版本.修订版 (如 1.2.0)
- 时间戳格式：ISO 8601 (如 2026-01-04T15:30:00+08:00)

### Commit 时机
- **可直接 commit**: 小改动（描述修正、时间戳更新、纯文档性质）
- **需先测试再 commit**: prompt 内容实质改动、逻辑变更 → 跑 annotation 验证输出正确后再提交
- prompt + metadata.json 应作为一个原子 commit 一起提交
