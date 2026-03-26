import asyncio
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_models import (
    GuestCreateRequest, GuestSearchRequest, MaterialAddRequest,
    MaterialUpdateRequest, GuestAnalyzeRequest, GuestChatRequest, ok,
)
from services import db_service, ai_service, task_service, tikhub_service
from services.web_fetcher import fetch_page_text, extract_urls_from_text
from database import get_db, async_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/guests", tags=["嘉宾研究"])


# ---- 嘉宾 CRUD ----

@router.post("",
    summary="创建嘉宾",
    description="创建嘉宾档案，需提供姓名和身份描述（用于搜索去重和 AI 分析上下文）")
async def create_guest(req: GuestCreateRequest, db: AsyncSession = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="嘉宾名称不能为空")
    guest = await db_service.create_guest(db, req.name.strip(), req.description.strip())
    return ok(guest)


@router.get("",
    summary="嘉宾列表",
    description="获取所有嘉宾档案，按创建时间倒序")
async def list_guests(db: AsyncSession = Depends(get_db)):
    try:
        guests = await db_service.get_guests(db)
        return ok({"guests": guests})
    except Exception as e:
        logger.warning(f"获取嘉宾列表失败: {e}")
        return ok({"guests": []})


@router.delete("/{guest_id}",
    summary="删除嘉宾",
    description="删除嘉宾及其所有素材和分析结果（级联删除）")
