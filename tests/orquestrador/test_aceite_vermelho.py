"""O trailer `Graphow-Aceite: vermelho`: o commit do laço que pode deixar a suíte vermelha o leva, e a fatia não.

Só a fatia muda o código, e ela só é commitada com a suíte verde. O que vem
antes da primeira fatia (o plano, os testes de aceite, a recusa, a retirada)
tem o código da base, que pode não ter suíte; os testes de aceite, inclusive
os refeitos, são vermelhos por definição. A medida `historico` da bancada
conta o vermelho com o trailer como esperado.
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.git_do_goal import ACEITE_VERMELHO, TRAILER_DO_ACEITE
from graphow.orquestrador.pedidos_do_humano import PEDIDO_RECUSAR_PLANO, PEDIDO_REFAZER_ACEITE, PEDIDO_RETIRAR_CRITERIO, NovoPedido

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    ACEITE_C1,
    PLANO,
    ExecutorQueCai,
    Queda,
    autor_de_aceite,
    montar_bancada,
    roteiro_completo,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SEPARADOR: str = "\x1f"
CONFTEST_DO_PROJETO: str = "# escrito pelo codigo do projeto que o planejador rodou\n"


def _trailers(repositorio: Path, ramo: str = "main") -> list[tuple[str, str]]:
    """O assunto e o valor de `Graphow-Aceite` de cada commit da branch depois do inicial, do mais antigo ao mais novo."""
    formato = f"%s{SEPARADOR}%(trailers:key={TRAILER_DO_ACEITE},valueonly,separator=)"
    linhas = git(repositorio, "log", "--reverse", "-z", f"--format={formato}", ramo)
    pares = [registro.split(SEPARADOR, 1) for registro in linhas.split("\x00") if registro.strip()]
    return [(assunto.strip(), valor.strip()) for assunto, valor in pares][1:]


def test_commit_do_aceite_leva_o_trailer_e_o_da_fatia_nao_nominal(tmp_path: Path) -> None:
    """T3e.1: no Goal que fecha, o plano e os testes de aceite saem marcados; as fatias e as pendências, não."""
    bancada = montar_bancada(tmp_path, roteiro_completo())

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    trailers = _trailers(bancada.repositorio)
    marcados = [assunto for assunto, valor in trailers if valor == ACEITE_VERMELHO]
    assert marcados == ["Planeja o Goal soma: Soma de dois numeros", "Escreve os testes de aceite do Goal soma (C1, C2)"]
    fatias = [(assunto, valor) for assunto, valor in trailers if assunto.startswith("Fatia ")]
    assert len(fatias) == 3 and all(valor == "" for _, valor in fatias)
    assert any(assunto.startswith("Registra as pendencias") for assunto, _ in trailers)


def _refeito() -> dict[str, Any]:
    """O autor de aceite que refaz só C1."""
    refeito = autor_de_aceite()
    refeito["saida"]["criterios"] = refeito["saida"]["criterios"][:1]
    refeito["arquivos"] = {"aceite/aceite_c1.py": ACEITE_C1 + "# refeito\n"}
    return refeito


def _plano_so_c1() -> tuple[dict[str, Any], dict[str, Any]]:
    """O plano que o planejador refaz depois da recusa, só com C1, e o aceite dele."""
    plano = copy.deepcopy(PLANO)
    plano["criterios"], plano["fatias"] = plano["criterios"][:1], plano["fatias"][:1]
    plano["marcos"] = [{"id": "M1", "titulo": "Soma", "fatias": ["F1"]}]
    aceite = autor_de_aceite()
    aceite["saida"]["criterios"] = aceite["saida"]["criterios"][:1]
    return plano, aceite


def test_refeito_retirada_e_recusa_antes_de_fatia_levam_o_trailer_nominal(tmp_path: Path) -> None:
    """Antes de qualquer fatia, todo commit do laço tem o código da base: o refazer, a retirada e a recusa saem marcados."""
    plano, aceite = _plano_so_c1()
    roteiro = roteiro_completo()
    roteiro["aceite"] += [_refeito(), aceite]
    roteiro["planejador"].append({"saida": plano, "custo": 0.4})
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco()).motivo == MotivoDaParada.AGUARDANDO_APROVACAO

    for pedido in (NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"),
                   NovoPedido(PEDIDO_RETIRAR_CRITERIO, "C2 fica para outro Goal", "david", alvo="C2"),
                   NovoPedido(PEDIDO_RECUSAR_PLANO, "so a funcao", "david")):
        orquestrador.pedir("goal-soma", pedido)
        parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())
        assert parada.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, parada.mensagem

    trailers = _trailers(bancada.repositorio, "graphow/soma")
    assuntos = [assunto for assunto, _ in trailers]
    assert any(a.startswith("Refaz os testes de aceite de C1") for a in assuntos)
    assert any(a.startswith("Registra os criterios retirados") for a in assuntos)
    assert any(a.startswith("Retira os testes de aceite do plano recusado") for a in assuntos)
    assert len(trailers) == 7 and all(valor == ACEITE_VERMELHO for _, valor in trailers), trailers


def test_plano_pago_retomado_commita_so_o_documento_edge_case(tmp_path: Path) -> None:
    """Caso de borda (T2n, item 3): a sessão do planejador cai e deixa um conftest.py; a retomada relê o plano e não o commita."""
    roteiro = roteiro_completo()
    roteiro["planejador"][0]["arquivos"] = {"conftest.py": CONFTEST_DO_PROJETO}
    bancada = montar_bancada(tmp_path, roteiro)
    with pytest.raises(Queda):
        bancada.orquestrador(executor=ExecutorQueCai(bancada.executor, 1)).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert len(bancada.chamadas("planejador")) == 1
    plano = git(bancada.repositorio, "log", "--format=%H", "--grep=^Planeja o Goal soma", "main").split()
    assert len(plano) == 1
    assert git(bancada.repositorio, "show", "--name-only", "--format=", plano[0]).split() == ["docs/goals/soma.md"]
    assert "conftest.py" not in git(bancada.repositorio, "log", "--name-only", "--format=", "main").split()
