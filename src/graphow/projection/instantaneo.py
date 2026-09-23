"""Reconstrução de um ramo a partir do último instantâneo guardado, conferido contra o log.

O instantâneo só é usado quando três coisas conferem: o evento na posição do
corte é o mesmo que estava lá quando ele foi gravado (o log não foi reescrito
até ali), a impressão digital do código de projeção é a de agora (o estado foi
dobrado pelas mesmas regras), e o texto se lê de volta. Qualquer divergência cai
no replay completo, que é sempre a resposta certa, só mais lenta.

A impressão digital é o hash do código-fonte dos módulos que decidem o que um
evento vira no estado. Um número de versão escrito à mão dependeria de alguém
lembrar de incrementá-lo a cada mudança no acumulador; esquecer serviria, calado,
um estado que o replay não produziria.
"""

from collections.abc import Sequence
from functools import cache
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from graphow.core.events import EventoLog
from graphow.core.models import ArestaGrafo, GrafoEstado, MetadadosTemporais, NoGrafo, OrdemNoLog, ProvenienciaNo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.reducer import GrafoReducer
from graphow.storage.instantaneos import InstantaneoGravado, RepositorioInstantaneos
from graphow.storage.interfaces import RepositorioEventos

# Abaixo disso o replay do que falta é barato e gravar de novo não compensa.
EVENTOS_ATE_NOVO_INSTANTANEO: int = 1000

MODULOS_QUE_DEFINEM_A_PROJECAO: tuple[str, ...] = (
    "graphow.core.events",
    "graphow.core.models",
    "graphow.core.types",
    "graphow.projection.acumulador",
    "graphow.projection.reducer",
    "graphow.projection.instantaneo",
    "graphow.storage.sqlite_store",
)


@cache
def impressao_da_projecao() -> str:
    """Hash do código que transforma eventos em estado, lido uma vez por processo."""
    resumo = hashlib.sha256()
    for nome in MODULOS_QUE_DEFINEM_A_PROJECAO:
        especificacao = importlib.util.find_spec(nome)
        origem = especificacao.origin if especificacao is not None else None
        resumo.update(nome.encode())
        resumo.update(Path(origem).read_bytes() if origem else b"")
    return resumo.hexdigest()


def serializar_estado(estado: GrafoEstado) -> str:
    """Estado completo em JSON, na ordem de inserção: a desserialização devolve um estado igual."""
    return json.dumps(
        {
            "versao_log": estado.versao_log,
            "nos": [_no_em_lista(no) for no in estado.nos.values()],
            "arestas": [_aresta_em_lista(aresta) for aresta in estado.arestas.values()],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def desserializar_estado(texto: str) -> GrafoEstado:
    """Refaz o estado gravado por `serializar_estado`."""
    dados = json.loads(texto)
    nos = (_no_de_lista(linha) for linha in dados["nos"])
    arestas = (_aresta_de_lista(linha) for linha in dados["arestas"])
    return GrafoEstado(
        nos={no.id: no for no in nos},
        arestas={aresta.id: aresta for aresta in arestas},
        versao_log=int(dados["versao_log"]),
    )


class ReconstrucaoComInstantaneo:
    """Reconstrói um ramo partindo do instantâneo válido e grava outro quando o delta cresce."""

    def __init__(self, eventos: RepositorioEventos, instantaneos: RepositorioInstantaneos) -> None:
        self._eventos: RepositorioEventos = eventos
        self._instantaneos: RepositorioInstantaneos = instantaneos

    def reconstruir(self, ramo_id: str) -> tuple[GrafoEstado, int]:
        """O estado do ramo e o último seq aplicado, pelo caminho mais curto que confere."""
        base, delta = self._partir_do_instantaneo(ramo_id)
        if base is None:
            base, delta = GrafoEstado(), self._eventos.ler_eventos(ramo_id)
        estado = GrafoReducer.aplicar_eventos(base, delta)
        if len(delta) >= EVENTOS_ATE_NOVO_INSTANTANEO:
            self._gravar(ramo_id, estado, delta[-1])
        return estado, (delta[-1].seq if delta else base.versao_log)

    def _partir_do_instantaneo(self, ramo_id: str) -> tuple[GrafoEstado | None, Sequence[EventoLog]]:
        """Estado guardado e eventos posteriores a ele, ou (None, ()) se o instantâneo não confere."""
        gravado = self._instantaneos.obter(ramo_id)
        if gravado is None or gravado.impressao != impressao_da_projecao():
            return None, ()
        desde_o_corte = self._eventos.ler_eventos_desde_seq(ramo_id, gravado.seq - 1)
        if not desde_o_corte or (desde_o_corte[0].seq, desde_o_corte[0].id) != (gravado.seq, gravado.evento_id):
            return None, ()
        try:
            return desserializar_estado(gravado.estado), desde_o_corte[1:]
        except (ValueError, KeyError, TypeError, IndexError):
            return None, ()

    def _gravar(self, ramo_id: str, estado: GrafoEstado, ultimo: EventoLog) -> None:
        """Guarda o estado recém-dobrado como ponto de partida da próxima abertura."""
        self._instantaneos.gravar(
            InstantaneoGravado(ramo_id, ultimo.seq, ultimo.id, impressao_da_projecao(), serializar_estado(estado))
        )


def _no_em_lista(no: NoGrafo) -> list[Any]:
    """Um nó em lista posicional: menor que um objeto com chaves, e o estado tem milhares."""
    proveniencia, ordem = no.proveniencia, no.ordem
    return [
        no.id, no.tipo.value, no.rotulo, dict(no.propriedades),
        no.metadados.criado_em, no.metadados.atualizado_em,
        proveniencia.autor, proveniencia.papel, proveniencia.origem, proveniencia.atualizado_por,
        ordem.seq_criacao, ordem.seq_atualizacao,
    ]  # fmt: skip


def _no_de_lista(linha: list[Any]) -> NoGrafo:
    """Inverso de `_no_em_lista`."""
    return NoGrafo(
        id=linha[0],
        tipo=TipoNo(linha[1]),
        rotulo=linha[2],
        propriedades=linha[3],
        metadados=MetadadosTemporais(criado_em=linha[4], atualizado_em=linha[5]),
        proveniencia=ProvenienciaNo(autor=linha[6], papel=linha[7], origem=linha[8], atualizado_por=linha[9]),
        ordem=OrdemNoLog(seq_criacao=linha[10], seq_atualizacao=linha[11]),
    )


def _aresta_em_lista(aresta: ArestaGrafo) -> list[Any]:
    """Uma aresta em lista posicional."""
    metadados = aresta.metadados
    return [aresta.id, aresta.origem_id, aresta.destino_id, aresta.tipo.value, metadados.criado_em, metadados.atualizado_em]


def _aresta_de_lista(linha: list[Any]) -> ArestaGrafo:
    """Inverso de `_aresta_em_lista`."""
    return ArestaGrafo(
        id=linha[0],
        origem_id=linha[1],
        destino_id=linha[2],
        tipo=TipoAresta(linha[3]),
        metadados=MetadadosTemporais(criado_em=linha[4], atualizado_em=linha[5]),
    )