async def delete_guest(guest_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest(db, guest_id)
    return ok()


# ---- 素材管理 ----

@router.get("/{guest_id}/materials",
    summary="素材列表",
    description="获取嘉宾的所有素材（搜索结果、手动添加的链接、AI汇总），含验证状态和正文内容")
async def list_materials(guest_id: int, db: AsyncSession = Depends(get_db)):
    try:
        materials = await db_service.get_guest_materials(db, guest_id)
        return ok({"materials": materials})
    except Exception as e:
        logger.warning(f"获取素材失败: {e}")
        return ok({"materials": []})


@router.post("/{guest_id}/materials",
    summary="添加素材",
    description="手动添加采访链接（支持抖音、B站、YouTube、小宇宙、网页等平台）")
async def add_material(guest_id: int, req: MaterialAddRequest, db: AsyncSession = Depends(get_db)):
    mat = await db_service.add_guest_material(db, guest_id, {
        "type": "manual_link",
        "platform": req.platform,
        "url": req.url,
        "title": req.title or req.url,
    })
    return ok(mat)


@router.put("/{guest_id}/materials/{material_id}",
    summary="编辑素材",
    description="编辑素材内容（如手动粘贴视频转录文本）或修改验证状态")
async def update_material(guest_id: int, material_id: int, req: MaterialUpdateRequest, db: AsyncSession = Depends(get_db)):
    if req.content is not None:
        await db_service.update_guest_material_content(db, material_id, req.content, status=req.status or "verified")
    elif req.status is not None:
        await db_service.update_guest_material_status(db, material_id, req.status)
    return ok()


@router.delete("/{guest_id}/materials/{material_id}",
    summary="删除素材",
    description="删除指定素材")
async def delete_material(guest_id: int, material_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest_material(db, material_id)
    return ok()


# ---- AI 同事 ----

@router.post("/{guest_id}/actions/search",
    summary="AI调查员 — 搜索采访素材",
    description="触发 AI调查员 后台搜索嘉宾的公开采访资料。包含多轮搜索、智能补搜、引用链追踪、微信公众号定向搜索。抓取全文后自动验证相关性。返回 task_id 用于查询进度。")
async def search_guest(guest_id: int, req: GuestSearchRequest = None, db: AsyncSession = Depends(get_db)):
    if req is None:
        req = GuestSearchRequest()
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    guest_name = guest["name"]
    guest_desc = guest["description"]
    extra_keywords = req.extra_keywords

    task_id = task_service.create_task(f"AI调查员: {guest_name}")

    async def _bg_search():
        try:
            task_service.update_progress(task_id, "正在搜索采访资料...")
            custom_search = ""
            async with async_session() as s:
                prompts = await db_service.get_ai_prompts(s)
                for p in prompts:
                    if p["name"] == "AI调查员":
                        custom_search = p["content"]
                        break
            result = await ai_service.guest_web_search(guest_name, guest_desc, custom_search, extra_keywords)
            search_results = result.get("search_results", [])

            # URL 去重 + 清理旧 AI 汇总
            async with async_session() as session:
                existing = await db_service.get_guest_materials(session, guest_id)
                for m in existing:
                    if m.get("type") == "ai_summary":
                        await db_service.delete_guest_material(session, m["id"])
            existing_urls = {m["url"] for m in existing if m.get("url")}

            task_service.update_progress(task_id, f"搜索完成，保存{len(search_results)}条结果...")
            async with async_session() as session:
                saved_ids = []
                skipped = 0
                for sr in search_results:
                    url = sr.get("url", "")
                    if not url or url in existing_urls:
                        if url:
                            skipped += 1
                        continue
                    mat = await db_service.add_guest_material(session, guest_id, {
                        "type": "search_result", "platform": "网页", "url": url,
                        "title": sr.get("title", ""), "summary": sr.get("snippet", ""),
                        "raw_data": sr, "status": "pending",
                    })
                    saved_ids.append((mat["id"], url))

                if result.get("summary"):
                    await db_service.add_guest_material(session, guest_id, {
                        "type": "ai_summary",
                        "title": f"AI 搜索汇总 - {guest_name}（仅供参考，可能含未经证实信息）",
                        "content": result["summary"],
                        "raw_data": {"type": "search_summary", "created_at": result.get("created_at", "")},
                        "status": "unverified",
                    })

            # 抓取验证
            task_service.update_progress(task_id, f"抓取验证中 0/{len(saved_ids)}...")
            verified = 0
            failed = 0
            for idx, (mat_id, url) in enumerate(saved_ids):
                task_service.update_progress(task_id, f"抓取验证中 {idx+1}/{len(saved_ids)}...")
                content = await fetch_page_text(url)
                async with async_session() as session:
                    if not content:
                        await db_service.update_guest_material_status(session, mat_id, "failed")
                        failed += 1
                    elif guest_name in content:
                        await db_service.update_guest_material_content(session, mat_id, content, status="verified")
                        verified += 1
                    else:
                        await db_service.update_guest_material_content(session, mat_id, content, status="unverified")

            # 引用链追踪
            task_service.update_progress(task_id, "引用链追踪...")
            async with async_session() as session:
                all_materials = await db_service.get_guest_materials(session, guest_id)
            all_existing_urls = {m["url"] for m in all_materials if m.get("url")}

            discovered_urls = []
            for mat_id, url in saved_ids:
                mat = next((m for m in all_materials if m["id"] == mat_id), None)
                if mat and mat.get("content"):
                    for found_url in extract_urls_from_text(mat["content"]):
                        if found_url not in all_existing_urls and found_url not in {u for u, _ in discovered_urls}:
                            discovered_urls.append((found_url, mat.get("title", "")))

            ref_verified = 0
            if discovered_urls:
                discovered_urls = discovered_urls[:10]
                async with async_session() as session:
                    for ref_url, source_title in discovered_urls:
                        mat = await db_service.add_guest_material(session, guest_id, {
                            "type": "search_result", "platform": "引用链", "url": ref_url,
                            "title": "", "summary": f"从「{source_title}」中发现的引用链接",
                            "status": "pending",
                        })
                        content = await fetch_page_text(ref_url)
                        if content and guest_name in content:
                            await db_service.update_guest_material_content(session, mat["id"], content, status="verified")
                            ref_verified += 1
                        elif content:
                            await db_service.update_guest_material_content(session, mat["id"], content, status="unverified")
                        else:
                            await db_service.update_guest_material_status(session, mat["id"], "failed")

            # 抖音站内搜索
            task_service.update_progress(task_id, "搜索抖音站内内容...")
            douyin_added = 0
            try:
                async with async_session() as session:
                    all_mats = await db_service.get_guest_materials(session, guest_id)
                all_urls = {m["url"] for m in all_mats if m.get("url")}

                # 搜用户：找嘉宾的抖音号
                dy_users = await tikhub_service.search_douyin_users(guest_name, count=5)
                async with async_session() as session:
                    for u in dy_users:
                        if u["follower_count"] < 1000:
                            continue
                        profile_url = f"https://www.douyin.com/user/{u['sec_uid']}" if u['sec_uid'] else ""
                        if profile_url and profile_url in all_urls:
                            continue
                        fmtfans = f"{u['follower_count']/10000:.1f}万" if u['follower_count'] >= 10000 else str(u['follower_count'])
                        await db_service.add_guest_material(session, guest_id, {
                            "type": "douyin_account", "platform": "抖音",
                            "url": profile_url,
                            "title": f"[抖音账号] {u['nickname']} (@{u['unique_id']}) {fmtfans}粉丝",
                            "summary": u.get("signature", ""),
                            "status": "verified",
                            "raw_data": u,
                        })
                        all_urls.add(profile_url)
                        douyin_added += 1

                # 搜视频：找嘉宾相关的抖音视频
                dy_videos = await tikhub_service.search_douyin_videos(guest_name, count=10)
                async with async_session() as session:
                    for v in dy_videos:
                        if not v.get("aweme_id"):
                            continue
                        vid_url = v["url"]
                        if vid_url in all_urls:
                            continue
                        # 筛选：标题含嘉宾名 或 播放量 > 1万
                        if guest_name not in v.get("desc", "") and v.get("play_count", 0) < 10000:
                            continue
                        fmtplay = f"{v['play_count']/10000:.1f}万" if v['play_count'] >= 10000 else str(v['play_count'])
                        await db_service.add_guest_material(session, guest_id, {
                            "type": "douyin_video", "platform": "抖音",
                            "url": vid_url,
                            "title": f"[抖音视频] {v['desc'][:80]}",
                            "summary": f"作者: {v['author_nickname']} | 播放{fmtplay} | 点赞{v['digg_count']} | 评论{v['comment_count']}",
                            "status": "verified",
                            "raw_data": v,
                        })
                        all_urls.add(vid_url)
                        douyin_added += 1
            except Exception as e:
                logger.warning(f"抖音站内搜索失败（不影响整体）: {e}")

            task_service.complete_task(task_id, {
                "new": len(saved_ids), "skipped": skipped,
                "verified": verified, "failed": failed,
                "ref_discovered": len(discovered_urls), "ref_verified": ref_verified,
                "douyin_added": douyin_added,
            })
            logger.info(f"AI调查员完成: {guest_name}, 新增{len(saved_ids)}, 验证{verified}, 引用链{ref_verified}, 抖音{douyin_added}")
        except Exception as e:
            logger.error(f"AI调查员失败: {e}", exc_info=True)
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg_search())
    return ok({"task_id": task_id})


@router.post("/{guest_id}/actions/plan",
    summary="AI策划专员 — 段落式采访策划",
    description="基于全部素材生成段落式采访策划方案（20-25个段落，每段=一个潜在切片）。含嘉宾速写、金句库、被问烂的问题、矛盾点分析。返回 task_id。")
async def analyze_guest(guest_id: int, req: GuestAnalyzeRequest = None, db: AsyncSession = Depends(get_db)):
    if req is None:
        req = GuestAnalyzeRequest()
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")
    materials = await db_service.get_guest_materials(db, guest_id)
    if not materials:
        raise HTTPException(status_code=400, detail="暂无资料，请先让AI调查员搜索素材")

    guest_name = guest["name"]
    custom_prompt = req.prompt
    task_id = task_service.create_task(f"AI策划专员: {guest_name}")

    async def _bg():
        try:
            task_service.update_progress(task_id, "正在生成采访策划...")
            result = await ai_service.analyze_guest(guest_name=guest_name, materials=materials, custom_prompt=custom_prompt)
            async with async_session() as session:
                await db_service.save_guest_analysis(session, guest_id, "interview", result)
            task_service.complete_task(task_id, {"analysis_type": "interview"})
            logger.info(f"AI策划专员完成: {guest_name}")
        except Exception as e:
            logger.error(f"AI策划专员失败: {e}", exc_info=True)
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg())
    return ok({"task_id": task_id})


