"""A rota GET /api/rastro devolve o mesmo rastro do `graphow orquestrar --rastro`, pelo servidor real."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import time
from typing import Any
import urllib.error
import urllib.request

import pytest

from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador.conferencia_na_leitura import LeituraPorGoal
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.rastro import ler_rastro
from graphow.web.server import EnderecoServidor, GraphowWebServer

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo
from tests.orquestrador.test_leitores_da_evidencia import _contar_o_git


def _porta_livre() -> int:
    """Uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor(kernel: WriteKernel) -> Iterator[str]:
    """O servidor do canvas sobre o kernel dado; devolve a URL base."""
    porta = _porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{porta}"
    finally:
        servidor.parar()


def _ler(url: str) -> tuple[int, dict[str, Any]]:
    """GET devolvendo status e corpo JSON, inclusive nas recusas."""
    try:
        with urllib.request.urlopen(url) as resposta:
            return resposta.status, json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def test_rota_devolve_o_mesmo_rastro_da_cli_do_goal_inteiro_e_de_um_criterio_nominal(tmp_path: Path) -> None:
    """T3f.2: `?goal=` traz o rastro que a CLI formata; `?criterio=` (o nó, como o inspetor pede) só o daquele critério."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo")).fechou
    view = bancada.kernel.obter_view()
    estado = ler_estado(view, "goal-soma")
    assert estado is not None
    esperado = json.loads(json.dumps(ler_rastro(view, estado, LeituraPorGoal(view)).em_json()))

    with _servidor(bancada.kernel) as base:
        status, corpo = _ler(f"{base}/api/rastro?goal=goal-soma&ramo=main")
        status_do_criterio, do_criterio = _ler(f"{base}/api/rastro?criterio=crit-soma-c2")

    assert status == 200 and corpo["sucesso"] is True
    assert {chave: corpo[chave] for chave in esperado} == esperado
    c1, c2 = corpo["criterios"]
    assert [f["codigo"] for f in c2["fatias"]] == ["F2", "M1.K1.1"] and c2["fatias"][1]["corrige"] == "ver-goal-soma-1"
    assert c1["testes"][0]["arquivo"] == "aceite/aceite_c1.py" and len(c1["commit_do_aceite"]) == 40
    assert c2["atestado"]["verificacao"] == "ver-goal-soma-2" and c2["atestado"]["conferencia"]["estado"] == "vigente"
    assert [(x["id"], x["estado"]) for x in c2["achados"]] == [("achado-goal-soma-v1-1", "resolvido")] and c1["achados"] == []
    assert status_do_criterio == 200 and do_criterio["goal"] == "goal-soma" and do_criterio["criterios"] == [c2]


def test_rota_sem_alvo_volta_400_e_alvo_que_nao_leva_a_goal_volta_404_edge_case() -> None:
    """Caso de borda: sem `goal` nem `criterio` vem 400; Goal ou Criterio desconhecido vem 404."""
    with _servidor(montar_kernel_em_memoria()) as base:
        sem_alvo = _ler(f"{base}/api/rastro")
        sem_goal = _ler(f"{base}/api/rastro?goal=nao-existe")
        sem_criterio = _ler(f"{base}/api/rastro?criterio=nao-existe")

    assert sem_alvo[0] == 400 and sem_alvo[1]["sucesso"] is False
    assert (sem_goal[0], sem_criterio[0]) == (404, 404)


def test_rota_marca_o_commit_fora_da_branch_e_guarda_a_conta_entre_pedidos_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3f2.2: a branch do Goal reescrita tira dela o commit da verificação; o inspetor recebe a marca com o aviso.

    O rótulo segue `vigente` (a árvore é a mesma), e a conta de ancestral fica
    na memória do canvas: o segundo pedido, sem a ponta andar, só pergunta a
    ponta.
    """
    bancada = montar_bancada(tmp_path, roteiro_completo())
    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo")).fechou
    repositorio = bancada.repositorio
    verificado = git(repositorio, "log", "-1", "--format=%h", "--abbrev=12", "--grep=README sem exemplo", "graphow/soma").strip()
    git(repositorio, "update-ref", "refs/heads/graphow/soma", git(repositorio, "commit-tree", "graphow/soma^{tree}", "-m", "Reescreve").strip())
    chamadas = _contar_o_git(monkeypatch)

    with _servidor(bancada.kernel) as base:
        primeiro = _ler(f"{base}/api/rastro?criterio=crit-soma-c2")
        do_primeiro = list(chamadas)
        segundo = _ler(f"{base}/api/rastro?criterio=crit-soma-c2")

    conferencia = primeiro[1]["criterios"][0]["atestado"]["conferencia"]
    assert (primeiro[0], conferencia["estado"], conferencia["rotulo"]) == (200, "vigente", "vigente")
    assert conferencia["marca"].startswith(f"vigente: commit fora da branch: {verificado} nao esta na historia da ponta"), conferencia
    assert segundo == primeiro and ("merge-base", "--is-ancestor") in {chamada[:2] for chamada in do_primeiro}
    assert chamadas[len(do_primeiro):] == [("rev-parse", "--verify", "--quiet", "refs/heads/graphow/soma^{commit}")]

