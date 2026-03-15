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
    """同步账号的所有视频数据"""
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


@router.get("/{sec_user_id}/xingtu")
async def get_account_xingtu(sec_user_id: str):
    """获取账号的星图（Xingtu）分析数据"""
    # 第一步：获取 kolId
    kol_result = await tikhub_service.fetch_xingtu_kol_id(sec_user_id)
    logger.info(f"星图 kolId 原始返回: {kol_result}")
    kol_id = ""
    if isinstance(kol_result, dict):
        base_resp = kol_result.get("base_resp", {})
        sc = kol_result.get("status_code", base_resp.get("status_code", 0))
        if sc and sc != 0 and not kol_result.get("id"):
            msg = (kol_result.get("status_message_zh") or kol_result.get("status_message")
                   or base_resp.get("status_message") or "未知错误")
            return JSONResponse(content={"error": f"该账号未加入星图: {msg}", "kol_id": ""})
        kol_id = str(kol_result.get("kolId", "") or kol_result.get("kol_id", "")
                     or kol_result.get("kolid", "") or kol_result.get("id", "") or "")
    elif isinstance(kol_result, (str, int)) and kol_result:
        kol_id = str(kol_result)
    if not kol_id:
        return JSONResponse(content={"error": "无法获取该账号的星图 kolId", "kol_id": ""})

    # 第二步：并发调用星图 API（部分失败不影响整体）
    results = await asyncio.gather(
        tikhub_service.fetch_kol_fans_portrait(kol_id),
        tikhub_service.fetch_kol_xingtu_index(kol_id),
        tikhub_service.fetch_kol_service_price(kol_id),
        tikhub_service.fetch_kol_cp_info(kol_id),
        tikhub_service.fetch_kol_convert_video_display(kol_id),
        return_exceptions=True,
    )
    # 异常结果替换为空值
    cleaned = []
    labels = ["fans_portrait", "xingtu_index", "service_price", "cp_info", "convert_videos"]
    defaults = [{}, {}, {}, {}, []]
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning(f"星图 {labels[i]} 失败: {r}")
            cleaned.append(defaults[i])
        else:
            cleaned.append(r)

    return JSONResponse(content={
        "kol_id": kol_id,
        "fans_portrait": cleaned[0],
        "xingtu_index": cleaned[1],
        "service_price": cleaned[2],
        "cp_info": cleaned[3],
        "convert_videos": cleaned[4],
    })
