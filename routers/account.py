import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from models.schemas import AccountAddRequest, AccountData
from services import tikhub_service, feishu_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["账号"])


@router.post("/add", response_model=AccountData)
async def add_account(req: AccountAddRequest):
    """添加竞品账号"""
    try:
        account = await tikhub_service.fetch_user_profile(req.unique_id)
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取用户信息失败: {str(e)}")

    account.category = req.category
    account.is_own_account = req.category in ("自己主号", "矩阵号")

    try:
        await feishu_service.save_account(account, category=req.category)
    except Exception as e:
        logger.warning(f"写入飞书失败: {e}")

    return account


@router.post("/{sec_user_id}/sync")
async def sync_account_videos(sec_user_id: str):
    """同步账号的所有视频数据"""
    try:
        videos = await tikhub_service.fetch_all_user_videos(sec_user_id)
    except Exception as e:
        logger.error(f"拉取视频失败: {e}")
        raise HTTPException(status_code=400, detail=f"拉取视频失败: {str(e)}")

    synced_count = 0
    try:
        if videos:
            await feishu_service.save_videos_batch(videos)
            synced_count = len(videos)
    except Exception as e:
        logger.warning(f"批量写入飞书失败: {e}")

    # 显式序列化 Pydantic 对象
    videos_data = jsonable_encoder(videos)
    logger.info(f"同步完成: {len(videos_data)} 条视频, 第一条: {videos_data[0].get('desc', '')[:30] if videos_data else 'N/A'}")

    return JSONResponse(content={
        "message": f"同步完成，共 {len(videos_data)} 条视频",
        "total": len(videos_data),
        "synced_to_feishu": synced_count,
        "videos": videos_data,
    })


@router.get("/list")
async def list_accounts():
    """获取已添加的账号列表"""
    try:
        accounts = await feishu_service.get_accounts()
        return {"accounts": accounts}
    except Exception as e:
        logger.warning(f"从飞书读取账号失败: {e}")
        return {"accounts": [], "error": str(e)}


@router.get("/{account_id}/videos")
async def get_account_videos(
    account_id: str,
    sort_by: str = Query("collect_rate", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
):
    """获取账号的视频列表（从飞书读取）"""
    try:
        videos = await feishu_service.get_account_videos(account_id)
    except Exception as e:
        logger.warning(f"从飞书读取视频失败: {e}")
        videos = []

    reverse = order == "desc"
    try:
        videos.sort(key=lambda v: v.get(sort_by, 0) or 0, reverse=reverse)
    except (TypeError, KeyError):
        pass

    return {"videos": videos, "total": len(videos)}


@router.get("/{sec_user_id}/xingtu")
async def get_account_xingtu(sec_user_id: str):
    """获取账号的星图（Xingtu）分析数据"""
    # 第一步：获取 kolId
    kol_result = await tikhub_service.fetch_xingtu_kol_id(sec_user_id)
    kol_id = ""
    if isinstance(kol_result, dict):
        kol_id = str(kol_result.get("kolId", "") or kol_result.get("kol_id", "") or "")
    if not kol_id:
        return JSONResponse(content={"error": "无法获取该账号的星图 kolId", "kol_id": "", "raw": kol_result})

    # 第二步：并发调用所有星图 API
    (
        fans_portrait,
        audience_portrait,
        data_overview,
        daily_fans,
        video_performance,
        xingtu_index,
        hot_comment_keywords,
    ) = await asyncio.gather(
        tikhub_service.fetch_kol_fans_portrait(kol_id),
        tikhub_service.fetch_kol_audience_portrait(kol_id),
        tikhub_service.fetch_kol_data_overview(kol_id),
        tikhub_service.fetch_kol_daily_fans(kol_id),
        tikhub_service.fetch_kol_video_performance(kol_id),
        tikhub_service.fetch_kol_xingtu_index(kol_id),
        tikhub_service.fetch_kol_hot_comment_keywords(kol_id),
    )

    return JSONResponse(content={
        "kol_id": kol_id,
        "fans_portrait": fans_portrait,
        "audience_portrait": audience_portrait,
        "data_overview": data_overview,
        "daily_fans": daily_fans,
        "video_performance": video_performance,
        "xingtu_index": xingtu_index,
        "hot_comment_keywords": hot_comment_keywords,
    })
