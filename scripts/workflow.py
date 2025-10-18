#!/usr/bin/env python3
"""
评测工作流统一入口

这个脚本提供了一个统一的命令行接口，将音频转写和评测评分两个步骤集成到一个工作流中。

使用示例：
    python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv
    python3 workflow.py --audio-path file://./audio/sample.mp3 --qb-path ./data/R1-65(1).csv --output result.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 导入模块函数
from captioner_qwen3 import transcribe_audio
from qwen3 import load_asr_data, load_qb, evaluate_pronunciation
from funasr_workflow import upload_audio_to_oss, transcribe_with_funasr, normalize_asr_output


# ===== 系统提示词（复用自 qwen3.py）=====
SYSTEM_PROMPT = """你是一个专业的AI语言教师助教。你的任务是基于学生提交的录音、对应的题库和ASR（自动语音识别）转写结果，对学生的"单词快反"作业进行客观、准确的评测。
你是一个AI助教，一个数据标记员。你的任务是分析学生录音转写文本，为教师生成一份结构化的JSON格式高亮报告。你的输出**必须**是**单一、有效**的JSON对象，**不包含任何解释性文字**。
**"该音频是一个用于ASR分析的异步、双轨语音交互数据。它包含以下结构化特征："**
*   **教师轨道 (预录制):** 一个固定的、时间轴精确的音频流，作为"主干"音轨。
*   **交互循环 (Call-and-Response Loop):** 该轨道遵循一个固定的 `[提问 -> 静默期 -> 答案]` 模式。
    *   **提问 (Prompt):** 教师发出一个语言提示（例如，中文词汇）。
    *   **静默期 (Response Window):** 预留一段空白时间，作为学生应答的窗口。
    *   **答案 (Answer Key):** 教师公布标准答案（例如，英文翻译）。
*   **学生轨道 (实时录制):** 学生的语音被实时捕获，并叠加在教师轨道上。分析的核心是评估学生在该交互循环中的表现，包括响应延迟、内容准确性和发音清晰度。

你的核心职责：

角色识别：根据题库内容和ASR结果，识别出哪个speaker是提问的老师，哪个是回答的学生。

逐项评估：严格按照题库顺序，将学生的每一次回答与标准答案进行匹配和评估。

精确判断：利用你强大的多模态能力，亲自"聆听"音频来判断PRONUNCIATION_ERROR（发音错误）和UNCLEAR_PRONUNCIATION（发音不清）这类ASR可能误判的情况。

严格遵守规则：严格遵循下面定义的评分标准和错误类型。

格式化输出：你的最终输出必须是一个单一、完整、且格式完全正确的JSON对象，不得包含任何额外的解释性文字。

输入信息
1. 题库上下文 (标准答案)
这是一个JSON数组，包含了所有题目的问题和期望答案。

举例：

[{"班级":"Zoe41900","日期":9.8,"index":1,"question":"数字；数","expected_answer":"number"},{"班级":"Zoe41900","日期":9.8,"index":2,"question":"一百","expected_answer":"hundred"},{"班级":"Zoe41900","日期":9.8,"index":3,"question":"千","expected_answer":"thousand"}]

2. ASR转写结果 (机器初步识别)
这是一个JSON数组，包含了音频中每一句话的说话人、文本内容和起止时间戳（单位：毫秒）。

[
  {
    "speaker": "spk0",
    "text": "",
    "start_time": 0,
    "end_time": 0,
    "word_timestamp": []
  }
]

3. 原始音频文件
音频文件已作为多模态输入提供给你。请在需要判断发音时，务必参考原始音频。

核心业务规则与评分标准
错误/观察点类型定义
你需要在评估时，为每个有问题的回答打上以下标签之一：

标识符

中文说明

判定核心依据

MEANING_ERROR

语义错误

硬性错误。学生回答的单词在文本上与答案完全不符，导致意思错误（例如，题库是boot，学生回答boat）。

PRONUNCIATION_ERROR

发音错误

软性观察点。学生说的词语义上可能是对的，但发音不准导致ASR识别成了另一个词。你必须听音频来确认。

