"""A fatia de conflito e o aceite depois do rebase (revisão da T3g): a base nova mesclada é a referência, e nada a desfaz."""

from pathlib import Path

from graphow.orquestrador.configuracao_do_aceite import diff_da_configuracao
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import FatiaRegistrada, ler_estado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    SOMA_ERRADA,
    Bancada,
    ate_o_portao_aprovado,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    verificacao,
)
from tests.orquestrador.test_base_que_andou import (
    RAMO,
    SOMA_COM_CABECALHO,
    SOMA_DA_BASE_QUE_CONFLITA,
    SOMA_RESOLVIDA,
    ExecutorQueAndaABase,
    _na_historia,
    _rebases,
    _roteiro_limpo,
    _verificacoes,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SETTINGS_DO_HUMANO: str = '{"permissions": {"allow": []}}\n'
INSTRUCOES_DO_HUMANO: str = "# Instrucoes do humano\nResponda em portugues.\n"
CONFTEST_DO_HUMANO: str = "def pytest_pyfunc_call(pyfuncitem):\n    return None\n"
CONFTEST_DA_BASE: str = "import sys\n"
ACEITE_COM_FATOR: str = (
    'import sys\nsys.path.insert(0, ".")\nfrom soma import somar\nfrom fator import FATOR\n\n\n'
    "def test_c1_soma():\n    assert somar(2, 3) * FATOR == 5, 'C1'\n\n\ntest_c1_soma()\nprint('aceite ok')\n"
)


def _commit(repositorio: Path, arquivos: dict[str, str], mensagem: str) -> str:
    """O commit dos arquivos dados na branch aberta do repositório; devolve o hash."""
    for nome, conteudo in arquivos.items():
        (repositorio / nome).parent.mkdir(parents=True, exist_ok=True)
        (repositorio / nome).write_text(conteudo, encoding="utf-8", newline="\n")
    git(repositorio, "add", "-A")
    git(repositorio, "commit", "-q", "-m", mensagem)
    return git(repositorio, "rev-parse", "HEAD").strip()


def _humano_depois_do_verificador(bancada: Bancada, arquivos: dict[str, str]) -> ExecutorQueAndaABase:
    """O executor que, depois da caçada do verificador, faz o commit do humano com os arquivos na main dele."""
    return ExecutorQueAndaABase(bancada.executor, "verificador", lambda: _commit(bancada.repositorio, arquivos, "Humano"))


def _fatia_de_conflito(bancada: Bancada) -> FatiaRegistrada:
    """A fatia M1.R1 do Goal."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    (conflito,) = [fatia for fatia in estado.fatias if fatia.codigo == "M1.R1"]
    return conflito


def _roteiro_com_a_fatia(*executores: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """O roteiro limpo com as respostas do executor da fatia de conflito e a conferência depois dela."""
    roteiro = _roteiro_limpo()
    roteiro["executor"] += list(executores)
    roteiro["verificador"].append(verificacao("atende"))
    return roteiro


def _roteiro_do_fator(*executores: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """O roteiro limpo com o teste de aceite de C1 que depende de fator.py, que nenhuma fatia toca."""
    roteiro = _roteiro_limpo()
    roteiro["aceite"] = [autor_de_aceite()]
    roteiro["aceite"][0]["arquivos"] = {"aceite/aceite_c1.py": ACEITE_COM_FATOR}
    roteiro["executor"] += list(executores)
    return roteiro


def test_fatia_de_conflito_sela_o_claude_como_na_base_nova_e_ele_chega_a_main_nominal(tmp_path: Path) -> None:
    """T3g2.1: a base traz o conflito, um .claude/settings.json e um CLAUDE.md do humano; o selo os mantém, e a main os tem."""
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA,
                                                       ".claude/settings.json": SETTINGS_DO_HUMANO, "CLAUDE.md": INSTRUCOES_DO_HUMANO})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "show", "main:.claude/settings.json") == SETTINGS_DO_HUMANO
    assert git(bancada.repositorio, "show", "main:CLAUDE.md") == INSTRUCOES_DO_HUMANO
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_RESOLVIDA
    conflito = _fatia_de_conflito(bancada)
    assert conflito.status == "concluido" and conflito.falhas == 0, "o .claude/ da base nao e trava mexida"


def test_fatia_de_conflito_que_desfaz_a_base_fora_do_conflito_e_recusada_edge_case(tmp_path: Path) -> None:
    """T3g2.1: o executor volta LICENCA.txt (só a base a mudou) à v1; a tentativa é recusada, e a base chega inteira."""
    errado = executor_pronto({"soma.py": SOMA_RESOLVIDA, "LICENCA.txt": "v1\n"})
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(errado, executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    _commit(bancada.repositorio, {"LICENCA.txt": "v1\n"}, "Licenca v1")
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA, "LICENCA.txt": "v2 do humano\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "show", "main:LICENCA.txt") == "v2 do humano\n"
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_RESOLVIDA
    segunda = bancada.chamadas("executor")[3]["stdin"]
    assert "desfez o que a base nova" in segunda and "LICENCA.txt" in segunda
    assert _fatia_de_conflito(bancada).falhas == 1


def test_fatia_de_conflito_com_o_aceite_de_outro_goal_e_o_conftest_do_humano_na_base_passa_nominal(tmp_path: Path) -> None:
    """T3g2.3: a base traz o conflito, o aceite/ de outro Goal e um conftest.py com hook; nada disso é da fatia, e ela passa."""
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA, "conftest.py": CONFTEST_DO_HUMANO,
                                                       "aceite/aceite_outro_goal.py": "print('outro goal')\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    conflito = _fatia_de_conflito(bancada)
    assert conflito.status == "concluido" and conflito.falhas == 0
    assert git(bancada.repositorio, "show", "main:aceite/aceite_outro_goal.py") == "print('outro goal')\n"
    assert git(bancada.repositorio, "show", "main:conftest.py") == CONFTEST_DO_HUMANO
    assert _verificacoes(bancada) == ["verificador", "conferencia"]


def test_aceite_vermelho_depois_do_rebase_limpo_vira_fatia_de_conflito_e_nao_chega_a_base_edge_case(tmp_path: Path) -> None:
    """T3g2.2: a base muda fator.py, que nenhuma fatia toca, e o aceite fica vermelho; a fatia de conflito não o resolve."""
    bancada = montar_bancada(tmp_path, _roteiro_do_fator(executor_pronto({}), executor_pronto({})))
    _commit(bancada.repositorio, {"fator.py": "FATOR = 1\n"}, "Fator")
    executor = _humano_depois_do_verificador(bancada, {"fator.py": "FATOR = 2\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.PENDENCIA and "M1.R1" in parada.mensagem, parada.mensagem
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_ERRADA, "o Goal com o aceite vermelho nao chega a base"
    assert git(bancada.repositorio, "show", "main:fator.py") == "FATOR = 2\n"
    conflito = _fatia_de_conflito(bancada)
    assert conflito.propriedades["conflito_com_a_base"]["motivo"] == "aceite_vermelho"
    assert conflito.propriedades["conflito_com_a_base"]["arquivos"] == ["fator.py"]
    primeira, segunda = (chamada["stdin"] for chamada in bancada.chamadas("executor")[2:])
    assert "deixou vermelho o teste de aceite test_c1_soma de C1" in primeira and "fator.py" in primeira
    assert "a area resolvida deixou vermelho o teste de aceite test_c1_soma de C1" in segunda
    assert _rebases(bancada) == [] and _verificacoes(bancada) == ["verificador"]


def test_aceite_vermelho_depois_do_rebase_limpo_no_supervisionado_para_e_a_branch_fica_edge_case(tmp_path: Path) -> None:
    """T3g2.2: no supervisionado, o aceite vermelho depois do rebase limpo para em conflito_com_a_base, com a falha."""
    bancada = montar_bancada(tmp_path, _roteiro_do_fator())
    _commit(bancada.repositorio, {"fator.py": "FATOR = 1\n"}, "Fator")
    orquestrador = ate_o_portao_aprovado(bancada)
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco()).motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR
    ponta = git(bancada.repositorio, "rev-parse", RAMO).strip()
    _commit(bancada.repositorio, {"fator.py": "FATOR = 2\n"}, "Humano muda o fator")

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.CONFLITO_COM_A_BASE, parada.mensagem
    assert "deixou vermelho o teste de aceite test_c1_soma de C1" in parada.mensagem and "C1" in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", RAMO).strip() == ponta and _rebases(bancada) == []
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_ERRADA


def _trailers_desde(bancada: Bancada, base: str) -> list[str]:
    """O `Graphow-Task` de cada commit de `base..main`, do mais novo ao mais antigo (o commit sem ele fica de fora)."""
    return git(bancada.repositorio, "log", "--format=%(trailers:key=Graphow-Task,valueonly)", f"{base}..main").split()


def test_verificacao_refeita_depois_do_rebase_roda_o_aceite_do_commit_novo_sem_a_configuracao_da_base_nominal(tmp_path: Path) -> None:
    """T3g3.3: a base muda soma.py (de C1) sem conflito e traz um conftest.py; a conferência roda o aceite do commit que o
    rebase refez, e a configuração de teste da base não aparece como mudança do Goal."""
    roteiro = _roteiro_limpo()
    roteiro["verificador"].append(verificacao("atende"))
    bancada = montar_bancada(tmp_path, roteiro)
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_COM_CABECALHO, "conftest.py": CONFTEST_DA_BASE})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert _verificacoes(bancada) == ["verificador", "conferencia"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.aceite is not None
    (rebase,) = _rebases(bancada)
    (par,) = rebase.obter_propriedade("aceites")
    antigo, novo = par["antes"], par["depois"]
    assert estado.aceite["commit"] == estado.aceite["commit_da_configuracao"] == estado.commits_do_aceite["C1"] == novo
    assert "Graphow-Task: aceite-goal-soma" in git(bancada.repositorio, "log", "-1", "--format=%B", novo)
    assert _na_historia(bancada.repositorio, novo) and not _na_historia(bancada.repositorio, antigo)
    assert estado.propriedades["aceite_antes_do_rebase"] == {antigo: novo}
    refeita = estado.verificacoes[-1]
    assert refeita.propriedades["configuracao_do_aceite"] == [], "a configuracao da base nao e troca do Goal"
    assert refeita.propriedades["aceite_com_a_configuracao_do_aceite"] == []
    assert diff_da_configuracao(bancada.repositorio, novo) == ""
    assert "conftest.py" in diff_da_configuracao(bancada.repositorio, antigo), "com o commit antigo, a base pareceria do Goal"


def test_aprovacao_do_humano_vale_para_o_aceite_que_o_rebase_refez_edge_case(tmp_path: Path) -> None:
    """Caso de borda: no supervisionado, o rebase limpo troca o commit do aceite; a aprovação do de antes segue, e o laço não volta ao portão."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = ate_o_portao_aprovado(bancada)
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco()).motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR
    _commit(bancada.repositorio, {"NOTAS.txt": "nota do humano\n"}, "Humano")

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.plano_aprovado and estado.aceite is not None
    assert _na_historia(bancada.repositorio, estado.aceite["commit"], RAMO) and len(_rebases(bancada)) == 1


