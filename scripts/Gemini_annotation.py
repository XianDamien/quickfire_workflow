#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生回答提取与评分系统（基于 Gemini LLM）

【输入来源】
1. Archive 批处理模式（推荐）：
   - 目录结构：archive/{class_code}_{date}/{student}/
   - 题库：archive/{class_code}_{date}/metadata.json -> question_bank_file
   - ASR 文本：{student}/2_qwen_asr.json
   - ASR 时间戳：{student}/3_asr_timestamp.json
   - 提示词：prompts/annotation/（system.md + user.md + metadata.json）

2. 旧模式（向后兼容）：
   - 题库：/questionbank/ 目录或学生目录下的 current_qb.json
   - ASR：2_qwen_asr.json

【输出】
- {student}/4_llm_annotation.json：评分结果（含时间戳）
- {student}/4_llm_prompt_log.txt：完整提示词日志
- archive/{class}_{date}/batch_annotation_report.json：班级级聚合报告

【命令行用法】
  # Archive 批处理模式（推荐）
  python3 Gemini_annotation.py --archive-batch Zoe41900_2025-09-08
  python3 Gemini_annotation.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # 旧模式（向后兼容）
  python3 Gemini_annotation.py --dataset Zoe51530-9.8
  python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar
  python3 Gemini_annotation.py --dataset Zoe51530-9.8 --workers 5
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
from dotenv import load_dotenv

# Add prompts directory to Python path for importing prompt_loader
sys.path.insert(0, str(Path(__file__).parent.parent / "prompts"))
from prompt_loader import PromptLoader, PromptContextBuilder

# 加载 .env 文件中的环境变量
load_dotenv()

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


