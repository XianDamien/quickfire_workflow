# NocoDB 题库管理

远程管理 NocoDB 上的题库（questionbank）记录。使用统一脚本 `scripts/nocodb_questionbank.py`。

## 前置条件

- `~/.nocodb/config` 已配置（NOCODB_BASE_URL + NOCODB_TOKEN）
- 依赖: `~/.claude/skills/nocodb-manager/scripts/nocodb_api.py`

## 可用操作

根据用户意图选择对应子命令：

### 1. 上传题库 JSON → NocoDB

将 `questionbank/` 目录下的 JSON 文件批量上传（已有记录更新、新记录创建）：

```bash
python3 scripts/nocodb_questionbank.py upload --dir questionbank --dry-run
python3 scripts/nocodb_questionbank.py upload --dir questionbank
```

- 先用 `--dry-run` 预览变更，确认后去掉 `--dry-run` 执行
- 默认目录: `questionbank/`，可用 `--dir` 指定其他路径

### 2. 批量更新记录字段

规范化 `questionbank_name`（去 .json 后缀、R1→V1/R3→V3）并设置 `type=单词快反`：

```bash
python3 scripts/nocodb_questionbank.py update --dry-run
python3 scripts/nocodb_questionbank.py update
```

### 3. 列出题库记录

```bash
python3 scripts/nocodb_questionbank.py list --limit 50
```

## 执行流程

1. **始终先 `--dry-run`**，确认操作范围
2. 展示 dry-run 输出给用户
3. 用户确认后执行实际操作
4. 汇报执行结果

## 表配置

- Table ID: `mcd5tmx0nqsgd3a`（默认）
- 字段: `questionbank_name`, `questionbank_json`, `type`
- 可用 `--table-id` 覆盖默认表
