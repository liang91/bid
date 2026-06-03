-- ============================================================
-- 招标公告数据服务 MySQL 表结构（最终版）
-- 适用: MySQL 8.0+ (使用 JSON 类型)
-- 字符集: utf8mb4 (支持完整 Unicode，包括 emoji)
-- ============================================================

CREATE DATABASE IF NOT EXISTS bid
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE bid;

-- ------------------------------------------------------------
-- 主表: 招标公告主表
-- ------------------------------------------------------------
CREATE TABLE notices (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    platform VARCHAR(64) NOT NULL DEFAULT '' COMMENT '平台：中国政府采购网',
    part VARCHAR(32) NOT NULL DEFAULT '' COMMENT '爬取栏目：中央公告/地方公告',
    title VARCHAR(256) NOT NULL DEFAULT '' COMMENT '列表页原始标题',
    notice_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公告类型：公开招标/竞争性谈判/询价/结果公告/废标公告',

    -- 来源信息
    url VARCHAR(256) NOT NULL DEFAULT '' COMMENT '来源URL',
    region_province VARCHAR(32) NOT NULL DEFAULT '' COMMENT '省/自治区/直辖市',
    region_city VARCHAR(32) NOT NULL DEFAULT '' COMMENT '市/直辖市辖区',
    region_district VARCHAR(32) NOT NULL DEFAULT '' COMMENT '区/县',

    -- 项目信息
    project_name VARCHAR(256) NOT NULL DEFAULT '' COMMENT '项目名称',
    project_no VARCHAR(128) NOT NULL DEFAULT '' COMMENT '项目编号',
    purchase_plan_no VARCHAR(128) NOT NULL DEFAULT '' COMMENT '采购计划编号',
    budget DECIMAL(15,2) NOT NULL DEFAULT 0.00 COMMENT '预算金额',
    currency VARCHAR(8) NOT NULL DEFAULT 'CNY' COMMENT '币种',
    -- 采购方式
    method VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公开招标/竞争性谈判/询价/单一来源',
    joint_bid_allowed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否接受联合体',
    joint_bid_max_members INT NOT NULL DEFAULT 0 COMMENT '联合体最多成员数',
    sme_oriented TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否面向中小企业',

    -- 时间节点（全部改为DATETIME）
    notice_date DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '公告发布日期',
    doc_obtain_start DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '文件获取开始',
    doc_obtain_end DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '文件获取截止',
    bid_deadline DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '投标截止',
    bid_open_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '开标时间',

    -- 投标方式
    bid_platform VARCHAR(128) NOT NULL DEFAULT '' COMMENT '投标平台',
    bid_platform_url VARCHAR(256) NOT NULL DEFAULT '' COMMENT '投标平台URL',
    ca_required TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否需要CA证书',
    doc_price DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '标书费用',

    -- 采购方（采购人）信息
    purchaser_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '采购人名称',
    purchaser_address VARCHAR(256) NOT NULL DEFAULT '' COMMENT '采购人地址',
    purchaser_contact_person VARCHAR(64) NOT NULL DEFAULT '' COMMENT '采购人联系人',
    purchaser_contact_phone VARCHAR(32) NOT NULL DEFAULT '' COMMENT '采购人联系电话',
    -- 代理机构信息
    agency_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '代理机构名称',
    agency_address VARCHAR(256) NOT NULL DEFAULT '' COMMENT '代理机构地址',
    agency_contact_person VARCHAR(64) NOT NULL DEFAULT '' COMMENT '代理机构联系人',
    agency_contact_phone VARCHAR(32) NOT NULL DEFAULT '' COMMENT '代理机构联系电话',

    -- 项目联系人信息（独立字段，用于项目咨询）
    project_contact_person VARCHAR(64) NOT NULL DEFAULT '' COMMENT '项目联系人',
    project_contact_phone VARCHAR(32) NOT NULL DEFAULT '' COMMENT '项目联系方式',

    -- 匹配特征
    qualification_summary TEXT COMMENT '资质要求摘要',
    industry_tags JSON COMMENT '行业标签',

    -- 原始摘要
    abstract TEXT COMMENT '原文摘要',
    supplier_profile VARCHAR(512) COMMENT '所需供应商画像',
    supplier_profile_embedding BLOB COMMENT '所需供应商画像语义向量',
    html VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'html文件路径',
    parse_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '解析时间',

    -- 状态（爬取流程状态）
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1:获取概要信息 20:获取了网页内容 30:解析出了公告内容',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建/爬取时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',

    UNIQUE KEY uk_url (url),
    INDEX idx_notice_date (notice_date),
    INDEX idx_bid_deadline (bid_deadline),
    INDEX idx_region (region_province, region_city, region_district),
    INDEX idx_budget (budget),
    INDEX idx_method (method),

    INDEX idx_status (status),
    FULLTEXT INDEX ft_project_name (project_name),
    FULLTEXT INDEX ft_abstract (abstract)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招标公告主表';

-- ------------------------------------------------------------
-- 资质要求表 notice_qualifications
-- ------------------------------------------------------------
CREATE TABLE notice_qualifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notice_id BIGINT NOT NULL DEFAULT 0 COMMENT '关联公告ID',
    qualification_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT '资质类型：资质许可/业绩要求/人员要求/设备要求/其他',
    name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '资质名称',

    INDEX idx_notice_qual (notice_id, qualification_type),
    INDEX idx_qual_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招标公告资质要求明细';

-- ------------------------------------------------------------
-- 公告附件表 notice_attachments
-- ------------------------------------------------------------
CREATE TABLE notice_attachments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    -- 关联信息
    notice_id BIGINT NOT NULL DEFAULT 0 COMMENT '关联公告ID（对应 notices.id）',

    -- 附件基本信息
    name VARCHAR(256) NOT NULL DEFAULT '' COMMENT '附件名称（如：招标文件、工程量清单、图纸等）',
    url VARCHAR(512) NOT NULL DEFAULT '' COMMENT '原始下载链接',
    object_key VARCHAR(256) NOT NULL DEFAULT '' COMMENT '对象存储Key',

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 索引
    INDEX idx_notice_id (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招标公告附件表';

-- ------------------------------------------------------------
-- 分包表 notice_packages
-- ------------------------------------------------------------
CREATE TABLE notice_packages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notice_id BIGINT NOT NULL DEFAULT 0 COMMENT '关联公告ID',
    no VARCHAR(16) NOT NULL DEFAULT '' COMMENT '包号',
    name VARCHAR(256) NOT NULL DEFAULT '' COMMENT '包名称',
    budget DECIMAL(15,2) NOT NULL DEFAULT 0.00 COMMENT '包预算',
    quantity VARCHAR(8) NOT NULL DEFAULT '' COMMENT '数量',
    unit VARCHAR(32) NOT NULL DEFAULT '' COMMENT '单位',
    intro VARCHAR(1024) NOT NULL DEFAULT '' COMMENT '标项规格描述或概况介绍',

    INDEX idx_notice_pkg (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招标公告分包信息';

-- ------------------------------------------------------------
-- 供应商画像表 supplier
-- ------------------------------------------------------------
CREATE TABLE supplier (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,

    -- 公司基本信息
    company_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '公司名称',
    company_scale VARCHAR(32) NOT NULL DEFAULT '' COMMENT '企业规模：微型/小型/中型/大型',
    province VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公司所在省',
    city VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公司所在市',
    district VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公司所在区',

    sme_status TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否中小企业：0否 1是',
    ca_ready TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已有CA证书：0否 1是',

    -- 业务范围（MVP精简：关键词文本，不用编码字典）
    business_scope TEXT COMMENT '业务范围关键词，逗号分隔，如：建筑设计,基因检测,软件开发,IT运维',
    service_regions JSON COMMENT '可服务地区列表，如：["四川","广东"]',
    profile_embedding JSON COMMENT '业务范围Embedding向量',

    -- 资质证书（JSON简化存储）
    qualifications JSON COMMENT '资质证书列表：[{name, cert_no, valid_until}]',
    qualification_summary VARCHAR(512) NOT NULL DEFAULT '' COMMENT '资质摘要，用于快速匹配，如：医疗机构执业许可证+临床基因扩增检验实验室资质',

    -- 需求偏好
    min_budget DECIMAL(15,2) NOT NULL DEFAULT 0.00 COMMENT '最低预算偏好（0表示不限）',
    max_budget DECIMAL(15,2) NOT NULL DEFAULT 999999999.99 COMMENT '最高预算偏好',
    preferred_methods VARCHAR(128) NOT NULL DEFAULT '' COMMENT '偏好采购方式，逗号分隔，如：公开招标,竞争性谈判',

    -- 服务范围
    joint_bid_willing TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否愿意联合体投标：0否 1是',

    -- 排除项
    excluded_keywords VARCHAR(256) NOT NULL DEFAULT '' COMMENT '排除关键词，逗号分隔，如：监狱,戒毒所,殡葬',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_region (province, city),
    FULLTEXT INDEX ft_business_scope (business_scope),
    FULLTEXT INDEX ft_qualification_summary (qualification_summary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商画像表（MVP精简版）';

-- ------------------------------------------------------------
-- 供应商可服务地区表（省级）
-- ------------------------------------------------------------
CREATE TABLE supplier_service_regions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    supplier_id BIGINT NOT NULL COMMENT '供应商ID，关联supplier.id',
    region_name VARCHAR(32) NOT NULL DEFAULT '' COMMENT '可服务地区省份名称，如：四川、广东',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_supplier_id (supplier_id),
    INDEX idx_region_name (region_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商可服务地区表（省级）';

-- ------------------------------------------------------------
-- 匹配结果表 match_results
-- ------------------------------------------------------------
CREATE TABLE match_results (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,

    supplier_id BIGINT NOT NULL DEFAULT 0 COMMENT '供应商ID（对应supplier.id）',
    filtered_notices JSON NULL COMMENT '粗筛后的公告',

    -- 第二层：AI精筛结果
    ai_match_score DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT 'AI匹配分数（0-100）',
    ai_match_level VARCHAR(16) NOT NULL DEFAULT '' COMMENT 'AI匹配等级：高(>=80)/中(60-79)/低(<60)/不匹配',
    ai_match_reasons TEXT COMMENT 'AI给出的匹配理由（多行文本）',
    ai_risk_tips TEXT COMMENT 'AI给出的风险提示（多行文本）',
    ai_key_matching_points TEXT COMMENT 'AI提取的关键匹配点（JSON或文本）',
    ai_mismatch_points TEXT COMMENT 'AI提取的不匹配点（JSON或文本）',
    ai_recommendation VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'AI建议：强烈推荐/推荐/谨慎考虑/不推荐',
    ai_raw_response TEXT COMMENT 'AI原始返回内容（用于调试和追溯）',
    ai_call_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT 'AI调用时间',

    -- 第三层：最终排序与输出
    final_score DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT '最终排序分数（目前等于ai_match_score，预留加权计算）',
    final_rank INT NOT NULL DEFAULT 0 COMMENT '该供应商所有匹配中的排名（1=Top1）',
    is_top3 TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否进入Top3推荐：0否 1是',

    -- 推送状态
    push_status TINYINT NOT NULL DEFAULT 0 COMMENT '推送状态：0未推送 1已推送 2推送失败 3用户已读 4用户忽略',
    push_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '推送时间',
    push_channel VARCHAR(32) NOT NULL DEFAULT '' COMMENT '推送渠道：企业微信/短信/邮件/App',
    push_message_id VARCHAR(128) NOT NULL DEFAULT '' COMMENT '企业微信消息ID（用于追踪）',

    -- 用户反馈（用于模型优化）
    user_feedback_score TINYINT NOT NULL DEFAULT 0 COMMENT '用户反馈评分：0未反馈 1-5星',
    user_feedback_comment VARCHAR(512) NOT NULL DEFAULT '' COMMENT '用户反馈文字',
    user_viewed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '用户是否点击查看详情：0否 1是',
    user_favorite TINYINT(1) NOT NULL DEFAULT 0 COMMENT '用户是否收藏：0否 1是',
    user_applied TINYINT(1) NOT NULL DEFAULT 0 COMMENT '用户是否实际投标：0否 1是',
    user_feedback_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '用户反馈时间',

    -- 状态
    status TINYINT NOT NULL DEFAULT 1 COMMENT '记录状态：1有效 2已过期（公告截止） 3已删除',

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 索引
    INDEX idx_supplier_id (supplier_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商-招标公告匹配结果表';


-- ------------------------------------------------------------
-- 任务执行日志表 job_logs
-- ------------------------------------------------------------
CREATE TABLE job_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    job_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '任务名称，如：crawl_list、parse、match、ai_match',
    trigger_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '计划触发时间',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=运行中 1=成功 2=失败',
    record_count BIGINT NOT NULL DEFAULT 0 COMMENT '本次任务处理记录数',
    message TEXT COMMENT '日志消息或异常堆栈',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_job_name (job_name),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定时任务执行日志表';

-- ------------------------------------------------------------
-- 爬虫目标网站配置表 sites
-- ------------------------------------------------------------
CREATE TABLE sites (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,

    platform VARCHAR(64) NOT NULL DEFAULT '' COMMENT '网站名称，如：中国政府采购网',
    part VARCHAR(32) NOT NULL DEFAULT '' COMMENT '栏目代码，如：地方公告',
    action VARCHAR(32) NOT NULL DEFAULT '' COMMENT '执行动作，如：fetch_list,fetch_html',
    crawler VARCHAR(128) NOT NULL DEFAULT '' COMMENT '爬虫类类名，如：CCGPCrawler',
    url VARCHAR(256) NOT NULL DEFAULT '' COMMENT '网站栏目对应的URL',

    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用：0禁用 1启用',
    schedule_type VARCHAR(16) NOT NULL DEFAULT 'interval' COMMENT '调度类型：interval/cron',
    schedule_config JSON COMMENT '调度配置，如：{minutes: 60} 或 {hour: 8, minute: 30}',

    pages INT NOT NULL DEFAULT 1 COMMENT '每次爬取页数',
    delay INT NOT NULL DEFAULT 60 COMMENT '请求间隔（秒）',
    fetch_detail TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否爬取详情页',
    notice_type_filter VARCHAR(32) NOT NULL DEFAULT '' COMMENT '公告类型过滤',

    extra_config JSON COMMENT '额外配置（各爬虫自定义参数）',
    priority INT NOT NULL DEFAULT 0 COMMENT '优先级，数字越大越优先',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_site_part (platform, part),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫目标网站配置表';

-- 默认数据：中国政府采购网
INSERT INTO sites (platform, part, action, crawler, url, enabled, schedule_type, schedule_config, pages, delay, fetch_detail, notice_type_filter, priority)
VALUES
('中国政府采购网', '地方公告', 'fetch_list', 'crawlers.ccgp_crawler.CCGPCrawler', 'https://www.ccgp.gov.cn', 1, 'interval', '{"minutes": 60}', 2, 1, 0, '招标公告', 10),
('中国政府采购网', '中央公告', 'fetch_list', 'crawlers.ccgp_crawler.CCGPCrawler', 'https://www.ccgp.gov.cn', 1, 'interval', '{"minutes": 60}', 2, 1, 0, '招标公告', 10),
('中国政府采购网', '地方公告', 'fetch_html', 'crawlers.ccgp_crawler.CCGPCrawler', 'https://www.ccgp.gov.cn', 1, 'interval', '{"minutes": 60}', 2, 1, 0, '招标公告', 10),
('中国政府采购网', '中央公告', 'fetch_html', 'crawlers.ccgp_crawler.CCGPCrawler', 'https://www.ccgp.gov.cn', 1, 'interval', '{"minutes": 60}', 2, 1, 0, '招标公告', 10),

-- 北京市公共资源交易服务平台（市级，已聚合各区公告）
('北京市公共资源交易服务平台', '工程建设招标公告', 'fetch_list', 'BJGGZYCrawler', 'https://ggzyfw.beijing.gov.cn/jyxxggjtbyqs/', 1, 'interval', '{"minutes": 60}', 3, 1, 0, '招标公告', 10),
('北京市公共资源交易服务平台', '工程建设招标公告', 'fetch_html', 'BJGGZYCrawler', 'https://ggzyfw.beijing.gov.cn/jyxxggjtbyqs/', 1, 'interval', '{"minutes": 60}', 3, 1, 0, '招标公告', 10),
('北京市公共资源交易服务平台', '政府采购招标公告', 'fetch_list', 'BJGGZYCrawler', 'https://ggzyfw.beijing.gov.cn/jyxxcggg/', 1, 'interval', '{"minutes": 60}', 3, 1, 0, '招标公告', 10),
('北京市公共资源交易服务平台', '政府采购招标公告', 'fetch_html', 'BJGGZYCrawler', 'https://ggzyfw.beijing.gov.cn/jyxxcggg/', 1, 'interval', '{"minutes": 60}', 3, 1, 0, '招标公告', 10);


-- ------------------------------------------------------------
-- 人员表: 供应商下的具体人员（企微推送目标）
-- ------------------------------------------------------------
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    supplier_id BIGINT NOT NULL DEFAULT 0 COMMENT '所属供应商ID',

    -- 基础信息
    name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '姓名',
    phone VARCHAR(20) NOT NULL DEFAULT '' COMMENT '手机号',
    email VARCHAR(128) NOT NULL DEFAULT '' COMMENT '邮箱',

    -- 企业微信绑定（客户联系）
    wechat_external_userid VARCHAR(64) NOT NULL DEFAULT '' COMMENT '个人微信在企业微信中的外部联系人ID',
    wechat_follow_user_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '跟进该人员的我方员工企微UserID',
    wechat_bind_time DATETIME DEFAULT NULL COMMENT '企微绑定时间',
    wechat_bind_state VARCHAR(128) NOT NULL DEFAULT '' COMMENT '绑定时的二维码state参数',

    -- 状态
    is_primary TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否主要联系人: 1=是 0=否',
    status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态: 1=正常 0=禁用',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_supplier_id (supplier_id),
    INDEX idx_wechat_external_userid (wechat_external_userid),
    INDEX idx_wechat_follow_user_id (wechat_follow_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商人员表';

-- ------------------------------------------------------------
-- 用户-公告互动表 user_notice_interactions（支撑小程序 Feed 收藏/不感兴趣）
-- ------------------------------------------------------------
CREATE TABLE user_notice_interactions (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id         BIGINT NOT NULL DEFAULT 0 COMMENT '用户ID（users.id）',
    notice_id       BIGINT NOT NULL DEFAULT 0 COMMENT '公告ID（notices.id）',

    is_viewed           TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已浏览: 1=是 0=否',
    is_favorite         TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否收藏: 1=是 0=否',
    is_not_interested   TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否标记不感兴趣: 1=是 0=否',
    is_applied          TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已投标: 1=是 0=否',

    viewed_at       DATETIME DEFAULT NULL COMMENT '浏览时间',
    favorited_at    DATETIME DEFAULT NULL COMMENT '收藏时间',

    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_user_notice (user_id, notice_id),
    INDEX idx_user_favorite (user_id, is_favorite),
    INDEX idx_user_not_interested (user_id, is_not_interested),
    INDEX idx_notice_interactions (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与公告的互动记录';
