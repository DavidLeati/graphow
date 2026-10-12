"""O modo autônomo não para em dúvida: o executor decide e registra, e o teste de aceite errado se refaz sozinho, uma vez.

Na bancada, o executor do api-tarefas abriu uma dúvida sobre o teste de aceite
de C13, e o Goal parou em `aguardando_resposta` no modo autônomo, onde ninguém
responde.
"""

from pathlib import Path
from typing import Any

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.status import formatar_status

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    SOMA_CERTA,
    VERIFICAR,
    ate_o_portao_aprovado,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
ARGUMENTO: str = "o teste herda NODE_TEST_CONTEXT e pula tudo quando roda dentro de outro node --test"


def _teste_errado(**campos: Any) -> dict[str, Any]:
    """A saída do executor do modo autônomo que diz que o teste de aceite de C1 está errado."""
    saida = {"status": "teste_errado", "resumo": "parei no teste de C1", "arquivos": [], "testes": [], "duvida": ARGUMENTO,
             "teste_errado": "C1"}
    return {"saida": saida, "custo": 0.1, **campos}


def _mantido() -> dict[str, Any]:
    """O autor de aceite que, refazendo C1, mantém o teste como estava e diz por quê."""
    resposta = autor_de_aceite()
    resposta["saida"]["criterios"] = resposta["saida"]["criterios"][:1]
    resposta["saida"]["resumo"] = "o teste esta certo: ele roda direto, sem node --test por fora"
    return resposta


def test_teste_errado_no_autonomo_refaz_o_aceite_uma_vez_e_a_fatia_segue_nominal(tmp_path: Path) -> None:
    """E: o executor aponta o teste de C1; o laço pede o refazer, o autor mantém com o porquê, e o executor segue e fecha."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(0, _teste_errado())
    roteiro["aceite"].append(_mantido())
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert [c["papel"] for c in bancada.chamadas()][:5] == ["planejador", "aceite", "executor", "aceite", "executor"]
    assert ARGUMENTO in bancada.chamadas("aceite")[1]["stdin"] and "mantenha-o" in bancada.chamadas("aceite")[1]["stdin"]
    retomada = bancada.chamadas("executor")[1]["stdin"]
    assert "O autor de aceite manteve os testes de C1: o teste esta certo" in retomada
    assert "Desacordos sobre testes de aceite" in bancada.chamadas("verificador")[0]["stdin"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].falhas == 0 and estado.propriedades["criterios_refeitos_pelo_agente"] == ["C1"]


def test_segundo_teste_errado_do_mesmo_criterio_nao_refaz_de_novo_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o refazer do agente é uma vez por critério; o segundo `teste_errado` segue como entregue, com o desacordo."""
    roteiro = roteiro_completo()
    insiste = _teste_errado()
    insiste["saida"]["arquivos"] = ["soma.py", "verificar.py"]
    insiste["arquivos"] = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}
    roteiro["executor"][0:1] = [_teste_errado(), insiste]
    roteiro["aceite"].append(_mantido())
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert len(bancada.chamadas("aceite")) == 2
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].propriedades["desacordo_sobre_o_teste"]["criterio"] == "C1"
    assert "insistiu" in bancada.chamadas("verificador")[0]["stdin"]


def test_executor_do_autonomo_decide_e_a_decisao_fica_para_o_humano_revisar_nominal(tmp_path: Path) -> None:
    """E: a incerteza vira decisão do agente: Decision que orienta a fatia, no status e no documento do Goal."""
    roteiro = roteiro_completo()
    decidida = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR})
    decidida["saida"]["decisoes"] = [{"questao": "inteiros ou decimais?", "decisao": "so inteiros", "motivo": "a spec diz so inteiros"}]
    roteiro["executor"][0] = decidida
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert '"enum":["pronto","teste_errado","falhou"]' in " ".join(bancada.chamadas("executor")[0]["argv"])
    view = bancada.kernel.obter_view()
    decisao = view.obter_no("dec-agente-task-soma-f1-t1-1")
    assert decisao is not None and decisao.tipo == TipoNo.DECISION and decisao.obter_propriedade("decidida_pelo_agente") is True
    assert [a.destino_id for a in view.obter_arestas_saida(decisao.id, TipoAresta.ORIENTA)] == ["task-soma-f1"]
    estado = ler_estado(view, "goal-soma")
    assert estado is not None
    assert any("inteiros ou decimais? -> so inteiros" in linha for linha in formatar_status(estado, []))
    documento = git(bancada.repositorio, "show", "main:docs/goals/soma.md")
    assert "## Decisoes do agente (para o humano revisar)" in documento and "(F1) inteiros ou decimais? -> so inteiros" in documento


def test_resposta_manter_a_duvida_do_teste_nao_refaz_o_aceite_edge_case(tmp_path: Path) -> None:
    """Caso de borda (ajuste 7): no supervisionado, a resposta `manter` à dúvida do teste errado não refaz nada."""
    roteiro = roteiro_completo()
    duvida = {"saida": {"status": "duvida", "resumo": "parei", "arquivos": [], "testes": [], "duvida": "O teste de C1 esta errado?",
                        "teste_errado": "C1"}, "custo": 0.1}
    roteiro["executor"].insert(0, duvida)
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = ate_o_portao_aprovado(bancada)
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco()).motivo == MotivoDaParada.AGUARDANDO_RESPOSTA
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    questao = estado.fatias[0].duvidas[0].id
    resposta = (ItemPatch(OperacaoPatch.REPLACE, f"/nos/{questao}/propriedades/status", "respondida"),
                ItemPatch(OperacaoPatch.REPLACE, f"/nos/{questao}/propriedades/resposta", "manter: o teste segue a spec"))
    assert bancada.kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=resposta, justificativa="resposta"))).sucesso

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert len(bancada.chamadas("aceite")) == 1, "manter nao refaz o teste"
    assert "manter: o teste segue a spec" in bancada.chamadas("executor")[1]["stdin"]


def test_duvida_no_autonomo_nao_confere_com_o_schema_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o executor do autônomo que devolve `duvida` volta à mesma sessão com o problema; a saída certa segue."""
    roteiro = roteiro_completo()
    duvida = {"saida": {"status": "duvida", "resumo": "parei", "arquivos": [], "testes": [], "duvida": "Inteiros?"}, "custo": 0.1}
    roteiro["executor"].insert(0, duvida)
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    retomada = bancada.chamadas("executor")[1]
    assert "--resume" in retomada["argv"] and "duvida" in retomada["stdin"]
