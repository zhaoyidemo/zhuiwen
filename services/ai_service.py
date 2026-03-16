import logging
from datetime import datetime

import anthropic

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS = {
    "AI洞察": """你是一位资深的抖音内容分析师和内容策划专家。请对这条视频进行全方位深度分析。

请从以下维度进行分析：

## 一、选题与定位
- 选题定位：属于什么内容类型？切入角度是什么？
- 目标受众：面向什么人群？他们的痛点/需求是什么？
- 情绪价值：视频提供了什么情绪价值（共鸣、好奇、焦虑、治愈等）？

## 二、标题与文案
- 标题/描述拆解：用了哪些钩子、关键词、情绪触发点？
- 标签策略：话题标签的选择是否精准？

## 三、数据解读
- 数据表现解读：收藏率和互动率说明了什么？哪个指标特别突出？
- 互动比例分析：点赞/评论/收藏/转发的比例是否健康？

## 四、评论区洞察
- 用户最关注什么？有哪些高频话题？
- 评论区情绪倾向如何？
- 有哪些有价值的用户反馈？

## 五、可借鉴的方法论
- 这条视频有哪些可以借鉴的具体技巧？
- 如何基于这个选题延伸出系列内容？

请用结构化的方式输出，每个发现都要有数据或评论支撑。""",
}


def _format_video_for_prompt(video: dict) -> str:
    """将单条视频数据格式化为 prompt 文本"""
    lines = [
        f"## 视频信息",
        f"- 描述：{video.get('desc', 'N/A')}",
        f"- 发布时间：{video.get('create_time', 'N/A')}",
        f"- 时长：{video.get('duration', 0)}秒",
        f"- 作者：{video.get('author_nickname', 'N/A')} (@{video.get('author_unique_id', '')})",
        f"- 话题标签：{video.get('tags', 'N/A')}",
        f"- 内容分类：{video.get('video_tags', 'N/A')}",
        f"",
        f"## 数据表现",
        f"- 播放量：{video.get('play_count', 0):,}",
        f"- 点赞数：{video.get('digg_count', 0):,}",
        f"- 评论数：{video.get('comment_count', 0):,}",
        f"- 收藏数：{video.get('collect_count', 0):,}",
        f"- 转发数：{video.get('share_count', 0):,}",
    ]

    collect_rate = video.get('collect_rate', 0)
    engagement_rate = video.get('engagement_rate', 0)
    if isinstance(collect_rate, (int, float)) and collect_rate > 0:
        lines.append(f"- 收藏率：{collect_rate * 100:.2f}%")
    if isinstance(engagement_rate, (int, float)) and engagement_rate > 0:
        lines.append(f"- 互动率：{engagement_rate * 100:.2f}%")

    return "\n".join(lines)


def _format_comments_for_prompt(comments: list) -> str:
    """将评论数据格式化为 prompt 文本"""
    if not comments:
        return ""
    lines = ["\n## 评论区内容（按点赞排序）"]
    sorted_comments = sorted(comments, key=lambda c: c.get("digg_count", 0), reverse=True)
    for i, c in enumerate(sorted_comments[:30], 1):
        digg = c.get("digg_count", 0)
        reply = c.get("reply_count", 0)
        content = c.get("content", "")
        nickname = c.get("user_nickname", "匿名")
        lines.append(f"{i}. [{nickname}] (❤{digg}, 回复{reply}) {content}")
    return "\n".join(lines)


async def analyze_single_video(
    video: dict,
    comments: list = None,
    prompt: str = None,
    include_cover: bool = True,
) -> dict:
    """用 Claude Opus 分析单条视频"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = prompt or DEFAULT_PROMPTS.get("AI洞察", list(DEFAULT_PROMPTS.values())[0])
    video_text = _format_video_for_prompt(video)
    comments_text = _format_comments_for_prompt(comments or [])

    # 判断封面图是否可用（Claude Vision 支持 jpeg/png/gif/webp）
    cover_url = video.get("cover_url", "")
    use_cover = False
    if include_cover and cover_url:
        lower = cover_url.lower().split("?")[0]
        if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            use_cover = True

    def _build_content(with_image: bool) -> list:
        content = []
        if with_image and cover_url:
            content.append({"type": "image", "source": {"type": "url", "url": cover_url}})
            content.append({"type": "text", "text": f"以上是视频封面图。\n\n{video_text}{comments_text}\n\n请根据以上数据和封面进行分析。"})
        else:
            content.append({"type": "text", "text": f"{video_text}{comments_text}\n\n请根据以上数据进行分析。"})
        return content

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": _build_content(use_cover)}],
        )
        result_text = message.content[0].text
    except Exception as e:
        # 如果带图失败，不带图重试
        if use_cover:
            logger.warning(f"带封面分析失败，不带图重试: {e}")
            try:
                message = client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": _build_content(False)}],
                )
                result_text = message.content[0].text
            except Exception as e2:
                logger.error(f"Claude API 调用失败: {e2}")
                result_text = f"分析失败：{str(e2)}"
        else:
            logger.error(f"Claude API 调用失败: {e}")
            result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": system_prompt,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
