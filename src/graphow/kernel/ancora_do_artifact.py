"""A âncora do Artifact: o hash que liga a entrega registrada ao conteúdo que ela entregou.

Na auditoria, duas entregas ficaram sem commit, e o grafo não tinha como dizer
o que elas eram. O Artifact novo nasce ancorado, numa de duas formas:

- código num repositório git: `commit`, o hash do commit que traz a entrega,
  com 40 caracteres hexadecimais (SHA-1, o formato padrão do git) ou 64 (o
  repositório criado com `--object-format=sha256`), e os `arquivos` que o git
  diz que ele mudou;
- fora de repositório git (trabalho que não é código, decisão 1 do BRIEF):
  `sha256`, os 64 caracteres hexadecimais do conteúdo do documento, e
  `caminho`, onde o documento mora.

O kernel distingue as duas pela propriedade presente: o `commit` válido vale
primeiro; sem ele, o `sha256` com o `caminho`. `ancora_do_artifact` diz qual
das duas o Artifact tem, para quem lê conferir sem repetir a regra.

O portão não lê o disco nem o git, porque o replay do log precisa dar o mesmo
veredito anos depois: ele garante a forma que torna a conferência possível,
como kernel/localizacao.py faz com a Evidence, e julga o Artifact como ele
vai ficar gravado depois do lote. A regra vale para o Artifact que o lote cria
(ou recria por `add`) e para o que já tinha âncora, que não a perde; o
Artifact antigo, sem âncora, segue editável, e o replay do banco antigo não
passa pelos portões.

A Task de ação externa (`entrega: acao_externa`) não deixa conteúdo para trás:
o Artifact que deriva só dela segue com o `resumo`, e a prova é a Evidence com
`fonte` e `resultado`. A isenção pede que todos os `deriva_de` do Artifact vão a
Tasks de ação externa: com um só, o executor isentava a entrega de código
citando, ao lado da Task dele, qualquer Task de ação externa do grafo.

A isenção é julgada nos `deriva_de` que sobram ao fim do lote, e vale também
para o Artifact de que o lote só cria ou tira uma aresta `deriva_de` (ou
remove o nó da outra ponta). Antes, o lote só de aresta não reavaliava o nó, e
o executor montava a isenção em três lotes: o Artifact sem âncora derivando da
ação externa, a remoção dessa aresta e a ligação à Task de código dele.
"""

from collections.abc import Mapping
import re
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.orquestracao import CAMPO_ENTREGA, ENTREGA_ACAO_EXTERNA, ler_texto
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.localizacao import projetar_nos_do_lote
from graphow.kernel.patch_models import OperacaoPatch, PropostaPatch, ResultadoValidacao

CAMPO_COMMIT: str = "commit"
CAMPO_SHA256: str = "sha256"
CAMPO_CAMINHO: str = "caminho"
ANCORA_COMMIT: str = "commit"
ANCORA_SHA256: str = "sha256"
PADRAO_DO_COMMIT: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
PADRAO_DO_SHA256: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{64}")
SEGMENTOS_DO_ELEMENTO: int = 2
FORMAS_DA_ANCORA: str = (
    "O Artifact novo leva 'commit' (o hash do commit que traz a entrega: 40 caracteres hexadecimais, ou 64 no "
    "repositorio sha256) ou, "
    "fora de repositorio git, 'sha256' (os 64 caracteres hexadecimais do conteudo do documento) e 'caminho' "
    "(onde o documento mora)"
)
ISENCAO_DA_ACAO_EXTERNA: str = (
    "So o Artifact cujos 'deriva_de' vao todos a Tasks de acao externa (entrega: acao_externa) segue sem ancora"
)


def _casa(padrao: re.Pattern[str], valor: object) -> bool:
    """O valor é texto e casa inteiro com o padrão."""
    return isinstance(valor, str) and padrao.fullmatch(valor) is not None


def ancora_do_artifact(propriedades: Mapping[str, Any]) -> str | None:
    """`commit`, `sha256` ou None, quando o Artifact não tem âncora válida."""
    if _casa(PADRAO_DO_COMMIT, propriedades.get(CAMPO_COMMIT)):
        return ANCORA_COMMIT
    if _casa(PADRAO_DO_SHA256, propriedades.get(CAMPO_SHA256)) and ler_texto(propriedades, CAMPO_CAMINHO):
        return ANCORA_SHA256
    return None


def diagnosticar_ancora(propriedades: Mapping[str, Any]) -> str | None:
    """O que falta ou está errado na âncora; None quando ela vale."""
    if ancora_do_artifact(propriedades) is not None:
        return None
    commit, sha256 = propriedades.get(CAMPO_COMMIT), propriedades.get(CAMPO_SHA256)
    if commit not in (None, ""):
        return f"'commit' {commit!r} nao e um hash de commit do git (40 ou 64 caracteres hexadecimais)"
    if sha256 not in (None, "") and not _casa(PADRAO_DO_SHA256, sha256):
        return f"'sha256' {sha256!r} nao tem 64 caracteres hexadecimais"
    if sha256 not in (None, ""):
        return "falta 'caminho': onde mora o documento de que o 'sha256' e o conteudo"
    return "falta 'commit' ou 'sha256'"


