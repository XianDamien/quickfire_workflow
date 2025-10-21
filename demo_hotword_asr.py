#!/usr/bin/env python3
"""
热词增强 ASR 演示脚本
展示如何将题库作为上下文注入到 Qwen3-ASR API 调用中
"""

import os
import json
from pathlib import Path
from scripts.qwen_asr import (
    QwenASRProvider,
    find_vocabulary_file,
    find_audio_file,
    should_process,
)

def demo_hotword_asr():
    """演示热词增强的 ASR 工作流"""

    print("=" * 80)
    print("🎯 Qwen3-ASR 热词增强工作流演示")
    print("=" * 80)

    # 测试两个数据集
    test_cases = [
        ("Zoe51530-9.8", "R3-14-D4.json"),
        ("Zoe41900-9.8", "R1-65.json"),
    ]

    for dataset_name, expected_vocab_file in test_cases:
        print(f"\n{'─' * 80}")
        print(f"📚 数据集: {dataset_name}")
        print(f"{'─' * 80}")

        project_root = Path(".")
        dataset_path = project_root / "archive" / dataset_name

        if not dataset_path.exists():
            print(f"✗ 数据集不存在: {dataset_path}")
            continue

        # 查找题库
        shared_context = dataset_path / "_shared_context"
        vocab_file = find_vocabulary_file(shared_context)

        if not vocab_file:
            print(f"✗ 未找到题库文件")
            continue

        print(f"\n[✓] 题库文件: {vocab_file.name}")

        # 加载题库
        try:
            vocab = QwenASRProvider.load_vocabulary(str(vocab_file))
            print(f"[✓] 加载成功: {len(vocab)} 条词汇")
        except Exception as e:
            print(f"[✗] 加载失败: {e}")
            continue

        # 构建上下文
        context = QwenASRProvider.build_context_text(vocab)
        print(f"[✓] 上下文: {len(context)} 字符")

        # 找到第一个需要处理的学生
        student_dirs = sorted([d for d in dataset_path.iterdir() if d.is_dir() and not d.name.startswith("_")])

        for student_dir in student_dirs:
            # 检查是否应该处理
            if not should_process(student_dir):
                continue

            audio_file = find_audio_file(student_dir)
            if not audio_file:
                continue

            print(f"\n[→] 处理学生: {student_dir.name}")
            print(f"    🎙️  音频文件: {audio_file.name}")

            # 生成 API 消息格式
            abs_audio_path = audio_file.resolve()
            audio_url = f"file://{abs_audio_path}"

            messages = [
                {
                    "role": "system",
                    "content": [
                        {"text": context}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"audio": audio_url}
                    ]
                }
            ]

            # 显示 API 调用格式
            print(f"\n    📋 API 调用格式:")
            print(f"       model: qwen3-asr-flash")
            print(f"       messages: [")
            print(f"           {{")
            print(f"               'role': 'system',")
            print(f"               'content': [{{'text': '{context[:60]}...'}}]")
            print(f"           }},")
            print(f"           {{")
            print(f"               'role': 'user',")
            print(f"               'content': [{{'audio': '{audio_url[-40:]}'}}]")
            print(f"           }}")
            print(f"       ]")
            print(f"       asr_options: {{'enable_itn': False, 'enable_lid': True}}")

            print(f"\n    💡 上下文内容示例 (前 5 个词汇):")
            for i, (key, values) in enumerate(list(vocab.items())[:5]):
                if len(values) >= 2:
                    print(f"       • {values[0]} → {values[1]}")

            # 只演示第一个需要处理的学生
            break

    print(f"\n{'=' * 80}")
    print("✅ 演示完成")
    print("=" * 80)

    print("\n📊 总结:")
    print("   ✓ 热词上下文已自动从题库提取")
    print("   ✓ 上下文被注入到 System Message 中")
    print("   ✓ Qwen3-ASR 使用上下文优化识别")
    print("   ✓ 支持 JSON 和 CSV 题库格式")

    print("\n🚀 完整处理命令:")
    print("   python3 scripts/qwen_asr.py --dataset Zoe51530-9.8")
    print("   python3 scripts/qwen_asr.py --dataset Zoe41900-9.8 --student Alvin")

if __name__ == "__main__":
    demo_hotword_asr()
