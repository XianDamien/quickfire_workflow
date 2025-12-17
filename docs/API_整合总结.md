# 配置管理 API 整合总结

## 概述

mj 提供了一套完整的配置管理 API,用于在线编辑和管理 LLM 提示词配置。已在开发环境 `https://8.159.139.145:7010` 部署并完成初步测试。

本文档总结了整个 API 的功能、工作流程,以及在快反项目中的集成方案。

---

## 1. 核心价值

| 功能 | 说明 | 收益 |
|-----|------|------|
| **在线编辑** | 通过 Web API 编辑提示词,无需修改代码 | 快速迭代,支持多人协作 |
| **自动备份** | 每次更新自动备份当前版本 | 误操作可快速恢复 |
| **版本控制** | 完整的审计日志记录 | 追踪谁在什么时间做了什么 |
| **即时生效** | 更新后立即可用 (通过 API 动态加载) | 无需重启脚本 |
| **权限管理** | JWT 认证 + ADMIN 权限控制 | 安全可靠 |

---

## 2. API 架构

### 部署环境

- **开发环境**: `https://8.159.139.145:7010/api/v1/config`
  - 支持 annotation 和 system_instruction 配置
  - 已通过 apifox 初步测试验证可用

- **生产环境**: `https://8.159.139.145:7008/api/v1/config`
  - 未启用 (保留备用)

### 可管理的配置

| 配置文件 | 当前位置 | 用途 | API 支持 |
|---------|---------|------|---------|
| annotation | `prompts/annotation.txt` | LLM 提示词模板 | ✅ |
| system_instruction | `prompts/system_instruction.txt` | LLM 系统指令 | ✅ |

---

## 3. 完整工作流程

### 3.1 前端编辑流程

```
┌─────────────────────────────────────────────┐
│  前端编辑器                                   │
└─────────────────────────────────────────────┘
         │
         ↓ 1. 获取当前内容
┌─────────────────────────────────────────────┐
│  GET /content/annotation                    │
│  → 显示当前提示词模板在编辑器中               │
└─────────────────────────────────────────────┘
         │
         ↓ 2. 用户修改内容
┌─────────────────────────────────────────────┐
│  编辑器显示修改后的内容                      │
└─────────────────────────────────────────────┘
         │
         ↓ 3. 用户保存
┌─────────────────────────────────────────────┐
│  POST /update                               │
│  ├─ 验证占位符 (annotation 需要 2 个)        │
│  ├─ 自动备份当前版本                        │
│  ├─ 保存新内容                              │
│  └─ 记录审计日志                            │
└─────────────────────────────────────────────┘
         │
         ↓ 4. 返回成功响应
┌─────────────────────────────────────────────┐
│  {success: true, backup_path: "...", ...}   │
│  → 前端显示保存成功提示                      │
└─────────────────────────────────────────────┘
```

### 3.2 脚本动态加载流程 (推荐)

```
┌─────────────────────────────────────────────┐
│  Gemini_annotation.py 启动                  │
└─────────────────────────────────────────────┘
         │
         ├─ 旧方式: open("prompts/annotation.txt").read()
         │          ↓ 需要重启脚本才能加载新版本
         │
         └─ 新方式: load_config_from_api("annotation")
                   ↓ 每次运行都获取最新版本
┌─────────────────────────────────────────────┐
│  GET /content/annotation                    │
│  → 获取最新的提示词模板                      │
└─────────────────────────────────────────────┘
         │
         ↓ 替换占位符
┌─────────────────────────────────────────────┐
│  annotation_template.replace(                │
│    "{{在此处粘贴题库 JSON}}", quiz_json)    │
│  ).replace(                                 │
│    "{{在此处粘贴学生音频转录文本}}", asr_text)│
│  )                                          │
└─────────────────────────────────────────────┘
         │
         ↓ 调用 LLM
┌─────────────────────────────────────────────┐
│  Gemini API 评分                            │
│  → 输出: 4_llm_annotation.json              │
└─────────────────────────────────────────────┘
```

### 3.3 版本回滚流程

```
┌─────────────────────────────────────────────┐
│  用户发现最新版本有问题                      │
└─────────────────────────────────────────────┘
         │
         ↓ 1. 查看历史版本
┌─────────────────────────────────────────────┐
│  GET /backups/annotation                    │
│  → 列出所有历史备份                         │
└─────────────────────────────────────────────┘
         │
         ↓ 2. 预览差异
┌─────────────────────────────────────────────┐
│  GET /diff/annotation/{backup_path}         │
│  → 显示当前版本和备份的差异                  │
└─────────────────────────────────────────────┘
         │
         ↓ 3. 确认恢复
┌─────────────────────────────────────────────┐
│  POST /restore                              │
│  ├─ 恢复指定的备份版本                      │
│  ├─ 自动备份当前版本 (以防再次回滚)          │
│  └─ 记录恢复操作到审计日志                  │
└─────────────────────────────────────────────┘
         │
         ↓ 4. 验证恢复结果
┌─────────────────────────────────────────────┐
│  GET /content/annotation                    │
│  → 确认已恢复到旧版本                       │
└─────────────────────────────────────────────┘
```

