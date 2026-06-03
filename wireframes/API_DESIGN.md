# 公装招标推荐小程序 — 接口与数据结构梳理

> 基于 wireframes（`index.html` / `detail.html` / `favorites.html` / `profile.html`）的页面功能，推导所需的数据模型与 API 设计。

---

## 一、页面功能 → 接口映射

| 页面 | 核心功能 | 所需接口 |
|------|---------|---------|
| **首页 Feed** | 沉浸式滑动推荐列表、匹配度展示、不感兴趣、收藏、进入详情 | `GET /feed` `POST /notices/{id}/not-interested` `POST /notices/{id}/favorite` |
| **招标详情** | 完整信息展示、收藏切换、联系招标方 | `GET /notices/{id}` `POST /notices/{id}/favorite` |
| **我的关注** | 收藏列表、取消关注、查看详情 | `GET /users/{id}/favorites` `POST /notices/{id}/favorite` |
| **偏好设置** | 资质/业务类型/金额/地区编辑与保存 | `GET /suppliers/{id}/settings` `PUT /suppliers/{id}/settings` |

---

## 二、数据模型调整

### 2.1 新增表：`user_notice_interactions`（用户-公告互动表）

**为什么需要**：现有 `match_results` 表的用户交互字段（`user_favorite` / `user_viewed` 等）是挂在 **match 记录**（按天聚合）上的，粒度太粗，无法表达"用户对某条具体 notice 收藏/不感兴趣"。

```sql
CREATE TABLE user_notice_interactions (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id         BIGINT NOT NULL COMMENT '用户ID（users.id）',
    notice_id       BIGINT NOT NULL COMMENT '公告ID（notices.id）',

    -- 互动状态（互斥或共存）
    is_viewed           TINYINT(1) DEFAULT 0 COMMENT '是否已浏览',
    is_favorite         TINYINT(1) DEFAULT 0 COMMENT '是否收藏',
    is_not_interested   TINYINT(1) DEFAULT 0 COMMENT '是否标记不感兴趣',
    is_applied          TINYINT(1) DEFAULT 0 COMMENT '是否已投标',

    -- 时间戳
    viewed_at       DATETIME DEFAULT NULL,
    favorited_at    DATETIME DEFAULT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_user_notice (user_id, notice_id),
    INDEX idx_user_favorite (user_id, is_favorite),
    INDEX idx_user_not_interested (user_id, is_not_interested),
    INDEX idx_notice_interactions (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与公告的互动记录';
```

> **对现有 `match_results` 的处理**：将其上的 `user_favorite` / `user_viewed` / `user_applied` / `user_feedback_score` / `user_feedback_comment` 逐步废弃，迁移到本表。

---

### 2.2 新增表：`match_notice_details`（AI 匹配明细表）

**为什么需要**：现有 `match_results` 的 `filtered_notices` JSON 只保存了 embedding 相似度分数；AI 精筛结果只保存了**最佳匹配**的分数和理由（`ai_match_score` / `ai_match_reasons` 等）。Feed 卡片需要**每条 notice 独立的 AI 分数和匹配等级**。

```sql
CREATE TABLE match_notice_details (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    match_id            BIGINT NOT NULL COMMENT '关联 match_results.id',
    notice_id           BIGINT NOT NULL COMMENT '公告ID',

    -- 阶段一：embedding 分数
    embed_score         DECIMAL(5,4) DEFAULT 0 COMMENT '语义相似度（0-1）',

    -- 阶段二：AI 精筛结果
    ai_score            DECIMAL(5,2) DEFAULT 0 COMMENT 'AI匹配分数（0-100）',
    ai_level            VARCHAR(16) DEFAULT '' COMMENT '高/中/低',
    ai_reasons          TEXT COMMENT '匹配理由',
    ai_risk_tips        TEXT COMMENT '风险提示',
    ai_matching_points  TEXT COMMENT '关键匹配点',
    ai_mismatch_points  TEXT COMMENT '不匹配点',
    ai_recommendation   VARCHAR(64) DEFAULT '' COMMENT '推荐建议',

    -- 最终排序
    final_score         DECIMAL(5,2) DEFAULT 0 COMMENT '最终分数（目前=ai_score）',
    final_rank          INT DEFAULT 0 COMMENT '该批次中的排名',
    is_top3             TINYINT(1) DEFAULT 0 COMMENT '是否进入Top3',

    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_match_id (match_id),
    INDEX idx_notice_id (notice_id),
    INDEX idx_final_score (final_score),
    UNIQUE KEY uk_match_notice (match_id, notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI匹配明细：每条match下各notice的评分';
```

