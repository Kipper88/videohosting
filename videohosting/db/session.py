from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from videohosting.core.config import Config
from videohosting.db.base import Base


def _to_async_db_uri(db_uri: str) -> str:
    if db_uri.startswith("sqlite:///"):
        return db_uri.replace("sqlite:///", "sqlite+aiosqlite:///")
    if db_uri.startswith("postgresql://"):
        return db_uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_uri


DATABASE_URL = _to_async_db_uri(Config.SQLALCHEMY_DATABASE_URI)
engine: AsyncEngine = create_async_engine(DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session():
    async with SessionLocal() as session:
        yield session
