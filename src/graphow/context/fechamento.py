"""Seção de fechamento: como uma sessão encerrada se apresenta a quem a retoma.

`ler_vista` numa Sessão encerrada devolvia o panorama dos filhos, que conta
tarefas e corta o resto: na maior sessão do banco real, 33 Evidence e 17 Note
ficavam de fora com "use buscar". Quem retoma não quer contar; quer saber o que
ficou decidido, o que ficou aberto e onde o trabalho parou. A seção abre a vista
com isso, tirado do fechamento determinístico do rollup, e com a condensação em
prosa quando um agente já a escreveu pelo PatchBoard.
"""

from collections.abc import Sequence

from graphow.context.secoes import (
    MARCA_DE_CONTEUDO_NAO_CONFIAVEL,
    GrupoDeLinhas,
    PrioridadeRetencao,
    SecaoContexto,
    anotar_ordem,
    anotar_proveniencia,
)
from graphow.core.models import NoGrafo
from graphow.core.types import StatusSessao, TipoAresta, TipoNo
from graphow.projection.fechamento import FechamentoDeSubarvore
from graphow.projection.graph_view import GrafoView

TITULO_FECHAMENTO: str = "Fechamento da Sessao (encerrada: leia isto antes de descer)"
ORDEM_DE_EXIBICAO_DO_FECHAMENTO: int = 0

# A Note de condensação se declara por esta ação e aponta em `id_alvo` para a
# sessão que condensa, como as notas reativas apontam para o nó que as motivou.
ACAO_DE_CONDENSACAO: str = "condensacao_de_sessao"
CAMPO_ACAO: str = "acao"
CAMPO_ALVO: str = "id_alvo"
CAMPO_CORPO: str = "corpo"
CAMPO_RESUMO: str = "resumo"


def esta_encerrada(no: NoGrafo) -> bool:
    """Uma Sessão encerrada foi fechada pelo humano, pelo harness ou pela interface."""
    if no.tipo != TipoNo.SESSAO:
        return False
    status = str(no.obter_propriedade("status", StatusSessao.ATIVA.value))
    return status == StatusSessao.CONCLUIDA.value


def localizar_condensacao(id_sessao: str, view: GrafoView) -> NoGrafo | None:
    """A Note de condensação mais recente produzida pela sessão, se um agente a escreveu."""
    produzidos = (
        view.obter_no(aresta.destino_id)
        for aresta in view.obter_arestas_saida(id_sessao, TipoAresta.PRODUZ)
    )
    candidatas = [no for no in produzidos if no is not None and _eh_condensacao_de(no, id_sessao)]
    if not candidatas:
        return None
    return max(candidatas, key=lambda no: (no.ordem.seq_criacao, no.id))


def _eh_condensacao_de(no: NoGrafo, id_sessao: str) -> bool:
    """Reconhece a Note que se declara condensação desta sessão."""
    if no.tipo != TipoNo.NOTE:
        return False
    return no.obter_propriedade(CAMPO_ACAO) == ACAO_DE_CONDENSACAO and no.obter_propriedade(CAMPO_ALVO) == id_sessao


def montar_secao_de_fechamento(sessao: NoGrafo, view: GrafoView) -> SecaoContexto:
    """Abre a vista da sessão encerrada com o que ela deixou em vigor."""
    resumo = view.obter_resumo(sessao.id)
    fechamento = resumo.fechamento if resumo is not None else FechamentoDeSubarvore()
    candidatos = (
        _grupo_de_abertura(sessao, fechamento),
        _grupo_de_condensacao(sessao, view),
        _grupo_de_nos("decisao vigente", fechamento.decisoes_vigentes, view),
        _grupo_de_nos("duvida aberta", fechamento.questoes_abertas, view),
        _grupo_de_nos("restricao", fechamento.restricoes, view),
        _grupo_de_nos("ultimo artefato", _como_tupla(fechamento.ultimo_artefato), view),
    )
    grupos = tuple(grupo for grupo in candidatos if grupo.linhas)
    return SecaoContexto(
        titulo=TITULO_FECHAMENTO,
        linhas=tuple(linha for grupo in grupos for linha in grupo.linhas),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DO_FECHAMENTO,
        prioridade_retencao=PrioridadeRetencao.MEMORIA,
        ids_incluidos=tuple(id_no for grupo in grupos for id_no in grupo.ids),
        grupos=grupos,
    )


def _como_tupla(id_no: str) -> tuple[str, ...]:
    """Um identificador vazio vira tupla vazia, não um item em branco."""
    return (id_no,) if id_no else ()


def _grupo_de_abertura(sessao: NoGrafo, fechamento: FechamentoDeSubarvore) -> GrupoDeLinhas:
    """Uma linha só, para nunca ser cortada ao meio: os números e o resumo declarado."""
    substituidas = (
        f" ({fechamento.decisoes_substituidas} substituidas)" if fechamento.decisoes_substituidas else ""
    )
    partes = [
        f"{len(fechamento.decisoes_vigentes)} decisoes vigentes{substituidas}",
        f"{len(fechamento.questoes_abertas)} duvidas abertas",
        f"{len(fechamento.restricoes)} restricoes",
    ]
    resumo = str(sessao.obter_propriedade(CAMPO_RESUMO, "")).strip()
    if resumo:
        partes.append(f"resumo declarado: {resumo}")
    return GrupoDeLinhas(rotulo="balanco", linhas=("- " + " | ".join(partes),))


def _grupo_de_condensacao(sessao: NoGrafo, view: GrafoView) -> GrupoDeLinhas:
    """A prosa escrita por um agente, marcada como não confiável quando é dele."""
    nota = localizar_condensacao(sessao.id, view)
    if nota is None:
        return GrupoDeLinhas(rotulo="condensacao", linhas=())
    corpo = str(nota.obter_propriedade(CAMPO_CORPO, "")).strip() or nota.rotulo
    marca = f" {MARCA_DE_CONTEUDO_NAO_CONFIAVEL}" if nota.proveniencia.eh_de_agente else ""
    texto = corpo.replace("\n", "\n  ")
    linha = f"- condensacao [{nota.id}]{anotar_ordem(nota)}{anotar_proveniencia(nota)}{marca}:\n  {texto}"
    return GrupoDeLinhas(rotulo="condensacao", linhas=(linha,), ids=(nota.id,))


def _grupo_de_nos(rotulo: str, ids: Sequence[str], view: GrafoView) -> GrupoDeLinhas:
    """Uma linha por nó do fechamento, com a proveniência de cada um."""
    nos = tuple(no for no in (view.obter_no(id_no) for id_no in ids) if no is not None)
    return GrupoDeLinhas(
        rotulo=rotulo,
        linhas=tuple(
            f"- {rotulo}: [{no.id}] {no.rotulo}{anotar_ordem(no)}{anotar_proveniencia(no)}" for no in nos
        ),
        ids=tuple(no.id for no in nos),
    )
