"""基于 LLM 的通用文本解析器.

封装字节火山引擎 Ark SDK 调用，提供统一的 LLM 交互能力。
具体业务解析逻辑由调用方提供。

使用方式：
    from crawlers.llm_parser import LLMParser
    result = LLMParser.parse(prompt)
"""
import json
import logging
import re
from typing import Optional

from volcenginesdkarkruntime import Ark

from config import load_config

logger = logging.getLogger(__name__)


class LLMParser:
    """通用 LLM 文本解析器.

    所有状态通过类变量维护，无需实例化：
        LLMParser.parse(prompt)      # 直接调用
        LLMParser.get_model()        # 获取模型名
    """

    _client = None
    _model = None

    @classmethod
    def _ensure_initialized(cls) -> None:
        """读取配置并创建 Ark 客户端（类级单例，仅首次调用时执行）."""
        if cls._client is not None:
            return

        try:
            cfg = load_config()
        except FileNotFoundError:
            cfg = {}

        api_key = cfg.get("llm.api_key")
        if not api_key:
            raise ValueError("缺少 LLM API 密钥配置 (llm.api_key)")

        cls._client = Ark(base_url=cfg.get("llm.base_url"), api_key=api_key)
        cls._model = cfg.get("llm.model")

    @classmethod
    def parse(cls, prompt: str) -> dict:
        """调用 LLM 解析文本，返回 JSON dict.

        Args:
            prompt: 用户提示词，说明任务（由平台爬虫类提供）

        Returns:
            LLM 返回的 JSON 对象（dict）
        """
        cls._ensure_initialized()
        try:
            response = cls._client.chat.completions.create(
                model=cls._model,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_content = response.choices[0].message.content or ""
            return cls._extract_json(raw_content)
        except Exception as e:
            logger.error(f"[LLM解析失败] {e}")
            return {}

    @classmethod
    def get_model(cls) -> Optional[str]:
        """返回当前使用的模型名称（首次调用时触发初始化）."""
        cls._ensure_initialized()
        return cls._model

    @staticmethod
    def _extract_json(content: str) -> dict:
        """从 LLM 回复中提取 JSON 对象."""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return json.loads(content)
