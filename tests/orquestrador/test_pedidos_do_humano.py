"""As saídas do humano do Goal parado, gravadas como Decision dele: descartar o Achado, mais ciclos e cancelar.

O caso vem da sonda da revisão adversarial da fase 2 (sonda_limite.py): depois
do limite de ciclos, o humano descartava os bloqueantes e o laço não andava,
porque lia o veredito velho da verificação, e não o estado do Achado.
"""

import os
from pathlib import Path
from typing import Any

import pytest

from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import (
    PEDIDO_CANCELAR,
    PEDIDO_DESCARTAR_ACHADO,
    PEDIDO_MAIS_CICLOS,
    PEDIDO_RETIRAR_CRITERIO,
    NovoPedido,
    PedidoRecusado,
)
from graphow.orquestrador.status import formatar_status

from tests.api.test_cli_orquestrar import _executavel, _rodar
from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    ACOMPANHAMENTO,
    BLOQUEANTE_DO_README,
    Bancada,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
EM_C1: dict[str, Any] = {**BLOQUEANTE_DO_README, "titulo": "somar sem docstring", "criterios": ["C1"]}


def _parado_no_limite(tmp_path: Path, depois: list[dict[str, Any]]) -> tuple[Bancada, str]:
    """O Goal parado depois dos dois ciclos da final, com um bloqueante em C1; o roteiro segue com as verificações dadas."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [EM_C1]) for _ in range(3)] + depois
    roteiro["executor"] = [*roteiro["executor"][:2], *(executor_pronto({"soma.py": f"def somar(a, b):\n    return a + b  # {n}\n"})
                                                        for n in range(1, 4))]
    bancada = montar_bancada(tmp_path, roteiro)
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return bancada, estado.verificacoes[-1].achados[0].id


def test_achado_descartado_pelo_humano_destrava_o_goal_e_ele_fecha_nominal(tmp_path: Path) -> None:
    """Bloqueante 3: o humano descarta o bloqueante que sobrou, com o motivo; o laço lê o estado do Achado e fecha."""
    bancada, id_achado = _parado_no_limite(tmp_path, [])
    orquestrador = bancada.orquestrador()

    gravado = orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_DESCARTAR_ACHADO, "a docstring fica para depois", "david", alvo=id_achado))
    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert "pedido-goal-soma-1" in gravado
    view = bancada.kernel.obter_view()
    achado, pedido = view.obter_no(id_achado), view.obter_no("pedido-goal-soma-1")
    assert achado is not None and achado.obter_propriedade("estado") == "descartado"
    assert achado.obter_propriedade("motivo_do_descarte") == "a docstring fica para depois"
    assert pedido is not None and pedido.tipo == TipoNo.DECISION and pedido.proveniencia.papel == "humano"
    assert len(bancada.chamadas("verificador")) == 3, "o descarte nao pede verificacao nova"


def test_mais_ciclos_dados_pelo_humano_abrem_outra_correcao_nominal(tmp_path: Path) -> None:
    """Bloqueante 3: --mais-ciclos 1 dá à final mais um ciclo; a correção roda, a verificação sai limpa e o Goal fecha."""
    bancada, _ = _parado_no_limite(tmp_path, [verificacao("atende")])
    orquestrador = bancada.orquestrador()

    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_MAIS_CICLOS, "a docstring e simples", "david", ciclos=1))
    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [f.codigo for f in estado.fatias][-1] == "M1.K3.1"
    assert estado.pedidos[0].alvo == "M1" and estado.limite_de_ciclos(estado.marcos()[0]) == 3


def test_cancelar_pela_cli_pede_o_motivo_e_para_o_laco_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bloqueante 3: --cancelar sem --motivo é recusado; com ele, o Goal fica cancelado e a CLI sai com o código de parada."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    banco = ["--db", str(tmp_path / "dados" / "graphow.db"), "orquestrar"]
    assert _rodar([*banco, "--spec", str(bancada.spec), "--repo", str(bancada.repositorio)], tmp_path / "dados")[0] == 3

    sem_motivo = _rodar([*banco, "--goal", "goal-soma", "--cancelar"], tmp_path / "dados")
    cancelado = _rodar([*banco, "--goal", "goal-soma", "--cancelar", "--motivo", "o pedido mudou"], tmp_path / "dados")

    assert sem_motivo[0] == 1 and any("--motivo" in linha for linha in sem_motivo[1])
    assert cancelado[0] == 3, cancelado[1]
    assert "Parada: cancelado" in cancelado[1] and any("o pedido mudou" in linha for linha in cancelado[1])


def test_pedido_que_nao_vale_e_recusado_antes_de_gravar_edge_case(tmp_path: Path) -> None:
    """Caso de borda: descartar o que não é Achado, ciclo não positivo e o Goal já cancelado não viram Decision."""
    bancada, _ = _parado_no_limite(tmp_path, [])
    orquestrador = bancada.orquestrador()
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_CANCELAR, "desisto", "david"))

    for pedido in (NovoPedido(PEDIDO_DESCARTAR_ACHADO, "x", "david", alvo="crit-soma-c1"),
                   NovoPedido(PEDIDO_MAIS_CICLOS, "x", "david", ciclos=0)):
        with pytest.raises(PedidoRecusado):
            orquestrador.pedir("goal-soma", pedido)

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [p.acao for p in estado.pedidos] == ["cancelar"] and estado.cancelado


def test_pedido_do_humano_nao_se_edita_nem_nasce_de_outro_papel_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o kernel recusa o orquestrador gravando um pedido, e qualquer um editando o do humano."""
    bancada, _ = _parado_no_limite(tmp_path, [])
    bancada.orquestrador().pedir("goal-soma", NovoPedido(PEDIDO_MAIS_CICLOS, "um ciclo", "david", ciclos=1))

    def submeter(papel: PapelAutor, *operacoes: ItemPatch) -> bool:
        dados = DadosPropostaPatch(autor="x", papel=papel, operacoes=operacoes, justificativa="burla")
        return bancada.kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso

    editar = ItemPatch(OperacaoPatch.REPLACE, "/nos/pedido-goal-soma-1/propriedades/ciclos", 9)
    forjado = ItemPatch(OperacaoPatch.ADD, "/nos/pedido-x", {"id": "pedido-x", "tipo": "Decision", "rotulo": "x",
                                                            "propriedades": {"acao_do_humano": "mais_ciclos", "goal": "goal-soma"}})
    assert not submeter(PapelAutor.HUMANO, editar) and not submeter(PapelAutor.ORQUESTRADOR, editar)
    assert not submeter(PapelAutor.ORQUESTRADOR, forjado)
    assert not submeter(PapelAutor.HUMANO, ItemPatch(OperacaoPatch.REMOVE, "/nos/pedido-goal-soma-1"))


