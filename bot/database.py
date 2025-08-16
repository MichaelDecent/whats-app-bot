from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

# Global variables
engine = None
async_session_maker = None


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def connect() -> None:
    """Create database engine and session maker."""
    global engine, async_session_maker

    settings = get_settings()

    # Determine database URL based on environment
    if hasattr(settings, "DATABASE_URL"):
        database_url = settings.DATABASE_URL
    else:
        # Default to SQLite for development
        database_url = "sqlite+aiosqlite:///./whatsapp_bot.db"

    engine = create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL logging in development
    )

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db() -> async_sessionmaker[AsyncSession]:
    """Get async session maker."""
    assert async_session_maker is not None, "Database not initialized"
    return async_session_maker


async def close() -> None:
    """Close database connections."""
    if engine:
        await engine.dispose()
