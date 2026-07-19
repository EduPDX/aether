"""Instalação a partir de catálogo e detecção de atualizações.

Sem rede: catálogo e downloader são dublês. O que importa aqui é a integridade
do que chega no disco e a comparação de versões.
"""

import asyncio
import hashlib

import pytest
from aether_core.application.sources import SourceService
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import Instance
from aether_sdk import SourceItem, SourceVersion

CONTEUDO = b"conteudo do jar" * 100
SHA1 = hashlib.sha1(CONTEUDO).hexdigest()
SHA512 = hashlib.sha512(CONTEUDO).hexdigest()


def _versao(**over) -> SourceVersion:
    base = dict(
        source_id="falso",
        project_id="proj1",
        version_id="v2",
        version_number="2.0.0",
        file_name="mod-2.0.0.jar",
        download_url="https://exemplo/mod-2.0.0.jar",
        size=len(CONTEUDO),
        sha1=SHA1,
        sha512=SHA512,
        game_versions=("1.20.1",),
        loaders=("forge",),
    )
    base.update(over)
    return SourceVersion(**base)


class _Catalogo:
    id = "falso"
    label = "Falso"
    requires_api_key = False

    def __init__(self, versoes=None, por_hash=None) -> None:
        self._versoes = versoes if versoes is not None else [_versao()]
        self._por_hash = por_hash or {}
        self.buscas: list[tuple] = []

    async def search(
        self, query, *, game_version=None, loader=None, categories=(), limit=20, offset=0
    ):
        self.buscas.append((query, game_version, loader, tuple(categories)))
        return [SourceItem(source_id=self.id, project_id="proj1", slug="mod", name="Mod")]

    def available_categories(self):
        return (("technology", "Tecnologia"), ("magic", "Magia"))

    async def versions(self, project_id, *, game_version=None, loader=None):
        return list(self._versoes)

    async def lookup_by_hash(self, sha1):
        return self._por_hash.get(sha1)


class _Baixador:
    def __init__(self, dados=CONTEUDO) -> None:
        self._dados = dados

    def stream(self, url):
        async def gen():
            for i in range(0, len(self._dados), 7):
                yield self._dados[i : i + 7]

        return gen()


class _Registro:
    def __init__(self, catalogo) -> None:
        self._catalogo = catalogo

    def get(self, _provider_id):
        catalogo = self._catalogo

        class _Provider:
            def content_sources(self):
                return [catalogo]

        return _Provider()

    def all(self):
        return {}


class _Bus:
    def __init__(self):
        self.eventos = []

    async def publish(self, topico, payload):
        self.eventos.append((topico, payload))


def _servico(tmp_path, catalogo=None, baixador=None):
    catalogo = catalogo or _Catalogo()
    return (
        SourceService(
            providers=_Registro(catalogo),
            downloader=baixador or _Baixador(),
            bus=_Bus(),
            content_dir_of=lambda _inst, _ct: tmp_path / "mods",
        ),
        catalogo,
    )


def _instancia() -> Instance:
    return Instance.new(
        "Srv", "minecraft", "/tmp/srv", provider_data={"game_version": "1.20.1", "loader": "Forge"}
    )


def test_install_writes_the_file_and_verifies_hashes(tmp_path):
    servico, _ = _servico(tmp_path)
    res = asyncio.run(servico.install(_instancia(), "mod", _versao()))

    destino = tmp_path / "mods" / "mod-2.0.0.jar"
    assert destino.read_bytes() == CONTEUDO
    assert res["size"] == len(CONTEUDO)
    assert not list((tmp_path / "mods").glob("*.parcial")), "não deixa arquivo parcial"


def test_corrupted_download_is_rejected_and_leaves_nothing(tmp_path):
    """O .jar vai ser executado pelo servidor: hash errado não pode entrar."""
    servico, _ = _servico(tmp_path, baixador=_Baixador(b"outra coisa"))

    with pytest.raises(ValidationFailedError, match="sha1"):
        asyncio.run(servico.install(_instancia(), "mod", _versao()))

    assert list((tmp_path / "mods").iterdir()) == [], "pasta limpa após falha"


def test_wrong_size_is_rejected(tmp_path):
    servico, _ = _servico(tmp_path)
    versao = _versao(sha1=None, sha512=None, size=999_999)

    with pytest.raises(ValidationFailedError, match="tamanho"):
        asyncio.run(servico.install(_instancia(), "mod", versao))


def test_existing_file_is_not_silently_overwritten(tmp_path):
    servico, _ = _servico(tmp_path)
    asyncio.run(servico.install(_instancia(), "mod", _versao()))

    with pytest.raises(ConflictError):
        asyncio.run(servico.install(_instancia(), "mod", _versao()))

    # com overwrite explícito, passa
    res = asyncio.run(servico.install(_instancia(), "mod", _versao(), overwrite=True))
    assert res["file"] == "mod-2.0.0.jar"


