"""Política de governança: quem pode fazer cada gesto que antes era só do humano.

Módulo puro, sem I/O: recebe as propriedades dos nós e devolve a política
efetiva. Quem lê o grafo é `kernel/politica_governanca.py`.

A política mora em dois níveis. O nó singleton `governanca-global` guarda o
`preset` global e a `personalizada` global; cada Projeto pode declarar a
propriedade `governanca` com o próprio `preset` (ou `herdar`) e uma
`personalizada` PARCIAL, em que o gesto ausente herda da política global.

Os presets `governanca_maxima` e `arbitragem_maxima` são fixos. Só a
`personalizada` é editável, e ela fica SEMPRE guardada à parte: trocar o
preset para um fixo não a apaga, e a resolução a ignora enquanto o preset for
fixo. Apagar ou preservar a personalizada ao trocar de preset é do chamador;
voltar à `personalizada` a recupera intacta.

Cada gesto da política efetiva carrega a origem do valor, para a UI mostrar de
onde ele veio: `global`, `projeto`, `preset:<nome>` ou `legado:nivel_autonomia`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from graphow.core.leituras_inteiras import (
    LEITURAS_INTEIRAS,
    MAX_CORRECOES_MAXIMO,
    MAX_CORRECOES_MINIMO,
)
from graphow.core.types import PapelAutor

ID_GOVERNANCA_GLOBAL: str = "governanca-global"

PROPRIEDADE_GOVERNANCA_DO_PROJETO: str = "governanca"
PROPRIEDADE_NIVEL_AUTONOMIA: str = "nivel_autonomia"

CHAVE_PRESET: str = "preset"
CHAVE_PERSONALIZADA: str = "personalizada"
CHAVES_DA_CONFIGURACAO: frozenset[str] = frozenset({CHAVE_PRESET, CHAVE_PERSONALIZADA})

VALOR_HUMANO: str = "humano"
VALOR_ARBITRO: str = "arbitro"
VALOR_EXECUTOR: str = "executor"
VALOR_ESTRITO: str = "estrito"
VALOR_ILIMITADO: str = "ilimitado"

ORIGEM_GLOBAL: str = "global"
ORIGEM_PROJETO: str = "projeto"
ORIGEM_LEGADO: str = "legado:nivel_autonomia"
PREFIXO_ORIGEM_PRESET: str = "preset:"
PREFIXO_ORIGEM_PROJETO_RESTRITIVO: str = "projeto:"

ValorDeGesto = str | int


class Gesto(str, Enum):
    """Gestos governáveis: cada um mapeia um portão que a política pode abrir ao árbitro."""

    RESPONDER_QUESTAO = "responder_questao"
    PROMOVER_APRENDIZADO = "promover_aprendizado"
    CONSTRAINT = "constraint"
    ESTRUTURA = "estrutura"
    EXCLUIR = "excluir"
    FECHAR_GOAL = "fechar_goal"
    ENCERRAR_SESSAO = "encerrar_sessao"
    LIBERAR_POSSE_ALHEIA = "liberar_posse_alheia"
    INTEGRACAO = "integracao"
    MAX_CORRECOES = "max_correcoes"
    ACAO_EXTERNA = "acao_externa"
    # Escopo governado: aprovar o plano que vira a referência do Goal, e
    # responder ao placar quando o trabalho emergente passa dos limiares.
    APROVAR_PLANO = "aprovar_plano"
    RESPONDER_DESVIO = "responder_desvio"
    LIMIAR_DESVIO_POR_RAIZ = "limiar_desvio_por_raiz"
    LIMIAR_DESVIO_POR_GOAL = "limiar_desvio_por_goal"
    TETO_EXPANSAO = "teto_expansao"


class PresetGovernanca(str, Enum):
    """Presets do nível global: dois fixos e a personalizada, a única editável."""

    GOVERNANCA_MAXIMA = "governanca_maxima"
    ARBITRAGEM_MAXIMA = "arbitragem_maxima"
    PERSONALIZADA = "personalizada"


class PresetDoProjeto(str, Enum):
    """Presets do nível do Projeto: os do global mais `herdar`, que é o padrão."""

    HERDAR = "herdar"
    GOVERNANCA_MAXIMA = "governanca_maxima"
    ARBITRAGEM_MAXIMA = "arbitragem_maxima"
    PERSONALIZADA = "personalizada"


# Leituras inteiras (veja `core/leituras_inteiras.py`): o valor é um número.
GESTOS_INTEIROS: frozenset[Gesto] = frozenset(Gesto(chave) for chave in LEITURAS_INTEIRAS)

# Gestos que se decidem por papel (humano ou árbitro). `estrutura`, `acao_externa`
# e as leituras inteiras não são permissões ao árbitro: têm leitura própria na
# política. A ação externa (a Task que entrega um gesto no mundo, não um
# arquivo) é do humano ou do executor que tem as ferramentas para ela.
GESTOS_COM_LEITURA_PROPRIA: frozenset[Gesto] = frozenset({Gesto.ESTRUTURA, Gesto.ACAO_EXTERNA}) | GESTOS_INTEIROS
GESTOS_POR_PAPEL: frozenset[Gesto] = frozenset(gesto for gesto in Gesto if gesto not in GESTOS_COM_LEITURA_PROPRIA)

_VALORES_DE_PAPEL: frozenset[str] = frozenset({VALOR_HUMANO, VALOR_ARBITRO})

VALORES_ACEITOS: Mapping[Gesto, frozenset[str]] = MappingProxyType({
    **{gesto: _VALORES_DE_PAPEL for gesto in GESTOS_POR_PAPEL},
    Gesto.ESTRUTURA: frozenset({VALOR_ESTRITO, VALOR_ILIMITADO}),
    Gesto.ACAO_EXTERNA: frozenset({VALOR_HUMANO, VALOR_EXECUTOR}),
})

_PADROES_INTEIROS: Mapping[Gesto, ValorDeGesto] = MappingProxyType({
    Gesto(chave): leitura.padrao for chave, leitura in LEITURAS_INTEIRAS.items()
})

_GOVERNANCA_MAXIMA: Mapping[Gesto, ValorDeGesto] = MappingProxyType({
    **{gesto: VALOR_HUMANO for gesto in GESTOS_POR_PAPEL},
    **_PADROES_INTEIROS,
    Gesto.ESTRUTURA: VALOR_ESTRITO,
    Gesto.ACAO_EXTERNA: VALOR_HUMANO,
})

_ARBITRAGEM_MAXIMA: Mapping[Gesto, ValorDeGesto] = MappingProxyType({
    **{gesto: VALOR_ARBITRO for gesto in GESTOS_POR_PAPEL},
    **_PADROES_INTEIROS,
    Gesto.ESTRUTURA: VALOR_ILIMITADO,
    # Responder o placar de desvio é o que mostra ao humano o quanto o trabalho
    # se afastou do plano; nem a arbitragem máxima o tira dele.
    Gesto.RESPONDER_DESVIO: VALOR_HUMANO,
    # A arbitragem entrega aos agentes tudo o que a política pode delegar, e a
    # ação externa vai ao executor, que a faz quando tem as ferramentas para ela.
    Gesto.ACAO_EXTERNA: VALOR_EXECUTOR,
})

PRESETS_FIXOS: Mapping[PresetGovernanca, Mapping[Gesto, ValorDeGesto]] = MappingProxyType({
    PresetGovernanca.GOVERNANCA_MAXIMA: _GOVERNANCA_MAXIMA,
    PresetGovernanca.ARBITRAGEM_MAXIMA: _ARBITRAGEM_MAXIMA,
})


@dataclass(frozen=True)
class PoliticaGovernanca:
    """Política efetiva: o valor de cada gesto e de onde esse valor veio."""

    valores: Mapping[Gesto, ValorDeGesto]
    origens: Mapping[Gesto, str]

    def __post_init__(self) -> None:
        """Congela os dois mapas: a política resolvida não muda depois de pronta."""
        object.__setattr__(self, "valores", MappingProxyType(dict(self.valores)))
        object.__setattr__(self, "origens", MappingProxyType(dict(self.origens)))

    def valor(self, gesto: Gesto) -> ValorDeGesto:
        """Valor efetivo do gesto: 'humano', 'arbitro', 'estrito', 'ilimitado' ou o inteiro."""
        return self.valores[gesto]

    def origem(self, gesto: Gesto) -> str:
        """De onde o valor veio: global, projeto, preset:<nome> ou legado:nivel_autonomia."""
        return self.origens[gesto]

    def permite(self, gesto: Gesto, papel: PapelAutor) -> bool:
        """Diz se o papel pode fazer o gesto: o humano sempre, o árbitro quando a política o entrega.

        Não se aplica a `estrutura` (veja `estrutura_ilimitada`), a
        `max_correcoes` (veja `max_correcoes`) nem a `acao_externa` (veja
        `acao_externa_com_executor`): perguntar por eles é erro de quem chama.
        """
        if gesto not in GESTOS_POR_PAPEL:
            raise ValueError(f"O gesto '{gesto.value}' não se decide por papel; leia o valor dele direto")
        if papel == PapelAutor.HUMANO:
            return True
        return papel == PapelAutor.ARBITRO and self.valores[gesto] == VALOR_ARBITRO

    @property
    def estrutura_ilimitada(self) -> bool:
        """Verdadeiro quando todos os agentes ganham os tipos de nó e a camada `contem`."""
        return self.valores[Gesto.ESTRUTURA] == VALOR_ILIMITADO

    @property
    def acao_externa_com_executor(self) -> bool:
        """Verdadeiro quando o executor assume e entrega a Task de ação externa; senão ela é do humano."""
        return self.valores[Gesto.ACAO_EXTERNA] == VALOR_EXECUTOR

    @property
    def max_correcoes(self) -> int:
        """Reprovações em cadeia antes do teto: a de ordem `max_correcoes` já escala (profundidade_correcao + 1 >= max_correcoes)."""
        return int(self.valores[Gesto.MAX_CORRECOES])

    @property
    def limiar_desvio_por_raiz(self) -> int:
        """K: Tasks emergentes de uma mesma raiz de cadeia a partir das quais o desvio dispara."""
        return int(self.valores[Gesto.LIMIAR_DESVIO_POR_RAIZ])

    @property
    def limiar_desvio_por_goal(self) -> int:
        """M: Tasks emergentes do Goal, desde o último zero do contador, a partir das quais o desvio dispara."""
        return int(self.valores[Gesto.LIMIAR_DESVIO_POR_GOAL])

    @property
    def teto_expansao(self) -> int:
        """Tasks emergentes admitidas até um `responder_desvio`; 0 desliga a recusa por contagem."""
        return int(self.valores[Gesto.TETO_EXPANSAO])


def _origem_de_preset(preset: PresetGovernanca) -> str:
    """Rótulo de origem dos valores que vêm de um preset fixo."""
    return f"{PREFIXO_ORIGEM_PRESET}{preset.value}"


def politica_do_preset(preset: PresetGovernanca) -> PoliticaGovernanca:
    """Política cujos gestos todos vêm de um preset fixo."""
    origem = _origem_de_preset(preset)
    return PoliticaGovernanca(PRESETS_FIXOS[preset], {gesto: origem for gesto in Gesto})


def politica_padrao() -> PoliticaGovernanca:
    """O que vale sem nó global: governança máxima."""
    return politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA)


def _como_gesto(chave: Any) -> Gesto | None:
    """O gesto que a chave nomeia, ou None se ela não nomeia nenhum."""
    try:
        return Gesto(chave)
    except ValueError:
        return None


def _valor_eh_valido(gesto: Gesto, valor: Any) -> bool:
    """Confere o valor contra o domínio do gesto, sem aceitar booleano como inteiro."""
    if gesto in GESTOS_INTEIROS:
        return LEITURAS_INTEIRAS[gesto.value].aceita(valor)
    return isinstance(valor, str) and valor in VALORES_ACEITOS[gesto]


def _descrever_dominio(gesto: Gesto) -> str:
    """O domínio do gesto em texto, para a mensagem de recusa."""
    if gesto in GESTOS_INTEIROS:
        return LEITURAS_INTEIRAS[gesto.value].descrever()
    return " ou ".join(f"'{valor}'" for valor in sorted(VALORES_ACEITOS[gesto]))


def _gestos_validos(personalizada: Any) -> dict[Gesto, ValorDeGesto]:
    """Os pares gesto-valor reconhecíveis; o resto é ignorado na resolução."""
    if not isinstance(personalizada, Mapping):
        return {}
    pares = ((_como_gesto(chave), valor) for chave, valor in personalizada.items())
    return {gesto: valor for gesto, valor in pares if gesto is not None and _valor_eh_valido(gesto, valor)}


def _com_gestos(base: PoliticaGovernanca, gestos: Mapping[Gesto, ValorDeGesto], origem: str) -> PoliticaGovernanca:
    """Política igual à base, com os gestos dados sobrepostos e marcados com a origem."""
    valores = {**base.valores, **gestos}
    origens = {**base.origens, **{gesto: origem for gesto in gestos}}
    return PoliticaGovernanca(valores, origens)


def _preset_ou_padrao(valor: Any, enum: type[Enum], padrao: Enum) -> Any:
    """O preset que o valor nomeia, ou o padrão quando ausente ou desconhecido."""
    try:
        return enum(valor)
    except ValueError:
        return padrao


def compor_politica_global(propriedades: Mapping[str, Any] | None) -> PoliticaGovernanca:
    """Política efetiva global a partir das propriedades do nó `governanca-global`.

    Sem nó (None) ou sem preset, vale `governanca_maxima`. Preset fixo vale
    como está e a `personalizada` é ignorada. Na `personalizada`, o gesto
    ausente completa com `governanca_maxima`.
    """
    declaradas: Mapping[str, Any] = propriedades or {}
    preset = _preset_ou_padrao(
        declaradas.get(CHAVE_PRESET), PresetGovernanca, PresetGovernanca.GOVERNANCA_MAXIMA
    )
    if preset != PresetGovernanca.PERSONALIZADA:
        return politica_do_preset(preset)
    gestos = _gestos_validos(declaradas.get(CHAVE_PERSONALIZADA))
    return _com_gestos(politica_padrao(), gestos, ORIGEM_GLOBAL)


def _herdada_da_global(politica_global: PoliticaGovernanca) -> PoliticaGovernanca:
    """A global vista do Projeto: todo gesto herdado leva a origem `global`."""
    return PoliticaGovernanca(politica_global.valores, {gesto: ORIGEM_GLOBAL for gesto in Gesto})


def _nivel_legado_eh_ilimitado(nivel_autonomia: Any) -> bool:
    """Lê o `nivel_autonomia` do Projeto como o resto do kernel o lê."""
    return str(nivel_autonomia or "").lower() == VALOR_ILIMITADO


def compor_politica_do_projeto(
    governanca: Any,
    nivel_autonomia: Any,
    politica_global: PoliticaGovernanca,
) -> PoliticaGovernanca:
    """Política efetiva do Projeto a partir da propriedade `governanca` e da global.

    `herdar` (ou ausente) vale a global; preset fixo vale o preset; a
    `personalizada` do Projeto é parcial e sobrepõe a global. Legado: Projeto
    com `nivel_autonomia='ilimitado'` que herda a global sobrepõe
    `estrutura='ilimitado'`; um Projeto com preset próprio não o conserva.
    """
    declarada: Mapping[str, Any] = governanca if isinstance(governanca, Mapping) else {}
    preset = _preset_ou_padrao(declarada.get(CHAVE_PRESET), PresetDoProjeto, PresetDoProjeto.HERDAR)
    herdada = _herdada_da_global(politica_global)
    if preset == PresetDoProjeto.HERDAR:
        return _aplicar_legado(herdada, nivel_autonomia)
    if preset == PresetDoProjeto.PERSONALIZADA:
        return _com_gestos(herdada, _gestos_validos(declarada.get(CHAVE_PERSONALIZADA)), ORIGEM_PROJETO)
    return politica_do_preset(PresetGovernanca(preset.value))


def _aplicar_legado(politica: PoliticaGovernanca, nivel_autonomia: Any) -> PoliticaGovernanca:
    """Preserva o comportamento do `nivel_autonomia='ilimitado'` de antes da política."""
    if not _nivel_legado_eh_ilimitado(nivel_autonomia):
        return politica
    return _com_gestos(politica, {Gesto.ESTRUTURA: VALOR_ILIMITADO}, ORIGEM_LEGADO)


def _problemas_de_preset(valor: Any, aceitos: type[Enum]) -> list[str]:
    """Recusa o preset que não seja um dos valores do enum."""
    validos = [membro.value for membro in aceitos]
    if isinstance(valor, str) and valor in validos:
        return []
    return [f"preset inválido {valor!r}: use um de {', '.join(validos)}"]


def validar_personalizada(personalizada: Any) -> list[str]:
    """Problemas de uma `personalizada`: gesto desconhecido ou valor fora do domínio.

    Parcial é válido: gesto ausente é decidido pela resolução, não pela validação.
    """
    if not isinstance(personalizada, Mapping):
        return ["'personalizada' deve ser um objeto gesto -> valor"]
    problemas: list[str] = []
    for chave, valor in personalizada.items():
        problemas.extend(_problemas_de_entrada(chave, valor))
    return problemas


def _problemas_de_entrada(chave: Any, valor: Any) -> list[str]:
    """Problemas de um par gesto-valor da personalizada."""
    gesto = _como_gesto(chave)
    if gesto is None:
        return [f"gesto desconhecido {chave!r}"]
    if _valor_eh_valido(gesto, valor):
        return []
    return [f"valor {valor!r} fora do domínio do gesto '{gesto.value}': {_descrever_dominio(gesto)}"]


def _validar_configuracao(configuracao: Any, aceitos: type[Enum]) -> list[str]:
    """Valida um objeto {preset, personalizada} contra o enum de presets do nível."""
    if not isinstance(configuracao, Mapping):
        return ["a configuração de governança deve ser um objeto JSON"]
    problemas = [
        f"propriedade desconhecida {chave!r}: só {CHAVE_PRESET} e {CHAVE_PERSONALIZADA}"
        for chave in configuracao
        if chave not in CHAVES_DA_CONFIGURACAO
    ]
    if CHAVE_PRESET in configuracao:
        problemas.extend(_problemas_de_preset(configuracao[CHAVE_PRESET], aceitos))
    if CHAVE_PERSONALIZADA in configuracao:
        problemas.extend(validar_personalizada(configuracao[CHAVE_PERSONALIZADA]))
    return problemas


def validar_configuracao_global(configuracao: Any) -> list[str]:
    """Problemas das propriedades do nó Governanca (`preset` e `personalizada`)."""
    return _validar_configuracao(configuracao, PresetGovernanca)


def validar_configuracao_do_projeto(configuracao: Any) -> list[str]:
    """Problemas da propriedade `governanca` de um Projeto."""
    return _validar_configuracao(configuracao, PresetDoProjeto)
