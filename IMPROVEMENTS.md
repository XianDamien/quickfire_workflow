# Gemini 批处理超时与失败恢复改进

**日期**: 2025-12-22
**提交**: 待创建

## 问题背景

根据 traceback 分析，"卡住"发生在 `client.models.generate_content()` 的网络读阶段（`httpcore/_sync/http11.py` 的 recv），因为当前实现没有显式 HTTP timeout，所以遇到网络/代理抖动时会一直等到 Ctrl-C。

关键差异对比：
- **Legacy**: 固定 gemini-2.5-pro + max_output_tokens=16384
- **现状**: 默认 gemini-3-pro-preview，且 gemini-3 系列默认 max_output_tokens=64000
- **问题**: token 上限越高 → 生成越久 → 在没有 timeout 的前提下更像"卡死"
- **根因**: 无超时 + 严格失败退出

## 解决方案

### 1. HTTP Timeout 配置支持

**修改文件**:
- `scripts/annotators/config.py`
- `scripts/annotators/gemini.py`

**功能**:
- 新增 `http_timeout` 参数（默认 600 秒 = 10 分钟）
- 可通过环境变量 `GEMINI_HTTP_TIMEOUT` 全局设置
- 可通过 CLI `--http-timeout` 参数覆盖

**实现**:
```python
# config.py
DEFAULT_HTTP_TIMEOUT = int(os.getenv("GEMINI_HTTP_TIMEOUT", "600"))

# gemini.py
http_options = types.HttpOptions(timeout=self.http_timeout)
self.client = genai.Client(api_key=api_key, http_options=http_options)
```

### 2. --continue-on-error 批处理模式

**修改文件**: `scripts/main.py`

**功能**:
- **默认模式**: 严格失败模式（任何学生失败立即停止）
- **新增模式**: 继续处理模式（单个学生失败不影响后续）
- 失败汇总：末尾显示所有失败学生列表及失败原因

**使用方式**:
```bash
# 严格模式（默认）
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08

# 继续处理模式
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --continue-on-error
```

### 3. Gemini 参数 CLI 可配置

**新增 CLI 参数**:
- `--max-output-tokens`: LLM 最大输出 tokens（默认：Gemini 3 系列 64000，其他 16384）
- `--max-retries`: API 调用最大重试次数（默认：5）
- `--retry-delay`: API 调用重试延迟，秒（默认：5）
- `--http-timeout`: HTTP 请求超时，秒（默认：600）

**使用示例**:
```bash
# 自定义所有参数
python3 scripts/main.py \
  --archive-batch Zoe41900_2025-09-08 \
  --http-timeout 300 \
  --max-output-tokens 32000 \
  --max-retries 3 \
  --retry-delay 10 \
  --continue-on-error

# 环境变量方式
export GEMINI_HTTP_TIMEOUT=900
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08
```

## 技术细节

### HttpOptions 参数

Google GenAI Python SDK 支持以下配置：

```python
from google.genai import types

http_options = types.HttpOptions(
    timeout=600,  # HTTP 超时（秒）
    retryOptions=types.HttpRetryOptions(
        attempts=5,  # 重试次数
        initialDelay=1.0,  # 初始延迟
        maxDelay=60.0,  # 最大延迟
        expBase=2.0,  # 指数基数
        jitter=0.1,  # 抖动
        httpStatusCodes=[500, 502, 503, 504]  # 要重试的状态码
    )
)
```

### run_stage 返回值变更

**之前**: `return bool`
**之后**: `return (success: bool, error_msg: Optional[str])`

这样可以收集详细的失败信息用于汇总显示。

### 失败信息收集

```python
failed_students = []
failure_info = {
    'student': student_name,
    'stage': stage,
    'error': error_msg or '未知错误'
}
failed_students.append(failure_info)

# 末尾显示
for info in failed_students:
    print(f"  - {info['student']} ({info['stage']}): {info['error']}")
```

## 测试验证

### Dry-run 测试

```bash
$ python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 \
    --student Oscar --only cards --dry-run \
    --http-timeout 300 --max-output-tokens 32000 \
    --max-retries 3 --continue-on-error

============================================================
Quickfire Pipeline
============================================================
Archive: Zoe41900_2025-09-08
学生数: 1
阶段: cards
Annotator: gemini-3-pro-preview
Annotator 参数:
  - max_output_tokens: 32000
  - max_retries: 3
  - http_timeout: 300
模式: 干运行
模式: 继续处理模式（单个学生失败不影响后续）
============================================================
```

### 预期效果

1. **网络超时场景**:
   - 之前：无限等待直到 Ctrl-C
   - 之后：600 秒（或自定义）后超时报错，可配置重试

2. **批处理失败场景**:
   - 之前：第一个学生失败立即退出，后续学生未处理
   - 之后（--continue-on-error）：继续处理所有学生，末尾汇总失败列表

3. **参数灵活性**:
   - 之前：max_output_tokens 等参数硬编码
   - 之后：所有关键参数均可通过 CLI 或环境变量配置

## 向后兼容性

✅ **完全兼容**: 所有新参数都是可选的，默认行为保持不变
- 默认 HTTP timeout: 600 秒（足够长）
- 默认失败模式：严格模式（与之前一致）
- 默认 Gemini 参数：从配置文件读取

## 参考资料

**Google GenAI Python SDK**:
- HttpOptions signature: `timeout: Optional[int] = None`
- HttpRetryOptions signature: `attempts, initialDelay, maxDelay, expBase, jitter, httpStatusCodes`

**相关 Issues**:
- [Setting timeout in genai.Client() does not work · Issue #911](https://github.com/googleapis/python-genai/issues/911)
- [60s timeout from python sdk - Gemini API Forum](https://discuss.ai.google.dev/t/60s-timeout-from-python-sdk/83274)

## 下一步建议

1. **监控与日志**: 添加超时事件的详细日志记录
2. **自适应超时**: 根据 max_output_tokens 自动调整 timeout
3. **重试策略优化**: 使用 HttpRetryOptions 配置指数退避
4. **性能统计**: 记录每个学生的处理时间，识别异常慢的请求