@router.post("/{guest_id}/actions/content",
    summary="AI内容编导 — 深度追问设计",
    description="用 Opus 对采访策划方案做二次深度打磨：升级核心段落、设计杀手锏问题、画追问链路图。需先完成策划专员。返回 task_id。")
async def deep_followup(guest_id: int, req: GuestAnalyzeRequest = None, db: AsyncSession = Depends(get_db)):
    if req is None:
        req = GuestAnalyzeRequest()
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    analyses = await db_service.get_guest_analyses(db, guest_id)
    interview_plan = ""
    for a in analyses:
        if a["analysis_type"] == "interview":
            interview_plan = a.get("content", {}).get("result", "")
            break
    if not interview_plan:
        raise HTTPException(status_code=400, detail="请先完成AI策划专员")

    guest_name = guest["name"]
    custom_prompt = req.prompt
    task_id = task_service.create_task(f"AI内容编导: {guest_name}")

    async def _bg():
        try:
            task_service.update_progress(task_id, "AI内容编导工作中...")
            prompt = custom_prompt
            if not prompt:
                async with async_session() as s:
                    prompts = await db_service.get_ai_prompts(s)
                    for p in prompts:
                        if p["name"] == "AI内容编导":
                            prompt = p["content"]
                            break
            result = await ai_service.deep_follow_up(guest_name, interview_plan, prompt)
            async with async_session() as session:
                await db_service.save_guest_analysis(session, guest_id, "followup", result)
            task_service.complete_task(task_id, {"analysis_type": "followup"})
            logger.info(f"AI内容编导完成: {guest_name}")
        except Exception as e:
            logger.error(f"AI内容编导失败: {e}", exc_info=True)
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg())
    return ok({"task_id": task_id})


