import logging

from fastapi import APIRouter, HTTPException

from models.schemas import AnalysisRequest
from services import ai_service, feishu_service
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["AI 分析"])


@router.post("/run")
async def run_analysis(req: AnalysisRequest):
    """运行 AI 分析"""
    # 从飞书获取视频数据
    videos = []
    if req.video_ids:
        try:
            tid = settings.FEISHU_TABLE_VIDEOS
            if tid:
                all_records = await feishu_service.search_records(tid)
                videos = [
                    r.get("fields", {})
                    for r in all_records
                    if r.get("fields", {}).get("aweme_id") in req.video_ids
                ]
        except Exception as e:
            logger.warning(f"从飞书读取视频失败: {e}")

    if not videos:
        raise HTTPException(status_code=400, detail="未找到指定视频数据")

    result = await ai_service.analyze_videos(
        videos=videos,
        analysis_type=req.analysis_type,
        custom_prompt=req.custom_prompt,
    )

    # 可选：将分析结果写入飞书
    try:
        tid = settings.FEISHU_TABLE_ANALYSES
        if tid:
            import time
            await feishu_service.create_record(tid, {
                "analysis_id": result["analysis_id"],
                "analysis_type": result["analysis_type"],
                "input_description": result["input_description"],
                "result": result["result"],
                "created_at": int(time.time() * 1000),
            })
    except Exception as e:
        logger.warning(f"写入分析记录到飞书失败: {e}")

    return result
