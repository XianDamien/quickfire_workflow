# 配置管理 API

**Base URL**: `http://localhost:8000/api/v1/config`

**认证**: 所有请求需要 JWT token: `Authorization: Bearer <token>`

**权限**: 仅 ADMIN 可操作

**支持的文件**:
- `annotation` - LLM提示词模板（必须包含2个占位符）
- `system_instruction` - LLM系统指令（最少10个字符）

---

## API 端点

### 0. 获取配置内容

```
GET /content/{file_key}
```

**用途**: 获取当前annotation或system_instruction的完整内容

**路径参数**:
- `file_key`: `annotation` | `system_instruction`

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "content": "...",
    "size": 1529,
    "lines": 68
  },
  "message": "Configuration content retrieved successfully"
}
```

---

### 1. 更新配置

```
POST /update
```

**请求示例 - annotation**:
```json
{
  "file_key": "annotation",
  "content": "题库:\n{{在此处粘贴题库 JSON}}\n转录:\n{{在此处粘贴学生音频转录文本}}"
}
```

**请求示例 - system_instruction**:
```json
{
  "file_key": "system_instruction",
  "content": "你是一个精通数据处理的AI助手。请按照以下规则处理请求..."
}
```

**参数要求**:
- `file_key`: `annotation` | `system_instruction`
- `content`: 文件内容
  - **annotation**: 必须包含2个占位符，最大1MB
  - **system_instruction**: 最少10个字符，最大1MB

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backup_path": "/path/to/backup.txt",
    "change_id": "550e8400-...",
    "message": "Configuration 'annotation' updated successfully"
  },
  "message": "Configuration updated with backup"
}
```

---

### 2. 恢复备份

```
POST /restore
```

**请求**:
```json
{
  "file_key": "annotation",
  "backup_path": "/path/to/data/llm/backups/annotation_backup_20251205_143022.txt"
}
```

备注: file_key 也支持 `system_instruction`

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backup_path": "/path/to/backup.txt",
    "change_id": "660e8400-...",
    "message": "Configuration restored from backup"
  },
  "message": "Configuration restored successfully"
}
```

---

### 3. 列出备份

```
GET /backups/{file_key}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "backups": [
      {
        "path": "/path/to/data/llm/backups/annotation_backup_20251205_143022.txt",
        "name": "annotation_backup_20251205_143022.txt",
        "size": 2048
      }
    ],
    "message": "Found 3 backups"
  },
  "message": "Backups retrieved successfully"
}
```

---

### 4. 对比差异

```
GET /diff/{file_key}/{backup_path}
```

**注意**: 需要 URL 编码 backup_path

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "current": {
      "size": 2148,
      "lines": 12,
      "last_modified": "2025-12-05T14:35:10Z"
    },
    "backup": {
      "size": 2048,
      "lines": 11,
      "last_modified": "2025-12-05T14:30:22Z"
    },
    "changed": true
  },
  "message": "Diff retrieved successfully"
}
```

---

### 5. 获取审计日志

```
GET /audit/{file_key}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "file_key": "annotation",
    "total_changes": 5,
    "changes": [
      {
        "id": "550e8400-...",
        "timestamp": "2025-12-05T14:35:10Z",
        "user_id": "admin_user",
        "action": "update",
        "file_key": "annotation",
        "backup_path": "/path/to/backup.txt",
        "details": {
          "content_size": 2148,
          "content_lines": 12
        }
      }
    ]
  },
  "message": "Audit log retrieved successfully"
}
```

---

## 功能支持矩阵

| 功能 | annotation | system_instruction |
|------|-----------|-------------------|
| 获取内容 | ✅ | ✅ |
| 更新保存 | ✅ | ✅ |
| 自动备份 | ✅ | ✅ |
| 恢复备份 | ✅ | ✅ |
| 列出备份 | ✅ | ✅ |
| 查看审计日志 | ✅ | ✅ |
| 对比差异 | ✅ | ✅ |

