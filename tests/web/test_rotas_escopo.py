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
from tests.web.cliente_http import cabecalhos_de_escrita


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


def _postar(url: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST com JSON e token da sessão, devolvendo status e corpo mesmo nas recusas."""
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers=cabecalhos_de_escrita(url))
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def test_aprovar_plano_pelo_servidor_grava_a_versao_humana_nominal() -> None:
    """O POST aprova o plano sob a identidade do servidor e o GET seguinte já o vê aprovado."""
    porta = _porta_livre()
    servidor = GraphowWebServer(montar_kernel(com_plano=False, emergentes=0), EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    base_url = f"http://127.0.0.1:{porta}"
    try:
        antes = _ler(f"{base_url}/api/escopo?goal=goal-e")[1]
        status, corpo = _postar(f"{base_url}/api/escopo/aprovar_plano", {"goal": "goal-e"})
        depois = _ler(f"{base_url}/api/escopo?goal=goal-e")[1]
    finally:
        servidor.parar()

    assert antes["plano_aprovado"] is False
    assert status == 200 and corpo["plano_aprovado"] is True and corpo["recibo"]["versao"] == 1
    assert depois["plano_aprovado"] is True and depois["referencia"]["papel"] == "humano"


def test_responder_desvio_pelo_servidor_zera_o_gatilho_nominal() -> None:
    """O POST com a raiz que passou de K devolve o placar sem gatilho disparado."""
    with _servidor() as base_url:
        antes = _ler(f"{base_url}/api/escopo?goal=goal-e")[1]
        status, corpo = _postar(
            f"{base_url}/api/escopo/responder_desvio", {"goal": "goal-e", "raiz": "d1", "resposta": "Segue o hub."}
        )

    assert len(antes["gatilhos_disparados"]) == 1
    assert status == 200 and corpo["gatilhos_disparados"] == []


def test_gestos_recusam_autor_declarado_resposta_vazia_e_goal_ausente_edge_case() -> None:
    """Caso de borda: autor no corpo é 400, resposta vazia é 400, Goal desconhecido é 404, raiz falsa é 422."""
    with _servidor() as base_url:
        declarado = _postar(f"{base_url}/api/escopo/aprovar_plano", {"goal": "goal-e", "autor": "outro"})
        vazia = _postar(f"{base_url}/api/escopo/responder_desvio", {"goal": "goal-e", "resposta": ""})
        ausente = _postar(f"{base_url}/api/escopo/aprovar_plano", {"goal": "nao-existe"})
        falsa = _postar(f"{base_url}/api/escopo/responder_desvio", {"goal": "goal-e", "raiz": "fantasma", "resposta": "ok"})

    assert declarado[0] == 400 and declarado[1]["sucesso"] is False
    assert vazia[0] == 400 and ausente[0] == 404
    assert falsa[0] == 422 and falsa[1]["sucesso"] is False