def extract_timestamp_text_from_asr_json(asr_timestamp_path: str) -> str:
    """
    从 3_asr_timestamp.json 提取带时间戳的文本（严格模式）

    输入格式 (FunASR 输出):
    {
        "file_url": "...",
        "transcripts": [{
            "channel_id": 0,
            "transcript": "全文文本",
            "sentences": [
                {"begin_time": 1000, "end_time": 2000, "text": "文本片段"},
                ...
            ]
        }]
    }

    输出格式 (用于 Prompt):
    00:01 文本片段1
    00:02 文本片段2
    ...

    Args:
        asr_timestamp_path: 3_asr_timestamp.json 文件路径

    Returns:
        带时间戳的文本（MM:SS 格式）

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
        ValueError: 结构校验失败（缺少 transcripts/sentences 或字段类型错误）
    """
    # Phase 1: 严格失败 - 不再吞掉异常
    with open(asr_timestamp_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 结构校验
    transcripts = data.get('transcripts')
    if not transcripts or not isinstance(transcripts, list):
        raise ValueError(
            f"3_asr_timestamp.json 结构无效: 缺少 transcripts 数组\n"
            f"文件: {asr_timestamp_path}"
        )

    lines = []
    has_valid_sentences = False

    for transcript in transcripts:
        sentences = transcript.get('sentences')
        if not sentences or not isinstance(sentences, list):
            continue

        for sentence in sentences:
            # 校验必要字段存在且类型正确
            begin_time_ms = sentence.get('begin_time')
            end_time_ms = sentence.get('end_time')
            text = sentence.get('text')

            if begin_time_ms is None or end_time_ms is None or text is None:
                raise ValueError(
                    f"3_asr_timestamp.json 句子结构无效: 缺少 begin_time/end_time/text\n"
                    f"句子内容: {sentence}\n"
                    f"文件: {asr_timestamp_path}"
                )

            # 校验时间戳为整数（毫秒）
            if not isinstance(begin_time_ms, int) or not isinstance(end_time_ms, int):
                raise ValueError(
                    f"3_asr_timestamp.json 时间戳类型错误: begin_time/end_time 必须是 int(ms)\n"
                    f"实际值: begin_time={begin_time_ms} ({type(begin_time_ms).__name__}), "
                    f"end_time={end_time_ms} ({type(end_time_ms).__name__})\n"
                    f"文件: {asr_timestamp_path}"
                )

            text = text.strip()
            if text:
                has_valid_sentences = True
                # 将毫秒转换为 MM:SS 格式
                total_seconds = begin_time_ms // 1000
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                timestamp = f"{minutes:02d}:{seconds:02d}"
                lines.append(f"{timestamp} {text}")

    # 校验至少有一个有效句子
    if not has_valid_sentences:
        raise ValueError(
            f"3_asr_timestamp.json 内容为空: 没有有效的 sentences\n"
            f"文件: {asr_timestamp_path}"
        )

    return "\n".join(lines)


def call_gemini_api(prompt: str, system_instruction: str = None, verbose: bool = False) -> str:
    """调用 Gemini API"""
    max_retries = 5
    response = None

    for attempt in range(max_retries):
        try:
            if verbose:
                print(f"📤 尝试 {attempt + 1}/{max_retries} - 发送提示词长度: {len(prompt)} 字符")

                # 打印完整的 System Prompt
                if attempt == 0:
                    print("\n" + "="*80)
                    print("🔍 SYSTEM PROMPT (完整内容):")
                    print("="*80)
                    if system_instruction:
                        print(system_instruction)
                    else:
                        print("(无 system instruction)")
                    print("="*80)

                    # 打印完整的 User Prompt
                    print("\n" + "="*80)
                    print("🔍 USER PROMPT (完整内容):")
                    print("="*80)
                    print(prompt)
                    print("="*80 + "\n")
            else:
                print(f"📤 尝试 {attempt + 1}/{max_retries}...")

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
            if verbose:
                print(f"📥 收到响应 (尝试 {attempt + 1})")
                print(f"   候选结果数量: {len(response.candidates) if response.candidates else 0}")
            break

        except Exception as e:
            if verbose:
                print(f"⚠️  尝试 {attempt + 1} 失败: {e}")
            if attempt < max_retries - 1:
                if verbose:
                    print(f"   等待 5 秒后重试...")
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

        # 输出完整调试信息（仅当 verbose 时）
        if verbose:
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


def find_question_bank_from_student_dir(student_dir: Path) -> tuple:
    """
    从学生目录中查找题库文件

    搜索优先级:
    1. student_dir/current_qb.json (如果存在，表示已提取的题库)
    2. /questionbank 中匹配的题库 (基于任何可用的索引)

    Args:
        student_dir: 学生目录路径

    Returns:
        (question_bank_path, question_bank_filename) 元组
        如果未找到返回 (None, None)
    """
    # 首先检查学生目录中的 current_qb.json
    current_qb = student_dir / "current_qb.json"
    if current_qb.exists():
        return current_qb, current_qb.name

    # 从 /questionbank 搜索
    # 这里可以添加逻辑来从 questionbank 中选择匹配的题库
    # 基于数据集名称、学生特征或其他标识符
    project_root = Path(__file__).parent.parent
    questionbank_dir = project_root / "questionbank"

    if questionbank_dir.exists():
        # 优先查找模式: R3-14-D4*.json, R1-65*.json, R*.json
        for pattern in ["R3-14-D4*.json", "R1-65*.json", "R*.json"]:
            for file in questionbank_dir.glob(pattern):
                if file.is_file() and "vocabulary" not in file.name.lower():
                    return file, file.name

    return None, None


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


def process_student_annotations(dataset_name: str, student_name: str, verbose: bool = False) -> dict:
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

        # 从学生目录中查找题库文件 (不再使用 _shared_context)
        question_bank_path, question_bank_filename = find_question_bank_from_student_dir(student_dir)

        if not question_bank_path:
            return {
                "student_name": student_name,
                "status": "error",
                "error": "未找到题库文件 (current_qb.json 或 /questionbank 中的题库)"
            }

        asr_file = find_asr_file(student_dir)

        if not asr_file:
            return {
                "student_name": student_name,
                "status": "error",
                "error": "未找到 ASR 转写文件"
            }

        # 加载所有内容
        question_bank = load_file_content(str(question_bank_path))
        student_asr_text = extract_text_from_asr_json(str(asr_file))

        # 初始化提示词加载器
        script_dir = Path(__file__).parent
        prompt_dir = script_dir.parent / "prompts" / "annotation"

        try:
            prompt_loader = PromptLoader(str(prompt_dir))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load prompt templates: {e}")

        # 构建提示词上下文
        prompt_context = PromptContextBuilder.build(
            question_bank_json=question_bank,
            student_asr_text=student_asr_text,
            dataset_name=dataset_name,
            student_name=student_name,
            metadata=prompt_loader.metadata
        )

        # 获取系统指令和渲染用户提示词
        system_instruction = prompt_loader.system_instruction
        full_prompt = prompt_loader.render_user_prompt(prompt_context)

        # 调用 Gemini API
        result = call_gemini_api(full_prompt, system_instruction, verbose=verbose)

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

        # 获取当前 git commit hash
        git_commit = "unknown"
        try:
            import subprocess
            result_git = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result_git.returncode == 0:
                git_commit = result_git.stdout.strip()
        except Exception:
            pass  # 如果 git 命令失败，继续使用 "unknown"

        # 保存提示词日志
        prompt_log_path = student_dir / "4_llm_prompt_log.txt"
        prompt_version = prompt_loader.metadata.get("prompt_version", "unknown")
        try:
            with open(prompt_log_path, 'w', encoding='utf-8') as f:
                f.write("=== 学生回答提取 - 完整提示词日志 ===\n\n")
                f.write(f"Prompt Version: {prompt_version}\n")
                f.write(f"生成时间: {datetime.now().isoformat()}\n")
                f.write(f"Git Commit: {git_commit}\n")
                f.write(f"题库文件: {question_bank_filename}\n")
                f.write(f"System Instruction 长度: {len(system_instruction)} 字符\n")
                f.write(f"User Prompt 长度: {len(full_prompt)} 字符\n")
                f.write("=" * 80 + "\n\n")

                # 记录 Prompt 元数据
                f.write("=" * 80 + "\n")
                f.write("PROMPT METADATA (提示词元数据)\n")
                f.write("=" * 80 + "\n")
                f.write(json.dumps(prompt_loader.metadata, ensure_ascii=False, indent=2))
                f.write("\n\n")

                # 记录 System Instruction
                f.write("=" * 80 + "\n")
                f.write("SYSTEM INSTRUCTION (系统指令)\n")
                f.write("=" * 80 + "\n")
                f.write(system_instruction)
                f.write("\n\n")

                # 记录 User Prompt
                f.write("=" * 80 + "\n")
                f.write("USER PROMPT (用户提示词)\n")
                f.write("=" * 80 + "\n")
                f.write(full_prompt)
                f.write("\n")
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


# ===== Archive 批处理模式 =====

def generate_run_id() -> str:
    """
    生成唯一的 run_id，用于区分不同的处理批次

    格式: {timestamp}_{git_short}
    例如: 20251218_143022_a5cd771

    Returns:
        run_id 字符串
    """
    import subprocess
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        git_short = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        git_short = "nogit"
    return f"{timestamp}_{git_short}"


def load_archive_metadata(archive_batch: str) -> dict:
    """
    加载 archive/{class}_{date}/metadata.json

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）

    Returns:
        metadata 字典
    """
    project_root = Path(__file__).parent.parent
    metadata_path = project_root / "archive" / archive_batch / "metadata.json"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json 不存在: {metadata_path}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_archive_students(archive_batch: str) -> list:
    """
    发现 archive/{class}_{date}/ 下的所有学生目录

    Args:
        archive_batch: 分组名称

    Returns:
        学生名称列表
    """
    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive" / archive_batch

    if not archive_dir.exists():
        return []

    students = []
    for item in archive_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            students.append(item.name)

    return sorted(students)


def find_archive_vocabulary_file(archive_batch: str, metadata: dict) -> tuple:
    """
    根据 metadata 查找题库文件

    符合 dataset_conventions.md 规范的三级优先级：
    1. question_bank_path（新格式，指向 questionbank/）
    2. question_bank_file（旧格式）
    3. progress 字段在 questionbank/ 中查找

    Args:
        archive_batch: 分组名称
        metadata: metadata.json 内容

    Returns:
        (题库文件路径, 题库文件名) 元组
    """
    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive" / archive_batch

    # 优先级 1: question_bank_path（新格式，指向 questionbank/）
    qb_path_str = metadata.get("question_bank_path")
    if qb_path_str:
        qb_path = project_root / qb_path_str
        if qb_path.exists():
            return qb_path, qb_path.name

    # 优先级 2: question_bank_file（旧格式）
    qb_file = metadata.get("question_bank_file")
    if qb_file:
        qb_path = archive_dir / qb_file
        if qb_path.exists():
            return qb_path, qb_path.name

    # 优先级 3: progress 字段在 questionbank/ 中查找
    progress = metadata.get("progress")
    if progress:
        questionbank_dir = project_root / "questionbank"
        if questionbank_dir.exists():
            qb_path = questionbank_dir / f"{progress}.json"
            if qb_path.exists():
                return qb_path, qb_path.name

    # Fallback: 查找 _shared_context 目录中的题库（向后兼容）
    shared_context = archive_dir / "_shared_context"
    if shared_context.exists():
        for f in shared_context.glob("R*.json"):
            if f.is_file() and "vocabulary" not in f.name.lower():
                return f, f.name

    return None, None


def should_process_archive_student(student_dir: Path) -> bool:
    """
    检查学生是否应该被处理（是否已存在 4_llm_annotation.json）

    Args:
        student_dir: 学生目录路径

    Returns:
        True 如果应该处理，False 如果应该跳过
    """
    output_file = student_dir / "4_llm_annotation.json"
    return not output_file.exists()


def process_archive_student_annotation(
    archive_batch: str,
    student_name: str,
    question_bank_path: Path,
    question_bank_filename: str,
    run_id: str,
    verbose: bool = False
) -> dict:
    """
    处理单个 archive 学生的评分（支持时间戳）

    符合 dataset_conventions.md 规范：
    - 输出到 {student}/runs/{run_id}/4_llm_annotation.json
    - 生成 {student}/runs/{run_id}/run_metadata.json

    Args:
        archive_batch: 分组名称
        student_name: 学生名称
        question_bank_path: 题库文件路径
        question_bank_filename: 题库文件名
        run_id: 运行批次 ID
        verbose: 是否显示详细信息

    Returns:
        包含学生信息的字典
    """
    try:
        project_root = Path(__file__).parent.parent
        student_dir = project_root / "archive" / archive_batch / student_name

        # 检查 ASR 文件是否存在
        asr_file = student_dir / "2_qwen_asr.json"
        if not asr_file.exists():
            return {
                "student_name": student_name,
                "status": "error",
                "error": "未找到 ASR 转写文件 (2_qwen_asr.json)"
            }

        # 加载题库
        question_bank = load_file_content(str(question_bank_path))

        # 提取 ASR 文本
        student_asr_text = extract_text_from_asr_json(str(asr_file))

        # 提取时间戳文本（Phase 1: 严格必填）
        asr_timestamp_file = student_dir / "3_asr_timestamp.json"
        if not asr_timestamp_file.exists():
            raise FileNotFoundError(
                f"3_asr_timestamp.json 不存在: {asr_timestamp_file}\n"
                f"请先运行 funasr.py --archive-batch {archive_batch} --student {student_name}"
            )

        # 提取时间戳文本（会抛异常如果结构无效）
        student_asr_with_timestamp = extract_timestamp_text_from_asr_json(str(asr_timestamp_file))

        # 双重校验：确保提取的内容非空
        if not student_asr_with_timestamp or not student_asr_with_timestamp.strip():
            raise ValueError(
                f"3_asr_timestamp.json 解析后为空，说明 sentences 无有效内容\n"
                f"文件: {asr_timestamp_file}"
            )

        # 初始化提示词加载器
        script_dir = Path(__file__).parent
        prompt_dir = script_dir.parent / "prompts" / "annotation"

        try:
            prompt_loader = PromptLoader(str(prompt_dir))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load prompt templates: {e}")

        # 构建提示词上下文（包含时间戳）
        prompt_context = PromptContextBuilder.build(
            question_bank_json=question_bank,
            student_asr_text=student_asr_text,
            dataset_name=archive_batch,
            student_name=student_name,
            student_asr_with_timestamp=student_asr_with_timestamp,
            metadata=prompt_loader.metadata
        )

        # 获取系统指令和渲染用户提示词
        system_instruction = prompt_loader.system_instruction
        full_prompt = prompt_loader.render_user_prompt(prompt_context)

        # 调用 Gemini API
        result = call_gemini_api(full_prompt, system_instruction, verbose=verbose)

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
            annotations = api_result.get('annotations', [])
            final_grade = api_result.get('final_grade_suggestion', 'C')
            mistake_count = api_result.get('mistake_count', {})
        elif isinstance(api_result, list):
            annotations = api_result
            final_grade = 'C'
            mistake_count = {"errors": 0}
        else:
            annotations = []
            final_grade = 'C'
            mistake_count = {"errors": 0}

        # Phase 1: card_timestamp 校验 - 任何 null 或无效格式直接失败
        # 保存原始输出以便排错
        raw_output_for_debug = result

        def validate_card_timestamp(ts):
            """校验 card_timestamp 格式为 MM:SS"""
            if not ts or ts is None:
                return False
            if not isinstance(ts, str):
                return False
            # 匹配 MM:SS 格式（允许 M:SS 和 MM:SS）
            import re
            return bool(re.match(r'^\d{1,2}:\d{2}$', ts.strip()))

        invalid_timestamps = []
        for idx, annotation in enumerate(annotations):
            card_ts = annotation.get('card_timestamp')
            if not validate_card_timestamp(card_ts):
                invalid_timestamps.append({
                    'index': idx,
                    'card_index': annotation.get('card_index', 'N/A'),
                    'card_timestamp': card_ts
                })

        if invalid_timestamps:
            # 保存原始输出到 run 目录便于排错
            run_dir = student_dir / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            raw_output_path = run_dir / "raw_api_output_debug.txt"
            with open(raw_output_path, 'w', encoding='utf-8') as f:
                f.write(f"=== Gemini API 原始输出 (card_timestamp 校验失败) ===\n")
                f.write(f"时间: {datetime.now().isoformat()}\n")
                f.write(f"学生: {student_name}\n")
                f.write(f"无效时间戳数: {len(invalid_timestamps)}\n")
                f.write(f"无效项:\n{json.dumps(invalid_timestamps, ensure_ascii=False, indent=2)}\n")
                f.write("=" * 80 + "\n")
                f.write(raw_output_for_debug)

            raise ValueError(
                f"card_timestamp 校验失败: {len(invalid_timestamps)} 个 annotation 的时间戳无效或为 null\n"
                f"无效项: {invalid_timestamps[:3]}{'...' if len(invalid_timestamps) > 3 else ''}\n"
                f"原始输出已保存到: {raw_output_path}"
            )

        # 获取 git commit hash
        git_commit = "unknown"
        try:
            import subprocess
            result_git = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result_git.returncode == 0:
                git_commit = result_git.stdout.strip()
        except Exception:
            pass

        # 创建 runs/{run_id}/ 目录
        run_dir = student_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 计算 prompt hash
        import hashlib
        prompt_hash = hashlib.sha256(full_prompt.encode('utf-8')).hexdigest()[:16]

        # 保存提示词日志到 runs/{run_id}/
        prompt_log_path = run_dir / "4_llm_prompt_log.txt"
        prompt_version = prompt_loader.metadata.get("prompt_version", "unknown")
        try:
            with open(prompt_log_path, 'w', encoding='utf-8') as f:
                f.write("=== 学生回答提取 - 完整提示词日志 ===\n\n")
                f.write(f"Prompt Version: {prompt_version}\n")
                f.write(f"生成时间: {datetime.now().isoformat()}\n")
                f.write(f"Run ID: {run_id}\n")
                f.write(f"Git Commit: {git_commit}\n")
                f.write(f"题库文件: {question_bank_filename}\n")
                f.write(f"System Instruction 长度: {len(system_instruction)} 字符\n")
                f.write(f"User Prompt 长度: {len(full_prompt)} 字符\n")
                f.write(f"Prompt Hash: {prompt_hash}\n")
                f.write("=" * 80 + "\n\n")
                f.write("=" * 80 + "\n")
                f.write("PROMPT METADATA\n")
                f.write("=" * 80 + "\n")
                f.write(json.dumps(prompt_loader.metadata, ensure_ascii=False, indent=2))
                f.write("\n\n")
                f.write("=" * 80 + "\n")
                f.write("SYSTEM INSTRUCTION\n")
                f.write("=" * 80 + "\n")
                f.write(system_instruction)
                f.write("\n\n")
                f.write("=" * 80 + "\n")
                f.write("USER PROMPT\n")
                f.write("=" * 80 + "\n")
                f.write(full_prompt)
                f.write("\n")
        except Exception as e:
            print(f"⚠️  保存提示词日志失败: {e}")

        # 验证评分
        if not final_grade or final_grade not in ['A', 'B', 'C']:
            raise ValueError(f"Gemini 未返回有效的评分等级: {final_grade}")

        # 保存学生评分结果到 runs/{run_id}/
        student_result = {
            "student_name": student_name,
            "final_grade_suggestion": final_grade,
            "mistake_count": mistake_count,
            "annotations": annotations
        }

        annotation_file_path = run_dir / "4_llm_annotation.json"
        try:
            with open(annotation_file_path, 'w', encoding='utf-8') as f:
                json.dump(student_result, f, ensure_ascii=False, indent=2)
            print(f"  ✓ {student_name}: 已保存到 runs/{run_id}/4_llm_annotation.json")
        except Exception as e:
            print(f"⚠️  保存评分结果失败: {e}")

        # 保存 run_metadata.json
        run_metadata = {
            "run_id": run_id,
            "git_commit": git_commit,
            "model": "gemini-2.5-pro",
            "prompt_path": "prompts/annotation/user.md",
            "prompt_hash": f"sha256:{prompt_hash}",
            "created_at": datetime.now().isoformat()
        }
        run_metadata_path = run_dir / "run_metadata.json"
        try:
            with open(run_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(run_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存 run_metadata.json 失败: {e}")

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


def create_archive_batch_report(archive_batch: str, student_results: list, metadata: dict) -> dict:
    """
    创建 archive 批处理报告

    Args:
        archive_batch: 分组名称
        student_results: 学生结果列表
        metadata: metadata.json 内容

    Returns:
        批量报告字典
    """
    report = {
        "package_info": {
            "package_id": archive_batch,
            "class_label": metadata.get("class_code", ""),
            "date": metadata.get("date", ""),
            "progress": metadata.get("progress", ""),
            "type": "vocabulary",
            "processing_timestamp": datetime.now().isoformat() + "Z"
        },
        "student_reports": []
    }

    for result in student_results:
        if result.get("status") == "success":
            report["student_reports"].append({
                "student_name": result["student_name"],
                "final_grade_suggestion": result["final_grade_suggestion"],
                "mistake_count": result["mistake_count"],
                "annotations": result["annotations"]
            })
        else:
            report["student_reports"].append({
                "student_name": result["student_name"],
                "status": "error",
                "error": result.get("error", "Unknown error")
            })

    return report


def process_archive_batch(
    archive_batch: str,
    student_name: str = None,
    max_workers: int = 3,
    verbose: bool = False,
    force: bool = False
) -> tuple:
    """
    批量处理 archive/{class}_{date}/ 下的所有学生

    Args:
        archive_batch: 分组名称（如 Zoe41900_2025-09-08）
        student_name: 可选的单个学生名称
        max_workers: 并行线程数
        verbose: 是否显示详细信息
        force: 是否强制重新处理

    Returns:
        (成功数, 跳过/失败数)
    """
    project_root = Path(__file__).parent.parent
    archive_dir = project_root / "archive" / archive_batch

    if not archive_dir.exists():
        print(f"❌ Archive 目录不存在: {archive_dir}")
        return 0, 0

    print(f"\n{'='*60}")
    print(f"📁 Gemini Annotation Archive 批处理: {archive_batch}")
    print(f"{'='*60}")

    # 加载 metadata
    try:
        metadata = load_archive_metadata(archive_batch)
        print(f"   班级: {metadata.get('class_code', 'N/A')}")
        print(f"   日期: {metadata.get('date', 'N/A')}")
        print(f"   进度: {metadata.get('progress', 'N/A')}")
    except FileNotFoundError as e:
        print(f"⚠️  {e}")
        metadata = {}

    # 查找题库文件
    question_bank_path, question_bank_filename = find_archive_vocabulary_file(archive_batch, metadata)
    if not question_bank_path:
        print(f"❌ 未找到题库文件")
        return 0, 0

    print(f"   📚 题库: {question_bank_filename}")

    # 生成 run_id
    run_id = generate_run_id()
    print(f"   🆔 Run ID: {run_id}")

    # 获取学生列表
    if student_name:
        students = [student_name]
    else:
        students = find_archive_students(archive_batch)

    if not students:
        print("   ⊘ 未找到任何学生")
        return 0, 0

    # 过滤已处理的学生
    students_to_process = []
    skipped_students = []

    for student in students:
        student_dir = archive_dir / student
        if force or should_process_archive_student(student_dir):
            students_to_process.append(student)
        else:
            skipped_students.append(student)

    if skipped_students:
        if force:
            print(f"   ⚠️  强制重新处理 {len(skipped_students)} 个已处理的学生")
            students_to_process.extend(skipped_students)
        else:
            print(f"   ℹ️  跳过 {len(skipped_students)} 个已处理的学生（使用 --force 重新处理）")

    if not students_to_process:
        print("   ✓ 所有学生都已处理过")
        return 0, len(students)

    print(f"   👥 将处理 {len(students_to_process)} 个学生")

    # 并行处理
    student_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_student = {}
        for s_name in students_to_process:
            future = executor.submit(
                process_archive_student_annotation,
                archive_batch,
                s_name,
                question_bank_path,
                question_bank_filename,
                run_id,
                verbose
            )
            future_to_student[future] = s_name

        for future in as_completed(future_to_student):
            s_name = future_to_student[future]
            try:
                result = future.result()
                student_results.append(result)
                if result.get("status") != "success":
                    print(f"  ✗ {s_name}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"  ✗ {s_name}: 处理失败 - {str(e)}")
                student_results.append({
                    "student_name": s_name,
                    "status": "error",
                    "error": str(e)
                })

    # 创建批量报告
    batch_report = create_archive_batch_report(archive_batch, student_results, metadata)
    batch_report["run_id"] = run_id  # 添加 run_id 到报告中

    # 创建 reports/{run_id}/ 目录并保存批量报告
    reports_dir = archive_dir / "reports" / run_id
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_path = reports_dir / "batch_annotation_report.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch_report, f, ensure_ascii=False, indent=2)

    print(f"\n   📊 批量报告已保存到: reports/{run_id}/batch_annotation_report.json")

    # 统计
    success_count = sum(1 for r in student_results if r.get("status") == "success")
    error_count = len(student_results) - success_count

    print(f"\n{'='*60}")
    print(f"✅ 处理完成！成功: {success_count}, 失败: {error_count}")
    print(f"{'='*60}")

    return success_count, error_count


def process_all_students(max_workers: int = 3, verbose: bool = False, force: bool = False):
    """
    处理所有数据集中的所有学生

    Args:
        max_workers: 并行处理的最大线程数
        verbose: 是否显示详细信息
        force: 是否强制重新处理已处理过的学生
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

        process_dataset_with_parallel(dataset_name, max_workers, verbose=verbose, force=force)

    print(f"\n{'='*60}")
    print("✅ 所有数据集处理完成!")
    print(f"{'='*60}")


def process_dataset_with_parallel(dataset_name: str, max_workers: int = 3, verbose: bool = False, force: bool = False):
    """
    使用并行处理处理整个数据集

    Args:
        dataset_name: 数据集名称
        max_workers: 并行处理的最大线程数
        verbose: 是否显示详细信息
        force: 是否强制重新处理已处理过的学生
    """
    students = find_students_in_dataset(dataset_name)
    if not students:
        print("  ⊘ 未找到任何学生")
        return

    print(f"  📋 找到 {len(students)} 个学生")

    # 检查是否存在已处理过的学生
    project_root = Path(__file__).parent.parent
    already_processed = []
    students_to_process = []

    for student_name in students:
        student_dir = project_root / "archive" / dataset_name / student_name

        if should_process_student(student_dir):
            students_to_process.append(student_name)
        else:
            already_processed.append(student_name)

    # 处理已处理过的学生
    if already_processed:
        if force:
            print(f"  ⚠️  检测到 {len(already_processed)} 个已处理的学生，使用 --force 重新处理")
            students_to_process.extend(already_processed)
        else:
            print(f"  ℹ️  跳过 {len(already_processed)} 个已处理的学生（使用 --force 重新处理）")

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
            future = executor.submit(process_student_annotations, dataset_name, student_name, verbose=verbose)
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
        python3 Gemini_annotation.py --archive-batch Zoe41900_2025-09-08  # Archive 批处理模式
        python3 Gemini_annotation.py --dataset Zoe51530-9.8               # 旧模式
    """
    parser = argparse.ArgumentParser(
        description='Gemini 批量标注工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # Archive 批处理模式（推荐）
  python3 Gemini_annotation.py --archive-batch Zoe41900_2025-09-08
  python3 Gemini_annotation.py --archive-batch Zoe41900_2025-09-08 --student Oscar

  # 旧模式（向后兼容）
  python3 Gemini_annotation.py --dataset Zoe51530-9.8
  python3 Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar
        """
    )

    # Archive 批处理模式参数
    parser.add_argument(
        '--archive-batch',
        type=str,
        help='Archive 批处理模式 (例如: Zoe41900_2025-09-08)'
    )

    # 旧模式参数（向后兼容）
    parser.add_argument(
        '--dataset',
        type=str,
        help='数据集名称 (例如: Zoe51530-9.8)。格式: CourseName-Date'
    )

    parser.add_argument(
        '--student',
        type=str,
        help='学生名称 (例如: Oscar)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='并行处理的最大线程数 (默认: 3)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细的调试信息'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新处理所有学生，即使已处理过'
    )

    args = parser.parse_args()

    # 验证参数依赖关系
    if args.student and not args.dataset and not args.archive_batch:
        parser.error("错误: --student 需要指定 --dataset 或 --archive-batch")

    # 检查 Gemini API 密钥
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ 错误: 请设置 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    # 根据参数执行相应的处理
    try:
        # Archive 批处理模式（推荐）
        if args.archive_batch:
            success, fail = process_archive_batch(
                args.archive_batch,
                student_name=args.student,
                max_workers=args.workers,
                verbose=args.verbose,
                force=args.force
            )
            sys.exit(0 if (success > 0 or fail > 0) else 1)

        # 旧模式：单个学生
        if args.student and args.dataset:
            print(f"🎯 处理单个学生: {args.dataset}/{args.student}")
            print("=" * 50)

            result = process_student_annotations(args.dataset, args.student, verbose=args.verbose)

            if result.get("status") == "success":
                print(f"\n✅ {args.student} 处理成功!")
                print(f"   最终等级: {result['final_grade_suggestion']}")
            else:
                print(f"\n❌ {args.student} 处理失败: {result.get('error', 'Unknown error')}")
                sys.exit(1)

        elif args.dataset:
            # 旧模式：整个数据集
            process_dataset_with_parallel(args.dataset, args.workers, verbose=args.verbose, force=args.force)
        else:
            # 旧模式：所有数据集
            process_all_students(args.workers, verbose=args.verbose, force=args.force)

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()