@router.post("/{guest_id}/actions/clip",
    summary="AI切片编导 — 标题/钩子/金句/评论引爆",
    description="用 Opus 从传播和算法角度审视策划方案：切片潜力评估、标题工厂、钩子重设计、金句催化、评论引爆预设。需先完成策划专员。返回 task_id。")
async def clip_review(guest_id: int, req: GuestAnalyzeRequest = None, db: AsyncSession = Depends(get_db)):
    if req is None:
        req = GuestAnalyzeRequest()
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    analyses = await db_service.get_guest_analyses(db, guest_id)
    interview_plan = ""
    for a in analyses:
        if a["analysis_type"] == "interview":
            interview_plan = a.get("content", {}).get("result", "")
            break
    if not interview_plan:
        raise HTTPException(status_code=400, detail="请先完成AI策划专员")

    guest_name = guest["name"]
    custom_prompt = req.prompt
    task_id = task_service.create_task(f"AI切片编导: {guest_name}")

    async def _bg():
        try:
            task_service.update_progress(task_id, "AI切片编导工作中...")
            prompt = custom_prompt
            if not prompt:
                async with async_session() as s:
                    prompts = await db_service.get_ai_prompts(s)
                    for p in prompts:
                        if p["name"] == "AI切片编导":
                            prompt = p["content"]
                            break
            result = await ai_service.clip_review(guest_name, interview_plan, prompt)
            async with async_session() as session:
                await db_service.save_guest_analysis(session, guest_id, "clip", result)
            task_service.complete_task(task_id, {"analysis_type": "clip"})
            logger.info(f"AI切片编导完成: {guest_name}")
        except Exception as e:
            logger.error(f"AI切片编导失败: {e}", exc_info=True)
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg())
    return ok({"task_id": task_id})


@router.post("/{guest_id}/actions/trending",
    summary="AI热点编导 — 热点话题嫁接",
    description="用 Sonnet+web search 搜索近期热点话题，找到与嘉宾领域的交叉点，设计热点嫁接问题和切片标题。需先完成策划专员。返回 task_id。")
