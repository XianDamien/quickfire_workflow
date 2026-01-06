# ASR Gatekeeper 实现文档

## 概述

ASR Gatekeeper 是一个独立的质检模块,在 annotation pipeline 前检测题库选择错误和音频异常,避免浪费 LLM 资源。

## 实现架构

### 模块结构

```
scripts/gatekeeper/
├── __init__.py           # 模块导出
├── base.py               # 基础接口定义 (GatekeeperInput, GatekeeperOutput, BaseGatekeeper)
└── qwen_plus.py          # Qwen Plus 实现
```

### DAG 集成

新的 pipeline 流程:
```
audio → qwen_asr → gatekeeper → timestamps → cards
```

gatekeeper 阶段:
- **输入依赖**: 2_qwen_asr.json, 题库文件
- **输出**: PASS/FAIL 状态 (不保存文件)
- **行为**: FAIL 时阻止后续阶段继续

## 核心组件

### 1. GatekeeperInput / GatekeeperOutput

```python
@dataclass
class GatekeeperInput:
    archive_batch: str
    student_name: str
    question_bank_path: Path
    qwen_asr_path: Path
    verbose: bool = False
    question_bank_content: Optional[str] = None
    asr_text: Optional[str] = None

@dataclass
class GatekeeperOutput:
    status: str  # "PASS" or "FAIL"
    issue_type: Optional[str] = None  # "WRONG_QUESTIONBANK" or "AUDIO_ANOMALY"
    student_name: str = ""
    model: str = "unknown"
    response_time_ms: Optional[float] = None
```

### 2. QwenPlusGatekeeper

**模型配置**:
- 模型: qwen-plus
- Temperature: 0.1 (低温以获得稳定判断)
- Max retries: 3
- Retry delay: 5s

**主要方法**:
- `_load_prompts()`: 加载 system.md 和 user.md
- `_build_user_prompt()`: 填充模板变量
- `_call_api()`: 调用 Qwen API
- `_parse_response()`: 解析 JSON 响应
- `check()`: 执行质检逻辑

## Prompt 设计

### system.md

定义两种检测类型:

**1. 题库错误 (WRONG_QUESTIONBANK)**
- 情况A: 翻译方向错误
  - 题库 D3 (中→英): question="小孩" answer="kid"
  - 题库 D4 (英→中): question="kid" answer="小孩"
  - ASR 模式: "kid 小孩" (英在前，中在后)
  - 如果题库是 D3 但 ASR 显示英→中模式 → 错误
- 情况B: 词汇内容不匹配
  - 题库词汇在转写中大量缺失 (<50%)

**2. 音频异常 (AUDIO_ANOMALY)**
- 音频不完整、严重缺失
- 缺失老师声音
- 只有零散词语

### user.md

4步检测流程:
1. 检查题库翻译方向
2. 检查词汇匹配度
3. 检查音频完整性
4. 输出判定结果

## main.py 集成

### 1. DAG_STAGES 更新

```python
DAG_STAGES = ["audio", "qwen_asr", "gatekeeper", "timestamps", "cards"]
```

### 2. check_stage_complete() 更新

```python
elif stage == "gatekeeper":
    # gatekeeper 阶段：始终返回 False，每次都重新检查
    return False
```

### 3. run_gatekeeper() 函数

```python
def run_gatekeeper(
    archive_batch: str,
    student_name: str,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> bool:
    """执行 gatekeeper 阶段"""
    # 1. 检查依赖文件 (2_qwen_asr.json, 题库)
    # 2. 加载题库和 ASR 内容
    # 3. 创建 GatekeeperInput
    # 4. 执行检查
    # 5. 返回 True (PASS) 或 False (FAIL)
```

### 4. run_stage() 更新

```python
elif stage == "gatekeeper":
    verbose = annotator_kwargs.get("verbose", False) if annotator_kwargs else False
    success = run_gatekeeper(archive_batch, student_name, force, dry_run, verbose)
    return (success, None) if success else (False, "gatekeeper 质检失败 - 需人工干预")
```

## 使用方法

### 单独运行 gatekeeper

