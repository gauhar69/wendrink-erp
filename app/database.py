"""
WENDRINK ERP - Async Database Engine and Session Management

Provides async SQLAlchemy engine and session factory.
Uses asyncpg driver for PostgreSQL.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

# Create async engine with connection pool
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,  # Log SQL in debug mode
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Check connection health
)

# Session factory - creates new sessions
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Usage in FastAPI:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection (for startup checks)."""
    async with engine.begin() as conn:
        # Just test the connection
        await conn.execute(text("SELECT 1 as ok"))


async def close_db() -> None:
    """Close database connections (for shutdown)."""
    await engine.dispose()