def test_file_name_from_the_catalog_cannot_escape_the_folder(tmp_path):
    """O nome vem de fora; sem basename daria para escrever fora da pasta."""
    servico, _ = _servico(tmp_path)
    asyncio.run(servico.install(_instancia(), "mod", _versao(file_name="../../fora.jar")))

    assert (tmp_path / "mods" / "fora.jar").is_file()
    assert not (tmp_path.parent / "fora.jar").exists()


def test_search_filters_by_the_instance_game_version_and_loader(tmp_path):
    servico, catalogo = _servico(tmp_path)
    asyncio.run(servico.search(_instancia(), "falso", "sodium"))

    assert catalogo.buscas == [("sodium", "1.20.1", "Forge", ())]


def test_search_passes_categories_and_loader_override(tmp_path):
    """Filtrar por categoria e por loader é o que torna o catálogo navegável."""
    servico, catalogo = _servico(tmp_path)
    asyncio.run(
        servico.search(
            _instancia(),
            "falso",
            "",
            categories=("technology", "magic"),
            loader_override="fabric",
        )
    )

    assert catalogo.buscas == [("", "1.20.1", "fabric", ("technology", "magic"))]


def test_filters_come_from_the_catalog(tmp_path):
    servico, _ = _servico(tmp_path)
    filtros = servico.filters(_instancia(), "falso")

    assert {"id": "technology", "label": "Tecnologia"} in filtros["categories"]
    # catálogo sem loaders declarados devolve lista vazia, não erro
    assert filtros["loaders"] == []


def test_updates_identify_installed_files_by_hash(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    # o usuário renomeou o arquivo: o nome não pode ser a fonte da verdade
    (mods / "renomeei-isso.jar").write_bytes(CONTEUDO)

    instalada = _versao(version_id="v1", version_number="1.0.0", file_name="mod-1.0.0.jar")
    catalogo = _Catalogo(versoes=[_versao()], por_hash={SHA1: instalada})
    servico, _ = _servico(tmp_path, catalogo=catalogo)

    candidatos = asyncio.run(servico.check_updates(_instancia(), "mod", "falso"))

    assert len(candidatos) == 1
    c = candidatos[0]
    assert c.file == "renomeei-isso.jar"
    assert (c.current_version, c.latest_version) == ("1.0.0", "2.0.0")


def test_up_to_date_mod_is_not_reported(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "mod-2.0.0.jar").write_bytes(CONTEUDO)

    catalogo = _Catalogo(versoes=[_versao()], por_hash={SHA1: _versao()})
    servico, _ = _servico(tmp_path, catalogo=catalogo)

    assert asyncio.run(servico.check_updates(_instancia(), "mod", "falso")) == []


def test_unknown_mod_is_skipped_not_an_error(tmp_path):
    """Mod privado ou de modpack não está no catálogo — e tudo bem."""
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "desconhecido.jar").write_bytes(b"nao esta no catalogo")

    servico, _ = _servico(tmp_path, catalogo=_Catalogo(por_hash={}))
    assert asyncio.run(servico.check_updates(_instancia(), "mod", "falso")) == []


def test_bulk_lookup_is_used_when_the_catalog_offers_it(tmp_path):
    """Com centenas de mods, consultar um a um estoura o limite de taxa."""
    mods = tmp_path / "mods"
    mods.mkdir()
    for i in range(5):
        (mods / f"m{i}.jar").write_bytes(CONTEUDO + bytes([i]))

    class _EmLote(_Catalogo):
        def __init__(self):
            super().__init__()
            self.chamadas_lote = 0
            self.chamadas_unitarias = 0

        async def lookup_many(self, hashes):
            self.chamadas_lote += 1
            return {}

        async def lookup_by_hash(self, sha1):
            self.chamadas_unitarias += 1
            return None

    catalogo = _EmLote()
    servico, _ = _servico(tmp_path, catalogo=catalogo)
    asyncio.run(servico.check_updates(_instancia(), "mod", "falso"))

    assert catalogo.chamadas_lote == 1
    assert catalogo.chamadas_unitarias == 0, "não deve cair no unitário havendo lote"


# --------------------------------------------------------- dependências --


