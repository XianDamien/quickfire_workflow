# Qwen ASR 重构计划 - 支持 backend_input 直接处理

## 概述

重构 `scripts/qwen_asr.py` 以支持直接处理 `backend_input/` 目录中的音频文件，无需先将文件组织到 `archive/<dataset>/<student>/` 结构中。

**新的工作流程**：
```
backend_input/{ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3
                    ↓
            文件名解析 & 题库查找
                    ↓
    questionbank/{QuestionBank}.json
                    ↓
               asr/{StudentName}.json
           asr/{StudentName}_metadata.json
```

---

## 1. CLI 参数设计

### 新的命令行用法

```bash
# 单个文件处理
python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

# 批量处理 - 按班级 + 日期
python3 qwen_asr.py --class Abby61000 --date 2025-10-30

# 批量处理 - 按班级 + 日期 + 题库
python3 qwen_asr.py --class Abby61000 --date 2025-10-30 --question-bank R1-27-D2

# 处理所有文件（保留向后兼容）
python3 qwen_asr.py --all

# 处理特定学生名字（支持正则或通配）
python3 qwen_asr.py --student Benjamin --date 2025-10-30
```

### 新增 argparse 参数

```python
# 位置参数
parser.add_argument(
    'input_file',
    nargs='?',
    default=None,
    help='单个音频文件路径 (例如: backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3)'
)

# 可选参数
parser.add_argument('--class', dest='class_code', help='班级代码 (例如: Abby61000)')
parser.add_argument('--date', help='日期 (例如: 2025-10-30)')
parser.add_argument('--student', help='学生名字 (支持模糊匹配)')
parser.add_argument('--question-bank', help='题库代码 (例如: R1-27-D2)')
parser.add_argument('--all', action='store_true', help='处理 backend_input 中的所有文件')
```

---

## 2. 核心新增函数

### 2.1 `parse_audio_filename(filename: str) -> Dict[str, str]`

**功能**：解析 backend_input 中的音频文件名

**输入**：`Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3`

**输出**：
```python
{
    'class_code': 'Abby61000',
    'date': '2025-10-30',
    'question_bank': 'R1-27-D2',
    'student_name': 'Benjamin',
    'filename': 'Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3'
}
```

**实现要点**：
- 使用正则表达式：`r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)_(.+)\.mp3$'`
- 处理数字后缀（如 `...D6_1.mp3`，数字是段索引）
- 返回 None 如果格式不符

```python
import re
from typing import Optional, Dict

def parse_audio_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    解析 backend_input 音频文件名。

    格式: {ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3
    例如: Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

    Args:
        filename: 音频文件名（不含路径）

    Returns:
        解析结果字典，或 None 如果格式无效
    """
    # 移除数字后缀（用于分段的文件）
    base_name = re.sub(r'_\d+\.mp3$', '.mp3', filename)

    pattern = r'^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)_(.+)\.mp3$'
    match = re.match(pattern, base_name)

    if not match:
        return None

    class_code, date, question_bank, student_name = match.groups()

    return {
        'class_code': class_code,
        'date': date,
        'question_bank': question_bank,
        'student_name': student_name,
        'filename': filename
    }
```

### 2.2 `find_questionbank_file(question_bank_code: str) -> Optional[Path]`

**功能**：在 `questionbank/` 目录中查找题库文件，支持多级 fallback

**查找优先级**：
1. 精确匹配：`R1-27-D2.json`
2. 前缀匹配：`R1-27-D2*.json`（处理子版本）
3. 部分前缀：`R1-27-*.json`
4. 更短前缀：`R1-*.json`
5. 返回 None

```python
def find_questionbank_file(question_bank_code: str) -> Optional[Path]:
    """
    在 questionbank/ 目录中查找题库文件。
    支持多级 fallback 机制。

    Args:
        question_bank_code: 题库代码 (例如: R1-27-D2)

    Returns:
        题库文件 Path，或 None
    """
    project_root = Path(__file__).parent.parent
    questionbank_dir = project_root / "questionbank"

    if not questionbank_dir.exists():
        return None

    # 优先级 1: 精确匹配
    exact = questionbank_dir / f"{question_bank_code}.json"
    if exact.exists():
        return exact

    # 优先级 2: 前缀匹配 (R1-27-D2*)
    for f in questionbank_dir.glob(f"{question_bank_code}*.json"):
        if f.is_file():
            return f

    # 优先级 3: 去掉最后一个部分 (R1-27-D* → R1-27*)
    parts = question_bank_code.rsplit('-', 1)
    if len(parts) == 2:
        prefix = parts[0]
        for f in questionbank_dir.glob(f"{prefix}-*.json"):
            if f.is_file():
                return f

    # 优先级 4: 只保留前两个部分 (R1-27-D2 → R1-27)
    if '-' in question_bank_code:
        parts = question_bank_code.split('-')
        if len(parts) >= 2:
            short_code = f"{parts[0]}-{parts[1]}"
            short_file = questionbank_dir / f"{short_code}.json"
            if short_file.exists():
                return short_file

    return None
```

