#!/usr/bin/env python3
"""
测试 Gatekeeper 功能的独立脚本
"""

import json
from pathlib import Path
from scripts.gatekeeper import QwenPlusGatekeeper, GatekeeperInput

PROJECT_ROOT = Path(__file__).parent

def test_gatekeeper(batch_id: str, student_name: str, verbose: bool = True):
    """测试单个学生的 gatekeeper"""
    print(f"\n{'='*80}")
    print(f"测试: {batch_id} / {student_name}")
    print(f"{'='*80}\n")

    # 构建路径
    student_dir = PROJECT_ROOT / "archive" / batch_id / student_name
    metadata_path = PROJECT_ROOT / "archive" / batch_id / "metadata.json"
    qwen_asr_path = student_dir / "2_qwen_asr.json"

    # 加载 metadata
    with open(metadata_path) as f:
        metadata = json.load(f)

    qb_path_str = metadata.get("question_bank_path", "")
    question_bank_path = PROJECT_ROOT / qb_path_str

    print(f"题库路径: {question_bank_path}")
    print(f"ASR 路径: {qwen_asr_path}")
    print()

    # 加载题库
    with open(question_bank_path) as f:
        question_bank_content = f.read()
        qb_data = json.loads(question_bank_content)

    print("题库前3题:")
    for item in qb_data[:3]:
        q = item.get("question", "")
        a = item.get("answer") or item.get("expected_answer", "")
        print(f"  question: '{q}' → answer: '{a}'")
    print()

    # 加载 ASR
    with open(qwen_asr_path) as f:
        asr_data = json.load(f)
    asr_text = (
        asr_data.get("output", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", [{}])[0]
        .get("text", "")
    )

    print(f"ASR 转写 (前200字符):")
    print(f"  {asr_text[:200]}...")
    print()

    # 创建输入
    gatekeeper_input = GatekeeperInput(
        archive_batch=batch_id,
        student_name=student_name,
        question_bank_path=question_bank_path,
        qwen_asr_path=qwen_asr_path,
        verbose=verbose,
        question_bank_content=question_bank_content,
        asr_text=asr_text,
    )

    # 执行检查
    print("正在执行 gatekeeper 检查...")
    gatekeeper = QwenPlusGatekeeper()
    result = gatekeeper.check(gatekeeper_input)

    # 显示结果
    print(f"\n{'='*80}")
    print(f"结果: {result.status}")
    print(f"{'='*80}")
    print(f"问题类型: {result.issue_type or 'None'}")
    print(f"响应时间: {result.format_response_time()}")

    if result.is_pass():
        print("✓ 质检通过")
    else:
        print(f"✗ 质检失败: {result.issue_type}")

    return result


if __name__ == "__main__":
    # 测试1: Benjamin (Abby61000_2025-11-05) - 应该 FAIL (WRONG_QUESTIONBANK)
    # 题库是 D3 (中→英) 但 ASR 显示 "英翻中"
    print("\n\n" + "="*80)
    print("测试用例 1: Benjamin - 预期 FAIL (WRONG_QUESTIONBANK)")
    print("="*80)
    result1 = test_gatekeeper("Abby61000_2025-11-05", "Benjamin", verbose=True)

    # 测试2: Oscar (Zoe41900_2025-09-08) - 应该 FAIL (WRONG_QUESTIONBANK)
    # 题库是 D5 (中→英) 但 ASR 显示 "英翻中"
    print("\n\n" + "="*80)
    print("测试用例 2: Oscar - 预期 FAIL (WRONG_QUESTIONBANK)")
    print("="*80)
    result2 = test_gatekeeper("Zoe41900_2025-09-08", "Oscar", verbose=True)

    # 总结
    print("\n\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"测试1 (Benjamin): {result1.status} - {result1.issue_type or 'None'}")
    print(f"测试2 (Oscar): {result2.status} - {result2.issue_type or 'None'}")
