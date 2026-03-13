---
name: qwen-asr-context
description: ASR 模型横向对比与迭代优化。当需要对比 ASR 模型效果（Qwen/FunASR/豆包）、调优 ASR context prompt、测试说话人分离、排查漏词或误识别时使用此 skill。触发词包括"ASR 对比"、"转写效果"、"说话人分离"、"漏词"、"context prompt"、"ASR 准确度"等，即使用户没有明确提到 skill 名称也应主动使用。
---

# ASR 模型对比与迭代优化

本项目使用三家 ASR 引擎处理中英混合教育场景音频。这个 skill 提供两个核心工作流：**多模型横向对比**和 **Qwen ASR context prompt 迭代优化**。两者共享相同的方法论：收集 bad cases → 对比测试 → 迭代改进。

## 支持的 ASR 引擎

| 引擎 | 模型 | 代码 | 关键能力 |
|------|------|------|---------|
| Qwen ASR | qwen3-asr-flash | `scripts/asr/qwen.py` | system context 偏置，最高中文准确度 |
| FunASR | fun-asr | `scripts/asr/funasr.py` | 句子+词级时间戳，热词表，说话人分离 |
| 豆包 | volc.bigasr.auc | skill `scripts/asr_compare.py` | 说话人聚类，corpus context |

API 调用细节见 `references/funasr-api.md` 和 `references/doubao-api.md`。

## 环境变量

所有 key 在 `scripts/.env`：
- `DASHSCOPE_API_KEY` — Qwen ASR + FunASR
- `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` / `OSS_ENDPOINT` / `OSS_BUCKET_NAME` — 上传音频（FunASR/豆包需要 URL）
- `X-Api-App-Key` / `X-Api-Access-Key` — 豆包

---

## 工作流一：多模型横向对比

同一段音频在三家 ASR 上跑，对比转写准确度、说话人分离效果、时间戳粒度。

### 调用模板

```bash
# 基础用法：指定音频和已有 Qwen 结果
uv run python .claude/skills/qwen-asr-context/scripts/asr_compare.py \
    --audio real_test/Batch/Student.mp3 \
    --qwen-archive archive/Batch/Student/2_qwen_asr.json \
    --output docs/asr_compare_xxx

# 脚本会自动：
# 1. 上传音频到 OSS（HTTPS 签名 URL，1 小时有效）
# 2. 加载已有 Qwen ASR 结果
# 3. FunASR 转写（diarization_enabled=True, speaker_count=2）
# 4. 豆包转写（enable_speaker_info=True）
# 5. 保存原始 JSON + 生成 Markdown 对比报告
```

### 输出

```
docs/asr_compare_xxx/
├── funasr_diarization_result.json   # FunASR 原始结果（含 speaker_id）
├── qwen_asr_result.json             # Qwen ASR 原始结果
├── doubao_asr_result.json           # 豆包原始结果（含 speaker info）
└── compare_report.md                # Markdown 对比报告
```

### 对比报告包含

- 逐句对齐表格（时间戳 + speaker + 文本）
- 关键差异标注（误识别用 **粗体** 高亮）
- 功能维度对比矩阵（准确度/说话人分离/时间戳）

历史对比结论见 `references/known-results.md`。

---

## 工作流二：Qwen ASR Context Prompt 优化

Qwen3-ASR-Flash 通过 system message 注入 context 实现转写偏置（Contextual Biasing）。当发现转写 bad case（漏词、误翻、中文错字）时，通过修改 context prompt 来修正。

### 核心文件

- **Prompt**: `prompts/asr_context/system.md`
- **加载**: `scripts/asr/qwen.py` → `load_asr_context_prompt()`
- **注入**: `messages[0].role="system"` → DashScope MultiModalConversation API
- **临时覆盖**: `transcribe_audio(system_context_override="...")`

### 步骤 1：A/B 对比测试

用 bad case 音频对比旧版和新版 prompt 的效果。

**调用模板：**

```bash
# 对比两个 prompt 版本
uv run python .claude/skills/qwen-asr-context/scripts/prompt_ab_test.py \
    --audio path/to/audio1.mp3 path/to/audio2.mp3 \
    --old-prompt "@prompts/asr_context/system.md.bak" \
    --new-prompt "@prompts/asr_context/system.md" \
    --output docs/ab_results.json
```

`@` 前缀从文件读取 prompt 内容。输出对比每个音频的字数变化和文本差异。

**输出示例：**

```
StudentA/audio1: 280 → 312 (+32)
  旧: Island.岛屿。We can go to the island...
  新: Island.岛屿。We can go to the island by boat.岛屿...
```

### 步骤 2：回归测试

在正常批次上随机抽样，确认新 prompt 没有引入回退。

**调用模板：**

```bash
uv run python .claude/skills/qwen-asr-context/scripts/prompt_regression.py \
    --batch-dir two_output/SomeBatch_2026-01-01 \
    --old-prompt "@prompts/asr_context/system.md.bak" \
    --new-prompt "@prompts/asr_context/system.md" \
    --sample-size 10 \
    --output docs/regression_results.json
```

回退判定：新 prompt 转写字数 < 旧版 × 0.8 即标记为回退。退出码 1 = 有回退。

### 步骤 3：提交

更新 `prompts/asr_context/metadata.json` 版本号，连同 `system.md` 一起提交。

### Prompt 编写经验

- 明确描述音频特征（倍速、低音量 = 有效语音，不是噪音）
- 给出正确/错误转写示例对，引导模型行为
- 强调输出预期（"中英文混合，不要翻译"）
- 避免过度约束——解释 why 比强制 MUST 更有效

---

## 脚本索引

| 脚本 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `scripts/asr_compare.py` | 三方 ASR 横向对比 | 音频文件 + Qwen 结果 | JSON + MD 报告 |
| `scripts/prompt_ab_test.py` | Prompt A/B 对比 | 音频 + 两版 prompt | 字数对比 JSON |
| `scripts/prompt_regression.py` | Prompt 回归测试 | 批次目录 + 两版 prompt | 回退报告 JSON |

## 参考文档

需要查看 API 细节时按需读取，不必一次性加载：

- `references/funasr-api.md` — FunASR 说话人分离参数、返回格式
- `references/doubao-api.md` — 豆包 Volcengine BigASR 完整调用示例
- `references/known-results.md` — 历史对比结论和已知局限
