from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings


def _build_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


DATABASE_URL = _build_url(settings.DATABASE_URL)

async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from models.db_models import Base as _Base  # noqa: F811
    async with async_engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
