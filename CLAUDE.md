# 项目规则 (Project Rules)

## Annotator 模块规范

### 可替换性原则

项目采用 **Annotator 接口抽象**，所有评分模型实现统一的 `BaseAnnotator` 接口，支持即插即用。

### 支持的 Annotator

| Annotator | 模型 | 输入方式 | 推荐场景 |
|-----------|------|---------|---------|
| **Gemini Audio** | `gemini-3-pro-preview` | 音频直传 | 🌟 **默认生产模型** |
| | `gemini-2.5-pro` | 音频直传 | 备选高质量模型 |
| | `gemini-2.0-flash` | 音频直传 | 快速测试 |
| **Qwen3-Omni** | `qwen-omni-flash` | 音频直传 (OpenAI 兼容) | 备用方案，100MB/20min |
| **Qwen Text** | `qwen-max` 等 | 仅文本 | 不推荐（无音频理解） |

### 默认模型

**生产环境默认**: `gemini-3-pro-preview`
- 配置位置: `scripts/annotators/config.py::DEFAULT_ANNOTATOR`
- 原因: 音频理解、多语言标注、异常检测表现最优

### 切换 Annotator

```bash
# 使用默认 annotator
python scripts/main.py --archive-batch Batch123

# 切换到 Qwen3-Omni Flash
python scripts/main.py --archive-batch Batch123 --annotator qwen-omni-flash

# 切换到 Gemini 2.5 Pro
python scripts/main.py --archive-batch Batch123 --annotator gemini-2.5-pro
```

## 测试模式

项目支持两种测试模式：

| 模式 | 脚本 | 用途 |
|------|------|------|
| **Batch 模式** | `gemini_batch_audio.py` | 正常端到端流程，批量处理多个学生 |
| **同步模式** | `GeminiAudioAnnotator` 直接调用 | 临时修改 prompt 后快速迭代验证 |

**同步测试示例：**
```python
from scripts.annotators.gemini_audio import GeminiAudioAnnotator
from scripts.common.runs import new_run_id, ensure_run_dir

annotator = GeminiAudioAnnotator(model='gemini-3-pro-preview')
run_id = new_run_id()
run_dir = ensure_run_dir(BATCH, STUDENT, annotator.name, run_id)

result = annotator.run_archive_student(
    archive_batch=BATCH,
    student_name=STUDENT,
    run_dir=run_dir,
)
print(result.validation, result.final_grade)
```

## 代码规范

- 不允许模拟 ASR 数据
- 不允许绕过音频测试
- 不允许修改 prompt 模板里的提示词（除非明确要求）

## 目录结构

```
prompts/annotation/
├── system.md              # 系统提示词
├── user_with_audio.md     # 主要 prompt (v2.0.0 音频直传)
├── metadata.json          # prompt 版本信息
└── archived/              # 旧版本归档

scripts/annotators/
├── config.py              # 模型配置
├── base.py                # BaseAnnotator 接口
├── gemini_audio.py        # Gemini 音频 annotator
├── qwen.py                # Qwen 文本 annotator
├── qwen_omni.py           # Qwen3-Omni 音频 annotator (NEW)
└── __init__.py            # get_annotator() 工厂函数
```
