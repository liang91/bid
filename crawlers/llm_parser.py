"""基于 LLM 的通用文本解析器.

封装字节火山引擎 Ark SDK 调用，提供统一的 LLM 交互能力。
具体业务解析逻辑由调用方提供。

使用方式：
    from crawlers.llm_parser import LLMParser
    result = LLMParser.parse(prompt)
"""
import json
import logging
from typing import Optional

from crawlers import llm_client, llm_model

logger = logging.getLogger(__name__)


class LLMParser:
    """通用 LLM 文本解析器.

    所有状态通过类变量维护，无需实例化：
        LLMParser.parse(prompt)      # 直接调用
        LLMParser.get_model()        # 获取模型名
    """

    @staticmethod
    def parse(prompt: str) -> dict:
        """调用 LLM 解析文本，返回 JSON dict.

        Args:
            prompt: 用户提示词，说明任务（由平台爬虫类提供）

        Returns:
            LLM 返回的 JSON 对象（dict）
        """
        try:
            response = llm_client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_content = response.choices[0].message.content or ""
            return LLMParser._extract_json(raw_content)
        except Exception as e:
            logger.error(f"[LLM解析失败] {e}")
            return {}


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
