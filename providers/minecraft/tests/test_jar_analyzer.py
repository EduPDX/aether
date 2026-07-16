"""Tests for the jar analyzer using synthetic jars built in-memory."""

import zipfile
from pathlib import Path

import pytest
from aether_provider_minecraft.content.jar_analyzer import (
    JarModAnalyzer,
    pretty_version_range,
)

FORGE_TOML = """\
modLoader="javafml"
loaderVersion="[47,)"
license="MIT"
[[mods]]
modId="examplemod"
version="1.2.3"
displayName="Example Mod"
description='''A test mod'''
authors="Tester"
displayURL="https://example.com"
[[dependencies.examplemod]]
modId="minecraft"
mandatory=true
versionRange="[1.20.1]"
[[dependencies.examplemod]]
modId="forge"
mandatory=true
versionRange="[47,)"
"""

FABRIC_JSON = """\
{
  "schemaVersion": 1,
  "id": "fabricmod",
  "version": "2.0.0",
  "name": "Fabric Mod",
  "description": "A fabric test mod",
  "authors": [{"name": "Alice"}, "Bob"],
  "license": "LGPL-3.0",
  "environment": "client",
  "icon": "assets/fabricmod/icon.png",
  "contact": {"homepage": "https://fabric.example"},
  "depends": {"minecraft": "~1.20", "fabricloader": ">=0.15"}
}
"""

MALFORMED_TOML = """\
modLoader="javafml"
[[mods]]
modId="brokenmod"
displayName="Broken Mod"
version="0.9"
description=\"\"\"multi
line \\ bad escape\"\"\"
[[dependencies.brokenmod]]
modId="minecraft"
versionRange="[1.19.2]"
this line is not valid toml at all !!!
"""

JARVERSION_TOML = """\
modLoader="javafml"
license="MIT"
[[mods]]
modId="manifestmod"
displayName="Manifest Mod"
version="${file.jarVersion}"
"""

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def make_jar(tmp_path: Path, name: str, files: dict[str, bytes | str]) -> Path:
    jar = tmp_path / name
    with zipfile.ZipFile(jar, "w") as zf:
        for arcname, data in files.items():
            zf.writestr(arcname, data)
    return jar


@pytest.fixture
def analyzer() -> JarModAnalyzer:
    return JarModAnalyzer()


def test_forge_mod(analyzer, tmp_path):
    jar = make_jar(
        tmp_path,
        "examplemod-1.2.3.jar",
        {"META-INF/mods.toml": FORGE_TOML, "assets/examplemod/icon.png": PNG},
    )
    meta = analyzer.analyze(jar)
    assert meta.error is None
    assert meta.content_id == "examplemod"
    assert meta.display_name == "Example Mod"
    assert meta.version == "1.2.3"
    assert meta.loader == "Forge"
    assert meta.game_version == "1.20.1"
    assert meta.authors == "Tester"
    assert meta.license == "MIT"
    assert meta.icon_png == PNG
    dep_ids = {d.content_id for d in meta.dependencies}
    assert {"minecraft", "forge"} <= dep_ids


def test_neoforge_mod(analyzer, tmp_path):
    jar = make_jar(tmp_path, "x.jar", {"META-INF/neoforge.mods.toml": FORGE_TOML})
    assert analyzer.analyze(jar).loader == "NeoForge"


def test_fabric_mod(analyzer, tmp_path):
    jar = make_jar(
        tmp_path,
        "fabricmod-2.0.0.jar",
        {"fabric.mod.json": FABRIC_JSON, "assets/fabricmod/icon.png": PNG},
    )
    meta = analyzer.analyze(jar)
    assert meta.loader == "Fabric"
    assert meta.content_id == "fabricmod"
    assert meta.version == "2.0.0"
    assert meta.authors == "Alice, Bob"
    assert meta.client_only is True
    assert meta.game_version == "1.20"
    assert meta.icon_png == PNG


def test_malformed_toml_falls_back_to_regex(analyzer, tmp_path):
    jar = make_jar(tmp_path, "broken.jar", {"META-INF/mods.toml": MALFORMED_TOML})
    meta = analyzer.analyze(jar)
    assert meta.error is None
    assert meta.content_id == "brokenmod"
    assert meta.display_name == "Broken Mod"
    assert meta.game_version == "1.19.2"


def test_jarversion_placeholder_resolved_from_manifest(analyzer, tmp_path):
    jar = make_jar(
        tmp_path,
        "manifestmod.jar",
        {
            "META-INF/mods.toml": JARVERSION_TOML,
            "META-INF/MANIFEST.MF": "Manifest-Version: 1.0\nImplementation-Version: 3.4.5\n",
        },
    )
    meta = analyzer.analyze(jar)
    assert meta.version == "3.4.5"


def test_game_version_guessed_from_filename(analyzer, tmp_path):
    jar = make_jar(tmp_path, "somemod-1.20.1-4.5.jar", {"META-INF/mods.toml": JARVERSION_TOML})
    meta = analyzer.analyze(jar)
    assert meta.game_version == "1.20.1"


def test_corrupted_jar_reports_error(analyzer, tmp_path):
    bad = tmp_path / "bad.jar"
    bad.write_bytes(b"this is not a zip")
    meta = analyzer.analyze(bad)
    assert meta.error is not None
    assert meta.display_name == "bad"


def test_unknown_jar_uses_filename(analyzer, tmp_path):
    jar = make_jar(tmp_path, "mystery-mod.jar", {"whatever.txt": "hi"})
    meta = analyzer.analyze(jar)
    assert meta.error is None
    assert meta.display_name == "mystery-mod"
    assert meta.loader == ""


@pytest.mark.parametrize(
    ("raw", "pretty"),
    [
        ("[1.20.1]", "1.20.1"),
        ("[1.20,)", "1.20+"),
        ("[1.20,1.21)", "1.20 – 1.21"),
        ("(,1.19]", "≤ 1.19"),
        (">=1.18", "1.18"),
        ("", ""),
        (["1.19", "1.20"], "1.19, 1.20"),
    ],
)
def test_pretty_version_range(raw, pretty):
    assert pretty_version_range(raw) == pretty
