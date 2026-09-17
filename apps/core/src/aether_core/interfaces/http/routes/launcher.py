"""Convites consultam metadados atuais; nunca incluem caminhos ou credenciais."""

import json
from urllib.parse import urljoin, urlsplit

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.dialects.sqlite import insert

from aether_core.domain.errors import NotFoundError
from aether_core.infrastructure.db import LauncherSettingsRow
from aether_core.interfaces.http.deps import (
    InstanceServiceDep,
    SessionDep,
    SyncRead,
    SyncServiceDep,
    SyncWrite,
)

router = APIRouter(tags=["launcher"])


class LauncherSettings(BaseModel):
    public_url: str = Field(default="", max_length=2048)
    name: str = Field(default="", max_length=100)
    game_address: str = Field(default="", max_length=255)
    map_url: str = Field(default="", max_length=2048)
    cover_url: str = Field(default="", max_length=2048)
    cover_credit: str = Field(default="", max_length=500)

    @field_validator("public_url", "map_url", "cover_url")
    @classmethod
    def web_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(c.isspace() for c in value)
            or "\\" in value
        ):
            raise ValueError("Use uma URL http(s) sem usuário ou senha.")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Porta inválida.") from exc
        return value

    @field_validator("public_url")
    @classmethod
    def base_url(cls, value: str) -> str:
        if value and (urlsplit(value).query or urlsplit(value).fragment):
            raise ValueError("O endereço do Aether não aceita query ou fragmento.")
        return value.rstrip("/")

    @field_validator("game_address")
    @classmethod
    def game_host(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        if any(c.isspace() or c in "/\\?#@" for c in value):
            raise ValueError("Use apenas o domínio/IP e a porta do jogo.")
        try:
            parsed = urlsplit("//" + value)
            if not parsed.hostname or (parsed.port is not None and parsed.port < 1):
                raise ValueError()
        except ValueError as exc:
            raise ValueError("Endereço ou porta do jogo inválidos.") from exc
        return value


async def settings_for(session, instance_id: str) -> LauncherSettings:
    row = await session.get(LauncherSettingsRow, instance_id)
    return LauncherSettings.model_validate_json(row.payload) if row else LauncherSettings()


async def presentation(request: Request, instance, config: LauncherSettings) -> dict:
    cover, credit = config.cover_url, config.cover_credit
    if not cover:
        games = await request.app.state.catalog.list()
        game = next((g for g in games if g["provider_id"] == instance.provider_id), {})
        cover = game.get("banner_url", "")
        credit = game.get("atribuicao_da_imagem", "")
        if cover and config.public_url:
            # Prefixos de proxy pertencem ao endereço público configurado.
            cover = urljoin(config.public_url + "/", cover.lstrip("/"))
    return {
        "name": config.name.strip() or instance.name,
        "cover_url": cover,
        "cover_credit": credit,
    }


@router.get("/instances/{instance_id}/launcher")
async def get_settings(
    instance_id: str,
    request: Request,
    session: SessionDep,
    instances: InstanceServiceDep,
    _: SyncRead,
) -> dict:
    instance = await instances.get(instance_id)
    config = await settings_for(session, instance_id)
    return {
        "settings": config.model_dump(),
        "presentation": await presentation(request, instance, config),
    }


@router.put("/instances/{instance_id}/launcher")
async def save_settings(
    instance_id: str,
    body: LauncherSettings,
    request: Request,
    session: SessionDep,
    instances: InstanceServiceDep,
    _: SyncWrite,
) -> dict:
    instance = await instances.get(instance_id)
    statement = insert(LauncherSettingsRow).values(
        instance_id=instance_id, payload=json.dumps(body.model_dump())
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["instance_id"], set_={"payload": statement.excluded.payload}
        )
    )
    await session.commit()
    return {
        "settings": body.model_dump(),
        "presentation": await presentation(request, instance, body),
    }


@router.get("/public/launcher/{profile_id}")
async def resolve_invite(
    profile_id: str,
    request: Request,
    session: SessionDep,
    instances: InstanceServiceDep,
    sync: SyncServiceDep,
) -> dict:
    profile = await sync.get_profile(profile_id)
    sync.public_payload(profile)  # perfil sem publicação não é um convite válido
    instance = await instances.get(profile.instance_id)
    config = await settings_for(session, instance.id)
    if not config.public_url:
        raise NotFoundError("O administrador ainda não configurou o Launcher.")
    return {
        "version": 1,
        "instance_id": instance.id,
        "profile_id": profile.id,
        "profile_name": profile.name,
        "provider_id": instance.provider_id,
        "server": config.public_url,
        "game_address": config.game_address,
        "map_url": config.map_url,
        **await presentation(request, instance, config),
    }
