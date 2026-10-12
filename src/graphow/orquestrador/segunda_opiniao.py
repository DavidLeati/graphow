"""A segunda opinião sobre o achado sem citação: rebaixá-lo a acompanhamento exige que dois concordem.

O código decide a gravidade pelo que o achado toca: o que fere critério ou
decisão é bloqueante, o resto é acompanhamento. Mas quem diz o que ele toca é
o verificador, e o achado que ele deixa sem citação vira acompanhamento por
uma opinião só. Para cada achado do verificador sem critério nem decisão, uma
sessão curta e sem ferramentas (Sonnet por padrão, só texto: os critérios,
as decisões e o achado) diz o que ele fere (a saída fora do formato volta a
ela uma vez). Se ela cita algum, o achado passa
a tocá-lo e é bloqueante. Se ela também não cita nada, ele fica
acompanhamento. Se ela não responde, os dois não concordaram, e o achado é
bloqueante. Cada sessão vai à telemetria do Goal como as outras, com o custo.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.esquemas import PAPEL_SEGUNDA_OPINIAO
from graphow.orquestrador.saida_do_verificador import ORIGEM_DO_VERIFICADOR, Achado, Verificacao
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel

MOTIVO_SEM_RESPOSTA: str = "a segunda opiniao nao respondeu: sem acordo, o achado nao se rebaixa"


def com_a_segunda_opiniao(contexto: ContextoDoGoal, verificacao: Verificacao, *, textos: Mapping[str, str]) -> Verificacao:
    """A verificação com cada achado sem citação julgado de novo, numa sessão própria, contra os critérios e decisões dados."""
    achados = tuple(
        _julgado(contexto, achado, textos=textos, numero=numero) if _sem_citacao(achado) else achado
        for numero, achado in enumerate(verificacao.achados, start=1)
    )
    return replace(verificacao, achados=achados)


def _sem_citacao(achado: Achado) -> bool:
    """O achado do verificador que não toca critério nem decisão."""
    return achado.origem == ORIGEM_DO_VERIFICADOR and not achado.toca


def _julgado(contexto: ContextoDoGoal, achado: Achado, *, textos: Mapping[str, str], numero: int) -> Achado:
    """O achado com o que a segunda opinião diz que ele fere; sem resposta, sem acordo, e bloqueante."""
    resposta = contexto.sessoes.rodar(PedidoDePapel(
        papel=PAPEL_SEGUNDA_OPINIAO, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=numero,
        briefing=briefing_da_segunda_opiniao(achado, textos), conferir=lambda dados: _conferir(dados, textos),
        orcamento_restante_usd=contexto.restante(), retomadas=1,
    ))
    if resposta.dados is None:
        return replace(achado, sem_acordo=True, segunda_opiniao=MOTIVO_SEM_RESPOSTA)
    criterios, decisoes = _citados(resposta.dados, textos)
    return replace(achado, criterios=criterios, decisoes=decisoes, segunda_opiniao=str(resposta.dados.get("motivo", "")))


def _citados(dados: Mapping[str, Any], textos: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Os critérios e as decisões citados que existem no Goal."""
    criterios = tuple(dict.fromkeys(str(c) for c in dados.get("criterios", []) if str(c) in textos))
    decisoes = tuple(dict.fromkeys(str(d) for d in dados.get("decisoes", []) if str(d) in textos))
    return criterios, decisoes


def _conferir(dados: Mapping[str, Any], textos: Mapping[str, str]) -> tuple[str, ...]:
    """Só códigos do Goal."""
    estranhos: Sequence[str] = [str(c) for c in (*dados.get("criterios", []), *dados.get("decisoes", [])) if str(c) not in textos]
    return (f"codigos que nao sao do Goal: {', '.join(estranhos)}",) if estranhos else ()


def briefing_da_segunda_opiniao(achado: Achado, textos: Mapping[str, str]) -> str:
    """O pedido: os critérios e as decisões com o texto, e o achado inteiro."""
    return "\n\n".join([
        "# Segunda opiniao sobre um achado",
        "## Criterios e decisoes do Goal\n" + "\n".join(f"- {codigo}: {texto}" for codigo, texto in textos.items()),
        f"## O achado\nTitulo: {achado.titulo}\nDescricao: {achado.descricao}\nProva: {achado.prova}"
        + (f"\nLocal: {achado.local}" if achado.local else ""),
        "Devolva o JSON do schema.",
    ])
