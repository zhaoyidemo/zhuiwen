import re
import logging
from datetime import datetime
from typing import Optional

import httpx

from config import settings
from models.schemas import VideoData, AccountData

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tikhub.io"
HEADERS = {
    "Authorization": f"Bearer {settings.TIKHUB_API_KEY}",
    "Content-Type": "application/json",
}


def _get_headers():
    return {
        "Authorization": f"Bearer {settings.TIKHUB_API_KEY}",
        "Content-Type": "application/json",
    }


async def _request(method: str, path: str, params: dict = None, json_data: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method,
            f"{BASE_URL}{path}",
            headers=_get_headers(),
            params=params,
            json=json_data,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_aweme_id(url: str) -> Optional[str]:
    """从完整抖音链接中提取 aweme_id"""
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"aweme_id=(\d+)", url)
    if match:
        return match.group(1)
    return None


def _is_share_url(url: str) -> bool:
    return "v.douyin.com" in url or "vm.douyin.com" in url


def _parse_duration(item: dict, video: dict) -> int:
    """解析视频时长（返回秒数）"""
    # item.duration 通常是毫秒
    d = item.get("duration", 0) or 0
    if d > 10000:  # 超过 10000 说明是毫秒
        return d // 1000
    if d > 0:
        return d
    # fallback: video.duration
    vd = video.get("duration", 0) or 0
    if vd > 10000:
        return vd // 1000
    return vd


def _parse_video_data(item: dict, source_url: str = "") -> VideoData:
    """从 TikHub 返回的视频数据中解析出 VideoData"""
    statistics = item.get("statistics", {}) or {}
    author = item.get("author", {}) or {}
    music = item.get("music", {}) or {}
    video = item.get("video", {}) or {}

    play_count = statistics.get("play_count", 0) or statistics.get("view_count", 0) or 0
    digg_count = statistics.get("digg_count", 0) or 0
    collect_count = statistics.get("collect_count", 0) or 0
    # 播放量为 0 时，用点赞数估算播放量来计算收藏率（抖音部分端点不返回播放量）
    denominator = play_count if play_count > 0 else digg_count
    collect_rate = round(collect_count / denominator, 6) if denominator > 0 else 0.0

    # 提取话题标签
    text_extra = item.get("text_extra", []) or []
    tags = ", ".join([t.get("hashtag_name", "") for t in text_extra if t.get("hashtag_name")])

    # 提取无水印视频链接
    play_addr = video.get("play_addr", {}) or {}
    video_url = ""
    url_list = play_addr.get("url_list", [])
    if url_list:
        video_url = url_list[-1]

    # 封面
    cover = video.get("cover", {}) or video.get("origin_cover", {}) or {}
    cover_url = ""
    cover_list = cover.get("url_list", [])
    if cover_list:
        cover_url = cover_list[0]

    # 共创信息
    mix_info = item.get("mix_info", {}) or {}
    co_creation = item.get("common_bar_info", None)
    is_co_creation = bool(co_creation) or bool(item.get("duet_origin_item", None))

    # 发布时间
    create_time_ts = item.get("create_time", 0)
    create_time_str = ""
    if create_time_ts:
        try:
            create_time_str = datetime.fromtimestamp(create_time_ts).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            create_time_str = str(create_time_ts)

    return VideoData(
        aweme_id=str(item.get("aweme_id", "")),
        account_id=str(author.get("uid", "")),
        desc=item.get("desc", ""),
        create_time=create_time_str,
        duration=_parse_duration(item, video),
        play_count=play_count,
        digg_count=digg_count,
        comment_count=statistics.get("comment_count", 0) or 0,
        collect_count=collect_count,
        share_count=statistics.get("share_count", 0) or 0,
        collect_rate=collect_rate,
        tags=tags,
        music_title=music.get("title", ""),
        video_url=video_url,
        cover_url=cover_url,
        is_co_creation=is_co_creation,
        co_creation_users="",
        source_url=source_url,
        author_nickname=author.get("nickname", ""),
        author_avatar=(author.get("avatar_thumb", {}) or {}).get("url_list", [""])[0] if author.get("avatar_thumb") else "",
        author_unique_id=author.get("unique_id", "") or author.get("short_id", ""),
        author_follower_count=author.get("follower_count", 0) or 0,
    )


