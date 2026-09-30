"""`orquestracao-medir --por-rodada`: uma linha por rodada do condutor, com o que caiu na janela dela."""

from datetime import datetime, timedelta, timezone
import time

from graphow.avaliacao.orquestracao import MedicaoDeGoal, MedidorDeOrquestracao
from graphow.avaliacao.relatorio_orquestracao import formatar_relatorio
from graphow.avaliacao.relatorio_rodadas import NOTA_DAS_RODADAS, SEM_RODADAS
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from tests.avaliacao.test_orquestracao import _aresta, _derivado, _montar, _no, _run, _tarefa

FOLGA_DO_RELOGIO_S: float = 0.02


def _submeter(kernel: WriteKernel, *operacoes: ItemPatch) -> None:
    """Um patch humano que precisa passar."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem


def _fechar(id_task: str) -> ItemPatch:
    """A troca de status que `concluir_tarefa` faz."""
    return ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_task}/propriedades/status", value=StatusTask.CONCLUIDO.value)


def _agora() -> datetime:
    """O relógio do log, que é o que data os nós, lido com folga dos dois lados.

    No Windows o relógio anda em passos de milissegundos; sem a folga, a
    escrita e a borda da janela caem no mesmo instante.
    """
    time.sleep(FOLGA_DO_RELOGIO_S)
    instante = datetime.now(timezone.utc)
    time.sleep(FOLGA_DO_RELOGIO_S)
    return instante


def _iso(instante: datetime) -> str:
    """O instante como o harness o grava."""
    return instante.isoformat().replace("+00:00", "Z")


def _montar_duas_rodadas() -> tuple[WriteKernel, datetime]:
    """Duas rodadas do condutor na mesma sessão: a primeira fecha t1 e aprova, a segunda fecha t2 e rejeita.

    O log data os nós pelo relógio, então as janelas dos condutores são medidas
    em volta das escritas de cada rodada.
    """
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-orq", TipoNo.SESSAO), _aresta("setor", "sess-orq", TipoAresta.CONTEM),
        _no("goal-r", TipoNo.GOAL, configuracao="padrao"), _aresta("sess-orq", "goal-r", TipoAresta.PRODUZ),
        *_tarefa("t1", "goal-r", status=StatusTask.PENDENTE.value),
        *_tarefa("t2", "goal-r", status=StatusTask.PENDENTE.value),
    )
    r1_inicio = _agora()
    _submeter(kernel, _fechar("t1"), *_derivado("evi-ok", TipoNo.EVIDENCE, ("t1",), veredito="aprovado"))
    r1_fim = _agora()
    r2_inicio = _agora()
    _submeter(kernel, _fechar("t2"), *_derivado("evi-rej", TipoNo.EVIDENCE, ("t2",), veredito="rejeitado"))
    r2_fim = _agora()
    _run(kernel, "run-sess-orq", tokens_entrada=7, inicio=_iso(r1_inicio - timedelta(hours=1)), cota_5h_fim=50, cota_semanal_fim=14)
    _run(kernel, "run-c1", agente="graphow-condutor", tokens_entrada=200, tokens_cache_leitura=800,
         inicio=_iso(r1_inicio), fim=_iso(r1_fim), duracao_s=1800, cota_5h_inicio=20, cota_semanal_inicio=10)
    _run(kernel, "run-c2", agente="graphow-condutor", tokens_entrada=100,
         inicio=_iso(r2_inicio), fim=_iso(r2_fim), duracao_s=1200, cota_5h_inicio=35, cota_semanal_inicio=12.5)
    _run(kernel, "run-e1", agente="graphow-executor", tarefas=["t1"], tokens_entrada=1000, tokens_cache_leitura=4000,
         inicio=_iso(r1_inicio + (r1_fim - r1_inicio) / 2))
    return kernel, r1_inicio


def _medir(kernel: WriteKernel) -> MedicaoDeGoal:
    """A medição do Goal das rodadas."""
    (medicao,) = MedidorDeOrquestracao(kernel.obter_view()).medir(["goal-r"])
    return medicao


def test_por_rodada_da_uma_linha_por_condutor_com_a_janela_nominal() -> None:
    """R1 fecha t1 com um aprovado e soma o executor que começou nela; R2 fecha t2 com um rejeitado."""
    kernel, r1_inicio = _montar_duas_rodadas()

    linhas = formatar_relatorio((_medir(kernel),), por_rodada=True)

    quando = r1_inicio.strftime("%Y-%m-%d %H:%M")
    indice = linhas.index("  rodadas:")
    assert linhas[indice + 1] == (
        f"    R1 {quando} | 30 min | concluidas 1 | revisao 1 aprovadas, 0 rejeitadas"
        " | tokens 6.000 (sem cache 1.200) | cota 5h +15, semana +2,5"
    )
    assert linhas[indice + 2].startswith("    R2 ")
    assert linhas[indice + 2].endswith(
        "| 20 min | concluidas 1 | revisao 0 aprovadas, 1 rejeitadas | tokens 100 (sem cache 100) | cota 5h +15, semana +1,5"
    )
    assert linhas[-len(NOTA_DAS_RODADAS):] == NOTA_DAS_RODADAS


def test_rodada_sem_inicio_vai_ao_fim_sem_janela_edge_case() -> None:
    """Caso de borda: o condutor sem instante fica por último, sem duração, sem janela e com cota desconhecida."""
    kernel, _ = _montar_duas_rodadas()
    _run(kernel, "run-c0", agente="graphow-condutor", motivo_sem_consumo="transcricao_ausente")

    linhas = formatar_relatorio((_medir(kernel),), por_rodada=True)

    assert "    R3 sem inicio | sem duracao | cota 5h ?, semana ?" in linhas


def test_sem_por_rodada_o_relatorio_nao_ganha_linha_de_rodada_edge_case() -> None:
    """Caso de borda: a opção é que acrescenta as linhas; sem ela, nem a nota aparece."""
    kernel, _ = _montar_duas_rodadas()

    linhas = formatar_relatorio((_medir(kernel),))

    assert "  rodadas:" not in linhas
    assert NOTA_DAS_RODADAS[0] not in linhas


def test_goal_sem_condutor_diz_que_nao_ha_rodada_edge_case() -> None:
    """Caso de borda: com Run antigos, sem condutor, a linha diz que não há rodada e a nota não aparece."""
    linhas = formatar_relatorio(MedidorDeOrquestracao(_montar().obter_view()).medir(), por_rodada=True)

    assert linhas.count(SEM_RODADAS) == 2
    assert NOTA_DAS_RODADAS[0] not in linhas
