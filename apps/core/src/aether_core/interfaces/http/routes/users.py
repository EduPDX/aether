"""User management routes (owner only) and audit listing."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aether_core.domain.users import Role
from aether_core.interfaces.http.deps import AuditRead, AuthServiceDep, SessionDep, UsersManage

router = APIRouter(tags=["users"])


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=200)
    role: Role


@router.get("/users")
async def list_users(auth: AuthServiceDep, _: UsersManage) -> list[dict]:
    return [
        {"id": u.id, "username": u.username, "role": str(u.role), "created_at": u.created_at}
        for u in await auth.list_users()
    ]


@router.post("/users", status_code=201)
async def create_user(body: CreateUserRequest, auth: AuthServiceDep, _: UsersManage) -> dict:
    user = await auth.create_user(body.username, body.password, body.role)
    return {"id": user.id, "username": user.username, "role": str(user.role)}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, auth: AuthServiceDep, acting: UsersManage) -> None:
    await auth.delete_user(user_id, acting)


@router.get("/audit")
async def audit_log(session: SessionDep, _: AuditRead, limit: int = 100) -> list[dict]:
    from aether_core.infrastructure.repositories import SqlAuditLog

    return await SqlAuditLog(session).list_recent(min(limit, 500))
