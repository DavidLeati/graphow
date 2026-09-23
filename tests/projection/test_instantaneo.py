"""Testes do instantâneo da projeção: usado quando confere com o log, ignorado quando não."""

from pathlib import Path

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.projection import instantaneo as modulo
from graphow.projection.instantaneo import (
    ReconstrucaoComInstantaneo,
    desserializar_estado,
    impressao_da_projecao,
    serializar_estado,
)
from graphow.projection.reducer import GrafoReducer
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.storage.instantaneos import InstantaneoGravado, RepositorioInstantaneosEmMemoria


def _evento(seq: int, tipo: TipoEvento, payload: dict[str, object]) -> EventoLog:
    """Evento do ramo main, escrito pelo humano."""
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, tipo, payload))


def _log(total_tasks: int) -> list[EventoLog]:
    """Tasks criadas, ligadas em cadeia, com uma atualização e uma remoção no meio."""
    eventos = [_evento(1, TipoEvento.NO_CRIADO, {"id": "g", "tipo": "Goal", "rotulo": "Raiz ç"})]
    for i in range(1, total_tasks):
        payload = {"id": f"t{i}", "tipo": "Task", "rotulo": f"T{i}", "propriedades": {"status": "pendente", "n": i}}
        eventos.append(_evento(len(eventos) + 1, TipoEvento.NO_CRIADO, payload))
        pai = "g" if i == 1 else f"t{i - 1}"
        aresta = {"id": f"e{i}", "origem_id": pai, "destino_id": f"t{i}", "tipo": "decompoe"}
        eventos.append(_evento(len(eventos) + 1, TipoEvento.ARESTA_CRIADA, aresta))
    atualizacao = {"id": "t1", "propriedades": {"status": "concluido"}, "propriedades_removidas": ["n"]}
    eventos.append(_evento(len(eventos) + 1, TipoEvento.NO_ATUALIZADO, atualizacao))
    eventos.append(_evento(len(eventos) + 1, TipoEvento.ARESTA_REMOVIDA, {"id": "e2"}))
    return eventos


def _com_log(eventos: list[EventoLog]) -> InMemoryEventStore:
    """Store em memória já com o log gravado."""
    store = InMemoryEventStore()
    store.append_eventos(eventos)
    return store


def test_serializacao_devolve_estado_identico_nominal() -> None:
    """Ida e volta preservam todo campo, inclusive a ordem de inserção."""
    estado = GrafoReducer.reconstruir(_log(50))

    refeito = desserializar_estado(serializar_estado(estado))

    assert refeito == estado
    assert list(refeito.nos) == list(estado.nos)
    assert list(refeito.arestas) == list(estado.arestas)


def test_instantaneo_que_confere_e_o_ponto_de_partida_nominal() -> None:
    """O estado sai do instantâneo e dos eventos depois dele, não do replay inteiro."""
    eventos = _log(20)
    corte = eventos[9]
    base = GrafoReducer.reconstruir(eventos[:10])
    marcado = base.nos["g"].com_propriedades({"so_no_instantaneo": True})
    base_marcada = GrafoEstado(nos={**base.nos, "g": marcado}, arestas=base.arestas, versao_log=base.versao_log)
    instantaneos = RepositorioInstantaneosEmMemoria()
    instantaneos.gravar(
        InstantaneoGravado("main", corte.seq, corte.id, impressao_da_projecao(), serializar_estado(base_marcada))
    )

    estado, seq = ReconstrucaoComInstantaneo(_com_log(eventos), instantaneos).reconstruir("main")

    assert estado.nos["g"].obter_propriedade("so_no_instantaneo") is True
    assert seq == eventos[-1].seq
    assert set(estado.nos) == set(GrafoReducer.reconstruir(eventos).nos)


def test_instantaneo_de_log_reescrito_e_ignorado_edge_case() -> None:
    """Caso de borda: o evento na posição do corte não é mais o mesmo; vale o replay."""
    eventos = _log(20)
    instantaneos = RepositorioInstantaneosEmMemoria()
    lixo = serializar_estado(GrafoReducer.reconstruir(eventos[:3]))
    instantaneos.gravar(InstantaneoGravado("main", 10, "outro-evento", impressao_da_projecao(), lixo))

    estado, _ = ReconstrucaoComInstantaneo(_com_log(eventos), instantaneos).reconstruir("main")

    assert estado == GrafoReducer.reconstruir(eventos)


def test_instantaneo_de_outro_codigo_de_projecao_e_ignorado_edge_case() -> None:
    """Caso de borda: impressão digital diferente; o estado foi dobrado por outras regras."""
    eventos = _log(20)
    corte = eventos[9]
    instantaneos = RepositorioInstantaneosEmMemoria()
    lixo = serializar_estado(GrafoReducer.reconstruir(eventos[:3]))
    instantaneos.gravar(InstantaneoGravado("main", corte.seq, corte.id, "impressao-antiga", lixo))

    estado, _ = ReconstrucaoComInstantaneo(_com_log(eventos), instantaneos).reconstruir("main")

    assert estado == GrafoReducer.reconstruir(eventos)


def test_instantaneo_ilegivel_e_ignorado_edge_case() -> None:
    """Caso de borda: texto corrompido não derruba a abertura."""
    eventos = _log(20)
    corte = eventos[9]
    instantaneos = RepositorioInstantaneosEmMemoria()
    instantaneos.gravar(InstantaneoGravado("main", corte.seq, corte.id, impressao_da_projecao(), '{"nos": [[1]]'))

    estado, _ = ReconstrucaoComInstantaneo(_com_log(eventos), instantaneos).reconstruir("main")

    assert estado == GrafoReducer.reconstruir(eventos)


def test_abertura_sqlite_grava_e_reusa_o_instantaneo_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Primeira abertura grava; a segunda parte dele e chega ao mesmo estado do replay."""
    monkeypatch.setattr(modulo, "EVENTOS_ATE_NOVO_INSTANTANEO", 100)
    caminho = tmp_path / "graphow.db"
    eventos = _log(80)
    store, kernel = abrir_kernel_sqlite(caminho)
    store.append_eventos(eventos)
    primeiro = kernel.obter_estado("main")
    gravado = store.conexao.execute("SELECT seq, evento_id FROM instantaneos WHERE ramo_id = 'main';").fetchone()
    store.fechar()

    store, kernel = abrir_kernel_sqlite(caminho)
    segundo = kernel.obter_estado("main")
    store.fechar()

    assert gravado == (eventos[-1].seq, eventos[-1].id)
    assert primeiro == segundo == GrafoReducer.reconstruir(eventos)
