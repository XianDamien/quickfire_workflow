# -*- coding: utf-8 -*-
"""
scripts/annotators/qwen.py - Qwen Annotator 实现

使用阿里云通义千问系列模型进行学生作业评分。
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

import dashscope

from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput

# 统一加载环境变量
from scripts.common.env import load_env
load_env()


class QwenAnnotator(BaseAnnotator):
    """
    Qwen Annotator 实现

    支持的模型:
    - qwen-max
    - qwen-max-latest
    - qwen3-max
    """

    def __init__(
        self,
        model: str = "qwen-max",
        temperature: float = 0.2,
        max_output_tokens: int = None,
        max_retries: int = None,
        retry_delay: int = None,
    ):
        """
        初始化 Qwen Annotator

        Args:
            model: 模型名称
            temperature: 温度参数
            max_output_tokens: 最大输出 tokens（如果为 None，自动从配置获取）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        from .config import (
            get_max_output_tokens,
            clamp_max_output_tokens,
            DEFAULT_MAX_RETRIES,
            DEFAULT_RETRY_DELAY,
        )

        self.model = model
        self.name = model
        self.temperature = temperature

        # 使用配置的模型上限
        if max_output_tokens is None:
            self.max_output_tokens = get_max_output_tokens(model)
        else:
            # 如果用户指定了值，确保不超过模型上限
            self.max_output_tokens = clamp_max_output_tokens(model, max_output_tokens)

        self.max_retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
        self.retry_delay = retry_delay if retry_delay is not None else DEFAULT_RETRY_DELAY

        # 从环境变量获取 API Key
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY 环境变量未设置\n"
                "请确保 .env 文件包含有效的 DASHSCOPE_API_KEY"
            )

        # 设置全局 API Key
        dashscope.api_key = self.api_key
        print(f"🔑 使用 Qwen API: {model}")

    def _call_api(
        self,
        user_prompt: str,
        system_instruction: Optional[str] = None,
        verbose: bool = False
    ) -> tuple:
        """
        调用 Qwen API

        Args:
            user_prompt: 用户提示词
            system_instruction: 系统指令
            verbose: 是否显示详细信息

        Returns:
            (API 响应文本, 响应时间毫秒)

        Raises:
            ValueError: API 调用失败
        """
        response_text = None
        response_time_ms = None

        for attempt in range(self.max_retries):
            try:
                if verbose:
                    print(f"📤 尝试 {attempt + 1}/{self.max_retries} - 发送提示词长度: {len(user_prompt)} 字符")
                    if attempt == 0:
                        print("\n" + "=" * 80)
                        print("🔍 SYSTEM PROMPT (完整内容):")
                        print("=" * 80)
                        print(system_instruction if system_instruction else "(无 system instruction)")
                        print("=" * 80)
                        print("\n" + "=" * 80)
                        print("🔍 USER PROMPT (完整内容):")
                        print("=" * 80)
                        print(user_prompt)
                        print("=" * 80 + "\n")
                else:
                    print(f"📤 尝试 {attempt + 1}/{self.max_retries}...")

                # 构建消息列表
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": user_prompt})

                # 发送请求
                api_start_time = time.time()
                response = dashscope.Generation.call(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    result_format="message"
                )
                api_end_time = time.time()
                response_time_ms = (api_end_time - api_start_time) * 1000

                if verbose:
                    print(f"📥 收到响应 (尝试 {attempt + 1}, 耗时 {response_time_ms:.0f}ms)")

                # 检查响应状态
                if response.status_code != 200:
                    error_msg = f"API 返回错误: {response.status_code}"
                    if hasattr(response, 'message'):
                        error_msg += f" - {response.message}"
                    raise ValueError(error_msg)

                # 提取响应文本
                response_text = self._extract_response_text(response, verbose)
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

        if response_text is None:
            raise ValueError("无法获得 API 响应")

        return response_text, response_time_ms

    def _extract_response_text(self, response: Any, verbose: bool = False) -> str:
        """从 Qwen API 响应中提取文本"""
        try:
            # DashScope API 响应结构: response.output.choices[0].message.content
            if not hasattr(response, 'output'):
                raise ValueError("响应缺少 output 字段")

            output = response.output
            if not hasattr(output, 'choices') or not output.choices:
                raise ValueError("响应缺少 choices 字段或为空")

            choice = output.choices[0]
            if not hasattr(choice, 'message'):
                raise ValueError("响应缺少 message 字段")

            message = choice.message
            if not hasattr(message, 'content'):
                raise ValueError("响应缺少 content 字段")

            content = message.content

            # 检查 finish_reason
            if hasattr(choice, 'finish_reason'):
                finish_reason = choice.finish_reason
                if verbose:
                    print(f"🔍 finish_reason: {finish_reason}")

                if finish_reason == 'stop':
                    # 正常完成
                    return content
                elif finish_reason == 'length':
                    print(
                        "⚠️  响应被截断 - 达到最大 token 限制 "
                        f"(model={self.model}, max_output_tokens={self.max_output_tokens})"
                    )
                    # 仍然返回部分内容
                    return content
                else:
                    print(f"⚠️  未知的 finish_reason: {finish_reason}")
                    return content

            return content

        except Exception as e:
            raise ValueError(f"无法从 API 响应中提取文本: {e}")

    def _build_prompt(
        self,
        input_data: AnnotatorInput
    ) -> tuple:
        """
        构建提示词

        Returns:
            (system_instruction, full_prompt, prompt_hash, prompt_loader)
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
                    f.write("=== Qwen API 原始输出 (JSON 解析失败) ===\n")
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
                    f.write(f"=== Qwen API 原始输出 (校验失败) ===\n")
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

            print(f"✓ {input_data.student_name}: 已保存到 {run_dir}")

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
            print(f"✗ {input_data.student_name}: {e}")
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
    ):
        """
        保存输出文件

        Args:
            run_dir: 运行目录
            student_name: 学生名称
            final_grade: 最终评分
            mistake_count: 错误统计
            annotations: 标注列表
            system_instruction: 系统指令
            full_prompt: 完整提示词
            prompt_hash: 提示词 hash
            prompt_loader: PromptLoader 实例
            run_id: 运行 ID
            question_bank_filename: 题库文件名
            response_time_ms: 响应时间（毫秒）
        """
        # 1. 保存 4_llm_annotation.json
        annotation_path = run_dir / "4_llm_annotation.json"
        with open(annotation_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "student_name": student_name,
                    "final_grade_suggestion": final_grade,
                    "mistake_count": mistake_count,
                    "annotations": annotations,
                    "run_id": run_id,
                    "model": self.model,
                    "question_bank_filename": question_bank_filename,
                    "prompt_hash": prompt_hash,
                    "response_time_ms": response_time_ms,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
                ensure_ascii=False,
                indent=2
            )

        # 2. 保存 prompt_log.txt
        prompt_log_path = run_dir / "prompt_log.txt"
        with open(prompt_log_path, "w", encoding="utf-8") as f:
            f.write("=== System Prompt ===\n")
            f.write(system_instruction)
            f.write("\n\n")
            f.write("=== User Prompt ===\n")
            f.write(full_prompt)
            f.write("\n")

        # 3. 保存 prompt metadata（如果有）
        if hasattr(prompt_loader, 'metadata') and prompt_loader.metadata:
            metadata_path = run_dir / "prompt_metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(
                    prompt_loader.metadata,
                    f,
                    ensure_ascii=False,
                    indent=2
                )
