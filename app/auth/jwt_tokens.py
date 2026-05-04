"""JWT generation and verification using HS256."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt

from app.config import get_settings


def create_access_token(user_id: UUID, login: str, role: str) -> str:
    """Create signed JWT containing user identity."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "login": login,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_lifetime_hours),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """Validate JWT signature + expiry. Returns payload or None on any failure."""
    if not token:
        return None
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None
