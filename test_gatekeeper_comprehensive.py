#!/usr/bin/env python3
"""
全面测试 Gatekeeper 功能，收集多种场景的测试数据
"""

import json
from pathlib import Path
from scripts.gatekeeper import QwenPlusGatekeeper, GatekeeperInput

PROJECT_ROOT = Path(__file__).parent

def analyze_questionbank(qb_path: Path) -> dict:
    """分析题库的翻译方向"""
    with open(qb_path) as f:
        qb_data = json.load(f)

    chinese_questions = 0
    english_questions = 0

    for item in qb_data[:5]:  # 分析前5题
        question = item.get("question", "")
        # 简单判断：包含中文字符
        if any('\u4e00' <= char <= '\u9fff' for char in question):
            chinese_questions += 1
        else:
            english_questions += 1

    if chinese_questions > english_questions:
        return {"direction": "中→英", "confidence": chinese_questions / 5}
    else:
        return {"direction": "英→中", "confidence": english_questions / 5}

def analyze_asr_pattern(asr_text: str) -> dict:
    """分析 ASR 的实际模式"""
    # 取前300字符分析
    sample = asr_text[:300]

    # 统计模式特征
    patterns = {
        "英_中": 0,  # kid 小孩
        "中_英": 0,  # 小孩 kid
        "混乱": 0
    }

    # 简单模式匹配（这里只是示例，实际可能需要更复杂的逻辑）
    words = sample.split()
    for i in range(len(words) - 1):
        curr = words[i]
        next_word = words[i + 1]

        # 判断当前词和下一个词的语言
        curr_is_chinese = any('\u4e00' <= char <= '\u9fff' for char in curr)
        next_is_chinese = any('\u4e00' <= char <= '\u9fff' for char in next_word)

        if not curr_is_chinese and next_is_chinese:
            patterns["英_中"] += 1
        elif curr_is_chinese and not next_is_chinese:
            patterns["中_英"] += 1

    # 判断主要模式
    if patterns["英_中"] > patterns["中_英"] * 1.5:
        return {"pattern": "英→中", "score": patterns["英_中"]}
    elif patterns["中_英"] > patterns["英_中"] * 1.5:
        return {"pattern": "中→英", "score": patterns["中_英"]}
    else:
        return {"pattern": "混乱", "score": max(patterns["英_中"], patterns["中_英"])}

def test_student(batch_id: str, student_name: str, expected_result: str = None) -> dict:
    """测试单个学生"""
    try:
        student_dir = PROJECT_ROOT / "archive" / batch_id / student_name
        metadata_path = PROJECT_ROOT / "archive" / batch_id / "metadata.json"
        qwen_asr_path = student_dir / "2_qwen_asr.json"

        # 检查文件存在
        if not qwen_asr_path.exists():
            return {
                "student": student_name,
                "status": "SKIP",
                "reason": "缺少 ASR 文件"
            }

        # 加载 metadata
        with open(metadata_path) as f:
            metadata = json.load(f)

        qb_path_str = metadata.get("question_bank_path", "")
        question_bank_path = PROJECT_ROOT / qb_path_str

        # 加载题库和 ASR
        with open(question_bank_path) as f:
            question_bank_content = f.read()

        with open(qwen_asr_path) as f:
            asr_data = json.load(f)
        asr_text = (
            asr_data.get("output", {})
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", [{}])[0]
            .get("text", "")
        )

        # 分析题库和 ASR
        qb_analysis = analyze_questionbank(question_bank_path)
        asr_analysis = analyze_asr_pattern(asr_text)

        # 创建输入
        gatekeeper_input = GatekeeperInput(
            archive_batch=batch_id,
            student_name=student_name,
            question_bank_path=question_bank_path,
            qwen_asr_path=qwen_asr_path,
            verbose=False,
            question_bank_content=question_bank_content,
            asr_text=asr_text,
        )

        # 执行检查
        gatekeeper = QwenPlusGatekeeper()
        result = gatekeeper.check(gatekeeper_input)

        # 预期结果判断
        expected_match = None
        if expected_result:
            expected_match = result.status == expected_result
        else:
            # 自动判断预期：如果题库和 ASR 方向不一致 → FAIL
            if qb_analysis["direction"] != asr_analysis["pattern"] and asr_analysis["pattern"] != "混乱":
                expected_match = result.status == "FAIL"
            else:
                expected_match = None  # 不确定

        return {
            "student": student_name,
            "batch": batch_id,
            "questionbank": qb_path_str,
            "qb_direction": qb_analysis["direction"],
            "asr_pattern": asr_analysis["pattern"],
            "asr_sample": asr_text[:100],
            "result": result.status,
            "issue_type": result.issue_type,
            "response_time": result.format_response_time(),
            "expected": expected_result or "AUTO",
            "match": expected_match,
        }

    except Exception as e:
        return {
            "student": student_name,
            "status": "ERROR",
            "error": str(e)
        }

