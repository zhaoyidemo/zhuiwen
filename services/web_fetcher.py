"""抓取网页内容，提取正文文本"""
import re
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


async def fetch_page_text(url: str, max_length: int = 15000, retry: bool = True) -> str:
    """
    抓取网页 URL，提取正文文本。
    返回清洗后的纯文本，最多 max_length 字符。
    失败时自动重试一次，最终失败返回空字符串。
    """
    for attempt in range(2 if retry else 1):
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(20.0),
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

            # 微信公众号文章特殊处理
            if "mp.weixin.qq.com" in url:
                js_content = soup.find(id="js_content")
                if js_content:
                    text = js_content.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)
            else:
                # 通用：尝试找正文容器
                article = soup.find("article") or soup.find("main")
                if article:
                    text = article.get_text(separator="\n", strip=True)
                else:
                    body = soup.find("body")
                    text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

            # 清理：去掉过短的行（通常是菜单项）
            lines = []
            for line in text.split("\n"):
                line = line.strip()
                if len(line) > 5:
                    lines.append(line)

            result = "\n".join(lines)

            if len(result) > max_length:
                result = result[:max_length] + "\n\n[内容已截断]"

            # 内容太短（<50字）视为抓取失败
            if len(result) < 50:
                logger.warning(f"抓取内容过短({len(result)}字): {url}")
                if attempt == 0 and retry:
                    continue
                return ""

            logger.info(f"抓取成功: {url} ({len(result)} 字符)")
            return result

        except httpx.TimeoutException:
            logger.warning(f"抓取超时(第{attempt+1}次): {url}")
            if attempt == 0 and retry:
                continue
        except httpx.HTTPStatusError as e:
            logger.warning(f"抓取HTTP错误: {url} ({e.response.status_code})")
            return ""  # HTTP 错误不重试
        except Exception as e:
            logger.warning(f"抓取失败(第{attempt+1}次): {url} ({type(e).__name__}: {e})")
            if attempt == 0 and retry:
                continue

    return ""


def extract_urls_from_text(text: str) -> list[str]:
    """从文本中提取所有 URL（用于引用链追踪）"""
    urls = re.findall(r'https?://[^\s\)）\]」\u201d\u201c<>]+', text)
    seen = set()
    unique = []
    for u in urls:
        u = u.rstrip('.,;:\'\"')
        if u not in seen and len(u) > 20:
            seen.add(u)
            unique.append(u)
    return unique
