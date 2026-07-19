"""Users, roles and permissions.

v0.3 ships four built-in roles with fixed permission sets; user-defined
roles arrive with the RBAC tables in a later version — the permission
*strings* are the stable contract.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.OWNER: {"*"},
    Role.ADMIN: {
        "instances.read",
        "instances.write",
        "content.read",
        "content.write",
        "power.use",
        "console.use",
        "audit.read",
        "files.read",
        "files.write",
        "config.read",
        "config.write",
        "sync.read",
        "sync.write",
        "backups.read",
        "backups.write",
    },
    Role.MODERATOR: {
        "instances.read",
        "content.read",
        "power.use",
        "console.use",
        # Vê e cria backup, mas não restaura nem apaga: restaurar sobrescreve
        # o mundo, e isso é decisão de quem administra.
        "backups.read",
    },
    Role.VIEWER: {"instances.read", "content.read"},
}


@dataclass(frozen=True)
class User:
    id: str
    username: str
    password_hash: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(username: str, password_hash: str, role: Role) -> "User":
        return User(
            id=uuid.uuid4().hex,
            username=username,
            password_hash=password_hash,
            role=role,
        )

    def has_permission(self, permission: str) -> bool:
        perms = ROLE_PERMISSIONS.get(self.role, set())
        return "*" in perms or permission in perms
