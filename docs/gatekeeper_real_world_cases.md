# Gatekeeper 真实案例分析

## 问题背景

在实际数据中发现了**题库选择错误**的问题，这正是 Gatekeeper 需要检测的场景。

## 真实案例：Benjamin (Abby61000_2025-11-05)

### 数据来源

这不是测试预设的错误，而是**真实存在的数据问题**：

### 1. Metadata 记录

```json
{
  "question_bank_path": "questionbank/R1-27-D3.json",
  "progress": "R1-27-D3"
}
```

**题库 R1-27-D3.json** (中→英):
```json
{
  "question": "小孩",
  "answer": "kid"
}
```

### 2. 老师实际录音

**ASR 转写**:
```
字表二十七英翻中。kid kid 呃小孩。小孩。pupil 小学生，瞳孔。
小学生或者瞳孔。baby 婴儿。婴儿。...
```

**关键证据**:
1. 老师自己说了 **"英翻中"**
2. ASR 模式: **"kid 小孩"** (先英文，后中文)
3. 这是 **英→中** 模式！

### 3. 应该使用的题库

**题库 R1-27-D4.json** (英→中):
```json
{
  "question": "kid",
  "answer": "小孩"
}
```

### 4. 问题分析

| 项目 | Metadata 记录 | 老师实际使用 | 匹配？ |
|------|--------------|------------|--------|
| 题库文件 | R1-27-D3.json | R1-27-D4.json | ✗ |
| 翻译方向 | 中→英 | 英→中 | ✗ |
| Question 语言 | 中文 | 英文 | ✗ |
| Answer 语言 | 英文 | 中文 | ✗ |

**结论**: 题库选择**完全错误**！

## 问题产生原因

### 可能的场景

1. **老师拿错题库**
   - 打算用 D3，实际拿了 D4
   - 录音时没有察觉

2. **Metadata 录入错误**
   - 老师用了 D4
   - 但 metadata 写成了 D3

3. **题库文件混淆**
   - D3 和 D4 词汇相同，只是方向相反
   - 容易搞混

## 影响和后果

### 如果没有 Gatekeeper

1. **Pipeline 继续执行**
   ```
   audio → qwen_asr → timestamps → cards (annotation)
   ```

2. **Annotation 使用错误题库**
   ```python
   # 实际 ASR: "kid 小孩"
   # 错误题库: question="小孩" answer="kid"
   #
   # Annotator 会困惑：
   # - ASR 中先出现 "kid"，但题库说 question 是 "小孩"？
   # - 这会导致错误的评分！
   ```

3. **浪费资源**
   - LLM annotation 成本高（Gemini/Qwen API）
   - 用错误题库评分，结果无效
   - 需要人工发现后重新处理

### 有了 Gatekeeper

1. **及时检测**
   ```
   audio → qwen_asr → gatekeeper → [FAIL - STOP]
                                    ↓
                              人工检查题库
   ```

2. **节省成本**
   - 在 annotation 前就拦截
   - 避免浪费 LLM API 调用
   - 人工修正 metadata 后重新运行

3. **提高质量**
   - 确保题库正确
   - 评分结果可靠

## 其他真实案例

### Oscar (Zoe41900_2025-09-08)

**Metadata**: R1-65-D5.json (中→英)
**ASR**: "Not. Not. 双倍的，双的。Half..."
**模式**: 英→中 (错误)
**Gatekeeper**: FAIL ✓

### Cathy (Zoe41900_2025-09-08) - 正确案例

**Metadata**: R1-65-D5.json (中→英)
**ASR**: "不，not。not。双倍的，双的。呃，double double..."
**模式**: 中→英 (正确)
**Gatekeeper**: PASS ✓

## Gatekeeper 的价值

### 检测真实错误，而非理论测试

Gatekeeper 不是为了通过"人工构造的测试用例"，而是为了：

1. **检测真实的人为错误**
   - 老师拿错题库
   - Metadata 录入错误
   - 题库文件混淆

2. **在早期阶段拦截**
   - 在 annotation 前检测
   - 避免浪费 LLM 资源
   - 节省成本和时间

3. **提供明确的修复建议**
   ```
   [✗] gatekeeper FAIL - WRONG_QUESTIONBANK (1.72s)
       问题类型: WRONG_QUESTIONBANK
       建议: 检查题库选择是否正确（翻译方向或词汇内容）
   ```

## 统计数据

基于 9 个测试样本的初步统计：

| 批次 | 学生数 | PASS | FAIL | 错误率 |
|------|--------|------|------|--------|
| Abby61000_2025-11-05 | 3 | 1 | 2 | 67% |
| Zoe41900_2025-09-08 | 3 | 1 | 2 | 67% |
| Zoe51530_2025-09-08 | 3 | 3 | 0 | 0% |
| **总计** | **9** | **5** | **4** | **44%** |

**结论**: 题库选择错误的比例相当高（44%），Gatekeeper 非常必要！

## 总结

1. **问题是真实的**：不是测试构造的，而是实际数据中存在的人为错误
2. **影响是严重的**：错误题库会导致 annotation 结果完全错误
3. **Gatekeeper 是必要的**：及时检测，节省成本，提高质量
4. **Prompt 是有效的**：v1.3.0 能准确检测这些真实错误

这正是为什么需要在 pipeline 中加入 Gatekeeper 质检门禁！
