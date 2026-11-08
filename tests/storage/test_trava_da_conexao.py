"""Uma trava só para a conexão do banco: quem escreve nela de outra thread espera o COMMIT do lote.

A conexão é uma por processo, em autocommit. Com uma trava para a telemetria e
outra para cada adaptador, o INSERT de outra thread que caía entre o
`BEGIN IMMEDIATE` e o `COMMIT` de um lote entrava nele: a telemetria o
commitava pela metade, e o ROLLBACK do lote levava junto a linha do adaptador.
"""

from collections.abc import Callable
from pathlib import Path
import threading
from typing import Any

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.exceptions import ErroConflitoDeSequencia
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao
from graphow.storage.composicao import ConjuntoRepositorios, montar_repositorios_sqlite
from graphow.storage.instantaneos import InstantaneoGravado
from graphow.storage.linhagem_ramo import DefinicaoRamo
from graphow.storage.sqlite_store import SQLiteEventStore
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria, SessaoRegistrada

# Quanto a escrita de fora tem para (não) terminar enquanto o lote está aberto.
ESPERA_COM_O_LOTE_ABERTO_S: float = 0.5
PRAZO_S: float = 10.0


class StoreQuePausa(SQLiteEventStore):
    """O store que, já dentro do `BEGIN IMMEDIATE` do lote, avisa e espera o sinal para seguir."""

    def __init__(self, caminho_banco: Path) -> None:
        super().__init__(caminho_banco)
        self.dentro: threading.Event = threading.Event()
        self.seguir: threading.Event = threading.Event()

    def _parametros_insercao_evento(self, evento: EventoLog) -> tuple[Any, ...]:
        self.dentro.set()
        assert self.seguir.wait(PRAZO_S)
        return super()._parametros_insercao_evento(evento)


def _contar(store: SQLiteEventStore, tabela: str) -> int:
    with store.trava:
        return int(store.conexao.execute(f"SELECT COUNT(*) FROM {tabela};").fetchone()[0])


def _item(caminho: str, valor: dict[str, str]) -> ItemPatch:
    return ItemPatch(op=OperacaoPatch.ADD, path=caminho, value=valor)


def _proposta_de_tres_eventos() -> PropostaPatch:
    operacoes = (
        _item("/nos/proj-1", {"id": "proj-1", "tipo": TipoNo.PROJETO.value, "rotulo": "proj-1"}),
        _item("/nos/setor-1", {"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "setor-1"}),
        _item("/arestas/c-1", {"id": "c-1", "origem_id": "proj-1", "destino_id": "setor-1", "tipo": TipoAresta.CONTEM.value}),
    )
    return PropostaPatch.criar(DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="lote"))


def _em_thread(alvo: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=alvo, daemon=True)
    thread.start()
    return thread


def test_insert_da_telemetria_de_outra_thread_so_termina_depois_do_commit_do_kernel(tmp_path: Path) -> None:
    """T3i1.1: o INSERT espera o COMMIT do lote do kernel e, quando termina, o lote inteiro já está no log."""
    store = StoreQuePausa(tmp_path / "graphow.db")
    kernel = montar_kernel_sqlite(store)
    telemetria = RepositorioTelemetria(store.conexao, trava=store.trava)
    recibos: list[ResultadoSubmissao] = []
    eventos_vistos: list[int] = []
    lote = _em_thread(lambda: recibos.append(kernel.submeter_patch(_proposta_de_tres_eventos())))
    assert store.dentro.wait(PRAZO_S)

    def registrar() -> None:
        telemetria.registrar(SessaoRegistrada(id_goal="goal-1", papel="executor"))
        eventos_vistos.append(_contar(store, "eventos"))

    escrita = _em_thread(registrar)
    escrita.join(ESPERA_COM_O_LOTE_ABERTO_S)
    assert escrita.is_alive() and store.conexao.in_transaction
    store.seguir.set()
    lote.join(PRAZO_S)
    escrita.join(PRAZO_S)
    assert recibos[0].sucesso, recibos[0].mensagem
    assert eventos_vistos == [len(recibos[0].eventos_gerados)] == [3]
    assert _contar(store, "telemetria_de_sessoes") == 1
    store.fechar()


def _telemetria(store: SQLiteEventStore, _: ConjuntoRepositorios) -> None:
    RepositorioTelemetria(store.conexao, trava=store.trava).registrar(SessaoRegistrada(id_goal="goal-1", papel="executor"))


def _lock(_: SQLiteEventStore, repositorios: ConjuntoRepositorios) -> None:
    assert repositorios.locks.tentar_adquirir("task-1", "david")


def _ramo(_: SQLiteEventStore, repositorios: ConjuntoRepositorios) -> None:
    repositorios.ramos.registrar(DefinicaoRamo(ramo_id="ramo-1", ramo_base="main", seq_corte=0))


def _instantaneo(_: SQLiteEventStore, repositorios: ConjuntoRepositorios) -> None:
    assert repositorios.instantaneos is not None
    assert repositorios.instantaneos.gravar(InstantaneoGravado("main", 0, "ev-0", "impressao", "{}"))


@pytest.mark.parametrize(
    ("escrever", "tabela"),
    [(_telemetria, "telemetria_de_sessoes"), (_lock, "locks_de_tarefa"), (_ramo, "ramos"), (_instantaneo, "instantaneos")],
    ids=["telemetria", "locks", "ramos", "instantaneos"],
)
def test_o_lote_desfeito_nao_leva_a_linha_escrita_de_outra_thread_edge_case(
    tmp_path: Path, escrever: Callable[[SQLiteEventStore, ConjuntoRepositorios], None], tabela: str
) -> None:
    """Caso de borda: o lote que bate na sequência faz ROLLBACK, e a linha de fora, escrita depois dele, fica."""
    store = StoreQuePausa(tmp_path / "graphow.db")
    repositorios = montar_repositorios_sqlite(store)
    evento = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "no-1"}))
    repetido = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "no-2"}))
    conflitos: list[ErroConflitoDeSequencia] = []

    def gravar_o_lote() -> None:
        try:
            store.append_eventos((evento, repetido))
        except ErroConflitoDeSequencia as erro:
            conflitos.append(erro)

    lote = _em_thread(gravar_o_lote)
    assert store.dentro.wait(PRAZO_S)
    escrita = _em_thread(lambda: escrever(store, repositorios))
    escrita.join(ESPERA_COM_O_LOTE_ABERTO_S)
    assert escrita.is_alive()
    store.seguir.set()
    lote.join(PRAZO_S)
    escrita.join(PRAZO_S)
    assert len(conflitos) == 1 and not escrita.is_alive()
    assert (_contar(store, "eventos"), _contar(store, tabela)) == (0, 1)
    store.fechar()
