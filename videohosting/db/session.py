from sqlalchemy import text
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
        await _apply_sqlite_compat_migrations(conn)


async def get_db_session():
    async with SessionLocal() as session:
        yield session


async def _apply_sqlite_compat_migrations(conn) -> None:
    if not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
        return

    async def column_names(table_name: str) -> set[str]:
        rows = (await conn.execute(text(f"PRAGMA table_info({table_name})"))).mappings().all()
        return {str(row["name"]) for row in rows}

    async def add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
        cols = await column_names(table_name)
        if column_name not in cols:
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

    await add_column_if_missing("users", "role", "role VARCHAR(16) NOT NULL DEFAULT 'user'")

    await add_column_if_missing(
        "videos",
        "moderation_status",
        "moderation_status VARCHAR(16) NOT NULL DEFAULT 'approved'",
    )
    await add_column_if_missing("videos", "deletion_reason", "deletion_reason VARCHAR(500)")
    await add_column_if_missing("videos", "is_deleted", "is_deleted BOOLEAN NOT NULL DEFAULT 0")
    await add_column_if_missing("videos", "tags", "tags VARCHAR(500)")
    await add_column_if_missing("videos", "duration_seconds", "duration_seconds FLOAT")
    await add_column_if_missing("videos", "is_short", "is_short BOOLEAN NOT NULL DEFAULT 0")

    await add_column_if_missing("video_comments", "parent_id", "parent_id INTEGER")
    await add_column_if_missing("video_comments", "likes", "likes INTEGER NOT NULL DEFAULT 0")
    await add_column_if_missing("video_comments", "dislikes", "dislikes INTEGER NOT NULL DEFAULT 0")
