#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生回答提取脚本
使用 Gemini LLM 根据提示词模板提取学生回答内容

支持命令行批量处理功能：
  python3 Gemini_annotation.py                                    # 处理所有数据集
  python3 Gemini_annotation.py --dataset Zoe51530-9.8            # 处理指定数据集
  python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar  # 处理单个学生
"""

import json
import os
import sys
import argparse
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from google import genai
from google.genai import types

def load_env_variables():
    """从 .env 文件加载环境变量"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 加载 .env 文件中的环境变量
load_env_variables()

# 配置 Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 错误: 请设置 GEMINI_API_KEY 环境变量")
    sys.exit(1)

# 创建 Gemini 客户端
client = genai.Client(api_key=GEMINI_API_KEY)


def load_file_content(file_path: str) -> str:
    """加载文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: 读取文件 {file_path} 时出错: {e}")
        sys.exit(1)


def load_prompt_template(template_path: str) -> str:
    """加载提示词模板"""
    template_content = load_file_content(template_path)

    # 移除 markdown 标记
    if "```text" in template_content:
        template_content = template_content.replace("```text", "").replace("```", "")

    return template_content.strip()


def build_full_prompt(template: str, question_bank: str, teacher_transcript: str, student_asr: str) -> str:
    """构建完整的提示词"""
    # 提取模板中的占位符
    template = template.replace("{{在此处粘贴题库 JSON}}", question_bank)
    template = template.replace("{{在此处粘贴老师音频转录文本}}", teacher_transcript)
    template = template.replace("{{在此处粘贴学生音频转录文本}}", student_asr)

    return template


def extract_text_from_asr_json(asr_json_path: str) -> str:
    """从 ASR JSON 文件中提取文本内容"""
    try:
        with open(asr_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 提取 text 内容
        text_content = data.get('output', {}).get('choices', [{}])[0].get('message', {}).get('content', [{}])[0].get('text', '')

        if not text_content:
            print(f"⚠️  警告: 在 {asr_json_path} 中未找到 text 内容")
            return ""

        return text_content

    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON 格式错误 - {e}")
        sys.exit(1)
    except (KeyError, IndexError, TypeError) as e:
        print(f"❌ 错误: 无法解析 ASR 文件结构 - {e}")
        sys.exit(1)


def call_gemini_api(prompt: str, system_instruction: str = None) -> str:
    """调用 Gemini API"""
    max_retries = 5
    response = None

    for attempt in range(max_retries):
        try:
            print(f"📤 尝试 {attempt + 1}/{max_retries} - 发送提示词长度: {len(prompt)} 字符")
            if attempt == 0:
                print(f"📤 提示词预览: {prompt[:200]}...")

            # 创建配置对象
            config_kwargs = {
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "max_output_tokens": 16384,  # 增加到 16384 tokens
            }

            # 如果有系统指令，添加到配置中
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs)
            )

            # 成功收到响应
            print(f"📥 收到响应 (尝试 {attempt + 1})")
            print(f"   候选结果数量: {len(response.candidates) if response.candidates else 0}")
            break

        except Exception as e:
            print(f"⚠️  尝试 {attempt + 1} 失败: {e}")
            if attempt < max_retries - 1:
                print(f"   等待 5 秒后重试...")
                import time
                time.sleep(5)
                continue
            else:
                print(f"❌ 所有尝试都失败了")
                raise e

    if not response:
        raise ValueError("无法获得 API 响应")

    # 检查响应状态
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]

        # 输出完整调试信息
        print(f"🔍 完整调试信息:")
        print(f"   finish_reason: {candidate.finish_reason}")
        if hasattr(candidate, 'finish_reason'):
            print(f"   finish_reason (enum): {candidate.finish_reason}")
            if hasattr(candidate.finish_reason, 'name'):
                print(f"   finish_reason.name: {candidate.finish_reason.name}")
            if hasattr(candidate.finish_reason, 'value'):
                print(f"   finish_reason.value: {candidate.finish_reason.value}")

        # 检查安全评级
        if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
            print(f"   安全评级详情:")
            for rating in candidate.safety_ratings:
                print(f"     - {rating.category}: {rating.probability} (blocked: {getattr(rating, 'blocked', 'N/A')})")

        # 检查内容
        print(f"   候选内容: {candidate.content}")
        print(f"   响应文本属性: {hasattr(response, 'text')}")
        if hasattr(response, 'text'):
            print(f"   response.text: {repr(response.text)}")

        # 处理不同的完成原因
        if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
            if hasattr(candidate.finish_reason, 'name') and candidate.finish_reason.name == 'STOP':
                # 正常完成 - 尝试提取文本
                try:
                    if hasattr(response, 'text') and response.text:
                        return response.text
                    elif candidate.content and candidate.content.parts:
                        return candidate.content.parts[0].text
                    else:
                        print("⚠️  警告: 响应为空")
                        return "[]"
                except Exception as text_error:
                    print(f"⚠️  文本提取失败: {text_error}")
                    return "[]"

            elif hasattr(candidate.finish_reason, 'name') and candidate.finish_reason.name == 'SAFETY':
                print("❌ 内容被安全过滤器阻止")
                print("💡 排查建议:")
                print("   1. 检查提示词是否包含敏感词汇")
                print("   2. 尝试缩短提示词长度")
                print("   3. 移除 response_mime_type='application/json' 限制")
                print("   4. 检查学生转录文本中的敏感内容")
                raise ValueError("内容被安全过滤器阻止，需要修改提示词内容")

            else:
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason.name == 'MAX_TOKENS':
                    print("⚠️  响应被截断 - 达到最大 token 限制")
                    print("💡 尝试获取部分响应...")
                    # 尝试获取部分响应
                    if hasattr(response, 'text') and response.text:
                        print(f"   获得部分响应: {len(response.text)} 字符")
                        return response.text
                    else:
                        print("   无法获取部分响应")
                        # 尝试不使用 JSON 格式限制
                        return handle_max_tokens_error(prompt)
                else:
                    print(f"⚠️  其他完成原因: {candidate.finish_reason}")
                    raise ValueError(f"API 返回异常状态: {candidate.finish_reason}")
        else:
            print("⚠️  无法确定完成状态")
            raise ValueError("无法确定 API 响应状态")
    else:
        print("⚠️  没有生成候选结果")
        raise ValueError("API 没有返回候选结果")


def handle_max_tokens_error(prompt: str, system_instruction: str = None) -> str:
    """处理 MAX_TOKENS 错误，尝试使用不同的配置重试"""
    print("\n🔄 尝试使用更高 token 限制...")

    try:
        # 移除 JSON 格式限制，增加 token 限制
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt + "\n\n请确保输出完整的 JSON 格式，不要截断。",
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192 * 2,  # 增加到 16384 tokens
            )
        )

        if response.candidates and response.candidates[0]:
            if hasattr(response, 'text') and response.text:
                print(f"✅ 成功获得完整响应: {len(response.text)} 字符")
                return response.text
            else:
                print("⚠️  响应仍为空")
                return create_simple_response(prompt)
        else:
            return create_simple_response(prompt)

    except Exception as e:
        print(f"⚠️  重试失败: {e}")
        return create_simple_response(prompt)


def create_simple_response(prompt: str) -> str:
    """创建简单的基础响应"""
    print("🔄 生成基础响应...")

    try:
        # 从提示词中提取题库信息
        import re
        question_bank_match = re.search(r'题库.*?```json\s*(.*?)\s*```', prompt, re.DOTALL)
        if question_bank_match:
            question_bank_json = question_bank_match.group(1)
            question_bank = json.loads(question_bank_json)

            # 创建基础响应
            response = []
            for i, item in enumerate(question_bank, 1):
                response.append({
                    "card_index": i,
                    "问题": item.get("问题", ""),
                    "学生回答": "未作答",
                    "答案": item.get("答案", "")
                })

            print("✅ 生成了基础响应")
            return json.dumps(response, ensure_ascii=False, indent=2)

        return "[]"

    except Exception as e:
        print(f"❌ 生成基础响应失败: {e}")
        return "[]"


def create_fallback_response(prompt: str) -> str:
    """创建备用响应"""
    print("🔄 使用本地解析方法...")

    try:
        # 尝试从提示词中提取题库信息并生成基础响应
        import re

        # 从提示词中提取题库
        question_bank_match = re.search(r'题库.*?```json\s*(.*?)\s*```', prompt, re.DOTALL)
        if question_bank_match:
            question_bank_json = question_bank_match.group(1)
            question_bank = json.loads(question_bank_json)

            # 创建基础响应结构
            response = []
            for i, item in enumerate(question_bank, 1):
                response.append({
                    "card_index": i,
                    "问题": item.get("问题", ""),
                    "学生回答": "未作答",  # 默认标记为未作答
                    "答案": item.get("答案", "")
                })

            print("✅ 生成了备用响应（所有问题标记为未作答）")
            return json.dumps(response, ensure_ascii=False, indent=2)

        return "[]"

    except Exception as fallback_error:
        print(f"❌ 备用方法也失败: {fallback_error}")
        return "[]"


def save_result(result: str, output_path: str):
    """保存结果到文件"""
    try:
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"✅ 结果已保存到: {output_path}")

    except Exception as e:
        print(f"❌ 错误: 保存文件时出错 - {e}")
        sys.exit(1)


# ===== 数据集和学生发现辅助函数 =====

def parse_dataset_name(dataset_name: str):
    """
    解析数据集名称为课程代码和日期

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)

    Returns:
        (course_code, date) 元组
    """
    parts = dataset_name.rsplit('-', 1)
    if len(parts) != 2:
        raise ValueError(f"无效的数据集名称格式: {dataset_name}")

    course_code, date = parts
    return course_code, date


def find_datasets():
    """
    发现 archive 目录下的所有数据集

    Returns:
        数据集名称列表 (例如: ["Zoe51530-9.8", "Zoe41900-9.8", ...])
    """
    project_root = Path(__file__).parent.parent
    archive_path = project_root / "archive"

    if not archive_path.exists():
        return []

    datasets = []
    for item in archive_path.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            datasets.append(item.name)

    return sorted(datasets)


def find_students_in_dataset(dataset_name: str):
    """
    发现指定数据集中的所有学生

    Args:
        dataset_name: 数据集名称 (例如: Zoe51530-9.8)

    Returns:
        学生名称列表
    """
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "archive" / dataset_name

    if not dataset_path.exists():
        return []

    students = []
    for student_dir in dataset_path.iterdir():
        if student_dir.is_dir() and not student_dir.name.startswith('_'):
            students.append(student_dir.name)

    return sorted(students)


def extract_progress_info(question_bank_path: str) -> str:
    """
    从题库文件名中提取进度信息

    例如: "R3-14-D4.json" -> "R3-14"

    Args:
        question_bank_path: 题库文件路径

    Returns:
        进度信息字符串
    """
    filename = Path(question_bank_path).name
    # 匹配类似 R3-14-D4.json 的模式
    match = re.match(r'([A-Z]\d+-\d+)', filename)
    if match:
        return match.group(1)

    # 如果没有匹配，尝试其他模式
    match = re.match(r'([A-Za-z]\d+-\d+)', filename)
    if match:
        return match.group(1)

    # 默认返回空字符串
    return ""


def find_asr_file(student_dir: Path) -> Path:
    """
    查找学生目录中的 ASR 结果文件

    Args:
        student_dir: 学生目录路径

    Returns:
        ASR 文件路径
    """
    # 优先查找 2_qwen_asr.json
    asr_file = student_dir / "2_qwen_asr.json"
    if asr_file.exists():
        return asr_file

    # 查找其他可能的 ASR 文件
    for pattern in ["*_asr.json", "*_transcript.json"]:
        for file in student_dir.glob(pattern):
            if file.is_file():
                return file

    # 如果没找到，返回 None
    return None


def should_process_student(student_dir: Path) -> bool:
    """
    检查学生是否已被处理过

    Args:
        student_dir: 学生目录路径

    Returns:
        False 如果已处理过 (存在 4_llm_annotation.json)
        True 如果未处理过
    """
    output_file = student_dir / "4_llm_annotation.json"
    return not output_file.exists()


def process_student_annotations(dataset_name: str, student_name: str) -> dict:
    """
    处理单个学生的回答提取

    Args:
        dataset_name: 数据集名称
        student_name: 学生名称

    Returns:
        包含学生信息的字典
    """
    try:
        # 构建路径
        project_root = Path(__file__).parent.parent
        dataset_path = project_root / "archive" / dataset_name
        student_dir = dataset_path / student_name

        # 查找必要文件
        shared_context = dataset_path / "_shared_context"
        # 提示词模板相对于脚本位置
        script_dir = Path(__file__).parent
        prompt_template_path = script_dir.parent / "prompts" / "annotation.txt"

        # 显式查找题库文件（支持 R3-14-D4*.json 和 R1-65*.json 等模式）
        question_bank_path = None

        # 优先查找 R3-14-D4 和 R1-65 等常见题库模式
        for pattern in ["R3-14-D4*.json", "R1-65*.json", "R*.json"]:
            for file in shared_context.glob(pattern):
                if file.is_file() and "vocabulary" not in file.name.lower():
                    question_bank_path = file
                    break
            if question_bank_path:
                break

        if not question_bank_path:
            return {
                "student_name": student_name,
                "status": "error",
                "error": "未找到题库文件 (R*.json，不包括 vocabulary)"
            }

        # 查找对应的转录文件（可选）
        teacher_transcript_path = None
        possible_names = [
            f"{question_bank_path.stem}_transcription.txt",
            f"{question_bank_path.stem}_merged_transcription.txt",
            "R3-14-D4_transcription.txt"
        ]
        for name in possible_names:
            path = shared_context / name
            if path.exists():
                teacher_transcript_path = path
                break

        asr_file = find_asr_file(student_dir)

        if not asr_file:
            return {
                "student_name": student_name,
                "status": "error",
                "error": "未找到 ASR 转写文件"
            }

        # 加载所有内容
        prompt_template = load_prompt_template(prompt_template_path)

        if teacher_transcript_path:
            teacher_transcript = load_file_content(str(teacher_transcript_path))
        else:
            teacher_transcript = ""  # 无转录文件时使用空字符串

        question_bank = load_file_content(str(question_bank_path))
        student_asr_text = extract_text_from_asr_json(str(asr_file))

        # 构建系统指令
        system_instruction = """# 角色
