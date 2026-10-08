"""A forma de `Goal.planos` e `Goal.respostas_de_desvio`: listas que só crescem, uma entrada por lote.

O papel que escreve cada lista é decidido pelo RoleGate (kernel/gestos_de_escopo.py);
aqui se confere a entrada, de quem quer que venha, o humano inclusive. O plano
aprovado e a resposta de desvio são registro de quem decidiu e de quando, e um
registro que se reescreve, ou que declara outro autor, não prova nada:

- a lista não perde nem altera entrada antiga, e cresce em exatamente uma por lote;
- o `seq` é o `versao_log` do estado antes do lote, o ponto do log que a entrada descreve;
- o autor e o papel são os da proposta, não os que o texto declara;
- a versão do plano é a anterior mais um.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao

AUSENTE: object = object()
SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2
SEGMENTOS_DE_UMA_PROPRIEDADE: int = 4

CHAVES_DO_PLANO: frozenset[str] = frozenset({"versao", "seq", "aprovado_por", "papel"})
CHAVES_OBRIGATORIAS_DA_RESPOSTA: frozenset[str] = frozenset({"seq", "respondido_por", "papel", "resposta"})
CHAVES_DA_RESPOSTA: frozenset[str] = CHAVES_OBRIGATORIAS_DA_RESPOSTA | {"raiz"}


@dataclass(frozen=True)
class ProblemaDeForma:
    """O que está errado na lista, com o modo de falha que o diagnostica."""

    mensagem: str
    modo: ModoFalhaMAST = ModoFalhaMAST.ESTRUTURA_INCOMPLETA


@dataclass(frozen=True)
class LoteSobreLista:
    """A lista de um Goal antes e depois do lote, e o que a entrada nova precisa dizer."""

    id_goal: str
    campo: str
    antes: list[Any]
    depois: Any
    proposta: PropostaPatch
    estado: GrafoEstado


def validar_forma_do_escopo(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Recusa o lote que reescreve, encurta ou falsifica uma entrada de plano ou de resposta de desvio."""
    for campo in _CONFERENCIAS:
        recusa = _primeira_recusa(proposta, estado, campo)
        if recusa is not None:
            return recusa
    return ResultadoValidacao.sucesso()


def _primeira_recusa(proposta: PropostaPatch, estado: GrafoEstado, campo: str) -> ResultadoValidacao | None:
    """A recusa do primeiro Goal cuja lista do campo o lote deixa fora da forma, ou None."""
    dobra = DobraDoCampo(campo, estado)
    for item in proposta.operacoes:
        dobra.aplicar(item)
    for id_goal, (antes, depois) in dobra.alterados().items():
        lote = LoteSobreLista(id_goal, campo, _como_lista(antes), depois, proposta, estado)
        problema = _conferir_crescimento(lote) or _CONFERENCIAS[campo](lote, depois[-1])
        if problema is not None:
            return _recusar(lote, problema)
    return None


def _recusar(lote: LoteSobreLista, problema: ProblemaDeForma) -> ResultadoValidacao:
    """A recusa nomeia o Goal, a lista e o que fazer: a ferramenta que monta a entrada certa."""
    ferramenta = "aprovar_plano" if lote.campo == CAMPO_PLANOS else "responder_desvio"
    return ResultadoValidacao.falha(
        f"Goal '{lote.id_goal}': '{lote.campo}' {problema.mensagem}. A lista so cresce, com uma entrada nova por lote, "
        f"feita pela ferramenta '{ferramenta}'. O seq da entrada nova e {lote.estado.versao_log}",
        "InvariantGate",
        {"id_goal": lote.id_goal, "campo": lote.campo},
        modo=problema.modo,
    )


def _conferir_crescimento(lote: LoteSobreLista) -> ProblemaDeForma | None:
    """A lista nova repete a antiga na ordem e acrescenta exatamente uma entrada."""
    if not isinstance(lote.depois, list):
        return ProblemaDeForma("deve continuar sendo uma lista, que so cresce")
    antes = lote.antes
    if len(lote.depois) < len(antes) or lote.depois[: len(antes)] != antes:
        return ProblemaDeForma("perderia ou alteraria uma entrada antiga")
    if len(lote.depois) != len(antes) + 1:
        return ProblemaDeForma(f"recebe {len(lote.depois) - len(antes)} entradas novas; so uma por lote")
    return None


def _conferir_plano(lote: LoteSobreLista, entrada: Any) -> ProblemaDeForma | None:
    """A versão nova do plano: versão seguinte, seq do log e autoria da proposta."""
    if not isinstance(entrada, Mapping) or set(entrada) != CHAVES_DO_PLANO:
        return ProblemaDeForma("pede a entrada {versao, seq, aprovado_por, papel}")
    esperada = max((e["versao"] for e in lote.antes if isinstance(e, Mapping) and _eh_inteiro(e.get("versao"))), default=0) + 1
    if not _eh_inteiro(entrada["versao"]) or entrada["versao"] != esperada:
        return ProblemaDeForma(f"pede a versao {esperada} (a anterior mais um), e veio {entrada['versao']!r}")
    return _conferir_seq_e_autoria(lote, entrada, "aprovado_por")