async def trending_review(guest_id: int, req: GuestAnalyzeRequest = None, db: AsyncSession = Depends(get_db)):
    if req is None:
        req = GuestAnalyzeRequest()
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    analyses = await db_service.get_guest_analyses(db, guest_id)
    interview_plan = ""
    for a in analyses:
        if a["analysis_type"] == "interview":
            interview_plan = a.get("content", {}).get("result", "")
            break
    if not interview_plan:
        raise HTTPException(status_code=400, detail="请先完成AI策划专员")

    guest_name = guest["name"]
    guest_desc = guest["description"]
    custom_prompt = req.prompt
    task_id = task_service.create_task(f"AI热点编导: {guest_name}")

    async def _bg():
        try:
            task_service.update_progress(task_id, "获取抖音实时热搜...")
            hot_search_text = ""
            try:
                hot_list = await tikhub_service.fetch_hot_search_list()
                if hot_list:
                    lines = [f"{i+1}. {h['word']}" + (f" ({h['label']})" if h.get('label') else "") for i, h in enumerate(hot_list[:30])]
                    hot_search_text = "\n\n## 当前抖音热搜（实时数据）\n" + "\n".join(lines)
            except Exception as e:
                logger.warning(f"获取抖音热搜失败（不影响整体）: {e}")

            task_service.update_progress(task_id, "AI热点编导搜索热点中...")
            prompt = custom_prompt
            if not prompt:
                async with async_session() as s:
                    prompts = await db_service.get_ai_prompts(s)
                    for p in prompts:
                        if p["name"] == "AI热点编导":
                            prompt = p["content"]
                            break

            # 把抖音热搜注入到采访方案末尾，让 Claude 一起参考
            plan_with_hot = interview_plan
            if hot_search_text:
                plan_with_hot = interview_plan + hot_search_text
            result = await ai_service.trending_review(guest_name, guest_desc, plan_with_hot, prompt)
            async with async_session() as session:
                await db_service.save_guest_analysis(session, guest_id, "trending", result)
            task_service.complete_task(task_id, {"analysis_type": "trending"})
            logger.info(f"AI热点编导完成: {guest_name}")
        except Exception as e:
            logger.error(f"AI热点编导失败: {e}", exc_info=True)
            task_service.fail_task(task_id, str(e))

    asyncio.create_task(_bg())
    return ok({"task_id": task_id})


@router.post("/{guest_id}/actions/chat",
    summary="AI嘉宾替身 — 对话预演",
    description="AI 扮演嘉宾进行多轮模拟对话，基于所有分析结果还原嘉宾的说话风格和观点立场。支持传入对话历史实现多轮对话。")
async def guest_chat(guest_id: int, req: GuestChatRequest, db: AsyncSession = Depends(get_db)):
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")

    analyses = await db_service.get_guest_analyses(db, guest_id)

    custom_prompt = ""
    prompts = await db_service.get_ai_prompts(db)
    for p in prompts:
        if p["name"] == "AI嘉宾替身":
            custom_prompt = p["content"]
            break

    reply = await ai_service.guest_chat(guest["name"], analyses, req.history, req.message, custom_prompt)
    return ok({"reply": reply})


# ---- 分析结果 ----

@router.get("/{guest_id}/analyses",
    summary="分析结果列表",
    description="获取嘉宾的所有 AI 分析结果（策划方案、内容编导、切片编导、热点编导），按时间倒序")
async def list_analyses(guest_id: int, db: AsyncSession = Depends(get_db)):
    try:
        analyses = await db_service.get_guest_analyses(db, guest_id)
        return ok({"analyses": analyses})
    except Exception as e:
        logger.warning(f"获取分析结果失败: {e}")
        return ok({"analyses": []})


@router.delete("/{guest_id}/analyses/{analysis_id}",
    summary="删除分析结果",
    description="删除指定的分析结果")
async def delete_analysis(guest_id: int, analysis_id: int, db: AsyncSession = Depends(get_db)):
    await db_service.delete_guest_analysis(db, analysis_id)
    return ok()


# ---- 数据导出 ----

@router.get("/{guest_id}/export",
    summary="导出嘉宾全量数据",
    description="导出嘉宾的所有数据（基本信息、素材列表、分析结果），适合外部工具（OpenClaw/Claude）使用")
async def export_guest(guest_id: int, db: AsyncSession = Depends(get_db)):
    guest = await db_service.get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="嘉宾不存在")
    materials = await db_service.get_guest_materials(db, guest_id)
    analyses = await db_service.get_guest_analyses(db, guest_id)
    return ok({
        "guest": guest,
        "materials": materials,
        "analyses": analyses,
    })
