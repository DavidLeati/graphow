"""O `atende` que a conferência dá com o excedente do teto pendente: o critério sai `parcial` e o excedente volta (T2m.1).

Na revisão da T2k+T2l, a regra da conferência só valia quando o código mudava
o parecer: a conferência dava C2 `atende` sem citar o 6º bloqueante, que
tinha ficado fora do teto, e o Goal fechava com ele só como pendência (K1); o
S-B do cartão da T2k, continuado com mais uma correção, fechava igual (K1b).
Agora o excedente volta como bloqueante, com o `persiste` dele, e a
conferência seguinte o confere: é um achado conhecido, e não uma borda nova.
"""

from pathlib import Path
from typing import Any

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco, Parada
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.saida_do_verificador import MARCA_DO_TETO
from graphow.orquestrador.tipo_da_verificacao import escolher_o_tipo

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
E6: str = "achado-goal-soma-v1-6"


def _seis() -> list[dict[str, Any]]:
    """Seis bloqueantes de C2: o 6º passa do teto."""
    return [{**BLOQUEANTE_DO_README, "titulo": f"README defeito {i}", "local": f"README.md:{i}"} for i in range(1, 7)]


def _rodar(tmp_path: Path, roteiro: dict[str, list[dict[str, Any]]]) -> tuple[Parada, EstadoDoGoal]:
    """O laço autônomo da spec com o roteiro dado: a parada e o estado do Goal."""
    bancada = montar_bancada(tmp_path, roteiro)
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return parada, estado


def _pareceres(estado: EstadoDoGoal, indice: int) -> dict[str, str]:
    """O veredito gravado de cada critério e decisão da verificação dada."""
    return {str(p["id"]): str(p["veredito"]) for p in estado.verificacoes[indice].propriedades["pareceres"]}


def _de_volta(estado: EstadoDoGoal, indice: int) -> list[tuple[str, str]]:
    """O título e o `persiste` de cada bloqueante da verificação dada."""
    return [(x.texto("titulo"), x.texto("persiste")) for x in estado.verificacoes[indice].bloqueantes()]


def test_conferencia_que_da_atende_sem_citar_o_excedente_nao_fecha_com_ele_pendente_nominal(tmp_path: Path) -> None:
    """T2m.1 (K1): a conferência dá C2 `atende` sem citar o 6º; C2 sai `parcial`, o 6º volta e só fecha depois de conferido."""
    roteiro = roteiro_completo()
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "Defeito 6 resolvido.\n"}))
    roteiro["verificador"] = [verificacao("parcial", _seis()), verificacao("atende"), verificacao("atende")]
    roteiro["revisor"] = [revisao() for _ in range(8)]

    parada, estado = _rodar(tmp_path, roteiro)

    assert estado.verificacoes[0].achados[5].texto("marca") == MARCA_DO_TETO
    assert _pareceres(estado, 1)["C2"] == "parcial"
    assert _de_volta(estado, 1) == [("README defeito 6", E6)]
    assert parada.fechou, parada.mensagem
    assert estado.verificacoes[1].achados[0].estado == "resolvido"
    assert E6 not in escolher_o_tipo(estado, estado.marcos()[-1]).ids_dos_excedentes
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]


def test_sb_continuado_para_com_o_excedente_de_volta_sem_ciclo_edge_case(tmp_path: Path) -> None:
    """T2m.1 (K1b): C2 parcial na 1ª conferência, sintético, correção; a 2ª dá `atende`; sem ciclo, o 6º volta e o laço para."""
    roteiro = roteiro_completo()
    c2_parcial = verificacao("parcial")
    c2_parcial["saida"]["criterios"][1]["prova"] = "README defeito 6 continua: README.md:6"
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "Mais um exemplo: somar(1, 1) == 2.\n"}))
    roteiro["verificador"] = [verificacao("parcial", _seis()), c2_parcial, verificacao("atende")]
    roteiro["revisor"] = [revisao() for _ in range(8)]

    parada, estado = _rodar(tmp_path, roteiro)

    assert [x.texto("titulo") for x in estado.verificacoes[1].bloqueantes()] == ["C2 parcial"]
    assert not parada.fechou
    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    assert _pareceres(estado, 2)["C2"] == "parcial"
    assert _de_volta(estado, 2) == [("README defeito 6", E6)]
    assert "README defeito 6" in parada.mensagem
