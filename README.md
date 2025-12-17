# 英语发音作业评测系统

**自动评分 + 结构化反馈系统**，用于评估学生英语发音作业。

## 📋 系统架构

```
学生音频 (1_input_audio.mp3)
    ↓
Qwen ASR 转写 (2_qwen_asr.json)
    ↓
Gemini LLM 智能注解 (4_llm_annotation.json)
    ↓
批量评分报告 (batch_annotation_report.json)
```

### 技术栈

- **Python 3.12+**
- **Qwen-Plus LLM** - ASR 和上下文处理
- **Google Gemini API** - 学生答案注解和评分
- **dashscope 1.24.6** - 阿里云 Qwen SDK
- **ffmpeg** - 音频分段处理

## 🗂️ 项目结构

```
quickfire_workflow/
├── scripts/                          # 核心脚本
│   ├── qwen_asr.py                  # Qwen ASR 转写脚本（支持音频分段）
│   ├── Gemini_annotation.py         # Gemini 注解脚本（支持并行处理）
│   └── .env                         # 环境变量配置
├── archive/                          # 历史测试数据
│   ├── Zoe51530-9.8/                # 数据集（班级代码-日期）
│   │   ├── _shared_context/         # 题库文件（所有学生共享）
│   │   │   ├── R3-14.csv            # CSV 题库
│   │   │   └── R3-14-D4.json        # JSON 题库格式
│   │   ├── StudentName1/            # 学生文件夹
│   │   │   ├── 1_input_audio.mp3    # 原始音频
│   │   │   ├── 2_qwen_asr.json      # ASR 转写结果
│   │   │   └── 4_llm_annotation.json # LLM 注解结果
│   │   ├── StudentName2/
│   │   └── batch_annotation_report.json  # 批量报告
│   ├── Zoe41900-9.8/
│   ├── Zoe70930-10.13/
│   └── Niko60900-10.12/
├── prompts/
│   └── annotation.txt               # Gemini 提示词模板
├── .env                             # 全局环境变量
└── README.md                        # 本文件
```

## 🚀 快速开始

### 前置条件

1. **安装依赖**

```bash
pip install dashscope openai python-dotenv google-generativeai pydub
```

2. **安装 FFmpeg**（音频分段处理所需）

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
choco install ffmpeg
```

3. **配置环境变量**

在项目根目录创建 `.env` 文件：

```env
# Qwen API Key（阿里云 DashScope）
DASHSCOPE_API_KEY=sk-xxx...

# Gemini API Key（Google）
GEMINI_API_KEY=AIzaSyD...
```

### 数据集目录结构

创建如下目录结构来组织待处理的数据：

```
archive/
└── DatasetName/              # 数据集名称，格式: Zoe51530-9.8
    ├── _shared_context/      # 题库文件夹（必须存在）
    │   ├── R3-14.csv         # 或其他题库文件
    │   └── R3-14-D4.json     # 可选 JSON 格式
    ├── StudentName1/
    │   ├── 1_input_audio.mp3 # 必须：学生音频文件
    │   └── (运行后自动生成 2_qwen_asr.json 和 4_llm_annotation.json)
    ├── StudentName2/
    └── ...
```

## 📝 使用指南

### 1️⃣ 第一步：Qwen ASR 转写

将音频文件转写成文本（支持自动音频分段处理）。

#### 转写所有数据集

```bash
cd scripts
python3 qwen_asr.py
```

#### 转写指定数据集

```bash
cd scripts
python3 qwen_asr.py --dataset Zoe51530-9.8
```

#### 转写单个学生

```bash
cd scripts
python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
```

**输出文件**: `archive/Zoe51530-9.8/Oscar/2_qwen_asr.json`

**ASR 输出格式**（标准 Qwen API 响应）：

```json
{
  "output": {
    "choices": [
      {
        "message": {
          "content": [
            {
              "text": "转写后的文本..."
            }
          ]
        }
      }
    ]
  }
}
```

#### 热词增强（可选）

ASR 支持从 CSV/JSON 题库加载热词来改进转写准确度：

```python
# scripts/qwen_asr.py 会自动从题库中提取关键词作为上下文
# 支持格式：
# 1. CSV: questions 列中的内容
# 2. JSON: questions 数组中的内容
```

**音频分段处理说明**：
- 自动检测音频时长
- 长于 180 秒的音频自动分段并行处理（3 线程）
- 转写结果自动合并为单一 JSON 文件

---

### 2️⃣ 第二步：Gemini LLM 注解

使用 Gemini 对学生答案进行智能注解和评分。

#### 处理所有数据集

```bash
cd scripts
python3 Gemini_annotation.py
```

#### 处理指定数据集

```bash
cd scripts
python3 Gemini_annotation.py --dataset Zoe51530-9.8
```

#### 处理单个学生

```bash
cd scripts
python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar
```

**输出文件**:
- 单个学生: `archive/Zoe51530-9.8/Oscar/4_llm_annotation.json`
- 批量报告: `archive/Zoe51530-9.8/batch_annotation_report.json`
- 调试日志: `archive/Zoe51530-9.8/Oscar/4_llm_prompt_log.txt`（可选）

**LLM 输出格式**（Gemini API 响应）：

```json
{
  "final_grade_suggestion": "A",
  "mistake_count": 0,
  "annotations": [
    {
      "sentence_index": 0,
      "student_answer": "...",
      "error_type": "MEANING_ERROR",
      "correction": "..."
    }
  ]
}
```

---

## 🧪 批量测试指南

完整的端到端批量测试工作流程。

### 场景 1：从头开始处理新数据集

**前提**：已有数据集目录和音频文件

```bash
# 1. 准备数据集
# 确保目录结构如下：
# archive/Zoe51530-9.8/
#   _shared_context/
#     R3-14.csv
#   StudentName1/
#     1_input_audio.mp3
#   StudentName2/
#     1_input_audio.mp3

