"""Testes de integração HTTP para o GraphowWebServer."""

import json
import socket
import time
import urllib.error
import urllib.request

from graphow.harness.ambiente_padrao import AmbientePadrao, GarantidorDeAmbientePadrao
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.desconexao_cliente import eh_desconexao_do_cliente
from graphow.web.server import EnderecoServidor, GraphowWebServer


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _postar_no(base_url: str, corpo: dict[str, str]) -> dict[str, object]:
    """Cria um nó por POST em /api/nodes e devolve o recibo, exigindo sucesso."""
    req = urllib.request.Request(f"{base_url}/api/nodes", data=json.dumps(corpo).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        recibo = json.loads(resp.read().decode("utf-8"))
    assert recibo["sucesso"] is True
    return recibo


def _pendurar_sessao(base_url: str) -> str:
    """Monta Projeto, Setor e Sessao pela API para que o trabalho nasça dentro da hierarquia."""
    _postar_no(base_url, {"tipo": "Projeto", "rotulo": "Projeto HTTP", "id_no": "p-http"})
    _postar_no(base_url, {"tipo": "Setor", "rotulo": "Setor HTTP", "id_no": "s-http", "contido_em": "p-http"})
    _postar_no(base_url, {"tipo": "Sessao", "rotulo": "Sessao HTTP", "id_no": "sess-http", "contido_em": "s-http"})
    return "sess-http"


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
        sessao_id = _pendurar_sessao(base_url)
        _postar_no(base_url, {"tipo": "Goal", "rotulo": "Meta Via HTTP", "id_no": "g-http", "sessao_id": sessao_id})

        # 3. GET / (index.html)
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")

    finally:
        servidor.parar()


def test_servidor_http_publica_busca_ontologia_e_escopo_por_setor_nominal() -> None:
    """As três leituras novas da moldura respondem pelo roteador, não só pelo controlador."""
    kernel = WriteKernel(InMemoryEventStore())
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{porta}"
    try:
        for corpo in ({"tipo": "Projeto", "rotulo": "Alfa", "id_no": "p"}, {"tipo": "Setor", "rotulo": "Setor Alfa", "id_no": "s", "contido_em": "p"}):
            req = urllib.request.Request(f"{base_url}/api/nodes", data=json.dumps(corpo).encode("utf-8"), headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req)

        with urllib.request.urlopen(f"{base_url}/api/busca?termo=alfa&limite=1") as resp:
            busca = json.loads(resp.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/api/ontologia") as resp:
            ontologia = json.loads(resp.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/api/canvas?setor=s") as resp:
            canvas = json.loads(resp.read().decode("utf-8"))

        assert busca["total"] == 2 and busca["truncado"] is True
        assert ["Projeto", "Setor"] in ontologia["arestas"]["contem"]
        assert [no["id"] for no in canvas["nos"]] == ["s"]
    finally:
        servidor.parar()


def test_servidor_http_separa_projetos_das_sessoes_do_hook_pelo_ambito_nominal() -> None:
    """O parâmetro `ambito` chega ao controlador, e a resposta traz o total de cada raiz."""
    kernel = WriteKernel(InMemoryEventStore())
    GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="meu-repo"))
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)

    base_url = f"http://127.0.0.1:{porta}"
    try:
        _postar_no(base_url, {"tipo": "Projeto", "rotulo": "Trabalho", "id_no": "p"})
        with urllib.request.urlopen(f"{base_url}/api/canvas?ambito=hook") as resp:
            hook = json.loads(resp.read().decode("utf-8"))
        with urllib.request.urlopen(f"{base_url}/api/canvas?ambito=projetos") as resp:
            projetos = json.loads(resp.read().decode("utf-8"))

        assert {no["id"] for no in hook["nos"]} == {"proj-meu-repo", "setor-meu-repo-memoria"}
        assert [(no["id"], no["ambito"]) for no in projetos["nos"]] == [("p", "projetos")]
        assert projetos["total_por_ambito"] == {"projetos": 1, "hook": 2}
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
        sessao_id = _pendurar_sessao(base_url)
        _postar_no(base_url, {"tipo": "Task", "rotulo": "Para Deletar", "id_no": "t-del", "sessao_id": sessao_id})

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