### 2.3 `discover_backend_files(class_code=None, date=None, student=None, question_bank=None) -> List[Path]`

**功能**：在 backend_input 目录中发现文件，支持多种过滤条件

```python
def discover_backend_files(
    class_code: Optional[str] = None,
    date: Optional[str] = None,
    student: Optional[str] = None,
    question_bank: Optional[str] = None
) -> List[Path]:
    """
    在 backend_input 目录中发现音频文件。

    支持按多个条件过滤。

    Args:
        class_code: 班级代码过滤 (例如: Abby61000)
        date: 日期过滤 (例如: 2025-10-30)
        student: 学生名字过滤
        question_bank: 题库代码过滤

    Returns:
        符合条件的音频文件路径列表
    """
    project_root = Path(__file__).parent.parent
    backend_input_dir = project_root / "backend_input"

    if not backend_input_dir.exists():
        return []

    files = []
    for f in backend_input_dir.glob("*.mp3"):
        parsed = parse_audio_filename(f.name)
        if not parsed:
            continue

        # 应用过滤条件
        if class_code and parsed['class_code'] != class_code:
            continue
        if date and parsed['date'] != date:
            continue
        if student and student.lower() not in parsed['student_name'].lower():
            continue
        if question_bank and parsed['question_bank'] != question_bank:
            continue

        files.append(f)

    return sorted(files)
```

### 2.4 `process_backend_file(audio_file_path: str, api_key=None) -> int`

**功能**：处理单个 backend_input 文件

```python
def process_backend_file(audio_file_path: str, api_key: Optional[str] = None) -> int:
    """
    处理单个 backend_input 音频文件。

    Args:
        audio_file_path: 音频文件完整路径
        api_key: DashScope API 密钥

    Returns:
        0 成功，1 失败
    """
    try:
        project_root = Path(__file__).parent.parent
        audio_file = Path(audio_file_path)

        if not audio_file.exists():
            print(f"❌ 文件不存在: {audio_file}")
            return 1

        # 解析文件名
        parsed = parse_audio_filename(audio_file.name)
        if not parsed:
            print(f"❌ 文件名格式无效: {audio_file.name}")
            print(f"   预期格式: {{ClassCode}}_{{Date}}_{{QuestionBank}}_{{StudentName}}.mp3")
            return 1

        student_name = parsed['student_name']

        # 检查是否已处理
        asr_dir = project_root / "asr"
        output_file = asr_dir / f"{student_name}.json"
        if output_file.exists():
            print(f"  ✓ {student_name}: 已处理过（跳过）")
            return 0

        # 查找题库
        vocab_file = None
        qb_code = parsed['question_bank']
        qb_path = find_questionbank_file(qb_code)
        if qb_path:
            vocab_file = str(qb_path)
            print(f"   📚 题库: {qb_path.name}")
        else:
            print(f"   ⚠️  未找到题库: {qb_code}")

        # 创建 ASR 提供者
        try:
            provider = QwenASRProvider(api_key=api_key)
        except ValueError as e:
            print(f"❌ 错误: {str(e)}")
            return 1

        # 创建输出目录
        asr_dir.mkdir(parents=True, exist_ok=True)

        # 转写并保存
        print(f"  ⟳ {student_name}: 处理音频...")
        response = provider.transcribe_and_save_with_segmentation(
            input_audio_path=str(audio_file),
            output_dir=str(asr_dir),
            vocabulary_path=vocab_file,
            output_filename=f"{student_name}.json",
            language="zh",
            segment_duration=180,
            max_workers=3,
        )

        # 保存元数据
        metadata = {
            "class_code": parsed['class_code'],
            "date": parsed['date'],
            "question_bank": parsed['question_bank'],
            "student": student_name,
            "audio_file": audio_file.name,
            "processed_at": datetime.datetime.now().isoformat(),
        }

        metadata_file = asr_dir / f"{student_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  ✓ {student_name}: 已保存到 asr/{student_name}.json")
        return 0

    except Exception as e:
        print(f"  ✗ 处理失败: {str(e)}")
        return 1
```

