"""A âncora do Artifact: o hash que liga a entrega registrada ao conteúdo que ela entregou.

Na auditoria, duas entregas ficaram sem commit, e o grafo não tinha como dizer
o que elas eram. O Artifact novo nasce ancorado, numa de duas formas:

- código num repositório git: `commit`, o hash de 40 caracteres hexadecimais
  do commit que traz a entrega (e os `arquivos` que o git diz que ele mudou);
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
o Artifact que deriva dela segue só com o `resumo`, e a prova é a Evidence com
`fonte` e `resultado`.
"""

from collections.abc import Iterable, Mapping
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
PADRAO_DO_COMMIT: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{40}")
PADRAO_DO_SHA256: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{64}")
SEGMENTOS_DO_ELEMENTO: int = 2
FORMAS_DA_ANCORA: str = (
    "O Artifact novo leva 'commit' (o hash de 40 caracteres hexadecimais do commit que traz a entrega) ou, "
    "fora de repositorio git, 'sha256' (os 64 caracteres hexadecimais do conteudo do documento) e 'caminho' "
    "(onde o documento mora)"
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
        return f"'commit' {commit!r} nao e um hash de commit do git (40 caracteres hexadecimais)"
    if sha256 not in (None, "") and not _casa(PADRAO_DO_SHA256, sha256):
        return f"'sha256' {sha256!r} nao tem 64 caracteres hexadecimais"
    if sha256 not in (None, ""):
        return "falta 'caminho': onde mora o documento de que o 'sha256' e o conteudo"
    return "falta 'commit' ou 'sha256'"


def validar_ancora_do_artifact(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Recusa o Artifact que o lote deixaria sem âncora quando ele precisa dela."""
    recriados, nos = _recriados(proposta), projetar_nos_do_lote(proposta, estado)
    for no in nos:
        if no.tipo != TipoNo.ARTIFACT or _antigo_sem_ancora(no.id, estado, recriados=recriados):
            continue
        problema = diagnosticar_ancora(no.propriedades)
        if problema is not None and not _de_acao_externa(no.id, proposta, estado, tocados=nos):
            return ResultadoValidacao.falha(
                f"Artifact '{no.id}' sem ancora: {problema}. {FORMAS_DA_ANCORA}",
                "InvariantGate",
                {"id_no": no.id},
                modo=ModoFalhaMAST.ARTIFACT_SEM_ANCORA,
            )
    return ResultadoValidacao.sucesso()


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


def _de_acao_externa(id_no: str, proposta: PropostaPatch, estado: GrafoEstado, *, tocados: Iterable[NoGrafo]) -> bool:
    """O Artifact deriva de uma Task de ação externa, pela aresta do lote ou pela que já existia."""
    tasks = {no.id: no for no in tocados if no.tipo == TipoNo.TASK}
    for destino in _destinos_de_deriva(id_no, proposta, estado):
        task = tasks.get(destino) or estado.nos.get(destino)
        if task is not None and task.tipo == TipoNo.TASK and ler_texto(task.propriedades, CAMPO_ENTREGA) == ENTREGA_ACAO_EXTERNA:
            return True
    return False


def _destinos_de_deriva(id_no: str, proposta: PropostaPatch, estado: GrafoEstado) -> list[str]:
    """Os destinos das arestas `deriva_de` que saem do nó: as que o lote cria e, se o nó já existia, as gravadas."""
    do_lote = [item.value for item in proposta.operacoes if item.op == OperacaoPatch.ADD and _segmentos(item.path)[:1] == ["arestas"]]
    destinos = [str(valor.get("destino_id", "")) for valor in do_lote if isinstance(valor, dict) and _deriva_de(valor, id_no)]
    if id_no in estado.nos:
        destinos += [a.destino_id for a in estado.arestas.values() if a.origem_id == id_no and a.tipo == TipoAresta.DERIVA_DE]
    return destinos


def _deriva_de(valor: Mapping[str, Any], id_no: str) -> bool:
    """A aresta declarada é um `deriva_de` que sai do nó."""
    return valor.get("origem_id") == id_no and valor.get("tipo") == TipoAresta.DERIVA_DE.value
