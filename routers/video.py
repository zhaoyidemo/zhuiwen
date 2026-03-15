import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import VideoParseRequest, VideoData
from services import tikhub_service, feishu_service, db_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["视频"])


@router.post("/parse", response_model=VideoData)
async def parse_video(req: VideoParseRequest, db: AsyncSession = Depends(get_db)):
    """解析单个抖音视频链接，获取完整数据并写入数据库"""
    try:
        video = await tikhub_service.parse_and_fetch_video(req.url)
    except Exception as e:
        logger.error(f"视频解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"视频解析失败: {str(e)}")

    # 存入视频历史
    try:
        from fastapi.encoders import jsonable_encoder
        await db_service.save_video_history(db, jsonable_encoder(video))
    except Exception as e:
        logger.warning(f"写入视频历史失败: {e}")

    # 飞书备份（可选）
    try:
        await feishu_service.save_video(video)
    except Exception as e:
        logger.warning(f"写入飞书失败（不影响返回）: {e}")

    return video


@router.post("/batch-stats")
async def batch_video_stats(aweme_ids: list[str], db: AsyncSession = Depends(get_db)):
    """批量获取视频播放量（每次建议传2个ID）"""
    if not aweme_ids:
        return JSONResponse(content={"stats": {}})
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
        # 只更新 play_count，collect_rate/engagement_rate 用 SQL 从现有数据计算
        if play_updates:
            try:
                await db_service.batch_update_play_count(db, play_updates)
            except Exception as e:
                logger.warning(f"更新数据库播放量失败: {e}")

        return JSONResponse(content={"stats": result})
    except Exception as e:
        logger.warning(f"批量统计失败: {e}")
        return JSONResponse(content={"stats": {}})


@router.get("/history")
async def get_video_history(db: AsyncSession = Depends(get_db)):
    """获取视频解析历史"""
    try:
        history = await db_service.get_video_history(db, limit=50)
        return {"history": history}
    except Exception as e:
        logger.warning(f"获取视频历史失败: {e}")
        return {"history": []}


@router.delete("/history")
async def clear_video_history(db: AsyncSession = Depends(get_db)):
    """清空视频解析历史"""
    try:
        await db_service.clear_video_history(db)
        return {"ok": True}
    except Exception as e:
        logger.warning(f"清空视频历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{aweme_id}/extended")
async def get_video_extended(aweme_id: str, duration: int = 0):
    """获取视频扩展数据：评论热词、弹幕"""
    result = {"comments": [], "danmaku": []}

    try:
        comment_data = await tikhub_service.fetch_video_comments(aweme_id, cursor=0, count=50)
        result["comments"] = comment_data.get("comments", [])
    except Exception as e:
        logger.warning(f"评论获取失败: {e}")

    try:
        danmaku = await tikhub_service.fetch_video_danmaku(aweme_id, duration=duration)
        if isinstance(danmaku, list):
            result["danmaku"] = danmaku
    except Exception as e:
        logger.warning(f"弹幕获取失败: {e}")

    logger.info(f"Extended: comments={len(result['comments'])}, danmaku={len(result['danmaku'])}")
    return JSONResponse(content=result)


@router.get("/{aweme_id}", response_model=VideoData)
async def get_video(aweme_id: str):
    """通过 aweme_id 获取视频数据"""
    try:
        video = await tikhub_service.fetch_video_by_id(aweme_id)
        return video
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取视频失败: {str(e)}")
