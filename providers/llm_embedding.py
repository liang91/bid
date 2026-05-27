"""Embedding 语义向量服务.

封装字节火山引擎 Ark SDK 的 Embedding 能力，提供：
1. 供应商画像文本 → Embedding 向量
2. 公告内容文本 → Embedding 向量
3. 向量相似度计算（余弦相似度）
"""
from typing import Any, List

from loguru import logger
import numpy as np
from config import config
import dashscope


class LLMEmbedding:
    """Embedding 语义向量服务（类级单例，无需实例化）."""
    api_key = config.get("embedding.api_key")
    model = config.get("embedding.model")

    @classmethod
    def embed(cls, text: str, text_type: str = 'document') -> bytes | None:
        """调用 Embedding API 获取向量.
        Args:
            text: 待编码文本
            text_type: 文本类型，document 或 query
        Returns:
            返回 numpy float32 字节流（用于 BLOB 存储）
        """
        try:
            resp = dashscope.TextEmbedding.call(
                api_key=cls.api_key,
                model=cls.model,
                input=text,
                dimension=512,
                text_type=text_type,
            )
            vec = resp.output['embeddings'][0]['embedding']
            return np.array(vec, dtype=np.float32).tobytes()
        except Exception as e:
            logger.error(f"[Embedding失败] {e}")
            return None

    @staticmethod
    def build_supplier_text(supplier: Any) -> str:
        """将供应商画像拼接为一段自然语言文本，用于 Embedding."""

        return "。".join(parts)

    # -------------------------------------------------------------------------
    # 便捷方法：直接传入模型对象
    # -------------------------------------------------------------------------

    @classmethod
    def get_supplier_embedding(cls, supplier: Any) -> bytes | None:
        """获取供应商画像的 Embedding 向量."""
        text = cls.build_supplier_text(supplier)
        return cls.embed(text)

    # -------------------------------------------------------------------------
    # 相似度计算
    # -------------------------------------------------------------------------
    @staticmethod
    def similarity(a: bytes, b: bytes) -> float:
        """计算两个向量的余弦相似度.

        Args:
            a: 向量 A
            b: 向量 B

        Returns:
            余弦相似度（-1 ~ 1），通常 Embedding 向量在 0 ~ 1 之间
        """
        if not a or not b:
            return 0.0
        vec_a = np.frombuffer(a, dtype=np.float32)
        vec_b = np.frombuffer(b, dtype=np.float32)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    @staticmethod
    def similarities(
            query_vec: bytes,
            candidate_vecs: list[bytes],
    ) -> list[float]:
        """计算一个 query 向量与多个候选向量的相似度（批量矩阵运算）.

        Args:
            query_vec: query 向量
            candidate_vecs: 候选向量列表

        Returns:
            相似度分数列表
        """
        if not query_vec or not candidate_vecs:
            return []
        q = np.frombuffer(query_vec, dtype=np.float32)
        mat = np.stack([np.frombuffer(b, dtype=np.float32) for b in candidate_vecs])

        # 归一化后矩阵乘法
        q_norm = q / np.linalg.norm(q)
        mat_norm = mat / np.linalg.norm(mat, axis=1, keepdims=True)
        scores = np.dot(mat_norm, q_norm)
        return scores.tolist()
