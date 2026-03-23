import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_models import VideoParseRequest, ok
from services import tikhub_service, feishu_service, db_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["视频分析"])


@router.post("/parse",
    summary="解析抖音视频",
    description="解析单个抖音视频链接，获取完整数据（封面、作者、互动数据等）并存入历史记录")
async def parse_video(req: VideoParseRequest, db: AsyncSession = Depends(get_db)):
    try:
        video = await tikhub_service.parse_and_fetch_video(req.url)
    except Exception as e:
        logger.error(f"视频解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"视频解析失败: {str(e)}")

    try:
        await db_service.save_video_history(db, jsonable_encoder(video))
    except Exception as e:
        logger.warning(f"写入视频历史失败: {e}")

    try:
        await feishu_service.save_video(video)
    except Exception as e:
        logger.warning(f"写入飞书失败: {e}")

    return ok(jsonable_encoder(video))


@router.post("/batch-stats",
    summary="批量获取播放量",
    description="批量获取视频播放量统计，每次建议传2个ID，自动更新数据库中的收藏率和互动率")
async def batch_video_stats(aweme_ids: list[str], db: AsyncSession = Depends(get_db)):
    if not aweme_ids:
        return ok({"stats": {}})
    ids_str = ",".join(aweme_ids[:5])
    try:
        data = await tikhub_service._request(
            "GET",
            "/api/v1/douyin/app/v3/fetch_video_statistics",
            params={"aweme_ids": ids_str},
        )
        stats_list = data.get("data", {}).get("statistics_list", []) or []
        result = {}
        play_updates = {}
        for s in stats_list:
            if isinstance(s, dict) and s.get("aweme_id"):
                aid = str(s["aweme_id"])
                play = s.get("play_count", 0) or 0
                result[aid] = {
                    "play_count": play,
                    "digg_count": s.get("digg_count", 0) or 0,
                    "share_count": s.get("share_count", 0) or 0,
                }
                if play > 0:
                    play_updates[aid] = play
        if play_updates:
            try:
                await db_service.batch_update_play_count(db, play_updates)
            except Exception as e:
                logger.warning(f"更新数据库播放量失败: {e}")
        return ok({"stats": result})
    except Exception as e:
        logger.warning(f"批量统计失败: {e}")
        return ok({"stats": {}})


@router.get("/history",
    summary="解析历史",
    description="获取最近50条视频解析历史记录")
async def get_video_history(db: AsyncSession = Depends(get_db)):
    try:
        history = await db_service.get_video_history(db, limit=50)
        return ok({"history": history})
    except Exception as e:
        logger.warning(f"获取视频历史失败: {e}")
        return ok({"history": []})


@router.delete("/history",
    summary="清空历史",
    description="清空所有视频解析历史记录")
async def clear_video_history(db: AsyncSession = Depends(get_db)):
    await db_service.clear_video_history(db)
    return ok()


@router.get("/{aweme_id}/comments",
    summary="视频评论",
    description="获取视频评论列表（按热度排序，最多50条）")
async def get_video_comments(aweme_id: str, duration: int = 0):
    try:
        comment_data = await tikhub_service.fetch_video_comments(aweme_id, cursor=0, count=50)
        return ok({"comments": comment_data.get("comments", [])})
    except Exception as e:
        logger.warning(f"评论获取失败: {e}")
        return ok({"comments": []})


@router.get("/{aweme_id}/comment-replies",
    summary="评论回复",
    description="获取某条评论的回复列表，支持分页")
async def get_comment_replies(aweme_id: str, comment_id: str, cursor: int = 0):
    try:
        result = await tikhub_service.fetch_comment_replies(aweme_id, comment_id, cursor=cursor, count=20)
        return ok(result)
    except Exception as e:
        logger.warning(f"评论回复获取失败: {e}")
        return ok({"replies": [], "has_more": False})


@router.get("/{aweme_id}",
    summary="获取视频",
    description="通过 aweme_id 获取单个视频的完整数据")
async def get_video(aweme_id: str):
    try:
        video = await tikhub_service.fetch_video_by_id(aweme_id)
        return ok(jsonable_encoder(video))
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取视频失败: {str(e)}")
