import logging
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from routers import video, account, analysis
from models.schemas import PasswordRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="继续追问 | 抖音数据分析平台", version="1.0.0")

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
    # 静态文件、健康检查、密码验证接口不需要密码
    path = request.url.path
    if (
        path == "/"
        or path == "/health"
        or path == "/api/auth/verify"
        or path.startswith("/assets")
        or path.endswith((".js", ".css", ".ico", ".png", ".svg", ".jpg"))
        or not path.startswith("/api")
    ):
        return await call_next(request)

    password = request.headers.get("X-Site-Password", "")
    if password != settings.SITE_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")

    return await call_next(request)


# 路由
app.include_router(video.router)
app.include_router(account.router)
app.include_router(analysis.router)


@app.post("/api/auth/verify")
async def verify_password(req: PasswordRequest):
    if req.password == settings.SITE_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="密码错误")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# 静态文件服务（前端构建产物）
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: 所有非 API 路由返回 index.html"""
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
