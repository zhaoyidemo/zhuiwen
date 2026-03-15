import logging
from datetime import datetime

import anthropic

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS = {
    "爆款分析": """你是一位资深的抖音内容分析师。请对这条视频进行深度爆款分析。

重点关注：
1. 选题策略：为什么这个选题能吸引用户？目标受众是谁？
2. 标题/描述拆解：用了哪些钩子、关键词、情绪触发点？
3. 数据表现解读：收藏率和互动率说明了什么？哪个指标特别突出？
4. 评论区洞察：用户最关注什么？有哪些高频话题？情绪倾向如何？
5. 可复用的方法论：这条视频有哪些可以借鉴的具体技巧？

请用结构化的方式输出，每个发现都要有数据或评论支撑。""",

    "选题分析": """你是一位资深的内容策划专家。请分析这条视频的选题策略。

重点关注：
1. 选题定位：属于什么内容类型？切入角度是什么？
2. 目标受众：面向什么人群？他们的痛点/需求是什么？
3. 情绪价值：视频提供了什么情绪价值（共鸣、好奇、焦虑、治愈等）？
4. 差异化：相比同类内容，这个选题有什么独特之处？
5. 选题可复制性：如何基于这个选题延伸出系列内容？

请给出具体可执行的建议。""",

    "封面分析": """你是一位视觉内容专家。请分析这条视频的封面图。

重点关注：
1. 视觉构图：画面布局、色彩运用、主体突出度
2. 文字信息：封面上的文字是否清晰、是否有吸引力
3. 情绪表达：封面传达了什么情绪？是否能引发点击欲望？
4. 与内容匹配度：封面是否准确反映了视频内容？
5. 改进建议：如何优化封面提升点击率？

请结合封面图片进行具体分析。""",
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

    system_prompt = prompt or DEFAULT_PROMPTS["爆款分析"]
    video_text = _format_video_for_prompt(video)
    comments_text = _format_comments_for_prompt(comments or [])

    user_content = []

    # 封面图（Claude Vision）
    cover_url = video.get("cover_url", "")
    if include_cover and cover_url:
        user_content.append({
            "type": "image",
            "source": {"type": "url", "url": cover_url},
        })
        user_content.append({
            "type": "text",
            "text": f"以上是视频封面图。\n\n{video_text}{comments_text}\n\n请根据以上数据和封面进行分析。",
        })
    else:
        user_content.append({
            "type": "text",
            "text": f"{video_text}{comments_text}\n\n请根据以上数据进行分析。",
        })

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"Claude API 调用失败: {e}")
        result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": system_prompt,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
