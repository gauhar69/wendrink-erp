#!/usr/bin/env python
"""
WENDRINK ERP
Creates the first admin user in the database.
WARNING: This script interacts with the production database.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Add the project root to sys.path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.user import User

try:
    from passlib.context import CryptContext
except ImportError:
    print("ERROR: passlib is not installed.")
    print("Please install passlib (added in Step 3.2) or run this script after Step 3.2 is deployed.")
    print("pip install passlib[bcrypt]>=1.7.4")
    sys.exit(1)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin():
    print("=== Create First Admin User ===")
    login = input("Enter admin login (e.g. arman): ").strip()
    if not login:
        print("Login cannot be empty.")
        return

    password = input("Enter admin password: ").strip()
    if not password:
        print("Password cannot be empty.")
        return

    password_hash = pwd_context.hash(password)

    async with async_session_maker() as session:
        async with session.begin():
            # Check if user exists
            result = await session.execute(select(User).where(User.login == login))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"User '{login}' already exists.")
                return

            # Create user
            user = User(
                id=uuid.uuid4().hex,
                login=login,
                password_hash=password_hash,
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(user)
            print(f"Creating user '{login}' with role 'admin'...")

    print("Success! Admin user created.")

if __name__ == "__main__":
    asyncio.run(create_admin())
