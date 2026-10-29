"""A diferença entre o aceite com a configuração entregue e com a do commit do aceite: o código decide o que pode, o verificador julga o resto.

Os casos vêm da revisão da T2a (notas/sonda_revisao_T2a.py). Um conftest com
`pytest_pyfunc_call` que devolve True, com `somar` devolvendo 0, fechava o
Goal: a diferença ia ao verificador, e o verificador falso dizia `atende`.
Agora o teste que só passa com a configuração entregue e, com a do aceite,
falha numa asserção reprova o critério sem o verificador; o que falha por
import (o layout `src/` legítimo, com `soma.py` fora da raiz) vai a ele, que
deve um parecer. Os cenários do layout legítimo e da neutralização são
distintos: no legítimo a soma da raiz sai, na neutralização ela fica errada.
"""

import copy
from pathlib import Path
import sys
from typing import Any

import pytest

from graphow.orquestrador import configuracao_do_aceite as cda
from graphow.orquestrador.aceite_no_commit import AceiteNoCommit
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.gravacao_do_aceite import commit_da_configuracao
from graphow.orquestrador.leitura_do_goal import VerificacaoRegistrada, ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_RETIRAR_CRITERIO, NovoPedido
from graphow.orquestrador.saida_do_aceite import ExecucaoDeAceite
from graphow.orquestrador.saida_do_verificador import ParecerDaDiferenca, Verificacao, conferir_verificacao

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    SOMA_CERTA,
    SOMA_ERRADA,
    Bancada,
    Queda,
    aceite_em_pytest,
    executor_pronto,
    montar_bancada,
    verificacao,
)
from tests.orquestrador.test_aceite_intocado import AUTONOMO, FATIA_CERTA, _roteiro
from tests.orquestrador.test_retomada import cai_uma_vez

# O aceite que importa `soma` pelo caminho que o pytest monta (sem pôr a raiz na frente), como na sonda_isol. Com o
# `-P` do aceite a raiz não entra sozinha: o teste a põe no fim do caminho, e o `pythonpath` do pytest vem antes dela.
ACEITE_PELO_CAMINHO_DO_PYTEST: str = (
    '"""C1: somar(2, 3) devolve 5."""\nimport sys\n\nsys.path.append(".")\n\n\n'
    "def test_c1_soma():\n    from soma import somar\n    assert somar(2, 3) == 5\n"
)
PYTHONPATH_SRC: str = '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
VERIFICAR_EM_SRC: str = "import sys\nsys.path.insert(0, 'src')\nfrom soma import somar\nassert somar(2, 3) == 5\nprint('ok')\n"
# O layout `src/` legítimo: a soma muda para src/, e a da raiz sai (com a configuração do aceite, ModuleNotFoundError).
LAYOUT_SRC: dict[str, Any] = executor_pronto({"src/soma.py": SOMA_CERTA, "pyproject.toml": PYTHONPATH_SRC, "verificar.py": VERIFICAR_EM_SRC},
                                             comandos=[[sys.executable, "-c", "import os; os.remove('soma.py')"]])
FINGE_QUE_PASSA: str = "import pytest\n\n\n@pytest.hookimpl(tryfirst=True)\ndef pytest_pyfunc_call(pyfuncitem):\n    return True\n"
# A neutralização pelo caminho: o pythonpath troca o módulo que o aceite importa, e a soma errada fica na raiz.
TROCA_O_MODULO: dict[str, str] = {"soma.py": SOMA_ERRADA, "src/soma.py": SOMA_CERTA, "pyproject.toml": PYTHONPATH_SRC,
                                  "verificar.py": VERIFICAR_EM_SRC}
MOTIVOS: dict[str, str] = {"legitima": "soma.py so mudou para src/, e o teste importa a mesma funcao",
                           "ilegitima": "o pythonpath novo troca o modulo que o teste de C1 importa"}


