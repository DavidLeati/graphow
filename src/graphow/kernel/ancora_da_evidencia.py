"""A âncora da Evidence sobre código: o commit em que o fato foi visto e os arquivos que ela afirma.

Na auditoria, 8 de 10 Evidence da api já não batiam com os arquivos 20
minutos depois, e o grafo não tinha como saber. A Evidence sobre código nasce
com o `commit` em que foi verificada, para quem a lê conferir se os arquivos
que ela afirma mudaram desde ele (orquestrador/conferencia_da_evidencia.py).

É sobre código:
- toda Evidence do papel orquestrador: o laço só roda num repositório git, e
  as dele (a verificação, a revisão de risco, o rebase) afirmam o que o código
  é num commit;
- a Evidence de qualquer papel com a localização de arquivo de
  kernel/localizacao.py (`arquivo` e `linhas`): o trecho lido mora num arquivo,
  e o arquivo muda. O `arquivo` sozinho (o log de teste, o relatório anexado)
  e a fonte genérica seguem livres.

A âncora é o `commit`, com 40 caracteres hexadecimais (64 no repositório
sha256). A Evidence localizada num arquivo fora de repositório git (a ata, a
planilha: decisão 1 do BRIEF) ancora no `sha256` do conteúdo dele; a do
orquestrador, só no commit. Os arquivos que ela afirma são os `arquivos` que
o orquestrador grava ou, na localizada, o `arquivo` dela
(`arquivos_afirmados`); sem nenhum, ela fala do commit inteiro.

Como a âncora do Artifact (kernel/ancora_do_artifact.py), o portão não lê o
git: garante a forma que torna a conferência possível e julga a Evidence como
ela vai ficar depois do lote. A regra vale para a Evidence que o lote cria (ou
recria por `add`) e para a que já tinha âncora, que não a perde; a Evidence
antiga, sem âncora, segue editável, e o replay do log não passa pelos portões.
"""

from collections.abc import Mapping
import re
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.orquestracao import ler_texto
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.ancora_do_artifact import ANCORA_COMMIT, ANCORA_SHA256, PADRAO_DO_COMMIT, PADRAO_DO_SHA256, recriados_pelo_lote
from graphow.kernel.localizacao import CAMPO_ARQUIVO, CAMPO_LINHAS, projetar_nos_do_lote
from graphow.kernel.patch_models import PropostaPatch, ResultadoValidacao

CAMPO_COMMIT: str = "commit"
CAMPO_SHA256: str = "sha256"
CAMPO_ARQUIVOS: str = "arquivos"
FORMA_DA_ANCORA: str = (
    "A Evidence sobre codigo (a do orquestrador e a localizada num arquivo, com 'arquivo' e 'linhas') leva 'commit': "
    "o hash do commit em que o fato foi visto (git rev-parse HEAD), 40 caracteres hexadecimais ou 64 no repositorio "
    "sha256. A localizada num arquivo fora de repositorio git leva, no lugar dele, 'sha256': os 64 caracteres "
    "hexadecimais do conteudo do arquivo"
)


def _valido(padrao: re.Pattern[str], valor: object) -> bool:
    """O valor é texto e casa inteiro com o padrão."""
    return isinstance(valor, str) and padrao.fullmatch(valor) is not None


def ancora_da_evidencia(propriedades: Mapping[str, Any]) -> str | None:
    """`commit`, `sha256` (só com `arquivo`) ou None, quando a Evidence não tem âncora válida."""
    if _valido(PADRAO_DO_COMMIT, propriedades.get(CAMPO_COMMIT)):
        return ANCORA_COMMIT
    if _valido(PADRAO_DO_SHA256, propriedades.get(CAMPO_SHA256)) and ler_texto(propriedades, CAMPO_ARQUIVO):
        return ANCORA_SHA256
    return None


def arquivos_afirmados(propriedades: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Os `arquivos` gravados ou o `arquivo` da localizada; None quando a Evidence fala do commit inteiro."""
    lista = propriedades.get(CAMPO_ARQUIVOS)
    if isinstance(lista, list):
        return tuple(str(item) for item in lista if str(item).strip())
    arquivo = ler_texto(propriedades, CAMPO_ARQUIVO)
    return (arquivo,) if arquivo else None


def sobre_codigo(papel_de_quem_criou: str, propriedades: Mapping[str, Any]) -> bool:
    """Do orquestrador, sempre; de qualquer papel, quando localizada num arquivo (`arquivo` e `linhas`)."""
    if papel_de_quem_criou == PapelAutor.ORQUESTRADOR.value:
        return True
    return bool(ler_texto(propriedades, CAMPO_ARQUIVO)) and propriedades.get(CAMPO_LINHAS) is not None


def diagnosticar_ancora_da_evidencia(papel_de_quem_criou: str, propriedades: Mapping[str, Any]) -> str | None:
    """O que falta ou está errado na âncora da Evidence sobre código; None quando ela vale."""
    ancora = ancora_da_evidencia(propriedades)
    do_orquestrador = papel_de_quem_criou == PapelAutor.ORQUESTRADOR.value
    if ancora == ANCORA_COMMIT or (ancora == ANCORA_SHA256 and not do_orquestrador):
        return None
    commit = propriedades.get(CAMPO_COMMIT)
    if commit not in (None, ""):
        return f"'commit' {commit!r} nao e um hash de commit do git (40 ou 64 caracteres hexadecimais)"
    sha256 = propriedades.get(CAMPO_SHA256)
    if sha256 not in (None, "") and not do_orquestrador and not _valido(PADRAO_DO_SHA256, sha256):
        return f"'sha256' {sha256!r} nao tem 64 caracteres hexadecimais"
    return "falta 'commit'" if do_orquestrador else "falta 'commit' ou, fora de repositorio git, 'sha256'"


def validar_ancora_da_evidencia(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Recusa a Evidence sobre código que o lote deixaria sem âncora."""
    recriados = recriados_pelo_lote(proposta)
    for no in projetar_nos_do_lote(proposta, estado):
        if no.tipo != TipoNo.EVIDENCE or _antiga_sem_ancora(no.id, estado, recriados=recriados):
            continue
        papel = no.proveniencia.papel
        problema = diagnosticar_ancora_da_evidencia(papel, no.propriedades) if sobre_codigo(papel, no.propriedades) else None
        if problema is not None:
            return ResultadoValidacao.falha(
                f"Evidence '{no.id}' sem ancora: {problema}. {FORMA_DA_ANCORA}",
                "InvariantGate",
                {"id_no": no.id, "papel_de_quem_criou": papel},
                modo=ModoFalhaMAST.EVIDENCIA_SEM_ANCORA,
            )
    return ResultadoValidacao.sucesso()


def _antiga_sem_ancora(id_no: str, estado: GrafoEstado, *, recriados: frozenset[str]) -> bool:
    """A Evidence gravada antes da regra, sem âncora, que o lote edita sem recriar: segue livre."""
    anterior = estado.nos.get(id_no)
    if anterior is None or anterior.tipo != TipoNo.EVIDENCE or id_no in recriados:
        return False
    return ancora_da_evidencia(anterior.propriedades) is None
