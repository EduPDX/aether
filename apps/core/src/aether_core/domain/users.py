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
    """Contato do administrador. Informativo: o Aether não envia e-mail, então
    não serve para recuperar senha — quem recupera é o dono da instalação."""
    email: str = ""
    """Nome de exibição; vazio = usa o nome de usuário."""
    display_name: str = ""
    """Muda a cada troca de senha e é gravado no token.

    Sem isso, trocar a senha não derrubaria as sessões antigas: o JWT é sem
    estado e um token roubado continuaria valendo até expirar — sete dias, no
    caso do refresh. Trocar a senha achando que cortou o acesso, sem cortar,
    é pior que não ter a funcionalidade.
    """
    token_epoch: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def label(self) -> str:
        return self.display_name or self.username

    @staticmethod
    def new(
        username: str,
        password_hash: str,
        role: Role,
        email: str = "",
        display_name: str = "",
    ) -> "User":
        return User(
            id=uuid.uuid4().hex,
            username=username,
            password_hash=password_hash,
            role=role,
            email=email,
            display_name=display_name,
        )

    def has_permission(self, permission: str) -> bool:
        perms = ROLE_PERMISSIONS.get(self.role, set())
        return "*" in perms or permission in perms
