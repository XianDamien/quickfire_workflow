# 开发命令和配置

## 环境设置
```bash
export DASHSCOPE_API_KEY="sk-xxxxx"
```

## 核心命令
```bash
# 主评测引擎（文本模式）
python3 scripts/qwen3.py

# 音频转写辅助（多模态模式，需参数）
python3 scripts/captioner_qwen3.py <audio_file_path>
```

## 文件路径配置
在脚本中修改以下变量：
```python
qb_filepath = "./data/R1-65(1).csv"           # 题库
asr_filepath = "./data/caption_result.txt"    # ASR纯文本结果
audio_file_path = "file://./audio/sample.mp3" # 音频文件(多模态)
```

## 常见修改

### 更改LLM模型
```python
model="qwen-plus"  # 改为其他模型名
```

### 调整评分规则
编辑`system_prompt`变量内容（system_prompt定义了所有评分逻辑）

### 启用高级特性
```python
stream=True              # 流式输出
enable_thinking=True    # 深度思考
incremental_output=True # 逐步输出
```

## 数据格式

### 题库 (CSV)
```csv
班级,日期,索引顺序,问题,答案
Zoe41900,9.8,1,"数字；数",number
```
- 编码：UTF-8
- 用途：qwen3.py的load_qb()函数

### ASR转写 (TXT)
纯文本格式，由captioner_qwen3.py或外部系统生成

### ASR原始 (JSON)
```json
{
  "transcripts": [{
    "text": "...",
    "sentences": [
      {"content": "...", "start_time": 0, "end_time": 1000}
    ]
  }]
}
```
- 时间戳：毫秒单位
- 说话人：通过channel_id/speaker_id区分

## 调试技巧
- 脚本直接输出完整API响应
- 查看response.output获取评分结果
- 检查response.status_code确认请求状态
- 错误信息查看response中的error字段

## 依赖库
- dashscope (1.24.6)
- json (内置)
- csv (内置)
- openai (可选兼容模式)
