"""Testes de integração HTTP para o GraphowWebServer."""

import json
import socket
import time
import urllib.error
import urllib.request

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.server import EnderecoServidor, GraphowWebServer, eh_desconexao_do_cliente


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_servidor_http_fluxo_nominal_get_post_put() -> None:
    """Valida inicialização, requisições GET, POST, PUT e encerramento do servidor."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{porta}"
    try:
        # 1. GET /api/canvas
        with urllib.request.urlopen(f"{base_url}/api/canvas") as resp:
            assert resp.status == 200
            dados = json.loads(resp.read().decode("utf-8"))
            assert dados["total_nos"] == 0

        # 2. POST /api/nodes
        payload_post = json.dumps({"tipo": "Goal", "rotulo": "Meta Via HTTP", "id_no": "g-http"}).encode("utf-8")
        req_post = urllib.request.Request(f"{base_url}/api/nodes", data=payload_post, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_post) as resp:
            assert resp.status == 201
            recibo = json.loads(resp.read().decode("utf-8"))
            assert recibo["sucesso"] is True

        # 3. GET / (index.html)
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")

    finally:
        servidor.parar()


def test_servidor_http_rota_desconhecida_retorna_404_edge_case() -> None:
    """Valida resposta 404 para rotas desconhecidas."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{porta}"
    try:
        req = urllib.request.Request(f"{base_url}/api/rota_desconhecida", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert False, "Deveria ter falhado"
    except urllib.error.HTTPError as err:
        assert err.code == 404
    finally:
        servidor.parar()


def test_servidor_http_delete_elementos_edge_case() -> None:
    """Valida requisição DELETE para exclusão de nós."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{porta}"
    try:
        # Cria nó
        payload_post = json.dumps({"tipo": "Task", "rotulo": "Para Deletar", "id_no": "t-del"}).encode("utf-8")
        req_post = urllib.request.Request(f"{base_url}/api/nodes", data=payload_post, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req_post)

        # Deleta nó via DELETE
        payload_del = json.dumps({"tipo": "nos", "id": "t-del"}).encode("utf-8")
        req_del = urllib.request.Request(f"{base_url}/api/elements", data=payload_del, headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(req_del) as resp:
            assert resp.status == 200
            recibo = json.loads(resp.read().decode("utf-8"))
            assert recibo["sucesso"] is True
    finally:
        servidor.parar()


def test_desconexao_do_cliente_nao_conta_como_falha_nominal() -> None:
    """As três variantes de queda de socket são o cliente indo embora, não erro.

    Qual delas o sistema levanta é escolha do sistema operacional: Windows aborta,
    Unix costuma resetar ou quebrar o cano. Tratar só as que aparecem na máquina de
    quem escreveu o código foi como o traceback do SSE sobreviveu.
    """
    quedas = (BrokenPipeError(), ConnectionAbortedError(), ConnectionResetError())
    assert all(eh_desconexao_do_cliente(queda) for queda in quedas)


def test_falha_real_continua_sendo_falha_edge_case() -> None:
    """Caso de borda: o filtro é estreito — só a desconexão passa em silêncio."""
    assert eh_desconexao_do_cliente(ValueError("payload malformado")) is False
    assert eh_desconexao_do_cliente(KeyError("id_no")) is False
    assert eh_desconexao_do_cliente(TimeoutError()) is False


def test_ausencia_de_excecao_nao_e_desconexao_edge_case() -> None:
    """Caso de borda: sem exceção em curso, não há o que silenciar."""
    assert eh_desconexao_do_cliente(None) is False


def test_servidor_sobrevive_a_cliente_que_desiste_no_meio_edge_case() -> None:
    """Caso de borda: fechar o socket durante o SSE não derruba nem suja o servidor."""
    kernel = WriteKernel(InMemoryEventStore())
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        conexao = socket.create_connection(("127.0.0.1", porta), timeout=2)
        conexao.sendall(b"GET /api/sse HTTP/1.1\r\nHost: localhost\r\n\r\n")
        conexao.recv(64)
        conexao.close()
        time.sleep(0.2)

        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/canvas", timeout=3) as resposta:
            assert json.loads(resposta.read().decode("utf-8"))["total_nos"] == 0
    finally:
        servidor.parar()