# 2. 运行 Qwen ASR 转写
cd scripts
python3 qwen_asr.py --dataset Zoe51530-9.8

# 预期结果：
# ✓ 所有学生生成 2_qwen_asr.json
# ✓ 长音频自动分段处理并行执行
# ✓ 转写结果成功合并

# 3. 运行 Gemini 注解
python3 Gemini_annotation.py --dataset Zoe51530-9.8

# 预期结果：
# ✓ 所有学生生成 4_llm_annotation.json
# ✓ 生成 batch_annotation_report.json
# ✓ 检测到已处理学生时报错停止（防重复处理）
```

### 场景 2：重新处理数据（验证一致性）

**目的**：确保系统处理结果稳定

```bash
# 1. 清除旧数据
cd archive/Zoe51530-9.8
# 删除所有 2_qwen_asr.json 文件
find . -name "2_qwen_asr.json" -delete

# 删除所有 4_llm_annotation.json 文件
find . -name "4_llm_annotation.json" -delete

# 2. 重新运行处理流程
cd ../../scripts
python3 qwen_asr.py --dataset Zoe51530-9.8
python3 Gemini_annotation.py --dataset Zoe51530-9.8

# 验证结果一致性（对比历史版本）
```

### 场景 3：单学生快速测试

**目的**：快速验证单个学生的处理流程

```bash
# 测试单个学生
cd scripts
python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar

# 检查 ASR 输出
cat ../archive/Zoe51530-9.8/Oscar/2_qwen_asr.json | python3 -m json.tool

# 继续注解
python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar

# 检查注解输出
cat ../archive/Zoe51530-9.8/Oscar/4_llm_annotation.json | python3 -m json.tool
```

### 场景 4：多数据集批量处理

**目的**：处理多个班级/日期的数据

```bash
# 处理所有数据集
cd scripts

# 所有 ASR 转写
python3 qwen_asr.py

# 预期：处理 archive/ 下所有数据集
# - Zoe51530-9.8
# - Zoe41900-9.8
# - Zoe70930-10.13
# - Niko60900-10.12

# 所有 Gemini 注解
python3 Gemini_annotation.py

# 预期：所有数据集都生成 batch_annotation_report.json
```

---

## 📊 批量报告格式

`batch_annotation_report.json` 包含所有学生的汇总数据：

```json
{
  "dataset": "Zoe51530-9.8",
  "total_students": 6,
  "processed_students": 6,
  "students": [
    {
      "student_name": "Oscar",
      "status": "success",
      "final_grade_suggestion": "A",
      "mistake_count": 0,
      "annotation_file": "archive/Zoe51530-9.8/Oscar/4_llm_annotation.json",
      "timestamp": "2025-10-22T01:08:53+08:00"
    },
    {
      "student_name": "Kevin",
      "status": "success",
      "final_grade_suggestion": "B",
      "mistake_count": 1,
      "annotation_file": "archive/Zoe51530-9.8/Kevin/4_llm_annotation.json",
      "timestamp": "2025-10-22T01:09:15+08:00"
    }
  ],
  "summary": {
    "grade_distribution": {
      "A": 3,
      "B": 2,
      "C": 1
    }
  }
}
```

---

## 🔍 调试和故障排查

### 问题 1：ASR 转写失败

**症状**：`2_qwen_asr.json` 文件为空或格式错误

**检查清单**：

```bash
# 1. 检查环境变量
echo $DASHSCOPE_API_KEY

# 2. 检查音频文件
file archive/Zoe51530-9.8/Oscar/1_input_audio.mp3

