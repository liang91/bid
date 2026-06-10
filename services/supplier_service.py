from loguru import logger

from dao import SupplierDao, NoticeDao, MatchDao
from models import MatchedNotice, MatchDto, NoticeDto
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
    1. match_score（0-100）：综合匹配分数（整数类型），100=完美匹配，
    2. advice：给供应商的建议。包含：是否建议投标（匹配分数>=60分），如果可以投标，请说明理由，以及投标的话更进一步的注意事项和建议；如果不建议投标，说明理由。注意，这个建议是直接展示给供应商看的，所以请你按跟供应商面对面沟通的场景组织语言。

    请严格按以下 JSON 格式返回，只返回 JSON 对象，不要包含任何其他文字：
    [
        {{
            "notice_id": 公告ID,
            "match_score": 85, 
            "advice": "...",
        }}
    ]
    """

    @classmethod
    def filter_for_all(cls) -> int:
        """对所有供应商执行粗筛 + 语义排序."""
        suppliers = SupplierDao.all()
        for supplier in suppliers:
            try:
                cls.filter_for_one(supplier.id)
            except Exception as e:
                logger.error(f"[job_match] 供应商 {supplier.id} 匹配失败: {e}")
        return len(suppliers)

    @classmethod
    def filter_for_one(cls, supplier_id: int, top_k: int = 10):
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
        if not supplier or not supplier.profile_embedding:
            return

        notices = NoticeDao.fetch_candidates(
            region_names=supplier.service_regions,
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
        )
        # 筛选出有Embedding的公告
        notices = [notice for notice in notices if notice.supplier_profile_embedding]
        if not notices:
            logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后无候选")
            return

        logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后: {len(notices)} 条")

        # -------------------------------------------------------------------
        # 第2层：语义排序（Embedding 余弦相似度）
        # -------------------------------------------------------------------
        # 批量矩阵计算相似度
        notice_vectors = [notice.supplier_profile_embedding for notice in notices]
        scores = LLMEmbedding.similarities(supplier.profile_embedding, notice_vectors)
        scored = list(zip(scores, notices))
        scored.sort(key=lambda x: x[0], reverse=True)

        matched_notices = [MatchedNotice(filter_score=score, notice_id=notice.id) for score, notice in scored[:top_k]]
        match_id = MatchDao.create(MatchDto(supplier_id=supplier_id, matched_notices=matched_notices, status=20))
        logger.info(f"[filtered_notices] 供应商 {supplier_id} 完成粗筛，结果ID: {match_id}")

    # -----------------------------------------------------------------------
    # AI 精筛
    # -----------------------------------------------------------------------
    @classmethod
    def match_for_one(cls, match_id: int, top_n: int = 20) -> bool:
        """对单个 Match 记录进行 AI 精筛。
        Args:
            match_id: 粗筛后的 Match 记录 ID
            top_n: 提交给 LLM 评估的候选公告数量（控制 token 消耗）
        """
        match = MatchDao.get(match_id)
        if not match or not match.matched_notices:
            logger.warning(f"[ai_match] Match {match_id} 不存在或无可选公告")
            return False

        supplier = SupplierDao.get(match.supplier_id)
        if not supplier:
            logger.warning(f"[ai_match] 供应商 {match.supplier_id} 不存在")
            return False

        # 获取候选公告详情（取 top_n 条）
        notices: list[NoticeDto] = []
        match.matched_notices = match.matched_notices[:top_n]
        for item in match.matched_notices:
            notice = NoticeDao.get(item.notice_id)
            if notice:
                notices.append(notice)
        if not notices:
            logger.warning(f"[ai_match] Match {match_id} 无法获取任何候选公告详情")
            return False

        logger.info(f"[ai_match] 供应商 {match.supplier_id} Match:{match_id} 开始对 {len(notices)} 条公告进行 AI 评估")

        prompt = cls.match_prompt(supplier, notices)
        try:
            result = LLMParser.parse(prompt)
        except Exception as e:
            logger.error(f"[ai_match] LLM 调用失败: {e}")
            return False

        if not result or not isinstance(result, list):
            logger.error(f"[ai_match] LLM 返回结果异常: {result}")
            return False

        # 把AI匹配结果和过滤结果结合
        for notice in match.matched_notices:
            for temp in result:
                if notice.notice_id == temp['notice_id']:
                    notice.match_score = temp['match_score']
                    notice.advice = temp['advice']
        match.matched_notices.sort(key=lambda x: x.match_score, reverse=True)
        match.status = 30

        success = MatchDao.update(match)
        if success:
            logger.info(f"[ai_match] 供应商 {match.supplier_id} Match {match_id} "
                        f"精筛完成，最佳匹配分数: {match.matched_notices[0].match_score}")
        else:
            logger.error(f"[ai_match] Match {match_id} 更新数据库失败")
        return success

    @classmethod
    def match_for_all(cls, limit: int = 100) -> None:
        """批量处理所有 status=20（已完成粗筛）的 Match 记录。"""
        matches = MatchDao.fetch_by_status(status=20, limit=limit)
        if not matches:
            logger.info("[ai_match_all] 没有待精筛的 Match 记录")
            return
        logger.info(f"[ai_match_all] 发现 {len(matches)} 条待精筛记录")

        with ThreadPoolExecutor(max_workers=20) as executor:
            for match in matches:
                try:
                    executor.submit(cls.match_for_one, match.id)
                except Exception as e:
                    logger.error(f"[ai_match_all] Match {match.id} 精筛异常: {e}")

    @classmethod
    def match_prompt(cls, supplier, notices: list[NoticeDto]) -> str:
        """构建 AI 精筛 Prompt。"""
        notices_text = "\n".join(cls.notice_text(n, i + 1) for i, n in enumerate(notices))

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
