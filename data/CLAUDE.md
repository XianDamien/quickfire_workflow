# data/CLAUDE.md - 数据模块

## 模块职责
存储评测系统的三类输入数据：题库、ASR转写结果、原始音频

## 数据文件清单

| 文件 | 类型 | 用途 | 编码 |
|-----|------|------|------|
| `R1-65(1).csv` | CSV | 题库，包含标准问题和答案 | UTF-8 |
| `caption_result.txt` | TXT | ASR转写结果（纯文本）| UTF-8 |
| `2_intermediate_asr_raw.json` | JSON | ASR原始数据（完整转写信息） | UTF-8 |

## 题库格式 (R1-65(1).csv)
```csv
班级,日期,索引顺序,问题,答案
Zoe41900,9.8,1,"数字；数",number
Zoe41900,9.8,2,"颜色",color
...
```
- 编码: UTF-8（含中文）
- 分隔符: 逗号
- 用途: qwen3.py 中 `load_qb()` 函数加载

## ASR 纯文本格式 (caption_result.txt)
```
学生回答内容文本
可能包含多行
通常由 captioner_qwen3.py 生成或外部系统提供
```
- 编码: UTF-8
- 用途: qwen3.py 中 `load_asr_data()` 函数加载
- 特点: 简洁，直接输入Prompt

## ASR 原始JSON格式 (2_intermediate_asr_raw.json)
```json
{
  "file_url": "...",
  "properties": {...},
  "transcripts": [{
    "channel_id": 0,
    "content_duration_in_milliseconds": 36400,
    "text": "...",
    "sentences": [
      {"channel_id": 0, "content": "...", "start_time": 0, "end_time": 1000}
    ]
  }]
}
```
- 字段说明:
  - `transcripts[].text` → 完整转写文本
  - `transcripts[].sentences` → 按句分割
  - `start_time` / `end_time` → 毫秒单位时间戳
  - `channel_id` → 说话人标识（区分教师/学生）

## 时间戳约定
- 单位: 毫秒 (milliseconds)
- 用途: qwen3.py 中检测"SLOW_RESPONSE"错误
- 说话人: 通过 `channel_id` 或 `speaker_id` 字段区分 spk0/spk1

## 使用指南
### 在 qwen3.py 中更改数据路径
```python
qb_filepath = "./data/R1-65(1).csv"           # 题库
asr_filepath = "./data/caption_result.txt"    # ASR纯文本
# 或
asr_filepath = "./data/2_intermediate_asr_raw.json"  # ASR完整JSON
```

### 数据加载函数
- `load_qb(filepath)` → 返回题库列表
- `load_asr_data(filepath)` → 返回ASR转写文本（自动处理JSON/TXT）

## 编码要求
- 所有文件必须 UTF-8 编码
- CSV 题库含中文字符，加载时指定 `encoding='utf-8'`
- 避免 BOM 字节序标记

## 新增数据
1. 题库更新: 添加新行到 CSV，保持格式一致
2. ASR结果: 运行 `python3 scripts/captioner_qwen3.py <audio>` 生成
3. 原始音频: 放置在 `../audio/` 目录（可选）
