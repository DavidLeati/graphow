"""Testes do instalador da skill: a cópia que todo projeto vê, atualizada a cada execução."""

from pathlib import Path

import pytest

from graphow.documentacao.skill import NOME_DA_SKILL, InstaladorDeSkill, SkillNaoEncontrada


def _skill_de_teste(raiz: Path) -> Path:
    """Uma skill com o arquivo principal, uma referência e um cache que não deve viajar."""
    origem = raiz / "origem" / NOME_DA_SKILL
    (origem / "references").mkdir(parents=True)
    (origem / "__pycache__").mkdir()
    (origem / "SKILL.md").write_text("# skill v1\n", encoding="utf-8")
    (origem / "references" / "cookbook.md").write_text("# cookbook\n", encoding="utf-8")
    (origem / "__pycache__" / "lixo.pyc").write_bytes(b"\x00")
    return origem


def test_instalacao_copia_a_skill_inteira_sem_caches_nominal(tmp_path: Path) -> None:
    """SKILL.md e referências chegam ao destino com o mesmo caminho relativo; o cache fica."""
    origem = _skill_de_teste(tmp_path)
    destino = tmp_path / "skills"

    resultado = InstaladorDeSkill(origem, destino).instalar()

    assert resultado.destino == destino / NOME_DA_SKILL
    assert resultado.arquivos_copiados == ("SKILL.md", "references/cookbook.md")
    assert (destino / NOME_DA_SKILL / "SKILL.md").read_text(encoding="utf-8") == "# skill v1\n"
    assert not (destino / NOME_DA_SKILL / "__pycache__").exists()


def test_reinstalar_atualiza_a_copia_anterior_nominal(tmp_path: Path) -> None:
    """A cópia por projeto envelhecia; rodar de novo é o que a põe em dia."""
    origem = _skill_de_teste(tmp_path)
    destino = tmp_path / "skills"
    InstaladorDeSkill(origem, destino).instalar()
    (origem / "SKILL.md").write_text("# skill v2\n", encoding="utf-8")

    InstaladorDeSkill(origem, destino).instalar()

    assert (destino / NOME_DA_SKILL / "SKILL.md").read_text(encoding="utf-8") == "# skill v2\n"


def test_origem_sem_skill_e_recusada_com_o_caminho_edge_case(tmp_path: Path) -> None:
    """Caso de borda: pacote instalado fora de um checkout; a recusa diz onde procurou e o que fazer."""
    with pytest.raises(SkillNaoEncontrada) as erro:
        InstaladorDeSkill(tmp_path / "nada", tmp_path / "skills").instalar()

    assert "--origem" in erro.value.mensagem
    assert not (tmp_path / "skills").exists()
