"""O livro do aceite não se reescreve: o que prova que o Goal está pronto só cresce, e só por quem pode escrevê-lo.

A invariante de fechamento (kernel/fechamento_do_goal.py) lê a verificação
final, os pareceres, os Achados, os critérios e a ponta da branch. A revisão
adversarial da fase 2 mostrou que, sem mais nada, quem quisesse fechar o Goal
burlava a regra no mesmo lote: trocava a ponta, forjava ou removia a
verificação, reescrevia os pareceres, punha o Achado em `resolvido`, tirava o
Goal do alcance removendo a condução, o plano ou o critério. Aqui, para todo
papel, o humano inclusive:

- a verificação do Goal (Evidence `verificacao_do_goal`) só o orquestrador a
  cria, com número inteiro, `final` e veredito válidos, e depois de gravada
  ninguém a edita nem a remove, nem tira a aresta que a liga;
- o Achado só o orquestrador cria, derivando no mesmo lote de uma verificação
  ou de uma revisão de risco; ele não se remove, nada nele muda além do estado,
  as arestas dele não saem, e o estado só anda: aberto para corrigido (pelo
  orquestrador, com o commit da correção), aberto ou corrigido para resolvido
  (pelo orquestrador) e para descartado (pelo humano, com o motivo); nada volta
  a aberto;
- o Criterio não se remove, as propriedades que as verificações e o aceite lhe
  dão são do orquestrador, e a ligação dele ao Goal conduzido é do
  orquestrador e não sai; `fere` é só do orquestrador;
- a ponta da branch, a condução, o plano e os testes de aceite do Goal são do
  orquestrador;
- o Goal do aceite (conduzido, ou com Criterio) só vai a `concluido` pelo
  orquestrador, num lote em que o fechamento é a única mudança; o humano o
  cancela (`cancelado`, com o motivo), e não o conclui.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.papel_do_orquestrador import sessao_do_goal
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao

PORTAO: str = "InvariantGate"
SEGMENTOS_DO_ELEMENTO: int = 2
SEGMENTOS_DA_PROPRIEDADE: int = 4
ORQUESTRADOR: PapelAutor = PapelAutor.ORQUESTRADOR
ACOES_DE_ONDE_ACHADO_DERIVA: frozenset[str] = frozenset({a.ACAO_DA_VERIFICACAO, a.ACAO_DA_REVISAO_DE_RISCO})
# As transições do estado do Achado: (de, para) -> o papel que a faz.
TRANSICOES_DO_ACHADO: Mapping[tuple[str, str], PapelAutor] = {
    (a.ESTADO_ABERTO, a.ESTADO_CORRIGIDO): ORQUESTRADOR,
    (a.ESTADO_ABERTO, a.ESTADO_RESOLVIDO): ORQUESTRADOR,
    (a.ESTADO_CORRIGIDO, a.ESTADO_RESOLVIDO): ORQUESTRADOR,
    (a.ESTADO_ABERTO, a.ESTADO_DESCARTADO): PapelAutor.HUMANO,
    (a.ESTADO_CORRIGIDO, a.ESTADO_DESCARTADO): PapelAutor.HUMANO,
    (a.ESTADO_DO_ACOMPANHAMENTO, a.ESTADO_DESCARTADO): PapelAutor.HUMANO,
}
# O que acompanha cada transição, no mesmo lote: a chave e o estado que ela exige.
EXIGENCIA_DA_TRANSICAO: Mapping[str, str] = {
    a.ESTADO_CORRIGIDO: a.CAMPO_COMMIT_DA_CORRECAO,
    a.ESTADO_DESCARTADO: a.CAMPO_MOTIVO_DO_DESCARTE,
}
CHAVES_DA_TRANSICAO: frozenset[str] = frozenset(EXIGENCIA_DA_TRANSICAO.values())


@dataclass(frozen=True)
class _Lote:
    """O lote e o estado de antes: o papel, os nós criados nele e as propriedades que ele escreve."""

    papel: PapelAutor
    estado: GrafoEstado
    criados: Mapping[str, Mapping[str, Any]]
    escritas: Mapping[tuple[str, str], Any]
    arestas_novas: tuple[Mapping[str, Any], ...]
    operacoes: tuple[ItemPatch, ...]

    def tipo(self, id_no: str) -> TipoNo | None:
        """O tipo do nó, existente ou criado no lote."""
        no = self.estado.nos.get(id_no)
        if no is not None:
            return no.tipo
        criado = self.criados.get(id_no)
        return TipoNo(criado["tipo"]) if criado and criado.get("tipo") in {t.value for t in TipoNo} else None

    def propriedades(self, id_no: str) -> Mapping[str, Any]:
        """As propriedades do nó antes do lote, ou as de criação."""
        no = self.estado.nos.get(id_no)
        if no is not None:
            return no.propriedades
        criado = self.criados.get(id_no) or {}
        propriedades = criado.get("propriedades")
        return propriedades if isinstance(propriedades, Mapping) else {}

    def escrito(self, id_no: str, chave: str) -> Any:
        """O valor que o lote escreve na propriedade, ou o que ela já tinha."""
        return self.escritas.get((id_no, chave), self.propriedades(id_no).get(chave))


def validar_livro_do_aceite(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Recusa a primeira operação que reescreve o livro do aceite ou o escreve com o papel errado."""
    lote = _montar(proposta, estado)
    for item in proposta.operacoes:
        motivo = _motivo(item, lote)
        if motivo:
            return ResultadoValidacao.falha(
                f"Livro do aceite: {motivo}", PORTAO, {"path": item.path}, modo=ModoFalhaMAST.ALTERACAO_DO_LIVRO_DO_ACEITE
            )
    return ResultadoValidacao.sucesso()


