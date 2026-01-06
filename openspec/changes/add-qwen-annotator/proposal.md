# Proposal: 添加 Qwen Annotator 实现

## Change ID
`add-qwen-annotator`

## Status
DRAFT

## Summary
新增 Qwen Annotator 实现，支持使用阿里云通义千问系列模型（qwen-max 等）进行学生作业评分，提供与现有 Gemini Annotator 平行的替代方案。

## Motivation

### 业务背景
当前系统仅支持 Google Gemini 作为评分 LLM，但在某些场景下可能需要使用国产大模型：
1. **多样性**: 提供多个 LLM 选择，对比评分质量
2. **可用性**: 当 Gemini API 不可用或配额限制时的备选方案
3. **成本优化**: 不同模型的价格差异，可根据需求选择
4. **合规要求**: 某些场景可能需要使用国产模型

### 技术背景
- 现有架构已预留 Qwen annotator 接口（`scripts/annotators/__init__.py:105-109`）
- 阿里云 DashScope API 已用于 ASR（`DASHSCOPE_API_KEY` 环境变量）
- Qwen 系列模型支持与 Gemini 类似的 System/User message 对话格式
- 可复用现有的 prompt 模板、解析和校验逻辑

### 当前实现的不足
```python
# scripts/annotators/__init__.py:105-109
if provider == "qwen":
    raise NotImplementedError(
        f"Qwen annotator 尚未实现: {name}\n"
        f"预留接口，待后续实现"
    )
```

**问题**:
1. 接口已预留但未实现，无法使用 Qwen 模型
2. 缺少 Qwen 特定的配置（模型列表、超时、token 限制等）
3. 无法在 cards 阶段使用 `--annotator qwen-max` 参数

## Goals
1. ✅ 实现 `QwenAnnotator` 类，复用 `BaseAnnotator` 架构
2. ✅ 支持 qwen-max/qwen-max-latest/qwen3-max 等模型
3. ✅ 复用现有 prompt 模板和 JSON 解析逻辑
4. ✅ 集成到 `get_annotator()` 注册机制
5. ✅ 使用真实音频文件测试完整流程（禁止 mock 数据）

## Non-Goals
- ❌ 不修改任何 prompt 模板（`prompts/annotation/system.md` 和 `user.md`）
- ❌ 不改变现有 Gemini Annotator 的行为
- ❌ 不添加 fallback 机制（开发阶段严禁 fallback）
- ❌ 不创建新的评分标准或输出格式

## Scope

### In Scope
- **代码实现**:
  - 创建 `scripts/annotators/qwen.py`
  - 实现 `QwenAnnotator` 类（继承 `BaseAnnotator`）
  - 使用 `dashscope.Generation.call()` 调用 API
  - 复用现有 `_render_prompts()`, `_parse_response()`, `_validate_output()` 等工具函数

- **配置集成**:
  - 更新 `scripts/annotators/__init__.py` 中的 `get_annotator()` 逻辑
  - 保持单一默认配置（不修改 `config.py` 的 `DEFAULT_ANNOTATOR`）

- **文档更新**:
  - 更新 `scripts/README.md` 说明 `--annotator qwen-max` 用法
  - 更新 `scripts/annotators/__init__.py` 的 docstring

- **真实测试**:
  - 使用 `archive/Zoe51530_2025-09-08/Stefan` 已有的 ASR 结果
  - 运行 cards 阶段: `python scripts/main.py --archive-batch ... --student Stefan --only cards --annotator qwen-max`
  - 验证生成的 `4_llm_annotation.json` 和 `prompt_log.txt`

### Out of Scope
- 不涉及 ASR 阶段的修改
- 不修改 Gemini Annotator 的实现
- 不添加 OpenAI 或其他 LLM 支持

## Technical Approach

### 核心实现
创建 `scripts/annotators/qwen.py`：

