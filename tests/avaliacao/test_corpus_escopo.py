"""O corpus anonimizado de escopo carrega, fecha em si e não guarda texto livre."""

import re
from collections import defaultdict

from graphow.avaliacao.anonimizacao_log import AUTORES, CATEGORICAS, CONTAGENS
from graphow.avaliacao.corpus_escopo import CorpusEscopo, carregar_corpus
from graphow.avaliacao.recorte_do_log import CAMPOS_DE_REFERENCIA
from graphow.core.events import TipoEvento
from graphow.core.models import GrafoEstado

# Tasks por Goal conferidas contra o banco real no dia da geração, pelo
# `decompoe` de todo o histórico do log, e não pelo corpus.
TASKS_POR_GOAL: dict[str, int] = {"goal-3e94e8": 100, "goal-7414f9": 14, "goal-a54cf5": 35}
ID_ANONIMO = re.compile(r"^[a-z]+-[0-9a-f]{6,}$")
AUTOR_ANONIMO = re.compile(r"^(humano-\d+|agente-\d+|sistema)$")
VALOR_CATEGORICO = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
CHAVES_PERMITIDAS: set[str] = (
    set(CATEGORICAS) | set(AUTORES) | set(CAMPOS_DE_REFERENCIA)
    | {f"n_{c}" for c in CONTAGENS} | {f"tem_{c}" for c in CONTAGENS}
)


def _tasks_do_goal(estado: GrafoEstado, goal: str) -> set[str]:
    """Tasks alcançáveis do Goal por `decompoe`, no estado final."""
    filhos: dict[str, list[str]] = defaultdict(list)
    for aresta in estado.arestas.values():
        if aresta.tipo.value == "decompoe":
            filhos[aresta.origem_id].append(aresta.destino_id)
    achados: set[str] = set()
    pilha = [goal]
    while pilha:
        for filho in filhos[pilha.pop()]:
            if filho not in achados:
                achados.add(filho)
                pilha.append(filho)
    return {i for i in achados if estado.nos[i].tipo.value == "Task"}


def test_corpus_carrega_e_o_replay_chega_ao_ultimo_evento() -> None:
    """O replay usa o redutor de produção e termina na versão do último evento."""
    corpus = carregar_corpus()

    assert len(corpus.eventos) > 1000
    assert corpus.estado.versao_log == corpus.eventos[-1].seq
    assert [e.seq for e in corpus.eventos] == sorted(e.seq for e in corpus.eventos)
    assert corpus.estado_ate(corpus.eventos[10].seq).versao_log == corpus.eventos[10].seq


def test_tasks_por_goal_batem_com_o_banco_original() -> None:
    """Os três Goals relevantes mantêm as Tasks que o banco real tinha."""
    estado = carregar_corpus().estado
    goals = {i for i, no in estado.nos.items() if no.tipo.value == "Goal"}

    assert {g: len(_tasks_do_goal(estado, g)) for g in goals} == TASKS_POR_GOAL


def test_nenhuma_aresta_tem_ponta_ausente() -> None:
    """No estado e no log: toda aresta tem as duas pontas, e nenhuma aponta para fora do recorte."""
    corpus: CorpusEscopo = carregar_corpus()
    for aresta in corpus.estado.arestas.values():
        assert aresta.origem_id in corpus.estado.nos and aresta.destino_id in corpus.estado.nos
    nos = _ids_criados(corpus)
    for evento in corpus.eventos:
        if evento.tipo_evento is TipoEvento.ARESTA_CRIADA:
            assert evento.payload["origem_id"] in nos and evento.payload["destino_id"] in nos


def _ids_criados(corpus: CorpusEscopo) -> set[str]:
    """Ids de nó que o log do corpus cria, por `no_criado` ou por evento de execução."""
    return {
        str(e.payload["id"])
        for e in corpus.eventos
        if e.tipo_evento is TipoEvento.NO_CRIADO or e.tipo_evento.value.startswith("execucao_")
    }


def test_corpus_nao_guarda_texto_livre() -> None:
    """Só ids anonimizados, rótulos de autor e valores de lista branca; nenhum rótulo."""
    corpus = carregar_corpus()
    for evento in corpus.eventos:
        assert AUTOR_ANONIMO.match(evento.autor)
        assert "rotulo" not in evento.payload
        for chave, valor in evento.payload.get("propriedades", {}).items():
            assert chave in CHAVES_PERMITIDAS, chave
            _confere_valor(chave, valor)
    for no in corpus.estado.nos.values():
        assert ID_ANONIMO.match(no.id)
        assert no.rotulo in ("", f"Run {no.id}")


def _confere_valor(chave: str, valor: object) -> None:
    """Valor permitido por chave: número, booleano, id, autor ou identificador curto."""
    if valor is None or isinstance(valor, (bool, int)):
        return
    assert isinstance(valor, str), (chave, valor)
    if chave in CAMPOS_DE_REFERENCIA:
        assert ID_ANONIMO.match(valor)
    elif chave in AUTORES:
        assert AUTOR_ANONIMO.match(valor)
    else:
        assert VALOR_CATEGORICO.match(valor), (chave, valor)
