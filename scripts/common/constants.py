# -*- coding: utf-8 -*-
"""
scripts/common/constants.py - Shared constants and enums

Defines shared constants used across the annotation pipeline.
"""

from enum import Enum
from typing import Optional


class InkMark(str, Enum):
    """
    Anomaly mark values for teacher review.

    These marks indicate different types of anomalies detected during
    the gatekeeper check. The annotation pipeline continues regardless
    of the mark value - these are for highlighting only, not blocking.
    """
    NORMAL = "normal"
    WRONG_QUESTIONBANK = "wrong_questionbank"
    AUDIO_ANOMALY = "audio_anomaly"

    @classmethod
    def from_gatekeeper_status(cls, status: str, issue_type: Optional[str]) -> "InkMark":
        """
        Convert gatekeeper status and issue_type to InkMark.

        Args:
            status: Gatekeeper status ("PASS" or "FAIL")
            issue_type: Issue type when status is "FAIL"
                       ("WRONG_QUESTIONBANK" or "AUDIO_ANOMALY")

        Returns:
            InkMark value

        Examples:
            InkMark.from_gatekeeper_status("PASS", None) -> InkMark.NORMAL
            InkMark.from_gatekeeper_status("FAIL", "WRONG_QUESTIONBANK") -> InkMark.WRONG_QUESTIONBANK
            InkMark.from_gatekeeper_status("FAIL", "AUDIO_ANOMALY") -> InkMark.AUDIO_ANOMALY
        """
        if status == "PASS":
            return cls.NORMAL
        elif status == "FAIL" and issue_type:
            # Map issue_type to InkMark
            issue_type_upper = issue_type.upper()
            if issue_type_upper == "WRONG_QUESTIONBANK":
                return cls.WRONG_QUESTIONBANK
            elif issue_type_upper == "AUDIO_ANOMALY":
                return cls.AUDIO_ANOMALY
            else:
                # Unknown issue type - default to audio anomaly
                return cls.AUDIO_ANOMALY
        else:
            # Default to normal if status is unclear
            return cls.NORMAL
