"""Testes da rota GET /api/escopo pelo servidor real."""

import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from graphow.web.server import EnderecoServidor, GraphowWebServer
from tests.web.cenario_escopo import montar_kernel


def _porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor() -> Iterator[str]:
    """Sobe o servidor sobre o cenário de escopo e devolve a URL base."""
    porta = _porta_livre()
    servidor = GraphowWebServer(montar_kernel(), EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{porta}"
    finally:
        servidor.parar()


def _ler(url: str) -> tuple[int, dict[str, Any]]:
    """GET devolvendo status e corpo JSON, inclusive nas recusas."""
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def test_ler_o_placar_pelo_servidor_nominal() -> None:
    """O GET devolve o placar do Goal com o plano aprovado e o gatilho K."""
    with _servidor() as base_url:
        status, corpo = _ler(f"{base_url}/api/escopo?goal=goal-e&ramo=main")

    assert status == 200 and corpo["plano_aprovado"] is True
    assert corpo["gatilhos_disparados"][0]["raiz"] == "d1"
    assert corpo["limiares"]["por_raiz"] == 3


def test_goal_ausente_ou_inexistente_volta_400_e_404_edge_case() -> None:
    """Caso de borda: sem `goal` na query vem 400; Goal desconhecido vem 404."""
    with _servidor() as base_url:
        sem_goal = _ler(f"{base_url}/api/escopo")
        desconhecido = _ler(f"{base_url}/api/escopo?goal=nao-existe")

    assert sem_goal[0] == 400 and sem_goal[1]["sucesso"] is False
    assert desconhecido[0] == 404
