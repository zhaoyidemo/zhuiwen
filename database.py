import logging
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings

logger = logging.getLogger(__name__)


def _build_url(raw: str) -> str:
    if not raw:
        return ""
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


DATABASE_URL = _build_url(settings.DATABASE_URL)

# 日志输出（隐藏密码）
if DATABASE_URL:
    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    logger.info(f"Database URL: ...@{safe_url}")
else:
    logger.warning("DATABASE_URL 未配置，数据库功能不可用")


class Base(DeclarativeBase):
    pass


async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_recycle=300,       # 每5分钟回收空闲连接
    pool_pre_ping=True,     # 每次使用前检测连接是否存活
    pool_size=5,
    max_overflow=10,
) if DATABASE_URL else None
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False) if async_engine else None


async def get_db():
    if not async_session:
        raise RuntimeError("数据库未配置")
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    if not async_engine:
        logger.warning("跳过数据库初始化：DATABASE_URL 未配置")
        return
    from models.db_models import Base as _Base  # noqa: F811
    async with async_engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
        # 自动添加缺失的列（create_all 不会修改已有表）
        migrations = [
            ("videos", "video_tags", "TEXT DEFAULT ''"),
            ("video_favorites", "ai_analysis", "JSONB DEFAULT '{}'::jsonb"),
            ("accounts", "xingtu_data", "JSONB DEFAULT '{}'::jsonb"),
            ("accounts", "xingtu_updated_at", "VARCHAR(64) DEFAULT ''"),
            ("video_favorites", "first5s_analysis", "JSONB DEFAULT '{}'::jsonb"),
            ("guest_materials", "status", "VARCHAR(32) DEFAULT 'pending'"),
        ]
        for table, col_name, col_def in migrations:
            try:
                await conn.execute(
                    sqlalchemy.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                )
            except Exception:
                pass
