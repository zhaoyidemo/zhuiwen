import logging
from datetime import datetime

import anthropic

from config import settings

logger = logging.getLogger(__name__)

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

    "前5秒分析": FIRST_5S_PROMPT,

    "嘉宾搜索策略": """搜索此人接受过的采访和访谈，覆盖以下类型：
- 文字采访稿、深度对话、专访
- 视频访谈、播客节目
- 演讲、公开发言、论坛圆桌
- 新闻报道中的引述和观点

请用多个不同的搜索关键词组合来搜索，确保覆盖面足够广。注意区分此人作为受访者的内容和其他同名者的内容。""",

    "采访策划方案": """你是「继续追问」节目的总编导兼首席研究员。「继续追问」是一档对标 Lex Fridman Podcast 的中文长视频深度访谈播客（60-180分钟）。

请根据嘉宾的全部采访素材，先快速研究再直接输出采访策划方案。

核心原则：不问别人问过的问题，专攻别人没挖到的深度。

# 第一部分：嘉宾速写

## 人物概览
- 一段话概括此人（身份、核心标签、公众认知）

## 金句库
- 从素材原文中提取5-8句最有价值的直接引语，每句标注出处

## 被问烂了的问题
- 列出各采访中被反复问到的话题（标注出现次数），这些必须避开或换角度

## 矛盾与未挖掘方向
- 此人在不同场合说过矛盾的话？（附原文出处）
- 采访者没有跟进但值得深挖的话题？

# 第二部分：采访策划

## 一、采访定位
- 这期节目的核心命题是什么？（一句话）
- 和此人之前的采访相比，我们的差异化在哪？

## 二、选题方向（3-5个）
每个选题：
- **话题**：一句话概括
- **为什么别人没问好**：分析之前采访的不足
- **我们的切入角度**：如何问出新东西
- **预期爆点**：哪些观点可能引发讨论

## 三、50个值得追问的问题

请设计50个高质量问题，按以下7个板块结构化排列。每个问题附一行「→ 追问方向」提示。

### A. 破冰与个人故事（7题）
用个人经历切入，打开嘉宾，让观众觉得"这个人有意思"。
- 关注人生转折点、童年影响、非公众认知的个人面
- 每题格式：
  **Q1.** [问题]
  → 追问方向：[如果嘉宾回答触发了什么信号，往哪里追]

### B. 职业经历深挖（8题）
挖细节、找决策背后的真实动机，不要表面叙事。
- 聚焦关键决策、失败经历、违背常识的选择
- 追问"当时真正在想什么""如果重来会怎么选"

### C. 核心观点追问（10题）
主战场。基于素材中此人的核心主张，追问观点的边界、矛盾和演变。
- 直接引用此人说过的原话来提问
- 设计"你说过X，但Y情况下这还成立吗"式的追问

### D. 行业洞察与趋势（7题）
借嘉宾的专业视角看大趋势，让观众获得认知增量。
- 关注此人最有发言权的领域
- 追问预判和赌注："你觉得X会怎样""你在赌什么"

### E. 争议与挑战（7题）
进入深水区。直面争议、质疑、外界批评。
- 语气要尊重但不回避
- 准备好嘉宾可能的回避策略，设计迂回追问

### F. 人生哲学与价值观（7题）
Lex Fridman 式的灵魂拷问。超越专业身份，触及人性层面。
- "什么让你害怕""你改变过最重要的一个观念是什么"
- 追问方向要能引出真实的、未经包装的回答

### G. 快问快答与开放题（4题）
收尾、制造传播点。轻松但有信息量。
- 适合剪成短视频的问题
- "给20岁的自己一句话""推荐一本改变你的书"

## 四、追问武器库
- 从"矛盾点"设计3-5个追问弹药
- 格式：「你在[某次采访]中说过[原话]，但[另一场合]又说[原话]，能解释一下吗？」

## 五、节奏设计
- 预估总时长和每个板块的时间分配
- 标注哪些问题/板块最可能产生适合短视频二创的片段

## 六、风险预案
- 可能的敏感话题及应对方式
- 嘉宾可能的回避策略及破解方式

重要规则：
- 只引用素材原文中明确存在的信息，不要用你自己的知识补充
- 每个观点、引语必须标注来源素材编号（如「资料3」）
- 如果某条信息只出现在标注为"未验证"的素材中，请注明"[未验证]"
- 不要编造嘉宾没说过的话或没做过的事
- 50个问题必须足量，不要偷工减料

请让每个问题都有明确的"追问路径"，这是「继续追问」的核心价值。""",
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


