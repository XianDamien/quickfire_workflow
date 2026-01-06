# Tasks: add-qwen-annotator

## 实施步骤

### 1. 前置验证
- [ ] 确认 `DASHSCOPE_API_KEY` 环境变量已设置
  ```bash
  echo $DASHSCOPE_API_KEY
  ```
- [ ] 确认测试学生已有 ASR 结果
  ```bash
  ls -la archive/Zoe51530_2025-09-08/Stefan/2_qwen_asr.json
  ```
- [ ] 确认题库文件存在
  ```bash
  ls -la questionbank/R3-14-D4.json
  ```
- [ ] 确认 dashscope SDK 已安装
  ```bash
  uv run python -c "import dashscope; print(dashscope.__version__)"
  ```

### 2. 代码实现

#### 2.1 创建 QwenAnnotator 类
**文件**: `scripts/annotators/qwen.py`

**实现内容**:
- [ ] 定义 `QwenAnnotator` 类，继承 `BaseAnnotator`
- [ ] 实现 `__init__()` 方法
  - 参数: `model`, `temperature`, `max_output_tokens`, `max_retries`, `retry_delay`
  - 从环境变量读取 `DASHSCOPE_API_KEY`
  - 初始化模型名称和配置
- [ ] 实现 `annotate()` 方法
  - 调用 `_render_prompts()` 渲染 system 和 user prompt
  - 使用 `dashscope.Generation.call()` 调用 API
  - 实现重试逻辑（最多 5 次，延迟 5 秒）
  - 提取响应中的文本内容
  - 调用 `_parse_response()` 解析 JSON
  - 调用 `_validate_output()` 校验格式
  - 返回 `AnnotatorOutput` 对象
- [ ] 实现 `run_archive_student()` 方法
  - 复用 `BaseAnnotator` 的通用逻辑
  - 加载 ASR 结果和题库
  - 调用 `annotate()`
  - 保存 `4_llm_annotation.json` 和 `prompt_log.txt`
  - 打印处理时间统计

**参考实现** (伪代码):
```python
class QwenAnnotator(BaseAnnotator):
    def __init__(self, model="qwen-max", ...):
        self.model = model
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        # ...

    def annotate(self, input_data: AnnotatorInput) -> AnnotatorOutput:
        # 1. 渲染 prompts
        system_prompt, user_prompt = self._render_prompts(input_data)

        # 2. 调用 API (带重试)
        for attempt in range(self.max_retries):
            try:
                response = dashscope.Generation.call(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    result_format="message"
                )
                break
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise

        # 3. 解析响应
        response_text = response.output.choices[0].message.content
        parsed_json = self._parse_response(response_text)

        # 4. 校验输出
        self._validate_output(parsed_json)

        # 5. 返回结果
        return AnnotatorOutput(
            raw_response=response_text,
            parsed_json=parsed_json,
            model=self.model,
            timestamp=datetime.now().isoformat()
        )
```

#### 2.2 更新注册逻辑
**文件**: `scripts/annotators/__init__.py`

**修改位置**: 第 105-109 行

- [ ] 移除 `raise NotImplementedError`
- [ ] 添加 Qwen annotator 导入和实例化逻辑
- [ ] 支持模型名称规范化（`qwen` → `qwen-max`）

**预期代码**:
```python
# Qwen 系列
if provider == "qwen":
    from .qwen import QwenAnnotator

    # 规范化模型名称
    if model in ["qwen", "qwen-max"]:
        model = "qwen-max"

    return QwenAnnotator(model=model, **kwargs)
```

#### 2.3 更新文档
**文件**: `scripts/annotators/__init__.py` (docstring)

- [ ] 更新第 23-24 行，移除 "(预留)" 标记
  ```python
  支持的 annotator:
      - gemini-2.5-pro (默认)
      - gemini-2.0-flash
      - qwen-max
      - (预留) openai:gpt-4.1
  ```

- [ ] 更新第 56 行，移除 "(预留)" 标记
  ```python
  - qwen:model-name
  ```

**文件**: `scripts/README.md`

