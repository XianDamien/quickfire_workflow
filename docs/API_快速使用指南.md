# 配置管理 API 快速使用指南

## 1. 快速开始 (5分钟)

### 准备工作

1. **获取 JWT Token** (联系后端开发者或从管理后台获取)
2. **确认环境**: 开发环境 `https://8.159.139.145:7010`

### 方式 A: 使用 Python 脚本 (推荐)

```bash
# 1. 编辑脚本,设置你的 JWT Token
vim scripts/test_config_api.py
# 修改: JWT_TOKEN = "你的实际令牌"

# 2. 安装依赖
pip3 install requests

# 3. 运行测试
cd /Users/damien/Desktop/LanProject/quickfire_workflow
python3 scripts/test_config_api.py
```

**在脚本末尾取消注释来运行测试**:
```python
# test_workflow()  # 取消注释此行
```

### 方式 B: 使用 cURL 脚本

```bash
# 1. 设置 Token
export JWT_TOKEN="你的实际令牌"

# 2. 运行交互式测试
bash scripts/test_api_curl.sh

# 或直接命令行模式
bash scripts/test_api_curl.sh test                    # 完整测试
bash scripts/test_api_curl.sh get annotation          # 获取内容
bash scripts/test_api_curl.sh backups annotation      # 列出备份
```

### 方式 C: 直接使用 cURL 命令

```bash
# 设置变量
API_BASE="https://8.159.139.145:7010/api/v1/config"
TOKEN="你的JWT令牌"

# 获取 annotation 内容
curl -k -X GET "${API_BASE}/content/annotation" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.'

# 列出备份
curl -k -X GET "${API_BASE}/backups/annotation" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.'
```

---

## 2. 核心 API 端点

| 操作 | API 端点 | 方法 | 说明 |
|-----|---------|------|------|
| 获取内容 | `/content/{file_key}` | GET | 获取当前配置内容 |
| 更新配置 | `/update` | POST | 更新配置并自动备份 |
| 列出备份 | `/backups/{file_key}` | GET | 查看所有历史备份 |
| 恢复备份 | `/restore` | POST | 从备份恢复配置 |
| 查看差异 | `/diff/{file_key}/{backup_path}` | GET | 对比当前版本和备份 |
| 审计日志 | `/audit/{file_key}` | GET | 查看修改历史 |

**file_key** 可选值: `annotation` 或 `system_instruction`

---

## 3. 常用操作示例

### 操作 1: 查看当前 annotation 内容

**cURL**:
```bash
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/content/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.'
```

**Python**:
```python
api = ConfigAPI(API_BASE, JWT_TOKEN)
result = api.get_content("annotation")
print(result["data"]["content"])
```

### 操作 2: 更新 annotation

**cURL**:
```bash
curl -k -X POST "https://8.159.139.145:7010/api/v1/config/update" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_key": "annotation",
    "content": "题库:\n{{在此处粘贴题库 JSON}}\n\n转录:\n{{在此处粘贴学生音频转录文本}}"
  }' | jq '.'
```

**Python**:
```python
new_content = """题库:
{{在此处粘贴题库 JSON}}

转录:
{{在此处粘贴学生音频转录文本}}
"""

result = api.update_config("annotation", new_content)
print(f"更新成功,备份: {result['data']['backup_path']}")
```

### 操作 3: 查看修改历史

**cURL**:
```bash
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/audit/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.'
```

**Python**:
```python
result = api.get_audit_log("annotation")
for change in result["data"]["changes"]:
    print(f"{change['timestamp']}: {change['action']} by {change['user_id']}")
```

### 操作 4: 恢复到之前的版本

**步骤 1: 列出备份**
```bash
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/backups/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.data.backups'
```

**步骤 2: 恢复指定备份**
```bash
curl -k -X POST "https://8.159.139.145:7010/api/v1/config/restore" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_key": "annotation",
    "backup_path": "/path/to/backup.txt"
  }' | jq '.'
```

---

