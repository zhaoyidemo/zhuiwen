import logging
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models.schemas import VideoParseRequest, VideoData
from services import tikhub_service, feishu_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["视频"])


@router.post("/parse", response_model=VideoData)
async def parse_video(req: VideoParseRequest):
    """解析单个抖音视频链接，获取完整数据并写入飞书"""
    try:
        video = await tikhub_service.parse_and_fetch_video(req.url)
    except Exception as e:
        logger.error(f"视频解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"视频解析失败: {str(e)}")

    # 异步写入飞书（不阻塞返回）
    try:
        await feishu_service.save_video(video)
    except Exception as e:
        logger.warning(f"写入飞书失败（不影响返回）: {e}")

    return video


@router.get("/{aweme_id}/extended")
async def get_video_extended(aweme_id: str):
    """获取视频扩展数据：数据趋势、评论词云、弹幕"""
    result = {"trends": [], "word_cloud": [], "danmaku": []}
    try:
        trends = await tikhub_service.fetch_video_trends(aweme_id)
        if isinstance(trends, list):
            result["trends"] = trends
    except Exception as e:
        logger.warning(f"趋势数据获取失败: {e}")
    try:
        word_cloud = await tikhub_service.fetch_comment_word_cloud(aweme_id)
        if isinstance(word_cloud, list):
            result["word_cloud"] = word_cloud
    except Exception as e:
        logger.warning(f"词云数据获取失败: {e}")
    try:
        danmaku = await tikhub_service.fetch_video_danmaku(aweme_id)
        if isinstance(danmaku, list):
            result["danmaku"] = danmaku
    except Exception as e:
        logger.warning(f"弹幕数据获取失败: {e}")
    logger.info(f"Extended: trends={len(result['trends'])}, wc={len(result['word_cloud'])}, dm={len(result['danmaku'])}")
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