def _conferir_resposta(lote: LoteSobreLista, entrada: Any) -> ProblemaDeForma | None:
    """A resposta de desvio: raiz conhecida ou nula, texto, seq do log e autoria da proposta."""
    if not isinstance(entrada, Mapping) or not CHAVES_OBRIGATORIAS_DA_RESPOSTA <= set(entrada) <= CHAVES_DA_RESPOSTA:
        return ProblemaDeForma("pede a entrada {seq, respondido_por, papel, raiz, resposta}")
    raiz = entrada.get("raiz")
    if raiz is not None and (not isinstance(raiz, str) or raiz not in lote.estado.nos):
        return ProblemaDeForma(f"aponta a raiz {raiz!r}, que nao e um no do grafo; use o id da decisao ou deixe nulo")
    if not isinstance(entrada["resposta"], str) or not entrada["resposta"].strip():
        return ProblemaDeForma("pede o texto da resposta, nao vazio")
    return _conferir_seq_e_autoria(lote, entrada, "respondido_por")


def _conferir_seq_e_autoria(lote: LoteSobreLista, entrada: Mapping[str, Any], campo_autor: str) -> ProblemaDeForma | None:
    """O `seq` é o do log antes do lote, e quem assina é quem propõe, com o papel dele."""
    if not _eh_inteiro(entrada["seq"]) or entrada["seq"] != lote.estado.versao_log:
        return ProblemaDeForma(f"pede seq {lote.estado.versao_log} (o versao_log antes do lote), e veio {entrada['seq']!r}")
    if entrada[campo_autor] != lote.proposta.autor or entrada["papel"] != lote.proposta.papel.value:
        return ProblemaDeForma(
            f"declara '{entrada[campo_autor]}' ({entrada['papel']}), mas o lote e de "
            f"'{lote.proposta.autor}' ({lote.proposta.papel.value}); a entrada leva a autoria de quem a propoe",
            ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )
    return None


_CONFERENCIAS: Mapping[str, Callable[[LoteSobreLista, Any], ProblemaDeForma | None]] = {
    CAMPO_PLANOS: _conferir_plano,
    CAMPO_RESPOSTAS_DE_DESVIO: _conferir_resposta,
}


class DobraDoCampo:
    """O valor de um campo de Goal antes e depois do lote, dobrando as operações na ordem em que vêm."""

    def __init__(self, campo: str, estado: GrafoEstado) -> None:
        self._campo: str = campo
        self._estado: GrafoEstado = estado
        self._valores: dict[str, list[Any]] = {}

    def alterados(self) -> dict[str, tuple[Any, Any]]:
        """Por Goal que o lote toca, o valor antes e o depois; só os que mudaram."""
        return {id_goal: (par[0], par[1]) for id_goal, par in self._valores.items() if par[0] != par[1]}

    def aplicar(self, item: ItemPatch) -> None:
        """Dobra a operação: criação do Goal, escrita ou remoção do campo, remoção do nó."""
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO or segmentos[0] != "nos":
            return
        if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO:
            self._aplicar_ao_no_inteiro(item, segmentos[1])
        elif len(segmentos) == SEGMENTOS_DE_UMA_PROPRIEDADE and segmentos[2:] == ["propriedades", self._campo]:
            self._aplicar_a_propriedade(item, segmentos[1])

    def _aplicar_ao_no_inteiro(self, item: ItemPatch, id_no: str) -> None:
        """O Goal criado já traz o campo ou não; o nó removido sai da conta."""
        if item.op == OperacaoPatch.REMOVE:
            self._valores.pop(id_no, None)
            return
        valor = item.value if isinstance(item.value, dict) else {}
        propriedades = valor.get("propriedades")
        if item.op == OperacaoPatch.ADD and valor.get("tipo") == TipoNo.GOAL.value:
            declarado = propriedades.get(self._campo, AUSENTE) if isinstance(propriedades, dict) else AUSENTE
            self._valores[id_no] = [AUSENTE, declarado]

    def _aplicar_a_propriedade(self, item: ItemPatch, id_no: str) -> None:
        """Escrever ou remover o campo muda o valor atual do Goal; outro tipo de nó não conta."""
        if id_no not in self._valores:
            no = self._estado.nos.get(id_no)
            if no is None or no.tipo != TipoNo.GOAL:
                return
            inicial = no.propriedades.get(self._campo, AUSENTE)
            self._valores[id_no] = [inicial, inicial]
        self._valores[id_no][1] = AUSENTE if item.op == OperacaoPatch.REMOVE else item.value


def _como_lista(valor: Any) -> list[Any]:
    """O valor como lista; ausente ou malformado conta como lista vazia."""
    return valor if isinstance(valor, list) else []


def _eh_inteiro(valor: Any) -> bool:
    """Inteiro de verdade: o booleano não conta."""
    return isinstance(valor, int) and not isinstance(valor, bool)
