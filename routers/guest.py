import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services import db_service, ai_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/guest", tags=["嘉宾研究"])


@router.post("")
async def create_guest(body: dict, db: AsyncSession = Depends(get_db)):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="嘉宾名称不能为空")
    description = body.get("description", "").strip()
    guest = await db_service.create_guest(db, name, description)
    return guest


@router.get("/list")
async def list_guests(db: AsyncSession = Depends(get_db)):
    try:
        guests = await db_service.get_guests(db)
        return {"guests": guests}
    except Exception as e:
        logger.warning(f"获取嘉宾列表失败: {e}")
        return {"guests": []}


@router.delete("/{guest_id}")
async def delete_guest(guest_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest(db, guest_id)
    return {"ok": True}


@router.get("/{guest_id}/materials")
async def list_materials(guest_id: int, db: AsyncSession = Depends(get_db)):
    try:
        materials = await db_service.get_guest_materials(db, guest_id)
        return {"materials": materials}
    except Exception as e:
        logger.warning(f"获取素材失败: {e}")
        return {"materials": []}


@router.post("/{guest_id}/search")
async def search_guest(guest_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    """使用 Claude web search 搜索嘉宾采访资料"""
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    try:
        result = await ai_service.guest_web_search(guest["name"], guest["description"])

        saved_materials = []
        # 将搜索汇总存为一条素材
        if result.get("summary"):
            mat = await db_service.add_guest_material(db, guest_id, {
                "type": "search_result",
                "title": f"网络搜索汇总 - {guest['name']}",
                "content": result["summary"],
                "raw_data": {"type": "search_summary", "created_at": result.get("created_at", "")},
            })
            saved_materials.append(mat)

        return {"summary": result.get("summary", ""), "materials": saved_materials}
    except Exception as e:
        logger.error(f"嘉宾搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guest_id}/material")
async def add_material(guest_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")
    mat = await db_service.add_guest_material(db, guest_id, {
        "type": "manual_link",
        "platform": body.get("platform", ""),
        "url": url,
        "title": body.get("title", "") or url,
    })
    return mat


@router.delete("/{guest_id}/material/{material_id}")
async def delete_material(guest_id: int, material_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest_material(db, material_id)
    return {"ok": True}


@router.post("/{guest_id}/analyze")
async def analyze_guest(guest_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    analysis_type = body.get("analysis_type", "archive")
    if analysis_type not in ("archive", "portrait", "topic", "interview"):
        raise HTTPException(status_code=400, detail="无效的分析类型")

    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    materials = await db_service.get_guest_materials(db, guest_id)
    if not materials:
        raise HTTPException(status_code=400, detail="暂无资料，请先搜索或添加素材")

    result = await ai_service.analyze_guest(
        guest_name=guest["name"],
        materials=materials,
        analysis_type=analysis_type,
        custom_prompt=body.get("prompt", ""),
    )
    saved = await db_service.save_guest_analysis(db, guest_id, analysis_type, result)
    return saved


@router.get("/{guest_id}/analyses")
async def list_analyses(guest_id: int, db: AsyncSession = Depends(get_db)):
    try:
        analyses = await db_service.get_guest_analyses(db, guest_id)
        return {"analyses": analyses}
    except Exception as e:
        logger.warning(f"获取分析结果失败: {e}")
        return {"analyses": []}


@router.delete("/{guest_id}/analysis/{analysis_id}")
async def delete_analysis(guest_id: int, analysis_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest_analysis(db, analysis_id)
    return {"ok": True}
