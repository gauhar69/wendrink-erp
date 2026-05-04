"""WENDRINK ERP - User model for authentication."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    """Application user with login + bcrypt-hashed password."""

    __tablename__ = "users"

    login: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="Username for login (case-sensitive)",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="bcrypt hash, never plain password",
    )

    role: Mapped[str] = mapped_column(
        String(32), default="admin", nullable=False,
        comment="admin | manager | viewer (semantics in app/dependencies.py)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