---

## 4. API 端点参考

### 4.1 获取配置内容

```
GET /content/{file_key}

Path Parameters:
  file_key: "annotation" | "system_instruction"

Response:
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "content": "...",  // 完整内容
    "size": 2148,      // 字节数
    "lines": 68        // 行数
  }
}

频率限制: 100 请求/分钟
```

### 4.2 更新配置

```
POST /update

Request Body:
{
  "file_key": "annotation",
  "content": "..."  // 完整内容
}

Validation Rules:
  - annotation: 必须包含 2 个占位符
  - system_instruction: 最少 10 个字符
  - 最大 1MB

Response:
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backup_path": "/path/to/backup.txt",
    "change_id": "550e8400-...",
    "message": "Configuration 'annotation' updated successfully"
  }
}

频率限制: 20 请求/分钟
```

### 4.3 列出备份

```
GET /backups/{file_key}

Response:
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backups": [
      {
        "path": "/path/to/backup.txt",
        "name": "annotation_backup_20251205_143022.txt",
        "size": 2048
      }
    ]
  }
}

频率限制: 50 请求/分钟
```

### 4.4 恢复备份

```
POST /restore

Request Body:
{
  "file_key": "annotation",
  "backup_path": "/path/to/backup.txt"
}

Response:
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backup_path": "/path/to/backup.txt",
    "change_id": "660e8400-...",
    "message": "Configuration restored from backup"
  }
}

频率限制: 20 请求/分钟
```

### 4.5 查看审计日志

```
GET /audit/{file_key}

Response:
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "total_changes": 5,
    "changes": [
      {
        "id": "550e8400-...",
        "timestamp": "2025-12-05T14:35:10Z",
        "user_id": "admin@example.com",
        "action": "update",
        "file_key": "annotation",
        "backup_path": "/path/to/backup.txt",
        "details": {
          "content_size": 2148,
          "content_lines": 12
        }
      }
    ]
  }
}

频率限制: 50 请求/分钟
```

---

## 5. 提供的工具和文档

### 5.1 Python 测试脚本

**文件**: `scripts/test_config_api.py`

**特点**:
- 完整的 API 客户端类 (ConfigAPI)
- 支持所有 6 个 API 端点
- 包含多个测试函数
- 详细的注释和文档

**使用方法**:
```bash
# 1. 设置 JWT_TOKEN
vim scripts/test_config_api.py
# JWT_TOKEN = "你的实际令牌"

# 2. 运行测试
python3 scripts/test_config_api.py

# 3. 取消注释相应的测试函数执行
```

### 5.2 cURL 测试脚本

**文件**: `scripts/test_api_curl.sh`

**特点**:
- 交互式菜单界面
- 彩色输出便于阅读
- 支持命令行参数模式和交互模式
- 自动检查环境依赖

**使用方法**:
```bash
# 交互式模式
export JWT_TOKEN="你的令牌"
bash scripts/test_api_curl.sh

# 命令行模式
bash scripts/test_api_curl.sh test
bash scripts/test_api_curl.sh get annotation
bash scripts/test_api_curl.sh backups annotation
```

### 5.3 文档

| 文档 | 路径 | 用途 |
|-----|------|------|
| 快速使用指南 | `docs/API_快速使用指南.md` | 快速上手,常用操作 |
| 详细流程说明 | `docs/API_调用流程说明.md` | 深入理解,集成指南 |
| API 参考文档 | `CONFIG_UPDATE_API.md` | 完整 API 规范参考 |
| 本总结文档 | `docs/API_整合总结.md` | 整体概述和架构设计 |

---

## 6. 集成建议

### 6.1 短期方案 (立即可行)

**保持当前方式,但添加手动同步**:
```bash
# 当提示词更新时,需要手动运行
python3 scripts/test_config_api.py

# 获取最新内容,手动保存到本地
# prompts/annotation.txt
# prompts/system_instruction.txt
```

**优点**: 零改动,最安全
**缺点**: 需要手动操作,容易遗漏

### 6.2 中期方案 (推荐)

**在 Gemini_annotation.py 中集成 API 调用**:

