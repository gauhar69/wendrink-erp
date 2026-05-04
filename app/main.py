"""
WENDRINK ERP - FastAPI Application

Main application factory and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize database connection
    - Shutdown: Close database connections
    """
    # Startup
    try:
        await init_db()
        print("[OK] Database connection established")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
    
    yield
    
    # Shutdown
    await close_db()
    print("[OK] Database connections closed")


def create_app() -> FastAPI:
    """
    Application factory.
    
    Creates and configures the FastAPI application.
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## WENDRINK ERP API

Ledger-first financial system for Kazakh coffee shop chain.

### Key Features
- **Inventory Management**: Track ingredients with WAC costing
- **Sales Processing**: Record sales with immutable COGS
- **OPEX Tracking**: Daily operational expense allocation
- **P&L Reporting**: Real-time profitability analysis

### Architecture Principles
- Append-only ledgers (no updates/deletes)
- Decimal-only for all financial values
- UTC timestamps with Almaty business date logic
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware for development
    if settings.app_env == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Static files (PWA icons, manifest)
    static_path = Path("app/static")
    static_path.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Include API routes
    app.include_router(api_router)

    templates = Jinja2Templates(directory="app/templates")

    @app.get("/login", response_class=HTMLResponse, tags=["UI"])
    async def login_page(request: Request):
        """Render the login page."""
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    @app.get("/dashboard", response_class=HTMLResponse, tags=["UI"])
    async def dashboard_ui():
        """Direct access to dashboard UI."""
        html_path = Path("app/templates/dashboard.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)

    @app.get("/", tags=["UI"])
    async def root():
        """Redirect to dashboard."""
        return RedirectResponse(url="/dashboard")

    return app


# Create application instance
app = create_app()
