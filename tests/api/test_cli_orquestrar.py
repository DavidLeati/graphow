"""`graphow orquestrar` pela linha de comando: o executável de `GRAPHOW_CLAUDE`, o banco pedido e o status."""

import os
from pathlib import Path
import stat
import sys

import pytest

from graphow.api.cli_execucao import ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.pedidos_do_humano import PEDIDO_MAIS_CICLOS, NovoPedido, PedidoRecusado, gravar_pedido
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos

from tests.orquestrador.apoio_laco import CLAUDE_ROTEIRIZADO, montar_bancada, roteiro_completo, roteiro_em_dois_marcos_com_um_ciclo_cada


def _executavel(pasta: Path) -> Path:
    """O falso roteirizado como executável, para `GRAPHOW_CLAUDE` apontar para ele."""
    pasta.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        caminho = pasta / "claude.cmd"
        caminho.write_text(f'@"{sys.executable}" "{CLAUDE_ROTEIRIZADO}" %*\r\n', encoding="utf-8")
        return caminho
    caminho = pasta / "claude"
    caminho.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{CLAUDE_ROTEIRIZADO}" "$@"\n', encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)
    return caminho


def _rodar(argumentos: list[str], dados: Path) -> tuple[int, list[str]]:
    """`graphow ...` pelo executor da linha de comando, com o diretório de dados no temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(dados)}, dados)
    codigo = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente)).executar(construir_parser().parse_args(argumentos))
    return codigo, console.linhas


def test_orquestrar_da_spec_fecha_o_goal_e_o_status_mostra_o_custo_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Da spec ao Goal fechado pela CLI, com o estado do Goal ao lado do banco e o status relido depois."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    banco = tmp_path / "dados" / "graphow.db"

    codigo, linhas = _rodar(
        ["--db", str(banco), "orquestrar", "--spec", str(bancada.spec), "--repo", str(bancada.repositorio), "--modo", "autonomo"],
        tmp_path / "dados",
    )
    codigo_do_status, status = _rodar(["--db", str(banco), "orquestrar", "--goal", "goal-soma", "--status"], tmp_path / "dados")

    assert codigo == 0, linhas
    assert "Parada: fechado" in linhas
    assert (tmp_path / "dados" / "orquestrar" / "goal-soma" / "sessoes").is_dir()
    assert codigo_do_status == 0
    assert status[1].startswith("Goal goal-soma: Soma de dois numeros [fechado]")
    assert any(linha.startswith("Sessoes: 7 invocacao(oes)") and "US$ 2.50" in linha for linha in status)


def test_comando_montado_pela_cli_usa_sonnet_no_marco_e_na_conferencia_e_opus_na_cacada_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T2d.4: com os padroes da CLI, o `--model` das sessoes e sonnet no marco e na conferencia e opus na cacada."""
    bancada = montar_bancada(tmp_path, roteiro_em_dois_marcos_com_um_ciclo_cada())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    banco = tmp_path / "dados" / "graphow.db"
    argumentos = ["--db", str(banco), "orquestrar", "--spec", str(bancada.spec), "--repo", str(bancada.repositorio), "--modo", "autonomo"]

    codigo, linhas = _rodar(argumentos, tmp_path / "dados")
    _, status = _rodar(["--db", str(banco), "orquestrar", "--goal", "goal-soma", "--status"], tmp_path / "dados")

    assert codigo == 0, linhas
    modelos = [(c["papel"], c["argv"][c["argv"].index("--model") + 1]) for c in bancada.chamadas()
               if c["papel"] in ("marco", "conferencia", "verificador")]
    assert modelos == [("marco", "sonnet"), ("conferencia", "sonnet"), ("verificador", "opus"), ("conferencia", "sonnet")]
    padroes = construir_parser().parse_args(["orquestrar", "--goal", "g"])
    assert (padroes.modelo_marco, padroes.modelo_conferencia, padroes.modelo_verificador) == ("sonnet", "sonnet", "opus")
    assert sum("conferencia" in linha for linha in status if linha.startswith("  ver-goal-soma-")) == 2, status


def test_status_de_goal_que_nao_existe_sai_com_1_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o status de um Goal desconhecido diz que não achou e sai com 1."""
    codigo, linhas = _rodar(["--db", str(tmp_path / "g.db"), "orquestrar", "--goal", "goal-x", "--status"], tmp_path)

    assert codigo == 1
    assert "ERRO: Goal 'goal-x' nao encontrado" in linhas


def test_spec_ou_goal_e_obrigatorio_edge_case() -> None:
    """Caso de borda: --spec e --goal são exclusivos, e um deles é obrigatório."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["orquestrar", "--status"])


@pytest.mark.parametrize(("argumentos", "trecho"), [
    (["--spec", "x.md", "--ciclos-de-correcao", "-1"], "precisa ser 0 ou mais"),
    (["--goal", "goal-soma", "--mais-ciclos", "0", "--motivo", "m"], "precisa ser 1 ou mais"),
    (["--goal", "goal-soma", "--mais-ciclos", "-2", "--motivo", "m"], "precisa ser 1 ou mais"),
])
def test_ciclos_negativos_sao_recusados_pela_cli_edge_case(argumentos: list[str], trecho: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Caso de borda: ciclos negativos tirariam ciclos do marco; a CLI os recusa antes de abrir o banco."""
    with pytest.raises(SystemExit) as saida:
        construir_parser().parse_args(["orquestrar", *argumentos])

    assert saida.value.code == 2
    assert trecho in capsys.readouterr().err


def test_ciclos_negativos_sao_recusados_fora_da_cli_edge_case(tmp_path: Path) -> None:
    """Caso de borda: as opções do laço e o pedido de mais ciclos também recusam o negativo, sem depender da CLI."""
    with pytest.raises(ValueError, match="nao pode ser negativo"):
        OpcoesDoLaco(ciclos_de_correcao=-1)
    bancada = montar_bancada(tmp_path, roteiro_completo())
    with pytest.raises(PedidoRecusado, match="pede 1 ou mais"):
        gravar_pedido(bancada.kernel, "goal-soma", NovoPedido(PEDIDO_MAIS_CICLOS, "m", "david", ciclos=-1))
