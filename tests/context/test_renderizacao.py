"""Testes unitários para a renderização de contexto sob orçamento de tokens."""

import pytest

from graphow.context.renderizacao import AVISO_DE_TRUNCAGEM, RenderizadorContexto
from graphow.context.secoes import PrioridadeRetencao, RecorteContexto, SecaoContexto
from graphow.core.exceptions import ErroOrcamentoExcedido
from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo

ORCAMENTO_FOLGADO: int = 5000


def _alvo() -> NoGrafo:
    """Nó alvo com propriedades de domínio e de layout misturadas."""
    return NoGrafo(
        id="task-1",
        tipo=TipoNo.TASK,
        rotulo="Implementar parser",
        propriedades={"status": "pendente", "pos_x": 100, "pos_y": 260},
    )


def _secao(titulo: str, quantidade_de_linhas: int, prioridade: PrioridadeRetencao, ordem: int) -> SecaoContexto:
    """Monta uma seção sintética com o volume de linhas pedido."""
    linhas = tuple(f"- [{titulo}-{indice}] linha de conteudo razoavelmente longa" for indice in range(quantidade_de_linhas))
    return SecaoContexto(
        titulo=titulo,
        linhas=linhas,
        ordem_exibicao=ordem,
        prioridade_retencao=prioridade,
        ids_incluidos=tuple(f"{titulo}-{indice}" for indice in range(quantidade_de_linhas)),
    )


def _recorte_completo() -> RecorteContexto:
    """Recorte com restrições, apoio volumoso e vizinhos expansíveis."""
    return RecorteContexto(
        alvo=_alvo(),
        secoes=(
            _secao("Restricoes Inviolaveis", 2, PrioridadeRetencao.RESTRICOES, 1),
            _secao("Evidencias Relacionadas", 40, PrioridadeRetencao.APOIO, 4),
            _secao("Vizinhos a 1 Salto", 3, PrioridadeRetencao.NAVEGACAO, 9),
        ),
    )


def test_renderiza_todas_as_secoes_quando_cabe_nominal() -> None:
    """Com orçamento folgado, nada é descartado nem truncado."""
    texto = RenderizadorContexto().renderizar(_recorte_completo(), ORCAMENTO_FOLGADO)
    assert AVISO_DE_TRUNCAGEM not in texto.conteudo
    assert len(texto.secoes_incluidas) == 3


def test_cada_cabecalho_aparece_uma_unica_vez_nominal() -> None:
    """O título da seção é emitido uma vez, não uma vez por item."""
    texto = RenderizadorContexto().renderizar(_recorte_completo(), ORCAMENTO_FOLGADO)
    assert texto.conteudo.count("## Evidencias Relacionadas") == 1


def test_propriedades_de_layout_nao_entram_no_contexto_nominal() -> None:
    """Coordenadas do canvas não gastam orçamento do agente."""
    texto = RenderizadorContexto().renderizar(_recorte_completo(), ORCAMENTO_FOLGADO)
    assert "pos_x" not in texto.conteudo
    assert "status" in texto.conteudo


def test_sob_pressao_descarta_apoio_antes_da_navegacao_edge_case() -> None:
    """Caso de borda: a seção de vizinhos sobrevive ao corte, o apoio não."""
    texto = RenderizadorContexto().renderizar(_recorte_completo(), 140)
    assert "Vizinhos a 1 Salto" in texto.secoes_incluidas
    assert "Evidencias Relacionadas" not in texto.secoes_incluidas
    assert AVISO_DE_TRUNCAGEM in texto.conteudo


def test_restricoes_sao_as_ultimas_a_cair_edge_case() -> None:
    """Caso de borda: sob orcamento extremo, o que sobra sao as regras invioláveis.

    A ordem de descarte e deliberada: vizinhos podem ser reencontrados por busca,
    uma Constraint ignorada vira trabalho invalido.
    """
    texto = RenderizadorContexto().renderizar(_recorte_completo(), 120)
    assert texto.secoes_incluidas == ("Restricoes Inviolaveis",)


def test_ids_publicados_refletem_apenas_o_que_sobreviveu_edge_case() -> None:
    """Caso de borda: o que foi cortado não pode continuar sendo anunciado."""
    texto = RenderizadorContexto().renderizar(_recorte_completo(), 140)
    assert not any(id_no.startswith("Evidencias") for id_no in texto.ids_incluidos)
    assert "Vizinhos a 1 Salto" in texto.ids_por_secao


def test_orcamento_impossivel_levanta_erro_edge_case() -> None:
    """Caso de borda: se nem o cabeçalho cabe, o erro é explícito."""
    with pytest.raises(ErroOrcamentoExcedido):
        RenderizadorContexto().renderizar(_recorte_completo(), 3)


def test_recorte_sem_secoes_renderiza_apenas_o_alvo_edge_case() -> None:
    """Caso de borda: um nó isolado produz uma vista mínima e válida."""
    texto = RenderizadorContexto().renderizar(RecorteContexto(alvo=_alvo(), secoes=()), 500)
    assert texto.secoes_incluidas == ()
    assert "task-1" in texto.conteudo
    assert texto.ids_incluidos == ("task-1",)
