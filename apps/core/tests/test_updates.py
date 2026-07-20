"""Autoatualização: o que ela recusa, o que salva antes e quando reinicia.

Os testes montam repositórios git de verdade em tmp_path — o serviço conversa
com o git de verdade, e um dublê aqui esconderia justamente os erros de uso do
comando.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest
from aether_core.application.events import EventBus
from aether_core.application.updates import UpdateService
from aether_core.domain.errors import ValidationFailedError


def _git(dir_: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(dir_), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    """Um clone com origem local, para exercitar fetch/pull sem rede."""
    origem = tmp_path / "origem"
    origem.mkdir()
    _git(origem, "init", "--quiet", "--initial-branch=main")
    _git(origem, "config", "user.email", "teste@aether")
    _git(origem, "config", "user.name", "Teste")
    (origem / "README.md").write_text("v1\n")
    _git(origem, "add", ".")
    _git(origem, "commit", "--quiet", "-m", "primeiro")

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(origem), str(clone)], check=True, capture_output=True
    )
    _git(clone, "config", "user.email", "teste@aether")
    _git(clone, "config", "user.name", "Teste")
    return origem, clone


def _dados(tmp_path: Path) -> Path:
    d = tmp_path / "dados"
    d.mkdir()
    (d / "aether.db").write_bytes(b"banco" * 100)
    return d


def _servico(clone: Path, dados: Path, monkeypatch=None) -> UpdateService:
    svc = UpdateService(repo_dir=clone, data_dir=dados, bus=EventBus())
    if monkeypatch is not None:
        # Nenhum teste pode reiniciar o serviço da máquina que roda a suíte.
        monkeypatch.setattr(svc, "_agendar_reinicio", lambda: None)
    return svc


def test_status_fora_de_um_clone_git_explica_o_motivo(tmp_path):
    svc = _servico(tmp_path / "qualquer", _dados(tmp_path))
    status = svc.status()

    assert status.gerenciavel is False
    assert "clone git" in status.motivo


def test_status_traz_commit_e_quantos_faltam(tmp_path):
    origem, clone = _repo(tmp_path)
    (origem / "README.md").write_text("v2\n")
    _git(origem, "commit", "--quiet", "-am", "segundo")

    status = _servico(clone, _dados(tmp_path)).status()

    assert status.gerenciavel is True
    assert status.branch == "main"
    assert status.assunto == "primeiro"
    assert len(status.commit_curto) == 8
    assert status.commits_atras == 1


def test_alteracao_local_aparece_no_status(tmp_path):
    _, clone = _repo(tmp_path)
    (clone / "README.md").write_text("editado no servidor\n")

    status = _servico(clone, _dados(tmp_path)).status()

    assert status.alteracoes_locais == ["README.md"]


def test_atualizar_com_alteracao_local_e_recusado(tmp_path, monkeypatch):
    """Editar arquivo direto no servidor acontece na urgência. Sobrescrever
    esse ajuste sem avisar destrói trabalho de quem estava apagando incêndio."""

    async def caso():
        _, clone = _repo(tmp_path)
        (clone / "README.md").write_text("ajuste às pressas\n")
        svc = _servico(clone, _dados(tmp_path), monkeypatch)

        with pytest.raises(ValidationFailedError, match="alterações locais"):
            await svc.update()

    asyncio.run(caso())


def test_atualizar_fora_de_clone_e_recusado(tmp_path, monkeypatch):
    async def caso():
        svc = _servico(tmp_path / "sem-git", _dados(tmp_path), monkeypatch)
        with pytest.raises(ValidationFailedError, match="clone git"):
            await svc.update()

    asyncio.run(caso())


def test_atualizacao_copia_o_banco_antes_e_traz_o_commit_novo(tmp_path, monkeypatch):
    """O banco precisa estar salvo antes de qualquer migração nova rodar."""

    async def caso():
        origem, clone = _repo(tmp_path)
        dados = _dados(tmp_path)
        (origem / "README.md").write_text("v2\n")
        _git(origem, "commit", "--quiet", "-am", "segundo")

        svc = _servico(clone, dados, monkeypatch)
        # Sem dependências para instalar neste repositório de teste.
        monkeypatch.setattr(svc, "_rodar", _fake_rodar(svc, clone))

        resultado = await svc.update()

        copias = list((dados / "updates").glob("*/aether.db"))
        assert len(copias) == 1
        assert copias[0].read_bytes() == (b"banco" * 100)
        assert resultado["assunto"] == "segundo"
        assert resultado["reiniciando"] is True

    asyncio.run(caso())


def _fake_rodar(svc: UpdateService, clone: Path):
    """Deixa o git rodar de verdade e ignora uv/pnpm, que não existem no teste."""

    async def rodar(*comando: str) -> None:
        if comando[0] == "git":
            subprocess.run(["git", "-C", str(clone), *comando[1:]], check=True, capture_output=True)

    return rodar


def test_pull_que_falha_nao_reinicia_o_servico(tmp_path, monkeypatch):
    """Reiniciar depois de uma atualização incompleta trocaria um erro visível
    por um serviço quebrado."""

    async def caso():
        _, clone = _repo(tmp_path)
        svc = _servico(clone, _dados(tmp_path))
        reinicios: list[int] = []
        monkeypatch.setattr(svc, "_agendar_reinicio", lambda: reinicios.append(1))

        async def rodar_quebrado(*comando: str) -> None:
            raise ValidationFailedError("origem inacessível")

        monkeypatch.setattr(svc, "_rodar", rodar_quebrado)

        with pytest.raises(ValidationFailedError, match="origem inacessível"):
            await svc.update()

        assert reinicios == []

    asyncio.run(caso())


def test_progresso_sai_pelo_event_bus(tmp_path, monkeypatch):
    async def caso():
        origem, clone = _repo(tmp_path)
        (origem / "README.md").write_text("v2\n")
        _git(origem, "commit", "--quiet", "-am", "segundo")

        bus = EventBus()
        etapas: list[str] = []
        bus.subscribe("update.progress", lambda t, p: etapas.append(p.get("etapa", "")))

        svc = UpdateService(repo_dir=clone, data_dir=_dados(tmp_path), bus=bus)
        monkeypatch.setattr(svc, "_agendar_reinicio", lambda: None)
        monkeypatch.setattr(svc, "_rodar", _fake_rodar(svc, clone))

        await svc.update()

        assert "backup" in etapas
        assert "pull" in etapas
        assert "restart" in etapas
        assert etapas[-1] == "done"

    asyncio.run(caso())