async def fetch_video_by_share_url(share_url: str) -> VideoData:
    """通过分享链接获取视频数据"""
    data = await _request("GET", "/api/v1/douyin/app/v3/fetch_one_video_by_share_url", params={"share_url": share_url})
    logger.info(f"TikHub share_url response keys: {list(data.keys())}")

    item_data = data.get("data", {})
    aweme_detail = item_data.get("aweme_detail") or item_data.get("aweme_details", [None])
    if isinstance(aweme_detail, list):
        aweme_detail = aweme_detail[0] if aweme_detail else {}
    if not aweme_detail:
        aweme_detail = item_data

    return _parse_video_data(aweme_detail, source_url=share_url)


async def fetch_video_by_id(aweme_id: str) -> VideoData:
    """通过 aweme_id 获取视频数据"""
    data = await _request("GET", "/api/v1/douyin/app/v3/fetch_one_video", params={"aweme_id": aweme_id})
    logger.info(f"TikHub video response keys: {list(data.keys())}")

    item_data = data.get("data", {})
    aweme_detail = item_data.get("aweme_detail") or item_data.get("aweme_details", [None])
    if isinstance(aweme_detail, list):
        aweme_detail = aweme_detail[0] if aweme_detail else {}
    if not aweme_detail:
        aweme_detail = item_data

    return _parse_video_data(aweme_detail, source_url=f"https://www.douyin.com/video/{aweme_id}")


async def parse_and_fetch_video(url: str) -> VideoData:
    """统一入口：根据 URL 类型选择不同的获取方式，并尝试补充真实播放量"""
    url = url.strip()
    if _is_share_url(url):
        video = await fetch_video_by_share_url(url)
    elif _extract_aweme_id(url):
        video = await fetch_video_by_id(_extract_aweme_id(url))
    else:
        video = await fetch_video_by_share_url(url)

    # 尝试通过 statistics 接口获取真实播放量
    if video.play_count == 0 and video.aweme_id:
        stats = await fetch_video_statistics(video.aweme_id)
        real_play = stats.get("play_count", 0)
        if real_play > 0:
            video.play_count = real_play
            denominator = real_play
            video.collect_rate = round(video.collect_count / denominator, 6) if denominator > 0 else 0.0
            logger.info(f"通过 statistics 接口补充播放量: {real_play}")

    return video


async def fetch_user_profile(unique_id: str) -> AccountData:
    """获取用户信息"""
    data = await _request("GET", "/api/v1/douyin/web/handler_user_profile_v2", params={"unique_id": unique_id})
    logger.info(f"TikHub user profile response keys: {list(data.keys())}")

    user_data = data.get("data", {})
    # handler_user_profile_v2 结构: data.data.user_info
    user_info = user_data.get("user_info", {}) or user_data.get("user", {}) or user_data
    logger.info(f"user_info 全部字段: {list(user_info.keys()) if isinstance(user_info, dict) else type(user_info)}")

    # 粉丝等数据可能在顶层或 statistics 子对象中
    stats = user_info.get("statistics", {}) or {}
    # 有些接口用 mplatform_followers_count
    follower = (user_info.get("follower_count") or user_info.get("mplatform_followers_count")
                or stats.get("follower_count") or 0)
    following = user_info.get("following_count") or stats.get("following_count") or 0
    favorited = (user_info.get("total_favorited") or user_info.get("favoriting_count")
                 or stats.get("total_favorited") or 0)
    aweme_count = user_info.get("aweme_count") or stats.get("aweme_count") or 0

    # 头像：可能是 dict{url_list} 或直接 string
    avatar = user_info.get("avatar_larger", {}) or user_info.get("avatar_medium", {}) or user_info.get("avatar_thumb", {}) or {}
    avatar_url = ""
    if isinstance(avatar, dict):
        url_list = avatar.get("url_list", [])
        avatar_url = url_list[0] if url_list else ""
    elif isinstance(avatar, str):
        avatar_url = avatar

    logger.info(f"解析结果: nickname={user_info.get('nickname')}, sec_uid={user_info.get('sec_uid')}, follower={follower}")

    return AccountData(
        account_id=str(user_info.get("uid", "")),
        sec_user_id=user_info.get("sec_uid", ""),
        unique_id=user_info.get("unique_id", "") or unique_id,
        nickname=user_info.get("nickname", ""),
        avatar_url=avatar_url,
        follower_count=int(follower) if follower else 0,
        following_count=int(following) if following else 0,
        total_favorited=int(favorited) if favorited else 0,
        video_count=int(aweme_count) if aweme_count else 0,
        signature=user_info.get("signature", ""),
    )


