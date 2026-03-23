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
    from services import task_service
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
