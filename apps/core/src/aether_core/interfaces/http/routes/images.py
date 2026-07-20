"""Rotas do gerenciador de imagens de container."""

from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel

from aether_core.interfaces.http.deps import InstancesRead, InstancesWrite

router = APIRouter(prefix="/images", tags=["images"])


class PullImageRequest(BaseModel):
    image: str


@router.get("")
async def list_images(request: Request, _: InstancesRead) -> dict:
    svc = request.app.state.images
    return {
        "referenced": svc.referenced_images(),
        "installed": [asdict(i) for i in await svc.list_installed()],
        "pulling": svc.pulling(),
    }


@router.post("/pull", status_code=202)
async def pull_image(request: Request, body: PullImageRequest, _: InstancesWrite) -> dict:
    await request.app.state.images.start_pull(body.image)
    return {"image": body.image, "status": "pulling"}


@router.delete("", status_code=204)
async def remove_image(request: Request, image: str, _: InstancesWrite) -> None:
    await request.app.state.images.remove(image)
