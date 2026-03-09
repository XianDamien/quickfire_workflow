# -*- coding: utf-8 -*-
"""
Prompt A/B 对比测试: 在指定音频上对比旧版 vs 新版 prompt 的转写效果。

用法:
    python skills/qwen-asr-context/scripts/prompt_ab_test.py \
        --audio path/to/_audio.mp3 [path/to/_audio2.mp3 ...] \
        --old-prompt "@prompts/asr_context/system.md.bak" \
        --new-prompt "@prompts/asr_context/system.md" \
        [--output results.json]

以 @ 开头的参数从文件读取 prompt 内容。
"""

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def load_prompt(value: str) -> str:
    if value.startswith("@"):
        path = Path(value[1:])
        if not path.is_absolute():
            path = project_root / path
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return value


def extract_text(response: dict) -> str:
    try:
        return response["output"]["choices"][0]["message"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return str(response)


def main():
    parser = argparse.ArgumentParser(description="Prompt A/B 对比测试")
    parser.add_argument("--audio", nargs="+", required=True)
    parser.add_argument("--old-prompt", required=True)
    parser.add_argument("--new-prompt", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    from scripts.common.env import load_env
    from scripts.asr.qwen import QwenASRProvider

    load_env()
    provider = QwenASRProvider()
    old_prompt = load_prompt(args.old_prompt)
    new_prompt = load_prompt(args.new_prompt)

    results = []
    for audio_str in args.audio:
        audio_path = Path(audio_str).resolve()
        if not audio_path.exists():
            print(f"⚠️  跳过: {audio_path}")
            continue

        case_name = f"{audio_path.parent.parent.name}/{audio_path.parent.name}"
        audio_url = f"file://{audio_path}"

        old_text = extract_text(provider.transcribe_audio(audio_path=audio_url, system_context_override=old_prompt))
        new_text = extract_text(provider.transcribe_audio(audio_path=audio_url, system_context_override=new_prompt))

        delta = len(new_text) - len(old_text)
        sign = "+" if delta > 0 else ""
        print(f"{case_name}: {len(old_text)} → {len(new_text)} ({sign}{delta})")
        print(f"  旧: {old_text[:80]}")
        print(f"  新: {new_text[:80]}")

        results.append({"case": case_name, "old": old_text, "new": new_text,
                         "old_len": len(old_text), "new_len": len(new_text)})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存: {args.output}")


if __name__ == "__main__":
    main()
