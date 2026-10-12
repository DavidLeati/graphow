"""A retomada do laço em cada ponto em que o processo pode cair, e as falhas de domínio como parada.

Nenhum caminho paga o planejador de novo quando o plano já está no livro-razão
ou no stream da sessão, e nenhuma falha de domínio escapa como exceção.
"""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador import planejamento
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    Bancada,
    Queda,
    executor_pronto,
    montar_bancada,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TUDO: dict[str, str] = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR, "README.md": "# brinquedo\nUse somar(2, 3).\n"}


def roteiro_farto(vezes: int = 6) -> dict[str, list[dict[str, Any]]]:
    """Respostas de sobra para cada papel: o teste conta quantas foram usadas."""
    return {
        "planejador": [{"saida": copy.deepcopy(PLANO), "custo": 0.4} for _ in range(vezes)],
        "executor": [executor_pronto(dict(TUDO)) for _ in range(vezes)],
        "verificador": [verificacao("atende") for _ in range(vezes)],
    }


def cai_uma_vez(original: Callable[..., Any]) -> Callable[..., Any]:
    """A função que derruba o processo na primeira chamada e funciona nas seguintes."""
    estado = {"caiu": False}

    def envolta(*argumentos: Any, **nomeados: Any) -> Any:
        if not estado["caiu"]:
            estado["caiu"] = True
            raise Queda()
        return original(*argumentos, **nomeados)

    return envolta


def _rodar_com_queda(bancada: Bancada) -> MotivoDaParada:
    """Uma chamada que cai e uma que retoma; devolve onde a retomada parou."""
    with pytest.raises(Queda):
        bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    return bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo


def test_queda_entre_o_commit_do_plano_e_a_gravacao_reaproveita_o_plano_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O documento já commitado vale, o plano proposto vale, e o planejador roda uma vez só."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    monkeypatch.setattr(planejamento, "gravar_plano", cai_uma_vez(planejamento.gravar_plano))

    motivo = _rodar_com_queda(bancada)

    assert motivo == MotivoDaParada.FECHADO
    assert len(bancada.chamadas("planejador")) == 1
    assert git(bancada.repositorio, "log", "--format=%s", "main").count("Planeja o Goal soma") == 1


def test_queda_logo_depois_da_sessao_do_planejador_rele_o_stream_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caiu antes de gravar o plano proposto: a saída é relida do stream da sessão paga."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    monkeypatch.setattr(LivroRazaoDoGoal, "gravar_plano_proposto", cai_uma_vez(LivroRazaoDoGoal.gravar_plano_proposto))

    motivo = _rodar_com_queda(bancada)

    assert motivo == MotivoDaParada.FECHADO
    assert len(bancada.chamadas("planejador")) == 1


def test_mesma_spec_depois_do_goal_fechado_abre_outro_goal_com_o_proprio_slug_nominal(tmp_path: Path) -> None:
    """O segundo Goal da mesma spec tem slug, fatias e branch próprios e fecha também."""
    bancada = montar_bancada(tmp_path, roteiro_farto(12))
    primeira = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    segunda = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert primeira.fechou and segunda.fechou, segunda.mensagem
    assert segunda.id_goal == "goal-soma-2"
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma-2")
    assert estado is not None and estado.configuracao is not None
    assert (estado.configuracao.slug, estado.configuracao.ramo) == ("soma-2", "graphow/soma-2")
    assert [fatia.id for fatia in estado.fatias] == ["task-soma-2-f1", "task-soma-2-f2"]


def test_branch_do_goal_igual_a_base_e_parada_legivel_edge_case(tmp_path: Path) -> None:
    """Caso de borda: `--ramo main` com a base main não chega ao git; vira parada com o motivo."""
    bancada = montar_bancada(tmp_path, roteiro_farto())

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", ramo="main"))

    assert parada.motivo == MotivoDaParada.FALHA
    assert "nao pode ser a propria base" in parada.mensagem
    assert bancada.chamadas() == []


def test_falha_do_git_vira_parada_e_nao_excecao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o repositório some depois de o Goal nascer; a chamada seguinte para com a falha do git."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.configuracao is not None
    git(bancada.repositorio, "worktree", "remove", "--force", estado.configuracao.area)
    git(bancada.repositorio, "branch", "-m", "graphow/soma", "outra")
    git(bancada.repositorio, "checkout", "-q", "outra")
    git(bancada.repositorio, "branch", "-D", "main")

    parada = bancada.orquestrador().rodar("goal-soma", AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert "FalhaDoGitDoGoal" in parada.mensagem


def test_duas_duvidas_respondidas_nao_gastam_as_tentativas_nominal(tmp_path: Path) -> None:
    """A fatia pergunta duas vezes, o humano responde as duas, e ela ainda roda e fecha: dúvida não é falha."""
    from graphow.core.types import PapelAutor
    from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch

    roteiro = roteiro_farto()
    duvida = {"saida": {"status": "duvida", "resumo": "parei", "arquivos": [], "testes": [], "duvida": "Inteiros?"}, "custo": 0.1}
    roteiro["executor"] = [copy.deepcopy(duvida), copy.deepcopy(duvida), *roteiro["executor"]]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()

    def responder() -> None:
        estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
        assert estado is not None and estado.fatias[0].duvida_aberta is not None
        id_questao = estado.fatias[0].duvida_aberta.id
        resposta = PropostaPatch.criar(DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, justificativa="r", operacoes=(
            ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/status", "respondida"),
            ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/resposta", "sim"))))
        assert bancada.kernel.submeter_patch(resposta).sucesso

    primeira = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    responder()
    segunda = orquestrador.rodar("goal-soma", AUTONOMO)
    responder()
    terceira = orquestrador.rodar("goal-soma", AUTONOMO)

    assert (primeira.motivo, segunda.motivo) == (MotivoDaParada.AGUARDANDO_RESPOSTA, MotivoDaParada.AGUARDANDO_RESPOSTA)
    assert terceira.fechou, terceira.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and (estado.fatias[0].tentativas, estado.fatias[0].falhas) == (3, 0)
