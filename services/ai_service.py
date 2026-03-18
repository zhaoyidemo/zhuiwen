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


FIRST_5S_PROMPT = """你是一位资深的短视频内容策划专家，专精于"黄金前5秒"留人策略研究。

我会发送一条抖音视频前5秒的逐秒截帧（第0秒、第1秒、第2秒、第3秒、第4秒、第5秒），请你根据画面内容进行深度分析。

请从以下维度分析：

## 一、开场钩子类型判断
判断这条视频使用了哪种开场钩子（可多选）：
- 悬念钩子：开头抛出一个让人好奇的问题或场景
- 冲突钩子：展示矛盾、对比、反差
- 利益钩子：直接告诉观众"看完你能获得什么"
- 情绪钩子：用强烈的情绪（震惊、搞笑、感动）抓住注意力
- 视觉钩子：用惊艳的画面、特效、运镜吸引眼球
- 人物钩子：有辨识度的人物直接出镜
- 声音钩子：音乐、音效、语气的运用

## 二、逐秒画面拆解
对每一秒的画面内容进行描述和分析：
- 第0秒（首帧）：观众第一眼看到什么？是否足够吸引停留？
- 第1-2秒：信息密度如何？是否建立了期待感？
- 第3-5秒：是否完成了"留人"？观众是否有继续看下去的动力？

## 三、留存策略评分（1-10分）
- 注意力抓取速度（首帧是否有效）
- 信息传递效率（前5秒传达了什么核心信息）
- 情绪曲线设计（情绪变化节奏）
- 视觉表现力（构图、色彩、文字排版）
- 继续观看动力（第5秒时是否让人想看下去）

## 四、可借鉴的关键技巧
列出3-5个具体可复用的技巧，每个技巧给出实操建议。

## 五、优化建议
如果要改进前5秒的留人效果，你有什么具体建议？

请用结构化的方式输出，分析要具体到画面细节，不要泛泛而谈。"""


async def analyze_first_5s(video: dict, frame_data_uris: list[str]) -> dict:
    """用 Claude Vision 分析视频前5秒截帧"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    video_text = _format_video_for_prompt(video)

    # 构建包含截帧图片的消息内容
    content = []
    for i, data_uri in enumerate(frame_data_uris):
        # data:image/jpeg;base64,xxxx → 提取 media_type 和 data
        if data_uri.startswith("data:"):
            header, b64_data = data_uri.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]  # image/jpeg
        else:
            media_type = "image/jpeg"
            b64_data = data_uri

        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64_data},
        })
        content.append({"type": "text", "text": f"第 {i} 秒截帧"})

    content.append({"type": "text", "text": f"\n\n{video_text}\n\n请根据以上截帧和视频数据，进行黄金前5秒分析。"})

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=4096,
            system=FIRST_5S_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"前5秒分析 Claude API 失败: {e}")
        # 带图失败时，尝试纯文本分析
        try:
            fallback_content = [{"type": "text", "text": f"{video_text}\n\n（截帧图片发送失败，请仅根据文本数据分析该视频可能的前5秒策略）"}]
            message = client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=4096,
                system=FIRST_5S_PROMPT,
                messages=[{"role": "user", "content": fallback_content}],
            )
            result_text = message.content[0].text
        except Exception as e2:
            logger.error(f"前5秒纯文本分析也失败: {e2}")
            result_text = f"分析失败：{str(e2)}"

    return {
        "result": result_text,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
