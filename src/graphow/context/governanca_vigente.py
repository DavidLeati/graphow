"""A governança vigente dita ao agente: o protocolo e as vistas leem a mesma política.

O texto fixo "promover aprendizado e encerrar a sessão são gestos humanos"
mentia assim que a política passou a ser configurável. Aqui a política efetiva
do Projeto do alvo vira texto curto: o preset, os gestos que não estão com o
humano e o que segue humano em qualquer preset.

A resolução parte de um `GrafoView`, que é o que o contexto enxerga, e delega a
`kernel/politica_governanca.py`: o Projeto do alvo e a herança são lidos como o
RoleGate os lê, num lugar só.
"""

from graphow.context.secoes import PrioridadeRetencao, SecaoContexto
from graphow.core.governanca import (
    GESTOS_POR_PAPEL,
    ORIGEM_LEGADO,
    PRESETS_FIXOS,
    VALOR_ARBITRO,
    Gesto,
    PoliticaGovernanca,
    PresetGovernanca,
    politica_padrao,
)
from graphow.core.types import TipoNo
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.projection.graph_view import GrafoView

TITULO_DA_SECAO_DE_GOVERNANCA: str = "Governanca"
# Vizinha das restrições, que também dizem o que vale para o alvo; cai antes de
# tudo, junto do contexto que só está perto (veja `PrioridadeRetencao.CONTEXTO`).
ORDEM_DE_EXIBICAO_DA_GOVERNANCA: int = 1

TIPOS_COM_SECAO_DE_GOVERNANCA: frozenset[TipoNo] = frozenset({TipoNo.SESSAO, TipoNo.TASK, TipoNo.GOAL})

PRESET_PERSONALIZADA: str = PresetGovernanca.PERSONALIZADA.value
MAX_CORRECOES_PADRAO: int = int(politica_padrao().valor(Gesto.MAX_CORRECOES))

SEMPRE_HUMANOS: str = "promocao global de aprendizado e a configuracao da governanca"


def resolver_politica_na_vista(id_no: str, view: GrafoView) -> PoliticaGovernanca:
    """Política efetiva do Projeto que contém o nó; sem Projeto ancestral, a global.

    Delega ao resolvedor do kernel, com o mesmo rastreador: a vista repete o
    veredito que o RoleGate aplica, e não uma busca própria do Projeto que
    poderia achar outro.
    """
    return resolver_politica_do_no(id_no, view.estado, RastreadorProjetoAncestral())


def nome_do_preset(politica: PoliticaGovernanca) -> str:
    """O preset fixo cujos valores a política repete; senão, `personalizada`."""
    for preset, valores in PRESETS_FIXOS.items():
        if all(politica.valor(gesto) == valor for gesto, valor in valores.items()):
            return preset.value
    return PRESET_PERSONALIZADA


def _gestos_por_papel() -> tuple[Gesto, ...]:
    """Os gestos que se decidem por papel, na ordem do catálogo."""
    return tuple(gesto for gesto in Gesto if gesto in GESTOS_POR_PAPEL)


def gestos_com_o_arbitro(politica: PoliticaGovernanca) -> tuple[Gesto, ...]:
    """Os gestos por papel que a política entrega ao árbitro, na ordem do catálogo."""
    return tuple(gesto for gesto in _gestos_por_papel() if politica.valor(gesto) == VALOR_ARBITRO)


def gestos_com_o_humano(politica: PoliticaGovernanca) -> tuple[Gesto, ...]:
    """Os gestos por papel que seguem só do humano, na ordem do catálogo."""
    return tuple(gesto for gesto in _gestos_por_papel() if politica.valor(gesto) != VALOR_ARBITRO)


def esta_toda_com_o_humano(politica: PoliticaGovernanca) -> bool:
    """Governança máxima sem nenhum desvio: nada está fora do humano, nem a estrutura nem as correções."""
    return nome_do_preset(politica) == PresetGovernanca.GOVERNANCA_MAXIMA.value


def _nomes(gestos: tuple[Gesto, ...]) -> str:
    """Os gestos separados por vírgula, como as ferramentas e a política os nomeiam."""
    return ", ".join(gesto.value for gesto in gestos)


def _linha_de_estrutura(politica: PoliticaGovernanca) -> list[str]:
    """Diz que todos os agentes criam todos os tipos de nó, quando a estrutura é ilimitada."""
    if not politica.estrutura_ilimitada:
        return []
    legado = " (legado nivel_autonomia)" if politica.origem(Gesto.ESTRUTURA) == ORIGEM_LEGADO else ""
    return [f"- estrutura ilimitada{legado}: todos os agentes criam todos os tipos de no"]


def _linha_de_correcoes(politica: PoliticaGovernanca) -> list[str]:
    """Diz o teto de reprovações em cadeia quando difere do padrão."""
    if politica.max_correcoes == MAX_CORRECOES_PADRAO:
        return []
    return [f"- max_correcoes: {politica.max_correcoes} reprovacoes em cadeia antes do teto (a de ordem {politica.max_correcoes} escala)"]


def _linha_de_acao_externa(politica: PoliticaGovernanca) -> list[str]:
    """Diz que o executor executa a Task de ação externa, quando a política a entrega a ele."""
    if not politica.acao_externa_com_executor:
        return []
    return ["- acao_externa com o executor: ele assume e entrega a Task de entrega acao_externa"]


def descrever_governanca(politica: PoliticaGovernanca) -> tuple[str, ...]:
    """As linhas da seção: o preset efetivo e o que não está com o humano; uma só na governança máxima."""
    preset = nome_do_preset(politica)
    if esta_toda_com_o_humano(politica):
        return (f"- {preset}: todos os gestos com o humano",)
    com_arbitro = gestos_com_o_arbitro(politica)
    linhas = [f"- preset efetivo: {preset}"]
    if com_arbitro:
        linhas.append(f"- com o arbitro: {_nomes(com_arbitro)}")
    linhas.extend(_linha_de_estrutura(politica))
    linhas.extend(_linha_de_correcoes(politica))
    linhas.extend(_linha_de_acao_externa(politica))
    linhas.append(f"- sempre do humano: {SEMPRE_HUMANOS}")
    return tuple(linhas)


def montar_secao_de_governanca(id_alvo: str, view: GrafoView) -> SecaoContexto:
    """A seção `Governanca` do alvo, lida da política do Projeto que o contém."""
    politica = resolver_politica_na_vista(id_alvo, view)
    return SecaoContexto(
        titulo=TITULO_DA_SECAO_DE_GOVERNANCA,
        linhas=descrever_governanca(politica),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DA_GOVERNANCA,
        prioridade_retencao=PrioridadeRetencao.CONTEXTO,
    )
