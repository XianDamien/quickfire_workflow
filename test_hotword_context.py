#!/usr/bin/env python3
"""
热词上下文增强功能测试脚本
演示 Qwen3-ASR 如何利用题库 CSV 作为上下文来优化识别准确率
"""

import sys
from pathlib import Path
from scripts.qwen_asr import (
    QwenASRProvider,
    find_vocabulary_file,
)

def test_hotword_context():
    """测试热词上下文增强功能"""

    print("=" * 70)
    print("Qwen3-ASR 热词上下文增强功能测试")
    print("=" * 70)

    # 测试数据集
    test_datasets = [
        ("archive/Zoe51530-9.8/_shared_context", "Zoe51530-9.8 (R3-14)"),
        ("archive/Zoe41900-9.8/_shared_context", "Zoe41900-9.8 (R1-65)"),
    ]

    for shared_context_path, dataset_name in test_datasets:
        print(f"\n{'─' * 70}")
        print(f"数据集: {dataset_name}")
        print(f"{'─' * 70}")

        shared_context = Path(shared_context_path)

        if not shared_context.exists():
            print(f"⚠️  路径不存在: {shared_context}")
            continue

        # 查找题库文件
        print("\n[1] 题库文件查找")
        vocab_file = find_vocabulary_file(shared_context)
        if vocab_file:
            print(f"    ✓ 找到题库文件: {vocab_file.name}")
            print(f"    📍 完整路径: {vocab_file}")
        else:
            print(f"    ✗ 未找到题库文件")
            continue

        # 加载词汇表
        print("\n[2] 词汇表加载")
        try:
            vocab = QwenASRProvider.load_vocabulary(str(vocab_file))
            print(f"    ✓ 加载成功，包含 {len(vocab)} 条词汇")
        except Exception as e:
            print(f"    ✗ 加载失败: {e}")
            continue

        # 构建上下文
        print("\n[3] 上下文构建（用于 ASR 识别优化）")
        context = QwenASRProvider.build_context_text(vocab)
        if context:
            print(f"    ✓ 上下文构建成功")
            print(f"    📊 统计信息:")
            print(f"       - 总字符数: {len(context)}")
            print(f"       - Token 数量 (估算): {len(context) // 3} tokens")
            print(f"       - 词汇条数: {len(vocab)}")
            print(f"\n    📋 上下文内容预览 (前 200 字符):")
            print(f"       {context[:200]}...")

            # 显示部分词汇
            print(f"\n    📚 词汇示例 (前 5 条):")
            for i, (key, values) in enumerate(list(vocab.items())[:5]):
                if len(values) >= 2:
                    print(f"       [{i+1}] {values[0]} ({values[1]})")
        else:
            print(f"    ✗ 上下文为空")

        # 说明 System Message 格式
        print("\n[4] 系统消息格式（在 API 调用中使用）")
        print(f"    messages = [")
        print(f"        {{")
        print(f"            'role': 'system',")
        print(f"            'content': [")
        print(f"                {{'text': '{context[:80]}...'}}")
        print(f"            ]")
        print(f"        }},")
        print(f"        {{")
        print(f"            'role': 'user',")
        print(f"            'content': [{{'audio': 'file:///path/to/audio.mp3'}}]")
        print(f"        }}")
        print(f"    ]")

    print(f"\n{'=' * 70}")
    print("✅ 测试完成")
    print("=" * 70)

    print("\n💡 热词上下文的优势:")
    print("   • 显著提升专业词汇识别准确率（如人名、地名、产品术语）")
    print("   • Qwen3-ASR 对分隔符容错性极高（支持多种格式）")
    print("   • 支持任意长度的文本内容（限制: ≤10000 Token）")
    print("   • 无关或无意义文本不会产生负面影响")
    print("\n📖 使用建议:")
    print("   • 将题库内容作为 System Message 的上下文")
    print("   • 可混合多种内容（词表、段落、篇章等）")
    print("   • 监控 Token 使用量，避免超过限制")

if __name__ == "__main__":
    try:
        test_hotword_context()
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)
