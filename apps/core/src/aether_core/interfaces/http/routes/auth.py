"""Authentication routes."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.interfaces.http.deps import AuthServiceDep, CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)
    email: str = Field(default="", max_length=200)
    display_name: str = Field(default="", max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class ProfileRequest(BaseModel):
    email: str = Field(default="", max_length=200)
    display_name: str = Field(default="", max_length=100)


class RefreshRequest(BaseModel):
    refresh_token: str


def _user_out(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": str(user.role),
        "email": user.email,
        "display_name": user.display_name,
        "label": user.label,
    }


@router.get("/status")
async def status(auth: AuthServiceDep) -> dict:
    return {"setup_required": await auth.setup_required()}


@router.post("/setup", status_code=201)
async def setup(body: Credentials, auth: AuthServiceDep, request: Request) -> dict:
    user = await auth.setup_owner(body.username, body.password, body.email, body.display_name)
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


@router.put("/me")
async def update_me(
    body: ProfileRequest, auth: AuthServiceDep, user: CurrentUserDep, request: Request
) -> dict:
    atualizado = await auth.update_profile(user, body.email, body.display_name)
    await _audit(request, "auth.profile_updated", user)
    return _user_out(atualizado)


@router.post("/password")
async def change_password(
    body: ChangePasswordRequest,
    auth: AuthServiceDep,
    user: CurrentUserDep,
    request: Request,
) -> dict:
    """Troca a senha. As outras sessões desta conta param de valer."""
    access, refresh = await auth.change_password(user, body.current_password, body.new_password)
    await _audit(request, "auth.password_changed", user)
    return {"access_token": access, "refresh_token": refresh}


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
