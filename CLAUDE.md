# 项目规则 (Project Rules)

## 模型规范

**整个项目必须使用 Gemini 3 Pro Preview 作为默认标注模型。**

- 模型名称: `gemini-3-pro-preview`
- 配置位置: `scripts/annotators/config.py`
- 原因: 该模型在音频理解和多语言标注任务上表现最优，能正确识别异常音频（如 NO_TEACHER_AUDIO）

> 测试时可临时使用其他模型，但生产环境必须使用此模型。

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
├── config.py              # 模型配置 (DEFAULT_ANNOTATOR)
├── gemini_audio.py        # Gemini 音频 annotator
└── base.py                # 基类定义
```