def _montar(proposta: PropostaPatch, estado: GrafoEstado) -> _Lote:
    """O lote lido uma vez: os criados, as escritas de propriedade e as arestas novas."""
    criados: dict[str, Mapping[str, Any]] = {}
    escritas: dict[tuple[str, str], Any] = {}
    arestas: list[Mapping[str, Any]] = []
    for item in proposta.operacoes:
        segmentos = _segmentos(item)
        valor = item.value if isinstance(item.value, Mapping) else {}
        criacao = item.op == OperacaoPatch.ADD and len(segmentos) == SEGMENTOS_DO_ELEMENTO
        if criacao and segmentos[0] == "nos":
            criados[segmentos[1]] = valor
        if criacao and segmentos[0] == "arestas":
            arestas.append(valor)
        if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE and segmentos[2] == "propriedades":
            escritas[(segmentos[1], segmentos[3])] = None if item.op == OperacaoPatch.REMOVE else item.value
    return _Lote(proposta.papel, estado, criados, escritas, tuple(arestas), tuple(proposta.operacoes))


def _segmentos(item: ItemPatch) -> list[str]:
    """Os segmentos do caminho da operação."""
    return [segmento for segmento in item.path.split("/") if segmento]


def _motivo(item: ItemPatch, lote: _Lote) -> str:
    """Por que a operação reescreve o livro do aceite; vazio quando ela pode."""
    segmentos = _segmentos(item)
    if len(segmentos) < SEGMENTOS_DO_ELEMENTO:
        return ""
    if segmentos[0] == "arestas":
        return _motivo_na_aresta(segmentos[1], item, lote)
    if len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return _motivo_na_criacao(segmentos[1], lote) if item.op == OperacaoPatch.ADD else _motivo_na_remocao(segmentos[1], lote)
    if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE and segmentos[2] == "propriedades":
        return _motivo_na_propriedade(segmentos[1], segmentos[3], item, lote=lote)
    return "a verificacao do Goal e o Achado nao se editam" if _imutavel(segmentos[1], lote) else ""


def _e_verificacao(propriedades: Mapping[str, Any]) -> bool:
    """A Evidence é a verificação do Goal."""
    return propriedades.get(a.CAMPO_ACAO) == a.ACAO_DA_VERIFICACAO


def _imutavel(id_no: str, lote: _Lote) -> bool:
    """A verificação do Goal e o Achado que já existem."""
    no = lote.estado.nos.get(id_no)
    return no is not None and (no.tipo == TipoNo.ACHADO or (no.tipo == TipoNo.EVIDENCE and _e_verificacao(no.propriedades)))


def _motivo_na_remocao(id_no: str, lote: _Lote) -> str:
    """O Criterio, o Achado e a verificação do Goal não se removem."""
    no = lote.estado.nos.get(id_no)
    if no is None:
        return ""
    if no.tipo in (TipoNo.CRITERIO, TipoNo.ACHADO):
        return f"o {no.tipo.value} '{id_no}' nao se remove"
    return f"a verificacao '{id_no}' nao se remove" if _e_verificacao(no.propriedades) else ""


def _motivo_na_criacao(id_no: str, lote: _Lote) -> str:
    """A verificação e o Achado nascem do orquestrador, com a forma que o fechamento lê."""
    propriedades = lote.propriedades(id_no)
    if _e_verificacao(propriedades):
        return _motivo_da_verificacao_nova(propriedades, lote)
    return _motivo_do_achado_novo(id_no, propriedades, lote) if lote.tipo(id_no) == TipoNo.ACHADO else ""


