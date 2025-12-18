 - 统一文件命名（用于批量测试/聚合）：以 file_id = {ClassCode}_{Date}_{QuestionBank}_{StudentName} 为主
    键；后续所有产物都用同名：
      - asr_timestamp/{file_id}.json（带时间戳 ASR，结构参考 asr_timestamp/Zoe41900_2025-09-08_R1-65-
        D5_Oscar.json）
      - asr/{file_id}.json（Qwen ASR：输出结构参考这个就可以/Users/damien/Desktop/LanProject/quickfire_workflow/asr/Cathy_test_report.json）
      - backend_output/{file_id}_annotation.json（Gemini 输出，严格按 prompts/annotation/user.md 里面提出的输出的 JSON
        结构）
  - Qwen 输出规范（批量友好）：在 scripts/qwen_asr.py 里把“原始 Qwen API 响应”和“归一化输出”分开保存：
      - 原始：asr/{file_id}_qwen_raw.json（便于排查）
      - 归一化：asr/{file_id}.json，字段固定为：file_url, transcripts[0].channel_id,
        transcripts[0].transcript, transcripts[0].sentences（可空）
  - Gemini 注解输入三件套（对齐 user.md）：在 scripts/Gemini_annotation.py 增加/切换到“按 file_id 处理”的路
    径（更适合你现在的目录结构）：
      - 题库：从 questionbank/{QuestionBank}.json 读取（QuestionBank 从 file_id 解析）
      - ASR 文本：从 asr/{file_id}.json 读 transcripts[0].transcript（qwen_asr 负责转录）
      - 带时间戳 ASR：从 asr_timestamp/{file_id}.json 读取；在进 prompt 前转换成“逐行时间戳文本”（建议格
        式：MM:SS text，时间用 begin_time 毫秒换算），作为 student_asr_with_timestamp
  - Prompt 加载改造：在 prompts/prompt_loader.py 做两点兼容：
      - 把 user 模板从固定的 user.txt 改为优先读 user.md（若不存在再 fallback user.txt）
      - 在 PromptContextBuilder.build(...) 增加必填字段 student_asr_with_timestamp，并在
        Gemini_annotation.py 构建 context 时传入
  - Gemini 输出严格校验与落盘（保证可聚合）：在 scripts/Gemini_annotation.py 对模型返回做结构校验/纠错
    策略：
      - 期望顶层为 JSON 对象：final_grade_suggestion, mistake_count, annotations[]（以 user.md 示例为准）
      - 每个 annotations[] 必须包含：card_index, card_timestamp, question, expected_answer,
        related_student_utterance{detected_text, issue_type}
      - 校验失败：保存 *_annotation_raw.txt + 输出 status=error，避免批量聚合被脏数据打断
  - 批量聚合（最省事的实现方式）：新增一个聚合脚本（例如 scripts/aggregate_annotation_report.py）只做“读文
    件 + 汇总”：
      - 输入：遍历 backend_output/*_annotation.json 或按 --class/--date/--question-bank 过滤 file_id
      - 输出：一个 batch_annotation_report.json（按 file_id/学生维度汇总 final_grade_suggestion、errors
        数、每题 issue_type 统计）
  - 建议的批量跑通流程（稳定可复现）：
      1. 生成 asr/{file_id}.json（Qwen）
      2. 生成 asr_timestamp/{file_id}.json（FunASR）
      3. 运行 Gemini_annotation.py --file-id {file_id} 或 --class/--date 批量
      4. 运行聚合脚本生成班级/日期维度报告