**验证规则**:
- **annotation**: 必须包含2个占位符 `{{在此处粘贴题库 JSON}}` 和 `{{在此处粘贴学生音频转录文本}}`
- **system_instruction**: 最少10个字符

---

## 前端完整工作流

### 1. 初始加载 - 获取当前内容
```bash
GET /api/v1/config/content/annotation
```
前端显示当前annotation内容供用户编辑

### 2. 用户修改内容
前端提供文本编辑框，用户修改annotation内容

### 3. 保存更改 - 发送更新请求
```bash
POST /api/v1/config/update
```
发送修改后的完整内容，系统自动创建备份并记录审计日志

### 4. 可选 - 查看更改历史
```bash
GET /api/v1/config/audit/annotation
```
显示所有更改记录和操作者信息

### 5. 可选 - 恢复到之前版本
```bash
POST /api/v1/config/restore
```
从备份恢复到之前的版本

---

## 使用示例

### JavaScript - 完整前端编辑流程

```javascript
const API_BASE = 'https://8.159.139.145:7010/api/v1/config';
const token = 'YOUR_JWT_TOKEN';

// 1. 加载当前annotation内容
async function loadAnnotation() {
  const response = await fetch(`${API_BASE}/content/annotation`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const result = await response.json();
  if (result.success) {
    document.getElementById('editor').value = result.data.content;
    console.log(`已加载 ${result.data.lines} 行内容`);
  } else {
    console.error('加载失败:', result.message);
  }
}

// 2. 保存修改
async function saveAnnotation() {
  const newContent = document.getElementById('editor').value;

  const response = await fetch(`${API_BASE}/update`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      file_key: 'annotation',
      content: newContent
    })
  });

  const result = await response.json();
  if (result.success) {
    alert('保存成功！');
    console.log('备份路径:', result.data.backup_path);
    console.log('更改ID:', result.data.change_id);
  } else {
    alert('保存失败: ' + result.message);
  }
}

// 3. 查看修改历史
async function viewHistory() {
  const response = await fetch(`${API_BASE}/audit/annotation`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const result = await response.json();
  if (result.success) {
    result.data.changes.forEach(change => {
      console.log(`${change.timestamp} - ${change.user_id}: ${change.action}`);
    });
  }
}

// 4. 列出所有备份
async function listBackups() {
  const response = await fetch(`${API_BASE}/backups/annotation`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const result = await response.json();
  if (result.success) {
    return result.data.backups;
  }
}

// 5. 恢复到备份
async function restoreBackup(backupPath) {
  const response = await fetch(`${API_BASE}/restore`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      file_key: 'annotation',
      backup_path: backupPath
    })
  });

  const result = await response.json();
  if (result.success) {
    alert('恢复成功！');
    await loadAnnotation(); // 重新加载内容
  } else {
    alert('恢复失败: ' + result.message);
  }
}
```

### cURL

```bash
# 1. 获取当前annotation内容
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/content/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2. 更新配置
curl -k -X POST "https://8.159.139.145:7010/api/v1/config/update" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_key":"annotation","content":"..."}'

# 3. 列出备份
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/backups/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. 恢复备份
curl -k -X POST "https://8.159.139.145:7010/api/v1/config/restore" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_key":"annotation","backup_path":"..."}'

# 5. 查看审计日志
curl -k -X GET "https://8.159.139.145:7010/api/v1/config/audit/annotation" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 错误响应

| 状态码 | 错误 | 解决方案 |
|--------|------|---------|
| 400 | 验证失败 | 检查占位符或文件大小 |
| 403 | 权限不足 | 使用 ADMIN 账号 |
| 404 | 资源不存在 | 检查备份路径 |
| 429 | 速率限制 | 等待后重试 |

---

## 速率限制

- 获取内容: 100 请求/分钟
- 更新/恢复: 20 请求/分钟
- 查询（备份/审计/对比）: 50 请求/分钟
