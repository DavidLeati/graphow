"""Testes do vigia que traz ao canvas o que outro processo escreveu no log.

O canal SSE era alimentado apenas pelo gancho pós-commit deste processo. O agente
MCP escreve de fora, no mesmo banco: o evento chegava ao SQLite e nunca ao
navegador, que só via a novidade recarregando a página. É essa travessia — do
kernel de fora até a fila do assinante — que os testes aqui amarram.
"""

from pathlib import Path
import queue
import time

from graphow.core.events import EventoLog, TipoEvento
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.lineage.fork_manager import ForkManager, PedidoFork
from graphow.storage.composicao import ConjuntoRepositorios, abrir_repositorios_sqlite, montar_repositorios_em_memoria
from graphow.web.composicao import montar_tempo_real
from graphow.web.sse_controller import SSEWebController
from graphow.web.vigia_do_log import VigiaDoLogExterno

TEMPO_LIMITE_DE_ESPERA: float = 5.0
INTERVALO_CURTO: float = 0.05
ID_SESSAO: str = "sess-vigia"


def _montar_kernel(repositorios: ConjuntoRepositorios) -> WriteKernel:
    """Monta um kernel independente sobre um conjunto de repositórios já composto."""
    dependencias = DependenciasKernel(
        repositorio_locks=repositorios.locks, repositorio_ramos=repositorios.ramos
    )
    return WriteKernel(repositorios.eventos, dependencias)


def _montar_vigia(repositorios: ConjuntoRepositorios, controlador: SSEWebController) -> VigiaDoLogExterno:
    """Cria o vigia sobre os mesmos repositórios, com intervalo curto para o teste."""
    return VigiaDoLogExterno(
        repositorios.eventos,
        controlador,
        repositorios.ramos,
        intervalo_segundos=INTERVALO_CURTO,
    )


def _operacao_de_no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch:
    """Operação que adiciona um nó."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo},
    )


def _operacao_de_aresta(origem_id: str, destino_id: str, tipo: TipoAresta) -> ItemPatch:
    """Operação que adiciona uma aresta tipada, com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{destino_id}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem_id, "destino_id": destino_id, "tipo": tipo.value},
    )


