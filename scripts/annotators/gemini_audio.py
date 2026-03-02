# -*- coding: utf-8 -*-
"""
scripts/annotators/gemini_audio.py - Gemini Audio Annotator 实现

同步音频模式：直接上传音频文件并调用 Gemini 评分。
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from jinja2 import Environment
from google import genai
from google.genai import types

from .base import BaseAnnotator, AnnotatorInput, AnnotatorOutput

# 统一加载环境变量（如果 main.py 已加载则跳过）
from scripts.common.env import load_env, require_env
load_env()

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

AUDIO_PROMPT_TEMPLATE = "user_with_audio.md"
DEFAULT_MODEL = "gemini-3-pro-preview"
DEFAULT_TIMEOUT_MS = 300000


def _round2(value: Optional[float]) -> Optional[float]:
    """Round to 2 decimals, returning None if value is falsy."""
    return round(value, 2) if value else None


def _guess_audio_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in [".mp3"]:
        return "audio/mpeg"
    if ext in [".wav"]:
        return "audio/wav"
    if ext in [".m4a", ".mp4"]:
        return "audio/mp4"
    if ext in [".flac"]:
        return "audio/flac"
    return "audio/mpeg"


def _create_client(proxy: Optional[str], timeout_ms: int) -> genai.Client:
    api_key = require_env("GEMINI_API_KEY")

    if proxy is None:
        proxy = (
            os.getenv("HTTPS_PROXY")
            or os.getenv("ALL_PROXY")
            or os.getenv("HTTP_PROXY")
            or os.getenv("PROXY")
        )
        if not proxy:
            proxy = "socks5://127.0.0.1:7890"

    http_options_kwargs: Dict[str, Any] = {"timeout": timeout_ms}

    if proxy:
        print(f"🌐 使用代理: {proxy}")
        transport = httpx.HTTPTransport(proxy=proxy, retries=3)
        custom_client = httpx.Client(
            transport=transport,
            timeout=timeout_ms / 1000,
            follow_redirects=True,
        )
        http_options_kwargs["httpx_client"] = custom_client
    else:
        print("⚠️  未配置代理，直连官方 API")

    http_options = types.HttpOptions(**http_options_kwargs)
    return genai.Client(api_key=api_key, http_options=http_options)


class GeminiAudioAnnotator(BaseAnnotator):
    """
    Gemini Audio Annotator 实现

    通过音频文件 + ASR 文本进行同步评分。
    """

    def __init__(
        self,
        model: str = None,
        name_override: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        max_retries: int = None,
        retry_delay: int = None,
        http_timeout: int = None,
        proxy: Optional[str] = None,
    ) -> None:
        from .config import (
            DEFAULT_HTTP_TIMEOUT,
            DEFAULT_MAX_RETRIES,
            DEFAULT_RETRY_DELAY,
            get_max_output_tokens,
            clamp_max_output_tokens,
        )

        if model is None:
            model = DEFAULT_MODEL

        self.model = model
        self.name = name_override or model
        self.temperature = temperature
        self.max_retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
        self.retry_delay = retry_delay if retry_delay is not None else DEFAULT_RETRY_DELAY
        self.http_timeout = http_timeout if http_timeout is not None else DEFAULT_HTTP_TIMEOUT

        if max_output_tokens is None:
            self.max_output_tokens = get_max_output_tokens(model)
        else:
            self.max_output_tokens = clamp_max_output_tokens(model, max_output_tokens)

        self.client = _create_client(proxy=proxy, timeout_ms=self.http_timeout)
        print("🔑 使用官方 SDK (同步音频)")

    def _build_prompt(self, question_bank_content: str, asr_text: str) -> tuple:
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

    def _extract_response_text(self, response: Any, verbose: bool = False) -> str:
        if not response.candidates or len(response.candidates) == 0:
            raise ValueError("API 没有返回候选结果")

        candidate = response.candidates[0]
        if verbose:
            print(f"🔍 finish_reason: {candidate.finish_reason}")

        if hasattr(candidate, "finish_reason") and candidate.finish_reason:
            reason_name = getattr(candidate.finish_reason, "name", None)
            if reason_name == "STOP":
                try:
                    if hasattr(response, "text") and response.text:
                        return response.text
                    if candidate.content and candidate.content.parts:
                        return candidate.content.parts[0].text
                    return "[]"
                except Exception:
                    return "[]"
            if reason_name == "SAFETY":
                raise ValueError("内容被安全过滤器阻止")
            if reason_name == "MAX_TOKENS":
                print(
                    "⚠️  响应被截断 - 达到最大 token 限制 "
                    f"(model={self.model}, max_output_tokens={self.max_output_tokens})"
                )
                if hasattr(response, "text") and response.text:
                    return response.text
                raise ValueError("响应被截断且无法获取部分内容")

            raise ValueError(f"API 返回异常状态: {candidate.finish_reason}")

        raise ValueError("无法确定 API 响应状态")

    def _extract_token_usage(self, response: Any) -> Dict[str, int]:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return {
                "prompt_tokens": 0,
                "candidates_tokens": 0,
                "total_tokens": 0,
                "cached_content_tokens": 0,
            }

        # 提取所有可能的 token 字段
        result = {
            "prompt_tokens": usage.prompt_token_count or 0,
            "candidates_tokens": usage.candidates_token_count or 0,
            "total_tokens": usage.total_token_count or 0,
            "cached_content_tokens": usage.cached_content_token_count or 0,
        }

        # 检查是否有 thinking tokens（Extended Thinking 模式）
        if hasattr(usage, "thoughts_token_count"):
            result["thoughts_tokens"] = usage.thoughts_token_count or 0

        return result

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
        audio_file_uri: str,
        audio_upload_time_seconds: float,
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
                "mode": "sync",
                "response_time_ms": response_time_ms,
                "token_usage": token_usage,
                "audio_upload_time_seconds": round(audio_upload_time_seconds, 2),
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
            f.write("=== Gemini 音频模式 - 完整提示词日志 ===\n\n")
            f.write(f"Prompt Version: {prompt_version}\n")
            f.write(f"生成时间: {datetime.now().isoformat()}\n")
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Git Commit: {git_commit}\n")
            f.write(f"Model: {self.model}\n")
            f.write(f"题库文件: {question_bank_filename}\n")
            f.write(f"System Instruction 长度: {len(system_instruction)} 字符\n")
            f.write(f"User Prompt 长度: {len(full_prompt)} 字符\n")
            f.write(f"Prompt Hash: {prompt_hash}\n")
            f.write(f"Audio File URI: {audio_file_uri}\n")
            f.write("=" * 80 + "\n\n")
            f.write("SYSTEM INSTRUCTION\n")
            f.write("=" * 80 + "\n")
            f.write(system_instruction)
            f.write("\n\n")
            f.write("USER PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(full_prompt)
            f.write("\n")

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
                    student_name=student_name
                )

            audio_path = find_audio_file(stu_dir)
            if not audio_path:
                return AnnotatorOutput(
                    success=False,
                    error=f"未找到音频文件: {stu_dir}/1_input_audio.*",
                    student_name=student_name
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
                    student_name=student_name
                )

            question_bank_content = load_file_content(question_bank_path)

            with open(qwen_asr_path, "r", encoding="utf-8") as f:
                asr_data = json.load(f)
            if asr_data.get("status_code") != 200 or asr_data.get("output") is None:
                error_msg = asr_data.get("message", "ASR 失败")
                return AnnotatorOutput(
                    success=False,
                    error=f"ASR 失败: {error_msg}",
                    student_name=student_name
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

            system_instruction, full_prompt, prompt_version = self._build_prompt(
                input_data.question_bank_content or "",
                input_data.asr_text or "",
            )
            prompt_hash = text_hash(full_prompt, prefix=True)

            mime_type = _guess_audio_mime_type(audio_path)
            upload_start = time.time()
            uploaded = self.client.files.upload(
                file=str(audio_path),
                config=types.UploadFileConfig(
                    display_name=f"{input_data.archive_batch}-{input_data.student_name}-audio",
                    mime_type=mime_type,
                )
            )
            audio_upload_time = time.time() - upload_start

            config_kwargs = {
                "temperature": self.temperature,
                "response_mime_type": "application/json",
                "max_output_tokens": self.max_output_tokens,
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            api_start_time = time.time()
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded.uri,
                                mime_type=mime_type,
                            ),
                            types.Part(text=full_prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(**config_kwargs),
            )
            response_time_ms = (time.time() - api_start_time) * 1000

            raw_response = self._extract_response_text(response, verbose=input_data.verbose)
            token_usage = self._extract_token_usage(response)

            # 计算总处理时间 = 音频上传时间 + API 响应时间
            total_time_seconds = audio_upload_time + response_time_ms / 1000

            parsed = parse_api_response(raw_response)
            if parsed.get("_parse_error"):
                raw_output_path = run_dir / "raw_api_output_parse_error.txt"
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write("=== Gemini Audio API 原始输出 (JSON 解析失败) ===\n")
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
                    audio_file_uri=uploaded.uri,
                    audio_upload_time_seconds=audio_upload_time,
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
                            "audio_upload_time_seconds": round(audio_upload_time, 2),
                            "api_response_time_ms": round(response_time_ms, 2),
                            "total_time_seconds": round(total_time_seconds, 2),
                        },
                        "audio_duration_seconds": _round2(audio_duration_seconds),
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
                    f.write("=== Gemini Audio API 原始输出 (校验失败) ===\n")
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
                audio_file_uri=uploaded.uri,
                audio_upload_time_seconds=audio_upload_time,
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
                        "audio_upload_time_seconds": round(audio_upload_time, 2),
                        "api_response_time_ms": round(response_time_ms, 2),
                        "total_time_seconds": round(total_time_seconds, 2),
                    },
                    "audio_duration_seconds": _round2(audio_duration_seconds),
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
            output_tokens = token_usage.get("candidates_tokens", 0)
            thoughts_tokens = token_usage.get("thoughts_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)
            cached_tokens = token_usage.get("cached_content_tokens", 0)

            # 计算总输出 token（包括思考 token）
            total_output_tokens = output_tokens + thoughts_tokens

            token_str = f"📊 Token: ↑{input_tokens} ↓{total_output_tokens}"
            if thoughts_tokens > 0:
                token_str += f" (💭{thoughts_tokens} thinking)"
            token_str += f" ∑{total_tokens}"
            if cached_tokens > 0:
                token_str += f" (💾{cached_tokens} cached)"

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
