"""A medição com o que o harness passou a gravar: leitura de cache, motivo sem consumo, duração e cota das rodadas."""

from graphow.avaliacao.orquestracao import MedicaoDeGoal, MedidorDeOrquestracao
from graphow.avaliacao.relatorio_orquestracao import formatar_relatorio
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from tests.avaliacao.test_orquestracao import _aresta, _no, _run, _tarefa
from tests.avaliacao.test_orquestracao import _montar as _montar_com_runs_antigos

RELATORIO_DOS_RUNS_ANTIGOS: tuple[str, ...] = (
    "[goal-a] goal-a | configuracao: padrao",
    "  tarefas 2 | concluidas 2 | sem retrabalho 1 | com retrabalho 1 (1 correcoes) | revisao: 1 rejeitadas, 1 aprovadas",
    "  modelo por tarefa: opus 1, sonnet 1",
    "  tokens 3.350 (graphow-executor 1.000, graphow-executor-opus 2.000, graphow-explorador 50, graphow-revisor 0,"
    " orquestrador 300) | 1 Run sem tokens",
    "[goal-b] goal-b | configuracao: tudo-opus",
    "  tarefas 1 | concluidas 0 | sem retrabalho 0 | com retrabalho 0 (0 correcoes) | revisao: 0 rejeitadas, 0 aprovadas",
    "  modelo por tarefa: opus 1",
    "  tokens 350 (graphow-explorador 50, orquestrador 300)",
    "",
    "Por configuracao:",
    "  padrao: 1 Goals | 2 tarefas | 2 concluidas, 1 sem retrabalho (50%) | 1 rejeicoes | 3.350 tokens"
    " | 1.675 por tarefa concluida",
    "  tudo-opus: 1 Goals | 1 tarefas | 0 concluidas, 0 sem retrabalho (sem conclusao) | 0 rejeicoes | 350 tokens"
    " | sem conclusao por tarefa concluida",
)