def _submeter(kernel: WriteKernel, operacoes: tuple[ItemPatch, ...], justificativa: str) -> None:
    """Submete o lote sob identidade humana, exigindo que os portões o aceitem."""
    dados = DadosPropostaPatch(
        autor="agente-de-fora",
        papel=PapelAutor.HUMANO,
        operacoes=operacoes,
        justificativa=justificativa,
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso is True, recibo.mensagem


def _montar_hierarquia(kernel: WriteKernel) -> None:
    """Projeto, Setor e Sessao onde as notas vão nascer penduradas."""
    operacoes = (
        _operacao_de_no("proj-vigia", TipoNo.PROJETO, "Projeto vigiado"),
        _operacao_de_no("setor-vigia", TipoNo.SETOR, "Setor vigiado"),
        _operacao_de_aresta("proj-vigia", "setor-vigia", TipoAresta.CONTEM),
        _operacao_de_no(ID_SESSAO, TipoNo.SESSAO, "Sessao vigiada"),
        _operacao_de_aresta("setor-vigia", ID_SESSAO, TipoAresta.CONTEM),
    )
    _submeter(kernel, operacoes, "hierarquia")


def _criar_nota(kernel: WriteKernel, id_no: str) -> None:
    """Escreve uma Note pendurada na Sessao por `produz`: dois eventos no log."""
    operacoes = (
        _operacao_de_no(id_no, TipoNo.NOTE, f"Nota {id_no}"),
        _operacao_de_aresta(ID_SESSAO, id_no, TipoAresta.PRODUZ),
    )
    _submeter(kernel, operacoes, "escrita externa")


def _drenar(fila: "queue.Queue[EventoLog]") -> list[EventoLog]:
    """Retira sem bloquear tudo o que já está na fila do assinante."""
    coletados: list[EventoLog] = []
    while not fila.empty():
        coletados.append(fila.get_nowait())
    return coletados


def _esperar_evento(fila: "queue.Queue[EventoLog]") -> EventoLog:
    """Espera o próximo evento do assinante dentro do tempo limite do teste."""
    return fila.get(timeout=TEMPO_LIMITE_DE_ESPERA)


def test_escrita_de_outro_kernel_chega_ao_assinante_nominal() -> None:
    """O evento que não passou pelo gancho pós-commit deste processo mesmo assim é publicado."""
    repositorios = montar_repositorios_em_memoria()
    _montar_hierarquia(_montar_kernel(repositorios))
    controlador = SSEWebController()
    vigia = _montar_vigia(repositorios, controlador)
    vigia.adotar_posicao_atual()
    fila = controlador.registrar_assinante()

    _criar_nota(_montar_kernel(repositorios), "nota-externa")
    assert vigia.varrer() == 2  # a Note e a aresta `produz` que a pendura

    evento = _esperar_evento(fila)
    assert evento.tipo_evento == TipoEvento.NO_CRIADO
    assert evento.payload["id"] == "nota-externa"


def test_agente_de_outro_processo_atualiza_o_canvas_sem_f5(tmp_path: Path) -> None:
    """Reprodução do defeito: dois kernels sobre o mesmo arquivo SQLite, um só canal.

    É a forma exata do problema em produção — `graphow web` e `graphow mcp` são
    processos distintos sobre o mesmo banco.
    """
    caminho_banco = tmp_path / "graphow.db"
    store_web, repositorios_web = abrir_repositorios_sqlite(caminho_banco)
    store_agente, repositorios_agente = abrir_repositorios_sqlite(caminho_banco)
    _montar_hierarquia(_montar_kernel(repositorios_agente))
    controlador = SSEWebController()
    montar_tempo_real(_montar_kernel(repositorios_web), controlador)
    vigia = _montar_vigia(repositorios_web, controlador)

    vigia.iniciar()
    fila = controlador.registrar_assinante()
    try:
        _criar_nota(_montar_kernel(repositorios_agente), "nota-do-agente")
        evento = _esperar_evento(fila)
    finally:
        vigia.parar()
        store_agente.fechar()
        store_web.fechar()

    assert evento.payload["id"] == "nota-do-agente"
    assert evento.autor == "agente-de-fora"


def test_evento_do_proprio_processo_nao_e_publicado_duas_vezes_edge_case() -> None:
    """Caso de borda: o gancho pós-commit e o vigia veem o mesmo fato; o canvas o vê uma vez."""
    repositorios = montar_repositorios_em_memoria()
    controlador = SSEWebController()
    kernel = _montar_kernel(repositorios)
    _montar_hierarquia(kernel)
    montar_tempo_real(kernel, controlador)
    vigia = _montar_vigia(repositorios, controlador)
    vigia.adotar_posicao_atual()
    fila = controlador.registrar_assinante()

    _criar_nota(kernel, "nota-local")
    vigia.varrer()

    publicados = _drenar(fila)
    assert [evento.payload["id"] for evento in publicados] == ["nota-local", "produz-nota-local"]


def test_historico_anterior_ao_inicio_nao_e_republicado_edge_case() -> None:
    """Caso de borda: quem conecta agora não recebe o log inteiro como se fosse novidade."""
    repositorios = montar_repositorios_em_memoria()
    kernel = _montar_kernel(repositorios)
    _montar_hierarquia(kernel)
    _criar_nota(kernel, "nota-antiga")

    controlador = SSEWebController()
    vigia = _montar_vigia(repositorios, controlador)
    vigia.adotar_posicao_atual()
    fila = controlador.registrar_assinante()

    assert vigia.varrer() == 0
    assert fila.empty() is True


def test_ramo_novo_publica_o_marco_sem_repetir_o_prefixo_herdado_edge_case() -> None:
    """Caso de borda: um fork feito de fora publica só os eventos próprios do ramo."""
    repositorios = montar_repositorios_em_memoria()
    kernel = _montar_kernel(repositorios)
    _montar_hierarquia(kernel)
    _criar_nota(kernel, "nota-base")

    controlador = SSEWebController()
    vigia = _montar_vigia(repositorios, controlador)
    vigia.adotar_posicao_atual()
    fila = controlador.registrar_assinante()

    evento_corte = repositorios.eventos.ler_eventos("main")[-1]
    ForkManager(repositorios.eventos, repositorios.ramos).criar_fork(
        PedidoFork(
            ramo_origem="main",
            id_evento_corte=evento_corte.id,
            novo_ramo_id="experimento",
            autor="agente-de-fora",
        )
    )
    vigia.varrer()

    publicados = _drenar(fila)
    assert [evento.tipo_evento for evento in publicados] == [TipoEvento.RAMO_CRIADO]
    assert publicados[0].ramo_id == "experimento"


def test_varredura_de_fundo_sobrevive_a_parada_e_reinicio_edge_case() -> None:
    """Caso de borda: parar o vigia encerra a thread; ele não fica varrendo o banco fechado."""
    repositorios = montar_repositorios_em_memoria()
    vigia = _montar_vigia(repositorios, SSEWebController())

    vigia.iniciar()
    assert vigia.esta_ativo is True

    vigia.parar()
    time.sleep(INTERVALO_CURTO * 2)
    assert vigia.esta_ativo is False
