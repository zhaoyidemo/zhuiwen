import asyncio
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services import db_service, ai_service
from services.web_fetcher import fetch_page_text
from database import get_db, async_session

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
    """使用 Claude web search 搜索嘉宾采访资料（后台任务）"""
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    guest_name = guest["name"]
    guest_desc = guest["description"]

    async def _bg_search():
        try:
            # 读取自定义搜索策略提示词
            custom_search = ""
            async with async_session() as s:
                prompts = await db_service.get_ai_prompts(s)
                for p in prompts:
                    if p["name"] == "嘉宾搜索策略":
                        custom_search = p["content"]
                        break
            result = await ai_service.guest_web_search(guest_name, guest_desc, custom_search)
            search_results = result.get("search_results", [])

            async with async_session() as session:
                # 保存各条搜索结果
                saved_ids = []
                for sr in search_results:
                    url = sr.get("url", "")
                    if not url:
                        continue
                    mat = await db_service.add_guest_material(session, guest_id, {
                        "type": "search_result",
                        "platform": "网页",
                        "url": url,
                        "title": sr.get("title", ""),
                        "summary": sr.get("snippet", ""),
                        "raw_data": sr,
                        "status": "pending",
                    })
                    saved_ids.append((mat["id"], url))

                # AI 汇总单独标记为 ai_summary 类型（分析时降权）
                if result.get("summary"):
                    await db_service.add_guest_material(session, guest_id, {
                        "type": "ai_summary",
                        "title": f"AI 搜索汇总 - {guest_name}（仅供参考，可能含未经证实信息）",
                        "content": result["summary"],
                        "raw_data": {"type": "search_summary", "created_at": result.get("created_at", "")},
                        "status": "unverified",
                    })

            logger.info(f"嘉宾搜索完成: {guest_name}, {len(saved_ids)} 条链接，开始抓取验证...")

            # 逐个抓取链接全文并验证相关性
            verified = 0
            failed = 0
            unverified = 0
            for mat_id, url in saved_ids:
                content = await fetch_page_text(url)
                if not content:
                    # 抓取失败 → 标记 failed
                    async with async_session() as session:
                        await db_service.update_guest_material_status(session, mat_id, "failed")
                    failed += 1
                elif guest_name in content:
                    # 抓取成功 + 包含嘉宾姓名 → verified
                    async with async_session() as session:
                        await db_service.update_guest_material_content(session, mat_id, content, status="verified")
                    verified += 1
                else:
                    # 抓取成功但不含嘉宾姓名 → unverified
                    async with async_session() as session:
                        await db_service.update_guest_material_content(session, mat_id, content, status="unverified")
                    unverified += 1

            logger.info(f"嘉宾验证完成: {guest_name}, 验证通过{verified}, 未验证{unverified}, 抓取失败{failed}")
        except Exception as e:
            logger.error(f"嘉宾后台搜索失败: {e}", exc_info=True)

    asyncio.create_task(_bg_search())
    return {"ok": True, "message": "搜索已开始，请稍候刷新查看结果"}


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
async def analyze_guest_endpoint(guest_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    analysis_type = body.get("analysis_type", "research")
    if analysis_type not in ("research", "interview"):
        raise HTTPException(status_code=400, detail="无效的分析类型")

    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    materials = await db_service.get_guest_materials(db, guest_id)
    if not materials:
        raise HTTPException(status_code=400, detail="暂无资料，请先搜索或添加素材")

    guest_name = guest["name"]
    custom_prompt = body.get("prompt", "")

    # 递进式：采访策划时，自动获取已有的研究报告作为前序分析
    prior_analyses = []
    if analysis_type == "interview":
        all_analyses = await db_service.get_guest_analyses(db, guest_id)
        prior_analyses = [a for a in all_analyses if a["analysis_type"] == "research"]

    async def _bg_analyze():
        try:
            result = await ai_service.analyze_guest(
                guest_name=guest_name,
                materials=materials,
                analysis_type=analysis_type,
                custom_prompt=custom_prompt,
                prior_analyses=prior_analyses,
            )
            async with async_session() as session:
                await db_service.save_guest_analysis(session, guest_id, analysis_type, result)
            logger.info(f"嘉宾分析完成: {guest_name} - {analysis_type}")
        except Exception as e:
            logger.error(f"嘉宾后台分析失败: {e}", exc_info=True)

    asyncio.create_task(_bg_analyze())
    return {"ok": True, "message": "分析已开始，请稍候刷新查看结果"}


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


@router.post("/{guest_id}/chat")
async def guest_chat(guest_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    """对话预演：AI 扮演嘉宾进行模拟对话"""
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    materials = await db_service.get_guest_materials(db, guest_id)
    analyses = await db_service.get_guest_analyses(db, guest_id)

    reply = await ai_service.guest_chat(guest["name"], materials, analyses, message)
    return {"reply": reply}
