#!/usr/bin/env python3
"""
单个学生的实际 ASR 处理测试
演示热词增强的完整工作流
"""

import sys
import os
from pathlib import Path

# 确保 DASHSCOPE_API_KEY 已设置
if not os.getenv("DASHSCOPE_API_KEY"):
    print("❌ 错误: 请先设置 DASHSCOPE_API_KEY 环境变量")
    print("   export DASHSCOPE_API_KEY='sk-xxxxx'")
    sys.exit(1)

from scripts.qwen_asr import process_student

def main():
    """处理单个学生的 ASR"""

    print("=" * 80)
    print("🎤 单个学生 ASR 处理测试 (热词增强)")
    print("=" * 80)

    # 测试用例
    test_cases = [
        ("Zoe51530-9.8", "Alvin"),
        ("Zoe41900-9.8", "Cathy"),
    ]

    for dataset_name, student_name in test_cases:
        print(f"\n{'─' * 80}")
        print(f"📚 数据集: {dataset_name}")
        print(f"👤 学生: {student_name}")
        print(f"{'─' * 80}\n")

        exit_code = process_student(dataset_name, student_name)

        if exit_code == 0:
            print(f"\n✅ 成功处理 {student_name}")
            # 检查输出文件
            output_file = Path(f"archive/{dataset_name}/{student_name}/2_qwen_asr.json")
            if output_file.exists():
                print(f"   📄 输出文件: {output_file}")
                print(f"   📊 文件大小: {output_file.stat().st_size} 字节")
        else:
            print(f"\n❌ 处理失败: {student_name}")

    print(f"\n{'=' * 80}")
    print("✅ 测试完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