async def analyze_first_5s(video: dict, frame_data_uris: list[str], custom_prompt: str = "") -> dict:
    """用 Claude Vision 分析视频前5秒截帧"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = custom_prompt or FIRST_5S_PROMPT
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
            system=system_prompt,
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
                system=system_prompt,
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


def _parse_search_results(text: str) -> list[dict]:
    """从 Claude 文本回复中解析采访记录（标题+链接+摘要）"""
    import re

    results = []
    sections = re.split(r'##\s*采访\s*\d+[：:]\s*', text)
    for section in sections[1:]:
        lines = section.strip().split('\n')
        title = lines[0].strip() if lines else ""
        url = ""
        snippet = ""
        for line in lines:
            url_match = re.search(r'https?://[^\s\)）\]」]+', line)
            if url_match and not url:
                url = url_match.group(0).rstrip('.,;:')
            if '摘要' in line and ('：' in line or ':' in line):
                sep = '：' if '：' in line else ':'
                snippet = line.split(sep, 1)[1].strip()
        if url:
            results.append({"url": url, "title": title, "snippet": snippet})

    # 降级：正则提取所有 URL
    if not results:
        seen = set()
        for u in re.findall(r'https?://[^\s\)）\]」]+', text):
            u = u.rstrip('.,;:')
            if u not in seen:
                seen.add(u)
                results.append({"url": u, "title": "", "snippet": ""})

    return results


async def guest_web_search(guest_name: str, guest_description: str = "", custom_search_prompt: str = "") -> dict:
    """多轮 Claude web search 搜索嘉宾采访资料，合并去重"""
    if not settings.ANTHROPIC_API_KEY:
        return {"summary": "错误：ANTHROPIC_API_KEY 未配置", "search_results": []}

    desc_hint = f"\n此人的身份信息：{guest_description}" if guest_description else ""
    search_strategy = custom_search_prompt or DEFAULT_PROMPTS.get("嘉宾搜索策略", "")

    output_format = """

请严格按以下格式整理每一条采访记录：

