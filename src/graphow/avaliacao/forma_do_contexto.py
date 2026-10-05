"""A forma do contexto dos Run, somada para o relatório: peso por turno, saídas grandes, pausas e leituras fora do alvo.

O harness grava, por Run, a forma do contexto lida da transcrição (ver
harness/forma_da_transcricao.py). Aqui ela se agrega para um Goal ou para um
lote de transcrições: a média de contexto é ponderada pelos turnos de cada Run,
porque um Run de 240 turnos pesa mais que um de 10; os picos ficam no máximo;
as contagens se somam. As saídas grandes se somam também por ferramenta, e o
relatório mostra as três que mais deram.

As leituras fora do alvo comparam os caminhos que o Run leu com os
`arquivos_alvo` das Tasks que ele assumiu e o `arquivo` das Evidence derivadas
delas, pelo Read, Grep e Glob e pelos comandos de shell reconhecidos. O
casamento é por sufixo do caminho normalizado: barra normal, sem `./`,
sem diferença de maiúsculas (o Windows não distingue, e a transcrição grava o
caminho absoluto enquanto o alvo é relativo à raiz do repositório). O alvo que é
pasta casa com o que estiver dentro dela. Sem Task conhecida ou sem alvo, a
contagem fica de fora em vez de virar zero.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from graphow.core.orquestracao import CAMPO_ARQUIVOS_ALVO, ler_texto, ler_textos
from graphow.core.types import TipoAresta, TipoNo
from graphow.harness.forma_da_transcricao import (
    CAMPO_CAMINHOS_LIDOS,
    CAMPO_CAMINHOS_LIDOS_SHELL,
    CAMPO_CONTEXTO_MAXIMO,
    CAMPO_CONTEXTO_MEDIO,
    CAMPO_MAIOR_PAUSA,
    CAMPO_MAIOR_SAIDA,
    CAMPO_PAUSAS_LONGAS,
    CAMPO_SAIDAS_GRANDES,
    CAMPO_SAIDAS_GRANDES_POR_FERRAMENTA,
)
from graphow.harness.transcricao import CHAVES_DE_USO
from graphow.projection.graph_view import GrafoView

CAMPO_ARQUIVO_DA_EVIDENCIA: str = "arquivo"
CAMPO_TURNOS: str = "mensagens_de_modelo"
CAMPOS_DA_FORMA: tuple[str, ...] = (
    CAMPO_CONTEXTO_MEDIO, CAMPO_MAIOR_SAIDA, CAMPO_MAIOR_PAUSA, CAMPO_CAMINHOS_LIDOS, CAMPO_CAMINHOS_LIDOS_SHELL,
)
RUNS_MAIS_CAROS: int = 3
FERRAMENTAS_MOSTRADAS: int = 3
SEGUNDOS_POR_MINUTO: int = 60


@dataclass(frozen=True)
class FormaAgregada:
    """A forma do contexto de vários Run: médias ponderadas pelos turnos, picos e somas."""

    contexto_medio: int | None = None
    contexto_maximo: int | None = None
    turnos_maximo: int | None = None
    maior_saida: int | None = None
    saidas_grandes: int = 0
    pausas_longas: int = 0
    maior_pausa_s: int | None = None
    leituras_fora_do_alvo: int | None = None
    saidas_grandes_por_ferramenta: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RunCaro:
    """Um Run pelo que custou: quem, quanto, quanto tempo, quantos turnos e o contexto médio."""

    agente: str
    tokens: int
    duracao_s: int | None
    turnos: int
    contexto_medio: int | None


def agregar_forma(runs: Iterable[tuple[Mapping[str, Any], int | None]]) -> FormaAgregada | None:
    """A forma somada dos Run, cada um com as suas leituras fora do alvo; None quando nenhum traz forma."""
    pares = [(propriedades, fora) for propriedades, fora in runs if any(campo in propriedades for campo in CAMPOS_DA_FORMA)]
    if not pares:
        return None
    com_contexto = [(_inteiro(p.get(CAMPO_CONTEXTO_MEDIO)), _inteiro(p.get(CAMPO_TURNOS))) for p, _ in pares if CAMPO_CONTEXTO_MEDIO in p]
    pesos = sum(max(turnos, 1) for _, turnos in com_contexto)
    foras = [fora for _, fora in pares if fora is not None]
    return FormaAgregada(
        contexto_medio=sum(medio * max(turnos, 1) for medio, turnos in com_contexto) // pesos if pesos else None,
        contexto_maximo=_maximo(p.get(CAMPO_CONTEXTO_MAXIMO) for p, _ in pares),
        turnos_maximo=_maximo(p.get(CAMPO_TURNOS) for p, _ in pares if CAMPO_CONTEXTO_MEDIO in p),
        maior_saida=_maximo(p.get(CAMPO_MAIOR_SAIDA) for p, _ in pares),
        saidas_grandes=sum(_inteiro(p.get(CAMPO_SAIDAS_GRANDES)) for p, _ in pares),
        pausas_longas=sum(_inteiro(p.get(CAMPO_PAUSAS_LONGAS)) for p, _ in pares),
        maior_pausa_s=_maximo(p.get(CAMPO_MAIOR_PAUSA) for p, _ in pares),
        leituras_fora_do_alvo=sum(foras) if foras else None,
        saidas_grandes_por_ferramenta=_somar_por_ferramenta(p.get(CAMPO_SAIDAS_GRANDES_POR_FERRAMENTA) for p, _ in pares),
    )


def formatar_forma(forma: FormaAgregada) -> str:
    """A linha da forma do contexto, cada trecho só quando o dado existe."""
    trechos = []
    if forma.contexto_medio is not None:
        trechos.append(f"medio/turno {_numero(forma.contexto_medio)}, maximo {_numero(forma.contexto_maximo or 0)}")
    if forma.turnos_maximo is not None:
        trechos.append(f"turnos max {forma.turnos_maximo}")
    if forma.maior_saida is not None:
        trechos.append(f"maior saida {_numero(forma.maior_saida)} car, {forma.saidas_grandes} saidas >2k")
    if forma.saidas_grandes_por_ferramenta:
        trechos.append(">2k: " + ", ".join(f"{nome} {total}" for nome, total in _mais_frequentes(forma.saidas_grandes_por_ferramenta)))
    if forma.maior_pausa_s is not None:
        trechos.append(f"{forma.pausas_longas} pausas >5min (maior {_minutos(forma.maior_pausa_s)})")
    if forma.leituras_fora_do_alvo is not None:
        trechos.append(f"{forma.leituras_fora_do_alvo} leituras fora do alvo")
    return "contexto: " + " | ".join(trechos)


def runs_mais_caros(runs: Iterable[Mapping[str, Any]], quantos: int = RUNS_MAIS_CAROS) -> tuple[RunCaro, ...]:
    """Os Run de maior custo em tokens, do mais caro ao mais barato; os sem token ficam de fora."""
    caros = (
        RunCaro(
            agente=ler_texto(propriedades, "agente") or "orquestrador",
            tokens=tokens_do_run(propriedades),
            duracao_s=propriedades.get("duracao_s") if isinstance(propriedades.get("duracao_s"), int) else None,
            turnos=_inteiro(propriedades.get(CAMPO_TURNOS)),
            contexto_medio=propriedades.get(CAMPO_CONTEXTO_MEDIO) if isinstance(propriedades.get(CAMPO_CONTEXTO_MEDIO), int) else None,
        )
        for propriedades in runs
    )
    return tuple(sorted((run for run in caros if run.tokens), key=lambda run: -run.tokens)[:quantos])


def formatar_run_caro(run: RunCaro) -> str:
    """O Run caro numa frase: agente, tokens, duração, turnos e contexto médio."""
    duracao = _minutos(run.duracao_s) if run.duracao_s is not None else "sem duracao"
    contexto = f", contexto medio {_numero(run.contexto_medio)}" if run.contexto_medio is not None else ""
    return f"{run.agente} {_numero(run.tokens)} tokens, {duracao}, {run.turnos} turnos{contexto}"


def leituras_fora_do_run(propriedades: Mapping[str, Any], view: GrafoView) -> int | None:
    """Quantos caminhos lidos pelo Run caem fora do alvo das Tasks que ele assumiu; None sem Task ou sem alvo."""
    tarefas = ler_textos(propriedades.get("tarefas"))
    caminhos = caminhos_lidos(propriedades)
    if not tarefas or not caminhos:
        return None
    return contar_fora_do_alvo(caminhos, alvos_das_tarefas(view, tarefas))


def caminhos_lidos(propriedades: Mapping[str, Any]) -> tuple[str, ...]:
    """Os caminhos lidos pelas ferramentas de leitura e pelo shell, sem repetição."""
    return tuple(dict.fromkeys(ler_textos(propriedades.get(CAMPO_CAMINHOS_LIDOS)) + ler_textos(propriedades.get(CAMPO_CAMINHOS_LIDOS_SHELL))))


def alvos_das_tarefas(view: GrafoView, ids_tarefas: Iterable[str]) -> tuple[str, ...]:
    """Os `arquivos_alvo` das Tasks e o `arquivo` das Evidence derivadas delas; vazio quando nenhuma existe."""
    alvos: list[str] = []
    for id_task in ids_tarefas:
        tarefa = view.obter_no(id_task)
        if tarefa is None:
            continue
        alvos.extend(ler_textos(tarefa.propriedades.get(CAMPO_ARQUIVOS_ALVO)))
        alvos.extend(_arquivos_das_evidencias(view, id_task))
    return tuple(dict.fromkeys(alvos))


def contar_fora_do_alvo(caminhos: Iterable[str], alvos: Iterable[str]) -> int | None:
    """Quantos caminhos não casam com alvo nenhum; None quando não há alvo contra o qual medir."""
    normalizados = tuple(alvo for alvo in (normalizar_caminho_lido(alvo) for alvo in alvos) if alvo)
    if not normalizados:
        return None
    return sum(1 for caminho in caminhos if not any(casa_com_alvo(caminho, alvo) for alvo in normalizados))


def casa_com_alvo(caminho: str, alvo: str) -> bool:
    """O caminho lido é o alvo, termina nele, é o sufixo dele ou está dentro da pasta que ele nomeia."""
    lido, alvo = normalizar_caminho_lido(caminho), normalizar_caminho_lido(alvo)
    if not lido or not alvo:
        return False
    return lido == alvo or lido.endswith("/" + alvo) or alvo.endswith("/" + lido) or f"/{alvo}/" in f"/{lido}"


def normalizar_caminho_lido(caminho: str) -> str:
    """Barra normal, sem `./` na frente nem barra no fim, em minúsculas: a forma em que dois caminhos se comparam."""
    limpo = caminho.strip().replace("\\", "/").casefold()
    while limpo.startswith("./"):
        limpo = limpo[2:]
    return limpo.rstrip("/")


def tokens_do_run(propriedades: Mapping[str, Any]) -> int:
    """A soma das quatro categorias de token; zero quando o Run não traz nenhuma."""
    return sum(_inteiro(propriedades.get(campo)) for campo in CHAVES_DE_USO.values())


def _arquivos_das_evidencias(view: GrafoView, id_task: str) -> tuple[str, ...]:
    """O `arquivo` de cada Evidence que deriva da Task."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE))
    return tuple(
        ler_texto(no.propriedades, CAMPO_ARQUIVO_DA_EVIDENCIA)
        for no in origens
        if no is not None and no.tipo == TipoNo.EVIDENCE and ler_texto(no.propriedades, CAMPO_ARQUIVO_DA_EVIDENCIA)
    )


