"""T2b: o teste de aceite refeito só vale se falhar contra o código de antes da implementação.

Escrito depois de a fatia entregar, o teste refeito podia nascer verde e não
provar nada. Agora ele roda também num checkout temporário do commit anterior à
primeira fatia que cobre o critério, e tem de falhar ali numa asserção.
"""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_REFAZER_ACEITE, NovoPedido
from graphow.orquestrador.vermelho_do_refeito import PASTA_DO_CHECKOUT, checkout_de_antes

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import (
    ACEITE_C1,
    SOMA_CERTA,
    SOMA_ERRADA,
    Bancada,
    autor_de_aceite,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
# Passa com qualquer soma: escrito depois da implementação, não prova nada.
ACEITE_QUE_NASCE_VERDE: str = '"""C1: somar(2, 3) devolve 5."""\n\n\ndef test_c1_soma():\n    assert True\n\n\ntest_c1_soma()\nprint("aceite ok")\n'
# Falha com a soma errada (somar devolve 0) e passa com a certa.
ACEITE_COM_NEGATIVOS: str = ACEITE_C1.replace("assert somar(2, 3) == 5\n", "assert somar(2, 3) == 5\n    assert somar(-2, -3) == -5\n")
PASSA_ANTES: str = "passa contra o codigo de antes da implementacao"


def _refeito(conteudo: str) -> dict[str, Any]:
    """O autor de aceite que, refazendo C1, reescreve o teste com o conteúdo dado."""
    resposta = autor_de_aceite()
    resposta["saida"]["criterios"] = resposta["saida"]["criterios"][:1]
    resposta["saida"]["resumo"] = "refiz o teste de C1 com negativos"
    resposta["arquivos"] = {"aceite/aceite_c1.py": conteudo}
    return resposta


def _roteiro_com_teste_errado_em_f2(*refeitos: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """F1 entrega a soma certa; F2 diz que o teste de C1 está errado; o autor refaz; F2 entrega o README; a verificação aprova."""
    teste_errado = {"saida": {"status": "teste_errado", "resumo": "parei no teste de C1", "arquivos": [], "testes": [],
                              "duvida": "o teste de C1 nao cobre negativos", "teste_errado": "C1"}, "custo": 0.1}
    roteiro = roteiro_completo()
    roteiro["aceite"] += list(refeitos)
    roteiro["executor"] = [roteiro["executor"][0], teste_errado, roteiro["executor"][2]]
    roteiro["verificador"] = [verificacao("atende")]
    return roteiro


def _sem_checkout(bancada: Bancada) -> bool:
    """O checkout temporário do código de antes não ficou na pasta do Goal."""
    return not (bancada.raiz / "estado" / "goal-soma" / PASTA_DO_CHECKOUT).exists()


def test_refeito_que_passa_contra_o_codigo_antigo_volta_ao_autor_e_fica_o_antigo_edge_case(tmp_path: Path) -> None:
    """T2b.1: o refeito que nasce verde volta ao autor com o motivo; na segunda, fica o teste antigo e o desacordo vai à verificação."""
    bancada = montar_bancada(tmp_path, _roteiro_com_teste_errado_em_f2(_refeito(ACEITE_QUE_NASCE_VERDE), _refeito(ACEITE_QUE_NASCE_VERDE)))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    retomada = bancada.chamadas("aceite")[2]
    assert "--resume" in retomada["argv"] and PASSA_ANTES in retomada["stdin"]
    assert git(bancada.repositorio, "show", "main:aceite/aceite_c1.py") == ACEITE_C1
    assert "Mantem os testes de aceite de C1 do Goal soma" in git(bancada.repositorio, "log", "--format=%s", "main")
    assert "O autor de aceite manteve os testes de C1: O teste refeito de C1" in bancada.chamadas("executor")[2]["stdin"]
    verificador = bancada.chamadas("verificador")[0]["stdin"]
    assert "Desacordos sobre testes de aceite" in verificador and PASSA_ANTES in verificador
    assert _sem_checkout(bancada)


def test_refeito_pedido_pelo_humano_que_nasce_verde_leva_o_desacordo_a_verificacao_edge_case(tmp_path: Path) -> None:
    """T2b.1, pela CLI e antes de qualquer fatia: o código de antes é a ponta; fica o antigo, e a verificação recebe o pedido."""
    roteiro = roteiro_completo()
    roteiro["aceite"] += [_refeito(ACEITE_QUE_NASCE_VERDE), _refeito(ACEITE_QUE_NASCE_VERDE)]
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2]]
    roteiro["verificador"] = [verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    orquestrador.aprovar_plano("goal-soma", "david")
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"))

    no_portao = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    orquestrador.aprovar_plano("goal-soma", "david")
    fechado = orquestrador.rodar("goal-soma", AUTONOMO)

    assert no_portao.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, no_portao.mensagem
    assert fechado.fechou, fechado.mensagem
    assert PASSA_ANTES in bancada.chamadas("aceite")[2]["stdin"]
    assert git(bancada.repositorio, "show", "main:aceite/aceite_c1.py") == ACEITE_C1
    verificador = bancada.chamadas("verificador")[0]["stdin"]
    assert "C1: o humano pediu para refazer o teste (o teste nao cobre negativos)" in verificador
    assert _sem_checkout(bancada)


def test_refeito_que_falha_antes_e_passa_na_ponta_e_aceito_nominal(tmp_path: Path) -> None:
    """T2b.2: o refeito que falha contra a soma errada de antes de F1 e passa com a certa entra, e o Goal fecha com ele."""
    bancada = montar_bancada(tmp_path, _roteiro_com_teste_errado_em_f2(_refeito(ACEITE_COM_NEGATIVOS)))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert len(bancada.chamadas("aceite")) == 2
    assert git(bancada.repositorio, "show", "main:aceite/aceite_c1.py") == ACEITE_COM_NEGATIVOS
    assert "Refaz os testes de aceite de C1 do Goal soma" in git(bancada.repositorio, "log", "--format=%s", "main")
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.aceite is not None and estado.aceite["revisoes"] == 1
    assert "O autor de aceite refez os testes de C1" in bancada.chamadas("executor")[2]["stdin"]
    assert [(e["teste"], e["passou"]) for e in estado.verificacoes[-1].propriedades["aceite_do_orquestrador"]][0] == ("test_c1_soma", True)
    assert _sem_checkout(bancada)


def test_checkout_de_antes_sai_mesmo_quando_a_rodada_falha_edge_case(tmp_path: Path) -> None:
    """T2b.3: o checkout tem o código do commit e o aceite/ refeito; sai quando a rodada cai, e a área fica como estava."""
    area = criar_repositorio(tmp_path / "area", {"soma.py": SOMA_ERRADA, "aceite/aceite_c1.py": ACEITE_C1})
    antes = git(area, "rev-parse", "HEAD").strip()
    (area / "soma.py").write_text(SOMA_CERTA, encoding="utf-8")
    git(area, "commit", "-qam", "Fatia F1")
    (area / "aceite" / "aceite_c1.py").write_text(ACEITE_COM_NEGATIVOS, encoding="utf-8")
    destino = tmp_path / "goal" / PASTA_DO_CHECKOUT

    with pytest.raises(RuntimeError, match="a rodada caiu"), checkout_de_antes(area, destino, antes) as pasta:
        assert (pasta / "soma.py").read_text(encoding="utf-8") == SOMA_ERRADA
        assert (pasta / "aceite" / "aceite_c1.py").read_text(encoding="utf-8") == ACEITE_COM_NEGATIVOS
        raise RuntimeError("a rodada caiu")

    assert not destino.exists()
    assert git(area, "status", "--porcelain").strip() == "M aceite/aceite_c1.py"
    assert git(area, "worktree", "list").count("\n") == 1
