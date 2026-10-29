"""Um orquestrador por Goal: a segunda chamada para e diz quem roda, a trava velha é liberada e a solta vale na exceção.

Os testes da trava de PID morto só usam processos que eles mesmos criaram e
que já saíram sozinhos: nenhum processo é morto aqui.
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.pedidos_do_humano import PEDIDO_CANCELAR, PEDIDO_RECUSAR_PLANO, NovoPedido
from graphow.orquestrador.trava_do_goal import NOME_DA_TRAVA, DonoDaTrava, GoalOcupado, conduzindo, ler_dono, processo_vivo
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.api.test_cli_orquestrar import _executavel, _rodar
from tests.orquestrador.apoio_laco import ExecutorQueCai, Queda, montar_bancada, roteiro_completo
from tests.orquestrador.test_retomada import roteiro_farto

SRC: Path = Path(__file__).resolve().parents[2] / "src"
# O `graphow` de um processo novo, com o código deste checkout (o venv instala o do checkout principal).
GRAPHOW_NOVO: str = (
    "import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = ['graphow', *sys.argv[2:]]; "
    "runpy.run_module('graphow.api.cli', run_name='__main__')"
)
# Um processo novo que toma a trava e sai sem soltá-la, como o orquestrar que morreu no meio.
TOMA_E_MORRE: str = (
    "import os, sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; "
    "from graphow.orquestrador.trava_do_goal import tomar_trava; tomar_trava(Path(sys.argv[2]), 'goal-soma'); os._exit(0)"
)


def _trava(pasta_de_estado: Path) -> Path:
    """O arquivo da trava do Goal da spec."""
    return pasta_de_estado / "goal-soma" / NOME_DA_TRAVA


def _pid_que_morreu(pasta_do_goal: Path) -> int:
    """O PID de um processo deste teste que tomou a trava do Goal e saiu sem soltá-la."""
    feito = subprocess.run([sys.executable, "-c", TOMA_E_MORRE, str(SRC), str(pasta_do_goal)], capture_output=True, text=True, check=False)
    assert feito.returncode == 0, feito.stderr
    dono = ler_dono(pasta_do_goal / NOME_DA_TRAVA)
    assert dono is not None and not processo_vivo(dono.pid)
    return dono.pid


@pytest.mark.parametrize("segundo", [["--goal", "goal-soma"], ["--spec", "SPEC", "--repo", "REPO"]], ids=["goal", "spec"])
def test_dois_orquestrar_no_mesmo_goal_o_segundo_para_e_o_primeiro_fecha_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, segundo: list[str]
) -> None:
    """T3b.1: no meio da sessão do planejador da primeira chamada, um `graphow orquestrar` noutro processo para com `ocupado`."""
    roteiro = roteiro_completo()
    bancada = montar_bancada(tmp_path, roteiro)
    banco = tmp_path / "dados" / "graphow.db"
    alvo = [str(bancada.spec) if a == "SPEC" else str(bancada.repositorio) if a == "REPO" else a for a in segundo]
    roteiro["planejador"][0]["comandos"] = [[sys.executable, "-c", GRAPHOW_NOVO, str(SRC), "--db", str(banco), "orquestrar", *alvo]]
    bancada.trocar_roteiro(roteiro)
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))

    codigo, linhas = _rodar(
        ["--db", str(banco), "orquestrar", "--spec", str(bancada.spec), "--repo", str(bancada.repositorio), "--modo", "autonomo"],
        tmp_path / "dados",
    )

    assert codigo == 0 and "Parada: fechado" in linhas, linhas
    [segunda] = bancada.chamadas("planejador")[0]["comandos"]
    assert segunda["codigo"] == 3, segunda
    assert "Parada: ocupado" in segunda["saida"]
    assert f"ja esta sendo conduzido pelo PID {os.getpid()} na maquina {socket.gethostname()}, desde " in segunda["saida"]
    assert f"encerre o PID {os.getpid()}" in segunda["saida"]
    assert len(bancada.chamadas("planejador")) == 1, "a segunda chamada nao abriu sessao"
    assert not _trava(tmp_path / "dados" / "orquestrar").exists()


def test_trava_de_pid_morto_e_liberada_com_aviso_e_a_chamada_segue_nominal(tmp_path: Path) -> None:
    """T3b.2: a trava que um processo deste teste tomou antes de sair sozinho é liberada, e o Goal anda até o portão."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    morto = _pid_que_morreu(tmp_path / "estado" / "goal-soma")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, parada.mensagem
    assert parada.mensagem.startswith(f"Aviso: a trava do Goal goal-soma era do PID {morto} na maquina ")
    assert "que nao existe mais nesta maquina; foi liberada." in parada.mensagem
    assert not _trava(tmp_path / "estado").exists()
    assert [p.name for p in (tmp_path / "estado" / "goal-soma").iterdir() if p.name.startswith(NOME_DA_TRAVA)] == []


