# -*- coding: utf-8 -*-
"""
scripts/annotators/qwen_omni.py - Qwen3-Omni Annotator 实现

使用 OpenAI 兼容接口调用 Qwen3-Omni Flash 模型进行音频标注。
"""

import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from jinja2 import Environment
from openai import OpenAI

from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput

# 统一加载环境变量
from scripts.common.env import load_env
load_env()

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

AUDIO_PROMPT_TEMPLATE = "user_with_audio.md"
DEFAULT_MODEL = "qwen-omni-flash"


def _round2(value: Optional[float]) -> Optional[float]:
    """Round to 2 decimals, returning None if value is falsy."""
    return round(value, 2) if value else None


class Qwen3OmniAnnotator(BaseAnnotator):
    """
    Qwen3-Omni Flash Annotator - 使用 OpenAI 兼容接口

    音频通过 base64 编码直接传递，无需文件上传。
    """

    def __init__(
        self,
        model: str = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        **kwargs
    ) -> None:
        from .config import get_max_output_tokens

        if model is None:
            model = DEFAULT_MODEL

        self.model = model
        self.name = model
        self.temperature = temperature

        # 文件限制 (Flash 模型)
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.max_duration = 20 * 60  # 20 分钟

        # 从 config 获取 token 限制
        if max_output_tokens is None:
            self.max_output_tokens = get_max_output_tokens(model)
        else:
            from .config import clamp_max_output_tokens
            self.max_output_tokens = clamp_max_output_tokens(model, max_output_tokens)

        # 创建 OpenAI 客户端（指向阿里云端点）
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "未设置 DASHSCOPE_API_KEY 环境变量\n"
                "请在 .env 文件中添加: DASHSCOPE_API_KEY=your_api_key"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        print(f"🔑 使用 Qwen3-Omni API (model={self.model})")

    def _validate_audio(self, audio_path: Path) -> Tuple[bool, Optional[str]]:
        """
        验证音频文件
        Returns: (is_valid, error_message)
        """
        # 检查文件大小
        file_size = audio_path.stat().st_size
        if file_size > self.max_file_size:
            size_mb = file_size / 1024 / 1024
            return False, f"文件过大: {size_mb:.1f}MB > 100MB"

        # 检查时长（使用 ffprobe）
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                 str(audio_path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                if duration > self.max_duration:
                    return False, f"音频过长: {duration/60:.1f}分钟 > 20分钟"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            # ffprobe 失败时只检查文件大小
            pass

        return True, None

    def _encode_audio(self, audio_path: Path) -> Tuple[str, str]:
        """
        编码音频为 base64
        Returns: (base64_string, mime_type)
        """
        # 识别 MIME 类型
        ext = audio_path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".mp4": "audio/mp4",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".amr": "audio/amr",
            ".3gp": "audio/3gpp"
        }
        mime_type = mime_map.get(ext, "audio/mpeg")

        # 编码
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        base64_audio = base64.b64encode(audio_data).decode("utf-8")

        return base64_audio, mime_type

    def _build_prompt(self, question_bank_content: str, asr_text: str) -> Tuple[str, str, str]:
        """
        构建 prompt（复用 Gemini 模板）
        Returns: (system_instruction, full_prompt, prompt_version)
        """
        prompt_dir = _PROJECT_ROOT / "prompts" / "annotation"
        audio_template_path = prompt_dir / AUDIO_PROMPT_TEMPLATE
        if not audio_template_path.exists():
            raise FileNotFoundError(f"未找到音频版模板: {audio_template_path}")

        with open(audio_template_path, "r", encoding="utf-8") as f:
            template_text = f.read()

        system_path = prompt_dir / "system.md"
        system_instruction = ""
        if system_path.exists():
            with open(system_path, "r", encoding="utf-8") as f:
                system_instruction = f.read().strip()

        env = Environment(trim_blocks=True, lstrip_blocks=True)
        template = env.from_string(template_text)
        full_prompt = template.render(
            question_bank_json=question_bank_content,
            student_asr_text=asr_text,
            student_input_audio="[音频文件已作为附件传入，请直接读取分析]",
        )

        metadata_path = prompt_dir / "metadata.json"
        prompt_version = "unknown"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                prompt_metadata = json.load(f)
                prompt_version = prompt_metadata.get("prompt_version", "unknown")

        return system_instruction, full_prompt, prompt_version

    def _call_api(
        self,
        system_instruction: str,
        user_prompt: str,
        audio_base64: str,
        mime_type: str,
        verbose: bool = False
    ) -> Tuple[str, float, Dict[str, int]]:
        """
        调用 Qwen3-Omni API（流式）
        Returns: (response_text, response_time_ms, token_usage)
        """
        # 构建消息
        messages = [
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio_url",
                        "audio_url": {
                            "url": f"data:{mime_type};base64,{audio_base64}"
                        }
                    },
                    {"type": "text", "text": user_prompt}
                ]
            }
        ]

        # 调用 API
        start_time = time.time()
        collected_text = []
        token_usage = {}

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                stream=True,
                response_format={"type": "json_object"}
            )

            # 处理流式响应
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    collected_text.append(chunk.choices[0].delta.content)

                # 提取 token 使用（在最后一个 chunk）
                if hasattr(chunk, 'usage') and chunk.usage:
                    token_usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0
                    }

            response_time_ms = (time.time() - start_time) * 1000
            response_text = "".join(collected_text)

            if verbose:
                print(f"🔍 API 响应时间: {response_time_ms:.0f}ms")
                print(f"🔍 Token 使用: {token_usage}")

            return response_text, response_time_ms, token_usage

        except Exception as e:
            raise ValueError(f"API 调用失败: {str(e)}")

    def _save_outputs(
        self,
        run_dir: Path,
        student_name: str,
        final_grade: Optional[str],
        mistake_count: Optional[Dict[str, Any]],
        annotations: list,
        system_instruction: str,
        full_prompt: str,
        prompt_hash: str,
        prompt_version: str,
        run_id: str,
        question_bank_filename: str,
        response_time_ms: float,
        token_usage: Dict[str, int],
        audio_encode_time_seconds: float,
        audio_file_size_bytes: int,
        validation: Optional[Dict[str, Any]] = None,
        audio_duration_seconds: Optional[float] = None,
        total_time_seconds: Optional[float] = None,
    ) -> None:
        from scripts.common.runs import get_git_commit

        git_commit = get_git_commit(short=False)

        annotation_result = {
            "student_name": student_name,
            "validation": validation or {"status": "PASS", "errors": []},
            "final_grade_suggestion": final_grade,
            "mistake_count": mistake_count,
            "annotations": annotations,
            "_metadata": {
                "model": self.model,
                "mode": "sync_streaming",
                "response_time_ms": response_time_ms,
                "token_usage": token_usage,
                "audio_encode_time_seconds": round(audio_encode_time_seconds, 2),
                "audio_file_size_bytes": audio_file_size_bytes,
                "audio_duration_seconds": _round2(audio_duration_seconds),
                "total_time_seconds": _round2(total_time_seconds),
                "prompt_version": prompt_version,
                "run_id": run_id,
                "git_commit": git_commit,
                "timestamp": datetime.now().isoformat(),
            }
        }

        annotation_path = run_dir / "4_llm_annotation.json"
        with open(annotation_path, "w", encoding="utf-8") as f:
            json.dump(annotation_result, f, ensure_ascii=False, indent=2)

        prompt_log_path = run_dir / "prompt_log.txt"
        with open(prompt_log_path, "w", encoding="utf-8") as f:
            f.write("=== Qwen3-Omni 音频模式 - 完整提示词日志 ===\n\n")
            f.write(f"Prompt Version: {prompt_version}\n")
            f.write(f"生成时间: {datetime.now().isoformat()}\n")
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Git Commit: {git_commit}\n")
            f.write(f"Model: {self.model}\n")
            f.write(f"题库文件: {question_bank_filename}\n")
            f.write(f"System Instruction 长度: {len(system_instruction)} 字符\n")
            f.write(f"User Prompt 长度: {len(full_prompt)} 字符\n")
            f.write(f"Prompt Hash: {prompt_hash}\n")
            f.write(f"音频文件大小: {audio_file_size_bytes / 1024 / 1024:.2f} MB\n")
            f.write("=" * 80 + "\n\n")
            f.write("SYSTEM INSTRUCTION\n")
            f.write("=" * 80 + "\n")
            f.write(system_instruction)
            f.write("\n\n")
            f.write("USER PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(full_prompt)
            f.write("\n")

    def annotate(self, input_data: AnnotatorInput) -> AnnotatorOutput:
        from scripts.common.archive import project_root, student_dir, load_metadata
        from scripts.common.runs import ensure_run_dir, write_run_manifest, new_run_id
        from scripts.common.hash import text_hash
        from scripts.contracts.cards import validate_cards, parse_api_response

        try:
            root = project_root()
            stu_dir = student_dir(input_data.archive_batch, input_data.student_name)

            run_id = input_data.run_id or new_run_id()
            run_dir = ensure_run_dir(
                input_data.archive_batch,
                input_data.student_name,
                self.name,
                run_id
            )

            audio_path = input_data.audio_path
            if not audio_path:
                raise ValueError("未提供音频文件路径")

            # 验证音频文件
            is_valid, error_msg = self._validate_audio(audio_path)
            if not is_valid:
                return AnnotatorOutput(
                    success=False,
                    error=error_msg,
                    student_name=input_data.student_name,
                    model=self.model
                )

            # 从 metadata.json 获取音频时长
            audio_duration_seconds = None
            try:
                metadata = load_metadata(input_data.archive_batch)
                audio_duration_seconds = next(
                    (item.get("duration_seconds") for item in metadata.get("items", [])
                     if item.get("student") == input_data.student_name),
                    None,
                )
            except FileNotFoundError:
                pass

            # 构建 prompt
            system_instruction, full_prompt, prompt_version = self._build_prompt(
                input_data.question_bank_content or "",
                input_data.asr_text or "",
            )
            prompt_hash = text_hash(full_prompt, prefix=True)

            # 编码音频为 base64
            encode_start = time.time()
            audio_base64, mime_type = self._encode_audio(audio_path)
            audio_encode_time = time.time() - encode_start
            audio_file_size = audio_path.stat().st_size

            # 调用 API（流式）
            response_text, response_time_ms, token_usage = self._call_api(
                system_instruction,
                full_prompt,
                audio_base64,
                mime_type,
                verbose=input_data.verbose
            )

            # 计算总处理时间 = 音频编码时间 + API 响应时间
            total_time_seconds = audio_encode_time + response_time_ms / 1000

            # 解析和验证响应
            parsed = parse_api_response(response_text)
            if parsed.get("_parse_error"):
                raw_output_path = run_dir / "raw_api_output_parse_error.txt"
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write("=== Qwen3-Omni API 原始输出 (JSON 解析失败) ===\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                    f.write(f"学生: {input_data.student_name}\n")
                    f.write(f"Model: {self.model}\n")
                    f.write(f"max_output_tokens: {self.max_output_tokens}\n")
                    f.write("=" * 80 + "\n")
                    f.write(response_text)
                raise ValueError(
                    "LLM 输出不是有效 JSON（很可能是触发 MAX_TOKENS 导致被截断）。\n"
                    f"原始输出已保存到: {raw_output_path}"
                )

            # 提取 validation 结果
            validation = parsed.get("validation", {"status": "PASS", "errors": []})
            validation_status = validation.get("status", "PASS")
            validation_errors = validation.get("errors", [])

            annotations = parsed["annotations"]
            final_grade = parsed["final_grade_suggestion"]
            mistake_count = parsed["mistake_count"]

            # 如果 validation 失败，跳过 cards 校验和 grade 校验
            if validation_status == "FAIL":
                print(f"  ⚠️  {input_data.student_name}: Validation FAIL - {validation_errors}")
                # 保存结果（validation 失败时 annotations 为空，grade/mistake_count 为 null）
                self._save_outputs(
                    run_dir=run_dir,
                    student_name=input_data.student_name,
                    final_grade=None,
                    mistake_count=None,
                    annotations=[],
                    system_instruction=system_instruction,
                    full_prompt=full_prompt,
                    prompt_hash=prompt_hash,
                    prompt_version=prompt_version,
                    run_id=run_id,
                    question_bank_filename=input_data.question_bank_path.name,
                    response_time_ms=response_time_ms,
                    token_usage=token_usage,
                    audio_encode_time_seconds=audio_encode_time,
                    audio_file_size_bytes=audio_file_size,
                    validation=validation,
                    audio_duration_seconds=audio_duration_seconds,
                    total_time_seconds=total_time_seconds,
                )

                write_run_manifest(
                    run_dir=run_dir,
                    annotator_name=self.name,
                    run_id=run_id,
                    archive_batch=input_data.archive_batch,
                    student_name=input_data.student_name,
                    prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / AUDIO_PROMPT_TEMPLATE,
                    prompt_hash=prompt_hash,
                    model=self.model,
                    extra={
                        "timing": {
                            "audio_encode_time_seconds": round(audio_encode_time, 2),
                            "api_response_time_ms": round(response_time_ms, 2),
                            "total_time_seconds": round(total_time_seconds, 2),
                        },
                        "audio_duration_seconds": _round2(audio_duration_seconds),
                        "audio_file_size_bytes": audio_file_size,
                        "token_usage": token_usage,
                        "validation": validation,
                    },
                )

                return AnnotatorOutput(
                    success=True,  # API 调用成功，但 validation 失败
                    student_name=input_data.student_name,
                    final_grade=None,
                    mistake_count=None,
                    annotations=[],
                    run_id=run_id,
                    run_dir=run_dir,
                    model=self.model,
                    prompt_hash=prompt_hash,
                    response_time_ms=response_time_ms,
                    validation=validation,
                )

            # validation 通过，继续原有的 cards 校验逻辑
            is_valid, invalid_items = validate_cards(annotations, strict_timestamp=True)
            if not is_valid:
                raw_output_path = run_dir / "raw_api_output_debug.txt"
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write("=== Qwen3-Omni API 原始输出 (校验失败) ===\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                    f.write(f"学生: {input_data.student_name}\n")
                    f.write(f"无效项数: {len(invalid_items)}\n")
                    f.write(f"无效项:\n{json.dumps(invalid_items[:5], ensure_ascii=False, indent=2)}\n")
                    f.write("=" * 80 + "\n")
                    f.write(response_text)
                raise ValueError(
                    f"cards 校验失败: {len(invalid_items)} 个无效项\n"
                    f"示例: {invalid_items[:3]}\n"
                    f"原始输出已保存到: {raw_output_path}"
                )

            if not final_grade or final_grade not in ["A", "B", "C"]:
                raise ValueError(f"无效的评分等级: {final_grade}")

            self._save_outputs(
                run_dir=run_dir,
                student_name=input_data.student_name,
                final_grade=final_grade,
                mistake_count=mistake_count,
                annotations=annotations,
                system_instruction=system_instruction,
                full_prompt=full_prompt,
                prompt_hash=prompt_hash,
                prompt_version=prompt_version,
                run_id=run_id,
                question_bank_filename=input_data.question_bank_path.name,
                response_time_ms=response_time_ms,
                token_usage=token_usage,
                audio_encode_time_seconds=audio_encode_time,
                audio_file_size_bytes=audio_file_size,
                validation=validation,
                audio_duration_seconds=audio_duration_seconds,
                total_time_seconds=total_time_seconds,
            )

            write_run_manifest(
                run_dir=run_dir,
                annotator_name=self.name,
                run_id=run_id,
                archive_batch=input_data.archive_batch,
                student_name=input_data.student_name,
                prompt_path=_PROJECT_ROOT / "prompts" / "annotation" / AUDIO_PROMPT_TEMPLATE,
                prompt_hash=prompt_hash,
                model=self.model,
                extra={
                    "timing": {
                        "audio_encode_time_seconds": round(audio_encode_time, 2),
                        "api_response_time_ms": round(response_time_ms, 2),
                        "total_time_seconds": round(total_time_seconds, 2),
                    },
                    "audio_duration_seconds": _round2(audio_duration_seconds),
                    "audio_file_size_bytes": audio_file_size,
                    "token_usage": token_usage,
                    "validation": validation,
                },
            )

            if response_time_ms < 1000:
                time_str = f"{response_time_ms:.0f}ms"
            else:
                time_str = f"{response_time_ms / 1000:.2f}s"

            # Token 统计信息
            input_tokens = token_usage.get("prompt_tokens", 0)
            output_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

            token_str = f"📊 Token: ↑{input_tokens} ↓{output_tokens} ∑{total_tokens}"

            print(f"  ✓ {input_data.student_name}: 已保存到 runs/{self.name}/{run_id}/ (⏱ {time_str}, {token_str})")

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
                validation=validation,
            )

        except Exception as e:
            return AnnotatorOutput(
                success=False,
                error=str(e),
                student_name=input_data.student_name,
                model=self.model,
            )

    def run_archive_student(
        self,
        archive_batch: str,
        student_name: str,
        run_dir: Path,
        force: bool = False,
        verbose: bool = False,
    ) -> AnnotatorOutput:
        from scripts.common.archive import (
            student_dir,
            resolve_question_bank,
            load_metadata,
            load_file_content,
            find_audio_file,
        )
        from scripts.common.asr import extract_qwen_asr_text

        try:
            stu_dir = student_dir(archive_batch, student_name)
            qwen_asr_path = stu_dir / "2_qwen_asr.json"
            if not qwen_asr_path.exists():
                return AnnotatorOutput(
                    success=False,
                    error=f"未找到 ASR 文件: {qwen_asr_path}",
                    student_name=student_name,
                    model=self.model
                )

            audio_path = find_audio_file(stu_dir)
            if not audio_path:
                return AnnotatorOutput(
                    success=False,
                    error=f"未找到音频文件: {stu_dir}/1_input_audio.*",
                    student_name=student_name,
                    model=self.model
                )

            try:
                metadata = load_metadata(archive_batch)
            except FileNotFoundError:
                metadata = {}

            question_bank_path = resolve_question_bank(archive_batch, metadata)
            if not question_bank_path:
                return AnnotatorOutput(
                    success=False,
                    error="未找到题库文件",
                    student_name=student_name,
                    model=self.model
                )

            question_bank_content = load_file_content(question_bank_path)

            with open(qwen_asr_path, "r", encoding="utf-8") as f:
                asr_data = json.load(f)
            if asr_data.get("status_code") != 200 or asr_data.get("output") is None:
                error_msg = asr_data.get("message", "ASR 失败")
                return AnnotatorOutput(
                    success=False,
                    error=f"ASR 失败: {error_msg}",
                    student_name=student_name,
                    model=self.model
                )

            asr_text = extract_qwen_asr_text(asr_data)

            input_data = AnnotatorInput(
                archive_batch=archive_batch,
                student_name=student_name,
                question_bank_path=question_bank_path,
                qwen_asr_path=qwen_asr_path,
                asr_timestamp_path=stu_dir / "3_asr_timestamp.json",
                run_id=run_dir.name,
                verbose=verbose,
                force=force,
                audio_path=audio_path,
            )
            input_data.question_bank_content = question_bank_content
            input_data.asr_text = asr_text

            return self.annotate(input_data)

        except Exception as e:
            return AnnotatorOutput(
                success=False,
                error=str(e),
                student_name=student_name,
                model=self.model,
            )