def _verificacao_com_parecer(parecer: str) -> dict[str, Any]:
    """A verificação limpa, com o parecer dado sobre a diferença de test_c1_soma, e sem achado."""
    resposta = verificacao("atende")
    resposta["saida"]["diferencas"] = [{"criterio": "C1", "teste": "test_c1_soma", "parecer": parecer, "motivo": MOTIVOS[parecer]}]
    return resposta


def _bancada_do_layout(tmp_path: Path, verificador: list[dict[str, Any]]) -> Bancada:
    """A fatia F1 no layout `src/` legítimo, o aceite pelo caminho do pytest e o verificador dado."""
    roteiro = _roteiro(copy.deepcopy(LAYOUT_SRC))
    roteiro["aceite"] = [aceite_em_pytest(ACEITE_PELO_CAMINHO_DO_PYTEST)]
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2], executor_pronto({"notas.txt": "x\n"})]
    roteiro["verificador"] = verificador
    return montar_bancada(tmp_path, roteiro)


def _verificacoes(bancada: Bancada) -> tuple[VerificacaoRegistrada, ...]:
    """As verificações do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado.verificacoes


@pytest.mark.parametrize("arquivos", [{"soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n", "conftest.py": FINGE_QUE_PASSA},
                                      TROCA_O_MODULO], ids=["conftest-finge-que-passa", "pythonpath-troca-o-modulo"])
def test_configuracao_que_esconde_a_falha_reprova_sem_o_verificador_edge_case(tmp_path: Path, arquivos: dict[str, str]) -> None:
    """T2a2.1: com a soma errada, o teste passa só com a configuração entregue; com a do aceite, falha na asserção.

    O verificador falso diz `atende` e não traz achado: C1 fica `nao_atende`
    pelo código, com o Achado bloqueante que leva as duas saídas, e o Goal só
    fecha depois da correção, com a soma certa.
    """
    roteiro = _roteiro(executor_pronto(arquivos))
    roteiro["aceite"] = [aceite_em_pytest(ACEITE_PELO_CAMINHO_DO_PYTEST)]
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2], executor_pronto(FATIA_CERTA)]
    roteiro["verificador"] = [verificacao("atende"), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    primeira = _verificacoes(bancada)[0]
    assert {p["id"]: p["veredito"] for p in primeira.propriedades["pareceres"]}["C1"] == "nao_atende"
    titulo = "A configuracao entregue esconde a falha do teste de aceite test_c1_soma de C1"
    achado = next(a for a in primeira.achados if a.texto("titulo") == titulo)
    assert achado.gravidade == "bloqueante"
    assert "1 passed" in achado.texto("descricao") and "assert 0 == 5" in achado.texto("descricao")
    assert [d["destino"] for d in primeira.propriedades["diferencas_de_configuracao"]][0] == "achado_automatico"
    assert "um parecer por diferenca" not in bancada.chamadas("verificador")[0]["stdin"]
    assert parada.fechou, parada.mensagem
    assert (bancada.repositorio / "soma.py").read_text(encoding="utf-8") == SOMA_CERTA


def test_layout_src_legitimo_fecha_com_o_parecer_legitima_nominal(tmp_path: Path) -> None:
    """T2a2.2: a soma que muda para src/ falha por import com a configuração do aceite; o verificador a julga legítima, e o Goal fecha."""
    bancada = _bancada_do_layout(tmp_path, [_verificacao_com_parecer("legitima")])

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    final = _verificacoes(bancada)[-1].propriedades
    assert {(e["teste"], e["passou"]) for e in final["aceite_do_orquestrador"]} >= {("test_c1_soma", True)}
    assert final["configuracao_do_aceite"] == ["pyproject.toml"]
    diferenca = next(d for d in final["diferencas_de_configuracao"] if d["teste"] == "test_c1_soma")
    assert (diferenca["destino"], diferenca["parecer"], diferenca["com_a_do_aceite"]) == ("verificador", "legitima", False)
    briefing = bancada.chamadas("verificador")[0]["stdin"]
    assert 'criterio "C1", teste "test_c1_soma"' in briefing and "ModuleNotFoundError" in briefing
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and f"commit do aceite {commit_da_configuracao(estado.aceite)} (pyproject.toml)" in briefing
    assert final["achados"] == []


def test_parecer_ilegitima_vira_bloqueante_pela_diferenca_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o verificador não traz achado nenhum; o bloqueante nasce do parecer `ilegitima` sobre a diferença, com as duas saídas."""
    bancada = _bancada_do_layout(tmp_path, [_verificacao_com_parecer("ilegitima"), _verificacao_com_parecer("legitima")])

    bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    primeira = _verificacoes(bancada)[0]
    titulo = "A configuracao entregue muda o que o teste de aceite test_c1_soma de C1 prova"
    assert [(a.texto("titulo"), a.gravidade) for a in primeira.achados] == [(titulo, "bloqueante")]
    descricao = primeira.achados[0].texto("descricao")
    assert MOTIVOS["ilegitima"] in descricao and "ModuleNotFoundError" in descricao
    assert next(d for d in primeira.propriedades["diferencas_de_configuracao"])["parecer"] == "ilegitima"