def test_trava_de_outra_maquina_nao_e_adivinhada_edge_case(tmp_path: Path) -> None:
    """T3b.2: a trava de outra máquina fica como está, e a parada diz como liberá-la à mão."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    caminho = _trava(tmp_path / "estado")
    caminho.parent.mkdir(parents=True)
    dono = {"pid": 4242, "maquina": "outra-maquina", "inicio": "2026-10-29T10:00:00-03:00", "comando": "graphow orquestrar", "ficha": "x"}
    caminho.write_text(json.dumps(dono), encoding="utf-8")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.OCUPADO
    assert "PID 4242 na maquina outra-maquina, desde 2026-10-29T10:00:00-03:00" in parada.mensagem
    assert f"libere a mao apagando {caminho}" in parada.mensagem
    assert json.loads(caminho.read_text(encoding="utf-8")) == dono
    assert bancada.chamadas() == []


class ExecutorQueVeATrava(ExecutorQueCai):
    """Cai depois da primeira sessão, e guarda quem tinha a trava enquanto ela rodava."""

    def __init__(self, base: ExecutorDeSessao, caminho: Path) -> None:
        super().__init__(base, 1)
        self.caminho: Path = caminho
        self.dono_na_sessao: DonoDaTrava | None = None

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """Lê a trava e roda a sessão, que cai."""
        self.dono_na_sessao = ler_dono(self.caminho)
        return super().rodar(pedido)


def test_trava_e_solta_quando_o_laco_sai_por_excecao_nominal(tmp_path: Path) -> None:
    """T3b.3: o processo "cai" (BaseException) na sessão do planejador; a trava some, e a próxima chamada segue sem aviso."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    executor = ExecutorQueVeATrava(bancada.executor, _trava(tmp_path / "estado"))
    with pytest.raises(Queda):
        bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    assert executor.dono_na_sessao is not None and executor.dono_na_sessao.pid == os.getpid()
    assert not _trava(tmp_path / "estado").exists()

    parada = bancada.orquestrador().rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, parada.mensagem
    assert "Aviso" not in parada.mensagem


def test_status_responde_com_a_trava_tomada_e_a_outra_chamada_para_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3b.4: com a trava de uma execução viva, `--status` lê o Goal (0) e `--goal` para com `ocupado` (3) sem sessão."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    dados = tmp_path / "dados"
    banco = ["--db", str(dados / "graphow.db"), "orquestrar"]
    codigo, linhas = _rodar([*banco, "--spec", str(bancada.spec), "--repo", str(bancada.repositorio)], dados)
    assert codigo == 3 and "Parada: aguardando_aprovacao" in linhas, linhas
    sessoes = len(bancada.chamadas())

    with conduzindo(dados / "orquestrar" / "goal-soma", "goal-soma"):
        codigo_do_status, status = _rodar([*banco, "--goal", "goal-soma", "--status"], dados)
        codigo_ocupado, ocupado = _rodar([*banco, "--goal", "goal-soma", "--aprovar-plano"], dados)

    assert codigo_do_status == 0
    assert any(linha.startswith("Goal goal-soma: Soma de dois numeros") for linha in status), status
    assert codigo_ocupado == 3 and "Parada: ocupado" in ocupado, ocupado
    assert any(f"conduzido pelo PID {os.getpid()}" in linha for linha in ocupado)
    assert len(bancada.chamadas()) == sessoes
    assert not _trava(dados / "orquestrar").exists()


def test_pedido_que_refaz_trabalho_pede_a_trava_e_o_cancelamento_nao_edge_case(tmp_path: Path) -> None:
    """Com outra execução no Goal, recusar o plano é recusado sem gravar; o cancelamento grava, e quem roda o lê depois."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco()).motivo == MotivoDaParada.AGUARDANDO_APROVACAO

    with conduzindo(tmp_path / "estado" / "goal-soma", "goal-soma"):
        with pytest.raises(GoalOcupado, match=f"conduzido pelo PID {os.getpid()}"):
            orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RECUSAR_PLANO, "plano errado", "david"))
        gravado = orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_CANCELAR, "desisti", "david"))

    assert "cancelar" in gravado
    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    assert parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