> **MVP 简化方案**：如果初期公告量小，可暂时不建此表，直接把 AI 精筛的每条 notice 分数写回 `match_results.filtered_notices` JSON 中（扩展 `MatchNoticeScore` 结构，增加 `ai_score` / `ai_level` 字段）。当需要按分数索引查询时再拆分为独立表。

---

### 2.3 `supplier` 表字段映射（设置页 `profile.html`）

| 前端设置项 | 对应字段 | 说明 |
|-----------|---------|------|
| 🛡️ 你能调用的资质有哪些？ | `qualification_summary` (VARCHAR) | 逗号分隔的资质名称列表，如 `"装修工程一级,消防设施工程,安全生产许可证"`，用于快速匹配 |
| 🔨 擅长业务类型 | `business_scope` (TEXT) | 逗号分隔的业务标签，如 `"办公室,餐饮,酒店"` |
| 💰 项目金额范围 | `min_budget` / `max_budget` (DECIMAL) | 已有字段 |
| 📍 关注地区 | `service_regions` (JSON) | 已有字段，如 `["北京","天津"]` |

> **关于 `qualifications` JSON 字段**：现有结构 `[{name, cert_no, valid_until}]` 更适合记录**自有实体资质证书**。前端的"你能调用的资质"语义更宽（含挂靠），所以用 `qualification_summary` 文本字段承载勾选列表即可，不必强套 `qualifications` JSON 结构。

---

## 三、API 接口设计

### 3.1 首页 Feed

#### `GET /api/v1/feed`

获取推荐招标列表（按匹配度倒序）。

**请求参数**：
```json
{
  "user_id": 10001,
  "limit": 10,
  "cursor": "eyJpZCI6MTIzNH0="   // 分页游标，可选
}
```

**响应示例**：
```json
{
  "data": [
    {
      "notice_id": 1234,
      "match_score": 95,
      "match_level": "高",           // ≥90 显示 🔥，<90 显示 💡
      "title": "某科技互联网公司总部办公楼装修项目",
      "tags": ["办公空间", "室内装修", "二级资质"],
      "is_urgent": true,              // 截标 < 7 天
      "amount": {
        "label": "预估金额",
        "value": 3800000,
        "display": "¥380万"
      },
      "info_grid": {
        "location": "朝阳区望京",
        "area": "4,200㎡",
        "duration": "90日历天",
        "deposit": { "value": "¥10万", "alert": true }
      },
      "timeline": {
        "register_deadline": "06-10",
        "bid_deadline": { "date": "06-15", "alert": true },
        "open_date": "06-20"
      },
      "qualifications": [
        "建筑装修装饰工程专业承包二级及以上",
        "具备有效的安全生产许可证",
        "项目经理须具备二级建造师资格"
      ],
      "description": "位于望京SOHO附近的新总部办公楼...",
      "purchaser": {
        "name": "北京某科技有限公司",
        "avatar_text": "科",
        "sub": "互联网 · 500-1000人 · 成立8年"
      },
      "is_favorite": false
    }
  ],
  "next_cursor": "eyJpZCI6NTY3OH0=",
  "has_more": true
}
```

**后端逻辑**：
1. 根据 `user_id` 找到关联的 `supplier_id`
2. 查询 `service_regions`、`budget` 等硬规则粗筛出候选 notice（`bid_deadline > now()`）
3. 排除 `user_notice_interactions.is_not_interested = 1` 的 notice
4. 从 `match_notice_details`（或 `filtered_notices` JSON）取 `final_score`，按分数倒序
5. 查询 `user_notice_interactions.is_favorite` 标记收藏状态
6. 组装 `is_urgent`（截标日期距今天数 < 7）等前端展示字段

---

#### `POST /api/v1/notices/{notice_id}/not-interested`

标记不感兴趣（该 notice 不再出现在 Feed 中）。

**请求体**：
```json
{ "user_id": 10001 }
```

**响应**：`{ "success": true }`

**后端逻辑**：
- INSERT OR UPDATE `user_notice_interactions` SET `is_not_interested = 1`

---

#### `POST /api/v1/notices/{notice_id}/favorite`

收藏 / 取消收藏。

**请求体**：
```json
{
  "user_id": 10001,
  "action": "add"    // "add" 或 "remove"
}
```

**响应**：`{ "success": true, "is_favorite": true }`

---

### 3.2 招标详情

#### `GET /api/v1/notices/{notice_id}`

