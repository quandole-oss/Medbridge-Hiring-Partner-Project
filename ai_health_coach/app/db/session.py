from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: add columns if missing (existing DBs)
        migrations = [
            "ALTER TABLE exercise_completions ADD COLUMN set_statuses JSON",
            "ALTER TABLE exercises ADD COLUMN week_number INTEGER DEFAULT 1",
            "ALTER TABLE patients ADD COLUMN pathway_id INTEGER",
            "ALTER TABLE patients ADD COLUMN current_week INTEGER DEFAULT 1",
        ]
        for migration in migrations:
            try:
                await conn.execute(text(migration))
            except Exception:
                pass  # Column already exists


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
