import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_models import AccountAddRequest, ok
from services import tikhub_service, feishu_service, db_service, task_service
from database import get_db, async_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/accounts", tags=["竞品雷达"])


@router.post("",
    summary="添加账号",
    description="通过抖音号（unique_id）添加竞品或自有账号，自动获取账号信息和粉丝数")
async def add_account(req: AccountAddRequest, db: AsyncSession = Depends(get_db)):
    try:
        account = await tikhub_service.fetch_user_profile(req.unique_id)
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取用户信息失败: {str(e)}")

    account.category = req.category
    account.is_own_account = req.category in ("自己主号", "矩阵号")

    try:
        result = await db_service.upsert_account(db, jsonable_encoder(account))
    except Exception as e:
        logger.warning(f"写入数据库失败: {e}")
        result = jsonable_encoder(account)

    try:
        await feishu_service.save_account(account, category=req.category)
    except Exception as e:
        logger.warning(f"写入飞书失败: {e}")

    return ok(result)


@router.get("",
    summary="账号列表",
    description="获取所有已添加的账号，含视频统计数据（平均收藏率、最高互动率等）")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    try:
        accounts = await db_service.get_accounts(db)
        return ok({"accounts": accounts})
    except Exception as e:
        logger.warning(f"从数据库读取账号失败: {e}")
        return ok({"accounts": []})


@router.delete("/{sec_user_id}",
    summary="删除账号",
    description="删除账号及其所有关联视频数据")
async def remove_account(sec_user_id: str, db: AsyncSession = Depends(get_db)):
    await db_service.delete_account(db, sec_user_id)
    return ok()


@router.post("/{sec_user_id}/sync",
    summary="同步视频",
    description="后台同步账号的所有视频数据。返回 task_id，可通过 /api/tasks/{task_id} 查询进度")
async def sync_account_videos(sec_user_id: str, db: AsyncSession = Depends(get_db)):
    account_update = None

    # 刷新账号信息（同步，很快）
    try:
        existing = await db_service.get_account_by_sec_user_id(db, sec_user_id)
        if existing and existing.get("unique_id"):
            profile = await tikhub_service.fetch_user_profile(existing["unique_id"])
            profile_data = jsonable_encoder(profile)
            profile_data["sec_user_id"] = sec_user_id
            profile_data["category"] = existing.get("category", "竞品")
            profile_data["is_own_account"] = existing.get("is_own_account", False)
            await db_service.upsert_account(db, profile_data)
            account_update = profile_data
    except Exception as e:
        logger.warning(f"刷新账号信息失败: {e}")

    task_id = task_service.create_task(f"同步视频: {sec_user_id}")

    async def _bg_sync():
        try:
            task_service.update_progress(task_id, "正在获取视频列表...")
            videos = await tikhub_service.fetch_all_user_videos(sec_user_id)
            videos_data = jsonable_encoder(videos)
            task_service.update_progress(task_id, f"正在写入数据库（{len(videos_data)}条）...")
            async with async_session() as bg_db:
                await db_service.upsert_videos_batch(bg_db, sec_user_id, videos_data)
            # 标记已删除/隐藏的视频
            active_ids = {v.get("aweme_id", "") for v in videos_data if v.get("aweme_id")}
            async with async_session() as bg_db:
                marked = await db_service.mark_deleted_videos(bg_db, sec_user_id, active_ids)
            task_service.complete_task(task_id, {"total": len(videos_data), "marked_deleted": marked})
            logger.info(f"同步完成: {len(videos_data)} 条视频")
            try:
                if videos:
                    await feishu_service.save_videos_batch(videos)
            except Exception as e:
                logger.warning(f"批量写入飞书失败: {e}")
        except Exception as e:
            logger.error(f"后台视频同步失败: {e}")
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg_sync())

    return ok({
        "task_id": task_id,
        "account": account_update,
        "message": "同步已开始，视频数据将在后台更新",
    })


@router.get("/{sec_user_id}/videos",
    summary="账号视频列表",
    description="获取某个账号的所有视频，支持按收藏率、互动率、播放量等排序")
async def get_account_videos(
    sec_user_id: str,
    sort_by: str = Query("collect_rate", description="排序字段：collect_rate/engagement_rate/play_count/create_time"),
    order: str = Query("desc", description="排序方向：desc/asc"),
    db: AsyncSession = Depends(get_db),
):
    try:
        videos = await db_service.get_account_videos(db, sec_user_id, sort_by, order)
    except Exception as e:
        logger.warning(f"从数据库读取视频失败: {e}")
        videos = []
    return ok({"videos": videos, "total": len(videos)})


# ---- 星图数据 ----

async def _get_kol_id(sec_user_id: str, db: AsyncSession) -> str:
    """获取星图 kolId，优先从缓存取"""
    cached = await db_service.get_account_xingtu(db, sec_user_id)
    if cached:
        data = cached.get("data") or {}
        if "kol_id" in data:
            return data["kol_id"]
    kol_result = await tikhub_service.fetch_xingtu_kol_id(sec_user_id)
    kol_id = ""
    if isinstance(kol_result, dict):
        base_resp = kol_result.get("base_resp", {})
        sc = kol_result.get("status_code", base_resp.get("status_code", 0))
        if sc and sc != 0 and not kol_result.get("id"):
            await db_service.update_account_xingtu_module(db, sec_user_id, "_xingtu_checked", True, kol_id="")
            return ""
        kol_id = str(kol_result.get("kolId", "") or kol_result.get("kol_id", "")
                     or kol_result.get("kolid", "") or kol_result.get("id", "") or "")
    elif isinstance(kol_result, (str, int)) and kol_result:
        kol_id = str(kol_result)
    return kol_id


@router.get("/{sec_user_id}/xingtu/portrait",
    summary="粉丝画像",
    description="获取星图粉丝画像数据（性别、年龄、地域分布等），支持缓存")
async def get_xingtu_portrait(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("fans_portrait"):
            return ok({"fans_portrait": cached["data"]["fans_portrait"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_fans_portrait(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "fans_portrait", data, kol_id)
    return ok({"fans_portrait": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/index",
    summary="星图指数",
    description="获取星图综合指数（传播力、合作力、种草力、涨粉力等）")
async def get_xingtu_index(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("xingtu_index"):
            return ok({"xingtu_index": cached["data"]["xingtu_index"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_xingtu_index(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "xingtu_index", data, kol_id)
    return ok({"xingtu_index": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/cp",
    summary="性价比分析",
    description="获取星图性价比数据（预估CPE、CPM、播放量等）")
async def get_xingtu_cp(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("cp_info"):
            return ok({"cp_info": cached["data"]["cp_info"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_cp_info(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "cp_info", data, kol_id)
    return ok({"cp_info": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/price",
    summary="商单报价",
    description="获取星图商单报价（视频报价、直播报价等）")
async def get_xingtu_price(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("service_price"):
            return ok({"service_price": cached["data"]["service_price"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_service_price(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "service_price", data, kol_id)
    return ok({"service_price": data or {}, "cached_at": ""})
