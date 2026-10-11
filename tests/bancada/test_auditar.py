"""`graphow bancada auditar`: o prompt do auditor sobre a execução, o relatório guardado e o PLACAR extraído."""

import argparse
import json
from pathlib import Path

import pytest

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.auditoria import bloqueantes_listados, extrair_placar, pedido_do_auditor
from graphow.bancada.projetos import Bancada, ErroDaBancada, preencher_modelo
from graphow.sessoes.sessao_claude import ExecutorDeSessao

from tests.sessoes.apoio import ambiente_de_teste, chamadas_registradas, comando_do_falso

STREAM_DO_AUDITOR: Path = Path(__file__).parent / "dados" / "stream_auditor.jsonl"
LINHA_DO_LABORATORIO: str = "PLACAR: criterios atende 14 / parcial 0 / nao_atende 0; sondas ok 6 / defeito 2; bloqueantes 0"


def _argumentos(*partes: str) -> argparse.Namespace:
    """`graphow bancada ...` analisado, com transcrições numa pasta que não existe."""
    return construir_parser().parse_args(["bancada", *partes, "--transcricoes", "nao-existe"])


def _execucao_do_estoque(tmp_path: Path, **extras: str) -> Path:
    """Uma execução da enxuta no estoque, rodada com o falso, que deixa o trabalho como pedido."""
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "registro-rodar", **extras))
    argumentos = _argumentos("rodar", "--arquitetura", "enxuta", "--projeto", "estoque-loja", "--saida", str(tmp_path / "saida"))
    assert executar_bancada(argumentos, EscritorConsoleEmMemoria(), sessoes=sessoes) == 0
    return next((tmp_path / "saida").iterdir())


def test_auditar_preenche_o_prompt_roda_na_pasta_propria_e_grava_o_placar_nominal(tmp_path: Path) -> None:
    """Prompt do laboratório com os caminhos da execução, sessão Opus em `auditoria/`, banco próprio e o PLACAR lido.

    A pasta de trabalho do auditor não é a da execução, onde está o relato do implementador em `sessoes/`."""
    execucao = _execucao_do_estoque(tmp_path, GRAPHOW_TESTE_COMMIT="chamado-142")
    registro = tmp_path / "registro-auditar"
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(registro, GRAPHOW_TESTE_STREAM=str(STREAM_DO_AUDITOR)))
    console = EscritorConsoleEmMemoria()

    codigo = executar_bancada(_argumentos("auditar", "--execucao", str(execucao)), console, sessoes=sessoes)

    assert codigo == 0, console.linhas
    bancada = Bancada()
    esperado = preencher_modelo(bancada.modelo_do_auditor(), {
        "REPO": str(execucao / "estoque-loja"),
        "SPEC": str(execucao / "spec-estoque-loja.md"),
        "RAMO": "chamado-142",
        "SONDAS": bancada.projeto("estoque-loja").texto_das_sondas(),
    })
    chamada = chamadas_registradas(registro)[0]
    assert chamada["stdin"] == esperado
    assert chamada["argv"][:5] == ["-p", "--model", "opus", "--permission-mode", "bypassPermissions"]
    assert Path(str(chamada["cwd"])) == execucao / "auditoria"
    assert not list(Path(str(chamada["cwd"])).glob("**/enxuta.jsonl"))
    assert chamada["env"]["GRAPHOW_DB"] == str(execucao / "auditoria" / "graphow.db")
    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert auditoria["erro"] == ""
    assert auditoria["placar"]["criterios"] == {"atende": 14, "parcial": 0, "nao_atende": 0}
    assert (auditoria["placar"]["sondas_ok"], auditoria["placar"]["sondas_defeito"], auditoria["placar"]["bloqueantes"]) == (6, 2, 0)
    assert auditoria["metricas"]["custo_usd"] == 1.73
    assert (execucao / "auditoria" / "relatorio.md").read_text(encoding="utf-8").count("PLACAR:") == 1
    assert (execucao / "auditoria" / "prompt.md").read_text(encoding="utf-8") == esperado
    assert any(LINHA_DO_LABORATORIO in linha for linha in console.linhas)


