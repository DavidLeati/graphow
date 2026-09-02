"""Diagnóstico e reparo de sequências duplicadas no log de eventos.

Forks criados mais de uma vez sobre o mesmo ramo reiniciavam a numeração em 1 e,
sem índice único, duplicavam posições. Com seq repetido, ORDER BY seq deixa de ser
uma ordem total e o replay perde o determinismo. Ver auditoria F-06.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from graphow.core.exceptions import GraphowError

DESLOCAMENTO_TEMPORARIO: int = 1_000_000_000


@dataclass(frozen=True)
class RegistroEvento:
    """Projeção mínima de um evento, suficiente para ordenar e deduplicar."""

    id: str
    seq: int
    timestamp_utc: str
    parent_evento_id: str | None
    tipo_evento: str
    payload_json: str

    @property
    def assinatura_de_conteudo(self) -> tuple[str, str, str]:
        """Identidade do conteúdo, para reconhecer cópias geradas por fork repetido."""
        return (self.parent_evento_id or "", self.tipo_evento, self.payload_json)


@dataclass(frozen=True)
class DiagnosticoRamo:
    """Resultado imutável da inspeção de um ramo do log."""

    ramo_id: str
    total_eventos: int
    posicoes_duplicadas: int
    ids_a_remover: tuple[str, ...]
    # Atribuição final completa dos sobreviventes. Precisa cobrir todos eles, e não
    # apenas os que mudam, porque o reparo desloca o ramo inteiro antes de renumerar.
    renumeracao: Mapping[str, int]
    posicoes_alteradas: int

    @property
    def precisa_reparo(self) -> bool:
        """Indica se há duplicatas ou lacunas de numeração a corrigir."""
        return bool(self.ids_a_remover) or self.posicoes_alteradas > 0


class AcessoSequencias(ABC):
    """Contrato de acesso de baixo nível à tabela de eventos, para reparo."""

    @abstractmethod
    def listar_ramos(self) -> tuple[str, ...]:
        """Enumera os ramos presentes no log."""
        raise NotImplementedError

    @abstractmethod
    def listar_registros(self, ramo_id: str) -> tuple[RegistroEvento, ...]:
        """Lê os registros do ramo em ordem determinística de sequência e tempo."""
        raise NotImplementedError

    @abstractmethod
    def aplicar_reparo(self, diagnostico: DiagnosticoRamo) -> None:
        """Remove duplicatas e renumera o ramo em uma única transação."""
        raise NotImplementedError


class AcessoSequenciasSQLite(AcessoSequencias):
    """Adaptador que opera diretamente no arquivo, mesmo quando ele está inconsistente."""

    def __init__(self, caminho_banco: Path) -> None:
        self._caminho_banco: Path = caminho_banco

    def listar_ramos(self) -> tuple[str, ...]:
        """Enumera os ramos distintos registrados na tabela de eventos."""
        with self._abrir() as conexao:
            linhas = conexao.execute("SELECT DISTINCT ramo_id FROM eventos ORDER BY ramo_id;").fetchall()
            return tuple(str(linha[0]) for linha in linhas)

    def listar_registros(self, ramo_id: str) -> tuple[RegistroEvento, ...]:
        """Lê o ramo ordenado por sequência, tempo e identificador, nesta ordem."""
        with self._abrir() as conexao:
            linhas = conexao.execute(
                "SELECT id, seq, timestamp_utc, parent_evento_id, tipo_evento, payload_json "
                "FROM eventos WHERE ramo_id = ? ORDER BY seq ASC, timestamp_utc ASC, id ASC;",
                (ramo_id,),
            ).fetchall()
        return tuple(
            RegistroEvento(
                id=str(linha[0]),
                seq=int(linha[1]),
                timestamp_utc=str(linha[2]),
                parent_evento_id=str(linha[3]) if linha[3] is not None else None,
                tipo_evento=str(linha[4]),
                payload_json=str(linha[5]),
            )
            for linha in linhas
        )

    def aplicar_reparo(self, diagnostico: DiagnosticoRamo) -> None:
        """Aplica remoção e renumeração dentro de uma transação única e reversível."""
        with self._abrir() as conexao:
            cursor = conexao.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                self._executar_passos_de_reparo(cursor, diagnostico)
                cursor.execute("COMMIT;")
            except sqlite3.Error as erro:
                cursor.execute("ROLLBACK;")
                raise GraphowError(
                    f"Falha ao reparar sequencias do ramo: {erro}", {"ramo_id": diagnostico.ramo_id}
                ) from erro

    def _executar_passos_de_reparo(self, cursor: sqlite3.Cursor, diagnostico: DiagnosticoRamo) -> None:
        """Remove as cópias e renumera em duas fases, evitando colisão transitória."""
        cursor.executemany(
            "DELETE FROM eventos WHERE id = ?;", [(id_evento,) for id_evento in diagnostico.ids_a_remover]
        )
        cursor.execute(
            "UPDATE eventos SET seq = seq + ? WHERE ramo_id = ?;",
            (DESLOCAMENTO_TEMPORARIO, diagnostico.ramo_id),
        )
        cursor.executemany(
            "UPDATE eventos SET seq = ? WHERE id = ?;",
            [(nova_seq, id_evento) for id_evento, nova_seq in diagnostico.renumeracao.items()],
        )

    def _abrir(self) -> sqlite3.Connection:
        """Abre a conexão em modo autocommit, sem passar pelo repositório de eventos."""
        return sqlite3.connect(str(self._caminho_banco), isolation_level=None)


class AnalisadorSequencias:
    """Consulta pura que descreve o reparo necessário sem tocar no banco."""

    def __init__(self, acesso: AcessoSequencias) -> None:
        self._acesso: AcessoSequencias = acesso

    def diagnosticar_todos_os_ramos(self) -> tuple[DiagnosticoRamo, ...]:
        """Diagnostica cada ramo existente no log."""
        return tuple(self.diagnosticar(ramo_id) for ramo_id in self._acesso.listar_ramos())

    def diagnosticar(self, ramo_id: str) -> DiagnosticoRamo:
        """Monta o plano de deduplicação e renumeração contígua do ramo."""
        registros = self._acesso.listar_registros(ramo_id)
        ids_a_remover = self._identificar_copias(registros)
        sobreviventes = [registro for registro in registros if registro.id not in ids_a_remover]
        renumeracao = self._montar_renumeracao(sobreviventes)
        return DiagnosticoRamo(
            ramo_id=ramo_id,
            total_eventos=len(registros),
            posicoes_duplicadas=self._contar_posicoes_duplicadas(registros),
            ids_a_remover=tuple(sorted(ids_a_remover)),
            renumeracao=renumeracao,
            posicoes_alteradas=self._contar_posicoes_alteradas(sobreviventes, renumeracao),
        )

    def _contar_posicoes_alteradas(
        self,
        sobreviventes: Sequence[RegistroEvento],
        renumeracao: Mapping[str, int],
    ) -> int:
        """Conta quantos eventos de fato trocam de posição na renumeração."""
        return sum(1 for registro in sobreviventes if renumeracao[registro.id] != registro.seq)

    def _identificar_copias(self, registros: Sequence[RegistroEvento]) -> frozenset[str]:
        """Marca para remoção as réplicas exatas de um mesmo evento de origem."""
        vistos: set[tuple[str, str, str]] = set()
        a_remover: set[str] = set()
        for registro in registros:
            assinatura = registro.assinatura_de_conteudo
            if not registro.parent_evento_id:
                continue
            if assinatura in vistos:
                a_remover.add(registro.id)
                continue
            vistos.add(assinatura)
        return frozenset(a_remover)

    def _contar_posicoes_duplicadas(self, registros: Sequence[RegistroEvento]) -> int:
        """Conta quantas posições de sequência aparecem mais de uma vez."""
        ocupacoes: dict[int, int] = defaultdict(int)
        for registro in registros:
            ocupacoes[registro.seq] += 1
        return sum(1 for total in ocupacoes.values() if total > 1)

    def _montar_renumeracao(self, sobreviventes: Sequence[RegistroEvento]) -> Mapping[str, int]:
        """Atribui a todos os sobreviventes posições contíguas de 1 a N, em ordem."""
        return {registro.id: posicao for posicao, registro in enumerate(sobreviventes, start=1)}


class ReparadorSequencias:
    """Comando que executa o plano de reparo previamente diagnosticado."""

    def __init__(self, acesso: AcessoSequencias) -> None:
        self._acesso: AcessoSequencias = acesso

    def reparar(self, diagnostico: DiagnosticoRamo) -> None:
        """Aplica o reparo do ramo, se ele for necessário."""
        if not diagnostico.precisa_reparo:
            return
        self._acesso.aplicar_reparo(diagnostico)