def test_pendencia_com_crlf_nao_derruba_o_documento_nem_as_saidas_do_humano_edge_case(tmp_path: Path) -> None:
    """Caso de borda (N2): o teste de aceite falha com a saída CRLF do Windows até a final esgotar; --mais-ciclos corrige e fecha."""
    roteiro = roteiro_completo()
    errada = {"soma.py": "def somar(a, b):\n    return 0\n", "verificar.py": "print('ok')\n"}
    roteiro["executor"] = [executor_pronto(errada), roteiro["executor"][1], *(executor_pronto({"notas.txt": f"t{n}\n"}) for n in (1, 2)),
                           executor_pronto({"soma.py": "def somar(a, b):\n    return a + b\n"})]
    roteiro["verificador"] = [verificacao("atende") for _ in range(4)]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo == MotivoDaParada.BLOQUEANTES_RESTANTES
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.pendencias
    assert os.name != "nt" or any("\r\n" in str(p.get("descricao")) for p in estado.pendencias), "a saida do runner veio em CRLF"
    documento = (tmp_path / "estado" / "goal-soma" / "area" / "docs" / "goals" / "soma.md").read_bytes()
    assert b"\r" not in documento, "o documento se grava com LF, venha a pendencia com o que vier"

    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_MAIS_CICLOS, "a soma certa esta pronta", "david", ciclos=1))
    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem


def test_achado_com_crlf_na_descricao_sincroniza_o_documento_duas_vezes_edge_case(tmp_path: Path) -> None:
    """Caso de borda (N2): o acompanhamento com CRLF vira pendência; a sincronização seguinte não regrava nem commita no vazio."""
    roteiro = roteiro_completo()
    com_crlf = {**ACOMPANHAMENTO, "descricao": "soma.py poderia ser calc.py\r\nsaida do runner:\r\nOK\r\n"}
    roteiro["verificador"] = [roteiro["verificador"][0], verificacao("atende", [com_crlf])]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    documento = git(bancada.repositorio, "show", "main:docs/goals/soma.md")
    assert "soma.py poderia ser calc.py\nsaida do runner:\nOK" in documento and "\r" not in documento


