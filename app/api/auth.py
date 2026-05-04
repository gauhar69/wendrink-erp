"""WENDRINK ERP - Auth endpoints: login, logout, me."""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_tokens import create_access_token, decode_access_token
from app.auth.passwords import verify_password
from app.database import get_async_session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(
    response: Response,
    login: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """Authenticate user and set HttpOnly JWT cookie."""
    # Generic error — never reveal which field is wrong
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )

    result = await session.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_error

    if not verify_password(password, user.password_hash):
        raise credentials_error

    # Update last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    await session.commit()

    token = create_access_token(user.id, user.login, user.role)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,   # set to True in prod with HTTPS
        samesite="lax",
        max_age=86400,  # 24 hours
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(key="access_token")
    return {"status": "ok"}


@router.get("/me")
async def me(
    access_token: Annotated[Optional[str], Cookie()] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """Return current user info or 401."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(access_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from uuid import UUID
    result = await session.execute(
        select(User).where(User.id == UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return {"id": str(user.id), "login": user.login, "role": user.role}
