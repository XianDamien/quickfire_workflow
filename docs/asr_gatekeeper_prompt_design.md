# ASR Gatekeeper 提示词设计方案

## 概述
ASR Gatekeeper 是一个质检模型,用于在 annotation pipeline 前检测题库选择错误和音频异常,避免浪费 LLM 资源。

## 问题分析

### 题库类型 (以 R1-27 系列为例)

| 题库文件 | Question | Answer | 方向 | 状态 |
|---------|----------|--------|------|------|
| R1-27-D3.json | 小孩 | kid | 中→英 | ✓ 正确 |
| R1-27-D4.json | kid | 小孩 | 英→中 | ✗ 方向反 |
| R1-27-D5.json | 小孩 | kid | 中→英 | ✗ 不同词汇 |

### 实际 ASR 转写示例
```
字表二十七英翻中。kid kid 呃小孩。小孩。pupil 小学生，瞳孔。
小学生或者瞳孔。baby 婴儿。婴儿。twin 双胞胎的，双胞胎之一...
```

**特征分析**:
- 老师念题顺序: 英文词 → 中文意思
- 对应 D3 题库: question(中文) → answer(英文)
- 如果误用 D4 题库: question(英文) → answer(中文) → 方向错误

## 检测策略

### 1. 翻译方向检测 (核心)

**步骤**:
1. 分析题库中 question/answer 的语言类型
2. 判断题库方向 (中→英 或 英→中)
3. 检查 ASR 中词汇出现顺序
4. 对比题库方向与 ASR 模式是否一致

**示例**:
```
题库 D3: question="小孩" answer="kid" (中→英)
ASR: "kid 小孩" (英在前，中在后)
结论: 匹配 ✓

题库 D4: question="kid" answer="小孩" (英→中)
ASR: "kid 小孩" (英在前，中在后)
结论: 不匹配，题库应该是中→英但实际选了英→中 ✗
```

### 2. 词汇匹配度检测

**步骤**:
1. 提取题库中所有词汇 (question + answer)
2. 统计转写中出现的词汇数量
3. 计算匹配率 = 出现词汇数 / 总词汇数
4. 阈值判断: >50% 通过, <50% 失败

### 3. 音频完整性检测

**指标**:
- 转写长度 > 题库数量 × 5 字符
- 存在完整的"问题-答案"对结构
- 包含老师声音 (不只是学生零散回答)

## 输出格式

### 成功示例
```json
{
  "status": "PASS",
  "issue_type": null
}
```

### 失败示例
```json
{
  "status": "FAIL",
  "issue_type": "WRONG_QUESTIONBANK"
}
```

```json
{
  "status": "FAIL",
  "issue_type": "AUDIO_ANOMALY"
}
```

## 提示词文件

### system.md
- 定义角色和背景
- 详细说明两种问题类型
- 提供翻译方向错误的具体示例
- 定义输出格式

### user.md
- 提供题库和转写输入
- 详细的4步检测流程
- 明确的输出要求

## 关键改进点

1. **针对性检测**: 不仅检测词汇是否存在,更重要的是检测**翻译方向**是否正确
2. **具体示例**: 在 system.md 中提供 D3/D4 的对比示例
3. **分步指令**: 在 user.md 中提供清晰的4步检测流程
4. **简洁输出**: 只输出 status 和 issue_type 两个字段

## 测试计划

使用 `Abby61000_2025-11-05` 批次数据:
- Benjamin/Dana/Jeffery + R1-27-D3.json → 应该 PASS
- 同样转写 + R1-27-D4.json → 应该 FAIL (WRONG_QUESTIONBANK)
- 同样转写 + R1-65.json → 应该 FAIL (WRONG_QUESTIONBANK)

## 文件清单

- `prompts/asr_gatekeeper/system.md` - 更新完成 ✓
- `prompts/asr_gatekeeper/user.md` - 更新完成 ✓
- `docs/asr_gatekeeper_test_cases.md` - 测试用例 ✓
- `docs/asr_gatekeeper_prompt_design.md` - 本文档 ✓