def test_trabalho_nao_commitado_vai_ao_auditor_com_a_ressalva_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem o ramo, o auditor é mandado ao working tree, como na agenda do graphow."""
    execucao = _execucao_do_estoque(tmp_path)

    pedido = pedido_do_auditor(execucao, Bancada())

    assert "O trabalho está na branch `main (o trabalho está NÃO commitado no working tree;" in pedido.prompt


def test_relatorio_sem_placar_grava_erro_e_sai_com_1_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o stream da enxuta não tem PLACAR; nada é inventado."""
    execucao = _execucao_do_estoque(tmp_path)
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r"))

    codigo = executar_bancada(_argumentos("auditar", "--execucao", str(execucao)), EscritorConsoleEmMemoria(), sessoes=sessoes)

    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert auditoria["placar"] is None
    assert "PLACAR" in auditoria["erro"]


def test_pasta_sem_execucao_json_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: auditar o que não foi montado pela bancada recusa com o caminho."""
    with pytest.raises(ErroDaBancada) as recusa:
        pedido_do_auditor(tmp_path, Bancada())

    assert recusa.value.contexto["arquivo"].endswith("execucao.json")


def test_placar_no_formato_do_prompt_nominal() -> None:
    """A linha exata que o prompt pede."""
    placar = extrair_placar(f"relatorio\n\n{LINHA_DO_LABORATORIO}\n- nenhum")

    assert placar is not None
    assert (placar.atende, placar.parcial, placar.nao_atende) == (14, 0, 0)
    assert (placar.sondas_ok, placar.sondas_defeito, placar.bloqueantes) == (6, 2, 0)
    assert placar.linha == LINHA_DO_LABORATORIO


@pytest.mark.parametrize(
    "linha",
    [
        "**PLACAR:** critérios atende 9 / parcial 3 / não_atende 0; sondas ok 0 / defeito 8; bloqueantes 3",
        "`PLACAR: criterios atende 9 / parcial 3 / nao atende 0; sondas ok 0 / defeitos 8; bloqueantes: 3`",
        "PLACAR: criterios atende: 9 / parcial: 3 / nao_atende: 0; sondas ok: 0 / defeito: 8; bloqueantes: 3",
    ],
)
def test_placar_com_o_que_o_modelo_costuma_mudar_edge_case(linha: str) -> None:
    """Caso de borda: negrito, crase, acento, espaço no lugar do sublinhado e dois-pontos."""
    placar = extrair_placar(linha)

    assert placar is not None
    assert (placar.atende, placar.parcial, placar.nao_atende, placar.sondas_ok, placar.sondas_defeito, placar.bloqueantes) == (
        9, 3, 0, 0, 8, 3,
    )


def test_vale_o_ultimo_placar_com_numeros_edge_case() -> None:
    """Caso de borda: o auditor repete o formato com letras e depois dá o placar; o modelo do prompt não conta."""
    texto = "\n".join([
        'Formato: "PLACAR: criterios atende X / parcial Y / nao_atende Z; sondas ok A / defeito B; bloqueantes C"',
        "PLACAR: criterios atende 1 / parcial 1 / nao_atende 1; sondas ok 1 / defeito 7; bloqueantes 1",
        "PLACAR: criterios atende 2 / parcial 0 / nao_atende 0; sondas ok 8 / defeito 0; bloqueantes 0",
        "PLACAR: incompleto",
    ])

    placar = extrair_placar(texto)

    assert placar is not None and (placar.atende, placar.sondas_ok) == (2, 8)
    assert extrair_placar("sem placar nenhum") is None


def test_bloqueantes_listados_depois_do_placar_nominal() -> None:
    """A lista que o prompt pede depois do PLACAR; o que vem antes dele não conta."""
    texto = "- antes\nPLACAR: criterios atende 1 / parcial 0 / nao_atende 1; sondas ok 7 / defeito 1; bloqueantes 2\n\n" \
            "1. 500 em GET /tarefas?pagina=99999999999999999999 (storage.js:107)\n- POST aceita status\nfim"

    assert bloqueantes_listados(texto) == ("500 em GET /tarefas?pagina=99999999999999999999 (storage.js:107)", "POST aceita status")
    assert bloqueantes_listados("- sem placar") == ()
