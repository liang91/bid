import json
from datetime import datetime

from loguru import logger

from dao import SupplierDao, NoticeDao, MatchDao
from models import MatchNoticeScore, MatchDto, NoticeDto
from providers import LLMEmbedding, LLMParser
from concurrent.futures.thread import ThreadPoolExecutor


class SupplierService:
    PROMPT = """你是一位资深的招标信息匹配分析师。请根据供应商画像和候选招标公告列表，深度评估供应商与每条公告的匹配程度。

    ## 供应商画像
    - 公司名称：{company_name}
    - 业务范围：{business_scope}
    - 可服务地区：{service_regions}
    - 资质证书：{qualifications}
    - 预算范围：{min_budget} ~ {max_budget} 元
    - 公司规模：{company_scale}
    - 是否中小企业：{sme_status}
    - 是否具备CA：{ca_ready}
    - 偏好采购方式：{preferred_methods}
    - 是否愿意联合投标：{joint_bid_willing}

    ## 候选招标公告列表
    {notices_text}

    ## 评估要求
    对每条公告从以下维度进行评估：
    1. score（0-100）：综合匹配分数，100=完美匹配
    2. level：高(>=80) / 中(50-79) / 低(<50)
    3. reasons：为什么匹配或不匹配的简要说明（100字以内）
    4. risk_tips：投标风险提示（80字以内）
    5. matching_points：2-3个关键匹配点
    6. mismatch_points：1-2个不匹配点（如有）
    7. recommendation：是否建议投标及策略建议（60字以内）

    请严格按以下 JSON 格式返回，只返回 JSON 对象，不要包含任何其他文字：

    {{
      "results": [
        {{
          "notice_id": 公告ID,
          "score": 85.5,
          "level": "高",
          "reasons": "...",
          "risk_tips": "...",
          "matching_points": "...",
          "mismatch_points": "...",
          "recommendation": "..."
        }}
      ],
      "top3_notice_ids": [最高分公告ID, 次高, 第三]
    }}
    """

    @classmethod
    def filter_all(cls) -> int:
        """对所有供应商执行粗筛 + 语义排序."""
        suppliers = SupplierDao.all()
        for supplier in suppliers:
            try:
                cls.filter_one(supplier.id)
            except Exception as e:
                logger.error(f"[job_match] 供应商 {supplier.id} 匹配失败: {e}")
        return len(suppliers)

    @classmethod
    def filter_one(cls, supplier_id: int, top_k: int = 200):
        """
        招标信息推荐，三层匹配架构，本函数执行前两步
            1. 粗筛（SQL硬规则）：时效性、地域、预算
            2. 初筛第二阶段（语义排序）：Embedding 余弦相似度排序
            3. 精筛（AI打分）：LLM 深度语义匹配，输出 Top3
        """
        # -------------------------------------------------------------------
        # 第1层：SQL硬规则粗筛
        # -------------------------------------------------------------------
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return

        candidates = NoticeDao.fetch_candidates(
            region_names=supplier.service_regions,
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
        )
        if not candidates:
            logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后无候选")
            return

        logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后: {len(candidates)} 条")

        # -------------------------------------------------------------------
        # 第2层：语义排序（Embedding 余弦相似度）
        # -------------------------------------------------------------------
        if not supplier.profile_embedding:
            return

        # 收集有 embedding 的公告（supplier_profile_embedding 为 BLOB，需反序列化）
        candidate_with_vectors = []
        candidate_vectors = []
        for candidate in candidates:
            if not candidate.supplier_profile_embedding:
                continue
            candidate_with_vectors.append(candidate)
            candidate_vectors.append(candidate.supplier_profile_embedding)

        if not candidate_with_vectors:
            logger.warning(f"[filtered_notices] 供应商 {supplier.id} 候选公告均无 embedding，跳过语义排序")
            return

        # 批量矩阵计算相似度
        scores = LLMEmbedding.similarities(supplier.profile_embedding, candidate_vectors)
        scored = list(zip(scores, candidate_with_vectors))
        scored.sort(key=lambda x: x[0], reverse=True)

        filtered_notices = [MatchNoticeScore(score=score, notice_id=notice.id) for score, notice in scored[:top_k]]
        match_id = MatchDao.create(MatchDto(supplier_id=supplier_id, filtered_notices=filtered_notices, status=20))
        logger.info(f"[filtered_notices] 供应商 {supplier_id} 完成粗筛，结果ID: {match_id}")

    # -----------------------------------------------------------------------
    # AI 精筛
    # -----------------------------------------------------------------------
    @classmethod
    def match_one(cls, match_id: int, top_n: int = 20) -> bool:
        """对单个 Match 记录进行 AI 精筛。

        Args:
            match_id: 粗筛后的 Match 记录 ID
            top_n: 提交给 LLM 评估的候选公告数量（控制 token 消耗）

        Returns:
            是否成功完成精筛
        """
        match = MatchDao.get(match_id)
        if not match or not match.filtered_notices:
            logger.warning(f"[ai_match] Match {match_id} 不存在或无可选公告")
            return False

        supplier = SupplierDao.get(match.supplier_id)
        if not supplier:
            logger.warning(f"[ai_match] 供应商 {match.supplier_id} 不存在")
            return False

        # 获取候选公告详情（取 top_n 条）
        candidate_notices: list[NoticeDto] = []
        for item in match.filtered_notices[:top_n]:
            notice = NoticeDao.get(item.notice_id)
            if notice:
                candidate_notices.append(notice)

        if not candidate_notices:
            logger.warning(f"[ai_match] Match {match_id} 无法获取任何候选公告详情")
            return False

        logger.info(
            f"[ai_match] 供应商 {match.supplier_id} Match {match_id} "
            f"开始对 {len(candidate_notices)} 条公告进行 AI 评估"
        )

        prompt = cls.match_prompt(supplier, candidate_notices)

        try:
            result = LLMParser.parse(prompt)
        except Exception as e:
            logger.error(f"[ai_match] LLM 调用失败: {e}")
            return False

        if not result or "results" not in result:
            logger.error(f"[ai_match] LLM 返回结果异常: {result}")
            return False

        # 解析并排序
        ai_results = result.get("results", [])
        ai_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        if not ai_results:
            logger.warning(f"[ai_match] LLM 未返回有效评估结果")
            return False

        # 取最佳匹配结果更新 Match 记录
        top = ai_results[0]
        match.ai_match_score = round(top.get("score", 0))
        match.ai_match_level = top.get("level", "")
        match.ai_match_reasons = top.get("reasons", "")
        match.ai_risk_tips = top.get("risk_tips", "")
        match.ai_key_matching_points = top.get("matching_points", "")
        match.ai_mismatch_points = top.get("mismatch_points", "")
        match.ai_recommendation = top.get("recommendation", "")
        match.ai_raw_response = json.dumps(result, ensure_ascii=False)
        match.ai_call_time = datetime.now()
        match.notice_id = top.get("notice_id", 0)
        match.final_score = match.ai_match_score
        match.is_top3 = 1 if match.final_score >= 80 else 0
        match.status = 30

        success = MatchDao.update(match)
        if success:
            logger.info(
                f"[ai_match] 供应商 {match.supplier_id} Match {match_id} "
                f"精筛完成，最佳匹配分数: {match.final_score}"
            )
        else:
            logger.error(f"[ai_match] Match {match_id} 更新数据库失败")
        return success

    @classmethod
    def match_all(cls, limit: int = 100) -> None:
        """批量处理所有 status=20（已完成粗筛）的 Match 记录。"""
        matches = MatchDao.fetch_by_status(status=20, limit=limit)
        if not matches:
            logger.info("[ai_match_all] 没有待精筛的 Match 记录")
            return

        logger.info(f"[ai_match_all] 发现 {len(matches)} 条待精筛记录")
        for match in matches:
            try:
                with ThreadPoolExecutor(max_workers=20) as executor:
                    executor.submit(cls.match_one, match.id)
            except Exception as e:
                logger.error(f"[ai_match_all] Match {match.id} 精筛异常: {e}")

    @classmethod
    def match_prompt(cls, supplier, notices: list[NoticeDto]) -> str:
        """构建 AI 精筛 Prompt。"""
        notices_text = "\n".join(
            cls.notice_text(n, i + 1) for i, n in enumerate(notices)
        )

        return cls.PROMPT.format(
            company_name=supplier.company_name or "未填写",
            business_scope=supplier.business_scope or "未填写",
            service_regions=", ".join(supplier.service_regions) if supplier.service_regions else "未填写",
            qualifications=supplier.qualification_summary or "未填写",
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
            company_scale=supplier.company_scale or "未填写",
            sme_status="是" if supplier.sme_status else "否",
            ca_ready="是" if supplier.ca_ready else "否",
            preferred_methods=supplier.preferred_methods or "未填写",
            joint_bid_willing="是" if supplier.joint_bid_willing else "否",
            notices_text=notices_text,
        )

    @classmethod
    def notice_text(cls, notice: NoticeDto, index: int) -> str:
        """将单条公告压缩为 Prompt 文本片段。"""
        deadline = ""
        if notice.bid_deadline and notice.bid_deadline.year > 1970:
            deadline = notice.bid_deadline.strftime("%Y-%m-%d")
        else:
            deadline = "未指定"

        return (
            f"【{index}】ID:{notice.id} | {notice.title}\n"
            f"    项目:{notice.project_name or '无'} | 预算:{notice.budget}元 | 方式:{notice.method or '未指定'}\n"
            f"    地区:{notice.region_province or '未指定'} | 截止:{deadline}\n"
            f"    中小企业:{'是' if notice.sme_oriented else '否'} | CA:{'是' if notice.ca_required else '否'} | 联合投标:{'是' if notice.joint_bid_allowed else '否'}\n"
            f"    资质要求:{notice.qualification_summary or '无'}\n"
            f"    所需供应商画像:{notice.supplier_profile or '无'}\n"
        )

    # -----------------------------------------------------------------------
    # Embedding 管理
    # -----------------------------------------------------------------------
    @classmethod
    def set_profile_embeddings(cls):
        suppliers = SupplierDao.unembed()
        for supplier in suppliers:
            cls.update_profile_embedding(supplier.id)

    @classmethod
    def update_profile_embedding(cls, supplier_id: int) -> bool:
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return False
        profile = f"公司业务范围：{supplier.business_scope}。具备的资质：{supplier.qualification_summary}"
        vector = LLMEmbedding.embed(profile, text_type='query')
        return SupplierDao.update_embedding(supplier.id, vector)
