# Gemini Batch API 实现报告

**日期**: 2026-01-05
**状态**: ✅ 已完成

## 概述

实现了使用官方 `google-genai` SDK 直接调用 Gemini Batch API 的功能，绕过中转站，支持 SOCKS5 代理配置。

## 测试结果

| 班级 | 学生数 | 模型 | 结果 |
|------|--------|------|------|
| Zoe41900_2025-09-08 | 6人 | gemini-3-pro-preview | 全部成功 |

**评分分布**: A(2) + B(4)

- Cathy: B
- Frances Wang: A
- Lucy: B
- Oscar: B
- Rico: B
- Yoyo: A

## 使用方法

### 提交 Batch Job

```bash
# 提交整个班级
python3 scripts/gemini_batch.py submit \
  --archive-batch <班级名> \
  --proxy socks5://127.0.0.1:7890

# 指定特定学生
python3 scripts/gemini_batch.py submit \
  --archive-batch <班级名> \
  --students "Alice,Bob,Charlie" \
  --proxy socks5://127.0.0.1:7890
```

### 获取结果

```bash
# 使用 manifest 文件
python3 scripts/gemini_batch.py fetch \
  --manifest <manifest路径> \
  --proxy socks5://127.0.0.1:7890

# 直接使用 job name
python3 scripts/gemini_batch.py fetch \
  --job batches/xxx \
  --proxy socks5://127.0.0.1:7890
```

### 其他命令

```bash
# 查询状态
python3 scripts/gemini_batch.py status --job batches/xxx --proxy socks5://127.0.0.1:7890

# 列出所有 jobs
python3 scripts/gemini_batch.py list --proxy socks5://127.0.0.1:7890

# 取消 job
python3 scripts/gemini_batch.py cancel --job batches/xxx --proxy socks5://127.0.0.1:7890
```

## 技术实现

### 代理配置

使用 `httpx` 客户端配置 SOCKS5 代理：

```python
transport = httpx.HTTPTransport(proxy=proxy, retries=3)
custom_client = httpx.Client(
    transport=transport,
    timeout=timeout_ms / 1000,
    follow_redirects=True,  # 重要：下载文件时需要跟随重定向
)

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        timeout=timeout_ms,
        httpx_client=custom_client
    )
)
```

### 关键修复

- `httpx.Client` 需要 `follow_redirects=True` 才能正确下载结果文件（Gemini 返回 302 重定向）
- 添加 `retries=3` 增强网络稳定性

### JSONL 格式

每行一个请求：

```json
{
  "key": "{archive_batch}:{student_name}:{run_id}",
  "request": {
    "contents": [{"role": "user", "parts": [{"text": "..."}]}],
    "systemInstruction": {"parts": [{"text": "..."}]},
    "generationConfig": {
      "temperature": 0.2,
      "maxOutputTokens": 65536,
      "responseMimeType": "application/json"
    }
  }
}
```

## 文件结构

```
scripts/
└── gemini_batch.py          # Batch API 脚本

archive/{batch}/
├── _batch_runs/
│   └── {run_id}/
│       ├── batch_input.jsonl      # 输入文件
│       └── batch_manifest.json    # Manifest（断点续跑）
└── {student}/
    └── runs/{model}/{run_id}/
        ├── 4_llm_annotation.json  # 标注结果
        └── run_manifest.json      # 运行元数据
```

## 与同步模式对比

| 特性 | 同步模式 | Batch 模式 |
|------|---------|-----------|
| 入口 | `scripts/main.py --stage cards` | `scripts/gemini_batch.py submit/fetch` |
| 成本 | 100% | **50%** |
| 延迟 | 即时 | 最长 24h（通常数分钟） |
| 适用场景 | 单个学生调试 | 整班批量处理 |

## 依赖

- `google-genai>=1.56.0`
- `httpx[socks]>=0.28.1`

均已在 `pyproject.toml` 中配置。

## 参考文档

- [Gemini Batch API 官方文档](https://ai.google.dev/gemini-api/docs/batch-api)
- `docs/gemini_batch_plan.md` - 原始计划文档
- `docs/batch_api.md` - API 参考
