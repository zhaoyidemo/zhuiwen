import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_models import PromptSaveRequest, AnalyzeRequest, ok
from services import tikhub_service, db_service, ai_service, video_processor
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/favorites", tags=["爆款收藏"])


@router.post("",
    summary="收藏视频",
    description="将视频数据快照保存到收藏列表")
async def add_favorite(video_data: dict, db: AsyncSession = Depends(get_db)):
    if not video_data.get("aweme_id"):
        raise HTTPException(status_code=400, detail="缺少 aweme_id")
    result = await db_service.add_favorite(db, video_data)
    return ok(result)


@router.delete("/{aweme_id}",
    summary="取消收藏",
    description="从收藏列表中移除指定视频")
async def remove_favorite(aweme_id: str, db: AsyncSession = Depends(get_db)):
    await db_service.remove_favorite(db, aweme_id)
    return ok()


@router.get("",
    summary="收藏列表",
    description="获取所有收藏的视频及其 AI 分析结果")
async def list_favorites(db: AsyncSession = Depends(get_db)):
    try:
        favorites = await db_service.get_favorites(db)
        return ok({"favorites": favorites})
    except Exception as e:
        logger.warning(f"获取收藏列表失败: {e}")
        return ok({"favorites": []})


@router.post("/{aweme_id}/refresh",
    summary="刷新收藏数据",
    description="重新获取收藏视频的最新播放量、互动数据")
async def refresh_favorite(aweme_id: str, db: AsyncSession = Depends(get_db)):
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
        return ok({"data": video_data})
    except Exception as e:
        logger.error(f"刷新收藏失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aweme_id}/analyze",
    summary="AI 分析视频",
    description="使用 Claude Opus 对收藏的视频进行全方位深度分析（选题、文案、数据、评论）")
async def analyze_favorite(aweme_id: str, body: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    video_data = body.video_data
    if not video_data:
        raise HTTPException(status_code=400, detail="缺少视频数据")

    comments = []
    try:
        comment_data = await tikhub_service.fetch_video_comments(aweme_id, cursor=0, count=50)
        comments = comment_data.get("comments", [])
    except Exception as e:
        logger.warning(f"获取评论失败: {e}")

    analysis = await ai_service.analyze_single_video(
        video=video_data, comments=comments, prompt=body.prompt or None,
    )
    await db_service.save_ai_analysis(db, aweme_id, analysis)
    return ok(analysis)


@router.post("/{aweme_id}/analyze-first5s",
    summary="前5秒截帧分析",
    description="用 ffmpeg 截取视频前5秒帧，通过 Claude Vision 分析钩子策略、留存效果")
async def analyze_first5s(aweme_id: str, body: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    video_data = body.video_data
    if not video_data:
        raise HTTPException(status_code=400, detail="缺少视频数据")

    # 获取最新视频链接
    video_url = ""
    try:
        fresh_video = await tikhub_service.fetch_video_by_id(aweme_id)
        video_url = getattr(fresh_video, 'video_url', '') if fresh_video else ""
    except Exception as e:
        logger.warning(f"获取最新视频链接失败: {e}")
    if not video_url:
        video_url = video_data.get("video_url", "")
    if not video_url:
        raise HTTPException(status_code=400, detail="该视频没有可用的视频链接")

    frames = await video_processor.extract_first_frames(video_url, seconds=5, fps=1)
    if not frames:
        raise HTTPException(status_code=500, detail="截帧失败，请稍后重试")

    analysis = await ai_service.analyze_first_5s(
        video=video_data, frame_data_uris=frames, custom_prompt=body.prompt or ""
    )

    try:
        await db_service.save_ai_analysis(db, aweme_id, analysis, analysis_type="first5s")
    except Exception as e:
        logger.warning(f"保存前5秒分析结果失败: {e}")

    return ok({**analysis, "frames": frames})


# ---- 提示词管理 ----

@router.get("/prompts",
    summary="提示词列表",
    description="获取所有 AI 提示词（含系统内置默认模板和用户自定义）",
    tags=["提示词管理"])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    db_prompts = await db_service.get_ai_prompts(db)
    db_names = {p["name"] for p in db_prompts}
    for name, content in ai_service.DEFAULT_PROMPTS.items():
        if name not in db_names:
            db_prompts.append({"id": None, "name": name, "content": content, "is_default": True})
    return ok({"prompts": db_prompts})


@router.post("/prompts",
    summary="保存提示词",
    description="创建或更新一个提示词（按名称去重）",
    tags=["提示词管理"])
async def save_prompt(body: PromptSaveRequest, db: AsyncSession = Depends(get_db)):
    result = await db_service.upsert_ai_prompt(db, body.name, body.content)
    return ok(result)


@router.delete("/prompts/{name}",
    summary="删除提示词",
    description="删除指定名称的提示词",
    tags=["提示词管理"])
async def delete_prompt(name: str, db: AsyncSession = Depends(get_db)):
    await db_service.delete_ai_prompt(db, name)
    return ok()
