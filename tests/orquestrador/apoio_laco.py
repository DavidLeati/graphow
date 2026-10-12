"""Apoio dos testes do laço: o repositório de brinquedo, o roteiro dos papéis e o orquestrador montado."""

import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador.contexto_do_laco import DependenciasDoLaco
from graphow.orquestrador.laco import Orquestrador
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria

from tests.orquestrador.apoio_git import criar_repositorio

CLAUDE_ROTEIRIZADO: Path = Path(__file__).parent / "claude_roteirizado.py"
SOMA_ERRADA: str = "def somar(a, b):\n    return 0\n"
SOMA_CERTA: str = "def somar(a, b):\n    return a + b\n"
VERIFICAR_INICIAL: str = "print('ainda sem teste')\n"
VERIFICAR: str ="from soma import somar\nassert somar(2, 3) == 5, 'C1'\nprint('ok')\n"
SUITE: str = f'"{sys.executable}" verificar.py'
SPEC: str = "# Pedido do humano\nQuero somar dois numeros.\n\n# Respostas do humano\nSo inteiros.\n"

PLANO: dict[str, Any] = {
    "titulo": "Soma de dois numeros",
    "comando_suite": SUITE,
    "criterios": [
        {"id": "C1", "texto": "somar(2, 3) devolve 5", "verificacao": "teste"},
        {"id": "C2", "texto": "o README explica como usar somar", "verificacao": "checagem"},
    ],
    "decisoes": [{"id": "D1", "texto": "so a biblioteca padrao", "motivo": "o repositorio nao tem dependencias"}],
    "fatias": [
        {"id": "F1", "titulo": "Funcao somar", "objetivo": "somar certo, com verificar.py", "criterios": ["C1"],
         "arquivos": ["soma.py", "verificar.py"], "depende_de": [], "modelo": "opus"},
        {"id": "F2", "titulo": "Uso no README", "objetivo": "README com exemplo", "criterios": ["C2"],
         "arquivos": ["README.md"], "depende_de": ["F1"], "modelo": "sonnet"},
    ],
}


def executor_pronto(arquivos: dict[str, str] | None = None, **campos: Any) -> dict[str, Any]:
    """Uma resposta de executor `pronto` que escreve os arquivos dados."""
    saida = {"status": "pronto", "resumo": "feito", "arquivos": sorted(arquivos or {}), "testes": ["verificar.py: ok"], "duvida": ""}
    return {"saida": saida, "arquivos": arquivos or {}, "custo": 0.3, **campos}


