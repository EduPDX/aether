"""Sync profile administration routes."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aether_core.application.sync import SyncProfile, SyncRules
from aether_core.interfaces.http.deps import (
    InstanceServiceDep,
    SyncRead,
    SyncServiceDep,
    SyncWrite,
)

router = APIRouter(prefix="/instances/{instance_id}/sync-profiles", tags=["sync"])


class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    channel: str = Field(default="stable", pattern="^(stable|beta)$")
    rules: SyncRules


class UpdateRulesRequest(BaseModel):
    rules: SyncRules


def _out(profile: SyncProfile) -> dict:
    return {
        "id": profile.id,
        "instance_id": profile.instance_id,
        "name": profile.name,
        "channel": profile.channel,
        "rules": profile.rules.model_dump(),
        "published_at": profile.published_at,
        "files": len(profile.manifest["files"]) if profile.manifest else None,
        "total_size": profile.manifest["total_size"] if profile.manifest else None,
    }


@router.get("")
async def list_profiles(
    instance_id: str,
    instances: InstanceServiceDep,
    sync: SyncServiceDep,
    _: SyncRead,
) -> list[dict]:
    instance = await instances.get(instance_id)
    return [_out(p) for p in await sync.list_profiles(instance)]


@router.post("", status_code=201)
async def create_profile(
    instance_id: str,
    body: CreateProfileRequest,
    instances: InstanceServiceDep,
    sync: SyncServiceDep,
    _: SyncWrite,
) -> dict:
    instance = await instances.get(instance_id)
    return _out(await sync.create_profile(instance, body.name, body.channel, body.rules))


@router.put("/{profile_id}/rules")
async def update_rules(
    instance_id: str,
    profile_id: str,
    body: UpdateRulesRequest,
    sync: SyncServiceDep,
    _: SyncWrite,
) -> dict:
    return _out(await sync.update_rules(profile_id, body.rules))


@router.post("/{profile_id}/publish")
async def publish(
    instance_id: str,
    profile_id: str,
    instances: InstanceServiceDep,
    sync: SyncServiceDep,
    _: SyncWrite,
) -> dict:
    instance = await instances.get(instance_id)
    return _out(await sync.publish(instance, profile_id))


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    instance_id: str, profile_id: str, sync: SyncServiceDep, _: SyncWrite
) -> None:
    await sync.delete_profile(profile_id)