def main():
    """运行全面测试"""
    print("=" * 100)
    print("ASR Gatekeeper 全面测试")
    print("=" * 100)

    # 测试用例列表
    test_cases = [
        # 已知的测试用例
        ("Abby61000_2025-11-05", "Benjamin", "FAIL"),  # D3 题库，英翻中 ASR
        ("Abby61000_2025-11-05", "Dana", None),
        ("Abby61000_2025-11-05", "Jeffery", None),

        ("Zoe41900_2025-09-08", "Oscar", None),
        ("Zoe41900_2025-09-08", "Cathy", None),
        ("Zoe41900_2025-09-08", "Lucy", None),

        ("Zoe51530_2025-09-08", "Alvin", None),
        ("Zoe51530_2025-09-08", "Kevin", None),
        ("Zoe51530_2025-09-08", "Stefan", None),
    ]

    results = []
    for batch_id, student_name, expected in test_cases:
        print(f"\n测试: {batch_id} / {student_name}")
        result = test_student(batch_id, student_name, expected)
        results.append(result)

        if result.get("status") in ["SKIP", "ERROR"]:
            print(f"  ⊘ {result.get('reason') or result.get('error')}")
        else:
            status_symbol = "✓" if result["result"] == "PASS" else "✗"
            match_symbol = ""
            if result["match"] is True:
                match_symbol = " ✓ 符合预期"
            elif result["match"] is False:
                match_symbol = " ✗ 不符预期"

            print(f"  {status_symbol} {result['result']} - {result['issue_type'] or 'None'} ({result['response_time']}){match_symbol}")
            print(f"     题库: {result['qb_direction']} | ASR: {result['asr_pattern']}")

    # 统计
    print("\n" + "=" * 100)
    print("测试统计")
    print("=" * 100)

    total = len([r for r in results if r.get("status") not in ["SKIP", "ERROR"]])
    passed = len([r for r in results if r.get("result") == "PASS"])
    failed = len([r for r in results if r.get("result") == "FAIL"])
    matched = len([r for r in results if r.get("match") is True])
    mismatched = len([r for r in results if r.get("match") is False])

    print(f"总测试数: {total}")
    print(f"PASS: {passed} | FAIL: {failed}")
    if matched + mismatched > 0:
        print(f"符合预期: {matched} | 不符预期: {mismatched}")

    # 详细结果表格
    print("\n" + "=" * 100)
    print("详细结果")
    print("=" * 100)
    print(f"{'学生':<15} {'题库方向':<10} {'ASR模式':<10} {'结果':<10} {'问题类型':<20} {'预期':<10}")
    print("-" * 100)

    for r in results:
        if r.get("status") not in ["SKIP", "ERROR"]:
            match_mark = ""
            if r["match"] is True:
                match_mark = "✓"
            elif r["match"] is False:
                match_mark = "✗"

            print(f"{r['student']:<15} {r['qb_direction']:<10} {r['asr_pattern']:<10} "
                  f"{r['result']:<10} {r['issue_type'] or '-':<20} {r['expected']:<10} {match_mark}")

    # 保存结果
    output_file = PROJECT_ROOT / "gatekeeper_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_file}")

if __name__ == "__main__":
    main()
