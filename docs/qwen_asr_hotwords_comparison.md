# Qwen ASR 热词效果对比分析报告

**生成时间**: 2026-01-04

## 概览

- **总对比样本数**: 25 个学生
- **结果相同**: 7 个 (28.0%)
- **结果有差异**: 18 个 (72.0%)

- **平均相似度**: 85.83%

## 各批次统计

| 批次 | 样本数 | 相同数 | 有差异数 | 平均相似度 |
|------|--------|--------|----------|------------|
| Niko60900_2025-10-12 | 5 | 2 | 3 | 73.24% |
| Niko60900_2025-11-14 | 1 | 0 | 1 | 73.74% |
| Niko60900_2025-11-19 | 1 | 1 | 0 | 100.00% |
| Niko60900_2025-12-15 | 4 | 0 | 4 | 72.52% |
| Zoe41900_2025-09-08 | 6 | 3 | 3 | 94.39% |
| Zoe41900_2025-10-24 | 4 | 0 | 4 | 98.24% |
| Zoe41900_2025-11-20 | 4 | 1 | 3 | 89.12% |

## 关键发现

### 1. 热词对转写结果的影响

- **结果相同的案例** (7/25, 28%):
  - 主要出现在语音清晰、词汇发音标准的场景
  - 热词在这种情况下影响不大

- **结果有差异的案例** (18/25, 72%):
  - 差异主要体现在以下几个方面:

### 2. 差异类型分析

**案例 1: 大小写和标点符号差异**

- 批次: Niko60900_2025-12-15, 学生: Zoe
- 有热词: `Housework. Housework. 整理收拾。Tidy. Tidy. 整洁的，整齐的。Tidy. Tidy. 打扫清除。专门有个扫的感觉是什么？Sweep. 洗。Wash. Wash. 清扫清洁。Clean. Clean. 干净的。Clean. Clean. 刷子。Brush. Brush. 刷，用刷子刷。Brush.`
- 无热词: `Housework. Housework. 整理收拾. tidy. tidy. 整洁的，整齐的. tidy. tidy. 打扫清除. 专门有个扫的感觉是什么？sweep. 洗. wash. wash. 清扫清洁. clean. clean. 干净的. clean. clean. 刷子. brush. brush. 刷，用刷子刷. brush.`
- **分析**: 热词版本保持了首字母大写，无热词版本全部小写

**案例 2: 词汇重复度差异**

- 批次: Niko60900_2025-10-12, 学生: Beta
- 有热词: `脚放下来，尊重老师姿势。老鼠。大象。老虎。狮子。狼。熊猫。猴子。`
- 无热词: `脚放下来，尊重老师姿势。老鼠。大象。大象。Tiger。老虎。老虎。Lion。狮子。狮子。Wolf。狼。狼。Panda。熊猫。熊猫。Monkey。猴子。猴子。`
- **分析**: 无热词版本包含更多词汇重复和英语原词，热词版本更简洁

**案例 3: 完全不同的转写**

- 批次: Niko60900_2025-10-12, 学生: Nemo
- 有热词: `Elephant, Lion, Monkey, Mouse, Panda, Tiger, Wolf, 大象, 熊猫, 狮子, 狼, 猴子, 老虎, 老鼠。`
- 无热词: `单词表十一，英翻中。mouse，老鼠。老鼠。elephant，大象。大象。tiger，老虎。老虎。lion，狮子。狮子。wolf，狼。狼。panda，熊猫。熊猫。monkey，猴子。猴子。`
- **分析**: 热词版本只输出词汇列表，无热词版本包含完整的练习引导语

### 3. 文本长度对比

- **有热词平均长度**: 201 字符
- **无热词平均长度**: 203 字符
- **差异**: -2 字符 (-0.8%)

## 建议

1. **建议使用热词**: 对于词汇练习场景，热词可以提高关键词的识别准确率
2. **注意格式差异**: 热词可能影响输出的大小写格式，需要在后处理中统一
3. **A/B 测试**: 对于重要的评估，建议同时使用有/无热词进行对比验证

## 详细数据

### Niko60900_2025-10-12 - Nemo
- 相似度: 21.05%
- 文本长度: 77 vs 94 字符
- 有热词: `Elephant, Lion, Monkey, Mouse, Panda, Tiger, Wolf, 大象, 熊猫, 狮子, 狼, 猴子, 老虎, 老鼠。`
- 无热词: `单词表十一，英翻中。mouse，老鼠。老鼠。elephant，大象。大象。tiger，老虎。老虎。lion，狮子。狮子。wolf，狼。狼。panda，熊猫。熊猫。monkey，猴子。猴子。`

