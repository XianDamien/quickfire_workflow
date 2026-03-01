# -*- coding: utf-8 -*-
"""
scripts/asr/ - ASR Provider 模块

提供可替换的 ASR 实现：
- QwenASRProvider: Qwen3-ASR 语音转写
- FunASRTimestampProvider: FunASR 时间戳生成
"""

from scripts.asr.qwen import QwenASRProvider
from scripts.asr.funasr import FunASRTimestampProvider, VocabularySlotManager

__all__ = ["QwenASRProvider", "FunASRTimestampProvider", "VocabularySlotManager"]
