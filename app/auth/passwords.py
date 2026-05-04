"""Password hashing utilities — bcrypt with constant-time compare.

Uses bcrypt directly (passlib 1.7.4 is incompatible with bcrypt>=5.0.0).
"""

import bcrypt


def hash_password(plain: str) -> str:
    """Return bcrypt hash of plaintext password."""
    if not plain:
        raise ValueError("Password cannot be empty")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time password verification — defends against timing attacks."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
