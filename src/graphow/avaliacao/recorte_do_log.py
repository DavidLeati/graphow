"""Recorte do log real que o corpus de escopo preserva: Goals com trabalho, suas Tasks e a vizinhança.

O corpus cobre só o que a análise de escopo lê. O recorte é calculado sobre a
história inteira do log, não sobre o estado final: nó removido depois continua
a ter existido, e a Task removida ainda conta no que o Goal chegou a ter.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
from typing import Any

MINIMO_DE_TASKS_POR_GOAL: int = 3
CAMPOS_DE_REFERENCIA: frozenset[str] = frozenset({"corrige", "id_alvo", "substitui"})
TIPO_GOAL: str = "Goal"
TIPO_TASK: str = "Task"
TIPO_SESSAO: str = "Sessao"
TIPO_RUN: str = "Run"
ARESTA_DECOMPOE: str = "decompoe"
ARESTA_CONTEM: str = "contem"
ARESTA_PRODUZ: str = "produz"


@dataclass(frozen=True)
class EventoBruto:
    """Evento do banco com o payload já decodificado, a única forma que o recorte lê."""

    id: str
    seq: int
    tipo_evento: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Historia:
    """Tudo que o log chegou a criar: tipo de cada nó, arestas e a sessão de cada Run."""

    tipos: dict[str, str]
    arestas: dict[str, tuple[str, str, str]]
    sessao_do_run: dict[str, str]
    referencias: dict[str, set[str]]


@dataclass(frozen=True)
class Recorte:
    """Nós e arestas que entram no corpus, e os Goals que o motivaram."""

    goals: frozenset[str]
    nos: dict[str, str]
    arestas: frozenset[str]


def id_do_run(evento: EventoBruto) -> str:
    """Identificador do Run de um evento de execução, igual ao que a projeção usa."""
    return str(evento.payload.get("id", f"run-{evento.id}"))


class _Levantamento:
    """Acumula, evento a evento, o que o log criou."""

    def __init__(self) -> None:
        self.tipos: dict[str, str] = {}
        self.arestas: dict[str, tuple[str, str, str]] = {}
        self.sessao_do_run: dict[str, str] = {}
        self.referencias: dict[str, set[str]] = defaultdict(set)

    def registrar(self, evento: EventoBruto) -> None:
        """Anota o nó, a aresta ou o Run que o evento cria."""
        if evento.tipo_evento == "no_criado":
            self.tipos[str(evento.payload["id"])] = str(evento.payload["tipo"])
        if evento.tipo_evento == "aresta_criada":
            self._registrar_aresta(evento.payload)
        if evento.tipo_evento.startswith("execucao_"):
            self._registrar_run(evento)
        self._registrar_referencias(evento)

    def _registrar_aresta(self, carga: dict[str, Any]) -> None:
        """Guarda origem, destino e tipo da aresta criada."""
        self.arestas[str(carga["id"])] = (str(carga["origem_id"]), str(carga["destino_id"]), str(carga["tipo"]))

    def _registrar_run(self, evento: EventoBruto) -> None:
        """O Run nasce no evento de execução, ligado à sessão que o evento cita."""
        id_run = id_do_run(evento)
        self.tipos.setdefault(id_run, TIPO_RUN)
        if evento.payload.get("id_sessao"):
            self.sessao_do_run[id_run] = str(evento.payload["id_sessao"])

    def _registrar_referencias(self, evento: EventoBruto) -> None:
        """Guarda, por nó, os ids que ele cita em propriedades de referência."""
        if evento.tipo_evento not in ("no_criado", "no_atualizado"):
            return
        propriedades = evento.payload.get("propriedades") or {}
        citados = [propriedades[c] for c in CAMPOS_DE_REFERENCIA & propriedades.keys()]
        self.referencias[str(evento.payload["id"])].update(c for c in citados if isinstance(c, str))

    def historia(self) -> Historia:
        """Fecha o levantamento; Run ligado só por `produz` ganha a sessão que o produziu."""
        for origem, destino, tipo in self.arestas.values():
            if tipo == ARESTA_PRODUZ and self.tipos.get(destino) == TIPO_RUN:
                self.sessao_do_run.setdefault(destino, origem)
        return Historia(self.tipos, self.arestas, self.sessao_do_run, dict(self.referencias))


def levantar_historia(eventos: Iterable[EventoBruto]) -> Historia:
    """Varre o log uma vez e junta o que o recorte precisa saber."""
    levantamento = _Levantamento()
    for evento in eventos:
        levantamento.registrar(evento)
    return levantamento.historia()


def tasks_por_goal(historia: Historia) -> dict[str, set[str]]:
    """Tasks alcançáveis de cada Goal por `decompoe`, em qualquer momento da história."""
    filhos: dict[str, list[str]] = defaultdict(list)
    for origem, destino, tipo in historia.arestas.values():
        if tipo == ARESTA_DECOMPOE:
            filhos[origem].append(destino)
    return {
        id_no: _descendentes(id_no, filhos, historia.tipos)
        for id_no, tipo in historia.tipos.items()
        if tipo == TIPO_GOAL
    }


def _descendentes(raiz: str, filhos: dict[str, list[str]], tipos: dict[str, str]) -> set[str]:
    """Tasks abaixo da raiz, seguindo `decompoe` sem repetir nó."""
    vistos: set[str] = set()
    pilha = [raiz]
    while pilha:
        novos = [filho for filho in filhos.get(pilha.pop(), ()) if filho not in vistos]
        vistos.update(novos)
        pilha.extend(novos)
    return {id_no for id_no in vistos if tipos.get(id_no) == TIPO_TASK}


def calcular_recorte(historia: Historia) -> Recorte:
    """Goals relevantes, Tasks, vizinhos, referências citadas, ancestrais e Runs das sessões."""
    por_goal = tasks_por_goal(historia)
    goals = {g for g, tasks in por_goal.items() if len(tasks) >= MINIMO_DE_TASKS_POR_GOAL}
    nucleo = set(goals).union(*(por_goal[g] for g in goals)) if goals else set()
    ids = nucleo | _vizinhos(nucleo, historia)
    ids |= {r for i in ids for r in historia.referencias.get(i, ()) if r in historia.tipos}
    ids |= _ancestrais(ids, historia)
    ids |= _runs_das_sessoes(ids, historia)
    nos = {i: historia.tipos[i] for i in ids}
    arestas = frozenset(a for a, (o, d, _) in historia.arestas.items() if o in nos and d in nos)
    return Recorte(frozenset(goals), nos, arestas)


def _vizinhos(nucleo: set[str], historia: Historia) -> set[str]:
    """Nós ligados ao núcleo por qualquer aresta, em qualquer sentido."""
    achados: set[str] = set()
    for origem, destino, _ in historia.arestas.values():
        if origem in nucleo:
            achados.add(destino)
        if destino in nucleo:
            achados.add(origem)
    return {i for i in achados if i in historia.tipos}


def _ancestrais(ids: set[str], historia: Historia) -> set[str]:
    """Quem contém os nós do recorte, subindo por `contem` até a raiz."""
    pais: dict[str, list[str]] = defaultdict(list)
    for origem, destino, tipo in historia.arestas.values():
        if tipo == ARESTA_CONTEM and origem in historia.tipos:
            pais[destino].append(origem)
    achados: set[str] = set()
    pilha = list(ids)
    while pilha:
        novos = [pai for pai in pais.get(pilha.pop(), ()) if pai not in achados]
        achados.update(novos)
        pilha.extend(novos)
    return achados


def _runs_das_sessoes(ids: set[str], historia: Historia) -> set[str]:
    """Runs cuja sessão está no recorte: o custo da sessão faz parte do que ela produziu."""
    return {run for run, sessao in historia.sessao_do_run.items() if sessao in ids}


def eventos_brutos(linhas: Sequence[Any]) -> list[EventoBruto]:
    """Converte as linhas do banco em eventos com payload decodificado."""
    return [
        EventoBruto(str(linha["id"]), int(linha["seq"]), str(linha["tipo_evento"]), json.loads(linha["payload_json"]))
        for linha in linhas
    ]
