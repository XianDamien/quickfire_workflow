# scripts/CLAUDE.md - 评测引擎模块

## 模块职责
- `workflow.py` → **统一工作流入口**（推荐使用）, 端到端集成音频转写 + 评测评分
- `qwen3.py` → 主评测引擎，文本模式，加载题库+ASR数据，调用Qwen Plus生成评分报告（可单独导入模块）
- `captioner_qwen3.py` → 音频转写辅助工具，多模态模式，接收音频文件路径，输出ASR转写（可单独导入模块）

## qwen3.py 核心流程
```
1. 加载题库 (CSV) → load_qb()
2. 加载ASR结果 (JSON/TXT) → load_asr_data()
3. 构建Prompt: system_prompt + qb_prompt + asr_prompt
4. 调用dashscope.Generation.call(model="qwen-plus", messages=[...])
5. 输出JSON评分报告
```

## 数据结构
- **系统提示** (system_prompt): 评分规则、错误类型定义、评级逻辑
- **题库提示** (qb_prompt): "以下是题库:" + CSV内容
- **ASR提示** (asr_prompt): "以下是学生回答:" + ASR转写
- **输出** (JSON): {final_grade_suggestion, mistake_count, annotations[...]}

## captioner_qwen3.py 用法
```bash
python3 scripts/captioner_qwen3.py <audio_file_path>
```
- 接收命令行参数: 音频文件路径
- 调用dashscope.Generation.call(model="qwen3-omni-30b-a3b-captioner", ...)
- 返回多模态音频转写结果

## 关键变量
- `audio_file_path`: 学生作业音频（qwen3.py中暂未使用）
- `asr_filepath`: ASR转写结果文件路径
- `qb_filepath`: 题库CSV文件路径
- `system_prompt`: 长文本，定义所有评分规则和指示

## 常见修改
| 操作 | 位置 |
|-----|------|
| 更换LLM模型 | `model="qwen-plus"` 参数 |
| 修改评分规则 | `system_prompt` 变量内容 |
| 更改输入文件 | `asr_filepath`、`qb_filepath` 变量 |
| 启用流式输出 | `stream=True` 参数 |
| 启用深度思考 | `enable_thinking=True` 参数 |

## 文件路径约定
- 相对路径: `"./data/caption_result.txt"`
- 多模态音频: `"file://./audio/sample.mp3"`
- 题库路径: `"./data/R1-65(1).csv"`

## 依赖
- `dashscope` (1.24.6) - 阿里云SDK
- `json` - 内置JSON处理
- `csv` - 内置CSV处理
- 环境变量: `DASHSCOPE_API_KEY`

## 调试
- 脚本直接打印完整API响应，查看 `response.output` 获取结果
- 检查 `response.status_code` 确认请求状态
- 错误信息位于 `response.usage` 中

---

# workflow.py - 统一工作流程（新增）

## 功能概述
提供端到端的命令行工作流，自动执行：
1. 音频转写 (ASR)
2. 题库加载
3. 发音评测
4. JSON报告输出

## 快速使用

### 基础用法（输出到控制台）
```bash
python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv
```

### 指定输出文件
```bash
python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv --output result.json
```

### 使用 file:// 前缀
```bash
python3 workflow.py --audio-path file://./audio/sample.mp3 --qb-path ./data/R1-65(1).csv
```

## 命令行参数
| 参数 | 必需 | 说明 |
|------|------|------|
| `--audio-path` | 是 | 音频文件路径（相对或绝对路径，支持 file:// 前缀） |
| `--qb-path` | 是 | 题库CSV文件路径 |
| `--output` | 否 | 输出文件路径（可选，默认输出到控制台） |
| `--api-key` | 否 | DashScope API密钥（可选，默认读取环境变量） |

## 工作流程图
```
┌─────────────────┐
│  输入参数验证   │
└────────┬────────┘
         │
┌────────▼────────┐
│   音频转写      │ (captioner_qwen3.transcribe_audio)
│   (ASR)         │
└────────┬────────┘
         │
┌────────▼────────┐
│   加载题库      │ (qwen3.load_qb)
└────────┬────────┘
         │
┌────────▼────────┐
│   执行评测      │ (qwen3.evaluate_pronunciation)
│   生成报告      │
└────────┬────────┘
         │
┌────────▼────────┐
│   输出结果      │ (文件或控制台)
└─────────────────┘
```

## 核心函数（模块化复用）

### 可导入的函数

#### qwen3.py
```python
from qwen3 import load_asr_data, load_qb, evaluate_pronunciation

# 加载ASR数据
asr_data = load_asr_data("path/to/asr.txt")

# 加载题库
qb_data = load_qb("path/to/qb.csv")

# 执行评测
result = evaluate_pronunciation(asr_data, qb_data, api_key="...", model="qwen-plus")
```

#### captioner_qwen3.py
```python
from captioner_qwen3 import transcribe_audio

# 转写音频
asr_result = transcribe_audio("path/to/audio.mp3", api_key="...")
```

## 向后兼容性
- ✅ 原脚本保持独立可用性
- ✅ `qwen3.py` 仍可直接运行：`python3 qwen3.py`
- ✅ `captioner_qwen3.py` 仍可直接运行：`python3 captioner_qwen3.py <audio>`
- ✅ 所有函数已提取为可重用模块
