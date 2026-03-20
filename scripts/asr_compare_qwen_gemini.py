# -*- coding: utf-8 -*-
"""
对比 Qwen3-ASR-Flash 与 Gemini Flash Lite 的转录效果。
使用同一份 context prompt 作为控制变量。

Usage:
    python scripts/asr_compare_qwen_gemini.py <audio_path> [--all]

    --all: 转录目录下所有音频文件（默认只转录第一个）
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

# 加载 scripts/.env
load_dotenv(Path(__file__).parent / ".env")


def load_context_prompt() -> str:
    """加载 ASR context prompt。"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "asr_context" / "system.md"
    return prompt_path.read_text(encoding="utf-8").strip()


def transcribe_qwen(audio_path: str, context: str) -> dict:
    """用 Qwen3-ASR-Flash 转录。"""
    import dashscope

    messages = [
        {"role": "system", "content": [{"text": context}]},
        {"role": "user", "content": [{"audio": f"file://{os.path.abspath(audio_path)}"}]},
    ]

    t0 = time.time()
    resp = dashscope.MultiModalConversation.call(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        model="qwen3-asr-flash",
        messages=messages,
        result_format="message",
        asr_options={"enable_itn": False},
    )
    elapsed = time.time() - t0

    # 提取文本
    text = ""
    if resp and isinstance(resp, dict):
        output = resp.get("output") or {}
        choices = output.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", [])
            if isinstance(content, list) and content:
                text = content[0].get("text", "")
            elif isinstance(content, str):
                text = content

    return {"text": text, "elapsed": round(elapsed, 2), "raw": resp}


def transcribe_gemini(audio_path: str) -> dict:
    """用 Gemini Flash Lite 转录。"""
    # 将 scripts/ 加入 sys.path 以支持直接运行
    scripts_dir = str(Path(__file__).parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from common.gemini import create_gemini_client

    client = create_gemini_client()

    # 上传音频文件（文件名需 ASCII 安全，否则 httpx header 编码失败）
    print("  [Gemini] 上传音频文件...")
    suffix = Path(audio_path).suffix
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    shutil.copy2(audio_path, tmp.name)
    try:
        uploaded = client.files.upload(file=tmp.name)
    finally:
        os.unlink(tmp.name)
    print(f"  [Gemini] 上传完成: {uploaded.name}")

    # 构建 prompt：强调逐字转录 + 说话人分离 + 极端情况处理
    prompt = """你是一个专业的语音转录引擎，具备说话人分离（speaker diarization）能力。请对以下音频进行**逐字逐句的完整转录**（verbatim transcription）。

## 场景说明
这是英语单词抽背录音，有**预录音频（成年男性声音，标准发音，音质清晰稳定）**和**学生（小孩，现场录音，音量小且可能口齿不清）**两个声源交替出现。典型流程：
- 预录音频说英文单词 → 学生回答中文释义 → 预录音频说英文例句 → 学生跟读单词或回答
- 预录音频的声音特征：成年男性、标准清晰、音量稳定
- 学生的声音特征：小孩、音量小、可能含糊不清、可能与预录音频重叠

## 关键要求

### 说话人分离（最重要）
- 使用 `[预录]` 和 `[学生]` 标签标注每段话的来源
- **当预录音频和学生同时发声（语音重叠）时，必须分别转录两个声源的内容**，不能只保留声音大的一方
- 学生可能在预录音频播放例句的过程中小声回答，这个回答必须被捕获

### 极端情况处理（重点关注）
1. **学生声音极小**：学生是小孩，声音可能非常小、几乎听不到，但只要有任何人声痕迹，都必须尽力识别并转录。宁可转录不准确，也不要跳过
2. **语音重叠**：预录音频在播放例句时，学生可能同时在小声说单词或释义。预录音频是成年男性清晰声音，学生是小孩微弱声音，两者音色差异大，请利用这个特征分离
3. **口齿不清**：小孩发音不标准、含糊不清，用最接近的文字转录，不要跳过
4. **倍速音频**：音频经过加速处理，语速很快，低音量片段不是噪音，是有效语音内容

### 转录规则
- 必须转录每一个字，包括重复、停顿、口头禅
- 绝对不要做摘要或提炼
- 如果听不清具体内容但能听到有人在说话，标注为 `[学生] (模糊语音)` 或 `[学生] (低声)`

请输出带声源标签的完整转录文本。"""

    t0 = time.time()
    resp = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=[prompt, uploaded],
    )
    elapsed = time.time() - t0

    text = resp.text if resp.text else ""

    # 提取 usage
    um = getattr(resp, "usage_metadata", None)
    usage = {}
    if um:
        usage = {
            "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
        }

    return {"text": text, "elapsed": round(elapsed, 2), "usage": usage}


