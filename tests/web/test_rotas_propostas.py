"""Testes das rotas HTTP das propostas: ler a caixa e decidir uma proposta pelo servidor real."""

import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from graphow.core.escopo import ACAO_PROPOSTA_FORA_DO_GOAL
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.server import EnderecoServidor, GraphowWebServer
from tests.web.cliente_http import cabecalhos_de_escrita


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
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers=cabecalhos_de_escrita(url))
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def _ler(url: str) -> dict[str, Any]:
    """GET devolvendo o corpo JSON."""
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        return json.loads(resp.read().decode("utf-8"))


def _pendurar_proposta(base_url: str) -> None:
    """Projeto, Sessão e uma proposta fora do Goal produzida pela sessão."""
    nos = (
        {"tipo": "Projeto", "rotulo": "Projeto HTTP", "id_no": "p-http"},
        {"tipo": "Setor", "rotulo": "Setor HTTP", "id_no": "s-http", "contido_em": "p-http"},
        {"tipo": "Sessao", "rotulo": "Sessao HTTP", "id_no": "sess-http", "contido_em": "s-http"},
        {"tipo": "Note", "rotulo": "Ideia fora do Goal", "id_no": "prop-http", "sessao_id": "sess-http", "propriedades": {"acao": ACAO_PROPOSTA_FORA_DO_GOAL}},
    )
    for corpo in nos:
        status, recibo = _postar(f"{base_url}/api/nodes", corpo)
        assert status == 201 and recibo["sucesso"] is True, recibo


def test_ler_e_decidir_a_proposta_pelo_servidor_nominal() -> None:
    """A caixa lê a proposta aberta, o humano a aceita, e ela some da próxima leitura."""
    with _servidor() as base_url:
        _pendurar_proposta(base_url)
        antes = _ler(f"{base_url}/api/propostas?ramo=main&projeto=p-http")

        status, recibo = _postar(f"{base_url}/api/propostas/decisoes", {"id_proposta": "prop-http", "status": "aceita"})
        depois = _ler(f"{base_url}/api/propostas")

    assert [p["id"] for p in antes["propostas"]] == ["prop-http"]
    assert antes["propostas"][0]["projeto_rotulo"] == "Projeto HTTP"
    assert status == 200 and recibo["sucesso"] is True, recibo
    assert depois["propostas"] == []


def test_decisao_invalida_volta_400_edge_case() -> None:
    """Caso de borda: status fora de aceita e descartada é recusado com 400, sem tocar o grafo."""
    with _servidor() as base_url:
        _pendurar_proposta(base_url)

        status, recibo = _postar(f"{base_url}/api/propostas/decisoes", {"id_proposta": "prop-http", "status": "feita"})
        ainda = _ler(f"{base_url}/api/propostas")

    assert status == 400 and recibo["sucesso"] is False
    assert [p["id"] for p in ainda["propostas"]] == ["prop-http"]


def test_decisao_que_declara_identidade_e_recusada_edge_case() -> None:
    """Caso de borda: autor e papel são do servidor, e o corpo que os declara é recusado."""
    with _servidor() as base_url:
        _pendurar_proposta(base_url)

        status, _ = _postar(
            f"{base_url}/api/propostas/decisoes",
            {"id_proposta": "prop-http", "status": "aceita", "papel": "arbitro"},
        )

    assert status == 400
