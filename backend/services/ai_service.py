import logging
import uuid
from datetime import datetime

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)


def _format_videos_for_prompt(videos: list[dict]) -> str:
    """将视频数据格式化为 prompt 文本"""
    lines = []
    for i, v in enumerate(videos, 1):
        lines.append(f"### 视频 {i}")
        lines.append(f"- 描述：{v.get('desc', 'N/A')}")
        lines.append(f"- 发布时间：{v.get('create_time', 'N/A')}")
        lines.append(f"- 播放量：{v.get('play_count', 0):,}")
        lines.append(f"- 点赞数：{v.get('digg_count', 0):,}")
        lines.append(f"- 评论数：{v.get('comment_count', 0):,}")
        lines.append(f"- 收藏数：{v.get('collect_count', 0):,}")
        lines.append(f"- 转发数：{v.get('share_count', 0):,}")
        collect_rate = v.get('collect_rate', 0)
        if isinstance(collect_rate, (int, float)):
            lines.append(f"- 收藏率：{collect_rate:.2f}%")
        lines.append(f"- 标签：{v.get('tags', 'N/A')}")
        lines.append(f"- 时长：{v.get('duration', 0)}秒")
        lines.append(f"- 是否共创：{'是' if v.get('is_co_creation') else '否'}")
        lines.append("")
    return "\n".join(lines)


ANALYSIS_PROMPTS = {
    "爆款分析": """你是一位资深的抖音内容分析师。请分析以下视频数据，找出爆款规律。

重点关注：
1. 收藏率异常高的视频有什么共同特征（标题关键词、时长、发布时间等）
2. 爆款视频的标题/描述模式
3. 高互动视频的话题标签使用策略
4. 发布时间与数据表现的关系
5. 可借鉴的内容方向建议

请用结构化的方式输出分析结论，每个发现都要有数据支撑。""",

    "竞品对比": """你是一位资深的抖音竞品分析师。请对比分析以下竞品账号的视频数据。

重点关注：
1. 各账号的内容定位差异
2. 发布频率和时间策略对比
3. 平均收藏率、爆款率对比
4. 共创使用率对比
5. 各自的优势内容方向
6. 值得借鉴的策略

请用表格+文字的方式输出对比结论。""",

    "文案改写": """你是一位擅长跨平台内容适配的文案专家。请基于以下抖音视频描述，改写为适合其他平台的版本。

请分别生成：
1. 小红书版本（加emoji、分段、强调体验感）
2. B站版本（加入B站特色语言风格）
3. 微信视频号版本（更正式、适合微信生态传播）

每个版本都要保留原始内容的核心价值点。""",
}


async def analyze_videos(
    videos: list[dict],
    analysis_type: str = "爆款分析",
    custom_prompt: str = None,
) -> dict:
    """调用 Anthropic API 分析视频数据"""
    if not settings.ANTHROPIC_API_KEY:
        return {
            "analysis_id": str(uuid.uuid4()),
            "analysis_type": analysis_type,
            "input_description": f"分析了 {len(videos)} 条视频",
            "result": "错误：ANTHROPIC_API_KEY 未配置",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    videos_text = _format_videos_for_prompt(videos)
    system_prompt = custom_prompt or ANALYSIS_PROMPTS.get(analysis_type, ANALYSIS_PROMPTS["爆款分析"])

    user_message = f"以下是需要分析的视频数据：\n\n{videos_text}"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API 调用失败: {e}")
        result_text = f"分析失败：{str(e)}"

    return {
        "analysis_id": str(uuid.uuid4()),
        "analysis_type": analysis_type,
        "input_description": f"分析了 {len(videos)} 条视频",
        "result": result_text,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
