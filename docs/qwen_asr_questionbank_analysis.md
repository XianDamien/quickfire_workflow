# Qwen ASR 题库上下文增强功能分析报告

## 执行时间
2025-12-04

## 分析目标
检查 `scripts/qwen_asr.py` 是否能够：
1. 从 `backend_input/` 目录文件名解析题库信息（如 R3-14-D4）
2. 从 `questionbank/` 目录动态加载对应题库文件
3. 提取题库中的单词/短语作为 Qwen ASR 的上下文

---

## 分析结果

### 1. 文件名解析功能 ✅ 部分支持

**位置**: `scripts/qwen_asr.py:698-735`

**函数**: `parse_audio_filename()`

**正则表达式**:
```python
^([A-Za-z]+\d+)_(\d{4}-\d{2}-\d{2})_([A-Z]\d+-\d+-D\d+)_(.+)$
```

**提取字段**:
- 班级 (如: Abby61000)
- 日期 (如: 2025-10-30)
- **进度** (如: R3-14-D4) ← 题库标识
- 学生 (如: Benjamin)

**当前限制**:
- ⚠️ 仅在使用 `--file` 参数时调用（`scripts/qwen_asr.py:895-973` `process_audio_file`）
- ⚠️ **脚本未遍历 `backend_input/` 目录**
- ⚠️ 没有批处理 `backend_input/` 的逻辑

---

### 2. 题库动态加载 ⚠️ 部分实现，存在问题

#### 2.1 文件模式（`--file` 参数）✅ 工作正常

**位置**: `scripts/qwen_asr.py:944-960` (`process_audio_file`)

**加载逻辑**:
1. 先查找 `questionbank/{progress}*.json` (精确匹配)
2. 再使用 `progress_prefix = progress.rsplit('-', 1)[0]` 做前缀匹配

**示例**:
- 文件名: `Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3`
- 进度: `R1-27-D2`
- 查找顺序:
  1. `questionbank/R1-27-D2*.json`
  2. `questionbank/R1-27*.json`

**限制**:
- 未向下兼容 `.csv` 格式
- 没有进一步的 fallback（如 R3-14-D4 → R3-14 → R3）

#### 2.2 数据集模式（`--dataset` 参数）❌ 存在严重问题

**位置**: `scripts/qwen_asr.py:843-878` (`find_questionbank_file`)

**问题**:
1. ⚠️ `process_student` 调用 `find_questionbank_file` 时**未传递进度参数**（`scripts/qwen_asr.py:1051-1056`）
2. ⚠️ 只按固定优先级加载（R3-14-D4* → R1-65* → R*.json），与学生/文件名进度无关
3. ❌ **致命bug**: `process_dataset` 调用了**不存在的** `find_vocabulary_file` 函数（`scripts/qwen_asr.py:1103-1108`）
   - 当前会抛出 `NameError`
   - 导致数据集模式无法加载题库

---

### 3. 上下文提取 ❌ **严重问题**

#### 3.1 上下文构建流程

**调用链**:
```
QwenASRProvider.transcribe_audio (line 438-477)
  ↓
load_vocabulary (line 304-368)
  ↓
build_context_text (line 371-414)
```

#### 3.2 核心问题：键名不匹配

**代码期望的键名**:
```python
# scripts/qwen_asr.py:304-368
if isinstance(data, list):
    for item in data:
        if isinstance(item, dict):
            chinese = item.get("问题", "")  # ← 期望中文键
            english = item.get("答案", "")  # ← 期望中文键
```

**实际题库的键名**:
```json
// questionbank/R3-14-D4.json
[
  {
    "card_index": 1,
    "hint": "形容词",
    "question": "simple",           // ← 实际是英文键
    "answer": "简单的、简易的、朴素的、简朴的"  // ← 实际是英文键
  }
]
```

**导致的后果**:
- ❌ `item.get("问题", "")` 返回空字符串
- ❌ 代码 fallback 到取字典的前两个值
- ❌ 实际提取的是 `card_index` (1) 和 `hint` (形容词)
- ❌ **生成的上下文**: `"Domain vocabulary: 1(形容词), 2(形容词), 3(及物动词)..."`
- ❌ **应该生成的上下文**: `"Domain vocabulary: simple(简单的、简易的、朴素的、简朴的), complete(完整的、完全的、彻底的)..."`