async def fetch_user_videos(sec_user_id: str, max_cursor: int = 0, count: int = 20) -> dict:
    """分页获取用户视频列表"""
    data = await _request(
        "GET",
        "/api/v1/douyin/app/v3/fetch_user_post_videos",
        params={"sec_user_id": sec_user_id, "max_cursor": max_cursor, "count": count},
    )

    result_data = data.get("data", {})
    aweme_list = result_data.get("aweme_list", []) or []
    has_more = result_data.get("has_more", False)
    next_cursor = result_data.get("max_cursor", 0)

    videos = [_parse_video_data(item) for item in aweme_list]

    return {
        "videos": videos,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


async def fetch_all_user_videos(sec_user_id: str) -> list[VideoData]:
    """拉取用户全部视频（自动分页），然后批量补充播放量"""
    all_videos = []
    cursor = 0
    while True:
        result = await fetch_user_videos(sec_user_id, max_cursor=cursor, count=20)
        all_videos.extend(result["videos"])
        logger.info(f"Fetched {len(result['videos'])} videos, total: {len(all_videos)}")
        if not result["has_more"]:
            break
        cursor = result["next_cursor"]

    # 批量补充播放量（每次最多20个）
    await _batch_fill_play_count(all_videos)
    return all_videos


async def _batch_fill_play_count(videos: list[VideoData]):
    """批量调用 fetch_video_statistics 补充播放量"""
    need_fill = [v for v in videos if v.play_count == 0 and v.aweme_id]
    if not need_fill:
        return
    # 每批20个
    for i in range(0, len(need_fill), 20):
        batch = need_fill[i:i+20]
        ids = ",".join(v.aweme_id for v in batch)
        try:
            data = await _request("GET", "/api/v1/douyin/app/v3/fetch_video_statistics", params={"aweme_ids": ids})
            stats_list = data.get("data", {}).get("statistics_list", []) or []
            stats_map = {str(s.get("aweme_id", "")): s for s in stats_list if isinstance(s, dict)}
            for v in batch:
                s = stats_map.get(v.aweme_id, {})
                play = s.get("play_count", 0) or 0
                if play > 0:
                    v.play_count = play
                    v.collect_rate = round(v.collect_count / play, 6) if play > 0 else 0.0
            logger.info(f"批量补充播放量: {len(batch)}条, 成功{len(stats_map)}条")
        except Exception as e:
            logger.warning(f"批量获取统计失败: {e}")


async def fetch_video_statistics(aweme_id: str) -> dict:
    """获取视频真实播放量统计（参数为 aweme_ids，支持批量）"""
    try:
        data = await _request("GET", "/api/v1/douyin/app/v3/fetch_video_statistics", params={"aweme_ids": aweme_id})
        result = data.get("data", {})
        # 结构: {statistics_list: [{aweme_id, play_count, digg_count, share_count}]}
        stats = {}
        if isinstance(result, dict):
            stats_list = result.get("statistics_list", [])
            if isinstance(stats_list, list) and stats_list:
                stats = stats_list[0]
            elif not stats_list:
                stats = result.get("statistics", {}) or result
        elif isinstance(result, list) and result:
            stats = result[0] if isinstance(result[0], dict) else {}
        logger.info(f"statistics 提取结果: play_count={stats.get('play_count', 0)}")
        return {
            "play_count": stats.get("play_count", 0) or 0,
            "digg_count": stats.get("digg_count", 0) or 0,
            "comment_count": stats.get("comment_count", 0) or 0,
            "collect_count": stats.get("collect_count", 0) or 0,
            "share_count": stats.get("share_count", 0) or 0,
        }
    except Exception as e:
        logger.warning(f"获取视频统计失败（不影响主流程）: {e}")
        return {}


def _extract_list(data: dict, *keys) -> list:
    """从 TikHub 嵌套响应中提取列表数据，支持多级 data 嵌套"""
    result = data.get("data", {})
    # TikHub 经常双层嵌套: {data: {data: [...], code: 0}}
    if isinstance(result, dict):
        for key in keys:
            val = result.get(key)
            if isinstance(val, list):
                return val
        # fallback: 尝试 result["data"]
        inner = result.get("data")
        if isinstance(inner, list):
            return inner
    if isinstance(result, list):
        return result
    return []


async def fetch_video_trends(aweme_id: str, date_window: int = 7) -> list:
    """获取视频数据趋势（Billboard API）"""
    try:
        data = await _request(
            "GET",
            "/api/v1/douyin/billboard/fetch_hot_item_trends_list",
            params={"aweme_id": aweme_id, "option": "all", "date_window": date_window},
        )
        return _extract_list(data, "trend_list", "trends")
    except Exception as e:
        logger.warning(f"获取视频趋势失败: {e}")
        return []


async def fetch_comment_word_cloud(aweme_id: str) -> list:
    """获取评论词云权重（Billboard API）"""
    try:
        data = await _request(
            "GET",
            "/api/v1/douyin/billboard/fetch_hot_comment_word_list",
            params={"aweme_id": aweme_id},
        )
        return _extract_list(data, "word_list", "words")
    except Exception as e:
        logger.warning(f"获取评论词云失败: {e}")
        return []


async def fetch_video_danmaku(aweme_id: str, duration: int = 0) -> list:
    """获取视频弹幕数据（Web API）"""
    try:
        params = {
            "item_id": aweme_id,
            "duration": duration if duration > 0 else 300,
            "start_time": 0,
            "end_time": duration if duration > 0 else 300,
        }
        data = await _request(
            "GET",
            "/api/v1/douyin/web/fetch_one_video_danmaku",
            params=params,
        )
        return _extract_list(data, "danmaku_list", "danmaku")
    except Exception as e:
        logger.warning(f"获取弹幕数据失败: {e}")
        return []


async def fetch_video_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
    """获取视频评论"""
    data = await _request(
        "GET",
        "/api/v1/douyin/web/fetch_video_comments",
        params={"aweme_id": aweme_id, "cursor": cursor, "count": count},
    )
    result_data = data.get("data", {})
    comments = result_data.get("comments", []) or []
    has_more = result_data.get("has_more", False)
    next_cursor = result_data.get("cursor", 0)

    parsed = []
    for c in comments:
        user = c.get("user", {}) or {}
        parsed.append({
            "comment_id": str(c.get("cid", "")),
            "aweme_id": aweme_id,
            "user_nickname": user.get("nickname", ""),
            "content": c.get("text", ""),
            "digg_count": c.get("digg_count", 0),
            "reply_count": len(c.get("reply_comment", []) or []),
            "create_time": c.get("create_time", 0),
        })

    return {"comments": parsed, "has_more": has_more, "next_cursor": next_cursor}
