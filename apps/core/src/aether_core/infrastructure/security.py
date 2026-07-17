"""Password hashing (Argon2) and JWT issuing/validation."""

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from aether_core.domain.errors import AuthenticationError

_hasher = PasswordHasher()

ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=7)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def load_or_create_secret(data_dir: Path) -> str:
    """JWT signing secret, generated once per installation."""
    path = data_dir / "secret.key"
    if path.is_file():
        return path.read_text().strip()
    secret = secrets.token_hex(32)
    path.write_text(secret)
    return secret


TokenType = Literal["access", "refresh"]


def issue_token(secret: str, user_id: str, token_type: TokenType) -> str:
    ttl = ACCESS_TTL if token_type == "access" else REFRESH_TTL
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + ttl,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(secret: str, token: str, expected_type: TokenType) -> str:
    """Validates the token and returns the user id."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("invalid token") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("wrong token type")
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("invalid token")
    return str(sub)