def compare_one(audio_path: str, context: str) -> dict:
    """对一个音频文件做对比转录。"""
    # 用父目录名标识学生（archive 结构）
    parent = Path(audio_path).parent.name
    fname = Path(audio_path).name
    label = parent if fname == "1_input_audio.mp3" else fname
    print(f"\n{'='*60}")
    print(f"音频: {label}")
    print(f"{'='*60}")

    err = lambda model, e: {"text": f"[ERROR] {e}", "elapsed": 0}

    # Qwen
    print("\n--- Qwen3-ASR-Flash ---")
    try:
        qwen_result = transcribe_qwen(audio_path, context)
    except Exception as e:
        print(f"  ❌ Qwen 失败: {e}")
        qwen_result = err("qwen", e)
    print(f"  耗时: {qwen_result['elapsed']}s")
    print(f"  字数: {len(qwen_result['text'])}")
    print(f"  文本: {qwen_result['text'][:200]}...")

    # Gemini
    print("\n--- Gemini 3.1 Flash Lite ---")
    try:
        gemini_result = transcribe_gemini(audio_path)
    except Exception as e:
        print(f"  ❌ Gemini 失败: {e}")
        gemini_result = err("gemini", e)
    print(f"  耗时: {gemini_result['elapsed']}s")
    print(f"  字数: {len(gemini_result['text'])}")
    print(f"  文本: {gemini_result['text'][:200]}...")

    return {
        "audio": label,
        "qwen": {"text": qwen_result["text"], "elapsed": qwen_result["elapsed"], "char_count": len(qwen_result["text"])},
        "gemini": {"text": gemini_result["text"], "elapsed": gemini_result["elapsed"], "char_count": len(gemini_result["text"]), "usage": gemini_result.get("usage", {})},
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/asr_compare_qwen_gemini.py <audio_path_or_dir> [--all]")
        sys.exit(1)

    target = sys.argv[1]
    do_all = "--all" in sys.argv

    context = load_context_prompt()
    print(f"Qwen context prompt ({len(context)} chars):")
    print(f"  {context[:80]}...")
    print("Gemini: 使用独立 prompt（含说话人分离指令）")

    # 收集音频文件
    if os.path.isdir(target):
        # 支持 archive 目录结构：子目录/1_input_audio.mp3
        archive_audios = sorted(Path(target).glob("*/1_input_audio.mp3"))
        if archive_audios:
            audio_files = [str(p) for p in archive_audios]
        else:
            audio_files = sorted(str(p) for p in Path(target).glob("*.mp3"))
        if not do_all:
            audio_files = audio_files[:1]
    else:
        audio_files = [target]

    print(f"\n待转录音频: {len(audio_files)} 个")

    results = []
    for af in audio_files:
        r = compare_one(af, context)
        results.append(r)

    # 保存结果
    out_dir = Path(__file__).parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "asr_compare_qwen_vs_gemini.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")

    # 打印摘要
    print(f"\n{'='*60}")
    print("摘要对比")
    print(f"{'='*60}")
    for r in results:
        print(f"\n{r['audio']}:")
        print(f"  Qwen:   {r['qwen']['char_count']} 字 / {r['qwen']['elapsed']}s")
        print(f"  Gemini: {r['gemini']['char_count']} 字 / {r['gemini']['elapsed']}s")


if __name__ == "__main__":
    main()
