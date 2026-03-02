# -*- coding: utf-8 -*-
"""
scripts/gatekeeper/qwen_plus.py - Qwen Plus Gatekeeper 实现

使用 Qwen Plus 模型进行 ASR 质检，检测题库选择错误和音频异常。
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 确保项目根目录在 Python path 中
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import dashscope

from .base import BaseGatekeeper, GatekeeperInput, GatekeeperOutput

# 统一加载环境变量
from scripts.common.env import load_env
load_env()


class QwenPlusGatekeeper(BaseGatekeeper):
    """
    Qwen Plus Gatekeeper 实现

    使用 qwen-plus 模型进行质检，检测：
    1. 题库选择错误 (WRONG_QUESTIONBANK)
    2. 音频异常 (AUDIO_ANOMALY)
    """

    def __init__(
        self,
        model: str = "qwen-plus",
        temperature: float = 0.1,
        max_retries: int = 3,
        retry_delay: int = 5,
    ):
        """
        初始化 Qwen Plus Gatekeeper

        Args:
            model: 模型名称
            temperature: 温度参数（低温以获得更稳定的判断）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.model = model
        self.name = f"gatekeeper-{model}"
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 从环境变量获取 API Key
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY 环境变量未设置\n"
                "请确保 .env 文件包含有效的 DASHSCOPE_API_KEY"
            )

        # 设置全局 API Key
        dashscope.api_key = self.api_key
        print(f"🔑 使用 Gatekeeper: {model}")

    def _load_prompts(self) -> tuple:
        """
        加载 gatekeeper prompt

        Returns:
            (system_instruction, user_template)
        """
        prompt_dir = _PROJECT_ROOT / "prompts" / "asr_gatekeeper"
        system_file = prompt_dir / "system.md"
        user_file = prompt_dir / "user.md"

        if not system_file.exists():
            raise FileNotFoundError(f"未找到 system prompt: {system_file}")
        if not user_file.exists():
            raise FileNotFoundError(f"未找到 user prompt: {user_file}")

        with open(system_file, "r", encoding="utf-8") as f:
            system_instruction = f.read()

        with open(user_file, "r", encoding="utf-8") as f:
            user_template = f.read()

        return system_instruction, user_template

    def _build_user_prompt(
        self,
        user_template: str,
        question_bank_json: str,
        student_asr_text: str
    ) -> str:
        """
        构建 user prompt

        Args:
            user_template: user prompt 模板
            question_bank_json: 题库 JSON 内容
            student_asr_text: 学生 ASR 转写文本

        Returns:
            完整的 user prompt
        """
        # 简单的模板替换
        prompt = user_template.replace("{{ question_bank_json }}", question_bank_json)
        prompt = prompt.replace("{{ student_asr_text }}", student_asr_text)
        return prompt

    def _call_api(
        self,
        user_prompt: str,
        system_instruction: str,
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
                        print("🔍 SYSTEM PROMPT:")
                        print("=" * 80)
                        print(system_instruction[:500] + "...")
                        print("=" * 80)
                        print("\n" + "=" * 80)
                        print("🔍 USER PROMPT:")
                        print("=" * 80)
                        print(user_prompt[:500] + "...")
                        print("=" * 80 + "\n")
                else:
                    print(f"📤 Gatekeeper 检查中 ({attempt + 1}/{self.max_retries})...")

                # 构建消息列表
                messages = [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ]

                # 发送请求
                api_start_time = time.time()
                response = dashscope.Generation.call(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
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

    def _extract_response_text(self, response, verbose: bool = False) -> str:
        """从 Qwen API 响应中提取文本"""
        try:
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

            if verbose and hasattr(choice, 'finish_reason'):
                print(f"🔍 finish_reason: {choice.finish_reason}")

            return content

        except Exception as e:
            raise ValueError(f"无法从 API 响应中提取文本: {e}")

    def _parse_response(self, response_text: str, verbose: bool = False) -> dict:
        """
        解析 API 响应为 JSON

        Args:
            response_text: API 响应文本
            verbose: 是否显示详细信息

        Returns:
            解析后的 JSON 对象

        Raises:
            ValueError: 解析失败
        """
        try:
            # 尝试提取 JSON（去除可能的 markdown 代码块）
            text = response_text.strip()

            # 移除可能的 markdown 代码块标记
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # 解析 JSON
            result = json.loads(text)

            if verbose:
                print(f"✓ 解析 JSON 成功:")
                print(f"  status: {result.get('status')}")
                print(f"  issue_type: {result.get('issue_type')}")

            return result

        except json.JSONDecodeError as e:
            if verbose:
                print(f"✗ JSON 解析失败:")
                print(f"  错误: {e}")
                print(f"  原始响应: {response_text[:200]}...")
            raise ValueError(f"无法解析 JSON 响应: {e}")

    def check(self, input_data: GatekeeperInput) -> GatekeeperOutput:
        """
        执行质检

        Args:
            input_data: GatekeeperInput 对象

        Returns:
            GatekeeperOutput 对象
        """
        try:
            # 加载 prompts
            system_instruction, user_template = self._load_prompts()

            # 构建 user prompt
            user_prompt = self._build_user_prompt(
                user_template,
                input_data.question_bank_content,
                input_data.asr_text
            )

            # 调用 API
            raw_response, response_time_ms = self._call_api(
                user_prompt,
                system_instruction,
                verbose=input_data.verbose
            )

            # 解析响应
            result = self._parse_response(raw_response, verbose=input_data.verbose)

            # 验证响应格式
            status = result.get("status")
            issue_type = result.get("issue_type")

            if status not in ["PASS", "FAIL"]:
                raise ValueError(f"无效的 status: {status}")

            if status == "FAIL" and not issue_type:
                raise ValueError("status 为 FAIL 但未指定 issue_type")

            if status == "PASS" and issue_type is not None:
                raise ValueError("status 为 PASS 但指定了 issue_type")

            # 返回结果
            return GatekeeperOutput(
                status=status,
                issue_type=issue_type,
                student_name=input_data.student_name,
                model=self.model,
                response_time_ms=response_time_ms
            )

        except Exception as e:
            print(f"✗ Gatekeeper 检查失败: {e}")
            # 失败时默认返回 FAIL 以保守处理，但 pipeline 继续执行
            return GatekeeperOutput(
                status="FAIL",
                issue_type="AUDIO_ANOMALY",
                student_name=input_data.student_name,
                model=self.model
            )
