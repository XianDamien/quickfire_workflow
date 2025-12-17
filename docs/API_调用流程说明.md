# 配置管理 API 调用流程说明

## 概述

这套 API 用于管理 LLM 提示词配置,支持 **annotation** 和 **system_instruction** 两个配置文件的在线编辑、版本控制和审计。

## 环境信息

- **开发环境 Base URL**: `https://8.159.139.145:7010/api/v1/config`
- **生产环境 Base URL**: `https://8.159.139.145:7008/api/v1/config` (未启用)
- **认证方式**: JWT Token (需要 ADMIN 权限)
- **协议**: HTTPS (使用自签名证书,需要禁用 SSL 验证)

## 核心概念

### 1. 两个可管理的配置文件

| 配置文件 | 用途 | 验证规则 |
|---------|------|---------|
| `annotation` | LLM 提示词模板 | 必须包含 2 个占位符 |
| `system_instruction` | LLM 系统指令 | 最少 10 个字符 |

### 2. 占位符说明 (annotation 专用)

annotation 配置必须包含以下 2 个占位符:

```
{{在此处粘贴题库 JSON}}
{{在此处粘贴学生音频转录文本}}
```

这些占位符在实际使用时会被替换为:
- 题库内容 (从 questionbank 加载的 JSON)
- 学生音频的 ASR 转录结果

### 3. 自动备份机制

每次更新配置时,系统会:
1. 自动创建当前版本的备份文件
2. 备份文件命名格式: `{file_key}_backup_YYYYMMDD_HHMMSS.txt`
3. 记录操作到审计日志 (包括操作者、时间、变更 ID)

---

## 完整工作流程

### 场景 1: 前端编辑器流程

这是最常见的使用场景,用户通过网页编辑器修改提示词。

```
┌─────────────────────────────────────────────────────────┐
│  1. 用户打开编辑器页面                                      │
│     ↓                                                    │
│  2. 前端调用 GET /content/annotation                      │
│     ↓                                                    │
│  3. 显示当前内容在编辑器中                                  │
│     ↓                                                    │
│  4. 用户修改内容                                           │
│     ↓                                                    │
│  5. 用户点击保存                                           │
│     ↓                                                    │
│  6. 前端调用 POST /update                                 │
│     ↓                                                    │
│  7. 后端自动备份 + 更新文件 + 记录审计日志                   │
│     ↓                                                    │
│  8. 返回成功响应 (包含备份路径和 change_id)                 │
│     ↓                                                    │
│  9. 前端显示保存成功提示                                    │
└─────────────────────────────────────────────────────────┘
```

#### 前端代码示例

```javascript
const API_BASE = 'https://8.159.139.145:7010/api/v1/config';
const token = localStorage.getItem('jwt_token');

// 1. 加载配置内容
async function loadConfig(fileKey) {
  const response = await fetch(`${API_BASE}/content/${fileKey}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const result = await response.json();
  if (result.success) {
    // 显示在编辑器中
    document.getElementById('editor').value = result.data.content;
    console.log(`加载成功: ${result.data.lines} 行`);
  }
}

