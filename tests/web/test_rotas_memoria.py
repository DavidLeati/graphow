"""Testes das rotas HTTP da memória: registrar, promover e ler o painel pelo servidor real."""

import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.server import EnderecoServidor, GraphowWebServer


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor() -> Iterator[str]:
    """Sobe o servidor sobre um kernel em memória e devolve a URL base."""
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(WriteKernel(InMemoryEventStore()), EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{porta}"
    finally:
        servidor.parar()


def _postar(url: str, corpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST com JSON, devolvendo status e corpo mesmo nas recusas."""
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def _pendurar_decisao(base_url: str) -> None:
    """Projeto, Setor, Sessão e uma Decision produzida pela sessão."""
    nos = (
        {"tipo": "Projeto", "rotulo": "Projeto HTTP", "id_no": "p-http"},
        {"tipo": "Setor", "rotulo": "Memoria", "id_no": "s-http", "contido_em": "p-http"},
        {"tipo": "Sessao", "rotulo": "Sessao HTTP", "id_no": "sess-http", "contido_em": "s-http"},
        {"tipo": "Decision", "rotulo": "Decisao HTTP", "id_no": "dec-http", "sessao_id": "sess-http"},
    )
    for corpo in nos:
        status, recibo = _postar(f"{base_url}/api/nodes", corpo)
        assert status == 201 and recibo["sucesso"] is True, recibo


def test_registrar_promover_e_ler_a_memoria_pelo_servidor_nominal() -> None:
    """O painel chega ao mesmo grafo por três rotas: registro, promoção e leitura."""
    with _servidor() as base_url:
        _pendurar_decisao(base_url)

        status, recibo = _postar(
            f"{base_url}/api/memoria/aprendizados",
            {"afirmacao": "Contencao no mesmo lote", "id_sessao": "sess-http", "origens": ["dec-http"], "id_aprendizado": "apr-http"},
        )
        assert status == 201 and recibo["sucesso"] is True, recibo

        status, recibo = _postar(f"{base_url}/api/memoria/promocoes", {"id_aprendizado": "apr-http", "global": True})
        assert status == 200 and recibo["sucesso"] is True, recibo

        with urllib.request.urlopen(f"{base_url}/api/memoria?ramo=main") as resp:
            assert resp.status == 200
            memoria = json.loads(resp.read().decode("utf-8"))

    assert memoria["sucesso"] is True
    assert [item["id"] for item in memoria["aprendizados"]] == ["apr-http"]
    assert memoria["aprendizados"][0]["alcances"] == ["global"]
    assert memoria["aprendizados"][0]["origens"][0]["id"] == "dec-http"
    assert [sessao["id"] for sessao in memoria["sessoes"]] == ["sess-http"]


def test_rotas_da_memoria_recusam_identidade_declarada_no_corpo_edge_case() -> None:
    """Caso de borda: a mesma recusa das outras escritas, para o painel não crer que `papel` surte efeito."""
    with _servidor() as base_url:
        _pendurar_decisao(base_url)

        status, recibo = _postar(
            f"{base_url}/api/memoria/aprendizados",
            {"afirmacao": "x", "id_sessao": "sess-http", "origens": ["dec-http"], "papel": "executor"},
        )
        assert status == 400
        assert recibo["sucesso"] is False

        status, _ = _postar(f"{base_url}/api/memoria/promocoes", {"id_aprendizado": "apr-x", "global": True, "autor": "alguem"})
        assert status == 400


def test_registro_sem_origem_volta_como_recusa_e_nao_como_erro_do_servidor_edge_case() -> None:
    """Caso de borda: o pedido incompleto volta com 400 e mensagem, não com traceback."""
    with _servidor() as base_url:
        _pendurar_decisao(base_url)

        status, recibo = _postar(f"{base_url}/api/memoria/aprendizados", {"afirmacao": "x", "id_sessao": "sess-http"})

    assert status == 400
    assert recibo["sucesso"] is False
    assert "origem" in recibo["mensagem"]