def _somar_por_ferramenta(contagens: Iterable[object]) -> dict[str, int]:
    """A soma das contagens por ferramenta dos Run; o que não é contagem se ignora."""
    total: Counter[str] = Counter()
    for contagem in contagens:
        if isinstance(contagem, Mapping):
            total.update({str(nome): _inteiro(valor) for nome, valor in contagem.items()})
    return dict(total.most_common())


def _mais_frequentes(contagem: Mapping[str, int]) -> list[tuple[str, int]]:
    """As ferramentas que mais deram saída grande, da maior à menor, empate por nome."""
    return sorted(contagem.items(), key=lambda par: (-par[1], par[0]))[:FERRAMENTAS_MOSTRADAS]


def _maximo(valores: Iterable[object]) -> int | None:
    """O maior dos inteiros; None quando nenhum valor é inteiro."""
    inteiros = [valor for valor in valores if isinstance(valor, int) and not isinstance(valor, bool)]
    return max(inteiros) if inteiros else None


def _minutos(segundos: int) -> str:
    """Segundos em minutos arredondados."""
    return f"{round(segundos / SEGUNDOS_POR_MINUTO)} min"


def _numero(valor: int) -> str:
    """Inteiro com separador de milhar."""
    return f"{valor:,}".replace(",", ".")


def _inteiro(valor: object) -> int:
    """Contagem como inteiro; o que não é número conta zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
