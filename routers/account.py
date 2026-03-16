import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import AccountAddRequest, AccountData
from services import tikhub_service, feishu_service, db_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["账号"])


@router.post("/add", response_model=AccountData)
async def add_account(req: AccountAddRequest, db: AsyncSession = Depends(get_db)):
    """添加竞品账号"""
    try:
        account = await tikhub_service.fetch_user_profile(req.unique_id)
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取用户信息失败: {str(e)}")

    account.category = req.category
    account.is_own_account = req.category in ("自己主号", "矩阵号")

    # 存入数据库
    try:
        await db_service.upsert_account(db, jsonable_encoder(account))
    except Exception as e:
        logger.warning(f"写入数据库失败: {e}")

    # 飞书备份（可选）
    try:
        await feishu_service.save_account(account, category=req.category)
    except Exception as e:
        logger.warning(f"写入飞书失败: {e}")

    return account


@router.get("/list")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """获取已添加的账号列表"""
    try:
        accounts = await db_service.get_accounts(db)
        return {"accounts": accounts}
    except Exception as e:
        logger.warning(f"从数据库读取账号失败: {e}")
        return {"accounts": [], "error": str(e)}


@router.delete("/{sec_user_id}")
async def remove_account(sec_user_id: str, db: AsyncSession = Depends(get_db)):
    """删除账号及关联视频"""
    try:
        await db_service.delete_account(db, sec_user_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"删除账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sec_user_id}/sync")
async def sync_account_videos(sec_user_id: str, db: AsyncSession = Depends(get_db)):
    """同步账号信息 + 所有视频数据"""
    account_update = None

    # 第一步：刷新账号信息（粉丝数等）
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
            logger.info(f"账号信息已刷新: {profile_data.get('nickname')}, 粉丝: {profile_data.get('follower_count')}")
    except Exception as e:
        logger.warning(f"刷新账号信息失败（不影响视频同步）: {e}")

    # 第二步：拉取视频列表
    try:
        videos = await tikhub_service.fetch_all_user_videos(sec_user_id)
    except Exception as e:
        logger.error(f"拉取视频失败: {e}")
        raise HTTPException(status_code=400, detail=f"拉取视频失败: {str(e)}")

    videos_data = jsonable_encoder(videos)

    # 存入数据库
    try:
        await db_service.upsert_videos_batch(db, sec_user_id, videos_data)
    except Exception as e:
        logger.warning(f"写入数据库失败: {e}")

    # 飞书备份（可选）
    try:
        if videos:
            await feishu_service.save_videos_batch(videos)
    except Exception as e:
        logger.warning(f"批量写入飞书失败: {e}")

    logger.info(f"同步完成: {len(videos_data)} 条视频, 第一条: {videos_data[0].get('desc', '')[:30] if videos_data else 'N/A'}")

    return JSONResponse(content={
        "message": f"同步完成，共 {len(videos_data)} 条视频",
        "total": len(videos_data),
        "videos": videos_data,
        "account": account_update,
    })


@router.get("/{sec_user_id}/videos")
async def get_account_videos(
    sec_user_id: str,
    sort_by: str = Query("collect_rate", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
    db: AsyncSession = Depends(get_db),
):
    """获取账号的视频列表（从数据库读取）"""
    try:
        videos = await db_service.get_account_videos(db, sec_user_id, sort_by, order)
    except Exception as e:
        logger.warning(f"从数据库读取视频失败: {e}")
        videos = []

    return {"videos": videos, "total": len(videos)}


async def _get_kol_id(sec_user_id: str, db: AsyncSession) -> str:
    """获取星图 kolId，优先从缓存取"""
    cached = await db_service.get_account_xingtu(db, sec_user_id)
    if cached and cached.get("data", {}).get("kol_id"):
        return cached["data"]["kol_id"]
    kol_result = await tikhub_service.fetch_xingtu_kol_id(sec_user_id)
    logger.info(f"星图 kolId 原始返回: {kol_result}")
    kol_id = ""
    if isinstance(kol_result, dict):
        base_resp = kol_result.get("base_resp", {})
        sc = kol_result.get("status_code", base_resp.get("status_code", 0))
        if sc and sc != 0 and not kol_result.get("id"):
            return ""
        kol_id = str(kol_result.get("kolId", "") or kol_result.get("kol_id", "")
                     or kol_result.get("kolid", "") or kol_result.get("id", "") or "")
    elif isinstance(kol_result, (str, int)) and kol_result:
        kol_id = str(kol_result)
    return kol_id


@router.get("/{sec_user_id}/xingtu/portrait")
async def get_xingtu_portrait(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    """粉丝画像"""
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("fans_portrait"):
            return JSONResponse(content={"fans_portrait": cached["data"]["fans_portrait"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_fans_portrait(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "fans_portrait", data, kol_id)
    return JSONResponse(content={"fans_portrait": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/index")
async def get_xingtu_index(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    """星图指数"""
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("xingtu_index"):
            return JSONResponse(content={"xingtu_index": cached["data"]["xingtu_index"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_xingtu_index(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "xingtu_index", data, kol_id)
    return JSONResponse(content={"xingtu_index": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/cp")
async def get_xingtu_cp(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    """性价比分析"""
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("cp_info"):
            return JSONResponse(content={"cp_info": cached["data"]["cp_info"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_cp_info(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "cp_info", data, kol_id)
    return JSONResponse(content={"cp_info": data or {}, "cached_at": ""})


@router.get("/{sec_user_id}/xingtu/price")
async def get_xingtu_price(sec_user_id: str, refresh: bool = False, db: AsyncSession = Depends(get_db)):
    """商单报价"""
    if not refresh:
        cached = await db_service.get_account_xingtu(db, sec_user_id)
        if cached and cached["data"].get("service_price"):
            return JSONResponse(content={"service_price": cached["data"]["service_price"], "cached_at": cached["updated_at"]})
    kol_id = await _get_kol_id(sec_user_id, db)
    if not kol_id:
        raise HTTPException(status_code=400, detail="该账号未加入星图或无法获取 kolId")
    data = await tikhub_service.fetch_kol_service_price(kol_id)
    if data:
        await db_service.update_account_xingtu_module(db, sec_user_id, "service_price", data, kol_id)
    return JSONResponse(content={"service_price": data or {}, "cached_at": ""})