你是一个精通数据处理和文本分析的 AI 助手。

# 背景信息
1. "老师音频转录文本"是一个模板，遵循【问题】-【停顿】-【答案】的固定模式。
2. "学生音频转录文本"是实际发生的录音。学生在听老师念出【问题】后，会在【停顿】期间尝试自己回答。之后，老师会念出【答案】。
3. 因此，在"学生音频转录文本"中，出现在某个【问题】和对应的【答案】之间的文本，就是学生的回答。
最后的评分逻辑按照检测出的errors错误来评级：
**A级:** 0 个 `NO_ANSWER` / 'MEANING_ERROR'
**B级:** 1-2 个 `NO_ANSWER`/'MEANING_ERROR'
**C级:** 3个及以上 `NO_ANSWER`/'MEANING_ERROR'
# 注意事项
1. 有的时候问题可能因为学生漏录，不会出现，只要检测到重复两次的答案即可进行定位，当出现两次答案时，前一个答案为学生回答'detected_answer'，后一个答案为教师公布的答案'expected_answer'。
2. 如果错误超过5个，请花更长时间进行复核：是否是定位学生回答的范围错误？两次重复的答案是否取的是前一次的答案作为学生回答？
"""

        # 如果没有转录文件，使用空字符串
        if not teacher_transcript_path:
            teacher_transcript = ""

        # 构建完整提示词
        full_prompt = build_full_prompt(
            prompt_template,
            question_bank,
            teacher_transcript,
            student_asr_text
        )

        # 调用 Gemini API
        result = call_gemini_api(full_prompt, system_instruction)

        # 清理结果
        result = result.strip()
        if "```json" in result:
            result = result.replace("```json", "").replace("```", "").strip()

        # 解析结果
        try:
            api_result = json.loads(result)
        except json.JSONDecodeError:
            api_result = {"annotations": []}

        # 处理不同的响应格式
        if isinstance(api_result, dict):
            # 新格式：包含 annotations 列表
            annotations = api_result.get('annotations', [])
            final_grade = api_result.get('final_grade_suggestion', 'C')
            mistake_count = api_result.get('mistake_count', {})
        elif isinstance(api_result, list):
            # 旧格式：直接是列表
            annotations = api_result
            final_grade = 'C'  # 默认值
            mistake_count = {"errors": 0}
        else:
            annotations = []
            final_grade = 'C'
            mistake_count = {"errors": 0}

        # 保存提示词日志
        prompt_log_path = student_dir / "4_llm_prompt_log.txt"
        try:
            with open(prompt_log_path, 'w', encoding='utf-8') as f:
                f.write("=== 学生回答提取 - 完整提示词 ===\n\n")
                f.write(f"生成时间: {datetime.now().isoformat()}\n")
                f.write(f"提示词长度: {len(full_prompt)} 字符\n")
                f.write("=" * 50 + "\n\n")
                f.write(full_prompt)
        except Exception as e:
            print(f"⚠️  保存提示词失败: {e}")

        # 直接返回 Gemini 的评分结果，不进行任何代码层面的计算
        # 评分逻辑完全由大模型负责
        if not final_grade or final_grade not in ['A', 'B', 'C']:
            raise ValueError(f"Gemini 未返回有效的评分等级: {final_grade}")

        # 保存学生的注释结果到 4_llm_annotation.json
        student_result = {
            "student_name": student_name,
            "final_grade_suggestion": final_grade,
            "mistake_count": mistake_count,
            "annotations": annotations
        }

        annotation_file_path = student_dir / "4_llm_annotation.json"
        try:
            with open(annotation_file_path, 'w', encoding='utf-8') as f:
                json.dump(student_result, f, ensure_ascii=False, indent=2)
            print(f"✓ 已保存到: {annotation_file_path}")
        except Exception as e:
            print(f"⚠️  保存注释结果失败: {e}")

        return {
            "student_name": student_name,
            "status": "success",
            "final_grade_suggestion": final_grade,
            "mistake_count": mistake_count,
            "annotations": annotations
        }

    except Exception as e:
        return {
            "student_name": student_name,
            "status": "error",
            "error": str(e)
        }


def create_batch_report(dataset_name: str, student_results: list) -> dict:
    """
    创建批量处理报告

    Args:
        dataset_name: 数据集名称
        student_results: 学生结果列表

    Returns:
        包含所有学生信息的报告字典
    """
    # 解析数据集信息
    course_code, date = parse_dataset_name(dataset_name)

    # 提取进度信息
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "archive" / dataset_name
    shared_context = dataset_path / "_shared_context"

    progress = ""
    for file in shared_context.glob("*.json"):
        if "vocabulary" not in file.name.lower():
            progress = extract_progress_info(str(file))
            break

    # 创建报告
    report = {
        "package_info": {
            "package_id": dataset_name,
            "class_label": course_code,
            "date": date,
            "progress": progress,
            "type": "vocabulary",
            "processing_timestamp": datetime.now().isoformat() + "Z"
        },
        "student_reports": []
    }

    # 添加学生报告
    for result in student_results:
        if result.get("status") == "success":
            report["student_reports"].append({
                "student_name": result["student_name"],
                "final_grade_suggestion": result["final_grade_suggestion"],
                "mistake_count": result["mistake_count"],
                "annotations": result["annotations"]
            })
        else:
            # 添加错误报告
            report["student_reports"].append({
                "student_name": result["student_name"],
                "status": "error",
                "error": result.get("error", "Unknown error")
            })

    return report


def process_all_students(max_workers: int = 3):
    """
    处理所有数据集中的所有学生

    Args:
        max_workers: 并行处理的最大线程数
    """
    print("🚀 开始批量处理所有学生回答...")
    print("=" * 60)

    datasets = find_datasets()
    if not datasets:
        print("❌ 未找到任何数据集")
        return

    for dataset_name in datasets:
        print(f"\n{'='*60}")
        print(f"处理数据集: {dataset_name}")
        print(f"{'='*60}")

        process_dataset_with_parallel(dataset_name, max_workers)

    print(f"\n{'='*60}")
    print("✅ 所有数据集处理完成!")
    print(f"{'='*60}")


def process_dataset_with_parallel(dataset_name: str, max_workers: int = 3):
    """
    使用并行处理处理整个数据集

    Args:
        dataset_name: 数据集名称
        max_workers: 并行处理的最大线程数
    """
    students = find_students_in_dataset(dataset_name)
    if not students:
        print("  ⊘ 未找到任何学生")
        return

    print(f"  📋 找到 {len(students)} 个学生")

    # 检查是否存在已处理过的学生（重复处理检查）
    project_root = Path(__file__).parent.parent
    already_processed = []
    students_to_process = []

    for student_name in students:
        student_dir = project_root / "archive" / dataset_name / student_name

        if should_process_student(student_dir):
            students_to_process.append(student_name)
        else:
            already_processed.append(student_name)

    # 如果存在已处理过的学生，报错并停止
    if already_processed:
        error_msg = f"""
