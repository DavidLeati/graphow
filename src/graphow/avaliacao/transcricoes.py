"""`graphow transcricao-medir`: a forma do contexto lida direto das transcrições, sem passar pelo banco.

Os Run gravados antes da forma do contexto não a têm, e reler o harness sobre
eles escreveria no banco. A linha de base sai então das transcrições em disco:
uma linha por transcrição, da mais cara à mais barata, com tokens, duração,
turnos, contexto por turno, saídas de ferramenta grandes, pausas longas e
leituras fora do alvo, e um agregado de todas no fim.

O banco só é lido, e numa cópia em memória: o `SQLiteEventStore` acerta pragma
e esquema ao abrir, o que é escrita no arquivo do usuário. Sem banco, ou com a
Task assumida ausente dele, as leituras fora do alvo ficam de fora.
"""

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import sqlite3
from typing import Any

from graphow.avaliacao.forma_do_contexto import (
    agregar_forma,
    caminhos_lidos,
    formatar_forma,
    leituras_fora_do_run,
    tokens_do_run,
)
from graphow.harness.transcricao import CHAVES_DE_USO, ler_consumo
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.projection.graph_view import GrafoView
from graphow.storage.sqlite_store import SQLiteEventStore

EXTENSAO_DE_TRANSCRICAO: str = ".jsonl"
SUFIXO_DOS_METADADOS: str = ".meta.json"
CAMPO_TIPO_DO_AGENTE: str = "agentType"
PASTA_DE_SUBAGENTES: str = "subagents"
CARACTERES_DA_SESSAO: int = 8
TOP_PADRAO: int = 20
SEM_TRANSCRICOES: str = "Nenhuma transcricao legivel: nada a medir."
CAMPO_CACHE_LEITURA: str = CHAVES_DE_USO["cache_read_input_tokens"]


@dataclass(frozen=True)
class MedicaoDeTranscricao:
    """Uma transcrição medida: de onde veio, quem a escreveu, as propriedades que viraria no Run e as leituras fora do alvo."""

    rotulo: str
    agente: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    leituras_fora_do_alvo: int | None = None

    @property
    def tokens(self) -> int:
        """O custo em tokens, as quatro categorias somadas."""
        return tokens_do_run(self.propriedades)


def coletar_transcricoes(entradas: Iterable[Path]) -> tuple[tuple[Path, str], ...]:
    """Cada transcrição com o rótulo que o relatório mostra; a pasta é varrida por inteiro."""
    return tuple(dict.fromkeys(achada for entrada in entradas for achada in _transcricoes_em(entrada)))


def _transcricoes_em(entrada: Path) -> tuple[tuple[Path, str], ...]:
    """O arquivo pedido, ou toda transcrição abaixo da pasta pedida; o que não existe não dá nada."""
    if entrada.is_file():
        return ((entrada, entrada.name),)
    if not entrada.is_dir():
        return ()
    return tuple((caminho, _rotulo(caminho, entrada)) for caminho in sorted(entrada.rglob(f"*{EXTENSAO_DE_TRANSCRICAO}")))


def medir_transcricoes(transcricoes: Iterable[tuple[Path, str]], view: GrafoView | None) -> tuple[MedicaoDeTranscricao, ...]:
    """A medição de cada transcrição legível, da mais cara à mais barata."""
    medicoes = []
    for caminho, rotulo in transcricoes:
        consumo = ler_consumo(caminho)
        if consumo is None:
            continue
        propriedades = consumo.em_propriedades()
        fora = leituras_fora_do_run(propriedades, view) if view is not None else None
        medicoes.append(MedicaoDeTranscricao(rotulo, _agente(caminho), propriedades, fora))
    return tuple(sorted(medicoes, key=lambda medicao: -medicao.tokens))


def formatar_transcricoes(medicoes: tuple[MedicaoDeTranscricao, ...], top: int = TOP_PADRAO) -> tuple[str, ...]:
    """As `top` transcrições mais caras, uma por linha, e o agregado de todas."""
    if not medicoes:
        return (SEM_TRANSCRICOES,)
    linhas = [f"Transcricoes: {len(medicoes)} lidas; as {min(top, len(medicoes))} mais caras:"]
    linhas.extend(_linha(medicao) for medicao in medicoes[:top])
    linhas.extend(("", *_agregado(medicoes)))
    return tuple(linhas)


