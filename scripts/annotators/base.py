# -*- coding: utf-8 -*-
"""
scripts/annotators/base.py - Annotator 基础接口

定义所有 annotator 的统一接口，供 main.py 调用。
"""

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class AnnotatorInput:
    """Annotator 输入数据"""

    # 必需字段
    archive_batch: str
    student_name: str
    question_bank_path: Path
    qwen_asr_path: Path
    asr_timestamp_path: Path

    # 可选字段
    run_id: Optional[str] = None
    verbose: bool = False
    force: bool = False
    audio_path: Optional[Path] = None

    # 从文件加载的内容（延迟加载）
    question_bank_content: Optional[str] = None
    asr_text: Optional[str] = None
    asr_with_timestamp: Optional[str] = None


@dataclass
class AnnotatorOutput:
    """Annotator 输出结果"""

    # 状态
    success: bool
    error: Optional[str] = None

    # 评分结果
    student_name: str = ""
    final_grade: str = "C"
    mistake_count: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    run_id: str = ""
    run_dir: Optional[Path] = None
    model: str = "unknown"
    prompt_hash: str = ""

    # 性能指标
    response_time_ms: Optional[float] = None  # API 响应时间（毫秒）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "student_name": self.student_name,
            "status": "success" if self.success else "error",
            "error": self.error,
            "final_grade_suggestion": self.final_grade,
            "mistake_count": self.mistake_count,
            "annotations": self.annotations,
            "run_id": self.run_id,
            "model": self.model,
            "response_time_ms": self.response_time_ms,
        }

    def format_response_time(self) -> str:
        """格式化响应时间为可读字符串"""
        if self.response_time_ms is None:
            return "N/A"
        if self.response_time_ms < 1000:
            return f"{self.response_time_ms:.0f}ms"
        return f"{self.response_time_ms / 1000:.2f}s"


class BaseAnnotator(ABC):
    """
    Annotator 基类

    所有 annotator 实现需要继承此类并实现 annotate 方法。
    """

    # 子类需要设置
    name: str = "base"
    model: str = "unknown"

    @abstractmethod
    def annotate(self, input_data: AnnotatorInput) -> AnnotatorOutput:
        """
        执行标注

        Args:
            input_data: AnnotatorInput 对象

        Returns:
            AnnotatorOutput 对象
        """
        pass

    def run_archive_student(
        self,
        archive_batch: str,
        student_name: str,
        run_dir: Path,
        force: bool = False,
        verbose: bool = False
    ) -> AnnotatorOutput:
        """
        便捷方法：处理单个 archive 学生

        自动加载所需文件并调用 annotate 方法。

        Args:
            archive_batch: batch 名称
            student_name: 学生名称
            run_dir: 输出目录
            force: 是否强制重新处理
            verbose: 是否显示详细信息

        Returns:
            AnnotatorOutput 对象
        """
        from scripts.common.archive import (
            student_dir,
            resolve_question_bank,
            load_metadata,
            load_file_content,
        )
        from scripts.contracts.asr_timestamp import extract_timestamp_text

        try:
            # 构建路径
            stu_dir = student_dir(archive_batch, student_name)
            qwen_asr_path = stu_dir / "2_qwen_asr.json"
            timestamp_path = stu_dir / "3_asr_timestamp.json"

            # 检查文件存在
            if not qwen_asr_path.exists():
                return AnnotatorOutput(
                    success=False,
                    error=f"未找到 ASR 文件: {qwen_asr_path}",
                    student_name=student_name
                )

            if not timestamp_path.exists():
                return AnnotatorOutput(
                    success=False,
                    error=f"未找到时间戳文件: {timestamp_path}",
                    student_name=student_name
                )

            # 加载 metadata 和题库
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

            # 创建输入
            input_data = AnnotatorInput(
                archive_batch=archive_batch,
                student_name=student_name,
                question_bank_path=question_bank_path,
                qwen_asr_path=qwen_asr_path,
                asr_timestamp_path=timestamp_path,
                run_id=run_dir.name,
                verbose=verbose,
                force=force,
            )

            # 预加载内容
            input_data.question_bank_content = load_file_content(question_bank_path)
            # 使用 extract_sentences_json 获取完整的 sentences 数组（包含 words 时间戳）
            from scripts.contracts.asr_timestamp import extract_sentences_json
            input_data.asr_with_timestamp = extract_sentences_json(timestamp_path)

            # 提取纯文本 ASR（仅保留文本，过滤元数据）
            import json
            from scripts.common.asr import extract_qwen_asr_text
            with open(qwen_asr_path, "r", encoding="utf-8") as f:
                asr_data = json.load(f)
            input_data.asr_text = extract_qwen_asr_text(asr_data)

            # 调用标注
            output = self.annotate(input_data)
            output.run_dir = run_dir

            return output

        except Exception as e:
            return AnnotatorOutput(
                success=False,
                error=str(e),
                student_name=student_name
            )