```python
"""
scripts/annotators/qwen.py - Qwen Annotator 实现

使用阿里云通义千问系列模型进行学生作业评分。
"""

import dashscope
from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput

class QwenAnnotator(BaseAnnotator):
    """
    Qwen Annotator 实现

    支持的模型:
    - qwen-max
    - qwen-max-latest
    - qwen3-max
    """

    def __init__(
        self,
        model: str = "qwen-max",
        temperature: float = 0.2,
        max_output_tokens: int = 16384,
        max_retries: int = 5,
        retry_delay: int = 5,
    ):
        """初始化 Qwen Annotator"""
        self.model = model
        self.name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 从环境变量获取 API Key
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 环境变量未设置")

    def annotate(self, input_data: AnnotatorInput) -> AnnotatorOutput:
        """
        调用 Qwen API 进行评分

        复用现有逻辑:
        1. 使用 _render_prompts() 渲染 system 和 user prompt
        2. 调用 dashscope.Generation.call()
        3. 使用 _parse_response() 解析 JSON 响应
        4. 使用 _validate_output() 校验输出格式
        5. 保存 prompt_log.txt 和 4_llm_annotation.json
        """
        # 实现细节省略...
```

### 集成到注册机制
更新 `scripts/annotators/__init__.py`：

```python
# 第105-109行，移除 NotImplementedError，改为:
if provider == "qwen":
    from .qwen import QwenAnnotator

    # 规范化模型名称
    if model in ["qwen", "qwen-max"]:
        model = "qwen-max"

    return QwenAnnotator(model=model, **kwargs)
```

### 测试流程
1. **前置检查**：
   - 确认 `DASHSCOPE_API_KEY` 已设置
   - 确认 Stefan 已有 ASR 结果: `archive/Zoe51530_2025-09-08/Stefan/2_qwen_asr.json`
   - 确认题库文件存在: `questionbank/R3-14-D4.json`

2. **执行测试**：
   ```bash
   # 测试 Qwen-max annotator
   python scripts/main.py \
       --archive-batch Zoe51530_2025-09-08 \
       --student Stefan \
       --only cards \
       --annotator qwen-max \
       --force
   ```

3. **结果验证**：
   - 检查 `runs/qwen-max/Zoe51530_2025-09-08_Stefan_{timestamp}/4_llm_annotation.json`
   - 检查 `prompt_log.txt` 包含完整的 system/user prompt
   - 验证 JSON 格式正确（`final_grade_suggestion`, `mistake_count`, `annotations`）
   - 验证评分逻辑合理（A/B/C 等级符合预期）

## Dependencies
- ✅ `dashscope` SDK 已安装（用于 ASR）
- ✅ `DASHSCOPE_API_KEY` 环境变量已配置
- ✅ `BaseAnnotator` 基类已定义
- ✅ Prompt 模板已存在（`prompts/annotation/system.md`, `user.md`）
- ⚠️  需要网络连接和有效的 DashScope API Key

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Qwen API 输出格式与 Gemini 不同 | JSON 解析失败 | 添加重试和详细错误日志，直接输出 API 响应 |
| API 配额限制 | 无法完成测试 | 使用已有测试数据，限制测试次数 |
| 评分结果质量差 | 不满足业务需求 | 先实现功能，评分质量由后续测试验证 |
| 与 Gemini 输出不一致 | 难以对比 | 保留详细日志，后续可对比两个模型的输出 |

## Success Criteria
1. ✅ `QwenAnnotator` 类实现完成，通过类型检查
2. ✅ `get_annotator("qwen-max")` 能成功返回实例
3. ✅ Stefan 测试成功运行，生成有效的 `4_llm_annotation.json`
4. ✅ 输出 JSON 格式正确，包含所有必需字段
5. ✅ `prompt_log.txt` 包含完整的 prompt 内容
6. ✅ 无 mock 数据，所有测试使用真实音频和 ASR 结果

## Open Questions
1. ❓ Qwen API 是否支持与 Gemini 相同的 System Message 格式？
2. ❓ Qwen 的 `max_output_tokens` 限制是多少？（需查阅文档或测试验证）
3. ❓ 是否需要添加 Qwen 特定的错误处理逻辑？

## Related Work
- Existing: `GeminiAnnotator` - 现有 Gemini 实现，作为参考
- Existing: `BaseAnnotator` - 基类定义
- Existing: `scripts/qwen_asr.py` - 已使用 DashScope API 的 ASR 实现
