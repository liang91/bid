"""公告信息解析工具.

注意：
- 本模块只包含【通用】文本/时间/金额解析逻辑，不依赖任何平台的 HTML 结构。
- 平台相关的 HTML 提取/清理逻辑（如针对特定 DOM 选择器）应放在各平台爬虫类中。
"""

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# HTML 噪声过滤（保留 HTML 结构，去掉 head/foot/css/js）
# ---------------------------------------------------------------------------
# 说明：此函数较为通用，仅移除标准噪声标签（script/style/nav 等），
# 不依赖特定平台的 DOM 结构。如需平台定制，请在平台爬虫类中重写。

_NOISE_HTML_TAGS = {"head", "script", "style", "nav", "footer", "header", "iframe", "noscript", "aside", "svg",
                    "canvas", "link", "meta"}


def strip_html_noise(html: str) -> str:
    """去掉 HTML 中的 head/foot/css/js 等噪声标签，保留正文 HTML 结构.

    适用于 fetch_html 阶段存储过滤后的详情页 HTML。

    Args:
        html: 原始 HTML 字符串

    Returns:
        过滤后的 HTML 字符串
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # 去掉已知噪声标签及其内容
    for tag in soup.find_all(_NOISE_HTML_TAGS):
        tag.decompose()

    # 返回过滤后的 HTML（优先 body，否则整个文档）
    body = soup.find("body")
    if body:
        return str(body)
    return str(soup)
