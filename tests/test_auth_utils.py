"""Tests for auth utilities (passwords + JWT).

Run: pytest tests/test_auth_utils.py -v
"""

import uuid
import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.jwt_tokens import create_access_token, decode_access_token


class TestPasswords:
    def test_hash_is_not_plain(self):
        hashed = hash_password("foo")
        assert hashed != "foo"

    def test_hash_is_string(self):
        hashed = hash_password("foo")
        assert isinstance(hashed, str)

    def test_verify_correct_password(self):
        hashed = hash_password("foo")
        assert verify_password("foo", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("foo")
        assert verify_password("wrong", hashed) is False

    def test_empty_plain_raises(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_verify_empty_returns_false(self):
        assert verify_password("", "somehash") is False
        assert verify_password("foo", "") is False


class TestJWT:
    def test_create_and_decode(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "arman", "admin")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["login"] == "arman"
        assert payload["role"] == "admin"
        assert payload["sub"] == str(uid)

    def test_garbage_token_returns_none(self):
        assert decode_access_token("garbage.token.here") is None

    def test_empty_token_returns_none(self):
        assert decode_access_token("") is None
