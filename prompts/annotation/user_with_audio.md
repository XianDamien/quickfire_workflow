# 输入数据

### 1. `题库文件`
```text
{{ question_bank_json }}
```

### 2. `学生音频转录文本`
这是包含老师声音和学生回答的混合文本。
```text
{{ student_asr_text }}
```

### 3. `作业音频` 

```json
{{ student_input_audio }}
```



# 处理指令

## 第一步：前置校验（validation）

在进行标注之前，先检查输入数据是否有效。检测以下4种错误：

| 错误类型 | 错误码 | 判断方法 |
|---------|--------|---------|
| 题库内容不匹配 | `WRONG_QUESTIONBANK` | ASR文本中能匹配到题库的条目比例过低（<50%） |
| 没录到老师音频 | `NO_TEACHER_AUDIO` | 答案字段没有重复出现（正常应该是：学生答1次 + 老师答1次 = 至少2次） |
| 学生跟读 | `STUDENT_FOLLOWING` | 问题字段也出现2次（学生跟着念问题，而不是提前回答） |

**正常模式**：`问题1次 → 学生回答 → 老师念答案` = 问题1次，答案至少2次

**异常示例**：
- `Juice果汁。Milk牛奶。Cola可乐。` → 每个答案只1次 = `NO_TEACHER_AUDIO`
- `nephew nephew。侄子。侄子。wife wife。妻子。妻子。` → 问题重复2次 = `STUDENT_FOLLOWING`

如果检测到任何错误，`validation.status` 设为 `FAIL`，并在 `errors` 数组中列出所有错误码。

---

## 第二步：标注处理

1. 本次题库包含`question（问题）`、`hint（提示，可能为空）`和`expected_answer(答案)`/`answer（答案）`,每个题库文件包含多个题目，`card_index(题目索引)`是老师录音念题目的顺序，每个题目一般的顺序为先念`question（问题）`，再念`hint（提示，可能为空）`，中间留空让学生回答，最后揭晓`expected_answer(答案)`/`answer（答案）`,在`学生音频转录文本`（只能从这个来源）中定位到对应的`question（问题）`文本和`expected_answer(答案)`文本，注意，学生可能在`question（问题）`和`expected_answer(答案)`/`answer（答案）`之间的任何时间说出我们需要的`detected_answer(学生回答)`。

2. **提取** 位于`学生音频转录文本`当中，`question（问题）`和`expected_answer(答案)`之间的所有文本内容,作为`detected_answer(学生回答)`。
3. **核心任务1**：检查`detected_answer(学生回答)`中是否至少有一个词的意思跟`expected_answer(答案)`中某个词的意思是相似的(充分利用你的泛化能力,不要太严格)，如果学生的回答与标准答案不相关/错误,请把issue_type标记为'MEANING_ERROR'；如果在"问题"和"答案"间没有找到任何实质性的回答文本,请将'expected_answer'输出为null, issue_type则为'NO_ANSWER';
4. **核心任务2**: 注意，学生转录有时会因为声音重叠等原因无法捕捉到学生的回答，请以asr和题库文件作为参照，直接读取整个输入的`作业音频` ，精确定位到每道题的`question（问题）`字段出现的时间戳。输出为 `card_timestamp` 字段（格式如 "00:17"），当无法确定时间戳时且确认学生有输出时，请返回估算值。



# 输出格式要求
- 输出必须是严格的、格式正确的 JSON 对象
- **必须包含 `validation` 字段**，包含 `status`（PASS/FAIL）和 `errors` 数组
- 如果 `validation.status` 为 FAIL，则 `annotations` 为空数组，`final_grade_suggestion` 和 `mistake_count` 为 null
- 如果 `validation.status` 为 PASS，则继续输出完整标注结果
- `annotations` 数组中的每个对象必须包含 `card_index`, `question`, `card_timestamp`, `expected_answer`, `related_student_utterance`
- 键和字符串值都必须使用双引号 `""`
- 注意 `detected_answer(学生回答)`必须来源于`学生音频转录文本`，不能来源于`带时间戳的音频转录文本`
- 注意 `detected_answer(学生回答)`不能包含老师说的`hint（提示，可能为空）`，需要精确识别和提取学生`detected_answer(学生回答)`的回答。



**输出示例:**
```json
{
    "validation": {
      "status": "PASS",
      "errors": []
    },
    "final_grade_suggestion": "B",
    "mistake_count": {
      "errors": 2
    },
    "annotations": [
      {
        "card_index": 1,
        "card_timestamp":"00:17",
        "question": "不",
        "expected_answer": "not",
        "related_student_utterance": {
          "detected_text": null,
          "issue_type":"NO_ANSWER"
        }
      },
      {
        "card_index": 2,
        "card_timestamp":"00:19",
        "question": "双倍的；双的",
        "expected_answer": "double",
        "related_student_utterance": {
          "detected_text": "double",
          "issue_type": null
        }
      },
      {
        "card_index": 3,
        "card_timestamp":"00:23",
        "question": "list，及物动词",
        "expected_answer": "把……列成表；列举",
        "related_student_utterance": {
          "detected_text": "清单，目录。",
          "issue_type": "MEANING_ERROR"
        }
      }
    ]
  }
```

**校验失败时的输出示例:**
```json
{
    "validation": {
      "status": "FAIL",
      "errors": ["WRONG_QUESTIONBANK"]
    },
    "final_grade_suggestion": null,
    "mistake_count": null,
    "annotations": []
  }
```