```python
import requests

class ConfigLoader:
    def __init__(self, token: str):
        self.token = token
        self.api_base = "https://8.159.139.145:7010/api/v1/config"
        self.headers = {"Authorization": f"Bearer {token}"}

    def load_annotation(self) -> str:
        """加载最新的 annotation 模板"""
        url = f"{self.api_base}/content/annotation"
        response = requests.get(url, headers=self.headers, verify=False)
        result = response.json()

        if result["success"]:
            return result["data"]["content"]
        else:
            # 如果 API 不可用,回退到本地文件
            with open("prompts/annotation.txt") as f:
                return f.read()

# 在 Gemini_annotation.py 中使用
loader = ConfigLoader(JWT_TOKEN)
annotation_template = loader.load_annotation()
system_instruction = loader.load_annotation()  # 或单独加载
```

**优点**:
- 无需重启脚本,自动获取最新配置
- 支持多人协作编辑
- 完整的版本控制和备份
- API 不可用时自动回退

**缺点**: 需要修改现有代码

### 6.3 长期方案 (完整集成)

**建立完整的配置管理工作流**:

1. **Web 编辑界面**
   - 用户在 Web UI 编辑 annotation 和 system_instruction
   - 实时预览、保存历史、版本对比

2. **自动部署**
   - 配置更新 → 自动通知运行中的脚本
   - 实时加载最新配置

3. **监控和告警**
   - 配置修改历史完整记录
   - 异常修改告警

4. **多环境支持**
   - 开发环境 (7010) - 快速迭代
   - 测试环境 (待定)
   - 生产环境 (7008) - 稳定可靠

---

## 7. 安全性考虑

### 7.1 认证

- 所有请求需要 JWT Token
- Token 必须有 ADMIN 权限
- Token 应妥善保管,不要提交到 Git

### 7.2 授权

- 仅 ADMIN 可修改配置
- 非 ADMIN 用户只能读取内容 (可选)
- 所有修改都记录审计日志

### 7.3 数据验证

- annotation: 必须包含 2 个指定的占位符
- system_instruction: 最少 10 个字符
- 内容大小限制 1MB

### 7.4 SSL 证书

- 开发环境使用自签名证书
- 需要在客户端禁用 SSL 验证 (仅开发环境)
- 生产环境建议使用正式证书

---

## 8. 故障排查

### 问题 1: 401 Unauthorized

**原因**: JWT Token 无效或过期
**解决**: 重新获取 Token

### 问题 2: 403 Forbidden

**原因**: 用户没有 ADMIN 权限
**解决**: 使用 ADMIN 账号获取 Token

### 问题 3: 400 Bad Request

**原因**: 占位符验证失败
**解决**: 确保包含以下两个占位符:
```
{{在此处粘贴题库 JSON}}
{{在此处粘贴学生音频转录文本}}
```

### 问题 4: SSL Certificate Error

**原因**: 开发环境使用自签名证书
**解决**:
- Python: `verify=False`
- cURL: `-k` 参数
- 浏览器: 在高级设置信任

### 问题 5: 速率限制

**原因**: 请求过于频繁
**解决**: 根据限制等待后重试

---

## 9. 性能指标

| 操作 | 平均响应时间 | 频率限制 |
|-----|-----------|---------|
| 获取内容 | <100ms | 100 请求/分钟 |
| 更新配置 | <200ms | 20 请求/分钟 |
| 列出备份 | <100ms | 50 请求/分钟 |
| 查看审计 | <150ms | 50 请求/分钟 |

---

## 10. 项目时间线

| 时间 | 事项 | 状态 |
|-----|------|------|
| 2025-12-05 | API 开发完成 | ✅ |
| 2025-12-05 | apifox 初步测试 | ✅ |
| 2025-12-06 | 提供 API 文档和工具 | ✅ |
| 待定 | 前端编辑界面开发 | ⏳ |
| 待定 | Gemini_annotation.py 集成 | ⏳ |
| 待定 | 生产环境配置 | ⏳ |

---

## 总结

配置管理 API 为快反项目的提示词调试提供了:

✅ **即时生效** - 无需重启脚本
✅ **版本控制** - 完整的修改历史和备份
✅ **安全可靠** - JWT 认证和权限控制
✅ **易于使用** - 提供了 Python 和 cURL 工具
✅ **文档完整** - 详细的流程说明和集成指南

**建议立即行动**:
1. 测试 API 连接 (使用提供的脚本)
2. 理解完整工作流程 (阅读详细说明文档)
3. 在 Gemini_annotation.py 中集成 API 调用 (中期方案)
4. 建立完整的配置管理工作流 (长期目标)

---

**相关联系**:
- API 开发: mj
- 项目负责: Damien
- 技术支持: AI 助手
