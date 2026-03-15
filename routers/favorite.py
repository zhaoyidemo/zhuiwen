import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from services import tikhub_service, db_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/favorite", tags=["爆款收藏"])


@router.post("/add")
async def add_favorite(video_data: dict, db: AsyncSession = Depends(get_db)):
    """收藏视频（快照）"""
    if not video_data.get("aweme_id"):
        raise HTTPException(status_code=400, detail="缺少 aweme_id")
    try:
        result = await db_service.add_favorite(db, video_data)
        return result
    except Exception as e:
        logger.error(f"收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{aweme_id}")
async def remove_favorite(aweme_id: str, db: AsyncSession = Depends(get_db)):
    """取消收藏"""
    try:
        await db_service.remove_favorite(db, aweme_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"取消收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_favorites(db: AsyncSession = Depends(get_db)):
    """获取收藏列表"""
    try:
        favorites = await db_service.get_favorites(db)
        return {"favorites": favorites}
    except Exception as e:
        logger.warning(f"获取收藏列表失败: {e}")
        return {"favorites": []}


@router.post("/{aweme_id}/refresh")
async def refresh_favorite(aweme_id: str, db: AsyncSession = Depends(get_db)):
    """刷新收藏视频的最新数据"""
    try:
        video = await tikhub_service.fetch_video_by_id(aweme_id)
        video_data = jsonable_encoder(video)
        # 补充播放量
        if not video_data.get("play_count"):
            try:
                stats = await tikhub_service.fetch_video_statistics(aweme_id)
                play = stats.get("play_count", 0) or 0
                if play > 0:
                    video_data["play_count"] = play
                    collect = video_data.get("collect_count", 0) or 0
                    digg = video_data.get("digg_count", 0) or 0
                    comment = video_data.get("comment_count", 0) or 0
                    share = video_data.get("share_count", 0) or 0
                    video_data["collect_rate"] = round(collect / play, 6)
                    video_data["engagement_rate"] = round((digg + comment + share + collect) / play, 6)
            except Exception:
                pass
        await db_service.update_favorite(db, aweme_id, video_data)
        return {"ok": True, "data": video_data}
    except Exception as e:
        logger.error(f"刷新收藏失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
