---
name: qwen-asr-context
description: 优化 Qwen3-ASR-Flash 的 context prompt 以提升转写质量。当需要调整 ASR 转写效果（如漏词、英文被翻译成中文、低音量片段丢失等）时使用此 skill。
---

# Qwen ASR Context 优化

## 核心机制

Qwen3-ASR-Flash 通过 system message 注入 context 实现转写偏置（Contextual Biasing），不是热词，而是类似 LLM 的上下文注入。任意格式的背景文本都可以影响识别结果。

- **Prompt 文件**: `prompts/asr_context/system.md`
- **加载函数**: `scripts/asr/qwen.py` → `load_asr_context_prompt()`
- **注入方式**: 作为 `messages[0].role="system"` 传入 DashScope API
- **API 调用**: `transcribe_audio()` 方法支持 `system_context_override` 参数，可临时覆盖 prompt 进行实验

## 优化流程

### 1. 收集 bad cases

从 `two_output/` 或 `archive/` 中找到转写质量差的样本，典型问题：
- 英文单词被翻译成中文（如 engine → 引擎）
- 低音量/倍速片段被跳过
- 中英文混合内容只输出单一语言

### 2. 编辑 prompt

修改 `prompts/asr_context/system.md`，关键经验：
- 明确描述音频特征（倍速、低音量 = 有效语音，不是噪音）
- 给出正确/错误转写示例，引导模型行为
- 强调输出预期（如"中英文混合，不要翻译"）

### 3. A/B 对比测试

用 bad cases 对比旧版和新版 prompt 的效果：

```bash
python skills/qwen-asr-context/scripts/prompt_ab_test.py \
    --audio two_output/Batch/Student/N/_audio.mp3 \
    --old-prompt "旧 prompt 文本" \
    --new-prompt "@prompts/asr_context/system.md" \
    --output docs/ab_results.json
```

`@` 前缀表示从文件读取 prompt。对比字数变化和内容质量，迭代调整 prompt 直到 bad cases 改善。

### 4. 回归测试

在正常批次上随机抽样，确认新 prompt 无回退：

```bash
python skills/qwen-asr-context/scripts/prompt_regression.py \
    --batch-dir two_output/SomeBatch_2026-01-01 \
    --old-prompt "旧 prompt 文本" \
    --new-prompt "@prompts/asr_context/system.md" \
    --sample-size 10 \
    --output docs/regression_results.json
```

回退判定：新 prompt 转写字数 < 旧版 * 0.8 即标记为回退。0 回退则可以合并。

### 5. 提交

更新 `prompts/asr_context/metadata.json` 版本号，连同 `system.md` 一起提交。
