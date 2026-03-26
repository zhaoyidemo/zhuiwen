import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_models import PromptSaveRequest, ok
from services import db_service, ai_service
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/prompts", tags=["提示词管理"])


@router.get("",
    summary="提示词列表",
    description="获取所有 AI 提示词（含系统内置默认模板和用户自定义）。内置提示词包括：AI洞察、前5秒分析、AI调查员、AI策划专员、AI内容编导、AI切片编导、AI热点编导、AI嘉宾替身。")
async def list_prompts(db: AsyncSession = Depends(get_db)):
    db_prompts = await db_service.get_ai_prompts(db)
    db_names = {p["name"] for p in db_prompts}
    for name, content in ai_service.DEFAULT_PROMPTS.items():
        if name not in db_names:
            db_prompts.append({"id": None, "name": name, "content": content, "is_default": True})
    return ok({"prompts": db_prompts})


@router.post("",
    summary="保存提示词",
    description="创建或更新一个提示词（按名称去重）")
async def save_prompt(body: PromptSaveRequest, db: AsyncSession = Depends(get_db)):
    result = await db_service.upsert_ai_prompt(db, body.name, body.content)
    return ok(result)


@router.delete("/{name}",
    summary="删除提示词",
    description="删除指定名称的提示词（内置提示词删除后会恢复为默认内容）")
async def delete_prompt(name: str, db: AsyncSession = Depends(get_db)):
    await db_service.delete_ai_prompt(db, name)
    return ok()
