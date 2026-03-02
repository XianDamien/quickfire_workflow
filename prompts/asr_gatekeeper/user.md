# 输入数据

### 1. `题库文件`
```json
{{ question_bank_json }}
```

### 2. `学生音频转录文本`
这是包含老师声音和学生回答的混合文本。
```text
{{ student_asr_text }}
```

# 处理指令
音频异常：

1. 判断是否是中英混合的asr，如果不是，请直接输出`FAIL` ，
2. 判断是否至少包含一对重复答案，如果不是，请直接输出`FAIL` 
示例：Juice果汁。这声好小。Milk是牛奶。他刚刚说tea茶。Cola可乐。Coffee咖啡。Beer是啤酒。Lemonade是柠檬汁……（该示例代表小朋友没有录到老师音频）
3. 判断是否遵循了整体的模式（问题字段只有一次，答案字段至少有一对是2次及以上）
示例：nephew nephew。侄子，外甥。侄子，外甥。wife wife。妻子。妻子。husband husband。丈夫。丈夫。people people。人们。人们。person person。人，是一个单数。guy guy。家伙。家伙。man man。男人。男人。人。woman woman。女人。女人。sir sir。先生，尊称。尊称……（该示例很明显代表学生没有提前回答，而是跟着老师音频在跟读）

题库选择错误：
1. 中翻英英翻中选反
提取前3-5个条目判断题库的question字段的语言，如果`answer`答案字段是英文，那么就是英翻中，否则就是中翻英。
由于`学生音频转录文本`包含老师声音和学生回答，所以属于`answer`答案字段的通常会出现不止一次，比如：mouse。老鼠。老鼠。elephant。大象。大象。tiger。老虎。老虎。lion。狮子。狮子。wolf。狼。狼。panda。熊猫。熊猫
这里很明显`answer`答案字段是中文，应该属于英翻中。

2. `学生音频转录文本`与题库条目内容不符，请直接输出`FAIL`

输出判定结果

只输出 JSON，不要额外解释。

# 输出要求

- 必须是严格的 JSON 格式
- 只包含 `status` ：`PASS`/`FAIL`字段
- 键和字符串值都必须使用双引号 `""`

# 输出示例

```json
{"status":"FAIL","issue_type":"WRONG_QUESTIONBANK"}
```
