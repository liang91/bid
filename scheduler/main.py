#!/usr/bin/env python3
"""定时调度器启动入口.

启动后会在后台运行，按预设时间自动执行任务流水线。

用法:
    # 前台启动（调试用，Ctrl+C 停止）
    python scheduler/main.py

    # 后台启动（生产环境）
    nohup python scheduler/main.py > scheduler.log 2>&1 &
"""
import signal
import sys
import time

from loguru import logger

from scheduler.job_manager import JobManager


def main():
    manager = JobManager()
    manager.start()

    # 注册信号处理，保证优雅退出
    def shutdown_handler(signum, frame):
        logger.info("[Scheduler] 收到退出信号，正在关闭...")
        manager.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("[Scheduler] 调度器运行中，按 Ctrl+C 停止")
    # 阻塞主线程，保持进程存活
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