## 采访 1：[标题]
- **链接**：[完整URL，必须以 http:// 或 https:// 开头]
- **来源**：[媒体/平台名称]
- **日期**：[发布日期]
- **摘要**：[2-3句话概括采访核心内容]

## 采访 2：[标题]
...

每条记录必须包含完整的可点击URL链接。"""

    base_instruction = f"请搜索关于「{guest_name}」的公开资料。{desc_hint}\n\n搜索策略：\n{search_strategy}\n"

    # 两轮搜索，不同角度
    search_rounds = [
        f"{base_instruction}\n本轮重点：深度采访、专访文章、对话记录、播客节目。\n搜索关键词建议：{guest_name} 采访、{guest_name} 专访、{guest_name} 对话、{guest_name} 播客。{output_format}",
        f"{base_instruction}\n本轮重点：演讲发言、观点评论、深度报道、人物特写。\n搜索关键词建议：{guest_name} 演讲、{guest_name} 观点、{guest_name} 报道、{guest_name} 人物。{output_format}",
    ]

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    all_results = []
    all_summaries = []
    seen_urls = set()

    for i, prompt in enumerate(search_rounds, 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8096,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
                messages=[{"role": "user", "content": prompt}],
            )

            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            results = _parse_search_results(text)
            new_count = 0
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
                    new_count += 1

            all_summaries.append(text)
            logger.info(f"嘉宾搜索第{i}轮: {guest_name}, 本轮{len(results)}条, 新增{new_count}条")

        except Exception as e:
            logger.error(f"嘉宾搜索第{i}轮失败: {e}")

    combined_summary = "\n\n---\n\n".join(all_summaries)
    logger.info(f"嘉宾搜索完成: {guest_name}, 共{len(all_results)}条链接")

    return {
        "summary": combined_summary,
        "search_results": all_results,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _format_materials_context(guest_name: str, materials: list[dict], max_chars: int = 300000) -> str:
    """将素材格式化为上下文文本，控制总长度不超限"""
    context_lines = [f"# 嘉宾：{guest_name}\n"]
    total_chars = 0

    for i, m in enumerate(materials, 1):
        status = m.get("status", "pending")
        mat_type = m.get("type", "")

        # ai_summary 类型降权标注
        if mat_type == "ai_summary":
            entry_lines = [f"## 资料 {i}：{m.get('title', '(无标题)')} [AI生成，仅供参考]"]
        elif status == "verified":
            entry_lines = [f"## 资料 {i}：{m.get('title', '(无标题)')} [已验证]"]
        elif status == "failed":
            entry_lines = [f"## 资料 {i}：{m.get('title', '(无标题)')} [抓取失败，信息未验证]"]
        elif status == "unverified":
            entry_lines = [f"## 资料 {i}：{m.get('title', '(无标题)')} [未验证]"]
        else:
            entry_lines = [f"## 资料 {i}：{m.get('title', '(无标题)')}"]

        if m.get("platform"):
            entry_lines.append(f"- 平台：{m['platform']}")
        if m.get("url"):
            entry_lines.append(f"- 来源：{m['url']}")
        if m.get("summary"):
            entry_lines.append(f"- 摘要：{m['summary']}")
        if m.get("content"):
            content = m["content"]
            if len(content) > 5000:
                content = content[:5000] + "\n[内容已截断]"
            entry_lines.append(f"- 内容：{content}")
        entry_lines.append("")

        entry_text = "\n".join(entry_lines)
        if total_chars + len(entry_text) > max_chars:
            context_lines.append(f"\n[剩余 {len(materials) - i + 1} 条素材因长度限制已省略]")
            break
        context_lines.append(entry_text)
        total_chars += len(entry_text)

    return "\n".join(context_lines)


async def analyze_guest(
    guest_name: str,
    materials: list[dict],
    analysis_type: str = "interview",
    custom_prompt: str = "",
    **kwargs,
) -> dict:
    """根据嘉宾素材直接生成采访策划方案"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = custom_prompt or DEFAULT_PROMPTS.get("采访策划方案", "")
    materials_text = _format_materials_context(guest_name, materials)
    user_text = f"{materials_text}\n请根据以上资料，先研究再输出完整的采访策划方案（包含50个问题）。"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"嘉宾分析失败: {e}", exc_info=True)
        result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": "采访策划方案",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def guest_chat(guest_name: str, analyses: list[dict], user_message: str) -> str:
    """对话预演：AI 扮演嘉宾进行模拟对话"""
    if not settings.ANTHROPIC_API_KEY:
        return "错误：ANTHROPIC_API_KEY 未配置"

    # 构建嘉宾人设：只用分析结果，不送素材全文（省 token）
    analyses_text = ""
    for a in analyses:
        result = a.get("content", {}).get("result", "")
        if result:
            analyses_text += f"\n{result}\n"

    system_prompt = f"""你现在扮演「{guest_name}」，正在接受「继续追问」节目的采访。

请根据以下研究资料还原此人的说话风格、观点立场和思维方式来回答问题：
- 用此人惯用的表达方式和语气
- 基于此人已知的观点和立场来回应
- 遇到敏感问题时，模拟此人可能的回避或应对方式
- 如果问题超出已知资料范围，用此人的思维模式合理推演

{analyses_text}

请始终保持角色，用第一人称回答。回答要自然、有深度，像真实的采访对话。"""

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"对话预演失败: {e}", exc_info=True)
        return f"对话失败：{str(e)}"
