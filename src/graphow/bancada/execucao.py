"""`graphow bancada rodar`: monta a execução, roda a arquitetura e grava `execucao.json`.

Cada execução é uma pasta `<arquitetura>-<projeto>-<carimbo>` com o repositório
recriado da semente, a spec ao lado dele (o prompt a referencia por
`../spec-<projeto>.md`, fora do repositório, como no laboratório), um banco
graphow próprio para os hooks e a pasta das sessões. `todos` roda os três
projetos em paralelo, cada um na sua pasta; a falha de um fica gravada no
`execucao.json` dele e não derruba os outros.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from graphow.bancada.arquiteturas import Arquitetura, PedidoDeExecucao
from graphow.bancada.entrega import ler_estado_da_entrega
from graphow.bancada.medicao import Invocacao, medir
from graphow.bancada.projetos import Bancada, ErroDaBancada, ProjetoDaBancada
from graphow.bancada.semente import criar_repositorio
from graphow.core.exceptions import GraphowError
from graphow.sessoes.pedido import TEMPO_LIMITE_PADRAO_S
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao, em_iso

ARQUIVO_DA_EXECUCAO: str = "execucao.json"
NOME_DO_BANCO: str = "graphow.db"
VERSAO_DO_REGISTRO: int = 1
FORMATO_DO_CARIMBO: str = "%Y%m%d-%H%M%S"


@dataclass(frozen=True)
class ConfiguracaoDaRodada:
    """O que vale para todas as execuções de uma rodada: onde gravar, de onde ler e quanto esperar."""

    bancada: Bancada
    saida: Path
    raiz_das_transcricoes: Path | None
    tempo_limite_s: float = TEMPO_LIMITE_PADRAO_S
    carimbo: str = field(default_factory=lambda: _agora().strftime(FORMATO_DO_CARIMBO))


@dataclass(frozen=True)
class ExecucaoGravada:
    """Uma execução terminada: a pasta dela e o que foi gravado em `execucao.json`."""

    diretorio: Path
    registro: dict[str, Any]


def montar_execucao(arquitetura: str, projeto: ProjetoDaBancada, configuracao: ConfiguracaoDaRodada) -> PedidoDeExecucao:
    """A pasta da execução, com o repositório da semente, a spec ao lado e o caminho do banco."""
    diretorio = configuracao.saida / f"{arquitetura}-{projeto.nome}-{configuracao.carimbo}"
    if diretorio.exists():
        raise ErroDaBancada("a pasta da execucao ja existe", {"execucao": str(diretorio)})
    diretorio.mkdir(parents=True)
    repositorio = diretorio / projeto.nome
    criar_repositorio(projeto, repositorio)
    spec = diretorio / f"spec-{projeto.nome}.md"
    shutil.copyfile(projeto.spec, spec)
    return PedidoDeExecucao(
        projeto=projeto,
        bancada=configuracao.bancada,
        diretorio=diretorio,
        repositorio=repositorio,
        spec=spec,
        banco=diretorio / NOME_DO_BANCO,
        tempo_limite_s=configuracao.tempo_limite_s,
    )


def rodar_execucao(
    arquitetura: Arquitetura, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao, *, transcricoes: Path | None
) -> ExecucaoGravada:
    """Roda a arquitetura na execução montada, mede e grava `execucao.json`."""
    inicio = _agora()
    resultados, erro = _executar(arquitetura, pedido, sessoes)
    erro = erro or erros_das_sessoes(resultados)
    invocacoes = tuple(Invocacao(r.session_id, r.inicio, r.fim, r.leitura.resultado) for r in resultados)
    medicao = medir(invocacoes, transcricoes).em_dicionario()
    entrega = ler_estado_da_entrega(pedido.repositorio, pedido.projeto)
    registro = {
        "versao": VERSAO_DO_REGISTRO,
        "arquitetura": arquitetura.nome,
        "projeto": pedido.projeto.nome,
        "repositorio": pedido.repositorio.name,
        "spec": pedido.spec.name,
        "banco": pedido.banco.name,
        "semente": pedido.projeto.semente.commit,
        "inicio": em_iso(inicio),
        "fim": em_iso(_agora()),
        "erro": erro,
        "metricas": {**medicao, "commits": entrega.commits},
        "entrega": entrega.em_dicionario(),
        "sessoes": [resultado.em_dicionario() for resultado in resultados],
    }
    gravar_json(pedido.diretorio / ARQUIVO_DA_EXECUCAO, registro)
    return ExecucaoGravada(pedido.diretorio, registro)


def rodar_projetos(
    arquitetura: Callable[[], Arquitetura],
    projetos: Sequence[ProjetoDaBancada],
    configuracao: ConfiguracaoDaRodada,
    *,
    sessoes: ExecutorDeSessao,
) -> tuple[ExecucaoGravada, ...]:
    """Cada projeto na sua execução; mais de um roda em paralelo, um por linha de execução."""
    nome = arquitetura().nome
    pedidos = [montar_execucao(nome, projeto, configuracao) for projeto in projetos]

    def rodar(pedido: PedidoDeExecucao) -> ExecucaoGravada:
        return rodar_execucao(arquitetura(), pedido, sessoes, transcricoes=configuracao.raiz_das_transcricoes)

    with ThreadPoolExecutor(max_workers=max(1, len(pedidos))) as paralelo:
        return tuple(paralelo.map(rodar, pedidos))


def erros_das_sessoes(resultados: Sequence[ResultadoDeSessao]) -> str:
    """Cada sessão que deu errado e por quê; vazio quando todas terminaram bem."""
    return "; ".join(
        f"sessao {resultado.session_id or '?'} terminou com erro: {resultado.motivo_do_erro}"
        for resultado in resultados
        if resultado.is_error
    )


def gravar_json(caminho: Path, dados: dict[str, Any]) -> None:
    """O registro em JSON legível, UTF-8 e fim de linha LF."""
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def ler_json(caminho: Path) -> dict[str, Any]:
    """Um registro da bancada; ausente ou ilegível recusa com o caminho."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ErroDaBancada("registro da bancada ausente ou ilegivel", {"arquivo": str(caminho), "erro": str(erro)}) from erro
    if not isinstance(dados, dict):
        raise ErroDaBancada("registro da bancada nao e um objeto JSON", {"arquivo": str(caminho)})
    return dados


def _executar(arquitetura: Arquitetura, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[tuple[ResultadoDeSessao, ...], str]:
    """As sessões que a arquitetura rodou, ou nenhuma e o erro que a impediu."""
    try:
        return arquitetura.executar(pedido, sessoes), ""
    except GraphowError as erro:
        return (), erro.formatar_para_llm()


def _agora() -> datetime:
    """O relógio da máquina, com fuso."""
    return datetime.now(timezone.utc).astimezone()
