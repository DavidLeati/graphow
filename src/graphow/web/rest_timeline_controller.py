"""Controlador REST especializado na Timeline de eventos bitemporais e Replay Temporal."""

from collections.abc import Sequence
from typing import Any

from graphow.core.events import EventoLog
from graphow.core.models import GrafoEstado
from graphow.projection.graph_view import GrafoView
from graphow.projection.reducer import GrafoReducer
from graphow.storage.interfaces import RepositorioEventos
from graphow.web.dto import DadosArestaVisual, DadosCanvasVisual, DadosNoVisual


class TimelineWebController:
    """Controlador para leitura cronológica do log e reconstrução de estado histórico."""

    def __init__(self, repositorio: RepositorioEventos) -> None:
        self._repositorio: RepositorioEventos = repositorio

    def obter_eventos(
        self,
        ramo_id: str = "main",
        autor: str | None = None,
        papel: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recupera lista cronológica de eventos com filtros opcionais por autor e papel."""
        eventos = self._repositorio.ler_eventos(ramo_id)
        resultado: list[dict[str, Any]] = []
        for e in eventos:
            if autor is not None and e.autor != autor:
                continue
            if papel is not None and e.papel.value != papel:
                continue
            resultado.append(self._formatar_evento(e))
        return resultado

    def _formatar_evento(self, e: EventoLog) -> dict[str, Any]:
        """Converte um EventoLog em representação de dicionário para serialização JSON."""
        return {
            "seq": e.seq,
            "id": e.id,
            "timestamp": e.timestamp_utc,
            "autor": e.autor,
            "papel": e.papel.value,
            "origem": e.origem.value,
            "tipo": e.tipo_evento.value,
            "ramo_id": e.ramo_id,
            "payload": dict(e.payload),
            "trace_id": e.trace_id,
            "versao_ontologia": e.versao_ontologia,
        }

    def obter_estado_na_versao(self, versao_alvo: int, ramo_id: str = "main") -> DadosCanvasVisual:
        """Reconstrói o estado do grafo exatamente como existia na versão de log informada."""
        eventos = self._repositorio.ler_eventos(ramo_id)
        eventos_filtrados: Sequence[EventoLog] = [e for e in eventos if e.seq <= versao_alvo]
        estado_historico: GrafoEstado = GrafoReducer.reconstruir(eventos_filtrados)
        view = GrafoView(estado_historico)
        nos_visuais = [
            DadosNoVisual(id=n.id, tipo=n.tipo.value, rotulo=n.rotulo, propriedades=dict(n.propriedades))
            for n in view._estado.nos.values()
        ]
        arestas_visuais = [
            DadosArestaVisual(id=a.id, origem_id=a.origem_id, destino_id=a.destino_id, tipo=a.tipo.value)
            for a in view._estado.arestas.values()
        ]
        return DadosCanvasVisual(
            ramo_id=ramo_id,
            versao_log=view.versao_log,
            total_nos=len(nos_visuais),
            total_arestas=len(arestas_visuais),
            nos=nos_visuais,
            arestas=arestas_visuais,
        )
