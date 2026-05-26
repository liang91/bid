"""Embedding 语义向量服务.

封装字节火山引擎 Ark SDK 的 Embedding 能力，提供：
1. 供应商画像文本 → Embedding 向量
2. 公告内容文本 → Embedding 向量
3. 向量相似度计算（余弦相似度）

使用方式：
    from services.embedding_service import EmbeddingService
    vec = EmbeddingService.get_supplier_embedding(supplier)
    vec = EmbeddingService.get_notice_embedding(notice)
    score = EmbeddingService.cosine_similarity(vec_a, vec_b)
"""
from typing import Any, List

from loguru import logger
import numpy as np
from config import config
import dashscope


class EmbeddingService:
    """Embedding 语义向量服务（类级单例，无需实例化）."""
    api_key = config.get("embedding.api_key")
    model = config.get("embedding.model")

    @classmethod
    def embed(cls, text: str, text_type: str = 'document', as_bytes: bool = False) -> list[float] | bytes | None:
        """调用 Embedding API 获取向量.

        Args:
            text: 待编码文本
            text_type: 文本类型，document 或 query
            as_bytes: 是否返回 numpy float32 字节流（用于 BLOB 存储）

        Returns:
            默认返回 float list；as_bytes=True 时返回 bytes
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
            if as_bytes:
                return np.array(vec, dtype=np.float32).tobytes()
            return vec
        except Exception as e:
            logger.error(f"[Embedding失败] {e}")
            return None

    @staticmethod
    def build_notice_text(notice: Any) -> str:
        """将招标公告拼接为一段自然语言文本，用于 Embedding."""
        parts = [
            f"项目名称：{notice.project_name or notice.title}",
        ]
        if notice.supplier_profile:
            parts.append(f"所需供应商画像：{notice.supplier_profile}")
        if notice.abstract:
            parts.append(f"项目简介：{notice.abstract}")
        if notice.qualification_summary:
            parts.append(f"资质要求：{notice.qualification_summary}")
        return "。".join(parts)

    @staticmethod
    def build_supplier_text(supplier: Any) -> str:
        """将供应商画像拼接为一段自然语言文本，用于 Embedding."""
        parts = [
            f"公司业务范围：{supplier.business_scope}",
        ]
        if supplier.qualification_summary:
            parts.append(f"具备的资质：{supplier.qualification_summary}")
        if supplier.company_scale:
            parts.append(f"企业规模：{supplier.company_scale}")
        return "。".join(parts)

    # -------------------------------------------------------------------------
    # 便捷方法：直接传入模型对象
    # -------------------------------------------------------------------------

    @classmethod
    def get_supplier_embedding(cls, supplier: Any) -> list[float] | None:
        """获取供应商画像的 Embedding 向量."""
        text = cls.build_supplier_text(supplier)
        return cls.embed(text)

    @classmethod
    def get_notice_embedding(cls, notice: Any) -> list[float] | None:
        """获取招标公告的 Embedding 向量."""
        text = cls.build_notice_text(notice)
        return cls.embed(text)

    # -------------------------------------------------------------------------
    # 相似度计算
    # -------------------------------------------------------------------------
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度.

        Args:
            a: 向量 A
            b: 向量 B

        Returns:
            余弦相似度（-1 ~ 1），通常 Embedding 向量在 0 ~ 1 之间
        """
        if not a or not b:
            return 0.0
        vec_a = np.array(a, dtype=np.float32)
        vec_b = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    @staticmethod
    def similarity_matrix(
            query_vec: list[float],
            candidate_vecs: list[list[float]],
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
        q = np.array(query_vec, dtype=np.float32)
        mat = np.array(candidate_vecs, dtype=np.float32)
        # 归一化后矩阵乘法
        q_norm = q / np.linalg.norm(q)
        mat_norm = mat / np.linalg.norm(mat, axis=1, keepdims=True)
        scores = np.dot(mat_norm, q_norm)
        return scores.tolist()
