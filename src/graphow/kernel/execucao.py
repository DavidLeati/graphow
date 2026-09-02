"""Registro do ciclo de vida de execução de um agente no log compartilhado.

`EXECUCAO_SOLICITADA`, `EXECUCAO_INICIADA` e `EXECUCAO_CONCLUIDA` existiam no
vocabulário e eram consumidos pelo acumulador, mas nenhum caminho do produto os
emitia: o contrato do harness estava declarado e não exercido. Estes eventos não
são patches — não descrevem uma mutação proposta, e sim um fato observado sobre
a execução — e por isso entram por uma porta própria, sempre sob a identidade
fixada na configuração do harness. Ver achados A-12 e A-10.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor

EVENTOS_DE_CICLO_DE_EXECUCAO: frozenset[TipoEvento] = frozenset(
    {
        TipoEvento.EXECUCAO_SOLICITADA,
        TipoEvento.EXECUCAO_INICIADA,
        TipoEvento.EXECUCAO_CONCLUIDA,
    }
)


@dataclass(frozen=True)
class PedidoDeExecucao:
    """Fato de ciclo de vida a registrar, com a identidade de quem o observou."""

    id_run: str
    id_sessao: str
    tipo_evento: TipoEvento
    autor: str = "harness"
    papel: PapelAutor = PapelAutor.SISTEMA
    origem: OrigemEvento = OrigemEvento.HARNESS
    ramo_id: str = "main"
    dados: Mapping[str, Any] = field(default_factory=dict)

    @property
    def eh_de_ciclo_de_execucao(self) -> bool:
        """Recusa qualquer tipo de evento que não pertença a este canal."""
        return self.tipo_evento in EVENTOS_DE_CICLO_DE_EXECUCAO

    def montar_payload(self) -> dict[str, Any]:
        """Payload do evento, com o vínculo à sessão sempre presente."""
        return {
            "id": self.id_run,
            "id_sessao": self.id_sessao,
            "rotulo": f"Execucao {self.id_run}",
            **dict(self.dados),
        }

    def montar_evento(self, seq: int) -> EventoLog:
        """Constrói o evento numerado na posição informada do log."""
        return EventoLog.criar(
            DadosCriacaoEvento(
                seq=seq,
                autor=self.autor,
                papel=self.papel,
                tipo_evento=self.tipo_evento,
                payload=self.montar_payload(),
                origem=self.origem,
                ramo_id=self.ramo_id,
            )
        )
