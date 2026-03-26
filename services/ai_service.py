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

    "AI调查员": """搜索此人接受过的采访和访谈，覆盖以下类型：
- 文字采访稿、深度对话、专访
- 视频访谈、播客节目
- 演讲、公开发言、论坛圆桌
- 新闻报道中的引述和观点

请用多个不同的搜索关键词组合来搜索，确保覆盖面足够广。注意区分此人作为受访者的内容和其他同名者的内容。""",

    "AI策划专员": """你是「继续追问」节目的AI策划专员。「继续追问」是一档对标 Lex Fridman Podcast 的中文长视频深度访谈播客（60-180分钟）。

核心理念：最好的长视频是好的短视频的合集。每个段落独立剪出来就是一条好切片，串起来就是一场好对话。

请根据嘉宾的全部采访素材，先快速研究再输出段落式采访策划方案。

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

# 第二部分：段落式采访策划

## 采访定位
- 这期节目的核心命题是什么？（一句话）
- 和此人之前的采访相比，我们的差异化在哪？

## 段落设计（20-25个段落）

将整场采访设计为20-25个段落。每个段落是一个完整的"微叙事"，独立剪出来就是一条切片。

每个段落严格按以下格式输出：

---
### 段落 N：[预设切片标题]（预估 X 分钟）
**场景定位**：破冰 / 经历深挖 / 观点交锋 / 行业洞察 / 争议直面 / 灵魂拷问 / 快问快答
**钩子问题**：[开场第一个问题——要能做切片的前3秒]
**核心问题**：[这个段落要挖到的核心信息]
**追问设计**：如果嘉宾回答触发 X → 追问 Y → 再追问 Z
**金句预判**：[这个段落最可能产出什么金句]
**剪辑点提示**：[嘉宾说到什么时候是切片的收尾点]
**→ 衔接到下一段落**：[用什么话自然过渡]
---

段落类型分布建议：
- 破冰与个人故事：3-4个段落（开场）
- 职业经历深挖：4-5个段落
- 核心观点交锋：5-6个段落（主战场）
- 行业洞察与趋势：3-4个段落
- 争议与挑战：2-3个段落
- 人生哲学与灵魂拷问：2-3个段落
- 快问快答与开放题：1-2个段落（收尾）

## 追问武器库
- 从"矛盾点"设计3-5个追问弹药
- 格式：「你在[某次采访]中说过[原话]，但[另一场合]又说[原话]，能解释一下吗？」

## 节奏总览
- 整场采访的叙事弧线
- 高潮段落标注（建议放在哪个时间点）
- 情绪曲线设计（轻松→深入→尖锐→温情→收尾）

## 风险预案
- 可能的敏感话题及应对方式
- 嘉宾可能的回避策略及破解方式

重要规则：
- 只引用素材原文中明确存在的信息，不要用你自己的知识补充
- 每个观点、引语必须标注来源素材编号（如「资料3」）
- 如果某条信息只出现在标注为"未验证"的素材中，请注明"[未验证]"
- 不要编造嘉宾没说过的话或没做过的事
- 20-25个段落必须足量，每个段落必须完整

请让每个段落都有明确的"追问路径"，这是「继续追问」的核心价值。""",

    "AI内容编导": """你是「继续追问」节目的AI内容编导，全球顶级的深度访谈策划大师，擅长设计让嘉宾说出从未公开说过的话的问题。

你将收到一份已有的段落式采访策划方案。请在此基础上进行二次深度打磨：

## 一、策划方案审视
- 这份策划最大的亮点是什么？
- 最大的薄弱环节在哪？
- 有哪些角度被遗漏了？

## 二、升级版核心段落（8-10个）
从原方案的段落中，挑出最有潜力的8-10个，进行升级改造：
- 让问题更具体、更尖锐、更难回避
- 设计2-3层递进追问链（如果嘉宾回答A→追问B→再追问C）
- 加入"意外切入"——用嘉宾不曾预料的角度来提问

## 三、杀手锏段落（3-5个）
设计3-5个原方案中完全没有的、全新角度的段落：
- 跨领域关联：将此人的经历与看似无关的领域连接
- 思想实验："如果X发生了，你会怎么做"
- 元问题：关于此人如何思考、如何做决策的问题
每个杀手锏段落同样按完整的段落格式输出（钩子、核心问题、追问、金句预判、剪辑点）

## 四、追问链路图
选择5个最重要的段落，画出完整的追问决策树：
```
段落 N：[标题]
├── 如果嘉宾回答方向A → 追问A1 → 再追问A2
├── 如果嘉宾回答方向B → 追问B1 → 再追问B2
└── 如果嘉宾回避/打太极 → 换角度C → 追问C1
```

## 五、对话节奏优化
- 哪个时间点抛出杀手锏段落效果最好？
- 哪些段落组合在一起会产生化学反应？
- 如何在嘉宾"表演状态"和"真实状态"之间制造切换？

请大胆思考，不要受原方案的框架限制。目标是让这场对话成为这位嘉宾有史以来最深度的一次采访。""",

    "AI切片编导": """你是「继续追问」节目的AI切片编导，专精于短视频传播和算法推荐机制。

你将收到一份段落式采访策划方案。请从传播和算法角度审视每个段落的切片潜力。

## 一、切片潜力评估
对每个段落打分（S/A/B/C），标注最有爆款潜力的 TOP5 段落
- S级：极高概率破百万播放
- A级：高概率10万+
- B级：稳定表现
- C级：建议优化或合并

## 二、标题工厂
为 TOP10 段落各设计 3 个备选切片标题（方便后期 A/B 测试）
标题要求：
- 有悬念或冲突或信息增量
- ≤20字
- 避免标题党但要有吸引力

## 三、钩子重设计
审视每个段落的钩子问题，从"前3秒留存"角度优化：
- 原钩子 → 优化后的钩子
- 为什么优化后的版本更能留住滑到这条视频的人
- 考虑：画面感、悬念感、信息密度

## 四、金句催化设计
针对高潜力段落，设计"逼出金句"的追问技巧：
- 什么样的追问能让嘉宾脱离"安全区"说出真话
- "沉默追问"：问完后故意停顿，让嘉宾补充
- "极端假设"：把嘉宾的观点推到极限看他怎么反应
- "第三人称"：如果你的朋友遇到这种情况...

## 五、评论引爆预设
为 TOP5 段落预测评论区反应：
- 预判正反方观点（观点对立驱动算法推荐）
- 设计最可能被刷屏的弹幕
- 建议在切片结尾加什么引导语触发评论（"你觉得他说的对吗？"）
- 预判转发动机（"这段话必须让XX看到"）

## 六、封面文案建议
为 TOP5 段落建议封面上的文字（通常是嘉宾金句的精简版），要求一眼抓住注意力。

请始终从"一个用户在刷抖音时滑到这条切片"的场景出发思考。""",

    "AI热点编导": """你是「继续追问」节目的AI热点编导，专精于社交媒体热点趋势和内容传播。

你将收到一位嘉宾的采访策划方案。请搜索当下最新的社会热点、行业动态和公众讨论话题，找到与这位嘉宾专业领域的交叉点。

## 一、热点扫描
搜索近1-2周内与此嘉宾领域相关的热点话题（抖音热搜、微博热搜、新闻热点等），列出 TOP5-8 个：
每个热点：
- **话题**：一句话概括
- **热度来源**：在哪个平台火的
- **与嘉宾的关联**：此人的专业背景为什么有资格谈这个话题

## 二、热点嫁接问题设计
为每个相关热点设计 1-2 个采访问题：
- 问题要自然地将热点话题和嘉宾的经验/观点关联起来
- 不是生硬地"你怎么看XX热搜"，而是找到深层连接
- 每个问题附追问方向

## 三、热点切片预判
从设计的热点问题中，挑出最有爆款潜力的 TOP3：
- 预设切片标题（蹭热点但不标题党）
- 为什么这个话题+这个嘉宾的组合能火
- 最佳发布时间窗口建议（热点有时效性）

## 四、风险提示
- 哪些热点话题可能有政治/舆论风险，建议谨慎或回避
- 哪些热点已经过气，不建议再蹭

请确保搜索的是最新的、当下正在讨论的话题，不要用过时的热点。""",

    "AI嘉宾替身": """你扮演采访嘉宾，正在接受「继续追问」节目的采访。

请根据提供的研究资料还原此人的说话风格、观点立场和思维方式来回答问题：
- 用此人惯用的表达方式和语气
- 基于此人已知的观点和立场来回应
- 遇到敏感问题时，模拟此人可能的回避或应对方式
- 如果问题超出已知资料范围，用此人的思维模式合理推演

请始终保持角色，用第一人称回答。回答要自然、有深度，像真实的采访对话。""",
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
            model="claude-opus-4-6-20250415",
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
                    model="claude-opus-4-6-20250415",
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
            model="claude-opus-4-6-20250415",
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
                model="claude-opus-4-6-20250415",
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


