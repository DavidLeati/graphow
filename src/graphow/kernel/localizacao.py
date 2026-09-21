"""Localização de uma Evidence de leitura de código: arquivo, faixa de linhas e trecho literal.

A exploração devolve ponteiros, e o planejador registra como Evidence o que leu
neles. Uma Evidence sem o ponteiro é interpretação com autoridade de fato
registrado: ninguém volta ao código para conferir. O portão não lê o disco,
porque o replay do log precisa dar o mesmo veredito anos depois; ele garante a
forma que torna a conferência possível: o caminho, uma faixa de linhas válida e
um trecho que cabe nela.

A regra vale em dois casos. A Evidence do planejador é sempre leitura de código,
então nasce localizada. E qualquer Evidence que cite `linhas` ou `trecho` cita o
ponteiro inteiro, de qualquer papel: localização pela metade não se confere.
`arquivo` sozinho segue livre, para o log de teste ou o relatório anexado.

O portão julga a Evidence como ela vai ficar gravada. Uma projeção própria das
operações deixava passar o que o conversor de eventos trata de outro jeito: um
`replace` em `/nos/<id>/trecho`, um `move` sobre a propriedade, o `add` que
recria a Evidence com outro autor. Por isso o lote passa pelo mesmo conversor e
pelo mesmo acumulador que o kernel usa para gravar e projetar.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Any

from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.patch_models import PropostaPatch
from graphow.projection.acumulador import AcumuladorProjecao

CAMPO_ARQUIVO: str = "arquivo"
CAMPO_LINHAS: str = "linhas"
CAMPO_TRECHO: str = "trecho"
CAMPOS_QUE_DECLARAM_PONTEIRO: tuple[str, ...] = (CAMPO_LINHAS, CAMPO_TRECHO)

# "120", "120-135" ou "120–135": o travessão entra porque é como modelos escrevem faixas.
PADRAO_DE_FAIXA: re.Pattern[str] = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+)\s*)?$")


@dataclass(frozen=True)
class FaixaDeLinhas:
    """Linhas de início e fim, as duas inclusivas e contadas a partir de 1."""

    inicio: int
    fim: int

    @property
    def total(self) -> int:
        """Quantas linhas a faixa cobre."""
        return self.fim - self.inicio + 1


def interpretar_faixa(valor: object) -> FaixaDeLinhas | None:
    """Lê `linhas` como faixa; None quando a forma não descreve linhas de arquivo."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return FaixaDeLinhas(valor, valor) if valor >= 1 else None
    casamento = PADRAO_DE_FAIXA.match(valor) if isinstance(valor, str) else None
    if casamento is None:
        return None
    inicio = int(casamento.group(1))
    fim = int(casamento.group(2) or inicio)
    return FaixaDeLinhas(inicio, fim) if 1 <= inicio <= fim else None


def contar_linhas(trecho: str) -> int:
    """Linhas como o editor as conta: só quebra de linha separa, e a quebra final não abre linha nova.

    `str.splitlines` também quebra em form feed e em U+2028, que aparecem
    dentro de uma linha de código de verdade, e recusaria um trecho literal.
    """
    linhas = trecho.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(linhas) > 1 and linhas[-1] == "":
        linhas.pop()
    return len(linhas)


def diagnosticar_localizacao(propriedades: Mapping[str, Any]) -> str | None:
    """O que falta ou está errado no ponteiro; None quando ele está inteiro."""
    arquivo = propriedades.get(CAMPO_ARQUIVO)
    if not isinstance(arquivo, str) or not arquivo.strip():
        return "falta 'arquivo': o caminho do arquivo lido, relativo a raiz do repositorio"
    faixa = interpretar_faixa(propriedades.get(CAMPO_LINHAS))
    if faixa is None:
        return "'linhas' ausente ou invalida: use '120' ou '120-135', com inicio >= 1 e fim >= inicio"
    trecho = propriedades.get(CAMPO_TRECHO)
    if not isinstance(trecho, str) or not trecho.strip():
        return "falta 'trecho': o texto literal das linhas citadas"
    linhas_do_trecho = contar_linhas(trecho)
    if linhas_do_trecho > faixa.total:
        return (
            f"'trecho' tem {linhas_do_trecho} linhas e a faixa {faixa.inicio}-{faixa.fim} tem {faixa.total}: "
            "o trecho literal cabe na faixa que ele cita"
        )
    return None


@dataclass(frozen=True)
class EvidenciaNoLote:
    """Uma Evidence que o lote cria ou edita, como ela ficará gravada depois dele."""

    id: str
    papel_de_quem_criou: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)

    @property
    def exige_localizacao(self) -> bool:
        """Do planejador, sempre; de qualquer papel, quando cita linhas ou trecho."""
        if self.papel_de_quem_criou == PapelAutor.PLANEJADOR.value:
            return True
        return any(self.propriedades.get(campo) is not None for campo in CAMPOS_QUE_DECLARAM_PONTEIRO)


def projetar_evidencias_do_lote(proposta: PropostaPatch, estado: GrafoEstado) -> tuple[EvidenciaNoLote, ...]:
    """As Evidence que o lote toca, depois de convertidas e aplicadas como o kernel as gravaria.

    Só os nós tocados entram na antevisão, para o custo acompanhar o tamanho do
    lote e não o do grafo. O `add` sobre uma Evidence existente a recria com o
    autor do lote, e o acumulador registra isso como a criação que é.
    """
    tocados = _nos_tocados(proposta)
    if not tocados:
        return ()
    antevisao = AcumuladorProjecao(
        GrafoEstado(nos={id_no: estado.nos[id_no] for id_no in tocados if id_no in estado.nos}, versao_log=estado.versao_log)
    )
    try:
        antevisao.aplicar_todos(ConversorPatchParaEventos().converter(proposta, estado.versao_log))
    except (KeyError, ValueError):
        return ()
    depois = antevisao.congelar()
    nos = (depois.nos.get(id_no) for id_no in tocados)
    return tuple(
        EvidenciaNoLote(id=no.id, papel_de_quem_criou=no.proveniencia.papel, propriedades=no.propriedades)
        for no in nos
        if no is not None and no.tipo == TipoNo.EVIDENCE
    )


def _nos_tocados(proposta: PropostaPatch) -> tuple[str, ...]:
    """Os ids de nó que as operações do lote alcançam, na ordem em que aparecem.

    O id do caminho e o do valor entram os dois: o conversor cria o nó pelo id
    do valor, e um valor com outro id escaparia do julgamento pelo caminho.
    """
    ids: list[str] = []
    for item in proposta.operacoes:
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) < 2 or segmentos[0] != "nos":
            continue
        ids.append(segmentos[1])
        if isinstance(item.value, dict) and "id" in item.value:
            ids.append(str(item.value["id"]))
    return tuple(dict.fromkeys(ids))
