"""抓取网页内容，提取正文文本"""
import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 模拟浏览器请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 需要移除的标签
REMOVE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "iframe", "noscript", "svg", "form"}

# 正文常见容器标签
CONTENT_TAGS = {"article", "main", "section", "div"}


async def fetch_page_text(url: str, max_length: int = 8000) -> str:
    """
    抓取网页 URL，提取正文文本。
    返回清洗后的纯文本，最多 max_length 字符。
    失败时返回空字符串。
    """
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(15.0),
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.info(f"跳过非文本内容: {url} ({content_type})")
                return ""

            html = resp.text

        soup = BeautifulSoup(html, "html.parser")

        # 移除无用标签
        for tag in soup.find_all(REMOVE_TAGS):
            tag.decompose()

        # 尝试找正文容器
        article = soup.find("article") or soup.find("main")
        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            # 降级：取 body 全文
            body = soup.find("body")
            text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

        # 清理：合并连续空行，去掉过短的行（通常是菜单项）
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 5:
                lines.append(line)

        result = "\n".join(lines)

        if len(result) > max_length:
            result = result[:max_length] + "\n\n[内容已截断]"

        logger.info(f"抓取成功: {url} ({len(result)} 字符)")
        return result

    except httpx.TimeoutException:
        logger.warning(f"抓取超时: {url}")
        return ""
    except httpx.HTTPStatusError as e:
        logger.warning(f"抓取HTTP错误: {url} ({e.response.status_code})")
        return ""
    except Exception as e:
        logger.warning(f"抓取失败: {url} ({type(e).__name__}: {e})")
        return ""
