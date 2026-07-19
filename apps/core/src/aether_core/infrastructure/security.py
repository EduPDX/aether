"""Password hashing (Argon2) and JWT issuing/validation."""

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

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


def load_or_create_sync_key(data_dir: Path) -> Ed25519PrivateKey:
    """Ed25519 signing key for sync manifests, generated once per install."""
    path = data_dir / "sync_signing.key"
    if path.is_file():
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(path.read_text().strip()))
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    path.write_text(raw.hex())
    return key


def sign_payload(key: Ed25519PrivateKey, payload: bytes) -> str:
    return key.sign(payload).hex()


def public_key_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


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


DOWNLOAD_TTL = timedelta(minutes=2)


def issue_download_token(secret: str, user_id: str, instance_id: str, path: str) -> str:
    """Token curto para o navegador baixar sem cabeçalho de autorização.

    Um download nativo é uma navegação: o navegador não manda o Bearer. Sem
    isso, o dashboard precisa buscar o arquivo por fetch e materializá-lo em
    memória — o que quebra em pastas grandes. O token é preso à instância e ao
    caminho para não virar uma chave genérica de leitura de arquivos.
    """
    payload = {
        "sub": user_id,
        "type": "download",
        "iid": instance_id,
        "path": path,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + DOWNLOAD_TTL,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_download_token(secret: str, token: str, instance_id: str, path: str) -> str:
    """Valida o token e confere que é exatamente para este arquivo."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("link de download expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("link de download inválido") from exc
    if payload.get("type") != "download":
        raise AuthenticationError("wrong token type")
    if payload.get("iid") != instance_id or payload.get("path") != path:
        raise AuthenticationError("link de download não corresponde ao arquivo")
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("invalid token")
    return str(sub)


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
