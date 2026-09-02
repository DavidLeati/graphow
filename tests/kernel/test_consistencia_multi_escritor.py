"""Testes das garantias de consistência quando há mais de um escritor no mesmo banco.

Reproduzem, como propriedades verificáveis, os achados F-04 (cache que não
reconsulta o log) e F-07 (commit que não era transacional) da auditoria.
"""

from pathlib import Path

import pytest

from graphow.core.exceptions import ErroConflitoDeSequencia
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.storage.lock_store import LockStoreSQLite
from graphow.storage.sqlite_store import SQLiteEventStore


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO):
    """Submete operações sob o papel informado e devolve o recibo."""
    dados = DadosPropostaPatch(
        autor="david", papel=papel, operacoes=tuple(operacoes), justificativa="teste de consistencia"
    )
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _criar_task(kernel: WriteKernel, id_task: str) -> None:
    """Cria uma Task pendente no ramo principal."""
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/nos/{id_task}",
                value={
                    "id": id_task,
                    "tipo": TipoNo.TASK.value,
                    "rotulo": "Tarefa",
                    "propriedades": {"status": StatusTask.PENDENTE.value},
                },
            )
        ],
    )


def _bloquear_task(kernel: WriteKernel, id_task: str, id_questao: str) -> None:
    """Abre uma Question e a liga à Task por uma aresta de bloqueio."""
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/nos/{id_questao}",
                value={
                    "id": id_questao,
                    "tipo": TipoNo.QUESTION.value,
                    "rotulo": "Posso apagar a base?",
                    "propriedades": {"status": StatusQuestion.ABERTA.value},
                },
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/arestas/bloq-{id_questao}",
                value={
                    "id": f"bloq-{id_questao}",
                    "origem_id": id_questao,
                    "destino_id": id_task,
                    "tipo": TipoAresta.BLOQUEIA.value,
                },
            ),
        ],
    )


def test_segundo_escritor_enxerga_bloqueio_criado_pelo_primeiro(tmp_path: Path) -> None:
    """O cenario exato de F-04: dois kernels sobre o mesmo banco nao podem divergir."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio_a, SQLiteEventStore(str(caminho)) as repositorio_b:
        kernel_web = WriteKernel(repositorio_a)
        kernel_agente = WriteKernel(repositorio_b)

        _criar_task(kernel_web, "task-4")
        assert kernel_web.obter_view().contem_no("task-4") is True

        _bloquear_task(kernel_agente, "task-4", "quest-1")

        fechamento = _submeter(
            kernel_web,
            [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/task-4/propriedades/status", value="concluido")],
        )
        assert fechamento.sucesso is False
        assert "Question aberta" in fechamento.mensagem


def test_projecao_incorpora_eventos_escritos_por_outro_processo(tmp_path: Path) -> None:
    """A consulta de estado reflete o que outro escritor persistiu depois da ultima leitura."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio_a, SQLiteEventStore(str(caminho)) as repositorio_b:
        kernel_leitor = WriteKernel(repositorio_a)
        kernel_escritor = WriteKernel(repositorio_b)

        assert kernel_leitor.obter_view().total_nos == 0
        _criar_task(kernel_escritor, "task-externa")
        assert kernel_leitor.obter_view().contem_no("task-externa") is True


def test_lote_rejeitado_nao_persiste_evento_algum(tmp_path: Path) -> None:
    """F-07: um lote que colide na sequencia nao pode deixar metade dos eventos gravada."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio:
        kernel = WriteKernel(repositorio)
        _criar_task(kernel, "task-1")
        seq_antes = repositorio.obter_ultimo_seq("main")

        eventos_existentes = repositorio.ler_eventos("main")
        with pytest.raises(ErroConflitoDeSequencia):
            repositorio.append_eventos(eventos_existentes)

        assert repositorio.obter_ultimo_seq("main") == seq_antes
        assert len(repositorio.ler_eventos("main")) == len(eventos_existentes)


def test_sequencias_nunca_se_repetem_no_mesmo_ramo(tmp_path: Path) -> None:
    """Escritas alternadas entre dois kernels produzem uma numeracao sem colisao."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio_a, SQLiteEventStore(str(caminho)) as repositorio_b:
        kernel_par = WriteKernel(repositorio_a)
        kernel_impar = WriteKernel(repositorio_b)
        for indice in range(10):
            kernel_da_vez = kernel_par if indice % 2 == 0 else kernel_impar
            _criar_task(kernel_da_vez, f"task-{indice}")

        sequencias = [evento.seq for evento in repositorio_a.ler_eventos("main")]
        assert sequencias == sorted(sequencias)
        assert len(sequencias) == len(set(sequencias)) == 10


def test_lock_de_tarefa_e_visto_por_outro_processo(tmp_path: Path) -> None:
    """Locks compartilhados pelo banco impedem escrita simultanea entre processos."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio_a, SQLiteEventStore(str(caminho)) as repositorio_b:
        kernel_a = WriteKernel(repositorio_a, DependenciasKernel(repositorio_locks=LockStoreSQLite(repositorio_a.conexao)))
        kernel_b = WriteKernel(repositorio_b, DependenciasKernel(repositorio_locks=LockStoreSQLite(repositorio_b.conexao)))

        assert kernel_a.adquirir_lock_task("task-1", "agente-executor") is True
        assert kernel_b.adquirir_lock_task("task-1", "outro-agente") is False
        assert kernel_b.obter_dono_do_lock("task-1") == "agente-executor"

        assert kernel_b.liberar_lock_task("task-1", "outro-agente") is False
        assert kernel_a.liberar_lock_task("task-1", "agente-executor") is True
        assert kernel_b.adquirir_lock_task("task-1", "outro-agente") is True


def test_escrita_em_no_travado_por_outro_autor_e_barrada(tmp_path: Path) -> None:
    """Caso de borda: o InvariantGate consulta o lock compartilhado, nao um mapa local."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as repositorio_a, SQLiteEventStore(str(caminho)) as repositorio_b:
        locks_a = LockStoreSQLite(repositorio_a.conexao)
        kernel_a = WriteKernel(repositorio_a, DependenciasKernel(repositorio_locks=locks_a))
        kernel_b = WriteKernel(
            repositorio_b, DependenciasKernel(repositorio_locks=LockStoreSQLite(repositorio_b.conexao))
        )

        _criar_task(kernel_a, "task-travada")
        assert kernel_a.adquirir_lock_task("task-travada", "agente-executor") is True

        recibo = _submeter(
            kernel_b,
            [
                ItemPatch(
                    op=OperacaoPatch.REPLACE,
                    path="/nos/task-travada/propriedades/status",
                    value=StatusTask.EM_ANDAMENTO.value,
                )
            ],
        )
        assert recibo.sucesso is False
        assert "bloqueado para escrita" in recibo.mensagem