UNCLEAR_PRONUNCIATION

发音不清

软性观察点。学生声音太小、含糊不清，导致ASR没能识别出内容。你必须听音频来确认。

SLOW_RESPONSE

回答过慢

软性观察点。学生的回答开始时间(start_time) 大于或等于(>=) 老师公布该题正确答案的开始时间。这是一个基于时间戳的客观判断，无需听音频。

最终评级逻辑 (由MEANING_ERROR数量决定)
A级: 0 个 MEANING_ERROR

B级: 1-2 个 MEANING_ERROR

C级: 3个及以上 MEANING_ERROR

任务指令
请严格按照以下JSON格式，生成你的评测报告：

{
  "final_grade_suggestion": "A/B/C中的一个",
  "mistake_count": {
    "hard_errors": 0, // MEANING_ERROR 的总数
    "soft_errors": 0  // 所有软性观察点 (PRONUNCIATION_ERROR, UNCLAER_PRONUNCIATION, SLOW_RESPONSE) 的总数
  },
  "annotations": [
    // 遍历题库中的每一道题，生成一个对应的条目
    {
      "card_index": 0, // 题库中题目的索引（从0开始）
      "question": "题库中的问题",
      "expected_answer": "题库中的标准答案",
      "related_student_utterance": { // 匹配到的学生回答
        "detected_text": "ASR识别出的学生回答文本",
        "start_time": 12345, // 学生回答的开始时间（毫秒）
        "end_time": 12890,   // 学生回答的结束时间（毫秒）
        "issue_type": "MEANING_ERROR" // 如果有错误，填入对应的标识符；如果回答正确，则为 null
      }
    },
    {
      "card_index": 1,
      "question": "另一道题",
      "expected_answer": "另一个答案",
      "related_student_utterance": null // 如果学生对这道题完全没有作答，则此字段为 null
    }
    // ... 更多条目
  ]
}