- [ ] 添加 Qwen annotator 使用示例
  ```markdown
  ### 使用 Qwen Annotator

  ```bash
  python scripts/main.py \
      --archive-batch Zoe51530_2025-09-08 \
      --student Stefan \
      --only cards \
      --annotator qwen-max
  ```

  支持的 Qwen 模型:
  - qwen-max (默认)
  - qwen-max-latest
  - qwen3-max
  ```

### 3. 测试执行

#### 3.1 测试 Stefan 音频（R3-14-D4）
- [ ] 创建测试目录
  ```bash
  mkdir -p /tmp/qwen_test
  ```

- [ ] 运行 cards 阶段
  ```bash
  python scripts/main.py \
      --archive-batch Zoe51530_2025-09-08 \
      --student Stefan \
      --only cards \
      --annotator qwen-max \
      --force
  ```

- [ ] 验证命令行输出
  - 显示 "使用 annotator: qwen-max"
  - 显示处理进度和时间统计
  - 显示 "✓ Stefan: 已保存到 ..."

- [ ] 检查输出文件
  ```bash
  # 找到最新的 run 目录
  ls -lt runs/qwen-max/
  ```

- [ ] 验证 `4_llm_annotation.json`
  - 文件存在且大小 > 0
  - 包含 `final_grade_suggestion` 字段（A/B/C）
  - 包含 `mistake_count` 对象
  - 包含 `annotations` 数组
  - JSON 格式有效（可用 `jq` 验证）
  ```bash
  jq . runs/qwen-max/Zoe51530_2025-09-08_Stefan_*/4_llm_annotation.json
  ```

- [ ] 验证 `prompt_log.txt`
  - 包含 "=== System Prompt ===" 部分
  - 包含 "=== User Prompt ===" 部分
  - 包含完整的题库 JSON 和 ASR 文本
  ```bash
  cat runs/qwen-max/Zoe51530_2025-09-08_Stefan_*/prompt_log.txt
  ```

### 4. 结果分析
- [ ] 对比 Qwen 和 Gemini 的评分结果（如果已有 Gemini 结果）
  - 检查 `final_grade_suggestion` 是否一致
  - 检查 `mistake_count` 是否相近
  - 检查具体 `annotations` 的差异

- [ ] 验证评分逻辑合理性
  - A 级: 0 个错误
  - B 级: 1-2 个错误
  - C 级: ≥3 个错误

- [ ] 记录发现的问题
  - 如果 JSON 解析失败 → 检查 API 响应格式
  - 如果评分不合理 → 检查 prompt 是否正确传递
  - 如果 API 调用失败 → 检查网络和 API Key

### 5. 文档归档（使用 Serena）
- [ ] 更新 Serena memory 记录
  - 记录 Qwen Annotator 实现细节
  - 记录测试结果和发现的问题
  - 记录与 Gemini 的对比结论

- [ ] 不创建额外的 markdown 文档（除非用户明确要求）

## 验收标准
1. ✅ `scripts/annotators/qwen.py` 文件创建完成
2. ✅ `QwenAnnotator` 类实现完整，包含所有必需方法
3. ✅ `get_annotator("qwen-max")` 成功返回实例
4. ✅ Stefan 测试运行成功，无崩溃或异常
5. ✅ 生成的 `4_llm_annotation.json` 格式正确
6. ✅ `prompt_log.txt` 包含完整 prompt 内容
7. ✅ 无使用 mock 数据，所有测试使用真实文件

## 依赖项
- `DASHSCOPE_API_KEY` 环境变量已设置
- 网络连接正常（调用阿里云 API）
- Python 环境已安装 `dashscope` SDK
- 测试数据已存在（Stefan 的 ASR 结果）

## 潜在阻塞点
1. 如果 `DASHSCOPE_API_KEY` 失效或配额不足 → 需要更新 API Key
2. 如果 Qwen API 响应格式与预期不符 → 需要调整解析逻辑
3. 如果 JSON 解析失败 → 需要检查 prompt 或添加更严格的输出格式要求
4. 如果网络连接失败 → 需要解决代理或防火墙问题
