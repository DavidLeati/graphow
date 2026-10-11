"""As arquiteturas que a bancada sabe rodar, registradas por nome.

Uma arquitetura recebe a execução montada (o repositório recriado da semente,
a spec ao lado dele e o banco descartável) e devolve as sessões que rodou. O
registro é o ponto de extensão: a fase 1 registra `orquestrar` aqui, e a
bancada passa a medi-la do mesmo jeito que mede a enxuta.

A enxuta é o controle do laboratório: uma sessão Opus com permissão total, na
pasta do repositório, com o prompt do processo fixo (spec, testes de aceite que
falham, implementação com commit a cada passo, até duas revisões adversariais).
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from graphow.bancada.projetos import Bancada, ErroDaBancada, ProjetoDaBancada, preencher_modelo
from graphow.sessoes.pedido import TEMPO_LIMITE_PADRAO_S, PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

NOME_DA_ENXUTA: str = "enxuta"
MODELO_DA_ENXUTA: str = "opus"
PERMISSAO_DA_ENXUTA: str = "bypassPermissions"
PASTA_DAS_SESSOES: str = "sessoes"


@dataclass(frozen=True)
class PedidoDeExecucao:
    """A execução montada que a arquitetura recebe: onde está cada coisa e quanto tempo ela tem."""

    projeto: ProjetoDaBancada
    bancada: Bancada
    diretorio: Path
    repositorio: Path
    spec: Path
    banco: Path
    tempo_limite_s: float = TEMPO_LIMITE_PADRAO_S

    @property
    def pasta_das_sessoes(self) -> Path:
        """Onde cada sessão grava o stream e a saída de erro."""
        return self.diretorio / PASTA_DAS_SESSOES


class Arquitetura(Protocol):
    """O que a bancada exige de uma arquitetura: um nome e rodar a execução montada."""

    nome: str

    def executar(self, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]:
        """Roda o projeto e devolve as sessões, na ordem em que rodaram."""
        ...


class ArquiteturaEnxuta:
    """Uma sessão Opus, sem graphow, com o prompt de processo fixo do laboratório."""

    nome: str = NOME_DA_ENXUTA

    def pedido_de_sessao(self, pedido: PedidoDeExecucao) -> PedidoDeSessao:
        """A sessão única: o prompt preenchido com a spec ao lado do repositório e o ramo do projeto."""
        modelo = pedido.bancada.modelo_da_arquitetura(self.nome)
        prompt = preencher_modelo(modelo, {"SPEC": f"../{pedido.spec.name}", "RAMO": pedido.projeto.ramo})
        return PedidoDeSessao(
            prompt=prompt,
            pasta=pedido.repositorio,
            arquivo_stream=pedido.pasta_das_sessoes / f"{self.nome}.jsonl",
            modelo=MODELO_DA_ENXUTA,
            modo_de_permissao=PERMISSAO_DA_ENXUTA,
            banco_graphow=pedido.banco,
            tempo_limite_s=pedido.tempo_limite_s,
        )

    def executar(self, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]:
        """Roda a sessão única."""
        return (sessoes.rodar(self.pedido_de_sessao(pedido)),)


class RegistroDeArquiteturas:
    """As arquiteturas por nome, cada uma com a fábrica que a cria."""

    def __init__(self) -> None:
        self._fabricas: dict[str, Callable[[], Arquitetura]] = {}

    @property
    def nomes(self) -> tuple[str, ...]:
        """Os nomes registrados, em ordem alfabética."""
        return tuple(sorted(self._fabricas))

    def registrar(self, nome: str, fabrica: Callable[[], Arquitetura]) -> None:
        """Registra a arquitetura; o mesmo nome duas vezes é engano e recusa."""
        if nome in self._fabricas:
            raise ErroDaBancada("arquitetura ja registrada", {"arquitetura": nome})
        self._fabricas[nome] = fabrica

    def criar(self, nome: str) -> Arquitetura:
        """A arquitetura pelo nome; a recusa lista as registradas."""
        if nome not in self._fabricas:
            raise ErroDaBancada("arquitetura desconhecida", {"arquitetura": nome, "registradas": ", ".join(self.nomes)})
        return self._fabricas[nome]()


def registro_padrao() -> RegistroDeArquiteturas:
    """O registro com as arquiteturas que existem hoje: só a enxuta."""
    registro = RegistroDeArquiteturas()
    registro.registrar(NOME_DA_ENXUTA, ArquiteturaEnxuta)
    return registro
