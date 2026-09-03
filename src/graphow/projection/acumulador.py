"""Acumulador mutável usado para dobrar muitos eventos em uma passada só.

A projeção pública continua imutável. O que muda é o caminho interno: copiar o
dicionário inteiro de nós a cada evento tornava o replay quadrático — 20 mil
eventos levavam 2,3 s, e cada tique do time-travel pagava esse custo. Ver F-09.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core.events import (
    CAMPO_PROPRIEDADES,
    CAMPO_PROPRIEDADES_REMOVIDAS,
    CAMPO_ROTULO,
    EventoLog,
    TipoEvento,
)
from graphow.core.models import (
    ArestaGrafo,
    GrafoEstado,
    MetadadosTemporais,
    NoGrafo,
    OrdemNoLog,
    ProvenienciaNo,
)
from graphow.core.types import TipoAresta, TipoNo


def metadados_do_evento(evento: EventoLog) -> MetadadosTemporais:
    """Marca temporal do nó tirada do log, nunca do relógio de quem projeta.

    Um nó datado no momento da projeção envelhece a cada replay: o mesmo log
    reconstruído amanhã diria que tudo nasceu amanhã.
    """
    return MetadadosTemporais(
        criado_em=evento.timestamp_utc,
        registrado_em=evento.timestamp_utc,
        valido_de=evento.timestamp_utc,
    )


def ordem_do_evento(evento: EventoLog) -> OrdemNoLog:
    """Posição de nascimento do nó na ordem total do log."""
    return OrdemNoLog(seq_criacao=evento.seq, seq_atualizacao=evento.seq)


class AcumuladorProjecao:
    """Estrutura interna e mutável que aplica eventos sem recriar o estado a cada um."""

    def __init__(self, estado_base: GrafoEstado) -> None:
        self._nos: dict[str, NoGrafo] = dict(estado_base.nos)
        self._arestas: dict[str, ArestaGrafo] = dict(estado_base.arestas)
        self._versao_log: int = estado_base.versao_log

    def aplicar_todos(self, eventos: Sequence[EventoLog]) -> None:
        """Dobra a sequência inteira de eventos sobre o acumulador."""
        for evento in eventos:
            self.aplicar(evento)

    def aplicar(self, evento: EventoLog) -> None:
        """Aplica um evento, delegando ao manipulador do seu tipo."""
        manipuladores = {
            TipoEvento.NO_CRIADO: self._criar_no,
            TipoEvento.NO_ATUALIZADO: self._atualizar_no,
            TipoEvento.NO_REMOVIDO: self._remover_no,
            TipoEvento.ARESTA_CRIADA: self._criar_aresta,
            TipoEvento.ARESTA_REMOVIDA: self._remover_aresta,
            TipoEvento.EXECUCAO_SOLICITADA: self._registrar_execucao,
            TipoEvento.EXECUCAO_INICIADA: self._registrar_execucao,
            TipoEvento.EXECUCAO_CONCLUIDA: self._registrar_execucao,
            TipoEvento.RAMO_CRIADO: self._apenas_avancar_versao,
        }
        manipulador = manipuladores.get(evento.tipo_evento)
        if manipulador is None:
            return
        manipulador(evento)
        self._versao_log = evento.seq

    def congelar(self) -> GrafoEstado:
        """Produz o estado imutável correspondente ao acumulado até aqui."""
        return GrafoEstado(nos=dict(self._nos), arestas=dict(self._arestas), versao_log=self._versao_log)

    def _criar_no(self, evento: EventoLog) -> None:
        """Insere o nó descrito no payload do evento."""
        payload: Mapping[str, Any] = evento.payload
        id_no = str(payload["id"])
        self._nos[id_no] = NoGrafo(
            id=id_no,
            tipo=TipoNo(payload["tipo"]),
            rotulo=str(payload.get("rotulo", "")),
            propriedades=dict(payload.get("propriedades", {})),
            metadados=metadados_do_evento(evento),
            proveniencia=ProvenienciaNo(
                autor=evento.autor, papel=evento.papel.value, origem=evento.origem.value
            ),
            ordem=ordem_do_evento(evento),
        )

    def _atualizar_no(self, evento: EventoLog) -> None:
        """Mescla rótulo e propriedades sobre um nó existente."""
        payload: Mapping[str, Any] = evento.payload
        id_no = str(payload["id"])
        existente = self._nos.get(id_no)
        if existente is None:
            return
        self._nos[id_no] = NoGrafo(
            id=existente.id,
            tipo=existente.tipo,
            rotulo=str(payload.get(CAMPO_ROTULO, existente.rotulo)),
            propriedades=self._mesclar_propriedades(existente.propriedades, payload),
            metadados=existente.metadados.com_atualizacao(evento.timestamp_utc),
            proveniencia=existente.proveniencia.com_atualizacao(evento.autor),
            ordem=existente.ordem.com_atualizacao(evento.seq),
        )

    def _mesclar_propriedades(
        self,
        atuais: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Aplica as propriedades escritas e retira as que o patch removeu.

        Um REMOVE sobre uma propriedade chegava aqui como {chave: None}, e a
        mescla gravava o nulo: a chave sobrevivia à própria remoção. Os portões
        aceitavam a operação, então ela falhava em silêncio.
        """
        mescladas = {**atuais, **payload.get(CAMPO_PROPRIEDADES, {})}
        for chave in payload.get(CAMPO_PROPRIEDADES_REMOVIDAS, ()):
            mescladas.pop(str(chave), None)
        return mescladas

    def _remover_no(self, evento: EventoLog) -> None:
        """Remove o nó e todas as arestas que nele incidem."""
        id_no = str(evento.payload["id"])
        self._nos.pop(id_no, None)
        incidentes = [
            id_aresta
            for id_aresta, aresta in self._arestas.items()
            if id_no in (aresta.origem_id, aresta.destino_id)
        ]
        for id_aresta in incidentes:
            del self._arestas[id_aresta]

    def _criar_aresta(self, evento: EventoLog) -> None:
        """Insere a aresta tipada descrita no payload."""
        payload: Mapping[str, Any] = evento.payload
        id_aresta = str(payload["id"])
        self._arestas[id_aresta] = ArestaGrafo(
            id=id_aresta,
            origem_id=str(payload["origem_id"]),
            destino_id=str(payload["destino_id"]),
            tipo=TipoAresta(payload["tipo"]),
            metadados=MetadadosTemporais(
                criado_em=evento.timestamp_utc, registrado_em=evento.timestamp_utc
            ),
        )

    def _remover_aresta(self, evento: EventoLog) -> None:
        """Remove a aresta indicada no payload."""
        self._arestas.pop(str(evento.payload["id"]), None)

    def _registrar_execucao(self, evento: EventoLog) -> None:
        """Cria ou atualiza o nó Run correspondente ao ciclo de vida da execução."""
        payload: Mapping[str, Any] = evento.payload
        id_run = str(payload.get("id", f"run-{evento.id}"))
        propriedades: dict[str, Any] = {
            "status_execucao": evento.tipo_evento.value,
            "disparado_por": evento.origem.value,
            "autor": evento.autor,
            **payload,
        }
        existente = self._nos.get(id_run)
        if existente is not None:
            atualizado = existente.com_propriedades(propriedades)
            self._nos[id_run] = atualizado.tocado_em(evento.timestamp_utc, evento.seq)
            return
        self._nos[id_run] = NoGrafo(
            id=id_run,
            tipo=TipoNo.RUN,
            rotulo=str(payload.get("rotulo", f"Run {id_run}")),
            propriedades=propriedades,
            metadados=metadados_do_evento(evento),
            ordem=ordem_do_evento(evento),
        )

    def _apenas_avancar_versao(self, evento: EventoLog) -> None:
        """A criação de ramo só move a versão do log, sem alterar nós ou arestas."""
        return
