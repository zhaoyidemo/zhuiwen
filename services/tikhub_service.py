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
    """统一入口：根据 URL 类型选择不同的获取方式"""
    url = url.strip()
    if _is_share_url(url):
        return await fetch_video_by_share_url(url)
    aweme_id = _extract_aweme_id(url)
    if aweme_id:
        return await fetch_video_by_id(aweme_id)
    # 尝试当作分享链接处理
    return await fetch_video_by_share_url(url)


async def fetch_user_profile(unique_id: str) -> AccountData:
    """获取用户信息"""
    data = await _request("GET", "/api/v1/douyin/web/fetch_user_profile", params={"uniqueId": unique_id})
    logger.info(f"TikHub user profile response keys: {list(data.keys())}")

    user_data = data.get("data", {})
    user_info = user_data.get("user", {}) or user_data
    stats = user_info.get("statistics", {}) or {}

    avatar = user_info.get("avatar_thumb", {}) or user_info.get("avatar_medium", {}) or {}
    avatar_url = ""
    if isinstance(avatar, dict):
        url_list = avatar.get("url_list", [])
        avatar_url = url_list[0] if url_list else ""
    elif isinstance(avatar, str):
        avatar_url = avatar

    return AccountData(
        account_id=str(user_info.get("uid", "")),
        sec_user_id=user_info.get("sec_uid", ""),
        unique_id=user_info.get("unique_id", "") or unique_id,
        nickname=user_info.get("nickname", ""),
        avatar_url=avatar_url,
        follower_count=user_info.get("follower_count", 0) or stats.get("follower_count", 0) or 0,
        following_count=user_info.get("following_count", 0) or stats.get("following_count", 0) or 0,
        total_favorited=user_info.get("total_favorited", 0) or stats.get("total_favorited", 0) or 0,
        video_count=user_info.get("aweme_count", 0) or stats.get("aweme_count", 0) or 0,
        signature=user_info.get("signature", ""),
    )


async def fetch_user_videos(sec_user_id: str, max_cursor: int = 0, count: int = 20) -> dict:
    """分页获取用户视频列表"""
    data = await _request(
        "GET",
        "/api/v1/douyin/web/fetch_user_post_videos",
        params={"secUid": sec_user_id, "max_cursor": max_cursor, "count": count},
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
    """拉取用户全部视频（自动分页）"""
    all_videos = []
    cursor = 0
    while True:
        result = await fetch_user_videos(sec_user_id, max_cursor=cursor, count=20)
        all_videos.extend(result["videos"])
        logger.info(f"Fetched {len(result['videos'])} videos, total: {len(all_videos)}")
        if not result["has_more"]:
            break
        cursor = result["next_cursor"]
    return all_videos


async def fetch_video_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
    """获取视频评论"""
    data = await _request(
        "GET",
        "/api/v1/douyin/web/fetch_one_video_comment",
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