def _motivo_da_verificacao_nova(propriedades: Mapping[str, Any], lote: _Lote) -> str:
    """Só o orquestrador grava a verificação do Goal, com número inteiro, `final` e veredito válidos."""
    if lote.papel != ORQUESTRADOR:
        return "so o orquestrador grava a verificacao do Goal"
    numero = propriedades.get(a.CAMPO_NUMERO)
    valida = isinstance(numero, int) and not isinstance(numero, bool) and isinstance(propriedades.get(a.CAMPO_FINAL), bool)
    veredito = propriedades.get(a.CAMPO_VEREDITO) in (a.VEREDITO_LIMPO, a.VEREDITO_COM_BLOQUEANTE)
    return "" if valida and veredito else "a verificacao do Goal nasce com numero inteiro, final e veredito validos"


def _motivo_do_achado_novo(id_no: str, propriedades: Mapping[str, Any], lote: _Lote) -> str:
    """Só o orquestrador grava o Achado, que nasce aberto ou pendente e deriva de uma verificação ou revisão."""
    if lote.papel != ORQUESTRADOR:
        return "so o orquestrador grava o Achado"
    gravidade = propriedades.get(a.CAMPO_GRAVIDADE)
    inicial = a.ESTADO_ABERTO if gravidade == a.GRAVIDADE_BLOQUEANTE else a.ESTADO_DO_ACOMPANHAMENTO
    if gravidade not in a.GRAVIDADES or propriedades.get(a.CAMPO_ESTADO) != inicial:
        return f"o Achado '{id_no}' nasce com gravidade valida e estado {inicial}"
    origens = (aresta.get("destino_id") for aresta in lote.arestas_novas
               if aresta.get("tipo") == TipoAresta.DERIVA_DE.value and aresta.get("origem_id") == id_no)
    if any(lote.propriedades(str(origem)).get(a.CAMPO_ACAO) in ACOES_DE_ONDE_ACHADO_DERIVA for origem in origens):
        return ""
    return f"o Achado '{id_no}' deriva, no mesmo lote, da verificacao ou da revisao que o achou"


def _motivo_na_propriedade(id_no: str, chave: str, item: ItemPatch, *, lote: _Lote) -> str:
    """A escrita de uma propriedade da verificação, do Achado, do Criterio ou do Goal do aceite."""
    existente, tipo = id_no not in lote.criados, lote.tipo(id_no)
    if chave == a.CAMPO_ACAO and item.value == a.ACAO_DA_VERIFICACAO and existente:
        return "a verificacao do Goal nasce verificacao; um no existente nao vira uma"
    if existente and tipo == TipoNo.EVIDENCE and _e_verificacao(lote.propriedades(id_no)):
        return f"a verificacao '{id_no}' nao se edita"
    if existente and tipo == TipoNo.ACHADO:
        return _motivo_no_achado(id_no, chave, item, lote=lote)
    if tipo == TipoNo.CRITERIO and chave in a.PROPRIEDADES_DERIVADAS_DO_CRITERIO and lote.papel != ORQUESTRADOR:
        return f"'{chave}' do Criterio vem das verificacoes e do aceite: e do orquestrador"
    if tipo == TipoNo.GOAL:
        return _motivo_no_goal(id_no, chave, item, lote=lote)
    return ""


def _motivo_no_achado(id_no: str, chave: str, item: ItemPatch, *, lote: _Lote) -> str:
    """No Achado só o estado anda, pelas transições dele, com o que cada uma exige."""
    if chave in CHAVES_DA_TRANSICAO and item.op != OperacaoPatch.REMOVE:
        exigente = next(estado for estado, exigida in EXIGENCIA_DA_TRANSICAO.items() if exigida == chave)
        return "" if lote.escritas.get((id_no, a.CAMPO_ESTADO)) == exigente else f"'{chave}' so acompanha o Achado indo a '{exigente}'"
    if chave != a.CAMPO_ESTADO or item.op == OperacaoPatch.REMOVE:
        return f"no Achado '{id_no}' so o estado muda"
    atual, novo = str(lote.propriedades(id_no).get(a.CAMPO_ESTADO) or ""), str(item.value)
    papel = TRANSICOES_DO_ACHADO.get((atual, novo))
    if papel is None:
        return f"o Achado '{id_no}' nao vai de '{atual}' a '{novo}'"
    if lote.papel != papel:
        return f"levar o Achado '{id_no}' a '{novo}' e do papel {papel.value}"
    exigida = EXIGENCIA_DA_TRANSICAO.get(novo)
    return f"levar o Achado '{id_no}' a '{novo}' pede '{exigida}' no mesmo lote" if exigida and not lote.escritas.get((id_no, exigida)) else ""


