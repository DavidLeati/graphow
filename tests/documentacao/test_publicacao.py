"""Testes para a montagem do catálogo e a publicação dos documentos gerados."""

import pytest

from graphow.core.exceptions import GraphowError
from graphow.documentacao.leitura_fonte import ArquivoFonte, LeitorCodigoFonteEmMemoria
from graphow.documentacao.publicacao import (
    EscritorDocumentacaoEmMemoria,
    GeradorDocumentacao,
    NOME_ARQUIVO_INDICE,
)
from graphow.documentacao.setores import DEFINICOES_DE_SETOR, MontadorCatalogo

MODULO_MINIMO: str = '"""Resumo do modulo."""\n\n\nclass Coisa:\n    """Uma coisa."""\n'


def _modulos_de_todas_as_alas() -> dict[str, tuple[ArquivoFonte, ...]]:
    """Um módulo mínimo para cada ala declarada, como o disco entregaria."""
    return {
        definicao.pacote: (
            ArquivoFonte(caminho_relativo=f"{definicao.pacote}/modulo.py", conteudo=MODULO_MINIMO),
        )
        for definicao in DEFINICOES_DE_SETOR
    }


def _leitor_completo() -> LeitorCodigoFonteEmMemoria:
    """Leitor que oferece um módulo mínimo para cada ala declarada."""
    return LeitorCodigoFonteEmMemoria(_modulos_de_todas_as_alas())


def test_catalogo_cobre_todas_as_alas_declaradas_nominal() -> None:
    """O catálogo montado tem um setor por ala, na ordem declarada."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    assert len(catalogo.setores) == len(DEFINICOES_DE_SETOR)
    assert [setor.numero for setor in catalogo.setores] == list(range(1, len(DEFINICOES_DE_SETOR) + 1))
    assert catalogo.total_classes == len(DEFINICOES_DE_SETOR)


def test_pacote_sem_ala_declarada_e_recusado_edge_case() -> None:
    """Caso de borda: um pacote novo sem ala correspondente quebra a geração."""
    modulos = _modulos_de_todas_as_alas()
    modulos["pacote_novo"] = (ArquivoFonte(caminho_relativo="pacote_novo/x.py", conteudo=MODULO_MINIMO),)
    with pytest.raises(GraphowError) as capturado:
        MontadorCatalogo(LeitorCodigoFonteEmMemoria(modulos)).montar()
    assert "pacote_novo" in capturado.value.contexto["sem_ala"]


def test_ala_sem_pacote_correspondente_e_recusada_edge_case() -> None:
    """Caso de borda: uma ala declarada sem pacote no disco também quebra."""
    modulos = _modulos_de_todas_as_alas()
    del modulos["core"]
    with pytest.raises(GraphowError) as capturado:
        MontadorCatalogo(LeitorCodigoFonteEmMemoria(modulos)).montar()
    assert "core" in capturado.value.contexto["sem_pacote"]


def test_publicacao_gera_indice_e_um_dossie_por_ala_nominal() -> None:
    """A publicação produz o índice e um dossiê para cada ala."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    escritor = EscritorDocumentacaoEmMemoria()
    resultado = GeradorDocumentacao(escritor).publicar(catalogo)

    assert resultado.documentos_escritos == len(DEFINICOES_DE_SETOR) + 1
    assert NOME_ARQUIVO_INDICE in escritor.documentos
    assert "setores/01_core.md" in escritor.documentos


def test_dossie_de_ala_extinta_e_removido_edge_case() -> None:
    """Caso de borda: o dossiê de uma ala que já não existe é apagado."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    escritor = EscritorDocumentacaoEmMemoria(dossies_existentes=("setores/99_ala_extinta.md",))
    resultado = GeradorDocumentacao(escritor).publicar(catalogo)

    assert resultado.documentos_removidos == ("setores/99_ala_extinta.md",)
    assert escritor.removidos == ["setores/99_ala_extinta.md"]


def test_montagem_de_documentos_nao_escreve_nada_edge_case() -> None:
    """Caso de borda: a consulta que renderiza não pode gravar em lugar algum."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    escritor = EscritorDocumentacaoEmMemoria()
    documentos = GeradorDocumentacao(escritor).montar_documentos(catalogo)

    assert len(documentos) == len(DEFINICOES_DE_SETOR) + 1
    assert escritor.documentos == {}


def test_geracao_e_deterministica() -> None:
    """Duas execuções sobre o mesmo código produzem bytes idênticos."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    gerador = GeradorDocumentacao(EscritorDocumentacaoEmMemoria())

    primeira = gerador.montar_documentos(catalogo)
    segunda = gerador.montar_documentos(catalogo)
    assert [documento.conteudo for documento in primeira] == [
        documento.conteudo for documento in segunda
    ]


def test_indice_referencia_cada_dossie_gerado() -> None:
    """Todo dossiê publicado precisa estar linkado a partir do índice."""
    catalogo = MontadorCatalogo(_leitor_completo()).montar()
    documentos = GeradorDocumentacao(EscritorDocumentacaoEmMemoria()).montar_documentos(catalogo)
    indice = documentos[0].conteudo

    ausentes = [
        documento.caminho_relativo
        for documento in documentos[1:]
        if documento.caminho_relativo not in indice
    ]
    assert not ausentes, ausentes
