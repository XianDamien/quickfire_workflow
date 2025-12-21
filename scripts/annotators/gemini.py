# -*- coding: utf-8 -*-
"""
scripts/annotators/gemini.py - Gemini Annotator 实现

从 Gemini_annotation.py 抽取的核心逻辑，提供模块化的 Gemini 标注能力。
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from google import genai
from google.genai import types

from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput

# 统一加载环境变量（如果 main.py 已加载则跳过）
from scripts.common.env import load_env
load_env()


class GeminiAnnotator(BaseAnnotator):
    """
    Gemini Annotator 实现

    支持的模型:
    - gemini-3-pro-preview
    - gemini-2.0-flash
    """

    def __init__(
        self,
        model: str = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        max_retries: int = 5,
        retry_delay: int = 5,
    ):
        """
        初始化 Gemini Annotator

        Args:
            model: 模型名称
            temperature: 温度参数
            max_output_tokens: 最大输出 tokens
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        from .config import (
            DEFAULT_ANNOTATOR,
            DEFAULT_MAX_OUTPUT_TOKENS,
            GEMINI3_MAX_OUTPUT_TOKENS,
        )

        # 使用配置的默认模型
        if model is None:
            model = DEFAULT_ANNOTATOR

        self.model = model
        self.name = model
        self.temperature = temperature
        if max_output_tokens is None:
            max_output_tokens = (
                GEMINI3_MAX_OUTPUT_TOKENS
                if model.startswith("gemini-3-")
                else DEFAULT_MAX_OUTPUT_TOKENS
            )
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 初始化 API 客户端
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 环境变量未设置")

        self.client = genai.Client(api_key=api_key)

    def _call_api(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        verbose: bool = False
    ) -> tuple:
        """
        调用 Gemini API

        Args:
            prompt: 用户提示词
            system_instruction: 系统指令
            verbose: 是否显示详细信息

        Returns:
            (API 响应文本, 响应时间毫秒)

        Raises:
            ValueError: API 调用失败
        """
        response = None
        response_time_ms = None

        for attempt in range(self.max_retries):
            try:
                if verbose:
                    print(f"📤 尝试 {attempt + 1}/{self.max_retries} - 发送提示词长度: {len(prompt)} 字符")

                    if attempt == 0:
                        print("\n" + "=" * 80)
                        print("🔍 SYSTEM PROMPT (完整内容):")
                        print("=" * 80)
                        print(system_instruction if system_instruction else "(无 system instruction)")
                        print("=" * 80)
                        print("\n" + "=" * 80)
                        print("🔍 USER PROMPT (完整内容):")
                        print("=" * 80)
                        print(prompt)
                        print("=" * 80 + "\n")
                else:
                    print(f"📤 尝试 {attempt + 1}/{self.max_retries}...")

                # 创建配置
                config_kwargs = {
                    "temperature": self.temperature,
                    "response_mime_type": "application/json",
                    "max_output_tokens": self.max_output_tokens,
                }

                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction

                # 记录 API 调用开始时间
                api_start_time = time.time()

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs)
                )

                # 计算响应时间
                api_end_time = time.time()
                response_time_ms = (api_end_time - api_start_time) * 1000

                if verbose:
                    print(f"📥 收到响应 (尝试 {attempt + 1}, 耗时 {response_time_ms:.0f}ms)")

                break

            except Exception as e:
                if verbose:
                    print(f"⚠️  尝试 {attempt + 1} 失败: {e}")
                if attempt < self.max_retries - 1:
                    if verbose:
                        print(f"   等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise e

        if not response:
            raise ValueError("无法获得 API 响应")

        # 处理响应
        return self._extract_response_text(response, verbose), response_time_ms

    def _extract_response_text(self, response: Any, verbose: bool = False) -> str:
        """从 API 响应中提取文本"""
        if not response.candidates or len(response.candidates) == 0:
            raise ValueError("API 没有返回候选结果")

        candidate = response.candidates[0]

        if verbose:
            print(f"🔍 finish_reason: {candidate.finish_reason}")

        # 检查完成原因
        if hasattr(candidate, "finish_reason") and candidate.finish_reason:
            reason_name = getattr(candidate.finish_reason, "name", None)

            if reason_name == "STOP":
                # 正常完成
                try:
                    if hasattr(response, "text") and response.text:
                        return response.text
                    elif candidate.content and candidate.content.parts:
                        return candidate.content.parts[0].text
                    else:
                        return "[]"
                except Exception:
                    return "[]"

            elif reason_name == "SAFETY":
                raise ValueError("内容被安全过滤器阻止")

            elif reason_name == "MAX_TOKENS":
                print(
                    "⚠️  响应被截断 - 达到最大 token 限制 "
                    f"(model={self.model}, max_output_tokens={self.max_output_tokens})"
                )
                if hasattr(response, "text") and response.text:
                    return response.text
                raise ValueError("响应被截断且无法获取部分内容")

            else:
                raise ValueError(f"API 返回异常状态: {candidate.finish_reason}")

        raise ValueError("无法确定 API 响应状态")

    def _build_prompt(
        self,
        input_data: AnnotatorInput
    ) -> tuple:
        """
        构建提示词

        Returns:
            (system_instruction, full_prompt, prompt_hash)
        """
        from scripts.common.archive import project_root
        from scripts.common.hash import text_hash

        # 加载 PromptLoader
        root = project_root()
        prompt_dir = root / "prompts" / "annotation"

        # 添加 prompts 目录到 path
        sys.path.insert(0, str(root / "prompts"))
        from prompt_loader import PromptLoader, PromptContextBuilder

        prompt_loader = PromptLoader(str(prompt_dir))

        # 构建上下文
        prompt_context = PromptContextBuilder.build(
            question_bank_json=input_data.question_bank_content,
            student_asr_text=input_data.asr_text or "",
            dataset_name=input_data.archive_batch,
            student_name=input_data.student_name,
            student_asr_with_timestamp=input_data.asr_with_timestamp,
            metadata=prompt_loader.metadata
        )

        # 获取提示词
        system_instruction = prompt_loader.system_instruction
        full_prompt = prompt_loader.render_user_prompt(prompt_context)

        # 计算 hash
        prompt_hash_value = text_hash(full_prompt, prefix=True)

        return system_instruction, full_prompt, prompt_hash_value, prompt_loader

    def annotate(self, input_data: AnnotatorInput) -> AnnotatorOutput:
        """
        执行标注

        Args:
            input_data: AnnotatorInput 对象

        Returns:
            AnnotatorOutput 对象
        """
        from scripts.common.archive import project_root, student_dir
        from scripts.common.runs import ensure_run_dir, write_run_manifest, new_run_id
        from scripts.contracts.cards import validate_cards, parse_api_response

        try:
            root = project_root()
            stu_dir = student_dir(input_data.archive_batch, input_data.student_name)

            # 确定 run_id 和 run_dir
            run_id = input_data.run_id or new_run_id()
            run_dir = ensure_run_dir(
                input_data.archive_batch,
                input_data.student_name,
                self.name,
                run_id
            )

            # 构建提示词
            system_instruction, full_prompt, prompt_hash, prompt_loader = self._build_prompt(input_data)

            # 调用 API
            raw_response, response_time_ms = self._call_api(
                full_prompt,
                system_instruction,
                verbose=input_data.verbose
            )

            # 解析响应
            parsed = parse_api_response(raw_response)
            if parsed.get("_parse_error"):
                raw_output_path = run_dir / "raw_api_output_parse_error.txt"
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write("=== Gemini API 原始输出 (JSON 解析失败) ===\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                    f.write(f"学生: {input_data.student_name}\n")
                    f.write(f"Model: {self.model}\n")
                    f.write(f"max_output_tokens: {self.max_output_tokens}\n")
                    f.write("=" * 80 + "\n")
                    f.write(raw_response)

                raise ValueError(
                    "LLM 输出不是有效 JSON（很可能是触发 MAX_TOKENS 导致被截断）。\n"
                    f"原始输出已保存到: {raw_output_path}"
                )
            annotations = parsed["annotations"]
            final_grade = parsed["final_grade_suggestion"]
            mistake_count = parsed["mistake_count"]

            # 校验 annotations
            is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)

            if not is_valid:
                # 保存原始输出便于排错
                raw_output_path = run_dir / "raw_api_output_debug.txt"
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(f"=== Gemini API 原始输出 (校验失败) ===\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                    f.write(f"学生: {input_data.student_name}\n")
                    f.write(f"无效项数: {len(invalid_items)}\n")
                    f.write(f"无效项:\n{json.dumps(invalid_items[:5], ensure_ascii=False, indent=2)}\n")
                    f.write("=" * 80 + "\n")
                    f.write(raw_response)

                raise ValueError(
                    f"cards 校验失败: {len(invalid_items)} 个无效项\n"
                    f"示例: {invalid_items[:3]}\n"
                    f"原始输出已保存到: {raw_output_path}"
                )

            # 校验评分
            if not final_grade or final_grade not in ["A", "B", "C"]:
                raise ValueError(f"无效的评分等级: {final_grade}")

            # 保存结果
            self._save_outputs(
                run_dir=run_dir,
                student_name=input_data.student_name,
                final_grade=final_grade,
                mistake_count=mistake_count,
                annotations=annotations,
                system_instruction=system_instruction,
                full_prompt=full_prompt,
                prompt_hash=prompt_hash,
                prompt_loader=prompt_loader,
                run_id=run_id,
                question_bank_filename=input_data.question_bank_path.name,
                response_time_ms=response_time_ms,
            )

            # 写入 manifest
            write_run_manifest(
                run_dir=run_dir,
                annotator_name=self.name,
                run_id=run_id,
                archive_batch=input_data.archive_batch,
                student_name=input_data.student_name,
                prompt_path=root / "prompts" / "annotation" / "user.md",
                prompt_hash=prompt_hash,
                model=self.model,
            )

            # 格式化响应时间
            if response_time_ms < 1000:
                time_str = f"{response_time_ms:.0f}ms"
            else:
                time_str = f"{response_time_ms / 1000:.2f}s"

            print(f"  ✓ {input_data.student_name}: 已保存到 runs/{self.name}/{run_id}/ (⏱ {time_str})")

            return AnnotatorOutput(
                success=True,
                student_name=input_data.student_name,
                final_grade=final_grade,
                mistake_count=mistake_count,
                annotations=annotations,
                run_id=run_id,
                run_dir=run_dir,
                model=self.model,
                prompt_hash=prompt_hash,
                response_time_ms=response_time_ms,
            )

        except Exception as e:
            return AnnotatorOutput(
                success=False,
                error=str(e),
                student_name=input_data.student_name,
                model=self.model,
            )

    def _save_outputs(
        self,
        run_dir: Path,
        student_name: str,
        final_grade: str,
        mistake_count: Dict[str, Any],
        annotations: list,
        system_instruction: str,
        full_prompt: str,
        prompt_hash: str,
        prompt_loader: Any,
        run_id: str,
        question_bank_filename: str,
        response_time_ms: float,
    ) -> None:
        """保存输出文件到 run_dir"""
        from scripts.common.runs import get_git_commit

        git_commit = get_git_commit(short=False)
        prompt_version = prompt_loader.metadata.get("prompt_version", "unknown")

        # 保存 4_llm_annotation.json (唯一标准输出)
        annotation_result = {
            "student_name": student_name,
            "final_grade_suggestion": final_grade,
            "mistake_count": mistake_count,
            "annotations": annotations,
            "_metadata": {
                "model": self.model,
                "response_time_ms": response_time_ms,
                "prompt_version": prompt_version,
                "run_id": run_id,
                "git_commit": git_commit,
                "timestamp": datetime.now().isoformat(),
            }
        }

        annotation_path = run_dir / "4_llm_annotation.json"
        with open(annotation_path, "w", encoding="utf-8") as f:
            json.dump(annotation_result, f, ensure_ascii=False, indent=2)

        # 保存 prompt_log.txt
        prompt_log_path = run_dir / "prompt_log.txt"
        with open(prompt_log_path, "w", encoding="utf-8") as f:
            f.write("=== 学生回答提取 - 完整提示词日志 ===\n\n")
            f.write(f"Prompt Version: {prompt_version}\n")
            f.write(f"生成时间: {datetime.now().isoformat()}\n")
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Git Commit: {git_commit}\n")
            f.write(f"Model: {self.model}\n")
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


# 便捷工厂函数
def create_gemini_annotator(model: str = "gemini-2.5-pro") -> GeminiAnnotator:
    """
    创建 Gemini Annotator 实例

    Args:
        model: 模型名称，支持:
            - gemini-2.5-pro (默认)
            - gemini-2.0-flash

    Returns:
        GeminiAnnotator 实例
    """
    return GeminiAnnotator(model=model)
