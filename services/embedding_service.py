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
import json
import logging
from typing import List, Optional

import numpy as np

from config import config
from model import ProcurementNotice, SupplierProfile

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 语义向量服务（类级单例，无需实例化）."""

    _client = None
    _model = None

    @classmethod
    def _ensure_initialized(cls) -> None:
        """读取配置并创建 Ark 客户端（类级单例，仅首次调用时执行）."""
        if cls._client is not None:
            return

        api_key = config.get("llm.api_key")
        if not api_key:
            raise ValueError("缺少 LLM API 密钥配置 (llm.api_key)")

        # 复用 llm_parser 中的 Ark 客户端初始化方式
        from volcenginesdkarkruntime import Ark
        cls._client = Ark(base_url=config.get("llm.base_url"), api_key=api_key)
        cls._model = config.get("embedding.model") or config.get("llm.model")
        if not cls._model:
            raise ValueError("缺少 Embedding 模型配置 (embedding.model)")

    # -------------------------------------------------------------------------
    # 文本构建
    # -------------------------------------------------------------------------

    @staticmethod
    def build_supplier_text(supplier: SupplierProfile) -> str:
        """将供应商画像拼接为一段自然语言文本，用于 Embedding."""
        parts = [
            f"公司业务范围：{supplier.business_scope}",
        ]
        if supplier.qualification_summary:
            parts.append(f"具备的资质：{supplier.qualification_summary}")
        if supplier.company_scale:
            parts.append(f"企业规模：{supplier.company_scale}")
        return "。".join(parts)

    @staticmethod
    def build_notice_text(notice: ProcurementNotice) -> str:
        """将招标公告拼接为一段自然语言文本，用于 Embedding."""
        keywords = "、".join(notice.keywords) if notice.keywords else ""
        parts = [
            f"项目名称：{notice.project_name or notice.title}",
            f"采购品目：{notice.category_name}",
        ]
        if keywords:
            parts.append(f"采购内容关键词：{keywords}")
        if notice.abstract:
            parts.append(f"项目简介：{notice.abstract}")
        if notice.qualification_summary:
            parts.append(f"资质要求：{notice.qualification_summary}")
        return "。".join(parts)

    # -------------------------------------------------------------------------
    # Embedding API 调用
    # -------------------------------------------------------------------------

    @classmethod
    def embed(cls, text: str) -> Optional[List[float]]:
        """调用 Embedding API 获取向量.

        Args:
            text: 输入文本

        Returns:
            向量列表（如 1536 维），失败返回 None
        """
        if not text or not text.strip():
            return None

        cls._ensure_initialized()
        try:
            response = cls._client.embeddings.create(
                model=cls._model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"[Embedding失败] {e}")
            return None

    @classmethod
    def embed_batch(cls, texts: List[str]) -> List[Optional[List[float]]]:
        """批量调用 Embedding API.

        Args:
            texts: 文本列表

        Returns:
            向量列表，与输入一一对应，失败的位置为 None
        """
        if not texts:
            return []

        cls._ensure_initialized()
        # 过滤空文本，但保持位置对应
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_indices]

        if not valid_texts:
            return [None] * len(texts)

        try:
            response = cls._client.embeddings.create(
                model=cls._model,
                input=valid_texts,
            )
            results = [None] * len(texts)
            for idx, data in zip(valid_indices, response.data):
                results[idx] = data.embedding
            return results
        except Exception as e:
            logger.error(f"[Embedding批量失败] {e}")
            return [None] * len(texts)

    # -------------------------------------------------------------------------
    # 便捷方法：直接传入模型对象
    # -------------------------------------------------------------------------

    @classmethod
    def get_supplier_embedding(cls, supplier: SupplierProfile) -> Optional[List[float]]:
        """获取供应商画像的 Embedding 向量."""
        text = cls.build_supplier_text(supplier)
        return cls.embed(text)

    @classmethod
    def get_notice_embedding(cls, notice: ProcurementNotice) -> Optional[List[float]]:
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
        query_vec: List[float],
        candidate_vecs: List[List[float]],
    ) -> List[float]:
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
