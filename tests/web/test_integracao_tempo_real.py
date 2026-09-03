"""Testes de fiação do tempo real: uma mutação aceita precisa chegar ao assinante.

Era exatamente esta asserção que faltava na suíte: o canal SSE existia, era testado
isoladamente e nunca recebia nada em produção. Ver auditoria F-05.
"""

from collections.abc import Iterable
import json
import queue
import socket
import threading
import time
import urllib.request

from graphow.core.events import EventoLog, TipoEvento
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.composicao import montar_tempo_real
from graphow.web.identidade_web import IdentidadeSessaoWeb
from graphow.web.server import EnderecoServidor, GraphowWebServer
from graphow.web.sse_controller import NOME_EVENTO_DESCARTE, SSEWebController

TEMPO_LIMITE_DE_ESPERA: float = 5.0
SEPARADOR_DE_BLOCO_SSE: str = "\n\n"


def _montar_ambiente() -> tuple[WriteKernel, SSEWebController]:
    """Monta kernel e canal SSE já ligados pelo gancho pós-commit."""
    kernel = WriteKernel(InMemoryEventStore())
    controlador = SSEWebController()
    montar_tempo_real(kernel, controlador)
    return kernel, controlador


def _criar_task(kernel: WriteKernel, id_task: str, status: str = StatusTask.PENDENTE.value) -> None:
    """Cria a Sessao e a Task com o status informado, ligadas por `produz`."""
    operacoes = (
        ItemPatch(
            op=OperacaoPatch.ADD,
            path="/nos/sess-obs",
            value={"id": "sess-obs", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao observada"},
        ),
        ItemPatch(
            op=OperacaoPatch.ADD,
            path=f"/nos/{id_task}",
            value={
                "id": id_task,
                "tipo": TipoNo.TASK.value,
                "rotulo": "Tarefa observada",
                "propriedades": {"status": status},
            },
        ),
        ItemPatch(
            op=OperacaoPatch.ADD,
            path=f"/arestas/prod-{id_task}",
            value={
                "id": f"prod-{id_task}",
                "origem_id": "sess-obs",
                "destino_id": id_task,
                "tipo": TipoAresta.PRODUZ.value,
            },
        ),
    )
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="criacao"
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))


def _coletar(fila: "queue.Queue[EventoLog]", total: int) -> list[EventoLog]:
    """Retira do canal a quantidade de eventos esperada, sem travar o teste."""
    coletados: list[EventoLog] = []
    for _ in range(total):
        coletados.append(fila.get(timeout=TEMPO_LIMITE_DE_ESPERA))
    return coletados


def test_mutacao_aceita_chega_ao_assinante_sse_nominal() -> None:
    """O evento persistido é publicado no canal de tempo real."""
    kernel, controlador = _montar_ambiente()
    fila = controlador.registrar_assinante()

    _criar_task(kernel, "task-1")

    eventos = _coletar(fila, 3)
    assert eventos[1].tipo_evento == TipoEvento.NO_CRIADO
    assert eventos[1].payload["id"] == "task-1"


def test_observadores_ficam_registrados_no_kernel_nominal() -> None:
    """A fiação é explícita: o kernel sabe quem está escutando."""
    kernel, _ = _montar_ambiente()
    assert kernel.observadores_registrados == ("CanalSSE", "MotorReativo")


def test_comportamento_reativo_dispara_e_tambem_e_publicado() -> None:
    """Uma Task pronta para revisão gera a nota do revisor, que também chega ao canvas."""
    kernel, controlador = _montar_ambiente()
    _criar_task(kernel, "task-1")
    fila = controlador.registrar_assinante()

    operacao = ItemPatch(
        op=OperacaoPatch.REPLACE,
        path="/nos/task-1/propriedades/status",
        value=StatusTask.PRONTO_PARA_REVISAO.value,
    )
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=(operacao,), justificativa="revisao"
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))

    eventos = _coletar(fila, 2)
    assert eventos[0].tipo_evento == TipoEvento.NO_ATUALIZADO
    assert eventos[1].tipo_evento == TipoEvento.NO_CRIADO
    assert "Revisao" in str(eventos[1].payload["rotulo"])


def test_lote_multiplo_publica_todos_os_eventos_edge_case() -> None:
    """Caso de borda: um patch com várias operações publica um evento por operação."""
    kernel, controlador = _montar_ambiente()
    fila = controlador.registrar_assinante()

    operacoes = tuple(
        ItemPatch(
            op=OperacaoPatch.ADD,
            path=f"/nos/n{indice}",
            value={"id": f"n{indice}", "tipo": TipoNo.NOTE.value, "rotulo": f"Nota {indice}"},
        )
        for indice in range(3)
    )
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="lote"
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))

    assert [evento.payload["id"] for evento in _coletar(fila, 3)] == ["n0", "n1", "n2"]


