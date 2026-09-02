"""Servidor HTTP integrado e despachante de rotas REST, SSE e Assets da interface do Graphow."""

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from typing import Any
import urllib.parse

from graphow.kernel.write_kernel import WriteKernel
from graphow.web.conversao_requisicoes import (
    converter_criar_fork,
    converter_edicao_no,
    converter_exclusao_lote,
    converter_exclusao_projeto,
    converter_nova_aresta,
    converter_novo_no,
    converter_salvar_layout,
    converter_simular_vista,
)
from graphow.web.identidade_web import (
    IdentidadeSessaoWeb,
    detectar_identidade_declarada,
    montar_recusa_de_identidade,
)
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_fork_controller import ForkWebController
from graphow.web.rest_lineage_controller import LineageWebController
from graphow.web.rest_simulation_controller import SimulationWebController
from graphow.web.rest_timeline_controller import TimelineWebController
from graphow.reactive.engine import MotorReativo
from graphow.web.composicao import montar_tempo_real
from graphow.web.sse_controller import SSEWebController
from graphow.web.static_assets_provider import StaticAssetsProvider


class GraphowHTTPHandler(BaseHTTPRequestHandler):
    """Manipulador de requisições HTTP REST, SSE e arquivos estáticos."""

    server: "GraphowThreadingServer"

    def do_GET(self) -> None:
        """Despacha requisições GET para os controladores específicos."""
        url_parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(url_parsed.query)
        if not self._despachar_api_get(url_parsed.path, params):
            self._tratar_static_asset(url_parsed.path)

    def _despachar_api_get(self, caminho: str, params: Mapping[str, list[str]]) -> bool:
        """Despacha endpoints REST da API Graphow."""
        if caminho == "/api/sse":
            self._tratar_sse()
            return True
        rotas = {
            "/api/canvas": lambda: self._tratar_get_canvas(params),
            "/api/timeline": lambda: self._tratar_get_timeline(params),
            "/api/timeline/state": lambda: self._tratar_get_timeline_state(params),
            "/api/lineage": lambda: self._tratar_get_lineage(params),
            "/api/diff": lambda: self._tratar_get_diff(params),
            "/api/branches": lambda: self._responder_json({"ramos": self.server.fork_ctrl.listar_ramos()}, HTTPStatus.OK),
            "/api/simulation/expand": lambda: self._tratar_get_simulation_expand(params),
            "/api/identity": self._tratar_get_identity,
        }
        handler = rotas.get(caminho)
        if handler:
            handler()
            return True
        return False

    def do_POST(self) -> None:
        """Despacha requisições POST para controladores de mutação e simulação."""
        url_parsed = urllib.parse.urlparse(self.path)
        caminho = url_parsed.path
        payload = self._ler_payload_json()

        if caminho == "/api/nodes":
            self._tratar_post_node(payload)
            return
        if caminho == "/api/edges":
            self._tratar_post_edge(payload)
            return
        if caminho == "/api/forks":
            self._tratar_post_fork(payload)
            return
        if caminho == "/api/simulation/view":
            self._tratar_post_simulation_view(payload)
            return

        self._responder_json({"erro": "Rota POST desconhecida"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        """Despacha requisições PUT para edição de nós e persistência de layout."""
        url_parsed = urllib.parse.urlparse(self.path)
        if url_parsed.path == "/api/layout":
            self._tratar_put_layout(self._ler_payload_json())
            return
        if url_parsed.path == "/api/nodes":
            self._tratar_put_node(self._ler_payload_json())
            return
        self._responder_json({"erro": "Rota PUT desconhecida"}, HTTPStatus.NOT_FOUND)

    def _tratar_put_node(self, payload: Mapping[str, Any]) -> None:
        """Aplica a edição de um nó sob a identidade fixada no servidor."""
        if self._recusar_identidade_declarada(payload):
            return
        recibo = self.server.canvas_ctrl.editar_no(converter_edicao_no(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _recusar_identidade_declarada(self, payload: Mapping[str, Any]) -> bool:
        """Recusa o corpo que tenta declarar autor ou papel, e diz por quê.

        É a mesma recusa observável do servidor MCP: aceitar o campo em
        silêncio faria a interface crer que ele surte efeito. Ver achado A-11.
        """
        campos = detectar_identidade_declarada(payload)
        if not campos:
            return False
        recusa = montar_recusa_de_identidade(campos, self.server.identidade)
        self._responder_json(recusa, HTTPStatus.BAD_REQUEST)
        return True

    def _tratar_put_layout(self, payload: Mapping[str, Any]) -> None:
        """Persiste no grafo as coordenadas informadas pelo canvas."""
        if self._recusar_identidade_declarada(payload):
            return
        recibo = self.server.canvas_ctrl.salvar_layout(converter_salvar_layout(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        """Despacha requisições DELETE para remoção de nós ou arestas."""
        url_parsed = urllib.parse.urlparse(self.path)
        caminho = url_parsed.path
        payload = self._ler_payload_json()
        if caminho == "/api/elements":
            self._tratar_delete_element(payload)
            return
        if caminho in ("/api/elements/batch", "/api/batch"):
            self._tratar_delete_batch(payload)
            return
        if caminho == "/api/projects":
            self._tratar_delete_project(payload)
            return
        self._responder_json({"erro": "Rota DELETE desconhecida"}, HTTPStatus.NOT_FOUND)

    def _tratar_delete_element(self, payload: Mapping[str, Any]) -> None:
        """Processa exclusão individual de elemento."""
        tipo = str(payload.get("tipo", "nos"))
        id_elem = str(payload.get("id", ""))
        ramo = str(payload.get("ramo_id", "main"))
        recibo = self.server.canvas_ctrl.remover_elemento(tipo, id_elem, ramo)
        self._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_delete_batch(self, payload: Mapping[str, Any]) -> None:
        """Processa exclusão em lote de nós e arestas."""
        recibo = self.server.canvas_ctrl.remover_lote(converter_exclusao_lote(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_delete_project(self, payload: Mapping[str, Any]) -> None:
        """Processa exclusão em cascata de projeto inteiro."""
        recibo = self.server.canvas_ctrl.remover_projeto_completo(
            converter_exclusao_projeto(payload)
        )
        self._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_get_canvas(self, params: Mapping[str, list[str]]) -> None:
        """Processa consulta do estado do Canvas."""
        ramo = params.get("ramo", ["main"])[0]
        sessao = params.get("sessao", [None])[0]
        projeto = params.get("projeto", [None])[0]
        dados = self.server.canvas_ctrl.obter_canvas(ramo, sessao, projeto)
        self._responder_json(self._serializar_dados_canvas(dados), HTTPStatus.OK)

    def _serializar_dados_canvas(self, dados: Any) -> dict[str, Any]:
        """Converte DTO DadosCanvasVisual em dicionário serializável."""
        return {
            "ramo_id": dados.ramo_id,
            "versao_log": dados.versao_log,
            "total_nos": dados.total_nos,
            "total_arestas": dados.total_arestas,
            "nos": [n.__dict__ for n in dados.nos],
            "arestas": [a.__dict__ for a in dados.arestas],
        }

    def _tratar_get_timeline(self, params: Mapping[str, list[str]]) -> None:
        """Processa consulta da timeline de eventos."""
        ramo = params.get("ramo", ["main"])[0]
        autor = params.get("autor", [None])[0]
        papel = params.get("papel", [None])[0]
        eventos = self.server.timeline_ctrl.obter_eventos(ramo, autor, papel)
        self._responder_json({"eventos": eventos}, HTTPStatus.OK)

    def _tratar_get_timeline_state(self, params: Mapping[str, list[str]]) -> None:
        """Processa reconstrução de estado histórico para time-travel."""
        versao = int(params.get("versao", [0])[0])
        ramo = params.get("ramo", ["main"])[0]
        dados = self.server.timeline_ctrl.obter_estado_na_versao(versao, ramo)
        self._responder_json(self._serializar_dados_canvas(dados), HTTPStatus.OK)

    def _tratar_get_lineage(self, params: Mapping[str, list[str]]) -> None:
        """Processa consulta de linhagem causal reversa."""
        id_no = params.get("id", [""])[0]
        ramo = params.get("ramo", ["main"])[0]
        linhagem = self.server.lineage_ctrl.obter_linhagem(id_no, ramo)
        self._responder_json(linhagem, HTTPStatus.OK)

    def _tratar_get_diff(self, params: Mapping[str, list[str]]) -> None:
        """Processa consulta de diff entre ramos."""
        ramo_a = params.get("ramo_a", ["main"])[0]
        ramo_b = params.get("ramo_b", ["main"])[0]
        diff = self.server.fork_ctrl.calcular_diff_ramos(ramo_a, ramo_b)
        self._responder_json(diff, HTTPStatus.OK)

    def _tratar_get_identity(self) -> None:
        """Publica a identidade sob a qual esta sessão web escreve no grafo."""
        identidade = self.server.identidade
        self._responder_json(
            {"autor": identidade.autor, "papel": identidade.papel_textual}, HTTPStatus.OK
        )

    def _tratar_get_simulation_expand(self, params: Mapping[str, list[str]]) -> None:
        """Processa expansão de nó sob demanda."""
        id_no = params.get("id", [""])[0]
        ramo = params.get("ramo", ["main"])[0]
        resultado = self.server.sim_ctrl.expandir_no(id_no, ramo)
        self._responder_json(resultado, HTTPStatus.OK if resultado["sucesso"] else HTTPStatus.NOT_FOUND)

    def _tratar_post_node(self, payload: Mapping[str, Any]) -> None:
        """Processa criação de novo nó."""
        if self._recusar_identidade_declarada(payload):
            return
        recibo = self.server.canvas_ctrl.criar_no(converter_novo_no(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.CREATED if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_post_edge(self, payload: Mapping[str, Any]) -> None:
        """Processa criação de nova aresta."""
        if self._recusar_identidade_declarada(payload):
            return
        recibo = self.server.canvas_ctrl.criar_aresta(converter_nova_aresta(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.CREATED if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_post_fork(self, payload: Mapping[str, Any]) -> None:
        """Processa criação de nova ramificação fork."""
        if self._recusar_identidade_declarada(payload):
            return
        recibo = self.server.fork_ctrl.criar_fork(converter_criar_fork(payload))
        self._responder_json(recibo.__dict__, HTTPStatus.CREATED if recibo.sucesso else HTTPStatus.BAD_REQUEST)

    def _tratar_post_simulation_view(self, payload: Mapping[str, Any]) -> None:
        """Processa simulação de vista de contexto."""
        resultado = self.server.sim_ctrl.simular_vista(converter_simular_vista(payload))
        self._responder_json(resultado, HTTPStatus.OK if resultado["sucesso"] else HTTPStatus.BAD_REQUEST)

    def _tratar_sse(self) -> None:
        """Mantém conexão de streaming SSE aberta para o cliente."""
        fila = self.server.sse_ctrl.registrar_assinante()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            for mensagem in self.server.sse_ctrl.gerar_stream_para_fila(fila, timeout_segundos=2.0):
                self.wfile.write(mensagem.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass
        finally:
            self.server.sse_ctrl.remover_assinante(fila)

    def _tratar_static_asset(self, caminho: str) -> None:
        """Serve arquivo HTML/CSS/JS estático através do provider seguro."""
        recurso = self.server.assets_provider.obter_recurso(caminho)
        self.send_response(recurso.status_code)
        self.send_header("Content-Type", recurso.tipo_conteudo)
        self.send_header("Content-Length", str(len(recurso.conteudo)))
        self.end_headers()
        self.wfile.write(recurso.conteudo)

    def _ler_payload_json(self) -> dict[str, Any]:
        """Lê o corpo da requisição e desserializa em dicionário."""
        comprimento = int(self.headers.get("Content-Length", 0))
        if comprimento == 0:
            return {}
        corpo = self.rfile.read(comprimento)
        try:
            return json.loads(corpo.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia resposta JSON formatada com headers adequados."""
        corpo_bytes = json.dumps(dict(conteudo), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo_bytes)))
        self.end_headers()
        self.wfile.write(corpo_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        """Silencia logs padrões do BaseHTTPRequestHandler para não poluir terminal."""
        pass


def eh_desconexao_do_cliente(erro: BaseException | None) -> bool:
    """Indica se a exceção é o cliente tendo ido embora, e não uma falha do servidor.

    As três variantes existem porque o sistema operacional escolhe qual levantar:
    Windows aborta (10053), Unix costuma resetar ou quebrar o cano. Tratar só as
    que aparecem na máquina de quem escreveu o código é como o traceback do SSE
    sobreviveu — o `except` já existia, faltava o irmão do Windows.
    """
    return isinstance(erro, ConnectionError)


class GraphowThreadingServer(ThreadingHTTPServer):
    """Servidor HTTP multithread contendo instâncias injetadas dos controladores."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Descarta o ruído da desconexão e deixa passar todo o resto.

        Um navegador que recarrega derruba o socket no meio de uma escrita, e o
        SSE vive disso: cada F5 rendia um traceback completo. Ruído constante é o
        que faz uma falha real passar batido, então o filtro é estreito — só o
        cliente sumindo. Qualquer outra exceção continua indo para o tratamento
        padrão, com o traceback inteiro.
        """
        if eh_desconexao_do_cliente(sys.exc_info()[1]):
            return
        super().handle_error(request, client_address)

    def __init__(
        self,
        endereco: tuple[str, int],
        kernel: WriteKernel,
        identidade: IdentidadeSessaoWeb | None = None,
    ) -> None:
        self.identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb.do_usuario_local()
        self.canvas_ctrl: CanvasWebController = CanvasWebController(kernel, self.identidade)
        self.timeline_ctrl: TimelineWebController = TimelineWebController(kernel.repositorio)
        self.lineage_ctrl: LineageWebController = LineageWebController(kernel)
        self.fork_ctrl: ForkWebController = ForkWebController(kernel, self.identidade)
        self.sim_ctrl: SimulationWebController = SimulationWebController(kernel)
        self.sse_ctrl: SSEWebController = SSEWebController()
        self.assets_provider: StaticAssetsProvider = StaticAssetsProvider()
        self.motor_reativo: MotorReativo = montar_tempo_real(kernel, self.sse_ctrl)
        super().__init__(endereco, GraphowHTTPHandler)


@dataclass(frozen=True)
class EnderecoServidor:
    """Host e porta em que a interface do canvas fica disponível."""

    host: str = "127.0.0.1"
    porta: int = 8000


class GraphowWebServer:
    """Gerenciador de alto nível para inicialização e desligamento do servidor web."""

    def __init__(
        self,
        kernel: WriteKernel,
        endereco: EnderecoServidor | None = None,
        identidade: IdentidadeSessaoWeb | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._endereco: EnderecoServidor = endereco or EnderecoServidor()
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb.do_usuario_local()
        self._server: GraphowThreadingServer | None = None
        self._thread: threading.Thread | None = None

    def iniciar(self, bloqueante: bool = False) -> None:
        """Inicializa o servidor HTTP na porta configurada."""
        self._server = GraphowThreadingServer(
            (self._endereco.host, self._endereco.porta), self._kernel, self._identidade
        )
        if bloqueante:
            self._server.serve_forever()
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        """Encerra o servidor e fecha os sockets."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