### Niko60900_2025-12-15 - Nemo
- 相似度: 47.36%
- 文本长度: 240 vs 233 字符
- 有热词: `家。 housework h o u s e w o r k housework 整理收拾 tidy t i d y tidy 整洁的整齐的 tidy t i d y tidy 打扫清除 sweep ...`
- 无热词: `家。housework H O U S E W O R K housework 整理收拾。tidy T I D Y tidy 整洁的整齐的。tidy T I D Y tidy 打扫清除。所以 S W ...`

### Niko60900_2025-10-12 - Beta
- 相似度: 58.18%
- 文本长度: 32 vs 78 字符
- 有热词: `脚放下来，尊重老师姿势。老鼠。大象。老虎。狮子。狼。熊猫。猴子。`
- 无热词: `脚放下来，尊重老师姿势。老鼠。大象。大象。Tiger。老虎。老虎。Lion。狮子。狮子。Wolf。狼。狼。Panda。熊猫。熊猫。Monkey。猴子。猴子。`

### Zoe41900_2025-11-20 - sophia
- 相似度: 71.25%
- 文本长度: 161 vs 159 字符
- 有热词: `单词表三十八中翻英。地方、地点、场所。Place. Place. 房间。Room. Room. 卧室。Bedroom. Bedroom. Kitchen. Kitchen. 浴室、卫生间。Bathro...`
- 无热词: `单词表三十八中翻英。地方、地点、场所，place。place。房间，room。room。卧室，bedroom。bedroom。bedroom。厨房，kitchen。kitchen。浴室、卫生间，bat...`

### Niko60900_2025-11-14 - Yiyi
- 相似度: 73.74%
- 文本长度: 387 vs 386 字符
- 有热词: `单词表十五中翻英。勺子 spoon。 spoon。盘子 菜品 佳肴。This this plate what hot plate what hot plate what hot dish plate ...`
- 无热词: `单词表十五中翻英。勺子 spoon。 spoon。盘子、菜品、佳肴。This this plate what pot plate what pot plate what pot dish plate ...`

### Zoe41900_2025-09-08 - Cathy
- 相似度: 74.29%
- 文本长度: 167 vs 183 字符
- 有热词: `不，not。not。双倍的，双的。呃，double double。一半，半。half。half。角色，部分。part。part。形容词，两个的。呃，both both。代词，两者。both。both。...`
- 无热词: `Not. Not. 双倍的，双的。嗯，double double. 一半，半。Half. Half. 角色，部分。Part. Part. 形容词，两个的。嗯，both both. 代词，两者。Both...`

### Niko60900_2025-12-15 - Jean
- 相似度: 75.90%
- 文本长度: 158 vs 174 字符
- 有热词: `家务 housework housework 整理收拾 tidy tidy 整洁的整齐的 tidy tidy 打扫清除，专门有个扫的感觉是什么？ sweep 洗 wash wash 清扫清洁 clea...`
- 无热词: `家务。Housework. Housework. 整理收拾。Tidy. Tidy. 整洁的，整齐的。Tidy. Tidy. 打扫清除。哎，对，专门有个扫的感觉是什么？扫帚。洗。Wash. Wash. ...`

### Niko60900_2025-12-15 - Elsa
- 相似度: 82.29%
- 文本长度: 187 vs 163 字符
- 有热词: `做题视频。家务。Housework. 整理收拾。Tidy. Tidy. 整洁的，整齐的。Tidy. Tidy. 打扫，清除。Sweep. 专门有个扫的感觉。Sweep. Sweep. 洗。Wash. ...`
- 无热词: `做题视频。家务。Housework. 整理收拾。tidy tidy 整洁的，整齐的。tidy tidy 打扫清除。sweep 专门有个扫的感觉。sweep sweep 洗。wash wash 清扫清洁...`

### Niko60900_2025-12-15 - Zoe
- 相似度: 84.52%
- 文本长度: 164 vs 172 字符
- 有热词: `Housework. Housework. 整理收拾。Tidy. Tidy. 整洁的，整齐的。Tidy. Tidy. 打扫清除。专门有个扫的感觉是什么？Sweep. 洗。Wash. Wash. 清扫清...`
- 无热词: `Housework. Housework. 整理收拾. tidy. tidy. 整洁的，整齐的. tidy. tidy. 打扫清除. 专门有个扫的感觉是什么？sweep. 洗. wash. wash....`

