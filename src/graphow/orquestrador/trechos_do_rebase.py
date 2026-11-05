"""Os trechos de um arquivo em conflito em que a fatia aberta pelo rebase tira o que a base nova trouxe (revisão da T3g5).

No arquivo que o rebase deixou em conflito, a mescla da base nova no
resultado (`git merge-tree --merge-base=<base antiga> <base nova>
<resultado>`, sem opção) tem conflito por definição: a resolução difere da
base no trecho em conflito. Ali a fatia pode o que quiser (quem julga é a
revisão); fora dele, não. O conflito da mescla só é aceito quando cai dentro
de um trecho que o rebase deixou em conflito (`arvore_mesclada(HEAD, base)`),
e a linha que a mescla limpa põe no resultado (o que a base mudou e ele não
tem) também. Antes, a mescla com `-Xtheirs` valia para o arquivo inteiro: a
fatia que tirava o cabeçalho da base e mudava a linha colada a ele abria um
conflito novo, que o `-Xtheirs` resolvia a favor do resultado.

Os trechos se comparam em linhas da base nova, o lado que as duas mesclas têm:
o lado da base de cada conflito é texto dela, e o alinhamento
(`difflib`) acha onde ele está nela. O que muda o número das linhas na mescla
fora do conflito (a mudança limpa do Goal ou do resultado) fica fora dele.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

ABRE: str = "<<<<<<<"
ANTIGA: str = "|||||||"
MEIO: str = "======="
FECHA: str = ">>>>>>>"
SECAO_DEPOIS: dict[str, int] = {ABRE: 0, ANTIGA: 2, MEIO: 1}

Trecho = tuple[int, int]
Bloco = tuple[str, int, int, int, int]


@dataclass(frozen=True)
class TextosDoArquivo:
    """Um arquivo em conflito: na base nova, no rebase (a ponta do Goal com a base), no resultado e na mescla da base nele."""

    base: str
    rebase: str
    resultado: str
    mescla: str


@dataclass(frozen=True)
class Resolvida:
    """O texto mesclado com cada conflito resolvido para um lado, e o trecho (início, fim) de cada conflito nas linhas dele."""

    linhas: tuple[str, ...]
    trechos: tuple[Trecho, ...]


def trechos_fora_do_rebase(textos: TextosDoArquivo) -> tuple[str, ...]:
    """Os trechos, em linhas da base nova, em que a mescla tem conflito ou tira linha da base fora dos trechos em conflito do
    rebase; vazio quando a mudança da base fora deles continua no resultado."""
    base = linhas_do_texto(textos.base)
    do_rebase = _na_base(base, resolvida(textos.rebase, lado=1))
    conflitos = [(trecho, "conflito fora do trecho do rebase") for trecho in _na_base(base, resolvida(textos.mescla, lado=0))]
    faltas = [(trecho, "linha da base fora do resultado") for trecho in _faltas(base, textos)]
    return tuple(f"{_nas_linhas(trecho)} da base nova, {motivo}" for trecho, motivo in [*conflitos, *faltas]
                 if not any(inicio <= trecho[0] and trecho[1] <= fim for inicio, fim in do_rebase))


def linhas_do_texto(texto: str) -> tuple[str, ...]:
    """As linhas do texto como o git as conta, cada uma com a quebra (a última pode não ter)."""
    partes = texto.split("\n")
    return tuple([parte + "\n" for parte in partes[:-1]] + ([partes[-1]] if partes[-1] else []))


def resolvida(texto: str, *, lado: int) -> Resolvida:
    """O texto com os marcadores de conflito, com cada conflito resolvido para o lado dado (0, o primeiro da mescla; 1, o
    segundo); a seção da base antiga (o estilo diff3) sai."""
    linhas: list[str] = []
    trechos: list[Trecho] = []
    secao: int | None = None
    inicio = 0
    for linha in linhas_do_texto(texto):
        marcador = _marcador(linha, dentro=secao is not None)
        if not marcador:
            linhas.extend([linha] if secao in (None, lado) else [])
            continue
        if marcador == FECHA:
            trechos.append((inicio, len(linhas)))
        inicio = len(linhas) if marcador == ABRE else inicio
        secao = SECAO_DEPOIS.get(marcador)
    return Resolvida(tuple(linhas), tuple(trechos))


def _marcador(linha: str, *, dentro: bool) -> str:
    """O marcador de conflito que a linha é, ou vazio: o que abre, só fora de um conflito; os outros, só dentro."""
    texto = linha.rstrip("\n")
    if not dentro:
        return ABRE if texto.startswith(ABRE + " ") else ""
    if texto == MEIO:
        return MEIO
    return texto[:7] if texto[:7] in (ANTIGA, FECHA) and texto[7:8] in ("", " ") else ""


def _na_base(base: Sequence[str], mescla: Resolvida) -> tuple[Trecho, ...]:
    """Os trechos dos conflitos da mescla resolvida para o lado da base, nas linhas da base nova."""
    blocos = _blocos(base, mescla.linhas)
    return tuple((_posicao(blocos, inicio, fim=False), _posicao(blocos, fim, fim=True)) for inicio, fim in mescla.trechos)


def _faltas(base: Sequence[str], textos: TextosDoArquivo) -> tuple[Trecho, ...]:
    """Os trechos, nas linhas da base nova, em que a mescla limpa põe no resultado o que a base mudou e ele não tem.

    Com cada conflito resolvido para o resultado, a mescla só difere dele
    onde a base mudou sem conflito; esse texto é dela, e o alinhamento com a
    base nova dá as linhas.
    """
    com_o_resultado = resolvida(textos.mescla, lado=1).linhas
    blocos = _blocos(base, com_o_resultado)
    diferencas = [(j1, j2) for tag, _i1, _i2, j1, j2 in _blocos(linhas_do_texto(textos.resultado), com_o_resultado)
                  if tag != "equal"]
    return tuple((_posicao(blocos, inicio, fim=False), _posicao(blocos, fim, fim=True)) for inicio, fim in diferencas)


def _blocos(antes: Sequence[str], depois: Sequence[str]) -> list[Bloco]:
    """O alinhamento das linhas, em blocos (tag, i1, i2, j1, j2) do `difflib`, sem o descarte das linhas frequentes."""
    return SequenceMatcher(None, antes, depois, autojunk=False).get_opcodes()


def _posicao(blocos: Sequence[Bloco], posicao: int, *, fim: bool) -> int:
    """A posição no segundo lado do alinhamento, no primeiro: num bloco igual, a mesma linha; no meio de um bloco diferente,
    a borda dele que alarga o trecho (a de antes no começo, a de depois no fim)."""
    iguais = [i1 + posicao - j1 for tag, i1, _i2, j1, j2 in blocos if tag == "equal" and j1 <= posicao <= j2]
    bordas = [i2 if fim else i1 for _tag, i1, i2, j1, j2 in blocos if j1 <= posicao <= j2]
    candidatas = iguais or bordas or [0]
    return max(candidatas) if fim else min(candidatas)


def _nas_linhas(trecho: Trecho) -> str:
    """O trecho em linhas contadas de 1: `linha 3`, `linhas 1 a 4`; o vazio, o ponto antes da linha seguinte."""
    inicio, fim = trecho
    if fim <= inicio:
        return f"antes da linha {inicio + 1}"
    return f"linha {fim}" if fim == inicio + 1 else f"linhas {inicio + 1} a {fim}"
