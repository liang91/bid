import os
import sys
import time
from loguru import logger

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log_formatter(record):
    """自定义格式：name:function:line 整体固定宽度."""
    location = f"{record['name']}:{record['function']}:{record['line']}"
    # 整体占 45 字符，左对齐，不足补空格；超长不截断
    record["extra"]["loc"] = f"{location: <45}"
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[loc]} | {message}\n"
        "{exception}"
    )


# 移除 loguru 默认的 stderr 输出器，避免格式不统一
logger.remove()

# 控制台输出（带颜色）
logger.add(
    sys.stderr,
    format=_log_formatter,
    colorize=True,
)

# 文件输出
logger.add(
    os.path.join(project_dir, "log.txt"),
    rotation="1 day",
    retention="7 days",
    encoding="utf-8",
    format=_log_formatter,
)


# 把html保存到本地文件
def save_html(html: str) -> str:
    filename = f"html/{int(time.time() * 1000000)}.html"
    filepath = os.path.join(project_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filename


# 从本地文件读取html内容
def get_html(filename: str) -> str:
    filepath = os.path.join(project_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