### Niko60900_2025-10-12 - Kyle
- 相似度: 86.96%
- 文本长度: 91 vs 93 字符
- 有热词: `十一，一分钟。Mouse 老鼠。老鼠。Elephant 大象。大象。Tiger 老虎。老虎。Lion 狮子。狮子。Wolf 狼。狼。Panda 熊猫。熊猫。Monkey 猴子。猴子。`
- 无热词: `十一 in 翻中。mouse 老鼠。老鼠。elephant 大象。大象。tiger 老虎。老虎。lion 狮子。狮子。wolf 狼。狼。panda 熊猫。熊猫。monkey 猴子。猴子。`

### Zoe41900_2025-11-20 - AL
- 相似度: 86.98%
- 文本长度: 164 vs 151 字符
- 有热词: `单词表三十八中发音。地方、地点、场所。Place. Place. 房间。Room. Room. 卧室。Bedroom. Bedroom. 厨房。Kitchen. Kitchen. 浴室、卫生间。Bat...`
- 无热词: `单词表三十八中发音。地方、地点、场所。Place。Place。房间。Room。Room。卧室。Bedroom。Bedroom。厨房。Kitchen。Kitchen。浴室、卫生间。Bathroom。Ba...`

### Zoe41900_2025-09-08 - Oscar
- 相似度: 92.66%
- 文本长度: 180 vs 174 字符
- 有热词: `Not. Not. 双倍的，双的。一半，半。 Half. 角色，部分。 Part, part. 形容词，两个的。 Both. Both. 代词，两者。 Both, both. Both. 副词，两者都...`
- 无热词: `Not. Not. 双倍的，双的。一半，半。 Half. 角色，部分。 Part. Part. 形容词，两个的。 Both. Both. 代词，两者。 Both. Both. Both. 副词，两者都...`

### Zoe41900_2025-10-24 - You
- 相似度: 96.30%
- 文本长度: 406 vs 404 字符
- 有热词: `单词表二，英翻中。啊，看到英翻中我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable。蔬菜。Fruit and vegetables are all good for our h...`
- 无热词: `二，英翻中。啊，看到英翻中我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。vegetable。蔬菜。Fruit and vegetables are all good for our heal...`

### Zoe41900_2025-11-20 - Kevin
- 相似度: 98.24%
- 文本长度: 173 vs 167 字符
- 有热词: `单词表三十八中翻英。地方、地点、场所。Place. Place. 房间。Room. Room. 卧室。Bedroom, bedroom, bedroom. 厨房。Kitchen, kitchen. 浴...`
- 无热词: `单词表三十八中翻英。地方、地点、场所。Place. Place.房间。Room. Room.卧室。Bedroom, bedroom, bedroom.厨房。Kitchen, kitchen.浴室、卫生...`

### Zoe41900_2025-10-24 - Oscar
- 相似度: 98.66%
- 文本长度: 413 vs 410 字符
- 有热词: `英翻中，啊，看到英翻中我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable，蔬菜。Fruit and vegetables are all good for our health...`
- 无热词: `英翻中，啊，看到英翻中我们就知道等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable，蔬菜。Fruit and vegetables are all good for our health....`

### Zoe41900_2025-10-24 - Rico
- 相似度: 98.90%
- 文本长度: 410 vs 411 字符
- 有热词: `英翻中，啊，看到英翻中我们就知道，等一会会看到英文，会在三秒钟之内说出中文。Vegetable。蔬菜。Fruit and vegetables are all good for our health....`
- 无热词: `英翻中，啊，看到英翻中我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable。蔬菜。Fruit and vegetables are all good for our health...`

### Zoe41900_2025-10-24 - Lucy
- 相似度: 99.11%
- 文本长度: 392 vs 393 字符
- 有热词: `啊，看到一分钟我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable. 蔬菜。Fruit and vegetables are all good for our health. 蔬...`
- 无热词: `啊，看到英文之后我们就知道，等一会儿会看到英文，会在三秒钟之内说出中文。Vegetable. 蔬菜。Fruit and vegetables are all good for our health. ...`

