import time

# 把html保存到本地文件
def save_html(html: str) -> str:
    filename = f"html/{int(time.time() * 1000000)}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename

# 从本地文件读取html内容
def get_html(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
