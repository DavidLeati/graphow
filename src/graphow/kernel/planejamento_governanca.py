"""Planeja a escrita da política de governança, comum à ferramenta MCP e à interface web.

A regra de gravar é uma só: a `personalizada` recebida é mesclada na guardada e
nunca apagada ao trocar de preset; no Projeto, o valor `herdar` apaga a
sobrescrita do gesto. Quem chama decide só a identidade e o canal; o plano de
operações, o texto das recusas e a política efetiva que a gravação produz saem
daqui, para o MCP e a web não divergirem.

Também mora aqui a escrita das propriedades operacionais do Projeto (cadência,
teto de rodadas, ramo base e globs de colisão), que a tela grava no mesmo lote.
"""

from collections.abc import Mapping
from typing import Any

from graphow.core.governanca import (
    CHAVE_PERSONALIZADA,
    CHAVE_PRESET,
    ID_GOVERNANCA_GLOBAL,
    PROPRIEDADE_GOVERNANCA_DO_PROJETO,
    Gesto,
    PoliticaGovernanca,
    PresetDoProjeto,
    PresetGovernanca,
    validar_configuracao_do_projeto,
    validar_configuracao_global,
)
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.orquestracao import CAMPO_CAMINHOS_DE_COLISAO, CAMPO_RAMO_BASE
from graphow.core.types import TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.politica_governanca import resolver_politica_do_projeto, resolver_politica_global

ESCOPO_GLOBAL: str = "global"
VALOR_HERDAR: str = "herdar"
ROTULO_DA_GOVERNANCA_GLOBAL: str = "Governanca global"

CAMPO_CADENCIA: str = "cadencia"
CAMPO_TETO_RODADAS: str = "teto_rodadas"
CADENCIAS_ACEITAS: tuple[str, ...] = ("tarefa", "goal", "setor")
PROPRIEDADES_OPERACIONAIS: tuple[str, ...] = (
    CAMPO_CADENCIA,
    CAMPO_TETO_RODADAS,
    CAMPO_RAMO_BASE,
    CAMPO_CAMINHOS_DE_COLISAO,
)
TETO_DE_RODADAS_MINIMO: int = 1


class ErroDeConfiguracaoDeGovernanca(ValueError):
    """A configuração recebida não pode ser gravada: o texto da recusa e, quando há, cada problema."""

    def __init__(self, mensagem: str, problemas: tuple[str, ...] = ()) -> None:
        super().__init__(mensagem)
        self.problemas: tuple[str, ...] = problemas


def planejar_configuracao(
    escopo: str,
    argumentos: Mapping[str, Any],
    estado: GrafoEstado,
) -> tuple[ItemPatch, ...]:
    """As operações que gravam a política do escopo ('global' ou o id de um Projeto), ou a recusa."""
    if escopo == ESCOPO_GLOBAL:
        return _planejar_global(argumentos, estado)
    return _planejar_projeto(escopo, argumentos, estado)


def configuracao_salva(escopo: str, estado: GrafoEstado) -> dict[str, Any]:
    """O `preset` e a `personalizada` guardados no escopo; sem nada guardado, o padrão do nível."""
    if escopo == ESCOPO_GLOBAL:
        no = estado.nos.get(ID_GOVERNANCA_GLOBAL)
        declarada: Any = no.propriedades if no is not None else {}
        padrao = PresetGovernanca.GOVERNANCA_MAXIMA.value
    else:
        no = estado.nos.get(escopo)
        declarada = no.propriedades.get(PROPRIEDADE_GOVERNANCA_DO_PROJETO) if no is not None else {}
        padrao = PresetDoProjeto.HERDAR.value
    declarada = declarada if isinstance(declarada, Mapping) else {}
    personalizada = declarada.get(CHAVE_PERSONALIZADA)
    return {
        CHAVE_PRESET: declarada.get(CHAVE_PRESET) or padrao,
        CHAVE_PERSONALIZADA: dict(personalizada) if isinstance(personalizada, Mapping) else {},
    }


def com_preset_salvo(
    escopo: str,
    argumentos: Mapping[str, Any],
    estado: GrafoEstado,
) -> dict[str, Any]:
    """Os argumentos com o preset guardado quando a chamada não traz um: trocar só a personalizada não troca o preset."""
    if argumentos.get(CHAVE_PRESET) is not None:
        return dict(argumentos)
    return {**argumentos, CHAVE_PRESET: configuracao_salva(escopo, estado)[CHAVE_PRESET]}


