#!/usr/bin/env python3
"""项目主入口脚本.

支持功能：
1. 爬虫：分步骤爬取政府采购网公告
2. 补算：为存量数据计算 Embedding 向量
3. 匹配：运行匹配引擎（粗筛 + 语义排序）
4. 调度器：启动后台定时任务
"""
import signal
import sys
import time

from loguru import logger
from services import ScheduleService

# ---------------------------------------------------------------------------
# 调度器模式
# ---------------------------------------------------------------------------
def run_scheduler():
    ScheduleService.start()
    def shutdown_handler(signum, frame):
        logger.info("[Scheduler] 收到退出信号，正在关闭...")
        ScheduleService.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("[Scheduler] 调度器运行中，按 Ctrl+C 停止")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