### 2.5 `process_backend_files_batch(class_code=None, date=None, student=None, question_bank=None, api_key=None) -> Tuple[int, int]`

**功能**：批量处理多个 backend_input 文件

```python
def process_backend_files_batch(
    class_code: Optional[str] = None,
    date: Optional[str] = None,
    student: Optional[str] = None,
    question_bank: Optional[str] = None,
    api_key: Optional[str] = None
) -> Tuple[int, int]:
    """
    批量处理 backend_input 中的音频文件。
    """
    files = discover_backend_files(
        class_code=class_code,
        date=date,
        student=student,
        question_bank=question_bank
    )

    if not files:
        print("❌ 没有找到符合条件的音频文件")
        return 0, 0

    print(f"\n{'='*60}")
    print(f"处理 {len(files)} 个文件")
    print(f"{'='*60}\n")

    processed = 0
    skipped = 0

    for audio_file in files:
        exit_code = process_backend_file(str(audio_file), api_key=api_key)
        if exit_code == 0:
            processed += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"处理完成！处理: {processed}, 失败: {skipped}")
    print(f"{'='*60}")

    return processed, skipped
```

---

## 3. 主函数修改

修改 `main()` 函数以支持新的 CLI 参数：

```python
def main():
    """
    主入口点 - 支持两种模式：
    1. 新模式：处理 backend_input 目录中的文件
    2. 旧模式：处理 archive/<dataset>/<student>/ 结构（向后兼容）
    """
    parser = argparse.ArgumentParser(
        description='Qwen ASR 批量转写工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 新模式 - 单个文件
  python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

  # 新模式 - 批量处理
  python3 qwen_asr.py --class Abby61000 --date 2025-10-30
  python3 qwen_asr.py --all

  # 旧模式 - 向后兼容
  python3 qwen_asr.py --dataset Zoe51530-9.8
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
        """
    )

    # 新模式参数
    parser.add_argument(
        'input_file',
        nargs='?',
        default=None,
        help='单个音频文件路径 (例如: backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3)'
    )

    parser.add_argument('--class', dest='class_code', help='班级代码 (例如: Abby61000)')
    parser.add_argument('--date', help='日期 (例如: 2025-10-30)')
    parser.add_argument('--student', help='学生名字')
    parser.add_argument('--question-bank', help='题库代码')
    parser.add_argument('--all', action='store_true', help='处理 backend_input 中的所有文件')

    # 旧模式参数（向后兼容）
    parser.add_argument('--dataset', help='数据集名称 (旧模式，例如: Zoe51530-9.8)')

    # 通用参数
    parser.add_argument(
        '--api-key',
        help='DashScope API 密钥 (可选，默认从环境变量读取)'
    )

    args = parser.parse_args()

    # 获取 API 密钥
    api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 DASHSCOPE_API_KEY 环境变量或通过 --api-key 传递")
        sys.exit(1)

    # 旧模式处理（向后兼容）
    if args.dataset:
        if args.student:
            exit_code = process_student(args.dataset, args.student, api_key=api_key)
            sys.exit(exit_code)
        else:
            processed, skipped = process_dataset(args.dataset, api_key=api_key)
            sys.exit(0 if (processed > 0 or skipped > 0) else 1)

    # 新模式处理
    if args.input_file:
        # 单个文件模式
        exit_code = process_backend_file(args.input_file, api_key=api_key)
        sys.exit(exit_code)

    elif args.all or (args.class_code or args.date or args.student or args.question_bank):
        # 批量模式
        processed, skipped = process_backend_files_batch(
            class_code=args.class_code,
            date=args.date,
            student=args.student,
            question_bank=args.question_bank,
            api_key=api_key
        )
        sys.exit(0 if (processed > 0 or skipped > 0) else 1)

    else:
        # 没有参数，提示用户
        parser.print_help()
        sys.exit(1)
```

---

## 4. 模块文档字符串更新

更新顶部的模块文档字符串：

