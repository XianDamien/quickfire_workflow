#!/usr/bin/env python3
"""
快速验证工作流可观测性输出格式
"""

import json
import sys

# 模拟ASR转写结果
mock_asr_result = """spk0: 数字
spk1: number
spk0: 一百
spk1: hundred
spk0: 千
spk1: thousand"""

# 模拟题库CSV
mock_qb_data = """班级,日期,索引顺序,问题,答案
Zoe41900,9.8,1,"数字；数",number
Zoe41900,9.8,2,一百,hundred
Zoe41900,9.8,3,千,thousand"""

# 系统提示词片段
SYSTEM_PROMPT = "你是一个专业的AI语言教师助教。你的任务是基于学生提交的录音、对应的题库和ASR（自动语音识别）转写结果，对学生的"单词快反"作业进行客观、准确的评测。"

print("=" * 60)
print("📊 评测工作流启动")
print("=" * 60)

print("\n✓ 第1步：验证输入参数...")
print("   音频文件: audio/Cathy.mp3")
print("   题库文件: data/R1-65(1).csv")

print("\n✓ 第2步：执行音频转写 (ASR)...")
print("   🎵 正在转写音频，请稍候...")
print("   ✅ 音频转写完成")

# 可观测性输出1: ASR转写结果
print("\n" + "=" * 60)
print("📄 ASR 转写原始结果")
print("=" * 60)
print(mock_asr_result)

print("\n✓ 第3步：加载题库数据...")
print(f"   ✅ 题库加载完成")

# 可观测性输出2: 题库摘要
lines = mock_qb_data.strip().split('\n')
print("\n" + "=" * 60)
print("📚 题库摘要")
print("=" * 60)
print(f"题库条目数: {len(lines) - 1}")  # 去掉header
print(f"字段: {lines[0] if lines else 'N/A'}")

print("\n✓ 第4步：执行发音评测...")

# 可观测性输出3: AI评测提示词结构
asr_prompt = "以下是本音频的ASR数据，包括时间戳和说话人识别数据:\n" + mock_asr_result
qb_prompt = "本次作业的题库，老师给的标准问题和答案（以csv形式给出）\n" + mock_qb_data

print("\n" + "=" * 60)
print("💬 AI 评测提示词结构")
print("=" * 60)

print("\n[Layer 1] System Prompt (系统角色定义)")
print("-" * 40)
system_prompt_preview = SYSTEM_PROMPT[:500] + "..." if len(SYSTEM_PROMPT) > 500 else SYSTEM_PROMPT
print(system_prompt_preview)

print("\n[Layer 2] Question Bank Prompt (题库上下文)")
print("-" * 40)
qb_prompt_preview = qb_prompt[:500] + "..." if len(qb_prompt) > 500 else qb_prompt
print(qb_prompt_preview)

print("\n[Layer 3] ASR Data Prompt (ASR 识别结果)")
print("-" * 40)
asr_prompt_preview = asr_prompt[:500] + "..." if len(asr_prompt) > 500 else asr_prompt
print(asr_prompt_preview)

print("\n" + "🤖 正在调用AI模型进行评测，请稍候...")
print("   ✅ 评测完成")

# 可观测性输出4: AI评测结果JSON
mock_evaluation_result = {
    "final_grade_suggestion": "A",
    "mistake_count": {
        "hard_errors": 0,
        "soft_errors": 2
    },
    "annotations": [
        {
            "card_index": 0,
            "question": "数字；数",
            "expected_answer": "number",
            "related_student_utterance": {
                "detected_text": "number",
                "start_time": 1000,
                "end_time": 1500,
                "issue_type": None
            }
        }
    ]
}

print("\n" + "=" * 60)
print("📊 AI 评测结果 (JSON)")
print("=" * 60)
try:
    print(json.dumps(mock_evaluation_result, indent=2, ensure_ascii=False))
except json.JSONDecodeError:
    print(str(mock_evaluation_result))

print("\n✓ 第5步：输出评测报告...")
print("\n" + "=" * 60)
print("✨ 工作流执行完成！")
print("=" * 60)

print("\n[验证结果]")
print("✅ 可观测性输出点1 (ASR转写结果) - 已输出")
print("✅ 可观测性输出点2 (题库摘要) - 已输出")
print("✅ 可观测性输出点3 (提示词结构) - 已输出")
print("✅ 可观测性输出点4 (评测结果JSON) - 已输出")