def test_diferenca_sem_parecer_e_saida_invalida_e_volta_ao_verificador_edge_case(tmp_path: Path) -> None:
    """T2a2.3: a verificação sem o parecer da diferença não confere; a retomada de sempre o pede, e a segunda vale."""
    bancada = _bancada_do_layout(tmp_path, [verificacao("atende"), _verificacao_com_parecer("legitima")])

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    chamadas = bancada.chamadas("verificador")
    assert len(chamadas) == 2 and "--resume" in chamadas[1]["argv"]
    assert "falta o parecer da diferenca de configuracao do teste test_c1_soma de C1" in chamadas[1]["stdin"]
    assert _verificacoes(bancada)[0].propriedades["diferencas_de_configuracao"][0]["parecer"] == "legitima"


def _execucao(teste: str, codigo: int, saida: str, criterio: str = "C1") -> ExecucaoDeAceite:
    """Uma execução de aceite em pytest."""
    return ExecucaoDeAceite(criterio, teste, f"python -P -m pytest aceite/a.py::{teste}", codigo, saida)


PASSOU: str = "1 passed in 0.01s\n"
SEM_MODULO: str = ("    def test_a():\n>       from soma import somar\nE   ModuleNotFoundError: No module named 'soma'\n\n"
                   "aceite/a.py:2: ModuleNotFoundError\nFAILED aceite/a.py::test_a - ModuleNotFoundError: No module\n1 failed in 0.01s\n")


def test_conferencia_pede_um_parecer_por_diferenca_sem_repetir_nem_inventar_edge_case() -> None:
    """T2a2.3: falta, repetição e parecer de diferença que o pedido não trouxe são problemas da saída."""
    base = Verificacao("ok", ())
    pedidas = (("C1", "test_a"),)
    legitima = ParecerDaDiferenca("C1", "test_a", "legitima", "o modulo so mudou de lugar")
    inventada = ParecerDaDiferenca("C1", "test_b", "legitima", "o modulo so mudou de lugar")

    assert conferir_verificacao(base, (), (), diferencas=pedidas) == ("falta o parecer da diferenca de configuracao do teste test_a de C1",)
    assert conferir_verificacao(Verificacao("ok", (), diferencas=(legitima,)), (), (), diferencas=pedidas) == ()
    assert conferir_verificacao(Verificacao("ok", (), diferencas=(legitima, legitima)), (), (), diferencas=pedidas) == (
        "parecer da diferenca do teste test_a de C1 repetido",)
    assert conferir_verificacao(Verificacao("ok", (), diferencas=(legitima, inventada)), (), (), diferencas=pedidas) == (
        "o parecer da diferenca do teste test_b de C1 nao corresponde a nenhuma diferenca do pedido",)


