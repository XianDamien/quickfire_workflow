# ASR 上下文差异分析报告

**分析日期**: 2025-12-04
**问题**: 为什么 `qwen_test.py` 和 `qwen_asr.py` 处理相同音频文件时产生不同的识别结果

## 问题现象

### 测试对比

1. **qwen_test.py** - 直接调用 Qwen API
   - 识别结果: `"rise名词。升高。升高、升起、上涨、增长。"`
   - 第一义项: **"升高"** ✅（正确）

2. **qwen_asr.py** - 使用封装的 QwenASRProvider
   - 识别结果: `"rise名词，身高。升高，升起，上涨，增长。"`
   - 第一义项: **"身高"** ❌（错误，应为"升高"）

3. **音频文件**: `/Users/damien/Desktop/LanProject/quickfire_workflow/backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3`

## 根因分析

### 核心原因：上下文格式不一致

#### qwen_test.py 的上下文格式
- 直接把整段词汇内容（含词性+中文释义）作为 system message
- 格式与音频朗读内容逐字匹配
- 示例：
  ```
  rise不及物动词。太阳、月亮等上升、上涨、起立、起床。
  rise名词。升高、升起、上涨、增长。
  raise及物动词。抬高，举起，提高，养育，提起话题。
  ```

#### qwen_asr.py 的上下文格式
- 使用 `build_context_text()` 生成 "Domain vocabulary" 列表
- **缺少词性提示**（无 `hint` 字段）
- 将 JSON 中的 `question`(英文) 放在前、`answer`(中文) 放在括号里
- 与音频的朗读形式不一致
- 示例：
  ```
  Domain vocabulary: rise(太阳、月亮等上升、上涨、起立、起床), rise(升高、升起、上涨、增长), ...
  ```

### 字段顺序混乱

**代码位置**: `scripts/qwen_asr.py:324-407`

1. **load_vocabulary** (lines 324-355)
   - 从题库 JSON 读取后返回: `{idx: [question, answer]}`
   - 即: `[英文, 中文]` 顺序

2. **build_context_text** (lines 364-407)
   - 注释里期望: `{key: [中文, English, ...]}`
   - 实际处理: `chinese_term = values[0]`, `english_term = values[1]`
   - 结果导致: 把 `question`(英文) 当成中文，`answer`(中文) 当成英文

3. **最终输出格式**
   - 实际生成: `rise(升高、升起、上涨、增长)` - 英文在前、中文在括号
   - **未利用 `hint` 里的词性信息**

### API 参数差异

#### qwen_test.py (lines 14-23)
```python
asr_options = {
    "enable_itn": False
}
# 未指定 language 或 enable_lid
```

#### qwen_asr.py (lines 437-458)
```python
asr_options = {
    "enable_itn": enable_itn,      # False
    "enable_lid": enable_lid,      # True
}
if language:
    asr_options["language"] = language  # "zh"
```

**差异点**:
- `qwen_asr.py` 显式设置 `language="zh"`, `enable_lid=True`
- 使用 `file://` 路径格式 (line 560)
- 支持分段并发处理 (lines 520-624)

### Endpoint 配置差异

#### qwen_test.py (lines 4-5)
```python
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
```

#### qwen_asr.py
- 未覆写 base URL，使用默认配置

## 上下文文本完整对比

### qwen_test.py 的 System Message
```
Simple形容词。简单的、简易的、朴素的、简朴的。
Complete形容词。完整的、完全的、彻底的。
Complete及物动词。完成。
List名词。清单、目录、一览表。
List及物动词。把什么什么列成表，举例。
...
rise不及物动词。太阳、月亮等上升、上涨、起立、起床。
rise名词。升高、升起、上涨、增长。
raise及物动词。抬高，举起，提高，养育，提起话题。
...
```

### qwen_asr.py 的 build_context_text 输出
```
Domain vocabulary: simple(简单的、简易的、朴素的、简朴的), complete(完整的、完全的、彻底的), complete(完成), list(清单、目录、一览表), list(把什么什么列成表，举例), assist(帮助、助攻), assist(参加、出席), assist(帮助、促进), scientist(科学家), tourist(旅游者、观光者), case(箱子、盒子、情况、状况), chase(追捕、追求、雕刻、试图赢得), chase(奔跑、追赶), chase(追捕、争取、狩猎), purchase(购买), purchase(购买、购买的物品), increase(增加、增大), increase(增加、增长), rise(太阳、月亮等上升、上涨、起立、起床), rise(升高、升起、上涨、增长), raise(抬高，举起，提高，养育，提起话题), surprise(使惊奇，使诧异), surprise(惊讶，令人吃惊的是), exercise(锻炼，运动，体操，练习，习题), exercise(练习，锻炼), praise(赞扬，表扬), praise(赞扬，表扬，称赞), noise(嘈杂声，喧闹声，噪音)
```