def verificacao(c2: str = "atende", achados: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Uma resposta de verificador com o parecer de C2 dado."""
    saida = {
        "resumo": "suite verde e programa rodado",
        "comandos": [{"comando": "python verificar.py", "codigo": 0, "saida": "ok"}],
        "criterios": [{"id": "C1", "veredito": "atende", "prova": "verificar.py: ok"},
                      {"id": "C2", "veredito": c2, "prova": "README lido"}],
        "decisoes": [{"id": "D1", "veredito": "atende", "prova": "sem import externo"}],
        "achados": achados or [],
    }
    return {"saida": saida, "custo": 0.5}


BLOQUEANTE_DO_README: dict[str, Any] = {
    "titulo": "README sem exemplo", "descricao": "falta um exemplo de somar", "prova": "README.md lido: nenhum exemplo",
    "local": "README.md:1", "criterios": ["C2"], "decisoes": [], "severidade": "alta",
}
ACOMPANHAMENTO: dict[str, Any] = {
    "titulo": "nome do modulo", "descricao": "soma.py poderia ser calc.py", "prova": "soma.py:1 lido, nome generico",
    "local": "soma.py:1", "criterios": [], "decisoes": [], "severidade": "baixa",
}


def roteiro_completo() -> dict[str, list[dict[str, Any]]]:
    """Plano, duas fatias, verificação com bloqueante, correção e verificação limpa."""
    return {
        "planejador": [{"saida": copy.deepcopy(PLANO), "custo": 0.4}],
        "executor": [
            executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}),
            executor_pronto({"README.md": "# brinquedo\nUse somar(a, b).\n"}),
            executor_pronto({"README.md": "# brinquedo\nUse somar(a, b): somar(2, 3) == 5.\n"}),
        ],
        "verificador": [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [ACOMPANHAMENTO])],
    }


@dataclass
class Bancada:
    """O que um teste do laço monta: o repositório, a spec, o kernel, a telemetria e o roteiro."""

    raiz: Path
    repositorio: Path
    spec: Path
    kernel: WriteKernel
    telemetria: RepositorioTelemetria
    roteiro: Path
    registro: Path
    executor: ExecutorDeSessao

    def orquestrador(self, **campos: Any) -> Orquestrador:
        """O orquestrador com o falso roteirizado; os campos sobrescrevem as dependências."""
        dependencias = {"kernel": self.kernel, "executor": self.executor, "telemetria": self.telemetria,
                        "pasta_de_estado": self.raiz / "estado", **campos}
        return Orquestrador(DependenciasDoLaco(**dependencias))

    def chamadas(self, papel: str | None = None) -> list[dict[str, Any]]:
        """O que o falso recebeu, na ordem, de todos os papéis ou de um."""
        todas = [json.loads(arquivo.read_text(encoding="utf-8")) for arquivo in sorted(self.registro.glob("*.json"))]
        return [chamada for chamada in todas if papel is None or chamada["papel"] == papel]

    def trocar_roteiro(self, roteiro: dict[str, list[dict[str, Any]]]) -> None:
        """Um roteiro novo, com os contadores zerados."""
        self.roteiro.write_text(json.dumps(roteiro), encoding="utf-8")
        self.roteiro.with_suffix(".estado.json").unlink(missing_ok=True)


def montar_bancada(tmp_path: Path, roteiro: dict[str, list[dict[str, Any]]]) -> Bancada:
    """O repositório de brinquedo com a soma errada, a spec fora dele e o falso apontado para o roteiro."""
    arquivos = {"README.md": "# brinquedo\n", "soma.py": SOMA_ERRADA, "verificar.py": VERIFICAR_INICIAL}
    repositorio = criar_repositorio(tmp_path / "brinquedo", arquivos)
    spec = tmp_path / "spec-soma.md"
    spec.write_text(SPEC, encoding="utf-8")
    caminho_do_roteiro = tmp_path / "roteiro.json"
    caminho_do_roteiro.write_text(json.dumps(roteiro), encoding="utf-8")
    ambiente = {**os.environ, "GRAPHOW_TESTE_ROTEIRO": str(caminho_do_roteiro),
                "GRAPHOW_TESTE_REGISTRO": str(tmp_path / "registro"), "CLAUDE_CODE_ENTRYPOINT": "teste"}
    executor = ExecutorDeSessao((sys.executable, str(CLAUDE_ROTEIRIZADO)), ambiente)
    return Bancada(
        raiz=tmp_path, repositorio=repositorio, spec=spec, kernel=montar_kernel_em_memoria(),
        telemetria=RepositorioTelemetria(sqlite3.connect(":memory:")), roteiro=caminho_do_roteiro,
        registro=tmp_path / "registro", executor=executor,
    )


class Queda(BaseException):
    """O processo do orquestrador caiu no meio de uma sessão."""


class ExecutorQueCai(ExecutorDeSessao):
    """Roda a sessão e cai logo depois da chamada de número dado, antes de o laço ver o resultado."""

    def __init__(self, base: ExecutorDeSessao, cair_na: int) -> None:
        super().__init__(base._executavel, base._ambiente)
        self._contador: int = 0
        self._cair_na: int = cair_na

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """A sessão roda e o processo cai na chamada marcada."""
        self._contador += 1
        resultado = super().rodar(pedido)
        if self._contador == self._cair_na:
            raise Queda()
        return resultado
