# Proposal: 增强 ASR 动态题库上下文加载

## Change ID
`enhance-asr-questionbank-context`

## Status
DRAFT

## Summary
改进 Qwen ASR 脚本的动态题库加载逻辑，确保根据音频文件名自动匹配正确的题库文件并作为识别上下文，提高特定词汇的识别准确率。

## Motivation

### 业务背景
当前系统使用 Qwen ASR 进行音频转写时，对于特定领域词汇（如 "all"、"升高" 等）识别准确率不足：

**实际问题**：
1. `Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3` - "all" 被识别成 "哦"
2. `Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3` - "升高" 被识别成 "身高"

这两个词汇都存在于对应的题库文件中：
- `questionbank/R1-65-D5.json`: card_index 8 包含 "all"
- `questionbank/R3-14-D4.json`: card_index 19-20 包含 "升高"

### 技术背景
Qwen3-ASR 支持通过 System Message 提供上下文文本（热词、段落等）来显著提升特定领域词汇的识别准确率：
- 上下文限制: ≤ 10000 Token
- 容错性高: 支持任意分隔符和格式
- 已实现: `QwenASRProvider` 类已支持 `vocabulary_path` 参数

### 当前实现的不足
虽然 `process_audio_file` 函数已尝试根据文件名查找题库：
```python
# 当前实现（scripts/qwen_asr.py:945-958）
progress_prefix = progress.rsplit('-', 1)[0]  # 获取 R1-27 部分
for vocab_path in questionbank_dir.glob(f"{progress}*.json"):
    vocab_file = str(vocab_path)
    break

# 如果没找到确切匹配，尝试用前缀匹配
if not vocab_file:
    for vocab_path in questionbank_dir.glob(f"{progress_prefix}*.json"):
        vocab_file = str(vocab_path)
        break
```

**问题**：
1. 逻辑不够精确：使用通配符 `{progress}*.json` 可能匹配到错误文件
2. 前缀匹配逻辑（`progress_prefix`）计算错误：`rsplit('-', 1)[0]` 只能去掉最后一个部分
   - 例如：`R1-65-D5` → `R1-65`，但正确的题库文件是 `R1-65-D5.json`
3. 缺少测试验证题库上下文是否真正改善识别效果

## Goals
1. ✅ 精确匹配题库文件：根据文件名中的 progress 字段精确查找题库（如 `R1-65-D5.json`）
2. ✅ 确保题库作为 ASR 上下文被正确加载和使用
3. ✅ 验证题库上下文对识别准确率的改善效果
4. ✅ 使用真实音频测试，严禁 mock 数据

## Non-Goals
- ❌ 修改 prompt 模板或评分逻辑
- ❌ 改变 ASR API 调用方式（已有实现正确）
- ❌ 创建新的题库文件或修改题库格式

## Scope

### In Scope
- **代码改进**:
  - 修复 `process_audio_file` 中的题库查找逻辑
  - 确保精确匹配 `{progress}.json` 文件
  - 添加日志输出以验证题库加载状态

- **测试验证**:
  - 使用 `backend_input/Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3` 测试（题库: R1-65-D5.json）
  - 使用 `backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3` 测试（题库: R3-14-D4.json）
  - 检查识别结果中 "all" 和 "升高" 是否正确

### Out of Scope
- 不涉及 `Gemini_annotation.py` 的修改
- 不涉及 prompt 模板的修改
- 不创建新的测试音频文件

## Technical Approach

### 核心修改
改进 `scripts/qwen_asr.py` 中的 `process_audio_file` 函数：

```python
# 当前问题代码（第945-958行）
progress_prefix = progress.rsplit('-', 1)[0]  # ❌ 错误逻辑
for vocab_path in questionbank_dir.glob(f"{progress}*.json"):  # ❌ 可能误匹配
    ...

# 改进方案
# 1. 精确匹配：优先查找完全匹配的题库文件
exact_match = questionbank_dir / f"{progress}.json"
if exact_match.exists() and "vocabulary" not in exact_match.name.lower():
    vocab_file = str(exact_match)
    print(f"   📚 题库（精确匹配）: {exact_match.name}")
else:
    # 2. 回退方案：如果精确匹配失败，使用通用查找
    vocab_file = find_questionbank_file(progress)
    if vocab_file:
        print(f"   📚 题库（模糊匹配）: {Path(vocab_file).name}")
```

### 日志增强
添加更详细的日志以便调试：
```python
if vocab_file:
    print(f"   📚 题库: {Path(vocab_file).name} (progress={progress})")
else:
    print(f"   ⚠️  警告：未找到题库 (progress={progress})，ASR 将不使用上下文")
```

### 测试流程
1. **前置检查**：
   - 确认题库文件存在: `ls -la questionbank/R1-65-D5.json questionbank/R3-14-D4.json`
   - 确认音频文件存在: `ls -la backend_input/Zoe*`

2. **执行测试**：
   ```bash
   # 测试 1: Cathy (R1-65-D5)
   python scripts/qwen_asr.py backend_input/Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3 \
       --output-dir /tmp/asr_test/cathy

   # 测试 2: Stefan (R3-14-D4)
   python scripts/qwen_asr.py backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3 \
       --output-dir /tmp/asr_test/stefan
   ```

3. **结果验证**：
   - 检查日志中是否显示正确的题库文件
   - 检查 `2_qwen_asr.json` 中是否包含正确的词汇
   - Cathy: 查找 "all"（不应该是"哦"）
   - Stefan: 查找 "升高"（不应该是"身高"）

## Dependencies
- ✅ 题库文件已存在于 `/questionbank`
- ✅ `QwenASRProvider` 已支持 `vocabulary_path`
- ✅ `parse_audio_filename` 已能正确解析 progress
- ⚠️  需要有效的 `DASHSCOPE_API_KEY` 环境变量

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| 题库上下文无效果 | 识别问题仍然存在 | 保留原有逻辑，添加日志以便诊断 |
| API 限制或配额 | 无法完成测试 | 使用真实 API Key，限制测试数量 |
| 文件名格式变化 | 无法匹配题库 | 保留 fallback 逻辑（通用查找）|

## Success Criteria
1. ✅ 代码能精确匹配 `R1-65-D5.json` 和 `R3-14-D4.json`
2. ✅ 日志显示题库已加载并作为上下文使用
3. ✅ Cathy 音频中 "all" 识别正确（或识别效果明显改善）
4. ✅ Stefan 音频中 "升高" 识别正确（或识别效果明显改善）
5. ✅ 无 mock 数据，所有测试使用 `backend_input/` 中的真实音频

## Open Questions
1. ❓ 如果题库上下文仍无效果，是否需要调整上下文格式或增加更多热词？
2. ❓ 是否需要在日志中输出实际发送给 ASR 的上下文文本内容以便调试？

## Related Work
- Existing: `enhance-qwen-asr-batch-processing` - 批量处理功能
- Existing: `QwenASRProvider.load_vocabulary()` - 题库加载逻辑
- Existing: `QwenASRProvider.build_context_text()` - 上下文构建逻辑