def _c1_sempre_vermelho(tmp_path: Path) -> tuple[Bancada, list[str]]:
    """A soma fica errada em toda tentativa: o teste de aceite de C1 reprova C1 até a final esgotar (sonda_descarte)."""
    roteiro = roteiro_completo()
    errada = {"soma.py": "def somar(a, b):\n    return 0\n", "verificar.py": "print('ok')\n"}
    roteiro["executor"] = [executor_pronto(errada), roteiro["executor"][1], *(executor_pronto({"notas.txt": f"t{n}\n"}) for n in range(1, 4))]
    roteiro["verificador"] = [verificacao("atende") for _ in range(4)]
    bancada = montar_bancada(tmp_path, roteiro)
    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo == MotivoDaParada.BLOQUEANTES_RESTANTES
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return bancada, [a.id for v in estado.verificacoes for a in v.bloqueantes_abertos()]


def test_descartar_achado_nao_fecha_o_goal_com_criterio_reprovado_edge_case(tmp_path: Path) -> None:
    """Caso de borda (ajuste 4, sonda_descarte): descartados todos os Achados, C1 segue nao_atende, e o laço para dizendo como sair."""
    bancada, abertos = _c1_sempre_vermelho(tmp_path)
    orquestrador = bancada.orquestrador()
    for id_achado in abertos:
        orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_DESCARTAR_ACHADO, "aceito o risco", "david", alvo=id_achado))

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    assert "o descarte nao aprova criterio" in parada.mensagem and "--retirar-criterio" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and not estado.fechado and estado.verificacoes[-1].reprovados == ("C1",)


def test_retirar_o_criterio_reprovado_fecha_o_goal_e_aparece_no_status_e_no_documento_nominal(tmp_path: Path) -> None:
    """Ajuste 4: --retirar-criterio C1 é Decision do humano; os Achados de C1 se descartam com ele, e o Goal fecha sem C1."""
    bancada, _ = _c1_sempre_vermelho(tmp_path)
    orquestrador = bancada.orquestrador()

    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RETIRAR_CRITERIO, "a soma fica para o proximo Goal", "david", alvo="C1"))
    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    view = bancada.kernel.obter_view()
    assert view.obter_no("crit-soma-c1").obter_propriedade("retirado")["decisao"] == "pedido-goal-soma-1"
    estado = ler_estado(view, "goal-soma")
    assert estado is not None
    assert any("C1 retirado pelo humano (a soma fica para o proximo Goal)" in linha for linha in formatar_status(estado, []))
    documento = git(bancada.repositorio, "show", "main:docs/goals/soma.md")
    assert "## Criterios retirados pelo humano" in documento and "**C1**, retirado por david" in documento


def test_ciclos_de_correcao_dados_na_chamada_valem_para_o_goal_edge_case(tmp_path: Path) -> None:
    """Caso de borda: com --ciclos-de-correcao 0, o bloqueante da final para o laço sem correção; o descarte fecha."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [EM_C1])]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()

    parada = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", ciclos_de_correcao=0))

    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.configuracao is not None and estado.configuracao.ciclos_de_correcao == 0
    assert not [f for f in estado.fatias if f.texto("corrige_verificacao")]
    id_achado = estado.verificacoes[-1].achados[0].id
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_DESCARTAR_ACHADO, "a docstring fica para depois", "david", alvo=id_achado))
    assert orquestrador.rodar("goal-soma", AUTONOMO).fechou


def test_parada_com_criterio_reprovado_avisa_que_o_descarte_nao_fecha_edge_case(tmp_path: Path) -> None:
    """Caso de borda (fumaça da rodada 3): a final sem ciclo, com C2 reprovado, já indica a retirada, e não só o descarte."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("nao_atende", [EM_C1])]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", ciclos_de_correcao=0))

    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    assert "A verificacao ver-goal-soma-1 reprova C2:" in parada.mensagem, parada.mensagem
    assert "descartar os achados nao fecha o Goal" in parada.mensagem
    assert "--retirar-criterio <criterio>" in parada.mensagem
