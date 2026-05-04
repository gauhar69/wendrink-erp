"""
WENDRINK ERP - Create initial users
Run ONCE on the server after migration:
  python create_users.py

Creates 4 users with full admin access:
  arman / wendrink2024
  aigul / wendrink2024
  partner1 / wendrink2024
  partner2 / wendrink2024

Users can change their passwords later.
"""

import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Settings ──────────────────────────────────────────────────────────────────
DATABASE_URL = "sqlite+aiosqlite:///./wendrink.db"

USERS = [
    {"login": "arman",    "password": "wendrink2024", "role": "admin"},
    {"login": "aigul",    "password": "wendrink2024", "role": "admin"},
    {"login": "partner1", "password": "wendrink2024", "role": "admin"},
    {"login": "partner2", "password": "wendrink2024", "role": "admin"},
]

# ── Hash passwords ─────────────────────────────────────────────────────────────
try:
    import bcrypt
    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
except ImportError:
    print("[ERROR] bcrypt not installed. Run: pip install bcrypt")
    sys.exit(1)

# ── UUID helper ────────────────────────────────────────────────────────────────
import uuid

def new_uuid() -> str:
    """Return UUID4 as 32-char hex (matches CHAR(32) column)."""
    return uuid.uuid4().hex


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check table exists
        try:
            await session.execute(text("SELECT 1 FROM users LIMIT 1"))
        except Exception:
            print("[ERROR] 'users' table not found. Run Alembic migration first:")
            print("  alembic upgrade head")
            await engine.dispose()
            sys.exit(1)

        now = datetime.now(timezone.utc)
        created = 0
        skipped = 0

        for u in USERS:
            # Check if login already exists
            result = await session.execute(
                text("SELECT id FROM users WHERE login = :login"),
                {"login": u["login"]},
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  [SKIP] '{u['login']}' — already exists")
                skipped += 1
                continue

            uid = new_uuid()
            phash = hash_password(u["password"])

            await session.execute(
                text("""
                    INSERT INTO users (id, login, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, :login, :hash, :role, 1, :now, :now)
                """),
                {
                    "id": uid,
                    "login": u["login"],
                    "hash": phash,
                    "role": u["role"],
                    "now": now.isoformat(),
                },
            )
            print(f"  [OK]   '{u['login']}' created (role: {u['role']})")
            created += 1

        await session.commit()

    await engine.dispose()

    print()
    print(f"Done: {created} created, {skipped} skipped.")
    if created > 0:
        print()
        print("All users have password: wendrink2024")
        print("Tell each person to remember it. You can change later.")


if __name__ == "__main__":
    asyncio.run(main())
