# -*- coding: utf-8 -*-
"""
scripts/gatekeeper/base.py - Gatekeeper 基础接口

定义所有 gatekeeper 的统一接口。
"""

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class GatekeeperInput:
    """Gatekeeper 输入数据"""

    # 必需字段
    archive_batch: str
    student_name: str
    question_bank_path: Path
    qwen_asr_path: Path

    # 可选字段
    verbose: bool = False

    # 从文件加载的内容（延迟加载）
    question_bank_content: Optional[str] = None
    asr_text: Optional[str] = None


@dataclass
class GatekeeperOutput:
    """Gatekeeper 输出结果"""

    # 状态
    status: str  # "PASS" or "FAIL"
    issue_type: Optional[str] = None  # "WRONG_QUESTIONBANK" or "AUDIO_ANOMALY"

    # Anomaly mark (non-blocking)
    ink: str = "normal"  # "normal", "wrong_questionbank", "audio_anomaly"

    # 元数据
    student_name: str = ""
    model: str = "unknown"
    response_time_ms: Optional[float] = None

    def is_pass(self) -> bool:
        """是否通过检查"""
        return self.status == "PASS"

    def format_response_time(self) -> str:
        """格式化响应时间为可读字符串"""
        if self.response_time_ms is None:
            return "N/A"
        if self.response_time_ms < 1000:
            return f"{self.response_time_ms:.0f}ms"
        return f"{self.response_time_ms / 1000:.2f}s"


class BaseGatekeeper(ABC):
    """
    Gatekeeper 基类

    所有 gatekeeper 实现需要继承此类并实现 check 方法。
    """

    # 子类需要设置
    name: str = "base"
    model: str = "unknown"

    @abstractmethod
    def check(self, input_data: GatekeeperInput) -> GatekeeperOutput:
        """
        执行质检

        Args:
            input_data: GatekeeperInput 对象

        Returns:
            GatekeeperOutput 对象
        """
        pass
