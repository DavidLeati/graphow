"""Extensão do cenário gravado com a camada de memória: a sessão encerrada e condensada.

O corpus base mede o custo de entrar numa tarefa. Os braços novos medem o que
vem depois: retomar uma sessão encerrada e reaproveitar o que ela ensinou. A
extensão é aplicada sobre um kernel próprio, montado do zero a cada medição,
para que o braço original continue medindo exatamente o mesmo grafo de sempre.
"""

from graphow.avaliacao.tarefas_gravadas import (
    ID_SESSAO,
    TAREFAS_GRAVADAS,
    Ligacao,
    montar_cenario_gravado,
)
from graphow.context.fechamento import ACAO_DE_CONDENSACAO
from graphow.core.types import PapelAutor, StatusSessao, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel

ID_NOTA_DE_CONDENSACAO: str = "nota-condensacao-sess-avaliacao"
AUTOR_HUMANO: str = "david"
AUTOR_REVISOR: str = "agente-revisor"
RESUMO_DECLARADO: str = "Nove das dez tarefas do kernel fechadas; o ciclo de vida pelos hooks ficou aberto"

# A prosa que um revisor escreveria ao condensar a sessão: decisões com o
# motivo, achados, o que ficou aberto e o que não repetir. É texto gravado, para
# a medição ser comparável entre execuções.
CORPO_DA_CONDENSACAO: str = (
    "Decisoes vigentes: o item de patch e um dataclass frozen, porque o lote precisa ser "
    "imutavel entre a validacao e o commit; a tabela de pares vive no SchemaGate e nao no "
    "modelo, para o portao ser o unico lugar que responde que aresta liga o que; criar e "
    "remover sao poderes distintos por tipo de aresta; a posse de tarefa vive no "
    "InvariantGate porque e concorrencia; a vizinhanca encolhe por dentro antes de qualquer "
    "descarte. Achados que sustentam isso: 40 payloads maliciosos sem escape, sonda de 17 "
    "casos sem caminho de fuga, sessao de 60 tarefas com 60 vizinhos a 800 tokens. Ficou "
    "aberto: emitir o ciclo de vida de execucao pelos hooks. Nao fazer de novo: cortar a "
    "vista linha a linha pelo fim, que apagava a lista de vizinhos antes do apoio."
)


def montar_cenario_com_memoria() -> WriteKernel:
    """O cenário gravado, mais a sessão encerrada e a condensação escrita pelo revisor."""
    return estender_com_memoria(montar_cenario_gravado())


def estender_com_memoria(kernel: WriteKernel) -> WriteKernel:
    """Encerra a sessão do corpus e grava a condensação que um revisor escreveria."""
    _submeter(kernel, _proposta(PapelAutor.HUMANO, AUTOR_HUMANO, _operacoes_de_encerramento()))
    _submeter(kernel, _proposta(PapelAutor.REVISOR, AUTOR_REVISOR, _operacoes_de_condensacao()))
    return kernel


def ids_de_conhecimento_do_corpus() -> tuple[str, ...]:
    """As decisões e evidências que o corpus gravou, na ordem das tarefas."""
    ids: list[str] = []
    for tarefa in TAREFAS_GRAVADAS:
        ids.extend(f"dec-{tarefa.id}-{indice}" for indice in range(len(tarefa.decisoes)))
        ids.extend(f"ev-{tarefa.id}-{indice}" for indice in range(len(tarefa.evidencias)))
    return tuple(ids)


def _operacoes_de_encerramento() -> tuple[ItemPatch, ...]:
    """O humano encerra a sessão e declara o resumo, como faria pela interface."""
    return (
        ItemPatch(
            op=OperacaoPatch.REPLACE,
            path=f"/nos/{ID_SESSAO}/propriedades/status",
            value=StatusSessao.CONCLUIDA.value,
        ),
        ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{ID_SESSAO}/propriedades/resumo", value=RESUMO_DECLARADO),
    )


def _operacoes_de_condensacao() -> tuple[ItemPatch, ...]:
    """A Note de condensação, pendurada na sessão e derivada de cada nó que condensa."""
    nota = ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{ID_NOTA_DE_CONDENSACAO}",
        value={
            "id": ID_NOTA_DE_CONDENSACAO,
            "tipo": TipoNo.NOTE.value,
            "rotulo": "Condensacao da sprint de avaliacao",
            "propriedades": {"acao": ACAO_DE_CONDENSACAO, "id_alvo": ID_SESSAO, "corpo": CORPO_DA_CONDENSACAO},
        },
    )
    produz = _aresta(f"p-{ID_NOTA_DE_CONDENSACAO}", Ligacao(ID_SESSAO, ID_NOTA_DE_CONDENSACAO, TipoAresta.PRODUZ))
    derivacoes = tuple(
        _aresta(
            f"d-{ID_NOTA_DE_CONDENSACAO}-{id_origem}",
            Ligacao(ID_NOTA_DE_CONDENSACAO, id_origem, TipoAresta.DERIVA_DE),
        )
        for id_origem in ids_de_conhecimento_do_corpus()
    )
    return (nota, produz) + derivacoes


def _aresta(id_aresta: str, ligacao: Ligacao) -> ItemPatch:
    """Operação de criação de aresta tipada entre dois nós."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={
            "id": id_aresta,
            "origem_id": ligacao.origem,
            "destino_id": ligacao.destino,
            "tipo": ligacao.tipo.value,
        },
    )


def _proposta(papel: PapelAutor, autor: str, operacoes: tuple[ItemPatch, ...]) -> PropostaPatch:
    """Proposta sob a identidade informada, com a justificativa do cenário."""
    dados = DadosPropostaPatch(
        autor=autor,
        papel=papel,
        operacoes=operacoes,
        justificativa="Montagem da camada de memoria do cenario gravado",
    )
    return PropostaPatch.criar(dados)


def _submeter(kernel: WriteKernel, proposta: PropostaPatch) -> None:
    """Escreve no kernel, exigindo que os portões aceitem o cenário."""
    recibo = kernel.submeter_patch(proposta)
    if not recibo.sucesso:
        raise RuntimeError(f"Cenario de memoria recusado pelo kernel: {recibo.mensagem}")