**请求参数**：`?user_id=10001`（可选，用于返回 `is_favorite`）

**响应示例**：
```json
{
  "notice_id": 1234,
  "title": "某科技互联网公司总部办公楼装修项目",
  "tags": ["办公空间", "室内装修"],
  "amount": { "value": 3800000, "display": "¥380万" },
  "hero_meta": {
    "location": "北京市朝阳区",
    "bid_deadline": { "date": "2026-06-15", "display": "⏰ 2026-06-15（3天后）", "alert": true }
  },
  "overview": {
    "project_type": "办公空间 · 室内装修",
    "area": "约 4,200 平方米",
    "duration": "90日历天",
    "method": "公开招标",
    "deposit": "¥10万元"
  },
  "qualifications": [
    "建筑装修装饰工程专业承包二级及以上资质",
    "具备有效的安全生产许可证",
    "近三年内完成过类似规模办公装修项目",
    "项目经理须具备建筑工程专业二级建造师资格"
  ],
  "description": "本项目为某科技互联网公司位于朝阳区望京SOHO附近的新总部办公楼装修工程...",
  "purchaser": {
    "name": "北京某科技有限公司",
    "sub": "互联网 / 500-1000人 / 成立8年",
    "avatar_text": "科"
  },
  "contacts": {
    "purchaser_contact_person": "张经理",
    "purchaser_contact_phone": "010-12345678",
    "agency_contact_person": "李代理",
    "agency_contact_phone": "010-87654321"
  },
  "attachments": [
    { "name": "招标文件.pdf", "url": "..." },
    { "name": "工程量清单.xlsx", "url": "..." }
  ],
  "is_favorite": false
}
```

---

### 3.3 我的关注

#### `GET /api/v1/users/{user_id}/favorites`

**响应示例**：
```json
{
  "total": 3,
  "data": [
    {
      "notice_id": 1234,
      "title": "某科技互联网公司总部办公楼装修项目",
      "amount_display": "¥380万",
      "meta": {
        "location": "北京 · 朝阳区",
        "bid_deadline": "截标 06-15",
        "area": "4,200㎡"
      },
      "tags": ["办公空间", "二级资质", "⚠️ 仅剩3天"]
    }
  ]
}
```

**后端逻辑**：
- JOIN `user_notice_interactions`（`is_favorite = 1`）+ `notices`
- 按 `favorited_at` 倒序

---

### 3.4 偏好设置

#### `GET /api/v1/suppliers/{supplier_id}/settings`

**响应示例**：
```json
{
  "callable_qualifications": ["装修工程一级", "装修工程二级", "安全生产许可证", "建造师"],
  "business_types": ["办公室", "餐饮"],
  "amount_range": {
    "min": 500000,
    "max": 5000000,
    "display": "50万 - 500万"
  },
  "service_regions": ["北京", "天津"]
}
```

> 注：`callable_qualifications` / `business_types` 在前端渲染为**多选标签**，需要有候选值列表。可另提供一个字典接口 `GET /api/v1/dict` 返回所有可选标签。

---

#### `PUT /api/v1/suppliers/{supplier_id}/settings`

**请求体**：
```json
{
  "callable_qualifications": ["装修工程一级", "消防设施工程", "安全生产许可证"],
  "business_types": ["办公室", "餐饮", "酒店"],
  "min_budget": 500000,
  "max_budget": 5000000,
  "service_regions": ["北京", "天津", "河北"]
}
```

**后端逻辑**：
1. 更新 `supplier` 表对应字段
2. 触发 `update_profile_embedding`（因为画像变了，需要重新生成 Embedding）
3. 可选：触发一次即时匹配重算

---

## 四、字典接口（支撑设置页标签渲染）

#### `GET /api/v1/dict`

返回所有前端需要的枚举值。

