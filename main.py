import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    from config import settings
    from routers import video, account, analysis, favorite, guest
    from models.api_models import PasswordRequest, ok, fail
    from services import task_service, db_service
    from database import init_db
except Exception as e:
    logger.error(f"Import error: {e}")
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield

app = FastAPI(
    title="继续追问 | 抖音数据分析平台",
    version="2.0.0",
    description="AI 原生的深度访谈播客内容研究平台。提供视频分析、竞品雷达、爆款收藏、嘉宾研究等功能。",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 统一异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.detail, exc.status_code),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=fail(f"服务器内部错误: {type(exc).__name__}", 500),
    )


# 密码验证中间件
@app.middleware("http")
async def password_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path == "/"
        or path == "/health"
        or path == "/api/auth/verify"
        or path == "/openapi.json"
        or path == "/docs"
        or path == "/redoc"
        or path.startswith("/static")
        or not path.startswith("/api")
    ):
        return await call_next(request)

    password = request.headers.get("X-Site-Password", "")
    if password != settings.SITE_PASSWORD:
        return JSONResponse(
            status_code=401,
            content=fail("密码错误", 401),
        )

    return await call_next(request)


# ---- 全局端点 ----

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>继续追问 | 抖音数据分析平台</h1><p>static/index.html not found</p>")


@app.get("/health",
    summary="健康检查",
    description="返回服务状态和版本号")
async def health():
    return ok({"status": "ok", "version": "2.0.0"})


@app.post("/api/auth/verify",
    summary="密码验证",
    description="验证访问密码，通过后在请求头中携带 X-Site-Password")
async def verify_password(req: PasswordRequest):
    if req.password == settings.SITE_PASSWORD:
        return ok({"verified": True})
    raise HTTPException(status_code=401, detail="密码错误")


@app.get("/api/tasks/{task_id}",
    summary="查询任务状态",
    description="查询后台异步任务的执行状态和结果",
    tags=["任务"])
async def get_task_status(task_id: str):
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ok(task)


@app.get("/api/diagnostics",
    summary="系统自检",
    description="返回系统全面的诊断信息：数据库状态、各表数据量、外部服务连通性、最近任务、提示词配置。Claude 和 AI Agent 可通过此端点快速了解系统全局状态。",
    tags=["系统"])
async def diagnostics():
    from database import async_session, async_engine
    from services import ai_service

    result = {
        "api_version": "2.0.0",
        "database": "disconnected",
        "tables": {},
        "prompts": {"total": 0, "default": 0, "custom": 0},
        "recent_tasks": [],
        "external_services": {},
    }

    # 数据库状态 + 各表数据量
    if async_engine:
        try:
            async with async_session() as db:
                from sqlalchemy import text
                tables = ["accounts", "videos", "video_favorites", "video_history", "ai_prompts", "guests", "guest_materials", "guest_analyses"]
                for table in tables:
                    try:
                        row = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        result["tables"][table] = row.scalar()
                    except Exception:
                        result["tables"][table] = "error"

                # 提示词统计
                prompts = await db_service.get_ai_prompts(db)
                db_names = {p["name"] for p in prompts}
                default_count = len(ai_service.DEFAULT_PROMPTS)
                custom_count = len([p for p in prompts if p["name"] not in ai_service.DEFAULT_PROMPTS])
                result["prompts"] = {"total": default_count + custom_count, "default": default_count, "custom": custom_count}

            result["database"] = "connected"
        except Exception as e:
            result["database"] = f"error: {str(e)}"

    # 最近任务
    all_tasks = task_service._tasks
    recent = sorted(all_tasks.values(), key=lambda t: t["created_at"], reverse=True)[:10]
    result["recent_tasks"] = [{"task_id": t["task_id"], "name": t["name"], "status": t["status"], "created_at": t["created_at"]} for t in recent]

    # 外部服务检测
    # Anthropic
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        result["external_services"]["anthropic"] = "configured" if settings.ANTHROPIC_API_KEY else "not_configured"
    except Exception:
        result["external_services"]["anthropic"] = "error"

    # TikHub
    result["external_services"]["tikhub"] = "configured" if settings.TIKHUB_API_KEY else "not_configured"

    # 飞书
    result["external_services"]["feishu"] = "configured" if settings.FEISHU_APP_ID else "not_configured"

    return ok(result)


@app.get("/api/self-test",
    summary="API 自动化测试",
    description="自动测试所有核心 API 端点是否正常响应。返回每个端点的测试结果（pass/fail）。",
    tags=["系统"])
async def self_test():
    import httpx

    base = "http://127.0.0.1:8080"
    headers = {"X-Site-Password": settings.SITE_PASSWORD, "Content-Type": "application/json"}

    tests = [
        ("GET", "/health", None),
        ("GET", "/api/accounts", None),
        ("GET", "/api/videos/history", None),
        ("GET", "/api/favorites", None),
        ("GET", "/api/favorites/prompts", None),
        ("GET", "/api/guests", None),
    ]

    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for method, path, body in tests:
            try:
                if method == "GET":
                    resp = await client.get(f"{base}{path}", headers=headers)
                else:
                    resp = await client.post(f"{base}{path}", headers=headers, json=body)

                data = resp.json()
                passed = resp.status_code == 200 and data.get("code", -1) == 0
                results.append({
                    "endpoint": f"{method} {path}",
                    "status": resp.status_code,
                    "result": "pass" if passed else "fail",
                    "message": data.get("message", ""),
                })
            except Exception as e:
                results.append({
                    "endpoint": f"{method} {path}",
                    "status": 0,
                    "result": "error",
                    "message": str(e),
                })

    passed = sum(1 for r in results if r["result"] == "pass")
    total = len(results)
    return ok({
        "summary": f"{passed}/{total} passed",
        "tests": results,
    })


# API 路由
app.include_router(video.router)
app.include_router(account.router)
app.include_router(analysis.router)
app.include_router(favorite.router)
app.include_router(guest.router)


# 静态文件服务 — 放在最后
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"Static files served from {STATIC_DIR}")
else:
    logger.warning(f"Static directory not found: {STATIC_DIR}")