def descrever_politica(politica: PoliticaGovernanca) -> dict[str, Any]:
    """Política efetiva em forma serializável: o valor e a origem de cada gesto."""
    return {
        "politica_efetiva": {gesto.value: politica.valor(gesto) for gesto in Gesto},
        "origens": {gesto.value: politica.origem(gesto) for gesto in Gesto},
    }


def descrever_politica_efetiva(escopo: str, estado: GrafoEstado) -> dict[str, Any]:
    """A política que vale no escopo, com a origem de cada gesto."""
    if escopo == ESCOPO_GLOBAL:
        return descrever_politica(resolver_politica_global(estado))
    return descrever_politica(resolver_politica_do_projeto(escopo, estado))


def ler_operacao_do_projeto(projeto: NoGrafo) -> dict[str, Any]:
    """As propriedades operacionais do Projeto; a que ninguém gravou volta como None."""
    return {chave: projeto.propriedades.get(chave) for chave in PROPRIEDADES_OPERACIONAIS}


def planejar_operacao(
    id_projeto: str,
    operacao: Any,
    estado: GrafoEstado,
) -> tuple[ItemPatch, ...]:
    """As operações que gravam as propriedades operacionais do Projeto; o valor nulo as apaga."""
    projeto = _exigir_projeto(id_projeto, estado)
    if not isinstance(operacao, Mapping):
        raise _recusar_operacao(["'operacao' deve ser um objeto propriedade -> valor"])
    problemas = [
        problema
        for chave, valor in operacao.items()
        for problema in _problemas_da_operacao(chave, valor)
    ]
    if problemas:
        raise _recusar_operacao(problemas)
    return tuple(
        _operacao_de_escrita(projeto, chave, valor)
        for chave, valor in operacao.items()
        if _muda(projeto, chave, valor)
    )


def _muda(projeto: NoGrafo, chave: str, valor: Any) -> bool:
    """Apagar o que não existe não é escrita; o resto é."""
    return valor is not None or chave in projeto.propriedades


def _operacao_de_escrita(projeto: NoGrafo, chave: str, valor: Any) -> ItemPatch:
    """Grava a propriedade operacional, ou a remove quando o valor é nulo."""
    caminho = f"/nos/{projeto.id}/propriedades/{chave}"
    if valor is None:
        return ItemPatch(op=OperacaoPatch.REMOVE, path=caminho)
    return ItemPatch(op=OperacaoPatch.REPLACE, path=caminho, value=valor)


def _problemas_da_operacao(chave: Any, valor: Any) -> list[str]:
    """Problemas de um par propriedade-valor das propriedades operacionais."""
    if chave not in PROPRIEDADES_OPERACIONAIS:
        return [f"propriedade operacional desconhecida {chave!r}: use {', '.join(PROPRIEDADES_OPERACIONAIS)}"]
    if valor is None or _valor_operacional_valido(chave, valor):
        return []
    return [f"valor {valor!r} invalido para '{chave}': {_dominio_operacional(chave)}"]


def _valor_operacional_valido(chave: str, valor: Any) -> bool:
    """Confere o valor contra o domínio da propriedade operacional."""
    if chave == CAMPO_CADENCIA:
        return valor in CADENCIAS_ACEITAS
    if chave == CAMPO_TETO_RODADAS:
        return isinstance(valor, int) and not isinstance(valor, bool) and valor >= TETO_DE_RODADAS_MINIMO
    if chave == CAMPO_RAMO_BASE:
        return isinstance(valor, str) and bool(valor.strip())
    return isinstance(valor, list) and all(isinstance(item, str) and item.strip() for item in valor)


def _dominio_operacional(chave: str) -> str:
    """O domínio da propriedade operacional em texto, para a mensagem de recusa."""
    dominios = {
        CAMPO_CADENCIA: f"um de {', '.join(CADENCIAS_ACEITAS)}",
        CAMPO_TETO_RODADAS: f"um inteiro a partir de {TETO_DE_RODADAS_MINIMO}",
        CAMPO_RAMO_BASE: "um texto nao vazio",
        CAMPO_CAMINHOS_DE_COLISAO: "uma lista de globs (textos nao vazios)",
    }
    return dominios[chave]


def _recusar_operacao(problemas: list[str]) -> ErroDeConfiguracaoDeGovernanca:
    """A recusa das propriedades operacionais inválidas, com cada problema."""
    return ErroDeConfiguracaoDeGovernanca(
        "Propriedades operacionais invalidas: " + "; ".join(problemas),
        tuple(problemas),
    )


