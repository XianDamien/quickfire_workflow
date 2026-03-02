# -*- coding: utf-8 -*-
"""
Prompt 回归测试: 从指定批次随机抽样，确认新 prompt 无回退。

用法:
    python skills/qwen-asr-context/scripts/prompt_regression.py \
        --batch-dir two_output/SomeBatch_2026-01-01 \
        --old-prompt "@prompts/asr_context/system.md.bak" \
        --new-prompt "@prompts/asr_context/system.md" \
        [--sample-size 10] [--seed 42] [--threshold 0.8] [--output results.json]

回退判定: 新 prompt 字数 < 旧 * threshold 视为回退（默认 0.8）。
"""

import argparse
import json
import random
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
    parser = argparse.ArgumentParser(description="Prompt 回归测试")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--old-prompt", required=True)
    parser.add_argument("--new-prompt", required=True)
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    from scripts.common.env import load_env
    from scripts.asr.qwen import QwenASRProvider

    load_env()
    provider = QwenASRProvider()
    old_prompt = load_prompt(args.old_prompt)
    new_prompt = load_prompt(args.new_prompt)

    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_absolute():
        batch_dir = project_root / batch_dir

    all_audios = sorted(batch_dir.rglob("_audio.mp3"))
    if not all_audios:
        print(f"❌ 未找到音频: {batch_dir}")
        sys.exit(1)

    random.seed(args.seed)
    samples = random.sample(all_audios, min(args.sample_size, len(all_audios)))

    results, regressions = [], 0
    for i, audio_path in enumerate(samples, 1):
        case_name = f"{audio_path.parent.parent.name}/{audio_path.parent.name}"
        audio_url = f"file://{audio_path.resolve()}"

        old_text = extract_text(provider.transcribe_audio(audio_path=audio_url, system_context_override=old_prompt))
        new_text = extract_text(provider.transcribe_audio(audio_path=audio_url, system_context_override=new_prompt))

        old_len, new_len = len(old_text), len(new_text)
        regressed = old_len > 0 and new_len < old_len * args.threshold
        if regressed:
            regressions += 1

        status = "⚠️" if regressed else "✅"
        print(f"[{i}/{len(samples)}] {status} {case_name}: {old_len} → {new_len}")

        results.append({"case": case_name, "old_len": old_len, "new_len": new_len,
                         "delta": new_len - old_len, "regressed": regressed})

    print(f"\n汇总: {len(samples)} 样本, {regressions} 个回退")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✅ 结果已保存: {args.output}")

    if regressions > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
