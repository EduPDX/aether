"""Authentication routes."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.interfaces.http.deps import AuthServiceDep, CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


def _user_out(user) -> dict:
    return {"id": user.id, "username": user.username, "role": str(user.role)}


@router.get("/status")
async def status(auth: AuthServiceDep) -> dict:
    return {"setup_required": await auth.setup_required()}


@router.post("/setup", status_code=201)
async def setup(body: Credentials, auth: AuthServiceDep, request: Request) -> dict:
    user = await auth.setup_owner(body.username, body.password)
    access, refresh, _ = await auth.login(body.username, body.password)
    await _audit(request, f"auth.setup owner={user.username}", user)
    return {"user": _user_out(user), "access_token": access, "refresh_token": refresh}


@router.post("/login")
async def login(body: Credentials, auth: AuthServiceDep, request: Request) -> dict:
    access, refresh, user = await auth.login(body.username, body.password)
    await _audit(request, "auth.login", user)
    return {"user": _user_out(user), "access_token": access, "refresh_token": refresh}


@router.post("/refresh")
async def refresh(body: RefreshRequest, auth: AuthServiceDep) -> dict:
    return {"access_token": await auth.refresh(body.refresh_token)}


@router.get("/me")
async def me(user: CurrentUserDep) -> dict:
    return _user_out(user)


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
