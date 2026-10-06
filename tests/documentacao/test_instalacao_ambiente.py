"""Testes da instalação do ambiente: as duas skills e os subagentes, e a conferência do que envelheceu."""

from pathlib import Path

import pytest

from graphow.documentacao.instalacao_ambiente import InstaladorDoAmbiente, RepositorioSemAmbiente

RAIZ_DO_REPOSITORIO: Path = Path(__file__).resolve().parents[2]
EXECUTAVEL: str = "C:/venv/Scripts/graphow.exe"


def test_instalacao_copia_as_duas_skills_e_os_subagentes_nominal(tmp_path: Path) -> None:
    """A orquestração e os subagentes, que se copiavam à mão, chegam junto da graphow-mcp."""
    resultado = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path, EXECUTAVEL).instalar()

    assert dict(resultado.arquivos_por_skill).keys() == {"graphow-mcp", "graphow-orquestracao"}
    assert (tmp_path / "skills" / "graphow-orquestracao" / "SKILL.md").is_file()
    assert {agente.name for agente in resultado.agentes} >= {"graphow-condutor.md", "graphow-executor.md"}
    condutor = (tmp_path / "agents" / "graphow-condutor.md").read_text(encoding="utf-8")
    assert f'command: "{EXECUTAVEL}"' in condutor


def test_conferencia_acusa_o_que_falta_e_o_que_mudou_nominal(tmp_path: Path) -> None:
    """Antes da instalação falta tudo; depois, só o arquivo mexido à mão aparece."""
    instalador = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path, EXECUTAVEL)
    assert instalador.desatualizados()

    instalador.instalar()
    assert instalador.desatualizados() == ()
    executor = tmp_path / "agents" / "graphow-executor.md"
    executor.write_text(executor.read_text(encoding="utf-8") + "editado\n", encoding="utf-8")

    assert instalador.desatualizados() == (executor,)


def test_subagente_instalado_com_outro_executavel_esta_desatualizado_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a cópia antiga com `command: graphow` sem caminho conta como envelhecida."""
    InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path, "graphow").instalar()

    desatualizados = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path, EXECUTAVEL).desatualizados()

    assert tmp_path / "agents" / "graphow-condutor.md" in desatualizados
    assert tmp_path / "agents" / "graphow-explorador.md" not in desatualizados


def test_origem_fora_de_um_checkout_e_recusada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: pacote instalado sem checkout; a recusa diz onde procurou e nada é gravado."""
    with pytest.raises(RepositorioSemAmbiente) as erro:
        InstaladorDoAmbiente(tmp_path / "nada", tmp_path / "claude", EXECUTAVEL).instalar()

    assert "--origem" in erro.value.mensagem
    assert not (tmp_path / "claude").exists()