```python
"""
Qwen3-ASR 音频转写系统 - 支持多种输入模式

【输入来源】
1. 新模式：backend_input/ 目录中的文件（推荐）
   - 文件格式：{ClassCode}_{Date}_{QuestionBank}_{StudentName}.mp3
   - 例如：Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
   - 题库自动从 questionbank/ 目录查找

2. 旧模式：archive/<dataset>/<student>/ 目录结构（向后兼容）
   - 音频来源：archive/<dataset>/<student>/1_input_audio.*

【输出结构】
统一输出到项目根目录的 asr/ 目录：
- asr/{学生名字}.json：Qwen ASR 转写结果（标准 API 响应格式）
- asr/{学生名字}_metadata.json：元数据（班级、日期、题库、处理时间）

【命令行用法】
  # 新模式
  python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3  # 单个文件
  python3 qwen_asr.py --class Abby61000 --date 2025-10-30  # 批量处理
  python3 qwen_asr.py --all  # 处理所有文件

  # 旧模式（向后兼容）
  python3 qwen_asr.py --dataset Zoe51530-9.8  # 转写指定数据集
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # 转写单个学生
"""
```

---

## 5. 需要修改的现有函数

### 5.1 `QwenASRProvider.transcribe_and_save_with_segmentation()`

**当前位置**：scripts/qwen_asr.py:515

**不需要修改**：已支持输出到任意 output_dir 和 output_filename

### 5.2 `should_process()`

**当前位置**：scripts/qwen_asr.py:896

**修改**：已适配新的输出目录结构（asr/{student_name}.json）

### 5.3 `find_vocabulary_file()`

**当前位置**：scripts/qwen_asr.py:814

**保留**：用于 archive 旧模式，但也可用于从 _shared_context 加载

---

## 6. 文件名输出规则

**关键决策**：如何避免 ASR 输出文件名冲突

**方案**：使用学生名字作为主键，加 metadata 记录完整信息

```
asr/Benjamin.json                    # 包含转写结果
asr/Benjamin_metadata.json           # {class_code, date, question_bank, student}
```

**优点**：
- 简单清晰
- 同一学生多次处理时，后处理覆盖前处理（可在 metadata 中看到）
- 与现有 archive 旧模式兼容

**潜在问题**：
- 如果不同班级有同名学生，会覆盖
- **解决方案**：可选择 `asr/{ClassCode}_{StudentName}.json` 格式

---

## 7. 测试计划

### 7.1 单文件处理测试

```bash
python3 qwen_asr.py backend_input/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3
# 验证：asr/Benjamin.json 和 asr/Benjamin_metadata.json 生成
```

### 7.2 批量处理 - 按班级 + 日期

```bash
python3 qwen_asr.py --class Abby61000 --date 2025-10-30
# 验证：处理 3 个文件 (Benjamin, Dana, Jeffery)
```

### 7.3 批量处理 - 按题库

```bash
python3 qwen_asr.py --date 2025-10-30 --question-bank R1-27-D3
# 验证：处理指定题库的所有文件
```

### 7.4 文件名解析边界情况

- 数字后缀：`...R1-27-D6_1.mp3`（分段文件）
- 中文学生名字：是否支持（需验证）
- 特殊字符：题库代码 `R1-27-D2` 中的连字符

### 7.5 向后兼容性

```bash
# 旧模式仍然工作
python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
```

---

## 8. 实现顺序

1. **第一阶段**：实现文件名解析和题库查找
   - `parse_audio_filename()`
   - `find_questionbank_file()`
   - 单元测试

2. **第二阶段**：实现文件发现和单文件处理
   - `discover_backend_files()`
   - `process_backend_file()`
   - 手动测试

3. **第三阶段**：实现批量处理和新 CLI
   - `process_backend_files_batch()`
   - 修改 `main()` 函数
   - 集成测试

4. **第四阶段**：向后兼容和文档
   - 保留旧模式入口
   - 更新模块文档
   - 性能测试

---

## 9. 关键变更总结

| 方面 | 旧模式 | 新模式 |
|------|--------|---------|
| 输入来源 | archive/<dataset>/<student>/ | backend_input/*.mp3 |
| 文件名解析 | 目录遍历 | 正则表达式解析 |
| 题库查找 | _shared_context/*.csv | questionbank/*.json |
| CLI 参数 | --dataset --student | input_file / --class --date |
| 输出位置 | asr/ | asr/（相同） |
| 输出文件名 | {StudentName}.json | {StudentName}.json |

---

## 10. 下一步行动

使用 `codex exec --full-auto` 命令执行重构：

```bash
codex exec --full-auto "按照 docs/qwen_asr_refactor_plan.md 中的计划重构 scripts/qwen_asr.py，
支持 backend_input 目录直接处理，实现新 CLI 参数，保持向后兼容性"
```
