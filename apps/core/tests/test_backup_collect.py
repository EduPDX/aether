"""Seleção de arquivos do backup — independente da versão do Python.

Regressão que motivou estes testes: ``Path.glob("world/**")`` devolve apenas
diretórios até o 3.12 e passou a incluir arquivos no 3.13. Depender disso faria
o backup sair vazio em produção (3.11) enquanto passava em quem desenvolve num
Python novo.
"""

from pathlib import Path

from aether_core.application.backups import collect_files
from aether_provider_minecraft.server.backup import backup_spec, level_name
from aether_sdk import BackupSpec


def _mundo(root: Path, nome: str = "world") -> None:
    (root / nome / "region").mkdir(parents=True)
    (root / nome / "level.dat").write_bytes(b"nivel")
    (root / nome / "region" / "r.0.0.mca").write_bytes(b"regiao")
    (root / nome / "playerdata").mkdir()
    (root / nome / "playerdata" / "uuid.dat").write_bytes(b"jogador")


def test_directory_pattern_collects_nested_files(tmp_path):
    _mundo(tmp_path)
    spec = BackupSpec(include=("world/**",))

    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}

    assert rel == {
        "world/level.dat",
        "world/region/r.0.0.mca",
        "world/playerdata/uuid.dat",
    }


def test_plain_file_patterns_are_collected(tmp_path):
    (tmp_path / "server.properties").write_text("level-name=world")
    (tmp_path / "ops.json").write_text("[]")
    spec = BackupSpec(include=("server.properties", "ops.json", "nao-existe.json"))

    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}
    assert rel == {"server.properties", "ops.json"}


def test_exclusions_win_over_inclusions(tmp_path):
    _mundo(tmp_path)
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "sodium.jar").write_bytes(b"jar")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "latest.log").write_text("log")

    spec = BackupSpec(include=("world/**", "mods/**", "logs/**"), exclude=("*.jar", "logs/**"))
    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}

    assert all(not r.endswith(".jar") for r in rel)
    assert all(not r.startswith("logs/") for r in rel)
    assert "world/level.dat" in rel


def test_missing_directory_is_not_an_error(tmp_path):
    """Servidor sem Nether/End separados não deve quebrar o backup."""
    _mundo(tmp_path)
    spec = BackupSpec(include=("world/**", "world_nether/**", "world_the_end/**"))
    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}
    assert "world/level.dat" in rel


def test_minecraft_spec_follows_level_name(tmp_path):
    """Mundo renomeado: o backup precisa seguir `level-name`, não o padrão."""
    (tmp_path / "server.properties").write_text("level-name=meu_mundo\nmax-players=20\n")
    _mundo(tmp_path, "meu_mundo")
    (tmp_path / "world").mkdir()
    (tmp_path / "world" / "antigo.dat").write_bytes(b"nao deve entrar")

    assert level_name(tmp_path) == "meu_mundo"
    spec = backup_spec(tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}

    assert "meu_mundo/level.dat" in rel
    assert "meu_mundo/region/r.0.0.mca" in rel
    assert "server.properties" in rel
    assert "world/antigo.dat" not in rel, "não deve pegar a pasta que não é o mundo ativo"


def test_minecraft_spec_excludes_jars_and_libraries(tmp_path):
    (tmp_path / "server.properties").write_text("level-name=world")
    _mundo(tmp_path)
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "create.jar").write_bytes(b"x" * 100)
    (tmp_path / "libraries" / "net").mkdir(parents=True)
    (tmp_path / "libraries" / "net" / "lib.jar").write_bytes(b"x" * 100)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "create.toml").write_text("a=1")

    spec = backup_spec(tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, spec)}

    assert "config/create.toml" in rel, "configuração é insubstituível e deve entrar"
    assert not any(r.endswith(".jar") for r in rel)
    assert not any(r.startswith("libraries/") for r in rel)


def test_level_name_falls_back_when_properties_is_absent(tmp_path):
    assert level_name(tmp_path) == "world"