## 关键代码位置

### 1. 硬编码上下文
- **文件**: `scripts/qwen_test.py:10-12`
- **问题**: 直接把目标文本写入 system message，与音频高度匹配

### 2. 词表加载逻辑
- **文件**: `scripts/qwen_asr.py:324-355`
- **问题**: 读取题库时返回 `[question, answer]` 格式

### 3. 上下文构建逻辑
- **文件**: `scripts/qwen_asr.py:364-407`
- **问题**:
  - 把第一个值当"中文"、第二个当"English"（实际相反）
  - 只输出"词(释义)"列表，不含 `hint` 词性信息

### 4. API 调用参数
- **qwen_test.py**: `scripts/qwen_test.py:14-23` 仅配置 `enable_itn=False`
- **qwen_asr.py**: `scripts/qwen_asr.py:437-458` 使用 `language="zh"`, `enable_lid=True`, `file://` 路径

### 5. 分段处理
- **文件**: `scripts/qwen_asr.py:520-624`
- **问题**: 支持分段并行处理，参数与测试脚本不一致

### 6. Endpoint 设置
- **qwen_test.py:4-5**: 强制北京域名
- **qwen_asr.py**: 未覆写，走默认 base URL

## 修复建议

### 1. 让上下文贴合题库结构与音频朗读

**建议**: 在 `build_context_text` 里使用 `hint` + `question` + `answer` 生成类似以下句式：

```python
# 目标格式
"rise不及物动词。太阳、月亮等上升、上涨、起立、起床。rise名词。升高、升起、上涨、增长。"
```

**实现方向**:
- 统一顺序为 "英文 + 词性 + 中文释义"
- 或直接复用题库文本
- 避免当前中英文角色颠倒

### 2. 规范字段顺序

**方案 A**: 调整 `load_vocabulary` 输出为 `[中文, English]`，匹配 `build_context_text` 的期望

**方案 B**: 修改 `build_context_text`：
- 把 `question` 视为英文
- 把 `answer` 视为中文
- 显式加入 `hint` 词性信息

### 3. 统一 API 选项

**建议**: 与验证脚本保持一致
- 禁用 `enable_lid` 或确认默认值
- 在两处都显式设定相同的:
  - `base_http_api_url`
  - `model`
  - `result_format`
  - `asr_options`

### 4. 调试可视化

**建议**:
- 在调用 API 前打印或保存最终 system context
- 方便核对与题库、音频的一致性
- 防止再出现隐性格式偏差

**实现示例**:
```python
print(f"📋 System Context Preview:\n{system_context[:500]}...")
```

### 5. 强化易混词

**可选优化**:
- 如仍有个别词误判，可在 context 中单独强化易混词
- 例如: "rise 名词=升高"（而非"身高"）
- 或在音频前增加简短提示，引导模型优先使用题库含义

## 验证步骤

修改 `qwen_asr.py` 后，建议按以下步骤验证：

1. **重新处理 Stefan 音频**
   ```bash
   python3 qwen_asr.py backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3
   ```

2. **检查输出结果**
   ```bash
   cat asr/Stefan.json | jq -r '.output.choices[0].message.content[0].text' | grep "rise"
   ```

3. **验证"rise"是否稳定输出"升高"**
   - 期望: `"rise名词，升高。"`
   - 而非: `"rise名词，身高。"`

4. **对比上下文文本**
   - 添加 debug 日志打印实际发送给 API 的 system context
   - 确认格式与 `qwen_test.py` 一致

## 参考文件

- `/Users/damien/Desktop/LanProject/quickfire_workflow/scripts/qwen_test.py`
- `/Users/damien/Desktop/LanProject/quickfire_workflow/scripts/qwen_asr.py`
- `/Users/damien/Desktop/LanProject/quickfire_workflow/asr/Stefan.json`
- `/Users/damien/Desktop/LanProject/quickfire_workflow/questionbank/R3-14.json` (推测)

## 结论

**根本原因**: `qwen_asr.py` 的 `build_context_text()` 方法未能正确利用题库的完整结构（特别是 `hint` 词性字段），且字段顺序颠倒，导致生成的上下文文本无法有效约束 ASR 模型对"rise"的识别，使其倾向于常见词"身高"而非题库中的正确义项"升高"。

**修复优先级**:
1. ✅ **高优先级**: 修复字段顺序，加入 `hint` 词性
2. ✅ **高优先级**: 统一 API 参数配置
3. ⚠️ **中优先级**: 添加调试日志
4. 💡 **低优先级**: 强化易混词（视修复效果而定）
