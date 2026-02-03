#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_qwen_omni.py - Qwen3-Omni Annotator 测试脚本

测试 Qwen3-Omni Flash 模型的音频标注功能。
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.annotators import get_annotator
from scripts.common.runs import new_run_id, ensure_run_dir

# 使用现有测试数据
TEST_BATCH = "Zoe61330_2025-12-30"
TEST_STUDENT = "Cici"


def main():
    """主测试函数"""
    print("=" * 80)
    print("Qwen3-Omni Flash Annotator 测试")
    print("=" * 80)
    print()

    try:
        # 获取 annotator
        print("🔧 初始化 Qwen3-Omni Flash annotator...")
        annotator = get_annotator("qwen-omni-flash")
        print(f"✓ Annotator: {annotator.name}")
        print(f"✓ Model: {annotator.model}")
        print(f"✓ Max output tokens: {annotator.max_output_tokens}")
        print()

        # 创建 run 目录
        run_id = new_run_id()
        run_dir = ensure_run_dir(TEST_BATCH, TEST_STUDENT, annotator.name, run_id)
        print(f"📁 Run 目录: {run_dir}")
        print()

        # 执行标注
        print(f"🎯 开始标注学生: {TEST_STUDENT}")
        print(f"📦 批次: {TEST_BATCH}")
        print()

        result = annotator.run_archive_student(
            archive_batch=TEST_BATCH,
            student_name=TEST_STUDENT,
            run_dir=run_dir,
            verbose=True
        )

        # 显示结果
        print()
        print("=" * 80)
        print("测试结果")
        print("=" * 80)

        if result.success:
            print(f"✅ 标注成功!")
            print(f"  学生: {result.student_name}")
            print(f"  评分: {result.final_grade}")
            print(f"  错误统计: {result.mistake_count}")
            print(f"  响应时间: {result.format_response_time()}")
            print(f"  Run ID: {result.run_id}")

            if result.validation:
                validation_status = result.validation.get("status", "UNKNOWN")
                print(f"  Validation: {validation_status}")
                if validation_status == "FAIL":
                    errors = result.validation.get("errors", [])
                    print(f"  Validation 错误: {errors}")

            print(f"\n📂 输出文件位于: {result.run_dir}")
        else:
            print(f"❌ 标注失败: {result.error}")
            return 1

        print()
        print("=" * 80)
        print("测试通过! ✅")
        print("=" * 80)
        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ 测试失败: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
