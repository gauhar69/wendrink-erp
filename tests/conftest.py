"""conftest.py - Shared fixtures and database isolation safety logic for WENDRINK ERP.
"""
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

from app.models import Base
from app.config import get_settings


def check_test_db_safety(url: str):
    """Enforces safety rules by blocking any connections to physical files."""
    if "sqlite" in url and ":memory:" not in url:
        raise RuntimeError(
            f"CRITICAL SAFETY WARNING: Test database URL points to a physical file! "
            f"Connection blocked: {url}"
        )
    if "wendrink.db" in url or "wendrink_prod.db" in url:
        raise RuntimeError(
            f"CRITICAL SAFETY WARNING: Test database URL target contains production DB filename! "
            f"Connection blocked: {url}"
        )


@pytest.fixture(scope="session")
def event_loop():
    """Create session-scoped event loop for async tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a isolated async database session using an in-memory SQLite database."""
    settings = get_settings()
    # Force test configuration
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    
    # Run safety checks
    check_test_db_safety(settings.database_url)
    
    engine = create_async_engine(
        settings.database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables in memory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        
    # Clean up and close connection
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