def _exigir_projeto(id_projeto: str, estado: GrafoEstado) -> NoGrafo:
    """O Projeto do escopo, ou a recusa de um id que não é de Projeto neste ramo."""
    projeto = estado.nos.get(id_projeto)
    if projeto is None or projeto.tipo != TipoNo.PROJETO:
        raise ErroDeConfiguracaoDeGovernanca(
            f"O escopo '{id_projeto}' nao e 'global' nem o id de um Projeto existente neste ramo"
        )
    return projeto


def _planejar_global(argumentos: Mapping[str, Any], estado: GrafoEstado) -> tuple[ItemPatch, ...]:
    """As operações que gravam a política global."""
    recebida = _personalizada_recebida(argumentos)
    existente = estado.nos.get(ID_GOVERNANCA_GLOBAL)
    guardada = dict(existente.propriedades.get(CHAVE_PERSONALIZADA) or {}) if existente else {}
    configuracao = {CHAVE_PRESET: argumentos.get(CHAVE_PRESET), CHAVE_PERSONALIZADA: {**guardada, **recebida}}
    problemas = validar_configuracao_global(configuracao)
    if problemas:
        raise _recusar_configuracao(problemas)
    if existente is None:
        no = {
            "id": ID_GOVERNANCA_GLOBAL,
            "tipo": TipoNo.GOVERNANCA.value,
            "rotulo": ROTULO_DA_GOVERNANCA_GLOBAL,
            "propriedades": configuracao,
        }
        return (ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{ID_GOVERNANCA_GLOBAL}", value=no),)
    return tuple(_definir_propriedade(ID_GOVERNANCA_GLOBAL, chave, valor) for chave, valor in configuracao.items())


def _planejar_projeto(
    id_projeto: str,
    argumentos: Mapping[str, Any],
    estado: GrafoEstado,
) -> tuple[ItemPatch, ...]:
    """As operações que gravam a política do Projeto."""
    projeto = _exigir_projeto(id_projeto, estado)
    recebida = _personalizada_recebida(argumentos)
    declarada = projeto.propriedades.get(PROPRIEDADE_GOVERNANCA_DO_PROJETO)
    guardada = dict((declarada or {}).get(CHAVE_PERSONALIZADA) or {}) if isinstance(declarada, Mapping) else {}
    apagadas = {gesto for gesto, valor in recebida.items() if valor == VALOR_HERDAR}
    sobrescritas = {gesto: valor for gesto, valor in {**guardada, **recebida}.items() if gesto not in apagadas}
    problemas = _gestos_desconhecidos_a_herdar(apagadas)
    configuracao = {CHAVE_PRESET: argumentos.get(CHAVE_PRESET), CHAVE_PERSONALIZADA: sobrescritas}
    problemas += validar_configuracao_do_projeto(configuracao)
    if problemas:
        raise _recusar_configuracao(problemas)
    return (_definir_propriedade(id_projeto, PROPRIEDADE_GOVERNANCA_DO_PROJETO, configuracao),)


def _definir_propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """A operação que define uma propriedade de um nó existente."""
    return ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)


def _gestos_desconhecidos_a_herdar(gestos: set[str]) -> list[str]:
    """Problemas de 'herdar' pedido para um gesto que não existe: apagar o que não existe seria silêncio."""
    conhecidos = {gesto.value for gesto in Gesto}
    return [f"gesto desconhecido {gesto!r}" for gesto in sorted(gestos) if gesto not in conhecidos]


def _personalizada_recebida(argumentos: Mapping[str, Any]) -> Mapping[str, Any]:
    """A `personalizada` declarada na chamada (ausente, vazia), ou a recusa se não for um objeto."""
    recebida = argumentos.get(CHAVE_PERSONALIZADA)
    if recebida is None:
        return {}
    if isinstance(recebida, Mapping):
        return recebida
    raise _recusar_configuracao(validar_configuracao_global({CHAVE_PERSONALIZADA: recebida}))


def _recusar_configuracao(problemas: list[str]) -> ErroDeConfiguracaoDeGovernanca:
    """A recusa de uma configuração de governança inválida, com cada problema."""
    return ErroDeConfiguracaoDeGovernanca(
        "Configuracao de governanca invalida: " + "; ".join(problemas),
        tuple(problemas),
    )