def test_revisao_de_risco_da_fatia_de_conflito_ve_so_a_mudanca_dela_contra_a_base_mesclada_edge_case(tmp_path: Path) -> None:
    """T3g3.3: a 1ª tentativa da fatia de conflito desfaz a base e falha; a 2ª vai à revisão de risco, que vê só soma.py, com o
    .claude/ da base selado, e o commit da fatia vai sobre o aceite refeito."""
    errado = executor_pronto({"soma.py": SOMA_RESOLVIDA, "LICENCA.txt": "v1\n"})
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(errado, executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    _commit(bancada.repositorio, {"LICENCA.txt": "v1\n"}, "Licenca v1")
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA, "LICENCA.txt": "v2 do humano\n",
                                                       ".claude/settings.json": SETTINGS_DO_HUMANO})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    conflito = _fatia_de_conflito(bancada)
    (revisor,) = bancada.chamadas("revisor")
    mudados = revisor["stdin"].split("Arquivos mudados", 1)[1].split("##", 1)[0]
    assert "soma.py" in mudados and "LICENCA.txt" not in mudados and ".claude" not in mudados, mudados
    assert "base nova mesclada" in revisor["stdin"]
    revisao = bancada.kernel.obter_view().obter_no(f"rev-{conflito.id}-t2")
    assert revisao is not None and revisao.obter_propriedade("arquivos") == ["soma.py"]
    assert revisao.obter_propriedade("observacao") == "", "o selo nao tirou o .claude/ da base durante a revisao"
    assert git(bancada.repositorio, "show", "main:.claude/settings.json") == SETTINGS_DO_HUMANO
    (rebase,) = _rebases(bancada)
    assert _trailers_desde(bancada, rebase.obter_propriedade("base_depois")) == [conflito.id, "aceite-goal-soma"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.aceite is not None and _na_historia(bancada.repositorio, estado.aceite["commit"])