@contextmanager
def vista_somente_leitura(caminho: Path | None) -> Iterator[GrafoView | None]:
    """A vista do ramo principal sobre uma cópia em memória do banco; None quando o banco não existe."""
    if caminho is None or not caminho.is_file():
        yield None
        return
    origem = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
    with SQLiteEventStore(":memory:") as copia:
        try:
            origem.backup(copia.conexao)
        finally:
            origem.close()
        yield montar_kernel_sqlite(copia).obter_view()


def _linha(medicao: MedicaoDeTranscricao) -> str:
    """Uma transcrição: rótulo, agente, tokens, duração, turnos e a forma do contexto; os turnos máximos só no agregado."""
    propriedades = medicao.propriedades
    duracao = propriedades.get("duracao_s")
    tempo = f"{round(duracao / 60)} min" if isinstance(duracao, int) else "sem duracao"
    forma = agregar_forma(((propriedades, medicao.leituras_fora_do_alvo),))
    lidos = len(caminhos_lidos(propriedades))
    return (
        f"  {medicao.rotulo} [{medicao.agente}] | tokens {_numero(medicao.tokens)}"
        f" (sem cache {_numero(medicao.tokens - _cache(propriedades))}) | {tempo}"
        f" | {propriedades.get('mensagens_de_modelo', 0)} turnos"
        + (f" | {formatar_forma(replace(forma, turnos_maximo=None))}" if forma is not None else "")
        + (f" | {lidos} caminhos lidos" if lidos else "")
    )


def _agregado(medicoes: tuple[MedicaoDeTranscricao, ...]) -> tuple[str, ...]:
    """O total de todas as transcrições lidas, não só das mostradas."""
    tokens = sum(medicao.tokens for medicao in medicoes)
    sem_cache = tokens - sum(_cache(medicao.propriedades) for medicao in medicoes)
    duracoes = [medicao.propriedades["duracao_s"] for medicao in medicoes if isinstance(medicao.propriedades.get("duracao_s"), int)]
    forma = agregar_forma((medicao.propriedades, medicao.leituras_fora_do_alvo) for medicao in medicoes)
    linhas = [
        f"Agregado: {len(medicoes)} transcricoes | tokens {_numero(tokens)} (sem cache {_numero(sem_cache)})"
        f" | {round(sum(duracoes) / 60)} min somados"
        f" | {sum(int(medicao.propriedades.get('mensagens_de_modelo', 0)) for medicao in medicoes)} turnos",
    ]
    if forma is not None:
        linhas.append(f"  {formatar_forma(forma)}")
    medidas = sum(1 for medicao in medicoes if medicao.leituras_fora_do_alvo is not None)
    linhas.append(f"  leituras fora do alvo medidas em {medidas} de {len(medicoes)} transcricoes")
    return tuple(linhas)


def _rotulo(caminho: Path, raiz: Path) -> str:
    """O caminho relativo à pasta pedida; o do subagente vira `<sessao abreviada>/<agente>`."""
    if caminho.parent.name == PASTA_DE_SUBAGENTES:
        return f"{caminho.parent.parent.name[:CARACTERES_DA_SESSAO]}/{caminho.stem}"
    return caminho.relative_to(raiz).as_posix()


def _agente(caminho: Path) -> str:
    """O tipo do subagente, lido dos metadados ao lado da transcrição; `principal` sem eles."""
    metadados = caminho.with_name(caminho.stem + SUFIXO_DOS_METADADOS)
    try:
        dados = json.loads(metadados.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "principal"
    tipo = dados.get(CAMPO_TIPO_DO_AGENTE) if isinstance(dados, dict) else None
    return str(tipo) if tipo else "subagente"


def _cache(propriedades: Mapping[str, Any]) -> int:
    """Os tokens de leitura de cache do Run."""
    valor = propriedades.get(CAMPO_CACHE_LEITURA)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


def _numero(valor: int) -> str:
    """Inteiro com separador de milhar."""
    return f"{valor:,}".replace(",", ".")
