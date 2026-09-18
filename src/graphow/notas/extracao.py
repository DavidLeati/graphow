"""Extração das notas a partir da projeção: só o que o grafo diz, na ordem do log."""

from graphow.context.memoria import (
    CAMPO_COMO_APLICAR,
    CAMPO_VALIDO_ATE,
    alcances_de,
    aprendizados_promovidos,
    identificar_contradicoes,
    identificar_substituto,
    origens_de,
)
from graphow.core.models import NoGrafo
from graphow.notas.modelo import NotaDeAprendizado, OrigemDaNota
from graphow.projection.graph_view import GrafoView

# Instante vazio: nenhum `valido_ate` é anterior a ele, então nada expira. O
# acervo guarda também o aprendizado vencido, com a data de validade escrita:
# quem lê o diretório decide, e a vista do agente já o deixa de fora sozinha.
SEM_LIMITE_DE_VALIDADE: str = ""
TIPO_DE_NO_REMOVIDO: str = "removido"


def extrair_notas(view: GrafoView) -> tuple[NotaDeAprendizado, ...]:
    """Uma nota por aprendizado promovido, na ordem em que nasceram no log."""
    return tuple(montar_nota(no, view) for no in aprendizados_promovidos(view, SEM_LIMITE_DE_VALIDADE))


def montar_nota(no: NoGrafo, view: GrafoView) -> NotaDeAprendizado:
    """Lê do nó e das arestas tudo que a nota vai dizer.

    É pública porque o painel de memória do canvas descreve um Aprendizado do
    mesmo jeito que o acervo: a leitura é uma só, promovido ou não.
    """
    return NotaDeAprendizado(
        id=no.id,
        afirmacao=no.rotulo,
        como_aplicar=str(no.obter_propriedade(CAMPO_COMO_APLICAR, "")).strip(),
        autor=no.proveniencia.autor,
        papel=no.proveniencia.papel,
        seq_criacao=no.ordem.seq_criacao,
        alcances=alcances_de(no, view),
        origens=tuple(_descrever(id_origem, view) for id_origem in origens_de(no, view)),
        substituto=identificar_substituto(no.id, view),
        contradicoes=tuple(_descrever(id_no, view) for id_no in identificar_contradicoes(no.id, view)),
        valido_ate=str(no.obter_propriedade(CAMPO_VALIDO_ATE, "") or ""),
    )


def _descrever(id_no: str, view: GrafoView) -> OrigemDaNota:
    """Cita o nó pelo tipo, rótulo e posição; um nó removido é dito removido, não inventado."""
    no = view.obter_no(id_no)
    if no is None:
        return OrigemDaNota(id=id_no, tipo=TIPO_DE_NO_REMOVIDO, rotulo="(no removido do grafo)", seq=0)
    return OrigemDaNota(id=no.id, tipo=no.tipo.value, rotulo=no.rotulo, seq=no.ordem.seq_criacao)
