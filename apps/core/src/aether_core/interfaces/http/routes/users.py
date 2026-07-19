"""User management routes (owner only) and audit listing."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.domain.users import Role
from aether_core.interfaces.http.deps import AuditRead, AuthServiceDep, SessionDep, UsersManage

router = APIRouter(tags=["users"])


def _out(u) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": str(u.role),
        "email": u.email,
        "display_name": u.display_name,
        "label": u.label,
    }


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=200)
    role: Role
    email: str = Field(default="", max_length=200)
    display_name: str = Field(default="", max_length=100)


@router.get("/users")
async def list_users(auth: AuthServiceDep, _: UsersManage) -> list[dict]:
    return [{**_out(u), "created_at": u.created_at} for u in await auth.list_users()]


@router.post("/users", status_code=201)
async def create_user(body: CreateUserRequest, auth: AuthServiceDep, _: UsersManage) -> dict:
    user = await auth.create_user(
        body.username, body.password, body.role, body.email, body.display_name
    )
    return _out(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, auth: AuthServiceDep, acting: UsersManage) -> None:
    await auth.delete_user(user_id, acting)


@router.get("/audit")
async def audit_log(session: SessionDep, _: AuditRead, limit: int = 100) -> list[dict]:
    from aether_core.infrastructure.repositories import SqlAuditLog

    return await SqlAuditLog(session).list_recent(min(limit, 500))


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=200)


@router.post("/users/{user_id}/password", status_code=204)
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    request: Request,
    auth: AuthServiceDep,
    user: UsersManage,
) -> None:
    """O dono redefine a senha de outro usuário.

    É o substituto de "esqueci minha senha": o Aether não envia e-mail, então
    quem devolve acesso é o dono da instalação.
    """
    await auth.reset_password(user_id, body.new_password, user)

    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(f"users.password_reset target={user_id}", user, ip)
