"""Analyzer de ModInfo.xml: pasta, zip e os dois dialetos do formato."""

import zipfile

from aether_provider_sevendays.content.modinfo_analyzer import ModInfoAnalyzer

MODINFO_V2 = """<?xml version="1.0" encoding="UTF-8" ?>
<xml>
\t<Name value="SomeMod" />
\t<DisplayName value="Some Mod" />
\t<Version value="1.2.3" />
\t<Description value="Faz coisas" />
\t<Author value="Fulano" />
\t<Website value="https://example.com" />
</xml>
"""

MODINFO_V1 = """<?xml version="1.0" encoding="UTF-8" ?>
<xml>
\t<ModInfo>
\t\t<Name value="OldMod" />
\t\t<Version value="0.9" />
\t</ModInfo>
</xml>
"""


def test_mod_em_pasta_formato_v2(tmp_path):
    pasta = tmp_path / "SomeMod"
    pasta.mkdir()
    (pasta / "ModInfo.xml").write_text(MODINFO_V2, encoding="utf-8")
    meta = ModInfoAnalyzer("mod").analyze(pasta)
    assert meta.display_name == "Some Mod"
    assert meta.version == "1.2.3"
    assert meta.authors == "Fulano"
    assert meta.homepage == "https://example.com"
    assert meta.error is None


def test_mod_em_pasta_formato_antigo(tmp_path):
    pasta = tmp_path / "OldMod"
    pasta.mkdir()
    (pasta / "ModInfo.xml").write_text(MODINFO_V1, encoding="utf-8")
    meta = ModInfoAnalyzer("mod").analyze(pasta)
    assert meta.display_name == "OldMod"
    assert meta.version == "0.9"


def test_mod_em_zip_ainda_nao_extraido(tmp_path):
    """Mod baixado do Nexus chega como zip; o painel deve identificá-lo
    antes mesmo de o usuário extrair."""
    arquivo = tmp_path / "SomeMod.zip"
    with zipfile.ZipFile(arquivo, "w") as zf:
        zf.writestr("SomeMod/ModInfo.xml", MODINFO_V2)
    meta = ModInfoAnalyzer("mod").analyze(arquivo)
    assert meta.display_name == "Some Mod"


def test_pasta_sem_modinfo_degrada_com_erro(tmp_path):
    pasta = tmp_path / "NaoEhMod"
    pasta.mkdir()
    meta = ModInfoAnalyzer("mod").analyze(pasta)
    assert meta.display_name == "NaoEhMod"
    assert meta.error is not None
