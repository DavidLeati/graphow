"""F1.6: a arquitetura `orquestrar` na bancada, com o claude falso roteirizado sobre a semente de um projeto."""

import json
import os
from pathlib import Path
import sys
from typing import Any

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.arquiteturas import registro_padrao
from graphow.bancada.projetos import Bancada
from graphow.sessoes.sessao_claude import ExecutorDeSessao

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import CLAUDE_ROTEIRIZADO, executor_pronto, verificacao

SUITE_QUE_PASSA: str = f'"{sys.executable}" -c "print(1)"'


def _roteiro() -> dict[str, list[dict[str, Any]]]:
    """Um plano de uma fatia sobre a semente, um executor que escreve um arquivo e um verificador limpo."""
    plano = {
        "titulo": "Entrega das operações", "comando_suite": SUITE_QUE_PASSA,
        "criterios": [{"id": "C1", "texto": "existe ENTREGA.md", "verificacao": "checagem"},
                      {"id": "C2", "texto": "o README segue igual", "verificacao": "checagem"}],
        "decisoes": [{"id": "D1", "texto": "nada de dependencia", "motivo": "teste"}],
        "fatias": [{"id": "F1", "titulo": "Entrega", "objetivo": "criar ENTREGA.md", "criterios": ["C1", "C2"],
                    "arquivos": ["ENTREGA.md"], "depende_de": [], "modelo": "opus"}],
    }
    return {
        "planejador": [{"saida": plano, "custo": 0.4}],
        "executor": [executor_pronto({"ENTREGA.md": "feito\n"})],
        "verificador": [verificacao("atende")],
    }


def test_orquestrar_roda_na_semente_integra_na_branch_de_entrega_e_mede_as_sessoes_nominal(tmp_path: Path) -> None:
    """O laço autônomo na branch `entrega` do projeto, com o custo e os commits medidos da telemetria."""
    roteiro = tmp_path / "roteiro.json"
    roteiro.write_text(json.dumps(_roteiro()), encoding="utf-8")
    ambiente = {**os.environ, "GRAPHOW_TESTE_ROTEIRO": str(roteiro), "GRAPHOW_TESTE_REGISTRO": str(tmp_path / "registro")}
    sessoes = ExecutorDeSessao((sys.executable, str(CLAUDE_ROTEIRIZADO)), ambiente)
    argumentos = construir_parser().parse_args(
        ["bancada", "rodar", "--arquitetura", "orquestrar", "--projeto", "api-tarefas", "--saida", str(tmp_path / "saida"),
         "--transcricoes", str(tmp_path / "sem-transcricoes")]
    )

    codigo = executar_bancada(argumentos, EscritorConsoleEmMemoria(), sessoes=sessoes)

    execucao = next((tmp_path / "saida").iterdir())
    gravado = json.loads((execucao / "execucao.json").read_text(encoding="utf-8"))
    parada = json.loads((execucao / "orquestrar.json").read_text(encoding="utf-8"))
    assert codigo == 0, gravado["erro"]
    assert (gravado["arquitetura"], gravado["erro"], parada["motivo"]) == ("orquestrar", "", "fechado")
    assert gravado["metricas"]["custo_usd"] == 1.2
    assert gravado["metricas"]["commits"] == 2
    assert gravado["entrega"]["ramo_existe"] is True
    assert any("Entrega das operações" in linha for linha in parada["status"])
    assert "\ufffd" not in (execucao / "orquestrar.json").read_bytes().decode("utf-8")
    assert len(gravado["sessoes"]) == 3
    projeto = Bancada().projeto("api-tarefas")
    repositorio = execucao / "api-tarefas"
    assert git(repositorio, "rev-parse", "entrega").strip() == git(repositorio, "rev-parse", "main").strip()
    assert git(repositorio, "rev-parse", "entrega~2").strip() == projeto.semente.commit


def test_orquestrar_esta_no_registro_padrao_nominal() -> None:
    """A arquitetura do orquestrador é registrada ao lado da enxuta."""
    assert registro_padrao().nomes == ("enxuta", "orquestrar")
    assert registro_padrao().criar("orquestrar").nome == "orquestrar"
