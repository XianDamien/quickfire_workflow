# 设计文档: 工作流可观测性增强

## 架构概述

当前工作流中，AI 处理的数据流向如下：

```
1. 音频文件
   ↓ [transcribe_audio]
   → ASR 原始文本（当前隐藏）
   ↓ [load_asr_data]
   → ASR JSON 对象

2. 题库 CSV
   ↓ [load_qb]
   → 题库 JSON 对象

3. ASR JSON + 题库 JSON + system_prompt
   ↓ [evaluate_pronunciation]
   → 评测 AI 调用（当前提示词隐藏）
   → 评测结果 JSON（当前仅返回不输出）
```

### 可观测性缺口
- **ASR 转写结果**: `transcribe_audio()` 返回文本后，直接传递，未在控制台展示
- **评测提示词**: `evaluate_pronunciation()` 内部构造的三层 prompt，对用户完全隐藏
- **评测中间过程**: AI 返回的完整 JSON，仅保存或打印，未格式化展示

## 实现方案

### 方案 A: 在 workflow.py 中增加输出（推荐）

**优点**:
- 不修改核心函数 (`qwen3.py`, `captioner_qwen3.py`)，保持模块独立性
- 输出逻辑集中在工作流层，便于维护和扩展
- 符合单一职责原则

**实现步骤**:
1. 在 `run_workflow()` 的关键步骤后，添加格式化输出
2. 创建辅助函数（如 `print_section()`, `format_json()`) 处理格式化
3. 输出点：
   - ASR 转写完成后 → 输出 ASR 原始文本
   - 加载题库完成后 → 输出题库摘要（行数、字段）
   - 评测前 → 输出三层提示词结构
   - 评测完成后 → 输出最终 JSON（已格式化）

### 方案 B: 在各模块函数中增加输出参数

**优点**:
- 模块自身可控输出

**缺点**:
- 破坏模块独立性，增加耦合
- 函数签名变更，影响向后兼容

**不推荐使用此方案**。

## 采用方案 A 的具体设计

### 1. ASR 转写结果输出

```python
# 在 transcribe_audio() 之后
print("\n" + "=" * 60)
print("📄 ASR 转写原始结果")
print("=" * 60)
print(asr_result)
```

### 2. 题库摘要输出

```python
# 在 load_qb() 之后
print("\n" + "=" * 60)
print("📚 题库摘要")
print("=" * 60)
# 解析 CSV，显示行数、字段
lines = qb_data.strip().split('\n')
print(f"题库条目数: {len(lines) - 1}")  # 去掉 header
print(f"字段: {lines[0] if lines else 'N/A'}")
```

### 3. 评测提示词输出

```python
# 在 evaluate_pronunciation() 调用前
print("\n" + "=" * 60)
print("💬 AI 评测提示词结构")
print("=" * 60)

# 打印三层 prompt
print("\n[Layer 1] System Prompt (系统角色定义)")
print("-" * 40)
print(system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt)

print("\n[Layer 2] Question Bank Prompt (题库上下文)")
print("-" * 40)
print(qb_prompt[:300] + "..." if len(qb_prompt) > 300 else qb_prompt)

print("\n[Layer 3] ASR Data Prompt (ASR 识别结果)")
print("-" * 40)
print(asr_prompt[:300] + "..." if len(asr_prompt) > 300 else asr_prompt)
```

### 4. 评测结果输出

```python
# 在 evaluate_pronunciation() 返回后
print("\n" + "=" * 60)
print("📊 AI 评测原始结果 (JSON)")
print("=" * 60)
try:
    result_json = json.loads(evaluation_result)
    print(json.dumps(result_json, indent=2, ensure_ascii=False))
except json.JSONDecodeError:
    print(evaluation_result)
```

## 可选扩展：详细程度控制

未来可添加命令行标志：

```bash
# 默认行为（显示所有中间结果）
python3 workflow.py --audio-path ... --qb-path ...

# 生产模式（仅显示最终结果）
python3 workflow.py --audio-path ... --qb-path ... --quiet

# 超详细模式（显示完整的 system_prompt 等）
python3 workflow.py --audio-path ... --qb-path ... --verbose
```

### 实现建议
- 添加 `--verbose` 和 `--quiet` 标志到 argparse
- 在关键输出点检查标志，条件输出
- 默认行为：中等详细程度（当前推荐的可观测性水平）

## 对现有代码的影响

### 修改范围
- **workflow.py**:
  - 在 `run_workflow()` 的 5 个关键步骤后添加输出语句
  - 添加若干辅助函数用于格式化
  - 若实现详细程度控制，则修改 `main()` 中的 argparse

- **qwen3.py**: 无修改（保持独立模块）
- **captioner_qwen3.py**: 无修改（保持独立模块）

### 向后兼容性
✅ 完全兼容
- 现有函数签名不变
- 新增输出仅影响控制台显示，不影响返回值
- 已有的模块级直接调用（如 `from qwen3 import evaluate_pronunciation`) 继续正常工作

## 数据流示意

```
工作流执行流程（带可观测性输出）

┌─────────────────────────────────┐
│ 第1步: 验证输入参数              │
│ → 音频文件、题库文件检查          │
└─────────────────────────────────┘
                ↓
┌─────────────────────────────────┐
│ 第2步: 音频转写 (ASR)            │
│ → 调用 transcribe_audio()        │
│ → [输出] ASR 原始文本             │ ← 可观测性输出点 1
└─────────────────────────────────┘
                ↓
┌─────────────────────────────────┐
│ 第3步: 加载题库数据              │
│ → 调用 load_qb()               │
│ → [输出] 题库摘要                │ ← 可观测性输出点 2
└─────────────────────────────────┘
                ↓
┌─────────────────────────────────┐
│ 第4步: AI 评测                  │
│ → [输出] 提示词结构               │ ← 可观测性输出点 3
│ → 调用 evaluate_pronunciation()  │
│ → [输出] 评测 JSON 结果           │ ← 可观测性输出点 4
└─────────────────────────────────┘
                ↓
┌─────────────────────────────────┐
│ 第5步: 输出评测报告              │
│ → 保存或打印最终结果              │
└─────────────────────────────────┘
```

## 测试策略

1. **功能测试**: 验证所有可观测性输出正确显示
2. **集成测试**: 端到端工作流仍正常工作
3. **边界情况**: 处理 JSON 解析失败时的降级输出
4. **性能验证**: 新增输出不显著影响性能

## 时间估算

- 实现基础可观测性输出: ~30 分钟
- 添加详细程度控制（可选）: ~20 分钟
- 测试验证: ~15 分钟

**总计**: ~1 小时

## 风险评估

**低风险**，原因：
- 仅添加输出语句，不修改核心逻辑
- 不改变函数签名和返回值
- 可以轻松回滚