**响应示例**：
```json
{
  "qualifications": [
    { "code": "DECORATION_L1", "name": "装修工程一级" },
    { "code": "DECORATION_L2", "name": "装修工程二级" },
    { "code": "SAFETY_LICENSE", "name": "安全生产许可证" },
    { "code": "FIRE_PROTECTION", "name": "消防设施工程" },
    { "code": "MECHATRONICS", "name": "机电安装工程" },
    { "code": "INTELLIGENCE", "name": "电子与智能化" },
    { "code": "CONSTRUCTOR", "name": "建造师" },
    { "code": "CURTAIN_WALL", "name": "建筑幕墙" },
    { "code": "STEEL_STRUCTURE", "name": "钢结构" }
  ],
  "business_types": [
    { "code": "OFFICE", "name": "办公室" },
    { "code": "RESTAURANT", "name": "餐饮" },
    { "code": "HOTEL", "name": "酒店" },
    { "code": "COMMERCIAL", "name": "商业空间" },
    { "code": "HOSPITAL", "name": "医院" },
    { "code": "SCHOOL", "name": "学校" },
    { "code": "FACTORY", "name": "厂房" },
    { "code": "EXHIBITION", "name": "展厅" }
  ],
  "regions": [
    { "code": "BEIJING", "name": "北京" },
    { "code": "TIANJIN", "name": "天津" },
    { "code": "HEBEI", "name": "河北" },
    { "code": "SHANDONG", "name": "山东" },
    { "code": "SHANXI", "name": "山西" },
    { "code": "NEIMENGGU", "name": "内蒙古" }
  ]
}
```

---

## 五、关键业务逻辑说明

### 5.1 Feed 数据流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户打开    │────→│  硬规则粗筛  │────→│  排除不感兴趣 │────→│  按匹配分数  │
│   首页      │     │(地区/预算/   │     │              │     │   排序返回   │
│             │     │  截标时间)   │     │              │     │              │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           ↑
                    ┌─────────────┐
                    │ match_notice │
                    │  _details    │  ← AI精筛分数
                    └─────────────┘
```

**去重与分页**：Feed 需要支持分页。考虑到用户可能"不感兴趣"或收藏后希望看到新内容，建议用 `notice_id < cursor_id` 的方式分页，而非固定 OFFSET。

### 5.2 匹配分数来源

| 分数来源 | 字段 | 说明 |
|---------|------|------|
| Embedding 相似度 | `embed_score` (0-1) | 供应商画像 vs 公告供应商画像的语义相似度 |
| AI 匹配分数 | `ai_score` (0-100) | LLM 根据资质、地区、预算、业务类型等维度评估 |
| 最终展示分 | `final_score` | 目前等于 `ai_score`，后续可加权融合 `embed_score` |

**前端展示规则**：
- `final_score >= 90` → 🔥 红色徽章
- `final_score < 90` → 💡 蓝色徽章

### 5.3 不感兴趣的处理

- 写入 `user_notice_interactions.is_not_interested = 1`
- Feed 查询时 `WHERE is_not_interested != 1`
- 若用户误点，无"撤销不感兴趣"入口（MVP 简化，后续可在设置中加"管理屏蔽列表"）

### 5.4 设置变更后的匹配重算

用户保存设置后，供应商画像（`service_regions`、`qualification_summary`、`business_scope`、`min_budget`、`max_budget`）发生变化：

1. **立即**：更新 `supplier` 表，重新生成 `profile_embedding`
2. **异步**：触发一次匹配任务（复用现有的 `SupplierService.filtered_notices` → `ai_match` 流程），生成新的 `match_notice_details`
3. **用户感知**：下次进入 Feed 时，看到的是基于新画像的推荐结果

> 注意：如果用户**减少**了资质或地区，之前高分的 notice 可能消失；如果**增加**了，可能看到新的匹配项。这是预期行为。

### 5.5 与现有企微推送的衔接

现有 `PushService` 走的是"企微员工确认后发送"模式，推送的是 **Top1 最佳匹配**。小程序 Feed 是用户主动浏览的**完整候选列表**。

- 推送时机：每天定时跑完匹配任务后，对 `is_top3 = 1` 且未推送的记录创建企微群发素材
- 推送内容：卡片标题含匹配等级 + 公告标题，点击跳转小程序详情页（或 H5 详情页）
- 小程序 Feed 中已推送的 notice 可以显示"已推送"标记，避免重复打扰感

---

## 六、MVP 阶段最小化实现建议

如果希望尽快跑通小程序原型，可按以下优先级裁剪：

| 优先级 | 内容 | 说明 |
|-------|------|------|
| P0 | `user_notice_interactions` 表 + Feed/收藏/不感兴趣接口 | 支撑首页和关注页核心体验 |
| P0 | `GET/PUT /settings` 接口 | 支撑设置页 |
| P1 | `match_notice_details` 表 | 先用 `filtered_notices` JSON 的 `score` 字段代替 AI 分数，后续再拆表 |
| P1 | `GET /dict` 接口 | 资质/业务类型/地区的候选值可以前端硬编码，后续再接口化 |
| P2 | 联系招标方 | detail.html 的"联系招标方"可直接展示电话，无需额外接口 |

---
