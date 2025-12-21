#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Structured prompt loader for Gemini annotation system.

This module provides a clean interface for loading and rendering prompt templates
without version management or fallback logic. All prompts are versioned via git,
and any breaking changes require explicit updates to system.md and user.txt.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError


@dataclass
class PromptArtifacts:
    """Container for loaded prompt components."""
    system_text: str
    user_template_text: str
    metadata: dict


class PromptLoader:
    """
    Loads and renders Gemini annotation prompts from a structured directory.

    Expected directory structure:
        prompts/annotation/
            system.md          # Markdown system instruction
            user.txt           # Jinja2 template for user prompt
            metadata.json      # Descriptive metadata (no version)

    No folder-based versioning, no manifests, no fallback copies.
    Git history is the sole version control mechanism.
    """

    def __init__(self, prompt_dir: str = None):
        """
        Initialize the prompt loader.

        Args:
            prompt_dir: Path to the prompt directory (e.g., prompts/annotation).
                       If None, defaults to prompts/annotation relative to this file.

        Raises:
            FileNotFoundError: If any required prompt file is missing.
            json.JSONDecodeError: If metadata.json is malformed.
        """
        if prompt_dir is None:
            prompt_dir = Path(__file__).parent / "annotation"
        else:
            prompt_dir = Path(prompt_dir)

        if not prompt_dir.exists():
            raise FileNotFoundError(f"Prompt directory not found: {prompt_dir}")

        self.prompt_dir = prompt_dir
        self._artifacts = self._load_artifacts()
        self._jinja_env = None

    def _load_artifacts(self) -> PromptArtifacts:
        """Load all prompt files and metadata."""
        system_file = self.prompt_dir / "system.md"
        # 优先使用 user.md，fallback 到 user.txt
        user_file = self.prompt_dir / "user.md"
        if not user_file.exists():
            user_file = self.prompt_dir / "user.txt"
        metadata_file = self.prompt_dir / "metadata.json"

        # Load system instruction
        if not system_file.exists():
            raise FileNotFoundError(f"System prompt not found: {system_file}")
        with open(system_file, 'r', encoding='utf-8') as f:
            system_text = f.read().strip()

        # Load user template
        if not user_file.exists():
            raise FileNotFoundError(f"User prompt template not found: {user_file}")
        with open(user_file, 'r', encoding='utf-8') as f:
            user_template_text = f.read().strip()

        # Load metadata
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Metadata JSON is malformed ({metadata_file}): {e.msg}",
                    e.doc,
                    e.pos
                )
        else:
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        return PromptArtifacts(
            system_text=system_text,
            user_template_text=user_template_text,
            metadata=metadata
        )

    @property
    def system_instruction(self) -> str:
        """Return the system instruction (non-templated)."""
        return self._artifacts.system_text

    @property
    def metadata(self) -> dict:
        """Return the metadata dictionary."""
        return self._artifacts.metadata

    def _get_jinja_env(self) -> Environment:
        """Create or return cached Jinja2 environment."""
        if self._jinja_env is None:
            # Create inline environment to render the template
            self._jinja_env = Environment(
                trim_blocks=True,
                lstrip_blocks=True
            )
        return self._jinja_env

    def render_user_prompt(self, context: dict) -> str:
        """
        Render the user prompt template with the given context.

        Args:
            context: Dictionary with keys like 'question_bank_json', 'student_asr_text', etc.

        Returns:
            Rendered user prompt as a string.

        Raises:
            jinja2.TemplateError: If template rendering fails.
            KeyError: If required context keys are missing.
        """
        env = self._get_jinja_env()
        try:
            template = env.from_string(self._artifacts.user_template_text)
            return template.render(**context)
        except TemplateNotFound as e:
            raise RuntimeError(f"Template not found: {e}")
        except TemplateSyntaxError as e:
            raise RuntimeError(f"Template syntax error in user prompt: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to render user prompt: {e}")


class PromptContextBuilder:
    """
    Helper class to assemble the context dictionary for prompt rendering.

    Ensures that both prompt files (system.md and user.txt) are consumed together
    with consistent metadata and question bank context.
    """

    @staticmethod
    def build(
        question_bank_json: str,
        student_asr_text: str,
        dataset_name: str,
        student_name: str,
        student_asr_with_timestamp: str = None,
        guidance: str = None,
        metadata: dict = None
    ) -> dict:
        """
        Build a context dictionary for template rendering.

        Args:
            question_bank_json: The question bank JSON content as a string.
            student_asr_text: The student ASR transcription text.
            dataset_name: Name of the dataset (e.g., 'Zoe51530-9.8').
            student_name: Name of the student.
            student_asr_with_timestamp: Optional timestamped ASR text (from 3_asr_timestamp.json).
            guidance: Optional guidance or notes.
            metadata: Optional metadata dictionary (from prompt metadata).

        Returns:
            Dictionary suitable for jinja2 template.render(**context).
        """
        context = {
            'question_bank_json': question_bank_json,
            'student_asr_text': student_asr_text,
            'dataset_name': dataset_name,
            'student_name': student_name,
        }

        # 带时间戳的 ASR 文本（严格必填，用于时间戳估算）
        # Phase 1: 消灭 fallback，缺失时直接失败
        if not student_asr_with_timestamp or not student_asr_with_timestamp.strip():
            raise ValueError(
                "缺少 student_asr_with_timestamp（依赖 3_asr_timestamp.json）。\n"
                "请先运行: python3 scripts/main.py --archive-batch <batch> --target timestamps"
            )
        context['student_asr_with_timestamp'] = student_asr_with_timestamp

        if guidance:
            context['guidance'] = guidance

        if metadata:
            context['metadata'] = metadata

        return context
