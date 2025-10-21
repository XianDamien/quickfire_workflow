# Qwen3-ASR 热词上下文增强功能说明

## 功能概述

**热词上下文增强** 是对 `qwen_asr.py` 的核心升级，通过将题库内容作为上下文注入到 Qwen3-ASR API 的 System Message 中，显著提升专业词汇（如人名、地名、产品术语）的识别准确率。

### 核心改进

✅ **自动题库检测** - 支持灵活的题库文件名模式
- 优先级：vocabulary.json > R*.json > R*.csv > *.csv
- 自动查找 `_shared_context` 目录中的题库

✅ **格式兼容性** - 支持多种题库格式
- JSON 格式：列表形式 `[{"问题": "...", "答案": "..."}]` 或字典形式
- CSV 格式：标准表格 (第1列=中文，第2列=English)

✅ **上下文增强** - 构建优化过的上下文文本
- 自动提取题库中的关键词汇
- 格式化为 "Domain vocabulary: term1(meaning1), term2(meaning2), ..."
- 完全兼容 Qwen3-ASR 的容错能力

✅ **透明集成** - 无需修改现有工作流
- 自动在 System Message 中注入上下文
- 完全向后兼容，默认启用
- 音频分段处理时保留上下文

---

## 新增函数

### `find_vocabulary_file(shared_context_dir: Path) -> Optional[Path]`

**功能：** 在 `_shared_context` 目录中自动查找题库文件

**优先级顺序：**
1. `vocabulary.json` - 标准词汇表
2. `R*.json` - JSON 格式题库
3. `R*.csv` - CSV 格式题库（如 R3-14.csv、R1-65.csv）
4. `*.csv` - 任何其他 CSV 文件
5. 无则返回 None

**使用示例：**
```python
from scripts.qwen_asr import find_vocabulary_file
from pathlib import Path

shared_context = Path("archive/Zoe51530-9.8/_shared_context")
vocab_file = find_vocabulary_file(shared_context)
if vocab_file:
    print(f"找到题库: {vocab_file.name}")
```

---

### 改进的 `QwenASRProvider.load_vocabulary(vocab_path: str)`

**功能升级：** 原来仅支持 JSON，现在同时支持 JSON 和 CSV

**支持的格式：**

#### JSON 格式（列表）
```json
[
  {"问题": "simple，形容词", "答案": "简单的，简易的"},
  {"问题": "complete，形容词", "答案": "完整的，完全的"},
  ...
]
```

#### JSON 格式（字典）
```json
{
  "0": ["中文术语", "English term"],
  "1": ["另一个术语", "Another term"],
  ...
}
```

#### CSV 格式
```csv
中文,English
一百,hundred
千,thousand
总是,always
```

**返回值：** 统一的词汇字典格式
```python
{
  "0": ["term_cn", "term_en"],
  "1": ["term_cn", "term_en"],
  ...
}
```

**使用示例：**
```python
from scripts.qwen_asr import QwenASRProvider

# 支持 JSON（自动检测格式）
vocab = QwenASRProvider.load_vocabulary("path/to/R3-14-D4.json")

# 支持 CSV
vocab = QwenASRProvider.load_vocabulary("path/to/R1-65.csv")

print(f"加载了 {len(vocab)} 条词汇")
```

---

### 改进的 `QwenASRProvider.build_context_text(vocabulary: Dict[str, list])`

**功能升级：** 更详细的文档和优化的上下文格式

**生成的上下文格式：**
```
Domain vocabulary: term1_cn(term1_en), term2_cn(term2_en), term3_cn(term3_en), ...
```

**特点：**
- 双语格式便于 Qwen3-ASR 识别
- 自动剔除空值
- 完全兼容 Qwen3-ASR 的容错性（支持多种分隔符格式）
- Token 使用量优化（限制: ≤10000 Token）

**使用示例：**
```python
from scripts.qwen_asr import QwenASRProvider

vocab = QwenASRProvider.load_vocabulary("path/to/vocabulary.csv")
context = QwenASRProvider.build_context_text(vocab)

print(f"上下文长度: {len(context)} 字符")
# 输出: Domain vocabulary: 一百(hundred), 千(thousand), 总是(always), ...
```

---

## 工作流程

### 完整的 ASR 处理流程（带热词增强）

```python
from scripts.qwen_asr import process_student

# 处理单个学生 - 自动启用热词增强
exit_code = process_student("Zoe51530-9.8", "Alvin")

# 内部流程：
# 1. 查找学生目录和音频文件
# 2. 查找题库文件 (find_vocabulary_file)
# 3. 加载题库 (load_vocabulary - 自动检测 JSON/CSV)
# 4. 构建上下文 (build_context_text)
# 5. 将上下文注入 System Message
# 6. 调用 Qwen3-ASR API
# 7. 保存转写结果到 2_qwen_asr.json
```

### API 调用示例

```python
messages = [
    {
        "role": "system",
        "content": [
            {
                "text": "Domain vocabulary: simple，形容词(简单的，简易的), complete，形容词(完整的，完全的), ..."
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {"audio": "file:///path/to/audio.mp3"}
        ]
    }
]

response = dashscope.MultiModalConversation.call(
    api_key=api_key,
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        "enable_itn": False,
        "enable_lid": True
    }
)
```

---

## 命令行使用

### 处理整个数据集（自动使用热词增强）
```bash
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8
```

**输出：**
```
============================================================
处理数据集: Zoe51530-9.8
============================================================
   📚 题库: R3-14-D4.json
  ⟳ Alvin: 处理音频...
   📊 音频时长: 267.6 秒
   ✂️  分割成 2 段...
   ✓ 片段 1/2 转写完成
   ✓ 片段 2/2 转写完成
   🔀 合并转写结果...
  ✓ Alvin: 已保存到 2_qwen_asr.json
  ✓ Kevin: 已处理过（跳过）
  ...
```

