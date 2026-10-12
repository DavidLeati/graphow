"""Os testes de aceite gravados no livro-razão: o commit como Artifact, a ligação de cada critério aos seus testes e o Goal.

O commit dos testes de aceite vira um Artifact que deriva de cada Criterio
que eles provam, com os arquivos, o comando de aceite e as execuções em que o
orquestrador os viu vermelhos antes da implementação. Cada Criterio ganha os
testes que o provam (arquivo, nome, comando), a lista de checagem, quando é
`checagem`, e a justificativa, quando o código já o atendia. O Goal guarda o
aceite inteiro (`aceite`): é dele que o laço lê o comando, os testes de cada
critério e os arquivos que o executor não toca.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta, propriedade
from graphow.orquestrador.saida_do_aceite import SaidaDoAceite


@dataclass(frozen=True)
class AceiteParaGravar:
    """O aceite conferido e commitado: a saída do autor, o commit, os arquivos, as execuções e o nó de cada critério."""

    saida: SaidaDoAceite
    commit: str
    arquivos: tuple[str, ...]
    execucoes: Sequence[Mapping[str, Any]]
    nos: Mapping[str, str]
    id_do_aceite: str = ""
    revisoes: int = 0
    atendidos: tuple[str, ...] = ()
    so: tuple[str, ...] = ()

    def em_json(self) -> dict[str, Any]:
        """O aceite como propriedade do Goal."""
        return {
            "commit": self.commit, "comando": self.saida.comando_aceite, "resumo": self.saida.resumo, "arquivos": list(self.arquivos),
            "criterios": [{"id": criterio.id, **criterio.em_json()} for criterio in self.saida.criterios], "revisoes": self.revisoes,
        }


def gravar_aceite_proposto(livro: LivroRazaoDoGoal, proposto: Mapping[str, Any] | None) -> None:
    """A saída conferida do autor e as execuções vermelhas, no Goal, antes do commit: a retomada a reaproveita."""
    valor = dict(proposto) if proposto is not None else None
    livro.gravar([propriedade(livro.id_goal, m.CAMPO_ACEITE_PROPOSTO, valor)], f"Aceite proposto do Goal {livro.id_goal}")


def gravar_aceite(livro: LivroRazaoDoGoal, pedido: AceiteParaGravar) -> None:
    """O Artifact do commit dos testes, a ligação de cada critério aos seus testes e o aceite no Goal, num lote."""
    id_artefato = f"art-{pedido.id_do_aceite or m.id_do_aceite(livro.id_goal)}"
    propriedades = {
        m.CAMPO_COMMIT: pedido.commit, "arquivos": list(pedido.arquivos), "comando_aceite": pedido.saida.comando_aceite,
        "resumo": pedido.saida.resumo, "vermelhos_antes_da_implementacao": [dict(item) for item in pedido.execucoes],
    }
    operacoes = [
        *livro.produzido(id_artefato, TipoNo.ARTIFACT, f"Testes de aceite em {pedido.commit[:12]}", propriedades=propriedades),
        *_ligacao_dos_criterios(livro, pedido, id_artefato),
        propriedade(livro.id_goal, m.CAMPO_ACEITE, pedido.em_json()),
        propriedade(livro.id_goal, m.CAMPO_ACEITE_PROPOSTO, None),
        *([propriedade(livro.id_goal, a.CAMPO_PEDIDOS_ATENDIDOS, list(pedido.atendidos))] if pedido.atendidos else []),
    ]
    livro.gravar(operacoes, f"Testes de aceite do Goal {livro.id_goal} em {pedido.commit[:12]}")


def _ligacao_dos_criterios(livro: LivroRazaoDoGoal, pedido: AceiteParaGravar, id_artefato: str) -> list[ItemPatch]:
    """Cada Criterio ganha os testes, a checagem e a justificativa, e o commit deriva dele; a Constraint de antes, não."""
    view = livro.view()
    operacoes: list[ItemPatch] = []
    for criterio in (c for c in pedido.saida.criterios if not pedido.so or c.id in pedido.so):
        id_no = pedido.nos.get(criterio.id, "")
        no = view.obter_no(id_no) if id_no else None
        if no is None or no.tipo != TipoNo.CRITERIO:
            continue
        operacoes += [
            aresta(id_artefato, id_no, TipoAresta.DERIVA_DE),
            propriedade(id_no, a.CAMPO_TESTES_DE_ACEITE, [teste.em_json() for teste in criterio.testes]),
            propriedade(id_no, a.CAMPO_CHECAGEM, list(criterio.checagem)),
            propriedade(id_no, a.CAMPO_JA_ATENDIDO, criterio.ja_atendido),
            propriedade(id_no, a.CAMPO_COMMIT_DO_ACEITE, pedido.commit),
        ]
    return operacoes
