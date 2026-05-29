"""定时任务调度包.

使用 APScheduler 管理每日任务流水线：
    爬取 → 解析 → 匹配 → AI精筛 → 推送

启动方式:
    python scheduler/main.py
"""