**影响**:
- 🔴 ASR 上下文中没有真正的单词/短语
- 🔴 无法提供 Qwen3-ASR 所需的专有词汇增强
- 🔴 识别准确率严重受限

---

## 需要补充的功能

### 1. 批量处理 `backend_input/` 目录 🔨

**需求**:
- 增加遍历 `backend_input/` 的入口函数
- 逐个调用 `process_audio_file` 处理每个音频文件
- 自动从文件名解析进度并驱动题库选择

**建议实现**:
```python
def process_backend_input(api_key: str, output_dir: Optional[Path] = None):
    """批量处理 backend_input/ 目录中的所有音频文件"""
    backend_input = Path("backend_input")

    for audio_file in backend_input.glob("*.mp3"):
        process_audio_file(
            api_key=api_key,
            audio_file=audio_file,
            output_dir=output_dir
        )
```

### 2. 修复上下文提取的键名问题 🔧 **紧急**

**位置**: `scripts/qwen_asr.py:304-368` (`load_vocabulary`)

**当前代码**:
```python
chinese = item.get("问题", "")
english = item.get("答案", "")
```

**修复方案**:
```python
# 支持多种键名格式
chinese = item.get("问题") or item.get("answer", "")
english = item.get("答案") or item.get("question", "")

# 或者更明确的映射
question_key = "question" if "question" in item else "问题"
answer_key = "answer" if "answer" in item else "答案"
chinese = item.get(answer_key, "")
english = item.get(question_key, "")
```

### 3. 实现缺失的 `find_vocabulary_file` 函数 🔧

**位置**: `scripts/qwen_asr.py:1103-1108` (`process_dataset`)

**当前问题**:
```python
vocab_path = find_vocabulary_file(shared_context)  # ← 函数不存在
```

**修复方案**:
- 方案 A: 实现 `find_vocabulary_file` 函数
- 方案 B: 改用现有的 `find_questionbank_file` 函数

```python
# 建议方案 B（更简单）
vocab_path = find_questionbank_file(questionbank_dir=Path("questionbank"))
```

### 4. 增强题库查找的 Fallback 机制 💡

**位置**: `scripts/qwen_asr.py:944-960` (`process_audio_file`)

**当前逻辑**:
```python
# R3-14-D4 → R3-14 (仅一级 fallback)
progress_prefix = progress.rsplit('-', 1)[0]
```

**建议增强**:
```python
def find_questionbank_with_fallback(progress: str) -> Optional[Path]:
    """
    多级 fallback 查找题库
    R3-14-D4 → R3-14-D* → R3-14 → R3 → 默认通用库
    """
    questionbank_dir = Path("questionbank")

    # 1. 精确匹配 R3-14-D4.json
    exact_match = list(questionbank_dir.glob(f"{progress}.json"))
    if exact_match:
        return exact_match[0]

    # 2. 前缀匹配 R3-14-D*.json
    prefix_match = list(questionbank_dir.glob(f"{progress}*.json"))
    if prefix_match:
        return prefix_match[0]

    # 3. 逐级向上 fallback
    parts = progress.split('-')
    for i in range(len(parts) - 1, 0, -1):
        partial = '-'.join(parts[:i])
        matches = list(questionbank_dir.glob(f"{partial}*.json"))
        if matches:
            return matches[0]

    # 4. 默认通用库
    default = questionbank_dir / "default.json"
    if default.exists():
        return default

    return None
```

### 5. 让数据集模式使用进度参数 🔧

**位置**: `scripts/qwen_asr.py:1051-1056` (`process_student`)

**当前代码**:
```python
vocab_path = find_questionbank_file(questionbank_dir=Path("questionbank"))
# ↑ 未传递进度参数
```

