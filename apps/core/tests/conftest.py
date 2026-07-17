"""Shared fixtures: isolated app instance and synthetic mod jars."""

import zipfile
from pathlib import Path

import pytest
from aether_core.infrastructure.settings import AppSettings
from aether_core.interfaces.http import create_app
from fastapi.testclient import TestClient

FORGE_TOML_TEMPLATE = """\
modLoader="javafml"
loaderVersion="[47,)"
license="MIT"
[[mods]]
modId="{modid}"
version="{version}"
displayName="{name}"
description='''test mod'''
authors="Tester"
[[dependencies.{modid}]]
modId="minecraft"
mandatory=true
versionRange="[1.20.1]"
"""

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def make_mod_jar(
    folder: Path,
    file_name: str,
    modid: str,
    version: str = "1.0.0",
    name: str | None = None,
    with_icon: bool = False,
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    jar = folder / file_name
    files = {
        "META-INF/mods.toml": FORGE_TOML_TEMPLATE.format(
            modid=modid, version=version, name=name or modid.title()
        )
    }
    if with_icon:
        files[f"assets/{modid}/icon.png"] = PNG
    with zipfile.ZipFile(jar, "w") as zf:
        for arcname, data in files.items():
            zf.writestr(arcname, data)
    return jar


@pytest.fixture
def client(tmp_path: Path):
    settings = AppSettings(data_dir=tmp_path / "aether-data")
    # Context manager: keeps a single event loop for every request (the
    # supervisor holds asyncio state) and runs the lifespan shutdown.
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def mods_dir(tmp_path: Path) -> Path:
    d = tmp_path / "instance-a"
    d.mkdir()
    return d


def create_instance(client: TestClient, root_dir: Path, name: str = "Test") -> str:
    res = client.post(
        "/api/v1/instances",
        json={
            "name": name,
            "provider_id": "minecraft",
            "root_dir": str(root_dir),
            "content_dirs": {"mod": "."},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]