def _motivo_no_goal(id_no: str, chave: str, item: ItemPatch, *, lote: _Lote) -> str:
    """O que no Goal é do orquestrador, e o fechamento e o cancelamento do Goal do aceite."""
    if chave in a.PROPRIEDADES_DO_ORQUESTRADOR_NO_GOAL and lote.papel != ORQUESTRADOR:
        return f"'{chave}' do Goal e do orquestrador"
    if chave != a.CAMPO_STATUS or not _goal_do_aceite(id_no, lote):
        return ""
    if item.value == a.STATUS_CONCLUIDO:
        return _motivo_do_fechamento(id_no, lote)
    if item.value == a.STATUS_CANCELADO:
        motivo = lote.escrito(id_no, a.CAMPO_MOTIVO_DO_CANCELAMENTO)
        return "" if lote.papel == PapelAutor.HUMANO and motivo else "so o humano cancela o Goal do aceite, com 'motivo_do_cancelamento'"
    return ""


def _goal_do_aceite(id_goal: str, lote: _Lote) -> bool:
    """O Goal é conduzido pelo orquestrador ou tem Criterio ligado."""
    if a.CAMPO_CONDUCAO in lote.propriedades(id_goal):
        return True
    ligados = (aresta.origem_id for aresta in lote.estado.arestas.values()
               if aresta.tipo == TipoAresta.ESCOPA and aresta.destino_id == id_goal)
    return any(lote.tipo(origem) == TipoNo.CRITERIO for origem in ligados)


def _motivo_do_fechamento(id_goal: str, lote: _Lote) -> str:
    """Só o orquestrador conclui o Goal do aceite, num lote que só fecha."""
    if lote.papel != ORQUESTRADOR:
        return "so o orquestrador conclui o Goal do aceite; o humano o cancela"
    permitidas = {f"/nos/{id_goal}/propriedades/{a.CAMPO_STATUS}", f"/nos/{id_goal}/propriedades/{a.CAMPO_INTEGRADO_EM}",
                  f"/nos/{sessao_do_goal(id_goal)}/propriedades/{a.CAMPO_STATUS}"}
    outras = [item.path for item in lote.operacoes if item.path not in permitidas]
    return f"o lote que conclui o Goal so fecha; ele tambem mexe em {outras[0]}" if outras else ""


def _motivo_na_aresta(id_aresta: str, item: ItemPatch, lote: _Lote) -> str:
    """As arestas do livro do aceite: quem as cria e as que não saem."""
    if item.op == OperacaoPatch.REMOVE:
        existente = lote.estado.arestas.get(id_aresta)
        return _motivo_na_aresta_removida(existente, lote) if existente else ""
    valor = item.value if isinstance(item.value, Mapping) else {}
    tipo, origem, destino = str(valor.get("tipo", "")), str(valor.get("origem_id", "")), str(valor.get("destino_id", ""))
    if lote.papel == ORQUESTRADOR:
        return ""
    if tipo == TipoAresta.FERE.value:
        return "a aresta fere e do orquestrador"
    if tipo == TipoAresta.ESCOPA.value and lote.tipo(origem) == TipoNo.CRITERIO and a.CAMPO_CONDUCAO in lote.propriedades(destino):
        return "ligar Criterio ao Goal conduzido e do orquestrador"
    if tipo == TipoAresta.DERIVA_DE.value and any(_e_verificacao(lote.propriedades(ponta)) for ponta in (origem, destino)):
        return "ligar a verificacao do Goal e do orquestrador"
    return ""


def _motivo_na_aresta_removida(aresta: ArestaGrafo, lote: _Lote) -> str:
    """O vínculo do Achado, do Criterio e da verificação não sai."""
    protegida = _pontas_protegidas(aresta.tipo.value, (aresta.origem_id, aresta.destino_id), lote)
    return f"a aresta {aresta.tipo.value} de {aresta.origem_id} a {aresta.destino_id} nao sai do livro do aceite" if protegida else ""


def _pontas_protegidas(tipo: str, pontas: Iterable[str], lote: _Lote) -> bool:
    """A aresta liga o Achado, o Criterio ao Goal, ou a verificação do Goal."""
    origem, destino = tuple(pontas)
    if tipo == TipoAresta.FERE.value:
        return True
    if tipo == TipoAresta.ESCOPA.value:
        return lote.tipo(origem) == TipoNo.CRITERIO
    if tipo != TipoAresta.DERIVA_DE.value:
        return False
    return TipoNo.ACHADO in (lote.tipo(origem), lote.tipo(destino)) or any(
        _e_verificacao(lote.propriedades(ponta)) for ponta in (origem, destino)
    )