## 4. 在项目中集成

### 在 Gemini_annotation.py 中使用 API

**当前方式 (本地文件)**:
```python
# prompts/annotation.txt 本地文件
with open("prompts/annotation.txt") as f:
    annotation_template = f.read()
```

**推荐方式 (API 动态加载)**:
```python
import requests

def load_config_from_api(file_key: str) -> str:
    """从 API 加载最新配置"""
    url = f"https://8.159.139.145:7010/api/v1/config/content/{file_key}"
    headers = {"Authorization": f"Bearer {JWT_TOKEN}"}

    response = requests.get(url, headers=headers, verify=False)
    result = response.json()

    if result.get("success"):
        return result["data"]["content"]
    else:
        raise Exception(f"加载配置失败: {result.get('message')}")

# 使用
annotation_template = load_config_from_api("annotation")
system_instruction = load_config_from_api("system_instruction")
```

**优势**:
- ✅ 无需重启脚本即可使用最新提示词
- ✅ 支持多人协作编辑
- ✅ 自动版本控制和备份
- ✅ 可随时回滚

---

## 5. 验证规则

### annotation 配置要求

必须包含以下 2 个占位符 (大小写和空格必须完全一致):

```
{{在此处粘贴题库 JSON}}
{{在此处粘贴学生音频转录文本}}
```

**示例模板**:
```
题库:
{{在此处粘贴题库 JSON}}

学生转录:
{{在此处粘贴学生音频转录文本}}

评分说明:
1. 检查发音准确性
2. 检查语法正确性
3. 检查流利度
```

### system_instruction 配置要求

- 最少 10 个字符
- 最大 1MB

**示例**:
```
你是一个专业的英语口语评分助手。

任务:
1. 根据题库和转录内容进行评分
2. 检查发音、语法、流利度
3. 提供详细评分理由

评分标准:
- A: 优秀 (90-100分)
- B: 良好 (80-89分)
- C: 及格 (70-79分)
```

---

## 6. 常见问题

### Q: 如何获取 JWT Token?

A: 联系后端开发者 (mj) 或从管理后台获取 ADMIN 账号的 JWT token。

### Q: annotation 更新失败,提示"必须包含2个占位符"

A: 确保你的内容包含以下两个占位符:
```
{{在此处粘贴题库 JSON}}
{{在此处粘贴学生音频转录文本}}
```

### Q: SSL 证书错误

A: 开发环境使用自签名证书,需要:
- cURL: 添加 `-k` 参数
- Python requests: 添加 `verify=False`
- 浏览器: 在高级设置中信任证书

### Q: 403 权限不足

A: 确保使用的是 ADMIN 账号的 JWT token。

### Q: 如何批量更新多个配置?

A: 按顺序调用 `/update` 接口,每次更新会自动创建备份。

---

## 7. 文件说明

| 文件 | 用途 |
|-----|------|
| `scripts/test_config_api.py` | Python 测试脚本,带完整 API 客户端类 |
| `scripts/test_api_curl.sh` | Bash/cURL 测试脚本,交互式菜单 |
| `docs/API_调用流程说明.md` | 详细的流程说明和架构文档 |
| `docs/API_快速使用指南.md` | 本文档,快速上手指南 |
| `CONFIG_UPDATE_API.md` | API 完整参考文档 (由后端提供) |

---

## 8. 下一步

1. **测试连接**: 先用 `test_workflow()` 确认 API 可用
2. **查看当前配置**: 了解现有的 annotation 和 system_instruction 内容
3. **尝试更新**: 修改配置并观察备份机制
4. **集成到项目**: 在 Gemini_annotation.py 中集成 API 调用
5. **建立工作流**: 提示词调试 → API 更新 → 立即生效

---

## 9. 联系方式

- **后端 API**: mj
- **快反项目**: Damien
- **API Base URL (开发)**: https://8.159.139.145:7010/api/v1/config
- **API Base URL (生产)**: https://8.159.139.145:7008/api/v1/config (未启用)
