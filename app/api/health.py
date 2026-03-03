"""
WENDRINK ERP - Health Check Endpoint

Provides system health status for monitoring and load balancers.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str
    timestamp: str
    version: str
    database: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check system health and database connectivity",
)
async def health_check(
    session: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        - status: "healthy" or "unhealthy"
        - timestamp: Current UTC time
        - version: Application version
        - database: "connected" or "disconnected"
    """
    settings = get_settings()
    db_status = "disconnected"
    
    try:
        # Test database connection
        result = await session.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    status = "healthy" if db_status == "connected" else "unhealthy"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
        database=db_status,
    )


@router.get(
    "/",
    summary="Root",
    description="API root - returns basic info",
)
async def root() -> dict:
    """Root endpoint with basic API info."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
