"""O que chega à conferência e à fatia de correção: os desacordos, o diff inteiro em resumo e as chamadas de cada achado.

Na revisão da T2c+T2d e da T2e: o desacordo do executor da correção não
chegava a ninguém (a caçada já tinha rodado e a conferência não o recebia), o
diff das correções ia cortado em ordem alfabética, sem aviso (`docs/` e o
README antes de `src/`), e o corte das chamadas que reproduzem valia para a
fatia inteira, com o achado herdado de outro marco sem as dele.
"""

from pathlib import Path
from typing import Any

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco

from tests.orquestrador.apoio_laco import autor_de_aceite, montar_bancada, roteiro_completo

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
ARGUMENTO: str = "o teste de C1 importa soma de uma pasta que a correcao nao usa"


def _teste_errado() -> dict[str, Any]:
    """A saída do executor do modo autônomo que diz que o teste de aceite de C1 está errado."""
    saida = {"status": "teste_errado", "resumo": "parei no teste de C1", "arquivos": [], "testes": [], "duvida": ARGUMENTO,
             "teste_errado": "C1"}
    return {"saida": saida, "custo": 0.1}


def _mantido() -> dict[str, Any]:
    """O autor de aceite que, refazendo C1, mantém o teste como estava e diz por quê."""
    resposta = autor_de_aceite()
    resposta["saida"]["criterios"] = resposta["saida"]["criterios"][:1]
    resposta["saida"]["resumo"] = "o teste esta certo: importa da raiz, como a suite"
    return resposta


def test_desacordo_do_executor_da_correcao_chega_a_conferencia_nominal(tmp_path: Path) -> None:
    """T2i.1: a correção diz que o teste de C1 está errado, o autor o mantém, e a conferência recebe o desacordo para julgar."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(2, _teste_errado())
    roteiro["aceite"].append(_mantido())
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    papeis = [c["papel"] for c in bancada.chamadas() if c["papel"] != "segunda_opiniao"]
    assert papeis == ["planejador", "aceite", "executor", "executor", "verificador", "executor", "aceite", "executor",
                      "conferencia"]
    assert "Desacordos sobre testes de aceite" not in bancada.chamadas("verificador")[0]["stdin"]
    conferencia = bancada.chamadas("conferencia")[0]["stdin"]
    assert "## Desacordos sobre testes de aceite (julgue o criterio)" in conferencia
    assert ("- C1: o executor de M1.K1.1 disse que o teste esta errado; o autor o manteve: o teste esta certo: importa da "
            "raiz, como a suite") in conferencia