def test_comando_de_todos_so_conta_sem_diferenca_de_teste_sozinho_edge_case() -> None:
    """Caso de borda: a diferença do comando de todos repete a do teste sozinho e não pede outro parecer; sozinha, pede."""
    teste = (_execucao("test_a", 0, PASSOU), _execucao("test_a", 1, SEM_MODULO))
    todos = (_execucao("comando_aceite", 0, PASSOU, ""), _execucao("comando_aceite", 1, SEM_MODULO, ""))
    juntos = AceiteNoCommit((teste[0], todos[0]), (teste[1], todos[1]), ("pyproject.toml",), "abc")
    so_todos = AceiteNoCommit((_execucao("test_a", 0, PASSOU), todos[0]), (_execucao("test_a", 0, PASSOU), todos[1]),
                              ("pyproject.toml",), "abc")

    assert juntos.chaves_a_julgar() == (("C1", "test_a"),) and juntos.escondidas() == ()
    assert so_todos.chaves_a_julgar() == (("", "comando_aceite"),)


def test_queda_na_segunda_rodada_retoma_com_a_configuracao_entregue_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T2a2.4: o processo cai com a área na configuração do aceite; a retomada a volta à entregue e roda o aceite com ela.

    A volta é no começo da retomada (T2g), pela marca da troca: quando a
    verificação descarta o que está fora de commit, já não há nada a guardar.
    """
    bancada = _bancada_do_layout(tmp_path, [_verificacao_com_parecer("legitima") for _ in range(2)])
    monkeypatch.setattr(cda, "_voltar_a_ponta", cai_uma_vez(cda._voltar_a_ponta))

    with pytest.raises(Queda):
        bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    assert all(arquivo.read_text(encoding="utf-8") != PYTHONPATH_SRC for arquivo in (bancada.raiz / "estado").rglob("pyproject.toml"))
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    primeira = _verificacoes(bancada)[0].propriedades
    assert [(e["teste"], e["passou"]) for e in primeira["aceite_do_orquestrador"]][0] == ("test_c1_soma", True)
    assert {p["id"]: p["veredito"] for p in primeira["pareceres"]}["C1"] == "atende"
    assert not list((bancada.raiz / "estado").rglob("antes-da-verificacao-1.patch"))
    assert not list((bancada.raiz / "estado").rglob(cda.MARCA_DA_TROCA))


def test_queda_na_segunda_rodada_e_pedido_antes_da_retomada_mantem_a_configuracao_entregue_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T2g.1 (sonda 2 da revisão da T2b+T2a2): o processo cai com a área na configuração do aceite, e o humano retira C2.

    A retomada volta a configuração à entregue antes do primeiro passo: o
    commit da retirada leva só o documento do Goal, e o `pythonpath` entregue
    segue na branch do Goal até o fechamento.
    """
    bancada = _bancada_do_layout(tmp_path, [_verificacao_com_parecer("legitima") for _ in range(3)])
    monkeypatch.setattr(cda, "_voltar_a_ponta", cai_uma_vez(cda._voltar_a_ponta))
    orquestrador = bancada.orquestrador()
    with pytest.raises(Queda):
        orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    assert len(list((bancada.raiz / "estado").rglob(cda.MARCA_DA_TROCA))) == 1
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RETIRAR_CRITERIO, "C2 fica para outro Goal", "david", alvo="C2"))

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco(modo="autonomo"))

    assert parada.fechou, parada.mensagem
    commits = dict(linha.split(" ", 1) for linha in git(bancada.repositorio, "log", "--format=%H %s", "main").splitlines())
    retirada = next(h for h, assunto in commits.items() if assunto.startswith("Registra os criterios retirados"))
    assert git(bancada.repositorio, "show", "--name-only", "--format=", retirada).split() == ["docs/goals/soma.md"]
    assert git(bancada.repositorio, "show", "main:pyproject.toml") == PYTHONPATH_SRC
    assert not list((bancada.raiz / "estado").rglob(cda.MARCA_DA_TROCA))
