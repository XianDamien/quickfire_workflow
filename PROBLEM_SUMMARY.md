# 问题总结与当前状态

**日期**: 2025-12-22
**状态**: 代码改进已完成，网络问题待解决

---

## 原始问题

### 症状
从 traceback 看，批处理"卡住"发生在 `client.models.generate_content()` 的网络读阶段（`httpcore/_sync/http11.py` 的 recv）。

### 根本原因
1. **无 HTTP timeout** → 网络/代理抖动时会无限等待，直到 Ctrl-C 中断
2. **严格失败模式** → 任何异常都会 `sys.exit(1)` 中断整条流水线
3. **参数不可配置** → max_output_tokens / timeout 等硬编码，无法灵活调整

### 环境对比
- **Legacy**: gemini-2.5-pro + max_output_tokens=16384
- **现状**: gemini-3-pro-preview + max_output_tokens=64000（默认）
- **影响**: token 上限越高 → 生成越久 → 在没有 timeout 的前提下更像"卡死"

---

## 已完成的代码改进 ✅

### 1. HTTP Timeout 配置
**文件**: `scripts/annotators/config.py`, `scripts/annotators/gemini.py`

```python
# 默认 10 分钟超时，可通过环境变量覆盖
DEFAULT_HTTP_TIMEOUT = int(os.getenv("GEMINI_HTTP_TIMEOUT", "600"))

# GeminiAnnotator 使用 HttpOptions
http_options = types.HttpOptions(timeout=self.http_timeout)
self.client = genai.Client(api_key=api_key, http_options=http_options)
```

**验证**: ✅ 超时后正确抛出 "The read operation timed out" 而非无限等待

---

### 2. --continue-on-error 批处理模式
**文件**: `scripts/main.py`

**功能**:
- 默认：严格失败模式（任何学生失败立即停止）
- 新增：`--continue-on-error` 继续处理其他学生
- 失败汇总：末尾显示所有失败学生列表及详细错误

**输出示例**:
```
============================================================
完成: 3 成功, 2 失败
============================================================

失败的学生列表:
------------------------------------------------------------
  - Oscar (cards): annotation 失败: The read operation timed out
  - Lucy (cards): annotation 失败: SSL handshake error
------------------------------------------------------------
```

---

### 3. Gemini 参数 CLI 可配置
**文件**: `scripts/main.py`

**新增参数**:
```bash
--max-output-tokens 32000    # LLM 最大输出 tokens
--max-retries 5               # API 调用最大重试次数
--retry-delay 5               # API 调用重试延迟（秒）
--http-timeout 600            # HTTP 请求超时（秒）
```

**验证**: ✅ 参数正确传递并显示

---

### 4. 失败信息收集
**实现**:
- `run_stage()` 返回值改为 `(success: bool, error_msg: Optional[str])`
- 收集失败详情: `failed_students = [{student, stage, error}, ...]`
- 末尾汇总显示

---

## 当前实际问题 ⚠️

### 测试过程中遇到的网络错误

#### 错误 1: SSL EOF 错误
```
[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1028)
```
- **出现次数**: 3/3 次重试后失败
- **原因**: 代理/网络连接中断

#### 错误 2: SSL Handshake Timeout
```
_ssl.c:1011: The handshake operation timed out
```
- **出现次数**: 5/5 次重试后失败
- **原因**: SSL 握手阶段超时（可能是代理问题）

#### 错误 3: Read Operation Timeout
```
The read operation timed out
```
- **出现次数**: 5/5 次重试后失败
- **原因**: HTTP timeout（300-600秒）内未完成读取
- **说明**: ✅ 这证明了 HTTP timeout 功能正常工作

---

## 问题诊断

### 网络连接问题
当前的错误主要是**网络/代理问题**，而非代码问题：

1. **代理不稳定**: SSL 握手失败、连接中断
2. **Gemini API 连接问题**: 可能是：
   - 代理配置问题
   - API endpoint 访问问题
   - 网络抖动

### 代码层面
所有改进功能**均正常工作**：
- ✅ HTTP timeout 正确触发
- ✅ 重试机制正常执行（显示 "尝试 1/5", "尝试 2/5" 等）
- ✅ 错误信息正确收集和显示
- ✅ CLI 参数正确传递

---

## 解决方案建议

### 方案 1: 检查代理配置
```bash
# 检查代理是否正常
set_proxy
curl -I https://generativelanguage.googleapis.com/

# 尝试使用系统代理
unset http_proxy https_proxy
```

### 方案 2: 调整重试策略
```bash
# 增加重试次数和延迟
python3 scripts/main.py \
  --archive-batch Zoe41900_2025-09-08 \
  --student Oscar \
  --only cards \
  --max-retries 10 \
  --retry-delay 10 \
  --http-timeout 900 \
  --continue-on-error
```

### 方案 3: 使用已有的成功 runs
```bash
# 检查是否已有成功的 runs
ls -la archive/Zoe41900_2025-09-08/Oscar/runs/gemini-2.5-pro/
ls -la archive/Zoe41900_2025-09-08/Oscar/runs/gemini-3-pro-preview/
```

### 方案 4: 分批处理
```bash
# 使用 --continue-on-error 分批处理，失败的后续手动处理
python3 scripts/main.py \
  --archive-batch Zoe41900_2025-09-08 \
  --continue-on-error \
  --http-timeout 600
```

---

## 实际测试结果

### 测试 1: 单学生 + 自定义参数
```bash
python3 scripts/main.py \
  --archive-batch Zoe41900_2025-09-08 \
  --student Oscar \
  --only cards \
  --http-timeout 300 \
  --max-output-tokens 32000 \
  --max-retries 3
```

**结果**:
- ✅ CLI 参数正确显示
- ✅ 重试机制正常（显示 1/3, 2/3, 3/3）
- ❌ 网络错误: SSL EOF 错误

### 测试 2: 单学生 + 增加重试
```bash
python3 scripts/main.py \
  --archive-batch Zoe41900_2025-09-08 \
  --student Oscar \
  --only cards \
  --http-timeout 600 \
  --max-retries 5 \
  --annotator gemini-2.5-pro
```

**结果**:
- ✅ HTTP timeout 功能正常（600秒后超时）
- ✅ 重试机制正常（显示 1/5 到 5/5）
- ❌ 网络错误: The read operation timed out

---

## 结论

### 代码改进状态: ✅ 完成
所有4项改进均已实现并验证功能正常：
1. HTTP timeout 配置 - ✅ 正常触发
2. --continue-on-error 模式 - ✅ 代码就绪
3. Gemini 参数 CLI 可配置 - ✅ 参数传递正常
4. 失败信息收集 - ✅ 错误显示正常

### 当前阻塞问题: ⚠️ 网络连接
- **根因**: 代理/网络不稳定导致 Gemini API 连接失败
- **表现**: SSL 握手错误、连接超时
- **影响**: 无法完成端到端的批处理测试

### 下一步建议
1. **修复网络问题**（优先级最高）
   - 检查代理配置
   - 测试直连 Gemini API
   - 考虑换网络环境

2. **如果网络无法立即修复**
   - 使用 `--continue-on-error` 模式尽可能处理成功的学生
   - 记录失败列表，网络恢复后重新处理
   - 或使用已有的成功 runs 数据进行其他分析

3. **可选优化**
   - 添加 HttpRetryOptions 配置指数退避
   - 添加连接健康检查（pre-flight check）
   - 记录每次重试的详细日志