```bash
# 检查单个学生
python3 scripts/main.py --archive-batch Abby61000_2025-11-05 --student Benjamin --only gatekeeper

# 检查整个批次
python3 scripts/main.py --archive-batch Abby61000_2025-11-05 --only gatekeeper
```

### 作为 pipeline 一部分

```bash
# 运行完整 pipeline (包含 gatekeeper)
python3 scripts/main.py --archive-batch Abby61000_2025-11-05 --target cards

# gatekeeper FAIL 时会自动停止，不继续后续阶段
```

### dry-run 模式

```bash
python3 scripts/main.py --archive-batch Abby61000_2025-11-05 --only gatekeeper --dry-run
```

## 测试结果

### 测试用例 1: Benjamin (Abby61000_2025-11-05)

**数据**:
- 题库: R1-27-D3.json (中→英)
  - question: "小孩" → answer: "kid"
- ASR: "字表二十七英翻中。kid kid 呃小孩。小孩。pupil 小学生，瞳孔..."
  - 模式: 英在前，中在后 (英翻中)

**结果**: ✓ FAIL - WRONG_QUESTIONBANK

**分析**:
- 题库方向: 中→英 (question=中文, answer=英文)
- ASR 模式: 英→中 (英文在前，中文在后)
- **判断正确**: 题库选择错误，应该用 R1-27-D4.json

### 测试用例 2: Oscar (Zoe41900_2025-09-08)

**数据**:
- 题库: R1-65-D5.json (中→英)
  - question: "不" → answer: "not"
- ASR: "Not. Not. 双倍的，双的。一半，半。 Half. 角色，部分。 Part, part..."
  - 模式: 混合，不一致

**结果**: PASS

**分析**:
- ASR 模式不够清晰，无法准确判断翻译方向
- gatekeeper 采用保守策略，选择 PASS（避免误杀）
- **合理行为**: 仅在有明确证据时才返回 FAIL

## 关键特性

### 1. 独立模块设计

- 完全独立于 annotators 模块
- 遵循 BaseGatekeeper 接口
- 易于扩展（可添加其他模型实现）

### 2. 保守策略

- 明确错误 → FAIL
- 模糊情况 → PASS
- API 失败 → FAIL（保守处理）

### 3. DAG 集成

- 自动依赖检查（需要 qwen_asr 完成）
- FAIL 时阻止后续阶段
- 每次都重新执行（不缓存结果）

### 4. 详细输出

```
[执行] gatekeeper -> Benjamin
  [✗] gatekeeper FAIL - WRONG_QUESTIONBANK (1.72s)
      问题类型: WRONG_QUESTIONBANK
      建议: 检查题库选择是否正确（翻译方向或词汇内容）
```

## 文件清单

**核心实现**:
- `scripts/gatekeeper/__init__.py`
- `scripts/gatekeeper/base.py`
- `scripts/gatekeeper/qwen_plus.py`
- `scripts/main.py` (已修改)

**Prompts**:
- `prompts/asr_gatekeeper/system.md`
- `prompts/asr_gatekeeper/user.md`
- `prompts/asr_gatekeeper/metadata.json`

**文档**:
- `docs/asr_gatekeeper_test_cases.md`
- `docs/asr_gatekeeper_prompt_design.md`
- `docs/gatekeeper_implementation.md` (本文档)

**测试**:
- `test_gatekeeper.py`

## 未来改进

1. **保存检查结果**
   - 可选保存 gatekeeper 结果到 JSON 文件
   - 用于分析和统计

2. **多模型支持**
   - 添加其他 LLM 实现（如 Gemini）
   - 对比不同模型的检测能力

3. **详细诊断信息**
   - 返回更详细的匹配度分数
   - 提供具体的修复建议

4. **批量报告**
   - 生成批次级别的质检报告
   - 统计各类问题的分布

## 总结

ASR Gatekeeper 成功实现并集成到 pipeline 中,能够有效检测题库选择错误,避免浪费 LLM annotation 资源。测试结果表明其能准确识别明显的翻译方向错误,同时采用保守策略避免误杀。