def _montar() -> WriteKernel:
    """Um Goal com duas rodadas do condutor, dois executores e três Run sem tokens por motivos diferentes."""
    kernel = montar_kernel_em_memoria()
    operacoes = (
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-orq", TipoNo.SESSAO), _aresta("setor", "sess-orq", TipoAresta.CONTEM),
        _no("goal-n", TipoNo.GOAL, configuracao="padrao"), _aresta("sess-orq", "goal-n", TipoAresta.PRODUZ),
        *_tarefa("t1", "goal-n", modelo="sonnet", status=StatusTask.CONCLUIDO.value),
        *_tarefa("t2", "goal-n", modelo="opus", status=StatusTask.CONCLUIDO.value),
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso
    _run(kernel, "run-sess-orq", tokens_entrada=100, tokens_cache_leitura=900,
         cota_5h_fim=50, cota_semanal_fim=14)
    _run(kernel, "run-c1", agente="graphow-condutor", tokens_entrada=200, tokens_cache_leitura=800,
         inicio="2026-09-29T10:00:00.000Z", fim="2026-09-29T10:30:00.000Z", duracao_s=1800,
         cota_5h_inicio=20, cota_semanal_inicio=10)
    _run(kernel, "run-c2", agente="graphow-condutor", tokens_entrada=100,
         inicio="2026-09-29T11:00:00.000Z", fim="2026-09-29T11:20:00.000Z", duracao_s=1200,
         cota_5h_inicio=35, cota_semanal_inicio=12)
    _run(kernel, "run-e1", agente="graphow-executor", tarefas=["t1"], tokens_entrada=1000,
         tokens_cache_leitura=4000, inicio="2026-09-29T10:05:00.000Z", fim="2026-09-29T10:20:00.000Z", duracao_s=900)
    _run(kernel, "run-e2", agente="graphow-executor", tarefas=["t2"], tokens_entrada=500,
         inicio="2026-09-29T11:02:00.000Z", fim="2026-09-29T11:10:00.000Z", duracao_s=480)
    _run(kernel, "run-rev", agente="graphow-revisor", tarefas=["t1"], motivo_sem_consumo="transcricao_ausente")
    _run(kernel, "run-sem-id", agente="subagente", motivo_sem_consumo="sem_agent_id")
    _run(kernel, "run-antigo", agente="graphow-explorador")
    return kernel


def _medir(kernel: WriteKernel) -> MedicaoDeGoal:
    """A medição do único Goal do cenário."""
    (medicao,) = MedidorDeOrquestracao(kernel.obter_view()).medir(["goal-n"])
    return medicao


def test_total_de_tokens_mostra_ao_lado_o_sem_cache_de_leitura_nominal() -> None:
    """A leitura de cache domina o total; a linha de tokens mostra os dois."""
    medicao = _medir(_montar())

    assert (medicao.tokens, medicao.tokens_cache_leitura, medicao.tokens_sem_cache_leitura) == (7600, 5700, 1900)
    linha = next(linha for linha in formatar_relatorio((medicao,)) if linha.startswith("  tokens "))
    assert linha.startswith("  tokens 7.600 (sem cache de leitura 1.900) (graphow-condutor 1.100, ")


def test_runs_sem_tokens_se_agrupam_por_motivo_nominal() -> None:
    """Cada Run sem tokens conta sob o motivo que o harness gravou; o Run antigo, sob `sem motivo`."""
    medicao = _medir(_montar())

    assert medicao.runs_sem_tokens_por_motivo == {"sem motivo": 1, "sem_agent_id": 1, "transcricao_ausente": 1}
    assert medicao.runs_sem_tokens == 3
    linha = next(linha for linha in formatar_relatorio((medicao,)) if linha.startswith("  tokens "))
    assert linha.endswith("| 3 Run sem tokens: 1 sem motivo, 1 sem_agent_id, 1 transcricao_ausente")


def test_rodadas_do_condutor_dao_duracao_e_variacao_de_cota_nominal() -> None:
    """A variação é o despacho seguinte menos o desta; a da última, a parada da raiz menos o despacho."""
    rodadas = _medir(_montar()).rodadas

    assert [rodada.id_run for rodada in rodadas] == ["run-c1", "run-c2"]
    assert [rodada.duracao_s for rodada in rodadas] == [1800, 1200]
    assert [(rodada.cota.cinco_horas, rodada.cota.semanal) for rodada in rodadas] == [(15, 2), (15, 2)]


def test_configuracao_ganha_minutos_cota_e_tokens_sem_cache_por_tarefa_nominal() -> None:
    """Por tarefa concluída: 50 minutos de condutor, 4 pontos semanais e 1.900 tokens sem cache, divididos por 2."""
    linhas = formatar_relatorio((_medir(_montar()),))

    padrao = next(linha for linha in linhas if linha.strip().startswith("padrao:"))
    assert padrao.endswith(
        "| 7.600 tokens | 3.800 por tarefa concluida (25 min, 2,0 pontos de cota semanal, 950 tokens sem cache de leitura)"
    )


def test_runs_antigos_dao_o_relatorio_de_sempre_edge_case() -> None:
    """Caso de borda: sem cache de leitura, motivo, duração nem cota nos Run, nenhuma linha muda."""
    medicoes = MedidorDeOrquestracao(_montar_com_runs_antigos().obter_view()).medir()

    assert formatar_relatorio(medicoes) == RELATORIO_DOS_RUNS_ANTIGOS


def test_janela_que_reiniciou_ou_cota_ausente_fica_desconhecida_edge_case() -> None:
    """Caso de borda: sem a cota da parada, a última rodada não tem variação; a negativa é reinício, não gasto."""
    kernel = _montar()
    _run(kernel, "run-sess-orq", cota_5h_fim=5, cota_semanal_fim=None)

    rodadas = _medir(kernel).rodadas

    assert (rodadas[1].cota.cinco_horas, rodadas[1].cota.semanal) == (None, None)
    assert (rodadas[0].cota.cinco_horas, rodadas[0].cota.semanal) == (15, 2)


def test_rodada_sem_inicio_vai_ao_fim_edge_case() -> None:
    """Caso de borda: o condutor cujo Run não trouxe instante fica depois dos datados, sem duração."""
    kernel = _montar()
    _run(kernel, "run-c0", agente="graphow-condutor", motivo_sem_consumo="transcricao_ausente")

    rodadas = _medir(kernel).rodadas

    assert [rodada.id_run for rodada in rodadas] == ["run-c1", "run-c2", "run-c0"]
    assert rodadas[2].duracao_s is None
