"""基于 LLM 的通用文本解析器.

封装字节火山引擎 Ark SDK 调用，提供统一的 LLM 交互能力。
具体业务解析逻辑（SYSTEM_PROMPT、字段映射）由调用方（平台爬虫类）提供。
"""
import json
import re
from typing import Optional

from volcenginesdkarkruntime import Ark

from .config_loader import load_config

# 加载配置（模块级缓存）
_cfg = None


def _get_config():
    global _cfg
    if _cfg is None:
        try:
            _cfg = load_config()
        except FileNotFoundError:
            _cfg = {}
    return _cfg


class LLMParser:
    """通用 LLM 文本解析器.

    不负责业务字段映射，仅提供：
    1. API 客户端初始化
    2. 调用 LLM 并返回结构化 JSON dict
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            model: Optional[str] = None,
            timeout: Optional[int] = None,
            max_retries: Optional[int] = None,
            max_tokens: Optional[int] = None,
    ):
        cfg = _get_config()

        self.api_key = api_key or cfg.get("llm.api_key") or ""
        self.base_url = base_url or cfg.get("llm.base_url") or "https://ark.cn-beijing.volces.com/api/v3"
        self.model = model or cfg.get("llm.model") or "doubao-seed-2-0-lite-260215"
        self.timeout = timeout if timeout is not None else cfg.get("llm.timeout", 60)
        self.max_retries = max_retries if max_retries is not None else cfg.get("llm.max_retries", 2)
        self.max_tokens = max_tokens if max_tokens is not None else cfg.get("llm.max_tokens", 2048)

        if not self.api_key:
            raise ValueError(
                "LLM API Key 未配置。请在 config.yaml 的 llm.api_key 中设置。"
            )

        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def parse(self, system_prompt: str, user_content: str) -> dict:
        """调用 LLM 解析文本，返回 JSON dict.

        Args:
            system_prompt: 系统提示词（由平台爬虫类提供，包含字段提取指令）
            user_content: 用户输入内容（通常为清理后的公告文本）

        Returns:
            LLM 返回的 JSON 对象（dict）
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ]
            )
            raw_content = response.choices[0].message.content or ""
            return self._extract_json(raw_content)
        except Exception as e:
            print(f"[LLM解析失败] {e}")
            return {}

    @staticmethod
    def _extract_json(content: str) -> dict:
        """从 LLM 回复中提取 JSON 对象."""
        content = content.strip()
        # 尝试去掉 markdown 代码块
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return json.loads(content)
