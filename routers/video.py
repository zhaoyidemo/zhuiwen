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


@router.post("/batch-stats")
async def batch_video_stats(aweme_ids: list[str]):
    """批量获取视频播放量（每次建议传2个ID）"""
    if not aweme_ids:
        return JSONResponse(content={"stats": {}})
    ids_str = ",".join(aweme_ids[:5])  # 最多5个
    try:
        stats = await tikhub_service.fetch_video_statistics(ids_str)
        # fetch_video_statistics 返回第一条，改为返回全部
        data = await tikhub_service._request(
            "GET",
            "/api/v1/douyin/app/v3/fetch_video_statistics",
            params={"aweme_ids": ids_str},
        )
        stats_list = data.get("data", {}).get("statistics_list", []) or []
        result = {}
        for s in stats_list:
            if isinstance(s, dict) and s.get("aweme_id"):
                result[str(s["aweme_id"])] = {
                    "play_count": s.get("play_count", 0) or 0,
                    "digg_count": s.get("digg_count", 0) or 0,
                    "share_count": s.get("share_count", 0) or 0,
                }
        return JSONResponse(content={"stats": result})
    except Exception as e:
        logger.warning(f"批量统计失败: {e}")
        return JSONResponse(content={"stats": {}})


@router.get("/{aweme_id}/extended")
async def get_video_extended(aweme_id: str, duration: int = 0):
    """获取视频扩展数据：评论热词、弹幕"""
    result = {"comments": [], "danmaku": []}

    # 拉取评论（已验证可用的接口）
    try:
        comment_data = await tikhub_service.fetch_video_comments(aweme_id, cursor=0, count=50)
        result["comments"] = comment_data.get("comments", [])
    except Exception as e:
        logger.warning(f"评论获取失败: {e}")

    # 拉取弹幕
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
