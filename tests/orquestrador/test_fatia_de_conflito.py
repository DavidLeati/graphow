"""A fatia de conflito (revisão da T3g): a base nova mesclada é a referência, e nada a desfaz."""

from pathlib import Path

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import FatiaRegistrada, ler_estado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    Bancada,
    executor_pronto,
    montar_bancada,
    verificacao,
)
from tests.orquestrador.test_base_que_andou import (
    SOMA_DA_BASE_QUE_CONFLITA,
    SOMA_RESOLVIDA,
    ExecutorQueAndaABase,
    _roteiro_limpo,
    _verificacoes,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SETTINGS_DO_HUMANO: str = '{"permissions": {"allow": []}}\n'
INSTRUCOES_DO_HUMANO: str = "# Instrucoes do humano\nResponda em portugues.\n"
CONFTEST_DO_HUMANO: str = "def pytest_pyfunc_call(pyfuncitem):\n    return None\n"


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