class _CatalogoGrafo:
    """Catálogo com um grafo de dependências configurável."""

    id = "falso"
    label = "Falso"
    requires_api_key = False

    def __init__(self, grafo: dict, por_hash=None) -> None:
        # grafo: project_id -> (version_id, [(dep_project, kind)])
        self._grafo = grafo
        self._por_hash = por_hash or {}
        self.consultas: list[str] = []

    def _versao_de(self, pid: str) -> SourceVersion:
        vid, deps = self._grafo[pid]
        from aether_sdk import SourceDependency

        return _versao(
            project_id=pid,
            version_id=vid,
            file_name=f"{pid}.jar",
            dependencies=tuple(SourceDependency(project_id=d, kind=k) for d, k in deps),
        )

    async def search(self, query, **kw):
        return []

    def available_categories(self):
        return ()

    async def versions(self, project_id, *, game_version=None, loader=None):
        self.consultas.append(project_id)
        if project_id not in self._grafo:
            return []
        return [self._versao_de(project_id)]

    async def version_by_id(self, version_id):
        for pid, (vid, _) in self._grafo.items():
            if vid == version_id:
                return self._versao_de(pid)
        return None

    async def lookup_by_hash(self, sha1):
        return self._por_hash.get(sha1)


def test_plan_includes_required_dependencies_transitively(tmp_path):
    grafo = {
        "raiz": ("vr", [("libA", "required")]),
        "libA": ("va", [("libB", "required")]),
        "libB": ("vb", []),
    }
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    assert plano.ok
    # dependências primeiro, raiz por último
    assert [i.project_id for i in plano.items] == ["libB", "libA", "raiz"]
    assert plano.items[-1].required_by is None
    assert plano.items[0].required_by is not None


def test_plan_skips_optional_and_embedded_dependencies(tmp_path):
    grafo = {
        "raiz": ("vr", [("opc", "optional"), ("emb", "embedded"), ("obr", "required")]),
        "opc": ("vo", []),
        "emb": ("ve", []),
        "obr": ("vb", []),
    }
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    assert sorted(i.project_id for i in plano.items) == ["obr", "raiz"]


def test_plan_survives_a_dependency_cycle(tmp_path):
    """A→B→A não pode virar recursão infinita."""
    grafo = {
        "A": ("va", [("B", "required")]),
        "B": ("vb", [("A", "required")]),
    }
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "va"))

    assert sorted(i.project_id for i in plano.items) == ["A", "B"]


def test_diamond_dependency_is_installed_once(tmp_path):
    """raiz→A→lib e raiz→B→lib: a lib entra uma vez só."""
    grafo = {
        "raiz": ("vr", [("A", "required"), ("B", "required")]),
        "A": ("va", [("lib", "required")]),
        "B": ("vb", [("lib", "required")]),
        "lib": ("vl", []),
    }
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    ids = [i.project_id for i in plano.items]
    assert ids.count("lib") == 1
    assert sorted(ids) == ["A", "B", "lib", "raiz"]


def test_dependency_without_compatible_version_blocks_the_plan(tmp_path):
    """Melhor recusar do que instalar metade e o servidor não subir."""
    grafo = {"raiz": ("vr", [("some", "required")])}  # "some" não existe no catálogo
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    assert plano.missing == ["some"]
    assert plano.ok is False


def test_blocked_plan_is_refused_at_execution(tmp_path):
    grafo = {"raiz": ("vr", [("some", "required")])}
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))
    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    with pytest.raises(ValidationFailedError, match="sem versão compatível"):
        asyncio.run(servico.install_plan(_instancia(), "mod", "falso", plano))

    assert not (tmp_path / "mods").exists() or list((tmp_path / "mods").iterdir()) == []


def test_already_installed_dependency_is_not_reinstalled(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "ja-tenho.jar").write_bytes(CONTEUDO)

    grafo = {"raiz": ("vr", [("libA", "required")]), "libA": ("va", [])}
    instalada = _versao(project_id="libA", version_id="va")
    catalogo = _CatalogoGrafo(grafo, por_hash={SHA1: instalada})
    servico, _ = _servico(tmp_path, catalogo=catalogo)

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    assert [i.project_id for i in plano.items] == ["raiz"]
    assert plano.already_installed == ["libA"]


def test_incompatible_installed_mod_is_reported(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "briga.jar").write_bytes(CONTEUDO)

    grafo = {"raiz": ("vr", [("inimigo", "incompatible")])}
    instalada = _versao(project_id="inimigo", version_id="vi")
    catalogo = _CatalogoGrafo(grafo, por_hash={SHA1: instalada})
    servico, _ = _servico(tmp_path, catalogo=catalogo)

    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    assert plano.conflicts == ["inimigo"]
    assert plano.ok, "incompatibilidade avisa, mas não bloqueia — a decisão é do usuário"


def test_executing_a_plan_installs_every_item(tmp_path):
    grafo = {
        "raiz": ("vr", [("libA", "required")]),
        "libA": ("va", []),
    }
    servico, _ = _servico(tmp_path, catalogo=_CatalogoGrafo(grafo))
    plano = asyncio.run(servico.plan_install(_instancia(), "mod", "falso", "vr"))

    res = asyncio.run(servico.install_plan(_instancia(), "mod", "falso", plano))

    assert res["count"] == 2
    assert sorted(p.name for p in (tmp_path / "mods").iterdir()) == ["libA.jar", "raiz.jar"]