❌ 错误: 检测到已处理过的学生，无法继续处理！

已处理过的学生 ({len(already_processed)}):
  {', '.join(already_processed)}

原因: 检测到这些学生已存在 4_llm_annotation.json 文件

解决方案:
  1. 如果要重新处理整个班级，请删除所有学生的 4_llm_annotation.json:
     rm archive/{dataset_name}/*/4_llm_annotation.json

  2. 如果要继续处理其他班级，请使用:
     python3 scripts/Gemini_annotation.py --dataset <其他班级名>

⚠️  为了数据一致性，不允许部分重新处理！
        """.strip()
        print(error_msg)
        sys.exit(1)

    if not students_to_process:
        print("  ✓ 所有学生都已处理过")
        return

    print(f"  🔄 将处理 {len(students_to_process)} 个学生（并行）")

    # 并行处理
    student_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_student = {}
        for student_name in students_to_process:
            future = executor.submit(process_student_annotations, dataset_name, student_name)
            future_to_student[future] = student_name

        # 收集结果
        for future in as_completed(future_to_student):
            student_name = future_to_student[future]
            try:
                result = future.result()
                student_results.append(result)

                if result.get("status") == "success":
                    print(f"  ✓ {student_name}: 处理成功")
                else:
                    print(f"  ✗ {student_name}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"  ✗ {student_name}: 处理失败 - {str(e)}")
                student_results.append({
                    "student_name": student_name,
                    "status": "error",
                    "error": str(e)
                })

    # 创建批量报告
    batch_report = create_batch_report(dataset_name, student_results)

    # 保存批量报告
    project_root = Path(__file__).parent.parent
    output_path = project_root / "archive" / dataset_name / "batch_annotation_report.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch_report, f, ensure_ascii=False, indent=2)

    print(f"\n  📊 批量报告已保存到: {output_path}")

    # 统计
    success_count = sum(1 for r in student_results if r.get("status") == "success")
    error_count = len(student_results) - success_count

    print(f"  📈 处理统计: 成功 {success_count}, 失败 {error_count}")


def main():
    """
    主入口点 - 支持 CLI 参数的批量处理

    用法:
        python3 Gemini_annotation.py                                    # 处理所有数据集
        python3 Gemini_annotation.py --dataset Zoe51530-9.8            # 处理指定数据集
        python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar  # 处理单个学生
    """
    parser = argparse.ArgumentParser(
        description='Gemini 批量标注工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理所有数据集和学生
  python3 Gemini_annotation.py

  # 处理指定数据集中的所有学生
  python3 Gemini_annotation.py --dataset Zoe51530-9.8

  # 处理指定学生
  python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar

  # 显示帮助
  python3 Gemini_annotation.py --help
        """
    )

    parser.add_argument(
        '--dataset',
        type=str,
        help='数据集名称 (例如: Zoe51530-9.8)。格式: CourseName-Date'
    )

    parser.add_argument(
        '--student',
        type=str,
        help='学生名称 (例如: Oscar)。需要指定 --dataset'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='并行处理的最大线程数 (默认: 3)'
    )

    args = parser.parse_args()

    # 验证参数依赖关系
    if args.student and not args.dataset:
        parser.error("错误: --student 需要指定 --dataset")

    # 检查 Gemini API 密钥
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ 错误: 请设置 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    # 根据参数执行相应的处理
    try:
        if args.student:
            # 处理单个学生
            print(f"🎯 处理单个学生: {args.dataset}/{args.student}")
            print("=" * 50)

            result = process_student_annotations(args.dataset, args.student)

            if result.get("status") == "success":
                print(f"\n✅ {args.student} 处理成功!")
                print(f"   最终等级: {result['final_grade_suggestion']}")
            else:
                print(f"\n❌ {args.student} 处理失败: {result.get('error', 'Unknown error')}")
                sys.exit(1)

        elif args.dataset:
            # 处理整个数据集
            process_dataset_with_parallel(args.dataset, args.workers)
        else:
            # 处理所有数据集（后向兼容）
            process_all_students(args.workers)

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()