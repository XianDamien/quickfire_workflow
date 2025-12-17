# 开发命令和配置

## 环境设置
```bash
export DASHSCOPE_API_KEY="sk-xxxxx"  # Qwen ASR API 密钥
export GEMINI_API_KEY="sk-xxxxx"     # Gemini API 密钥
```

## 核心命令

### ASR 转写 (qwen_asr.py)

**标准模式**（基于 archive 目录结构）：
```bash
# 转写所有数据集
python3 scripts/qwen_asr.py

# 转写指定数据集的所有学生
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8

# 转写指定学生
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
```

**✨ 文件名解析模式**（新增，无需目录结构）：
```bash
# 直接处理单个音频文件，自动从文件名解析班级、日期、进度、学生
python3 scripts/qwen_asr.py --file /path/to/Abby61000_2025-10-30_R1-27-D2_Benjamin.mp3

# 指定输出目录
python3 scripts/qwen_asr.py --file /path/to/audio.mp3 --output /path/to/output

# 指定 API 密钥
python3 scripts/qwen_asr.py --file /path/to/audio.mp3 --api-key YOUR_KEY
```

### Gemini 评分 (Gemini_annotation.py)
```bash
# 处理所有数据集
python3 scripts/Gemini_annotation.py

# 处理指定数据集
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8

# 处理指定学生
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar

# 指定并发线程数
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8 --workers 5

# 强制重新处理（跳过已处理检查）
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8 --force
```

## 数据目录结构

### archive 目录（标准模式）
```
archive/
├── <dataset>/
│   └── <student>/
│       ├── 1_input_audio.mp3          # 输入音频
│       ├── 2_qwen_asr.json            # ASR 输出
│       ├── 2_qwen_asr_metadata.json   # ASR 元数据
│       ├── 4_llm_annotation.json      # Gemini 评分
│       └── 4_llm_prompt_log.txt       # 提示词日志
```

### questionbank 目录（题库来源）
```
questionbank/
├── R1-27-D2*.json
├── R1-65*.json
├── R3-14-D4*.json
└── R*.json
```

### prompts 目录（提示词模板）
```
prompts/
└── annotation/
    ├── system.md         # 系统指令
    ├── user.txt          # Jinja2 模板
    └── metadata.json     # 版本元数据
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
