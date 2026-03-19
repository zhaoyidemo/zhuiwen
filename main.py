import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 延迟导入，确保启动时报错能看到
try:
    from config import settings
    from routers import video, account, analysis, favorite, guest
    from models.schemas import PasswordRequest
    from database import init_db
except Exception as e:
    logger.error(f"Import error: {e}")
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield

app = FastAPI(title="继续追问 | 抖音数据分析平台", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 密码验证中间件
@app.middleware("http")
async def password_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path == "/"
        or path == "/health"
        or path == "/api/auth/verify"
        or path.startswith("/static")
        or not path.startswith("/api")
    ):
        return await call_next(request)

    password = request.headers.get("X-Site-Password", "")
    if password != settings.SITE_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")

    return await call_next(request)


# 根路径 — 放在 mount 之前
@app.get("/", response_class=HTMLResponse)
async def index():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>继续追问 | 抖音数据分析平台</h1><p>static/index.html not found</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.4"}


@app.post("/api/auth/verify")
async def verify_password(req: PasswordRequest):
    if req.password == settings.SITE_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="密码错误")


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
