"""`graphow bancada rodar`: monta a execução, roda a arquitetura e grava `execucao.json`.

Cada execução é uma pasta `<arquitetura>-<projeto>-<carimbo>` com o repositório
recriado da semente, a spec ao lado dele (o prompt a referencia por
`../spec-<projeto>.md`, fora do repositório, como no laboratório), um banco
graphow próprio para os hooks e a pasta das sessões.

`todos` roda os três projetos em paralelo, e cada um fica isolado dos outros.
Montar o repositório, rodar a arquitetura, medir e ler o estado git acontecem
na linha de execução do projeto, numa `ExecucaoEmAndamento` preenchida etapa a
etapa. A falha de domínio da arquitetura ou do git vira erro na hora, e a
execução segue até o fim; a falha de qualquer outro tipo para a linha de
execução, que a devolve. Nos dois casos o `execucao.json` do projeto é gravado
com o erro e com o que já se sabia (as sessões, a medição, a entrega), e os
outros projetos seguem.
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
from graphow.bancada.entrega import EstadoDaEntrega, ler_estado_da_entrega
from graphow.bancada.medicao import Invocacao, Medicao, medir
from graphow.bancada.projetos import Bancada, ErroDaBancada, ProjetoDaBancada
from graphow.bancada.semente import criar_repositorio
from graphow.core.exceptions import GraphowError
from graphow.sessoes.pedido import TEMPO_LIMITE_PADRAO_S
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao, em_iso

ARQUIVO_DA_EXECUCAO: str = "execucao.json"
NOME_DO_BANCO: str = "graphow.db"
VERSAO_DO_REGISTRO: int = 1
FORMATO_DO_CARIMBO: str = "%Y%m%d-%H%M%S"
SEPARADOR_DE_ERROS: str = "; "


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


class ExecucaoEmAndamento:
    """Uma execução de um projeto, preenchida etapa a etapa: a falha de qualquer etapa grava o que já se sabia."""

    def __init__(self, arquitetura: str, projeto: ProjetoDaBancada, configuracao: ConfiguracaoDaRodada) -> None:
        self.arquitetura = arquitetura
        self.projeto = projeto
        self.configuracao = configuracao
        self.diretorio: Path = configuracao.saida / f"{arquitetura}-{projeto.nome}-{configuracao.carimbo}"
        self.criada: bool = False
        self.inicio: datetime | None = None
        self.fim: datetime | None = None
        self.resultados: tuple[ResultadoDeSessao, ...] = ()
        self.medicao: Medicao | None = None
        self.entrega: EstadoDaEntrega | None = None
        self.erros: list[str] = []

    def rodar(self, arquitetura: Arquitetura, sessoes: ExecutorDeSessao) -> None:
        """Monta, roda a arquitetura, mede e lê a entrega; a falha de domínio vira erro e a execução segue."""
        self.inicio = _agora()
        self.diretorio.mkdir(parents=True)
        self.criada = True
        pedido = montar_execucao(self.projeto, self.diretorio, self.configuracao)
        self.resultados, erro = _executar(arquitetura, pedido, sessoes)
        self._anotar(erro or erros_das_sessoes(self.resultados))
        invocacoes = tuple(Invocacao(r.session_id, r.inicio, r.fim, r.leitura.resultado) for r in self.resultados)
        self.medicao = medir(invocacoes, self.configuracao.raiz_das_transcricoes)
        self.entrega, erro = _ler_entrega(pedido)
        self._anotar(erro)
        self.fim = _agora()

    def gravar(self, falha: BaseException | None) -> ExecucaoGravada:
        """`execucao.json` com o que se sabe, e a falha que parou a linha de execução no erro.

        Nada se grava numa pasta que esta execução não criou: a que já existia é
        de outra rodada.
        """
        if falha is not None:
            self._anotar(f"a execucao parou com {type(falha).__name__}: {falha}")
        registro = self.em_dicionario()
        if not self.criada:
            return ExecucaoGravada(self.diretorio, registro)
        try:
            gravar_json(self.diretorio / ARQUIVO_DA_EXECUCAO, registro)
        except OSError as erro:
            registro["erro"] = SEPARADOR_DE_ERROS.join((*self.erros, f"execucao.json nao gravado: {erro}"))
        return ExecucaoGravada(self.diretorio, registro)

    def em_dicionario(self) -> dict[str, Any]:
        """O registro no formato de `execucao.json`; o que não chegou a ser medido fica null."""
        medicao = (self.medicao or Medicao(None, None, "", None, ())).em_dicionario()
        return {
            "versao": VERSAO_DO_REGISTRO,
            "arquitetura": self.arquitetura,
            "projeto": self.projeto.nome,
            "repositorio": self.projeto.nome,
            "spec": nome_da_spec(self.projeto),
            "banco": NOME_DO_BANCO,
            "semente": self.projeto.semente.commit,
            "inicio": em_iso(self.inicio) if self.inicio else None,
            "fim": em_iso(self.fim or _agora()),
            "erro": SEPARADOR_DE_ERROS.join(self.erros),
            "metricas": {**medicao, "commits": self.entrega.commits if self.entrega else None},
            "entrega": self.entrega.em_dicionario() if self.entrega else None,
            "sessoes": [resultado.em_dicionario() for resultado in self.resultados],
        }

    def _anotar(self, erro: str) -> None:
        """Acrescenta o erro, quando há um."""
        if erro:
            self.erros.append(erro)


def montar_execucao(projeto: ProjetoDaBancada, diretorio: Path, configuracao: ConfiguracaoDaRodada) -> PedidoDeExecucao:
    """Na pasta criada, o repositório da semente, a spec ao lado e o caminho do banco."""
    repositorio = diretorio / projeto.nome
    criar_repositorio(projeto, repositorio)
    spec = diretorio / nome_da_spec(projeto)
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


def rodar_projetos(
    arquitetura: Callable[[], Arquitetura],
    projetos: Sequence[ProjetoDaBancada],
    configuracao: ConfiguracaoDaRodada,
    *,
    sessoes: ExecutorDeSessao,
) -> tuple[ExecucaoGravada, ...]:
    """Cada projeto na sua execução, um por linha de execução; a falha de um fica gravada nele e os outros seguem.

    A pasta que já existe recusa a rodada inteira antes de criar qualquer coisa.
    """
    nome = arquitetura().nome
    execucoes = [ExecucaoEmAndamento(nome, projeto, configuracao) for projeto in projetos]
    existentes = [str(execucao.diretorio) for execucao in execucoes if execucao.diretorio.exists()]
    if existentes:
        raise ErroDaBancada("a pasta da execucao ja existe", {"execucao": ", ".join(existentes)})

    def rodar(execucao: ExecucaoEmAndamento) -> None:
        execucao.rodar(arquitetura(), sessoes)

    with ThreadPoolExecutor(max_workers=max(1, len(execucoes))) as paralelo:
        futuros = [paralelo.submit(rodar, execucao) for execucao in execucoes]
    return tuple(execucao.gravar(futuro.exception()) for execucao, futuro in zip(execucoes, futuros))


def nome_da_spec(projeto: ProjetoDaBancada) -> str:
    """O arquivo da spec ao lado do repositório, como o prompt o cita."""
    return f"spec-{projeto.nome}.md"


def erros_das_sessoes(resultados: Sequence[ResultadoDeSessao]) -> str:
    """Cada sessão que deu errado e por quê; vazio quando todas terminaram bem."""
    return SEPARADOR_DE_ERROS.join(
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
    """As sessões que a arquitetura rodou, ou nenhuma e o erro de domínio que a impediu."""
    try:
        return arquitetura.executar(pedido, sessoes), ""
    except GraphowError as erro:
        return (), erro.formatar_para_llm()


def _ler_entrega(pedido: PedidoDeExecucao) -> tuple[EstadoDaEntrega | None, str]:
    """O estado git da entrega, ou nenhum e o motivo: o agente pode ter deixado o repositório ilegível."""
    try:
        return ler_estado_da_entrega(pedido.repositorio, pedido.projeto), ""
    except (GraphowError, ValueError) as erro:
        motivo = erro.formatar_para_llm() if isinstance(erro, GraphowError) else str(erro)
        return None, f"estado git da entrega ilegivel: {motivo}"


def _agora() -> datetime:
    """O relógio da máquina, com fuso."""
    return datetime.now(timezone.utc).astimezone()
