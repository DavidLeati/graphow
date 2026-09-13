"""Testes do caminho crítico: quem trava quem e quanto cada gargalo destrava."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta
from graphow.projection.caminho_critico import CalculadoraDeCaminhoCritico
from graphow.projection.reducer import GrafoReducer


def _no(seq: int, id_no: str, tipo: str, rotulo: str, **propriedades: str) -> EventoLog:
    """Evento de criação de nó, com propriedades opcionais."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": rotulo, "propriedades": dict(propriedades)}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _aresta(seq: int, origem: str, destino: str, tipo: TipoAresta) -> EventoLog:
    """Evento de criação de aresta entre dois nós."""
    payload = {"id": f"{origem}->{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, payload))


def _cadeia_de_tres() -> CalculadoraDeCaminhoCritico:
    """c depende de b, que depende de a: `a` é o gargalo da cadeia."""
    estado = GrafoReducer.reconstruir([
        _no(1, "a", "Task", "Primeira", status=StatusTask.PENDENTE.value),
        _no(2, "b", "Task", "Segunda", status=StatusTask.PENDENTE.value),
        _no(3, "c", "Task", "Terceira", status=StatusTask.PENDENTE.value),
        _aresta(4, "b", "a", TipoAresta.DEPENDE_DE),
        _aresta(5, "c", "b", TipoAresta.DEPENDE_DE),
    ])
    return CalculadoraDeCaminhoCritico(estado)


def test_gargalo_da_cadeia_destrava_todos_os_dependentes_transitivos() -> None:
    """`a` destrava `b` diretamente e `c` por consequência."""
    caminho = _cadeia_de_tres().calcular()

    principal = caminho.gargalos[0]
    assert principal.id == "a"
    assert principal.desbloqueia_diretamente == 1
    assert principal.desbloqueia_no_total == 2


def test_aresta_depende_de_e_lida_no_sentido_de_quem_destrava() -> None:
    """`b depende_de a` sai de b e chega em a, mas quem destrava é a."""
    caminho = _cadeia_de_tres().calcular()

    por_id = {gargalo.id: gargalo for gargalo in caminho.gargalos}
    assert "a" in por_id
    assert "c" not in por_id


def test_questao_aberta_conta_como_gargalo_da_tarefa_que_ela_bloqueia() -> None:
    """`bloqueia` já sai do bloqueador e é lida como está."""
    estado = GrafoReducer.reconstruir([
        _no(1, "q", "Question", "Duvida", status=StatusQuestion.ABERTA.value),
        _no(2, "t", "Task", "Travada", status=StatusTask.PENDENTE.value),
        _aresta(3, "q", "t", TipoAresta.BLOQUEIA),
    ])

    caminho = CalculadoraDeCaminhoCritico(estado).calcular()

    assert caminho.gargalos[0].id == "q"
    assert caminho.gargalos[0].desbloqueia_diretamente == 1


def test_grafo_sem_dependencia_declarada_devolve_caminho_vazio() -> None:
    """A tela precisa poder dizer 'nada declarado' em vez de mostrar vazio."""
    estado = GrafoReducer.reconstruir([
        _no(1, "t1", "Task", "Solta", status=StatusTask.PENDENTE.value),
        _no(2, "t2", "Task", "Tambem solta", status=StatusTask.PENDENTE.value),
    ])

    caminho = CalculadoraDeCaminhoCritico(estado).calcular()

    assert caminho.esta_vazio is True
    assert caminho.total_de_arestas_de_dependencia == 0
    assert set(caminho.tarefas_sem_dependencia_declarada) == {"t1", "t2"}


def test_tarefas_abertas_entram_no_caminho_mesmo_sem_dependencia() -> None:
    """Esconder a tarefa aberta faria a vista de fila omitir a própria fila."""
    estado = GrafoReducer.reconstruir([
        _no(1, "a", "Task", "Com dependente", status=StatusTask.PENDENTE.value),
        _no(2, "b", "Task", "Dependente", status=StatusTask.PENDENTE.value),
        _no(3, "solta", "Task", "Sem dependencia", status=StatusTask.PENDENTE.value),
        _aresta(4, "b", "a", TipoAresta.DEPENDE_DE),
    ])

    caminho = CalculadoraDeCaminhoCritico(estado).calcular()

    assert caminho.contem("solta") is True
    assert caminho.tarefas_sem_dependencia_declarada == ("solta",)


def test_ciclo_de_dependencia_nao_trava_o_calculo() -> None:
    """Duas tarefas que dependem uma da outra não podem gerar travessia sem fim."""
    estado = GrafoReducer.reconstruir([
        _no(1, "a", "Task", "Uma", status=StatusTask.PENDENTE.value),
        _no(2, "b", "Task", "Outra", status=StatusTask.PENDENTE.value),
        _aresta(3, "a", "b", TipoAresta.DEPENDE_DE),
        _aresta(4, "b", "a", TipoAresta.DEPENDE_DE),
    ])

    caminho = CalculadoraDeCaminhoCritico(estado).calcular()

    assert caminho.total_de_arestas_de_dependencia == 2
    assert len(caminho.gargalos) == 2