// 2. 保存配置
async function saveConfig(fileKey) {
  const newContent = document.getElementById('editor').value;

  const response = await fetch(`${API_BASE}/update`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      file_key: fileKey,
      content: newContent
    })
  });

  const result = await response.json();
  if (result.success) {
    alert('保存成功!');
    console.log('备份:', result.data.backup_path);
  }
}
```

---

### 场景 2: 查看修改历史

用户可以查看所有历史修改记录。

```
┌─────────────────────────────────────────────────────────┐
│  1. 用户点击"查看历史"按钮                                   │
│     ↓                                                    │
│  2. 前端调用 GET /audit/annotation                        │
│     ↓                                                    │
│  3. 返回所有修改记录 (时间、操作者、变更ID)                   │
│     ↓                                                    │
│  4. 前端显示修改历史列表                                    │
└─────────────────────────────────────────────────────────┘
```

#### API 响应示例

```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "total_changes": 5,
    "changes": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-12-05T14:35:10Z",
        "user_id": "admin@example.com",
        "action": "update",
        "file_key": "annotation",
        "backup_path": "/data/llm/backups/annotation_backup_20251205_143510.txt"
      }
    ]
  }
}
```

---

### 场景 3: 版本回滚

用户发现最新版本有问题,需要恢复到之前的版本。

```
┌─────────────────────────────────────────────────────────┐
│  1. 用户点击"查看备份"按钮                                   │
│     ↓                                                    │
│  2. 前端调用 GET /backups/annotation                      │
│     ↓                                                    │
│  3. 显示所有备份文件列表                                    │
│     ↓                                                    │
│  4. 用户选择某个备份,点击"预览差异"                          │
│     ↓                                                    │
│  5. 前端调用 GET /diff/annotation/{backup_path}           │
│     ↓                                                    │
│  6. 显示当前版本和备份的差异对比                             │
│     ↓                                                    │
│  7. 用户确认后点击"恢复"                                    │
│     ↓                                                    │
│  8. 前端调用 POST /restore                                │
│     ↓                                                    │
│  9. 后端恢复备份 + 自动备份当前版本 + 记录审计日志            │
│     ↓                                                    │
│ 10. 返回成功响应                                           │
│     ↓                                                    │
│ 11. 前端刷新编辑器内容                                      │
└─────────────────────────────────────────────────────────┘
```

#### 前端代码示例

```javascript
// 1. 列出所有备份
async function listBackups(fileKey) {
  const response = await fetch(`${API_BASE}/backups/${fileKey}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const result = await response.json();
  return result.data.backups;
}

// 2. 恢复备份
async function restoreBackup(fileKey, backupPath) {
  const response = await fetch(`${API_BASE}/restore`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      file_key: fileKey,
      backup_path: backupPath
    })
  });

  const result = await response.json();
  if (result.success) {
    alert('恢复成功!');
    await loadConfig(fileKey); // 重新加载内容
  }
}
```

---

## 在本地项目中的应用

### 当前项目集成流程

```
┌──────────────────────────────────────────────────────────────┐
│                    快反项目完整流程                             │
└──────────────────────────────────────────────────────────────┘

1. 【音频处理】qwen_asr.py
   ├─ 输入: 学生提交的音频/视频文件
   ├─ 处理: Qwen ASR 转录音频
   └─ 输出: asr/{student_name}/2_qwen_asr.json

2. 【提示词配置】通过 API 管理
   ├─ annotation (提示词模板)
   │  └─ 包含占位符: {{题库 JSON}} + {{转录文本}}
   └─ system_instruction (系统指令)
      └─ 定义 LLM 的角色和评分标准

3. 【LLM 评分】Gemini_annotation.py
   ├─ 加载: 题库 JSON (从 questionbank/)
   ├─ 加载: ASR 转录结果
   ├─ 加载: annotation 模板 (通过 API 获取或从本地文件)
   ├─ 替换: 占位符 → 实际内容
   ├─ 调用: Google Gemini API 进行评分
   └─ 输出: asr/{student_name}/4_llm_annotation.json

4. 【批量报告】
   └─ 输出: batch_annotation_report.json
```

### API 在项目中的作用

当前项目有两种运行模式:

#### 模式 A: 本地文件模式 (当前使用)

```python
# Gemini_annotation.py 中
annotation_template = open("prompts/annotation.txt").read()
system_instruction = open("prompts/system_instruction.txt").read()
```

#### 模式 B: API 动态加载模式 (推荐)

```python
import requests

def load_config_from_api(file_key: str, token: str) -> str:
    """从 API 加载最新的配置"""
    url = f"https://8.159.139.145:7010/api/v1/config/content/{file_key}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, verify=False)
    result = response.json()
    return result["data"]["content"]

# 使用 API 加载
annotation_template = load_config_from_api("annotation", JWT_TOKEN)
system_instruction = load_config_from_api("system_instruction", JWT_TOKEN)
```

**优势**:
- 无需重启脚本即可使用最新的提示词
- 支持多人协作编辑
- 自动记录修改历史
- 可以随时回滚到之前的版本

---

## 测试步骤

### 1. 设置 JWT Token

编辑 `scripts/test_config_api.py`:

```python
JWT_TOKEN = "你的实际JWT令牌"
```

### 2. 运行测试

```bash
cd /Users/damien/Desktop/LanProject/quickfire_workflow
python3 scripts/test_config_api.py
```

### 3. 测试各个功能

在脚本末尾取消注释:

```python
# 测试完整工作流
test_workflow()

# 或单独测试 annotation 更新
test_annotation_update()

# 或单独测试 system_instruction 更新
test_system_instruction_update()
```

---

## API 端点总览

| 端点 | 方法 | 用途 | 频率限制 |
|-----|------|------|---------|
| `/content/{file_key}` | GET | 获取配置内容 | 100/分钟 |
| `/update` | POST | 更新配置 | 20/分钟 |
| `/backups/{file_key}` | GET | 列出备份 | 50/分钟 |
| `/restore` | POST | 恢复备份 | 20/分钟 |
| `/diff/{file_key}/{backup_path}` | GET | 对比差异 | 50/分钟 |
| `/audit/{file_key}` | GET | 查看审计日志 | 50/分钟 |

---

## 常见问题

### Q1: annotation 更新失败,提示"必须包含2个占位符"

**原因**: annotation 模板必须包含以下两个占位符:
```
{{在此处粘贴题库 JSON}}
{{在此处粘贴学生音频转录文本}}
```

**解决**: 确保你的内容包含这两个占位符 (大小写和空格必须完全一致)

### Q2: SSL 证书错误

**原因**: 开发环境使用自签名证书

**解决**:
```python
# Python
requests.get(url, verify=False)

# JavaScript (浏览器会自动处理,或在高级设置中信任证书)
```

### Q3: 403 权限不足

**原因**: 当前用户没有 ADMIN 权限

**解决**: 使用 ADMIN 账号获取 JWT token

### Q4: 如何在 Gemini_annotation.py 中集成 API?

参考上面"模式 B: API 动态加载模式"的示例代码,或者保持当前的本地文件模式。

---

## 总结

这套 API 提供了完整的提示词配置管理能力:

1. **在线编辑**: 无需修改代码文件,通过 API 即时更新
2. **版本控制**: 自动备份每次修改,支持回滚
3. **审计追踪**: 记录谁在什么时间做了什么修改
4. **安全验证**: JWT 认证 + ADMIN 权限控制
5. **内容验证**: 自动检查占位符和格式要求

建议将 `Gemini_annotation.py` 集成 API 调用,实现提示词的动态加载和热更新。