**建议修改**:
```python
# 从文件名或元数据中提取进度
progress = extract_progress_from_audio(audio_file)  # 新函数

vocab_path = find_questionbank_file(
    questionbank_dir=Path("questionbank"),
    progress=progress  # ← 传递进度
)
```

---

## Qwen3-ASR 上下文增强说明

### 官方用法

**功能**: 通过提供上下文（Context），对专有词汇进行识别优化

**长度限制**: 不超过 10000 Token

**API 调用**: 通过 System Message 的 `text` 参数传入

**支持的文本类型**:
- 热词列表（多种分隔符格式）
- 任意格式与长度的文本段落
- 混合内容：词表与段落的任意组合
- 对无关文本的容错性极高

### 当前实现的格式

**位置**: `scripts/qwen_asr.py:371-414` (`build_context_text`)

**格式**:
```python
context = "Domain vocabulary: " + ", ".join(terms)
# 输出: "Domain vocabulary: 术语1, 术语2, 术语3, ..."
```

**示例输出** (修复后):
```
Domain vocabulary: simple(简单的、简易的、朴素的、简朴的), complete(完整的、完全的、彻底的), common(普通的、常见的)...
```

---

## 优先级建议

### 🔴 P0 - 紧急修复（影响核心功能）

1. **修复上下文提取的键名问题** (3.2 节)
   - 当前无法提取真正的单词/短语
   - 直接影响 ASR 准确率

2. **实现/修复 `find_vocabulary_file`** (问题 3)
   - 数据集模式完全无法工作
   - 会抛出 `NameError`

### 🟡 P1 - 重要功能（影响易用性）

3. **增加 `backend_input/` 批处理** (问题 1)
   - 当前需要手动逐个处理文件
   - 影响工作效率

4. **让数据集模式使用进度参数** (问题 5)
   - 当前使用固定优先级
   - 可能加载错误的题库

### 🟢 P2 - 优化改进（锦上添花）

5. **增强 fallback 机制** (问题 4)
   - 提高题库匹配成功率
   - 更好的容错性

---

## 测试建议

### 测试案例 1: 文件模式 + backend_input

```bash
# 测试单个文件
python scripts/qwen_asr.py --file backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

# 预期:
# 1. 解析出进度: R1-27-D2
# 2. 加载题库: questionbank/R1-27-D2.json
# 3. 提取正确的单词对（question/answer）
# 4. 生成正确的上下文
```

### 测试案例 2: 验证上下文提取

```python
# 手动测试
from scripts.qwen_asr import QwenASRProvider

provider = QwenASRProvider(api_key="test")
context = provider.load_vocabulary(Path("questionbank/R3-14-D4.json"))

# 验证 context 中包含:
# "simple(简单的...)", "complete(完整的...)"
# 而不是: "1(形容词)", "2(形容词)"
```

### 测试案例 3: 批量处理

```bash
# 测试批量处理所有 backend_input 文件
python scripts/qwen_asr.py --batch-backend-input

# 预期:
# 处理 backend_input/ 中的所有 .mp3 文件
# 每个文件自动加载对应题库
# 输出到 products/ 目录
```

---

## 总结

### 当前状态
- ✅ **文件名解析**: 可以提取题库标识，但缺少批处理
- ⚠️ **题库加载**: 文件模式正常，数据集模式有 bug
- ❌ **上下文提取**: **严重问题**，键名不匹配导致无法提取单词

### 关键问题
1. 🔴 上下文提取使用错误的键名（"问题/答案" vs "question/answer"）
2. 🔴 缺失 `find_vocabulary_file` 函数
3. 🟡 没有 `backend_input/` 批处理逻辑

### 修复后效果
- ✅ 能够从 `backend_input/` 文件名解析题库
- ✅ 能够从 `questionbank/` 动态加载正确的题库
- ✅ 能够提取题库中的单词/短语作为 Qwen ASR 上下文
- ✅ 显著提升 ASR 对专有词汇的识别准确率

---

## 相关文件

- 主脚本: `scripts/qwen_asr.py`
- 题库目录: `questionbank/`
- 输入目录: `backend_input/`
- 测试题库示例: `questionbank/R3-14-D4.json`