async def guest_web_search(guest_name: str, guest_description: str = "", custom_search_prompt: str = "", extra_keywords: str = "") -> dict:
    """多轮 Claude web search 搜索嘉宾采访资料，合并去重，含智能补搜"""
    import re

    if not settings.ANTHROPIC_API_KEY:
        return {"summary": "错误：ANTHROPIC_API_KEY 未配置", "search_results": []}

    desc_hint = f"\n此人的身份信息：{guest_description}" if guest_description else ""
    search_strategy = custom_search_prompt or DEFAULT_PROMPTS.get("AI调查员", "")
    extra_hint = f"\n补充搜索关键词：{extra_keywords}" if extra_keywords else ""

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

    base_instruction = f"请搜索关于「{guest_name}」的公开资料。{desc_hint}{extra_hint}\n\n搜索策略：\n{search_strategy}\n"

    # 构建搜索关键词（包含用户补充的）
    base_keywords = guest_name
    if extra_keywords:
        extra_kw_list = [k.strip() for k in extra_keywords.replace('，', ',').split(',') if k.strip()]
    else:
        extra_kw_list = []

    # 前三轮：固定角度搜索（含微信公众号定向）
    search_rounds = [
        f"{base_instruction}\n本轮重点：深度采访、专访文章、对话记录、播客节目。\n搜索关键词建议：{guest_name} 采访、{guest_name} 专访、{guest_name} 对话、{guest_name} 播客。{output_format}",
        f"{base_instruction}\n本轮重点：演讲发言、观点评论、深度报道、人物特写。\n搜索关键词建议：{guest_name} 演讲、{guest_name} 观点、{guest_name} 报道、{guest_name} 人物。{output_format}",
        f"{base_instruction}\n本轮重点：微信公众号文章。请专门搜索此人在微信公众号上的采访、对话、观点文章。\n搜索关键词建议：site:mp.weixin.qq.com {guest_name}、{guest_name} 微信公众号 采访、{guest_name} 微信 专访。{output_format}",
    ]

    # 如果有补充关键词，加一轮定向搜索
    if extra_kw_list:
        kw_str = "、".join([f"{guest_name} {kw}" for kw in extra_kw_list])
        search_rounds.append(
            f"{base_instruction}\n本轮重点：使用用户指定的补充关键词搜索。\n搜索关键词：{kw_str}。{output_format}"
        )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    all_results = []
    all_summaries = []
    seen_urls = set()

    def _run_round(prompt, round_num):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6-20250414",
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
            logger.info(f"嘉宾搜索第{round_num}轮: {guest_name}, 本轮{len(results)}条, 新增{new_count}条")
        except Exception as e:
            logger.error(f"嘉宾搜索第{round_num}轮失败: {e}")

    for i, prompt in enumerate(search_rounds, 1):
        _run_round(prompt, i)

    # 智能补搜：分析已有结果，搜索缺失的维度
    if len(all_results) > 0:
        found_summary = "\n".join([f"- {r['title']}" for r in all_results[:20]])
        gap_prompt = f"""我已经搜索到以下关于「{guest_name}」的采访资料：
{found_summary}

请分析还缺少哪些维度的资料（比如：是否缺少视频访谈？缺少某个时期的采访？缺少某个话题的讨论？），然后搜索补充。
{desc_hint}{extra_hint}
{output_format}"""
        _run_round(gap_prompt, len(search_rounds) + 1)

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

    # 过滤已排除的素材
    active_materials = [m for m in materials if m.get("status") != "excluded"]

    for i, m in enumerate(active_materials, 1):
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
            context_lines.append(f"\n[剩余 {len(active_materials) - i + 1} 条素材因长度限制已省略]")
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

    system_prompt = custom_prompt or DEFAULT_PROMPTS.get("AI策划专员", "")
    materials_text = _format_materials_context(guest_name, materials)
    user_text = f"{materials_text}\n请根据以上资料，先研究再输出段落式采访策划方案（20-25个段落）。"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6-20250414",
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
        "prompt_used": "AI策划专员",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def deep_follow_up(guest_name: str, interview_plan: str, custom_prompt: str = "") -> dict:
    """继续追问：用 Opus 对采访策划方案做二次深度打磨"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = custom_prompt or DEFAULT_PROMPTS.get("AI内容编导", "")
    user_text = f"# 嘉宾：{guest_name}\n\n# 已有采访策划方案\n\n{interview_plan}\n\n请在此基础上进行二次深度打磨。"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-opus-4-6-20250415",
            max_tokens=8096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"继续追问失败: {e}", exc_info=True)
        result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": "AI内容编导",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def trending_review(guest_name: str, guest_description: str, interview_plan: str, custom_prompt: str = "") -> dict:
    """AI热点编导：搜索热点话题并嫁接到采访问题"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = custom_prompt or DEFAULT_PROMPTS.get("AI热点编导", "")
    desc_hint = f"（{guest_description}）" if guest_description else ""
    user_text = f"# 嘉宾：{guest_name}{desc_hint}\n\n# 已有采访策划方案\n\n{interview_plan}\n\n请搜索当下热点话题，找到与这位嘉宾的交叉点，设计热点嫁接问题。"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6-20250414",
            max_tokens=8096,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        result_text = ""
        for block in message.content:
            if block.type == "text":
                result_text += block.text
    except Exception as e:
        logger.error(f"AI热点编导失败: {e}", exc_info=True)
        result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": "AI热点编导",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def clip_review(guest_name: str, interview_plan: str, custom_prompt: str = "") -> dict:
    """AI切片编导：从传播和算法角度审视策划方案"""
    if not settings.ANTHROPIC_API_KEY:
        return {"result": "错误：ANTHROPIC_API_KEY 未配置", "created_at": ""}

    system_prompt = custom_prompt or DEFAULT_PROMPTS.get("AI切片编导", "")
    user_text = f"# 嘉宾：{guest_name}\n\n# 段落式采访策划方案\n\n{interview_plan}\n\n请从切片传播和算法推荐角度审视每个段落。"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-opus-4-6-20250415",
            max_tokens=8096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        result_text = message.content[0].text
    except Exception as e:
        logger.error(f"AI切片编导失败: {e}", exc_info=True)
        result_text = f"分析失败：{str(e)}"

    return {
        "result": result_text,
        "prompt_used": "AI切片编导",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def guest_chat(guest_name: str, analyses: list[dict], chat_history: list[dict], user_message: str, custom_prompt: str = "") -> str:
    """AI嘉宾替身：多轮模拟对话"""
    if not settings.ANTHROPIC_API_KEY:
        return "错误：ANTHROPIC_API_KEY 未配置"

    base_prompt = custom_prompt or DEFAULT_PROMPTS.get("AI嘉宾替身", "")

    analyses_text = ""
    for a in analyses:
        result = a.get("content", {}).get("result", "")
        if result:
            analyses_text += f"\n{result}\n"

    system_prompt = f"你现在扮演「{guest_name}」。\n\n{base_prompt}\n\n以下是关于此人的研究资料：\n{analyses_text}"

    # 构建多轮对话消息
    messages = []
    for msg in chat_history:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": msg.get("text", "")})
    messages.append({"role": "user", "content": user_message})

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6-20250414",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"对话预演失败: {e}", exc_info=True)
        return f"对话失败：{str(e)}"
