"""Testes da instalação do ambiente: as skills do humano, a conferência e a limpeza das cópias obsoletas."""

from pathlib import Path

import pytest

from graphow.documentacao.instalacao_ambiente import (
    AGENTES_OBSOLETOS,
    InstaladorDoAmbiente,
    RepositorioSemAmbiente,
)

RAIZ_DO_REPOSITORIO: Path = Path(__file__).resolve().parents[2]


def _copias_antigas(diretorio_claude: Path) -> None:
    """O que a versão 0.4 instalava e saiu: a skill de orquestração e os sete subagentes, e algo do usuário ao lado."""
    skill = diretorio_claude / "skills" / "graphow-orquestracao" / "references"
    skill.mkdir(parents=True)
    (skill.parent / "SKILL.md").write_text("antiga\n", encoding="utf-8")
    (skill / "despacho.md").write_text("antiga\n", encoding="utf-8")
    agentes = diretorio_claude / "agents"
    agentes.mkdir(parents=True)
    for nome in AGENTES_OBSOLETOS:
        (agentes / nome).write_text("antigo\n", encoding="utf-8")
    (agentes / "meu-agente.md").write_text("do usuario\n", encoding="utf-8")
    (diretorio_claude / "skills" / "minha-skill").mkdir()


def test_instalacao_copia_so_as_skills_da_sessao_do_humano_nominal(tmp_path: Path) -> None:
    """A graphow-mcp e a graphow-gerente; nenhum subagente nem a skill de orquestração."""
    resultado = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path).instalar()

    assert dict(resultado.arquivos_por_skill).keys() == {"graphow-mcp", "graphow-gerente"}
    assert (tmp_path / "skills" / "graphow-gerente" / "SKILL.md").is_file()
    assert not (tmp_path / "skills" / "graphow-orquestracao").exists()
    assert not (tmp_path / "agents").exists()
    assert resultado.removidos == ()


def test_instalacao_remove_as_copias_obsoletas_e_so_elas_nominal(tmp_path: Path) -> None:
    """A skill de orquestração e os sete subagentes saem; o agente e a skill do usuário ficam."""
    _copias_antigas(tmp_path)

    resultado = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path).instalar()

    assert len(resultado.removidos) == 1 + len(AGENTES_OBSOLETOS)
    assert not (tmp_path / "skills" / "graphow-orquestracao").exists()
    assert [arquivo.name for arquivo in (tmp_path / "agents").iterdir()] == ["meu-agente.md"]
    assert (tmp_path / "skills" / "minha-skill").is_dir()


def test_conferencia_acusa_o_que_falta_o_que_mudou_e_o_obsoleto_nominal(tmp_path: Path) -> None:
    """Antes da instalação falta tudo e sobra o obsoleto; depois, só o arquivo mexido à mão aparece."""
    _copias_antigas(tmp_path)
    instalador = InstaladorDoAmbiente(RAIZ_DO_REPOSITORIO, tmp_path)
    assert tmp_path / "agents" / "graphow-condutor.md" in instalador.desatualizados()

    instalador.instalar()
    assert instalador.desatualizados() == ()
    skill = tmp_path / "skills" / "graphow-mcp" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "editado\n", encoding="utf-8")

    assert instalador.desatualizados() == (skill,)


def test_origem_fora_de_um_checkout_e_recusada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: pacote instalado sem checkout; a recusa diz onde procurou e nada é gravado."""
    with pytest.raises(RepositorioSemAmbiente) as erro:
        InstaladorDoAmbiente(tmp_path / "nada", tmp_path / "claude").instalar()

    assert "--origem" in erro.value.mensagem
    assert not (tmp_path / "claude").exists()
