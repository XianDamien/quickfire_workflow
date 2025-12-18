# 输入数据

### 1. 这是本次的题库
```text
{{ question_bank_json }}
```

### 2. 学生音频转录文本
这是包含老师声音和学生回答的混合文本。
```text
{{ student_asr_text }}
```

### 3. 学生带时间戳的音频转录文本

```text
{{ student_asr_with_timestamp }}
```


# 处理指令
1. 请遍历"题库"中的每一个词条。-----对于每个词条,在"学生音频转录文本"中定位到对应的"问题"文本和"答案"文本。
2. 本次题库包含"问题"和"答案",以及出现的顺序,老师录音就是直接按照顺序念题库.
3. **提取** 位于"问题"和"答案"之间的所有文本内容,作为"学生回答"。
4. **核心任务1**：检查`detected_answer(学生回答)`中是否至少有一个词的意思跟`expected_answer(答案)`中某个词的意思是相似的(充分利用你的泛化能力,不要太严格)，如果学生的回答与标准答案不相关/错误,请把issue_type标记为'MEANING_ERROR'；如果在"问题"和"答案"间没有找到任何实质性的回答文本,请将'expected_answer'输出为null, issue_type则为'NO_ANSWER';
5. **核心任务2**: 根据{{ question_bank_json }}、利用{{ student_asr_with_timestamp }}给出的词级别的时间戳，大概估算出每道题的问题出现的时间戳，注意只需要估算每个问题卡的`question（问题）`开始的时间点即可，输出为`card_timestamp`字段。



# 输出格式要求
- 输出必须是严格的、格式正确的 JSON 数组。
- 数组中的每个对象都必须包含 `card_index`, `question(问题)`,`card_timestamp（问题时间戳）`， `detected_answer(学生回答)`, `expected_answer(答案)` 四个键。
- 键和字符串值都必须使用双引号 `""`.



**输出示例:**
```json
{
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
