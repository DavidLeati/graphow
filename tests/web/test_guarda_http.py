"""Testes da guarda do canvas: só a própria página escreve, e só este servidor responde."""

from collections.abc import Iterator
from contextlib import contextmanager
import http.client
import json
import socket
import time

import pytest

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.guarda_http import CABECALHO_DO_TOKEN, GuardaHTTP
from graphow.web.server import EnderecoServidor, GraphowWebServer
from tests.web.cliente_http import cabecalhos_de_escrita

CORPO_DE_PROJETO: bytes = json.dumps({"tipo": "Projeto", "rotulo": "Plantado", "id_no": "p-plantado"}).encode("utf-8")


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor() -> Iterator[int]:
    """Servidor real numa porta livre, com banco em memória."""
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(WriteKernel(InMemoryEventStore()), EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        yield porta
    finally:
        servidor.parar()


def _requisitar(porta: int, metodo: str, caminho: str, cabecalhos: dict[str, str]) -> tuple[int, dict[str, object]]:
    """Requisição crua, com os cabeçalhos exatos, para o teste escolher o Host e a Origin."""
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=3)
    try:
        corpo = CORPO_DE_PROJETO if metodo != "GET" else None
        conexao.request(metodo, caminho, body=corpo, headers=cabecalhos)
        resposta = conexao.getresponse()
        return resposta.status, json.loads(resposta.read().decode("utf-8") or "{}")
    finally:
        conexao.close()


def _projeto_foi_criado(porta: int) -> bool:
    """Diz se o Projeto plantado chegou ao grafo."""
    _, canvas = _requisitar(porta, "GET", "/api/canvas", {"Host": f"127.0.0.1:{porta}"})
    nos = canvas.get("nos")
    return isinstance(nos, list) and any(no.get("id") == "p-plantado" for no in nos)


def test_post_de_outro_site_sem_preflight_e_recusado_edge_case() -> None:
    """Caso de borda: o `fetch` simples de outro site, em text/plain, escrevia como o humano."""
    with _servidor() as porta:
        status, _ = _requisitar(
            porta,
            "POST",
            "/api/nodes",
            {"Host": f"127.0.0.1:{porta}", "Origin": "https://evil.example", "Content-Type": "text/plain"},
        )
        assert status == 403
        assert _projeto_foi_criado(porta) is False


def test_escrita_sem_token_e_recusada_mesmo_da_propria_origem_edge_case() -> None:
    """Caso de borda: a origem certa não basta; a escrita prova que leu o token da sessão."""
    with _servidor() as porta:
        host = f"127.0.0.1:{porta}"
        status, corpo = _requisitar(
            porta, "POST", "/api/nodes", {"Host": host, "Origin": f"http://{host}", "Content-Type": "application/json"}
        )
        assert status == 403
        assert CABECALHO_DO_TOKEN in str(corpo["mensagem"])
        assert _projeto_foi_criado(porta) is False


def test_escrita_com_token_exige_corpo_json_edge_case() -> None:
    """Caso de borda: o corpo em text/plain é o formato que o navegador manda sem preflight."""
    with _servidor() as porta:
        cabecalhos = cabecalhos_de_escrita(f"http://127.0.0.1:{porta}")
        cabecalhos.update({"Host": f"127.0.0.1:{porta}", "Content-Type": "text/plain"})
        status, _ = _requisitar(porta, "POST", "/api/nodes", cabecalhos)
        assert status == 415
        assert _projeto_foi_criado(porta) is False


def test_pagina_com_o_token_escreve_nominal() -> None:
    """A página, que lê o token em /api/identity, segue escrevendo como antes."""
    with _servidor() as porta:
        host = f"127.0.0.1:{porta}"
        cabecalhos = cabecalhos_de_escrita(f"http://{host}")
        cabecalhos.update({"Host": host, "Origin": f"http://{host}"})
        status, corpo = _requisitar(porta, "POST", "/api/nodes", cabecalhos)
        assert status == 201, corpo
        assert _projeto_foi_criado(porta) is True


def test_host_de_outro_dominio_nao_le_o_grafo_edge_case() -> None:
    """Caso de borda: um domínio que aponta para 127.0.0.1 (DNS rebinding) lia o grafo inteiro."""
    with _servidor() as porta:
        status, _ = _requisitar(porta, "GET", "/api/canvas", {"Host": f"attacker.example:{porta}"})
        assert status == 403


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000", "LOCALHOST"])
def test_nomes_de_loopback_passam_nominal(host: str) -> None:
    """Os nomes com que o navegador chega ao servidor local passam pela guarda."""
    assert GuardaHTTP.para_o_host("127.0.0.1").avaliar("GET", {"Host": host}) is None


def test_servidor_aberto_em_todas_as_interfaces_ainda_exige_o_token_edge_case() -> None:
    """Caso de borda: em 0.0.0.0 qualquer nome chega, e a escrita segue dependendo do token."""
    guarda = GuardaHTTP.para_o_host("0.0.0.0")
    assert guarda.avaliar("GET", {"Host": "192.168.0.10:8000"}) is None
    recusa = guarda.avaliar("PUT", {"Host": "192.168.0.10:8000", "Content-Type": "application/json"})
    assert recusa is not None
    assert recusa.status == 403
