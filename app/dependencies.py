"""
WENDRINK ERP - FastAPI Dependencies

Provides dependency injection for database sessions and other common dependencies.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session

# Type alias for injected async session
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_async_session for cleaner imports."""
    async for session in get_async_session():
        yield session