### 处理单个学生（自动使用热词增强）
```bash
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Alvin
```

### 处理所有数据集
```bash
python3 scripts/qwen_asr.py
```

---

## 热词增强的优势

### 1. 识别准确率提升
- **专业词汇**：显著提升领域专业术语（医学、法律、技术等）的识别准确率
- **人名地名**：改善人名、地名、品牌名的识别
- **多义词**：上下文帮助 ASR 正确选择词义

### 2. 兼容性强
- **格式容错**：Qwen3-ASR 对分隔符容错性极高
  - 支持逗号、分号、空格等多种分隔符
  - 无关或无意义文本不会产生负面影响
- **灵活输入**：支持任意长度的文本内容

### 3. 零配置使用
- **自动检测**：无需手动指定题库文件
- **格式自适应**：自动识别 JSON/CSV 格式
- **即插即用**：现有代码无需修改

### 4. 生产就绪
- **完全向后兼容**：不影响现有工作流
- **错误恢复**：题库加载失败不中断处理
- **清晰日志**：在处理过程中显示题库来源

---

## 技术细节

### Token 使用量估算

对于不同规模的题库：

| 题库规模 | 词汇数 | 字符数 | Token 数 | 限制 |
|---------|--------|--------|----------|------|
| 小 | 10 | 100 | ~33 | ✅ 远低于限制 |
| 中 | 25 | 250 | ~83 | ✅ 低于限制 |
| 大 | 100 | 1000 | ~333 | ✅ 低于限制 |
| 超大 | 300 | 3000 | ~1000 | ✅ 低于限制 |

**限制：** 每个请求的上下文 ≤ 10000 Token（充足的空间）

### 音频分段处理中的上下文保留

当音频超过 180 秒时，自动分段处理：

```
原始音频 (267.6 秒)
    ↓
分段处理（3 线程并行）
    ├─ 片段 1: 180 秒 + 上下文 ✓
    ├─ 片段 2: 87.6 秒 + 上下文 ✓
    └─ 片段 3: ...
    ↓
合并转写结果（保持顺序）
```

**关键点：** 每个片段都独立使用完整上下文，确保识别质量

---

## 测试验证

### 演示脚本

运行演示脚本查看热词增强的工作流：

```bash
python3 demo_hotword_asr.py
```

**输出示例：**
```
📚 数据集: Zoe51530-9.8
[✓] 题库文件: R3-14-D4.json
[✓] 加载成功: 28 条词汇
[✓] 上下文: 656 字符

[→] 处理学生: Alvin
    🎙️  音频文件: 1_input_audio.mp3
    📋 API 调用格式:
       model: qwen3-asr-flash
       上下文: Domain vocabulary: simple，形容词(...), complete，形容词(...), ...
```

### 实际处理测试

验证热词增强的实际效果：

```bash
python3 test_single_student.py
```

---

## 故障排除

### 题库文件未找到
**症状：** 处理时没有显示题库信息
```
⟳ Alvin: 处理音频...
[不显示 📚 题库: ... 的行]
```

**原因：** `_shared_context` 目录中无法找到合适的题库文件

**解决方案：**
1. 检查 `archive/<dataset>/_shared_context/` 目录是否存在
2. 确认题库文件名格式（R*.json, R*.csv, vocabulary.json）
3. 手动指定词汇表路径（如果支持）

### 上下文过长（Token 超限）
**症状：** API 返回错误信息

**原因：** 题库文件过大，生成的上下文超过 10000 Token 限制

**解决方案：**
1. 减少题库条目
2. 缩短题库条目的描述文本
3. 使用专业的分词工具优化上下文

---

## 代码示例

### 完整的程序化使用示例

```python
from scripts.qwen_asr import (
    QwenASRProvider,
    find_vocabulary_file,
    find_audio_file,
)
from pathlib import Path
import os

# 初始化
api_key = os.getenv("DASHSCOPE_API_KEY")
provider = QwenASRProvider(api_key=api_key)

# 设置路径
dataset_path = Path("archive/Zoe51530-9.8/Alvin")
shared_context = dataset_path.parent / "_shared_context"

# 查找题库
vocab_file = find_vocabulary_file(shared_context)
vocab = provider.load_vocabulary(str(vocab_file))
context = provider.build_context_text(vocab)

print(f"加载题库: {vocab_file.name}")
print(f"上下文: {len(context)} 字符")

# 查找音频
audio_file = find_audio_file(dataset_path)
print(f"音频文件: {audio_file.name}")

# 转写（自动使用上下文）
result = provider.transcribe_and_save_with_segmentation(
    input_audio_path=str(audio_file),
    output_dir=str(dataset_path),
    vocabulary_path=str(vocab_file),
    output_filename="2_qwen_asr.json",
    language="zh",
    segment_duration=180,
    max_workers=3,
)

print("✅ 转写完成！")
```

---

## 向后兼容性

✅ **完全向后兼容**

- 现有的 `QwenASRProvider` 类完全兼容
- 新增参数都是可选的，有合理默认值
- 无题库文件时自动跳过上下文增强
- 所有现有命令行用法保持不变

---

## 总结

热词上下文增强是一项 **透明的、自动的** 功能升级，通过充分利用题库信息来优化 Qwen3-ASR 的识别准确率。

**关键特性：**
- 🎯 自动题库检测（无需配置）
- 📚 格式自适应（JSON/CSV）
- 🚀 完全向后兼容
- 💯 零配置即用
- 📊 清晰的处理日志