请开始分析，并仅输出JSON结果。"""


def load_env_config(env_path: str = ".env") -> dict:
    """
    从 .env 文件读取 OSS 相关配置和凭证

    Args:
        env_path: .env 文件路径，默认为项目根目录的 .env

    Returns:
        dict: 配置字典，包含以下键（若存在）：
            - bucket: OSS 桶名称 (来自 OSS_BUCKET_NAME)
            - region: OSS 区域 (来自 OSS_REGION)
            - endpoint: OSS 端点 (来自 OSS_ENDPOINT)
            - access_key_id: OSS 访问密钥 ID (来自 OSS_ACCESS_KEY_ID)
            - access_key_secret: OSS 访问密钥 Secret (来自 OSS_ACCESS_KEY_SECRET)
    """
    config = {}

    # 检查文件是否存在
    if not Path(env_path).exists():
        return config

    try:
        # 手动解析 .env（避免引入新依赖）
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if line.startswith('#') or '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"\'')

                # 映射 .env 键到配置字典
                if key == 'OSS_BUCKET_NAME':
                    config['bucket'] = value
                elif key == 'OSS_REGION':
                    config['region'] = value
                elif key == 'OSS_ENDPOINT':
                    config['endpoint'] = value
                elif key == 'OSS_ACCESS_KEY_ID':
                    config['access_key_id'] = value
                elif key == 'OSS_ACCESS_KEY_SECRET':
                    config['access_key_secret'] = value
                elif key == 'DASHSCOPE_API_KEY':
                    config['dashscope_api_key'] = value

    except Exception as e:
        print(f"⚠️  警告：读取 .env 失败 ({str(e)})，继续使用命令行参数")

    return config


def verify_oss_credentials(region: str, bucket: str, endpoint: str = None) -> tuple:
    """
    验证 OSS 凭证和参数的有效性

    Args:
        region: OSS 区域（如 cn-shanghai）
        bucket: OSS 桶名称
        endpoint: OSS 端点（可选）

    Returns:
        (success: bool, message: str)
            - success=True: 凭证有效
            - success=False: 凭证无效，message 包含故障信息
    """
    try:
        import alibabacloud_oss_v2 as oss

        # 从环境变量读取 OSS 凭证
        # 优先级：ALIBABA_CLOUD_* → OSS_* → .env 文件
        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')

        # 如果标准环境变量不存在，尝试读取 OSS_* 格式的变量
        if not access_key_id or not access_key_secret:
            access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
            access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')

        if not access_key_id or not access_key_secret:
            return False, ("❌ OSS 凭证验证失败: 凭证缺失\n"
                          "💡 诊断建议：\n"
                          "   - 设置环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET\n"
                          "   - 或设置环境变量 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET\n"
                          "   - 或配置 .env 文件中的 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET")

        # 使用静态凭证提供器
        credentials_provider = oss.credentials.StaticCredentialsProvider(access_key_id, access_key_secret)
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region
        if endpoint:
            cfg.endpoint = endpoint

        # 尝试创建客户端
        client = oss.Client(cfg)

        # 轻量级测试：尝试检查桶是否存在
        exists = client.is_bucket_exist(bucket)

        if exists:
            return True, "✅ OSS 凭证验证通过"
        else:
            return False, f"❌ OSS 验证失败: 桶不存在或无访问权限"

    except ImportError:
        return False, "❌ 缺少 alibabacloud_oss_v2 依赖，请安装：pip install alibabacloud_oss_v2"
    except Exception as e:
        error_str = str(e)
        suggestions = []

        # 根据错误信息提供建议
        if "NoSuchBucket" in error_str or "404" in error_str:
            suggestions.append("- 检查 OSS 桶名称是否正确")
            suggestions.append("- 检查 OSS 区域是否与桶对应")
        elif "AccessDenied" in error_str or "403" in error_str:
            suggestions.append("- 检查 OSS 凭证权限（需要 GetBucketInfo 权限）")
            suggestions.append("- 验证凭证是否有效（OSS_ACCESS_KEY_ID/SECRET 或 ALIBABA_CLOUD_ACCESS_KEY_*）")
        elif "InvalidAccessKeyId" in error_str:
            suggestions.append("- 检查 OSS_ACCESS_KEY_ID 是否正确")
        elif "InvalidAccessKeySecret" in error_str:
            suggestions.append("- 检查 OSS_ACCESS_KEY_SECRET 是否正确")
        elif "Network" in error_str or "Connection" in error_str:
            suggestions.append("- 检查网络连接")
            suggestions.append("- 检查 OSS 端点是否正确")

        message = f"❌ OSS 凭证验证失败: {error_str}\n"
        if suggestions:
            message += "💡 诊断建议：\n"
            for s in suggestions:
                message += f"   {s}\n"

        return False, message


def validate_file(filepath):
    """验证文件是否存在"""
    if not Path(filepath).exists():
        print(f"❌ 错误：文件不存在 - {filepath}")
        sys.exit(1)


def run_workflow(audio_path, qb_path, output_path=None, api_key=None, asr_engine="qwen", oss_region=None, oss_bucket=None, oss_endpoint=None, keep_oss_file=False):
    """
    执行评测工作流：音频转写 → 评测评分 → 输出报告

    Args:
        audio_path (str): 音频文件路径
        qb_path (str): 题库文件路径
        output_path (str, optional): 输出文件路径，如果为None则打印到控制台
        api_key (str, optional): DashScope API密钥，默认从环境变量读取
        asr_engine (str, optional): ASR 引擎选择 ("qwen" 或 "funasr")，默认 "qwen"
        oss_region (str, optional): OSS 区域（FunASR 模式必需）
        oss_bucket (str, optional): OSS 桶名称（FunASR 模式必需）
        oss_endpoint (str, optional): OSS 端点（可选）
        keep_oss_file (bool, optional): 转写后是否保留 OSS 文件，默认 False

    Returns:
        dict: 评测结果（JSON对象）
    """
    if api_key is None:
        api_key = os.getenv('DASHSCOPE_API_KEY')
        if not api_key:
            print("❌ 错误：未设置 DASHSCOPE_API_KEY")
            print("💡 解决方案：")
            print("   方案 1：在 .env 文件中添加 DASHSCOPE_API_KEY=sk-xxxxx")
            print("   方案 2：设置环境变量 export DASHSCOPE_API_KEY=sk-xxxxx")
            print("   方案 3：使用命令行参数 --api-key sk-xxxxx")
            sys.exit(1)

    print("=" * 60)
    print("📊 评测工作流启动")
    print("=" * 60)

    # 第1步：验证输入文件和参数
    print("\n✓ 第1步：验证输入参数...")
    validate_file(qb_path)
    # audio_path 可能是 file:// 格式，只验证普通路径
    if not audio_path.startswith("file://"):
        validate_file(audio_path)
    print(f"   音频文件: {audio_path}")
    print(f"   题库文件: {qb_path}")
    print(f"   ASR 引擎: {asr_engine}")

    # 如果使用 FunASR，验证必需参数
    if asr_engine == "funasr":
        if not oss_region or not oss_bucket:
            print("❌ 错误：使用 FunASR 模式必须指定 --oss-region 和 --oss-bucket")
            print("\n用法示例：")
            print("  python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv \\")
            print("    --asr-engine funasr --oss-region cn-hangzhou --oss-bucket your-bucket")
            sys.exit(1)

    # 第1.5步：验证 OSS 凭证（仅 FunASR 模式）
    if asr_engine == "funasr":
        print("\n✓ 第1.5步：验证 OSS 凭证...")
        success, message = verify_oss_credentials(oss_region, oss_bucket, oss_endpoint)
        print(message)
        if not success:
            sys.exit(1)

    # 第2步：音频转写
    print("\n✓ 第2步：执行音频转写 (ASR)...")
    try:
        if asr_engine == "qwen":
            # 使用 Qwen 多模态 ASR
            print(f"   🎵 使用 Qwen 引擎转写音频，请稍候...")
            asr_result = transcribe_audio(audio_path, api_key=api_key)
            print("   ✅ Qwen 音频转写完成")

        elif asr_engine == "funasr":
            # 使用 FunASR 引擎
            print(f"   🎵 使用 FunASR 引擎转写音频...")
            print(f"   第 2.1 步：上传音频到 OSS...")
            try:
                oss_url, status_code, file_key = upload_audio_to_oss(
                    local_path=audio_path,
                    region=oss_region,
                    bucket=oss_bucket,
                    endpoint=oss_endpoint
                )
                print(f"   ✅ 上传完成")
            except Exception as e:
                print(f"   ❌ 上传失败: {str(e)}")
                print("   💡 诊断建议：")
                print("      - 检查 OSS 区域和桶名称是否正确")
                print("      - 验证 OSS 凭证权限（需要 PutObject 权限）")
                print("      - 检查环境变量是否配置（ALIBABA_CLOUD_*）")
                sys.exit(1)

            print(f"   第 2.2 步：调用 FunASR 进行转写...")
            try:
                funasr_output = transcribe_with_funasr(oss_url)
                # 标准化 FunASR 输出
                asr_result = normalize_asr_output(funasr_output)
                print("   ✅ FunASR 音频转写完成")
            except Exception as e:
                print(f"   ❌ 转写失败: {str(e)}")
                sys.exit(1)

        else:
            print(f"❌ 错误：不支持的 ASR 引擎: {asr_engine}")
            sys.exit(1)

        # 可观测性输出：ASR 转写结果
        print("\n" + "=" * 60)
        print("📄 ASR 转写原始结果")
        print("=" * 60)
        print(asr_result)

    except Exception as e:
        print(f"   ❌ 转写失败: {str(e)}")
        sys.exit(1)

    # 第3步：加载题库
    print("\n✓ 第3步：加载题库数据...")
    try:
        qb_data = load_qb(qb_path)
        print(f"   ✅ 题库加载完成")

        # 可观测性输出：题库摘要
        lines = qb_data.strip().split('\n')
        print("\n" + "=" * 60)
        print("📚 题库摘要")
        print("=" * 60)
        print(f"题库条目数: {len(lines) - 1}")  # 去掉 header
        print(f"字段: {lines[0] if lines else 'N/A'}")

    except Exception as e:
        print(f"   ❌ 加载失败: {str(e)}")
        sys.exit(1)

    # 第4步：执行评测
    print("\n✓ 第4步：执行发音评测...")
    try:
        # 可观测性输出：AI 评测提示词结构（在调用前）
        asr_prompt = "以下是本音频的ASR数据，包括时间戳和说话人识别数据:\n" + asr_result
        qb_prompt = "本次作业的题库，老师给的标准问题和答案（以csv形式给出）\n" + qb_data

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
        evaluation_result = evaluate_pronunciation(asr_result, qb_data, api_key=api_key)
        print("   ✅ 评测完成")

        # 可观测性输出：AI 评测结果 JSON
        print("\n" + "=" * 60)
        print("📊 AI 评测结果 (JSON)")
        print("=" * 60)
        try:
            result_json = json.loads(evaluation_result)
            print(json.dumps(result_json, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(evaluation_result)

    except Exception as e:
        print(f"   ❌ 评测失败: {str(e)}")
        sys.exit(1)

    # 第5步：输出结果
    print("\n✓ 第5步：输出评测报告...")
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(evaluation_result)
            print(f"   ✅ 报告已保存到: {output_path}")
        except Exception as e:
            print(f"   ❌ 保存失败: {str(e)}")
            sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("📋 评测报告结果")
        print("=" * 60)
        print(evaluation_result)

    print("\n" + "=" * 60)
    print("✨ 工作流执行完成！")
    print("=" * 60)

    return evaluation_result


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="英语发音作业评测系统 - 统一工作流入口 (支持多种 ASR 引擎)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基础用法 (Qwen ASR，输出到控制台)
  python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv

  # 指定输出文件 (Qwen ASR)
  python3 workflow.py --audio-path ../audio/sample.mp3 --qb-path ../data/R1-65(1).csv --output result.json

  # 使用 FunASR 引擎 (从 .env 自动读取 OSS 配置)
  python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \\
    --asr-engine funasr

  # 使用 FunASR 引擎并通过命令行覆盖 OSS 配置
  python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \\
    --asr-engine funasr --oss-region cn-hangzhou --oss-bucket your-bucket

  # FunASR 引擎（带自定义端点）
  python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/R1-65(1).csv \\
    --asr-engine funasr --oss-region cn-hangzhou --oss-bucket your-bucket \\
    --oss-endpoint oss-cn-hangzhou.aliyuncs.com

  # 使用 file:// 前缀
  python3 workflow.py --audio-path file://./audio/sample.mp3 --qb-path ./data/R1-65(1).csv

参数优先级（从高到低）:
  1. 命令行参数 (--oss-region, --oss-bucket 等)
  2. .env 文件配置 (OSS_REGION, OSS_BUCKET_NAME 等)
  3. 默认值
        """
    )

    parser.add_argument(
        '--audio-path',
        required=True,
        help='音频文件路径（支持相对路径和 file:// 前缀）'
    )
    parser.add_argument(
        '--qb-path',
        required=True,
        help='题库CSV文件路径'
    )
    parser.add_argument(
        '--output',
        default=None,
        help='输出JSON报告文件路径（可选，默认输出到控制台）'
    )
    parser.add_argument(
        '--api-key',
        default=None,
        help='DashScope API密钥（可选，默认从环境变量 DASHSCOPE_API_KEY 读取）'
    )

    # ===== ASR 引擎选择 =====
    parser.add_argument(
        '--asr-engine',
        choices=['qwen', 'funasr'],
        default='qwen',
        help='ASR 引擎选择（默认: qwen，支持 qwen/funasr）'
    )

    # ===== FunASR 相关参数 =====
    parser.add_argument(
        '--oss-region',
        default=None,
        help='OSS 区域（如 cn-hangzhou，优先级：命令行 > .env 文件）'
    )
    parser.add_argument(
        '--oss-bucket',
        default=None,
        help='OSS 桶名称（优先级：命令行 > .env 文件）'
    )
    parser.add_argument(
        '--oss-endpoint',
        default=None,
        help='OSS 端点（可选，如 oss-cn-hangzhou.aliyuncs.com，优先级：命令行 > .env 文件）'
    )
    parser.add_argument(
        '--keep-oss-file',
        action='store_true',
        help='转写完成后是否保留 OSS 文件（可选标志，默认删除）'
    )

    args = parser.parse_args()

    # 加载 .env 配置
    env_config = load_env_config()

    # 如果环境变量中没有凭证，则从 .env 配置中设置
    # 优先级：环境变量 > .env 文件
    if not os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID') and not os.getenv('OSS_ACCESS_KEY_ID'):
        # 尝试从 .env 读取的凭证设置为环境变量
        if 'access_key_id' in env_config:
            os.environ['OSS_ACCESS_KEY_ID'] = env_config['access_key_id']
        if 'access_key_secret' in env_config:
            os.environ['OSS_ACCESS_KEY_SECRET'] = env_config['access_key_secret']

    # 处理 DashScope API Key（从 .env 读取）
    if not os.getenv('DASHSCOPE_API_KEY') and 'dashscope_api_key' in env_config:
        os.environ['DASHSCOPE_API_KEY'] = env_config['dashscope_api_key']

    # 实现参数优先级：命令行参数 > .env 配置 > 默认值
    oss_region = args.oss_region or env_config.get('region') or None
    oss_bucket = args.oss_bucket or env_config.get('bucket') or None
    oss_endpoint = args.oss_endpoint or env_config.get('endpoint') or None

    # 验证 FunASR 模式的必需参数
    if args.asr_engine == "funasr":
        if not oss_region or not oss_bucket:
            # 记录哪些参数缺失及其来源
            missing = []
            if not oss_region:
                missing.append("OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)")
            if not oss_bucket:
                missing.append("OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)")

            print("❌ 错误：使用 FunASR 模式必须指定以下参数：")
            for item in missing:
                print(f"   - {item}")
            print("\n💡 解决方案：")
            print("   方案 1：创建或更新 .env 文件并添加配置")
            print("           OSS_REGION=cn-hangzhou")
            print("           OSS_BUCKET_NAME=your-bucket")
            print("   方案 2：使用命令行参数")
            print("           --oss-region cn-hangzhou --oss-bucket your-bucket")
            sys.exit(1)

        # 显示 OSS 配置来源
        print("✓ OSS 配置来源：")
        print(f"   Region: {oss_region} (来自 {'命令行' if args.oss_region else '.env 文件'})")
        print(f"   Bucket: {oss_bucket} (来自 {'命令行' if args.oss_bucket else '.env 文件'})")
        if oss_endpoint:
            print(f"   Endpoint: {oss_endpoint} (来自 {'命令行' if args.oss_endpoint else '.env 文件'})")

        # 验证 OSS 凭证（在工作流开始前）
        print("\n✓ 验证 OSS 凭证...")
        success, message = verify_oss_credentials(oss_region, oss_bucket, oss_endpoint)
        print(message)
        if not success:
            sys.exit(1)

    # 显示 DashScope API Key 配置来源
    dashscope_api_key = args.api_key or os.getenv('DASHSCOPE_API_KEY')
    if dashscope_api_key:
        print("\n✓ DashScope API Key 配置来源：")
        source = '命令行参数' if args.api_key else '.env 文件或环境变量'
        # 掩码显示 API Key（保护敏感信息）
        masked_key = dashscope_api_key[:5] + '...' + dashscope_api_key[-4:] if len(dashscope_api_key) > 9 else '***'
        print(f"   {masked_key} (来自 {source})")

    # 执行工作流
    run_workflow(
        audio_path=args.audio_path,
        qb_path=args.qb_path,
        output_path=args.output,
        api_key=args.api_key,
        asr_engine=args.asr_engine,
        oss_region=oss_region,
        oss_bucket=oss_bucket,
        oss_endpoint=oss_endpoint,
        keep_oss_file=args.keep_oss_file
    )


if __name__ == "__main__":
    main()
