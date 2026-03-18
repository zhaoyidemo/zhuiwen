import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from services import tikhub_service, db_service, ai_service, video_processor
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


@router.post("/{aweme_id}/analyze")
async def analyze_favorite(aweme_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """AI 分析收藏的视频"""
    prompt = body.get("prompt", "")
    video_data = body.get("video_data", {})
    if not video_data:
        raise HTTPException(status_code=400, detail="缺少视频数据")

    # 获取评论
    comments = []
    try:
        comment_data = await tikhub_service.fetch_video_comments(aweme_id, cursor=0, count=50)
        comments = comment_data.get("comments", [])
    except Exception as e:
        logger.warning(f"获取评论失败（不影响分析）: {e}")

    # 调用 Claude Opus
    try:
        analysis = await ai_service.analyze_single_video(
            video=video_data,
            comments=comments,
            prompt=prompt or None,
        )
        # 保存到收藏记录
        await db_service.save_ai_analysis(db, aweme_id, analysis)
        return analysis
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{aweme_id}/analyze-first5s")
async def analyze_first5s(aweme_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """前5秒截帧分析"""
    try:
        video_data = body.get("video_data", {})
        custom_prompt = body.get("prompt", "")
        if not video_data:
            raise HTTPException(status_code=400, detail="缺少视频数据")

        # 总是先从 TikHub 获取最新视频链接（CDN URL 几小时就过期）
        logger.info(f"前5秒分析开始: aweme_id={aweme_id}")
        video_url = ""
        try:
            fresh_video = await tikhub_service.fetch_video_by_id(aweme_id)
            video_url = getattr(fresh_video, 'video_url', '') if fresh_video else ""
        except Exception as e:
            logger.warning(f"获取最新视频链接失败: {e}")

        # 回退到收藏时保存的 URL
        if not video_url:
            video_url = video_data.get("video_url", "")

        if not video_url:
            raise HTTPException(status_code=400, detail="该视频没有可用的视频链接")

        # 截帧
        frames = await video_processor.extract_first_frames(video_url, seconds=5, fps=1)
        if not frames:
            raise HTTPException(status_code=500, detail="截帧失败，请稍后重试")

        logger.info(f"前5秒截帧完成: {len(frames)} 帧, aweme_id={aweme_id}")

        # Claude Vision 分析
        analysis = await ai_service.analyze_first_5s(
            video=video_data, frame_data_uris=frames, custom_prompt=custom_prompt
        )

        # 保存分析结果（不含 frames base64，太大）
        try:
            await db_service.save_ai_analysis(db, aweme_id, analysis, analysis_type="first5s")
        except Exception as e:
            logger.warning(f"保存前5秒分析结果失败: {e}")

        return {**analysis, "frames": frames}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"前5秒分析未捕获异常: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# ---- 提示词管理 ----

@router.get("/prompts")
async def list_prompts(db: AsyncSession = Depends(get_db)):
    """获取提示词列表（数据库 + 默认模板）"""
    db_prompts = await db_service.get_ai_prompts(db)
    db_names = {p["name"] for p in db_prompts}
    # 补充默认模板（未被用户覆盖的）
    for name, content in ai_service.DEFAULT_PROMPTS.items():
        if name not in db_names:
            db_prompts.append({"id": None, "name": name, "content": content, "is_default": True})
    return {"prompts": db_prompts}


@router.post("/prompts")
async def save_prompt(body: dict, db: AsyncSession = Depends(get_db)):
    """保存/更新提示词"""
    name = body.get("name", "").strip()
    content = body.get("content", "").strip()
    if not name or not content:
        raise HTTPException(status_code=400, detail="名称和内容不能为空")
    result = await db_service.upsert_ai_prompt(db, name, content)
    return result


@router.delete("/prompts/{name}")
async def delete_prompt(name: str, db: AsyncSession = Depends(get_db)):
    """删除提示词"""
    await db_service.delete_ai_prompt(db, name)
    return {"ok": True}