def test_patch_rejeitado_nao_publica_nada_edge_case() -> None:
    """Caso de borda: o que os portões recusam não chega ao canal de tempo real."""
    kernel, controlador = _montar_ambiente()
    fila = controlador.registrar_assinante()

    operacao = ItemPatch(
        op=OperacaoPatch.ADD,
        path="/nos/c1",
        value={"id": "c1", "tipo": TipoNo.CONSTRAINT.value, "rotulo": "Restricao"},
    )
    dados = DadosPropostaPatch(
        autor="agente", papel=PapelAutor.EXECUTOR, operacoes=(operacao,), justificativa="tentativa"
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is False
    assert fila.empty() is True


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_evento_atravessa_o_servidor_http_ate_o_stream_sse() -> None:
    """Ponta a ponta sobre HTTP: POST em /api/nodes vira mensagem no stream SSE."""
    porta = _obter_porta_livre()
    identidade = IdentidadeSessaoWeb(autor="humano-ui")
    servidor = GraphowWebServer(
        WriteKernel(InMemoryEventStore()), EnderecoServidor(porta=porta), identidade
    )
    servidor.iniciar(bloqueante=False)
    time.sleep(0.1)
    try:
        recebidas = _ler_stream_apos_mutacao(f"http://127.0.0.1:{porta}")
    finally:
        servidor.parar()

    bloco_da_mutacao = _localizar_bloco(recebidas, "event: no_criado")
    corpo = json.loads(_extrair_dados(bloco_da_mutacao))
    assert corpo["payload"]["rotulo"] == "Tarefa via HTTP"
    assert corpo["autor"] == "humano-ui"


def _localizar_bloco(fluxo_recebido: list[str], marcador: str) -> str:
    """Encontra, no fluxo bruto, o bloco SSE que carrega o marcador informado."""
    blocos = "".join(fluxo_recebido).split(SEPARADOR_DE_BLOCO_SSE)
    correspondentes = [bloco for bloco in blocos if marcador in bloco]
    assert correspondentes, f"marcador {marcador} ausente em {blocos}"
    return correspondentes[0]


def _extrair_dados(bloco: str) -> str:
    """Isola a linha 'data:' de um bloco SSE."""
    linhas_de_dados = [linha for linha in bloco.splitlines() if linha.startswith("data: ")]
    assert len(linhas_de_dados) == 1, bloco
    return linhas_de_dados[0].removeprefix("data: ")


def _ler_stream_apos_mutacao(base_url: str) -> list[str]:
    """Assina o stream, dispara a mutação e devolve os blocos SSE recebidos."""
    blocos: list[str] = []
    pronto = threading.Event()
    leitor = threading.Thread(target=_consumir_stream, args=(base_url, blocos, pronto), daemon=True)
    leitor.start()
    pronto.wait(timeout=TEMPO_LIMITE_DE_ESPERA)

    corpo = json.dumps({"tipo": "Task", "rotulo": "Tarefa via HTTP"}).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{base_url}/api/nodes", data=corpo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE_DE_ESPERA) as resposta:
        assert resposta.status == 201
    leitor.join(timeout=TEMPO_LIMITE_DE_ESPERA)
    return blocos


def _consumir_stream(base_url: str, blocos: list[str], pronto: threading.Event) -> None:
    """Lê o stream SSE até o bloco da mutação terminar, sinalizando a conexão."""
    with urllib.request.urlopen(f"{base_url}/api/sse", timeout=TEMPO_LIMITE_DE_ESPERA) as fluxo:
        acumulado = ""
        for linha_bruta in fluxo:
            acumulado += linha_bruta.decode("utf-8")
            pronto.set()
            if not _bloco_de_mutacao_completo(acumulado):
                continue
            blocos.append(acumulado)
            return


def _bloco_de_mutacao_completo(acumulado: str) -> bool:
    """Um bloco SSE só está inteiro quando a linha em branco final chega."""
    if "event: no_criado" not in acumulado:
        return False
    posterior = acumulado.split("event: no_criado", 1)[1]
    return SEPARADOR_DE_BLOCO_SSE in posterior


def test_assinante_descartado_recebe_o_fim_do_stream_edge_case() -> None:
    """Caso de borda: o descarte precisa chegar como fim de resposta, e nao como silencio.

    Encerrar o iterador nao bastaria sozinho: o cabecalho manda `keep-alive`, e sem
    fechar a conexao o navegador ficaria com um `EventSource` vivo, sem evento algum
    e sem `onerror` — logo sem nunca reconectar, que e o mesmo sintoma de nao haver
    tempo real. E essa travessia que o teste amarra, do controlador ate o socket.
    """
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(WriteKernel(InMemoryEventStore()), EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.1)
    try:
        recebido = _ler_stream_ate_o_descarte(f"http://127.0.0.1:{porta}", servidor)
    finally:
        servidor.parar()

    assert f"event: {NOME_EVENTO_DESCARTE}" in recebido


def _ler_stream_ate_o_descarte(base_url: str, servidor: GraphowWebServer) -> str:
    """Assina o stream, descarta o assinante pelo controlador e le ate o fim da resposta."""
    with urllib.request.urlopen(f"{base_url}/api/sse", timeout=TEMPO_LIMITE_DE_ESPERA) as fluxo:
        acumulado = fluxo.readline().decode("utf-8")
        _descartar_o_unico_assinante(servidor)
        return acumulado + _ler_ate_a_resposta_terminar(fluxo)


def _ler_ate_a_resposta_terminar(fluxo: Iterable[bytes]) -> str:
    """Le o restante da resposta, desistindo se o servidor insistir em mante-la aberta.

    O prazo nao e zelo excessivo: sem ele, o defeito que este teste cobre faz o
    laco receber pings para sempre, e um teste que trava nao acusa nada.
    """
    limite = time.time() + TEMPO_LIMITE_DE_ESPERA
    recebido = ""
    for linha in fluxo:
        recebido += linha.decode("utf-8")
        if time.time() > limite:
            return recebido
    return recebido


def _descartar_o_unico_assinante(servidor: GraphowWebServer) -> None:
    """Faz pelo controlador o mesmo que a fila cheia faz com um cliente lento."""
    controlador = servidor._server.sse_ctrl
    controlador.remover_assinante(controlador._assinantes[0])
