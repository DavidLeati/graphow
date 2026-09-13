"""Testes unitários para a leitura do código-fonte do repositório."""

from pathlib import Path

import pytest

from graphow.core.exceptions import GraphowError
from graphow.documentacao.leitura_fonte import ArquivoFonte, LeitorCodigoFonteEmDisco


def _montar_arvore_de_exemplo(raiz: Path) -> None:
    """Cria uma árvore mínima com dois pacotes e um diretório sem __init__."""
    pacote = raiz / "kernel"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text('"""Pacote kernel."""\n', encoding="utf-8")
    (pacote / "portao.py").write_text('"""Um portao."""\n', encoding="utf-8")

    outro = raiz / "core"
    outro.mkdir()
    (outro / "__init__.py").write_text('"""Pacote core."""\n', encoding="utf-8")

    sem_init = raiz / "__pycache__"
    sem_init.mkdir()
    (sem_init / "lixo.py").write_text("x = 1\n", encoding="utf-8")


def test_lista_apenas_diretorios_que_sao_pacotes_nominal(tmp_path: Path) -> None:
    """Um diretório sem __init__.py não é pacote e fica de fora."""
    _montar_arvore_de_exemplo(tmp_path)
    assert LeitorCodigoFonteEmDisco(tmp_path).listar_pacotes() == ("core", "kernel")


def test_le_modulos_em_ordem_estavel_nominal(tmp_path: Path) -> None:
    """A ordem de leitura é determinística, para a saída não oscilar."""
    _montar_arvore_de_exemplo(tmp_path)
    modulos = LeitorCodigoFonteEmDisco(tmp_path).ler_modulos("kernel")
    assert [modulo.caminho_relativo for modulo in modulos] == ["kernel/__init__.py", "kernel/portao.py"]


def test_nome_de_modulo_deriva_do_caminho_nominal() -> None:
    """O caminho no disco vira o caminho de importação."""
    arquivo = ArquivoFonte(caminho_relativo="kernel/portao.py", conteudo="")
    assert arquivo.nome_modulo == "graphow.kernel.portao"


def test_init_colapsa_para_o_nome_do_pacote_edge_case() -> None:
    """Caso de borda: __init__.py representa o pacote, não um módulo homônimo."""
    arquivo = ArquivoFonte(caminho_relativo="kernel/__init__.py", conteudo="")
    assert arquivo.nome_modulo == "graphow.kernel"


def test_pacote_inexistente_devolve_nada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: pedir um pacote que não existe não levanta erro."""
    _montar_arvore_de_exemplo(tmp_path)
    assert LeitorCodigoFonteEmDisco(tmp_path).ler_modulos("inexistente") == ()


def test_raiz_inexistente_falha_apontando_o_caminho_edge_case(tmp_path: Path) -> None:
    """Caso de borda: raiz ausente vira erro de domínio com contexto."""
    inexistente = tmp_path / "nao_existe"
    with pytest.raises(GraphowError) as capturado:
        LeitorCodigoFonteEmDisco(inexistente).listar_pacotes()
    assert str(inexistente) in capturado.value.contexto["caminho"]


def test_total_de_linhas_reflete_o_conteudo_edge_case() -> None:
    """Caso de borda: a contagem de linhas alimenta o inventário dos dossiês."""
    arquivo = ArquivoFonte(caminho_relativo="x.py", conteudo="a\nb\nc\n")
    assert arquivo.total_linhas == 3
