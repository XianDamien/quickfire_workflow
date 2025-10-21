# 学生回答提取功能规格说明

## ADDED Requirements

### Requirement 1: 数据输入处理
**新增** 学生回答提取功能需要支持多种输入数据格式的加载和解析。

#### Scenario: 加载教师转录模板
```python
# 当系统需要处理教师转录模板时
# 应该能够读取并解析 archive/Zoe51530-9.8/_shared_context/R3-14-D4_transcription.txt
teacher_transcript = load_teacher_transcript(
    "archive/Zoe51530-9.8/_shared_context/R3-14-D4_transcription.txt"
)
# 期望获得包含问题和答案顺序的结构化数据
assert teacher_transcript.contains_questions_and_answers()
```

#### Scenario: 加载题库数据
```python
# 当系统需要加载题库时
# 应该能够解析 archive/Zoe51530-9.8/_shared_context/R3-14-D4.json
question_bank = load_question_bank(
    "archive/Zoe51530-9.8/_shared_context/R3-14-D4.json"
)
# 期望获得包含 id、问题、答案的字典列表
assert all(hasattr(q, 'id') and hasattr(q, '问题') and hasattr(q, '答案') for q in question_bank)
```

#### Scenario: 加载学生 ASR 结果
```python
# 当系统需要处理学生 ASR 结果时
# 应该能够从 archive/Zoe51530-9.8/Phoebe/2_qwen_asr.json 提取文本
student_asr = load_student_asr("archive/Zoe51530-9.8/Phoebe/2_qwen_asr.json")
# 期望获得纯文本转录内容
assert isinstance(student_asr.text, str)
assert len(student_asr.text) > 0
```

### Requirement 2: LLM 提示词集成
**新增** 系统需要集成 prompts/annotation.txt 中的提示词模板来指导 Gemini LLM 进行学生回答提取。

#### Scenario: 构建完整提示词
```python
# 当系统需要构建 LLM 提示词时
# 应该将模板和数据组合成完整的提示词
prompt_template = load_prompt_template("prompts/annotation.txt")
full_prompt = build_annotation_prompt(
    template=prompt_template,
    question_bank=question_bank,
    teacher_transcript=teacher_transcript,
    student_asr=student_asr
)
# 期望提示词包含所有必要的数据和指令
assert "题库" in full_prompt
assert "老师音频转录文本" in full_prompt
assert "学生音频转录文本" in full_prompt
```

#### Scenario: Gemini API 调用
```python
# 当系统需要调用 Gemini LLM 时
# 应该使用现有的 gemini_client.py 架构
from scripts.gemini_client import OptimizedGeminiClient
client = OptimizedGeminiClient(config)
response = client.generate_json(prompt=full_prompt)
# 期望获得结构化的 JSON 回答
assert isinstance(response, dict) or isinstance(response, list)
```

### Requirement 3: 学生回答内容提取
**新增** 系统需要能够从学生 ASR 文本中准确提取每个问题的学生回答内容。

#### Scenario: 问题-答案对匹配
```python
# 当系统需要匹配问题和答案时
# 应该能够在学生 ASR 文本中识别问题和答案的位置
matches = find_question_answer_pairs(
    student_text=student_asr.text,
    question_bank=question_bank,
    teacher_template=teacher_transcript
)
# 期望找到所有问题的对应位置
assert len(matches) == len(question_bank)
```

#### Scenario: 回答内容提取
```python
# 当系统需要提取学生回答时
# 应该能够提取问题和答案之间的文本内容
for match in matches:
    student_answer = extract_student_answer(
        student_text=student_asr.text,
        question_start=match.question_position,
        answer_start=match.answer_position
    )
    # 期望获得有效的回答内容或"未作答"标记
    assert student_answer is not None
    if not student_answer.strip():
        student_answer = "未作答"
```

### Requirement 4: 结构化输出生成
**新增** 系统需要生成符合指定格式的 JSON 输出文件。

#### Scenario: JSON 结果构建
```python
# 当系统需要生成输出结果时
# 应该构建包含所有必需字段的 JSON 对象
annotations = []
for i, question in enumerate(question_bank, 1):
    annotation = {
        "card_index": i,
        "问题": question.问题,
        "学生回答": extracted_answers[i-1],
        "答案": question.答案
    }
    annotations.append(annotation)
# 期望每个对象都包含四个必需字段
assert all(
    all(key in ann for key in ["card_index", "问题", "学生回答", "答案"])
    for ann in annotations
)
```

#### Scenario: 输出文件保存
```python
# 当系统需要保存结果时
# 应该将 JSON 结果保存到指定位置
output_path = "archive/Zoe51530-9.8/Phoebe/4_llm_annotation.json"
save_annotation_result(annotations, output_path)
# 期望文件被正确保存且格式正确
import json
with open(output_path, 'r', encoding='utf-8') as f:
    saved_data = json.load(f)
assert isinstance(saved_data, list)
```

### Requirement 5: 错误处理和边界情况
**新增** 系统需要能够处理各种错误情况和边界条件。

#### Scenario: 未作答处理
```python
# 当学生在问题和答案之间没有实质性回答时
# 应该标记为"未作答"
empty_answer = extract_student_answer(
    student_text="simple 答案：简单的",
    question_start=0,
    answer_start=8
)
# 期望返回"未作答"
assert empty_answer == "未作答"
```

#### Scenario: 匹配失败处理
```python
# 当无法在学生文本中找到问题或答案时
# 应该使用默认标记或跳过处理
try:
    match = find_question_in_text("complex", student_text)
except QuestionNotFoundError:
    # 标记为"未作答"或使用默认值
    handle_missing_question("complex")
```

#### Scenario: API 错误处理
```python
# 当 Gemini API 调用失败时
# 应该使用现有的重试和错误处理机制
try:
    response = client.generate_json(prompt=full_prompt)
except APIError as e:
    # 记录错误并返回空结果或错误信息
    log_error(f"Gemini API 调用失败: {e}")
    return empty_annotation_result()
```

### Requirement 6: 性能和兼容性
**新增** 系统需要满足性能要求并保持与现有架构的兼容性。

#### Scenario: 处理时间限制
```python
# 当处理单个学生文件时
# 应该在合理时间内完成处理
import time
start_time = time.time()
annotations = extract_student_annotations(
    teacher_path="archive/Zoe51530-9.8/_shared_context/R3-14-D4_transcription.txt",
    question_bank_path="archive/Zoe51530-9.8/_shared_context/R3-14-D4.json",
    student_asr_path="archive/Zoe51530-9.8/Phoebe/2_qwen_asr.json"
)
processing_time = time.time() - start_time
# 期望处理时间不超过 30 秒
assert processing_time < 30
```

#### Scenario: 架构兼容性
```python
# 当集成到现有系统时
# 应该保持与现有 gemini_client.py 的兼容性
from scripts.gemini_client import OptimizedGeminiClient, GeminiConfig
config = GeminiConfig.from_env()
client = OptimizedGeminiClient(config)
# 期望客户端能够正常初始化和使用
assert client is not None
assert hasattr(client, 'generate_json')
```