# 3. 查看详细日志
cd scripts
python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar 2>&1 | tee debug.log

# 4. 检查 ffprobe（音频分段所需）
which ffprobe
```

### 问题 2：Gemini 注解失败

**症状**：`4_llm_annotation.json` 不存在或 LLM 返回错误

**检查清单**：

```bash
# 1. 检查 Gemini API Key
echo $GEMINI_API_KEY | head -c 20

# 2. 检查 ASR 文件存在
cat archive/Zoe51530-9.8/Oscar/2_qwen_asr.json | python3 -m json.tool

# 3. 检查题库文件
ls -la archive/Zoe51530-9.8/_shared_context/

# 4. 运行单学生测试
cd scripts
python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar

# 5. 检查 prompt 日志
cat ../archive/Zoe51530-9.8/Oscar/4_llm_prompt_log.txt
```

### 问题 3：重复处理检查

**症状**：运行 Gemini 脚本时报错：`Found already processed student`

**原因**：防重复处理机制检测到已处理的学生

**解决**：

```bash
# 方案 1：只处理未处理的学生
# 脚本会自动跳过存在 4_llm_annotation.json 的学生

# 方案 2：完全重新处理
# 删除已处理的文件再运行
find archive/Zoe51530-9.8 -name "4_llm_annotation.json" -delete
python3 Gemini_annotation.py --dataset Zoe51530-9.8
```

### 问题 4：音频分段失败

**症状**：`⚠️ warning: ffprobe not found`

**解决**：

```bash
# 安装 ffmpeg
brew install ffmpeg  # macOS
# 或
sudo apt-get install ffmpeg  # Linux

# 验证安装
ffprobe -version
```

---

## 📈 性能参数

### ASR 转写

- **支持音频时长**：无限制（自动分段）
- **默认分段长度**：180 秒（3 分钟）
- **并行处理线程数**：3
- **长音频处理**：自动分段 + 并行转写 + 结果合并

**性能示例**（Zoe51530-9.8）：
- 6 个学生
- 总音频时长：~3-4 小时
- 处理时间：~30-40 分钟（含 API 等待）
- 平均每个学生：6-7 分钟

### Gemini 注解

- **并行处理线程数**：自适应（通常 3-5）
- **重试次数**：5
- **重试延迟**：5 秒
- **超时时间**：60 秒/请求

**性能示例**（Zoe51530-9.8）：
- 6 个学生
- 平均注解时间：2-3 分钟/学生
- 批量处理时间：~12-18 分钟

---

## 🏗️ 数据流验证清单

在运行批量测试前，请确认以下项目：

- [ ] 数据集目录存在：`archive/Zoe51530-9.8/`
- [ ] 题库文件存在：`archive/Zoe51530-9.8/_shared_context/R3-14*.csv` 或 `.json`
- [ ] 所有学生音频存在：`archive/Zoe51530-9.8/StudentName/1_input_audio.mp3`
- [ ] 环境变量已设置：`DASHSCOPE_API_KEY` 和 `GEMINI_API_KEY`
- [ ] FFmpeg 已安装：`ffprobe` 和 `ffmpeg` 可用
- [ ] 依赖包已安装：运行 `pip install -r requirements.txt`
- [ ] 旧数据已清理：如果重新处理，删除 `2_qwen_asr.json` 和 `4_llm_annotation.json`

---

## 📝 高级配置

### 自定义提示词模板

编辑 `prompts/annotation.txt`：

```text
# 系统提示词模板
...
{{在此处粘贴题库 JSON}}
...
{{在此处粘贴老师音频转录文本}}
...
{{在此处粘贴学生音频转录文本}}
...
```

### 自定义音频分段长度

编辑 `scripts/qwen_asr.py`，修改 `split_audio()` 函数中的 `segment_duration` 参数。

### 自定义题库检测

脚本支持多种题库文件名模式的自动检测：
1. 优先查找 `R3-14-D4*.json`
2. 其次查找 `R1-65*.json`
3. 最后查找任何 `R*.json` 模式

---

## 📚 参考资源

- [Qwen 官方文档](https://dashscope.aliyuncs.com)
- [Google Gemini API 文档](https://ai.google.dev)
- [FFmpeg 用户指南](https://ffmpeg.org/documentation.html)

---

## 📄 文件清单

| 文件 | 说明 |
|------|------|
| `scripts/qwen_asr.py` | Qwen ASR 转写脚本 |
| `scripts/Gemini_annotation.py` | Gemini 注解脚本 |
| `scripts/.env` | 脚本级环境变量（可选） |
| `prompts/annotation.txt` | Gemini 提示词模板 |
| `.env` | 全局环境变量 |
| `.gitignore` | Git 忽略规则 |

---

**最后更新**: 2025-10-22
**版本**: 1.0.0

