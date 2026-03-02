# Gemini API 学生回答提取 - 问题总结

## 项目概述
开发一个使用 Gemini API 从学生 ASR 转写文本中提取回答的脚本，处理：
- 教师转录模板 (R3-14-D4_transcription.txt)
- 题库数据 (R3-14-D4.json) 
- 学生 ASR 结果 (2_qwen_asr.json)

## 遇到的问题及解决方案

### 1. 网络连接问题
**错误**: `Server disconnected without sending a response`
**原因**: 使用了代理 (http://127.0.0.1:7890)，代理在处理长请求时不稳定
**解决方案**: 
- 临时关闭代理运行脚本
- 添加重试机制（3次重试，间隔5秒）
- 增加超时时间到120秒

### 2. API 接口不兼容
**错误**: `Models.generate_content() got an unexpected keyword argument 'http_options'`
**原因**: google-genai 新版 API 不支持在 generate_content 时传递 http_options
**解决方案**: 移除 http_options 参数，改用默认设置

### 3. Token 限制问题
**错误**: `FinishReason.MAX_TOKENS`
**原因**: 响应内容超过 8192 tokens 限制
**解决方案**:
- 将 max_output_tokens 从 8192 增加到 16384
- 添加 MAX_TOKENS 错误处理逻辑
- 实现备用方案：生成基础响应（所有问题标记为"未作答"）

### 4. 提示词优化
**问题**: 提示词过长（4086字符），包含重复的背景信息
**解决方案**:
- 将背景信息移到 system_instruction 中
- 从提示词中删除重复内容
- 分离角色定义和背景信息，提高效率

## 技术要点

### Gemini API 使用注意事项
1. **新版 google-genai API** vs **旧版 google.generativeai**
   - 新版: `from google import genai`, `client = genai.Client()`
   - 旧版: `import google.generativeai as genai`, `genai.configure()`
   
2. **系统指令 (system_instruction)**
   - 适合放角色定义和背景信息
   - 不占用 prompt 的 token 限制
   - 新版 API 支持直接传递

3. **错误处理策略**
   - 网络错误：重试机制
   - MAX_TOKENS：增加限制或简化请求
   - SAFETY：检查敏感内容，使用备用方案

### 代码优化建议
1. **提示词结构化**
   ```
   System Instruction: 角色定义 + 背景信息
   Prompt: 具体任务 + 输入数据 + 输出格式
   ```

2. **错误处理流程**
   ```
   API调用失败 → 重试 → 降级方案 → 本地处理
   ```

3. **日志和调试**
   - 保存完整提示词到文件
   - 输出详细的调试信息
   - 记录 API 响应状态

## 最终脚本功能
- 输入：教师转录 + 题库 + 学生ASR
- 输出：JSON格式的学生回答标注
- 特点：支持重试、错误处理、提示词优化
- 位置：`scripts/Gemini_annotation.py`

## 文件输出
- `4_llm_annotation.json` - 最终结果
- `4_llm_prompt_log.txt` - 完整提示词记录

## 经验教训
1. 代理设置对长请求有影响，需要测试或临时关闭
2. API 版本差异大，需要查看文档确认参数
3. Token 限制需要预估，避免内容被截断
4. System instruction 是优化提示词的有效方式
5. 完善的错误处理和日志对调试至关重要