### Zoe41900_2025-09-08 - Frances Wang
- 相似度: 99.42%
- 文本长度: 171 vs 171 字符
- 有热词: `不。not。not。双倍的，双的。double。double。嗯，一半，半。half。half。角色，部分。part。part。形容词，两个的。both。both。代词，两者。both。both。副词...`
- 无热词: `不。not。not。双倍的，双的。double。double。嗯。一半，半。half。half。角色，部分。part。part。形容词，两个的。both。both。代词，两者。both。both。副词...`

### Niko60900_2025-10-12 - Jean
- 相似度: 100.00%
- 文本长度: 88 vs 88 字符
- 有热词: `一分钟。mouse。老鼠。老鼠。elephant。大象。大象。tiger。老虎。老虎。lion。狮子。狮子。wolf。狼。狼。panda。熊猫。熊猫。monkey。猴子。猴子。`
- 无热词: `一分钟。mouse。老鼠。老鼠。elephant。大象。大象。tiger。老虎。老虎。lion。狮子。狮子。wolf。狼。狼。panda。熊猫。熊猫。monkey。猴子。猴子。`

### Niko60900_2025-10-12 - Yiyi
- 相似度: 100.00%
- 文本长度: 94 vs 94 字符
- 有热词: `单词表十一，英翻中。Mouse 老鼠。老鼠。Elephant 大象。大象。Tiger 老虎。老虎。Lion 狮子。狮子。Wolf 狼。狼。Panda 熊猫。熊猫。Monkey 猴子。猴子。`
- 无热词: `单词表十一，英翻中。Mouse 老鼠。老鼠。Elephant 大象。大象。Tiger 老虎。老虎。Lion 狮子。狮子。Wolf 狼。狼。Panda 熊猫。熊猫。Monkey 猴子。猴子。`

### Niko60900_2025-11-19 - Nemo
- 相似度: 100.00%
- 文本长度: 183 vs 183 字符
- 有热词: `Teapot, T E A P O T. Teapot. Bed, B E D. Bed. Table, T A B L E. Table. Desk, D E S K. Desk. Chair, C...`
- 无热词: `Teapot, T E A P O T. Teapot. Bed, B E D. Bed. Table, T A B L E. Table. Desk, D E S K. Desk. Chair, C...`

### Zoe41900_2025-09-08 - Lucy
- 相似度: 100.00%
- 文本长度: 170 vs 170 字符
- 有热词: `Not. Not. 双倍的，双的。Double. Half. Half. 角色，部分。Party. Part. 形容词，两个的。Both. Both. 代词，两者。Both. Both. 副词，两者都...`
- 无热词: `Not. Not. 双倍的，双的。Double. Half. Half. 角色，部分。Party. Part. 形容词，两个的。Both. Both. 代词，两者。Both. Both. 副词，两者都...`

### Zoe41900_2025-09-08 - Rico
- 相似度: 100.00%
- 文本长度: 184 vs 184 字符
- 有热词: `Not. Not. 双倍的，双的。Double. Double. 一半，半。Half. Half. 角色，部分。Part. Part. 形容词，两个的。Both. Both. 代词，两者。Both. ...`
- 无热词: `Not. Not. 双倍的，双的。Double. Double. 一半，半。Half. Half. 角色，部分。Part. Part. 形容词，两个的。Both. Both. 代词，两者。Both. ...`

### Zoe41900_2025-09-08 - Yoyo
- 相似度: 100.00%
- 文本长度: 182 vs 182 字符
- 有热词: `Not. Not. 双倍的，双的。Double. Double. 一半，半。Half. Half. 角色，部分。Part. Part. 形容词，两个的。Both. Both. 代词，两者。Both. ...`
- 无热词: `Not. Not. 双倍的，双的。Double. Double. 一半，半。Half. Half. 角色，部分。Part. Part. 形容词，两个的。Both. Both. 代词，两者。Both. ...`

### Zoe41900_2025-11-20 - ANNA
- 相似度: 100.00%
- 文本长度: 163 vs 163 字符
- 有热词: `四表三十八中翻英。地方、地点、场所。Place. Place. 房间。Room. Room. 卧室。Bedroom. Bedroom. 厨房。Kitchen. Kitchen. 浴室、卫生间。Bath...`
- 无热词: `四表三十八中翻英。地方、地点、场所。Place. Place. 房间。Room. Room. 卧室。Bedroom. Bedroom. 厨房。Kitchen. Kitchen. 浴室、卫生间。Bath...`
