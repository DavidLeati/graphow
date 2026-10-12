"""As saídas do humano do Goal parado, gravadas como Decision dele: descartar o Achado, mais ciclos e cancelar.

O caso vem da sonda da revisão adversarial da fase 2 (sonda_limite.py): depois
do limite de ciclos, o humano descartava os bloqueantes e o laço não andava,
porque lia o veredito velho da verificação, e não o estado do Achado.
"""

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
    NovoPedido,
    PedidoRecusado,
)

from tests.api.test_cli_orquestrar import _executavel, _rodar
from tests.orquestrador.apoio_laco import BLOQUEANTE_DO_README, Bancada, executor_pronto, montar_bancada, roteiro_completo, verificacao

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