def validar_ancora_do_artifact(proposta: PropostaPatch, estado: GrafoEstado, *, depois: GrafoEstado) -> ResultadoValidacao:
    """Recusa o Artifact que o lote deixaria sem âncora quando ele precisa dela.

    `depois` é o grafo ao fim do lote, remoções incluídas (`EstruturaAposLote`).
    Julga o Artifact que o lote cria ou edita (menos o antigo sem âncora) e todo
    Artifact de que o lote cria ou tira um `deriva_de`, pelos `deriva_de` que
    sobram: o lote só de aresta montava a isenção em partes.
    """
    recriados, nos = _recriados(proposta), projetar_nos_do_lote(proposta, estado)
    tocados = {no.id: no for no in nos}
    julgados = {no.id: no for no in nos if not _antigo_sem_ancora(no.id, estado, recriados=recriados)}
    for id_no in _com_deriva_de_mexido(proposta, estado, depois):
        julgados.setdefault(id_no, tocados.get(id_no) or depois.nos[id_no])
    sem_ancora = {
        no.id: problema for no in julgados.values()
        if no.tipo == TipoNo.ARTIFACT and (problema := diagnosticar_ancora(no.propriedades)) is not None
    }
    destinos = _destinos_de_deriva(frozenset(sem_ancora), depois) if sem_ancora else {}
    for id_no, problema in sem_ancora.items():
        derivadas = [_e_acao_externa(tocados.get(destino) or depois.nos.get(destino)) for destino in destinos.get(id_no, [])]
        if not _isento(derivadas):
            return _recusa(id_no, f"{problema}, e {_sem_isencao(derivadas)}")
    return ResultadoValidacao.sucesso()


def _isento(derivadas: list[bool]) -> bool:
    """A isenção da ação externa: há `deriva_de`, e todos vão a Tasks de ação externa."""
    return bool(derivadas) and all(derivadas)


def _sem_isencao(derivadas: list[bool]) -> str:
    """Por que os `deriva_de` que sobram ao fim do lote não isentam o Artifact."""
    if not derivadas:
        return "nao tem 'deriva_de'"
    if any(derivadas):
        return "deriva de Task de acao externa e de Task que nao e"
    return "nao deriva de Task de acao externa"


def _recusa(id_no: str, problema: str) -> ResultadoValidacao:
    """A recusa do Artifact sem âncora, com o que falta, as formas da âncora e a isenção."""
    return ResultadoValidacao.falha(
        f"Artifact '{id_no}' sem ancora: {problema}. {FORMAS_DA_ANCORA}. {ISENCAO_DA_ACAO_EXTERNA}",
        "InvariantGate",
        {"id_no": id_no},
        modo=ModoFalhaMAST.ARTIFACT_SEM_ANCORA,
    )


def _segmentos(caminho: str) -> list[str]:
    """Os segmentos não vazios do caminho JSON Pointer."""
    return [seg for seg in caminho.split("/") if seg]


def _recriados(proposta: PropostaPatch) -> frozenset[str]:
    """Os nós que o lote cria ou recria inteiros, por `add` em `/nos/<id>`."""
    adicionados = (_segmentos(item.path) for item in proposta.operacoes if item.op == OperacaoPatch.ADD)
    return frozenset(seg[1] for seg in adicionados if len(seg) == SEGMENTOS_DO_ELEMENTO and seg[0] == "nos")


def _antigo_sem_ancora(id_no: str, estado: GrafoEstado, *, recriados: frozenset[str]) -> bool:
    """O Artifact gravado antes da regra, sem âncora, que o lote edita sem recriar: segue livre."""
    anterior = estado.nos.get(id_no)
    if anterior is None or anterior.tipo != TipoNo.ARTIFACT or id_no in recriados:
        return False
    return ancora_do_artifact(anterior.propriedades) is None


def _e_acao_externa(no: NoGrafo | None) -> bool:
    """O nó é uma Task com `entrega: acao_externa`, como ficará depois do lote."""
    return no is not None and no.tipo == TipoNo.TASK and ler_texto(no.propriedades, CAMPO_ENTREGA) == ENTREGA_ACAO_EXTERNA


def _com_deriva_de_mexido(proposta: PropostaPatch, estado: GrafoEstado, depois: GrafoEstado) -> tuple[str, ...]:
    """Os nós que seguem no grafo e de onde sai um `deriva_de` que o lote cria ou tira.

    Tira a aresta o `remove` dela e o `remove` do nó de uma das pontas, que leva
    as arestas dele junto.
    """
    caminhos = [(item.op, _segmentos(item.path)) for item in proposta.operacoes]
    ids_de_aresta = {seg[1] for _, seg in caminhos if len(seg) == SEGMENTOS_DO_ELEMENTO and seg[0] == "arestas"}
    nos_removidos = {seg[1] for op, seg in caminhos if op == OperacaoPatch.REMOVE and len(seg) == SEGMENTOS_DO_ELEMENTO and seg[0] == "nos"}
    mexidas = [aresta for id_aresta in ids_de_aresta for aresta in (estado.arestas.get(id_aresta), depois.arestas.get(id_aresta)) if aresta]
    if nos_removidos:
        mexidas += [a for a in estado.arestas.values() if a.origem_id in nos_removidos or a.destino_id in nos_removidos]
    origens = (aresta.origem_id for aresta in mexidas if aresta.tipo == TipoAresta.DERIVA_DE)
    return tuple(id_no for id_no in dict.fromkeys(origens) if id_no in depois.nos)


def _destinos_de_deriva(origens: frozenset[str], depois: GrafoEstado) -> dict[str, list[str]]:
    """Os destinos dos `deriva_de` que saem de cada origem ao fim do lote."""
    destinos: dict[str, list[str]] = {}
    for aresta in depois.arestas.values():
        if aresta.origem_id in origens and aresta.tipo == TipoAresta.DERIVA_DE:
            destinos.setdefault(aresta.origem_id, []).append(aresta.destino_id)
    return destinos
