---
name: backend-sync-notify
description: 当实验端（quickfire_workflow）验证通过某项 AI 配置变更后，创建 Linear issue 并发送邮件通知后端团队同步更新。触发场景：prompt 文件有变更、模型参数调整、ASR 配置更新等需要后端手动同步的情况。
---

# Backend Sync Notify

实验端与生产后端相互独立，配置变更不会自动同步。每次实验端验证通过改动后，通过此流程通知后端团队。

## 团队成员

| 角色 | 姓名 | Linear 用户名 | 邮箱 |
|------|------|---------------|------|
| 后端开发 | 吴明净 | mjay.lanlan2943914182 | mjay.lanlan2943914182@gmail.com |
| 前端开发 | 董楚阳 | anthonydonghikazuri | anthonydonghikazuri@gmail.com |
| 项目经理 | 郑嘉业 | xpectuer233 | zhengjiaye@126.com |
| 产品经理 | 熊扬锬 | alanyr638 | xianblack@qq.com |

Linear 配置：团队 `AI_English`，项目 `Quickfire`，API Key 在 `~/.linear/config`。

## 流程

### 1. 准备 Issues JSON

在 `docs/` 下创建 `YYYYMMDD-<topic>-issue.json`：

```json
[
  {
    "title": "后端同步更新 <模块>（<简要说明>）",
    "description": "## 背景\n\n...\n\n## 变更内容\n\n...\n\n## 需要后端做的\n\n...",
    "priority": "P1",
    "status": "Todo",
    "assignee": "mjay.lanlan2943914182",
    "labels": ["Improvement"]
  }
]
```

description 必须包含：背景、变更内容（含新配置全文）、验证结果、后端操作说明。

### 2. 创建 Linear Issue

```bash
set_proxy && python3 ~/.claude/skills/meeting-to-linear/scripts/create_linear_issues.py \
  --issues docs/YYYYMMDD-<topic>-issue.json \
  --team "AI_English" \
  --project "Quickfire" \
  --output docs/YYYYMMDD-<topic>-issue-result.json
```

### 3. 准备邮件 Issues JSON

从 result JSON 提取数据，创建 `docs/YYYYMMDD-<topic>-email-issues.json`：

```json
[
  {
    "identifier": "LAN-XXX",
    "title": "issue 标题",
    "priority": {"value": 2, "name": "High"},
    "assignee": "mjay.lanlan2943914182",
    "labels": ["Improvement"],
    "url": "https://linear.app/aienglish/issue/LAN-XXX/...",
    "status": "Todo"
  }
]
```

### 4. 发送邮件通知

```bash
set_proxy
cd ~/.claude/skills/meeting-to-linear
python3 scripts/send_linear_notification.py \
  --issues-json /path/to/docs/YYYYMMDD-<topic>-email-issues.json \
  --date "YYYY-MM-DD" \
  --topic "<变更主题>" \
  --to anthonydonghikazuri@gmail.com \
  --to mjay.lanlan2943914182@gmail.com \
  --to zhengjiaye@126.com \
  --to xianblack@qq.com
```

必须 cd 到脚本目录再执行，否则相对路径报错。禁止使用 MCP 工具。

## 常见变更场景

| 变更类型 | 文件位置 | 后端对应位置 |
|----------|----------|-------------|
| ASR context prompt | `prompts/asr_context/system.md` | DashScope API 的 system message |
| Annotation prompt | `prompts/annotation/system.md` | LLM 标注调用的 system prompt |
| Gatekeeper prompt | `prompts/asr_gatekeeper/system.md` | ASR 质检服务的 prompt |
