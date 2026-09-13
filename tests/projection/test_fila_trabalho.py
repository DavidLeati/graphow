"""Testes da fila de trabalho: o que está de fato executável em uma sessão."""

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.projection.fila_trabalho import FilaDeTrabalho, MotivoDeImpedimento
from graphow.projection.graph_view import GrafoView


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, str] | None = None) -> NoGrafo:
    """Cria um nó de teste com as propriedades informadas."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades or {})


def _aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Cria uma aresta tipada de teste."""
    return ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo)


def _estado_com_tres_tarefas(status_da_livre: str = StatusTask.PENDENTE.value) -> GrafoEstado:
    """Sessao com uma tarefa livre, uma dependente e uma bloqueada por dúvida."""
    nos = {
        "sess-1": _no("sess-1", TipoNo.SESSAO),
        "t-livre": _no("t-livre", TipoNo.TASK, {"status": status_da_livre, "criterio_pronto": "testes verdes"}),
        "t-dependente": _no("t-dependente", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        "t-bloqueada": _no("t-bloqueada", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        "q1": _no("q1", TipoNo.QUESTION, {"status": StatusQuestion.ABERTA.value}),
    }
    arestas = {
        "p1": _aresta("p1", "sess-1", "t-livre", TipoAresta.PRODUZ),
        "p2": _aresta("p2", "sess-1", "t-dependente", TipoAresta.PRODUZ),
        "p3": _aresta("p3", "sess-1", "t-bloqueada", TipoAresta.PRODUZ),
        "d1": _aresta("d1", "t-dependente", "t-livre", TipoAresta.DEPENDE_DE),
        "b1": _aresta("b1", "q1", "t-bloqueada", TipoAresta.BLOQUEIA),
    }
    return GrafoEstado(nos=nos, arestas=arestas)


def _sessao_com_tres_tarefas() -> GrafoView:
    """Vista somente-leitura sobre o cenário padrão de três tarefas."""
    return GrafoView(_estado_com_tres_tarefas())


def test_fila_devolve_apenas_a_tarefa_executavel_nominal() -> None:
    """Dependência pendente e dúvida aberta tiram a tarefa da fila."""
    fila = FilaDeTrabalho(_sessao_com_tres_tarefas())

    tarefas = fila.proximas_tarefas("sess-1")

    assert [tarefa.id for tarefa in tarefas] == ["t-livre"]
    assert tarefas[0].criterio_pronto == "testes verdes"


def test_fila_libera_dependente_quando_prerequisito_conclui_nominal() -> None:
    """Concluída a dependência, a tarefa seguinte entra na fila."""
    view = GrafoView(_estado_com_tres_tarefas(StatusTask.CONCLUIDO.value))

    tarefas = FilaDeTrabalho(view).proximas_tarefas("sess-1")

    assert [tarefa.id for tarefa in tarefas] == ["t-dependente"]
    assert tarefas[0].depende_de == ("t-livre",)


def test_fila_exclui_tarefa_ja_assumida_edge_case() -> None:
    """Caso de borda: tarefa sob posse de alguém não é oferecida de novo."""
    fila = FilaDeTrabalho(_sessao_com_tres_tarefas(), {"t-livre": "agente-a"})

    assert fila.proximas_tarefas("sess-1") == ()


def test_fila_alcanca_subtarefas_por_decompoe_edge_case() -> None:
    """Caso de borda: a fila enxerga a decomposição, não só o primeiro nível."""
    nos = {
        "sess-1": _no("sess-1", TipoNo.SESSAO),
        "goal-1": _no("goal-1", TipoNo.GOAL),
        "t-filha": _no("t-filha", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
    }
    arestas = {
        "p1": _aresta("p1", "sess-1", "goal-1", TipoAresta.PRODUZ),
        "dec": _aresta("dec", "goal-1", "t-filha", TipoAresta.DECOMPOE),
    }

    tarefas = FilaDeTrabalho(GrafoView(GrafoEstado(nos=nos, arestas=arestas))).proximas_tarefas("sess-1")

    assert [tarefa.id for tarefa in tarefas] == ["t-filha"]


def test_fila_ordena_revisao_antes_de_pendente_edge_case() -> None:
    """Caso de borda: a ordem é de atendimento, não alfabética como antes."""
    nos = {
        "sess-1": _no("sess-1", TipoNo.SESSAO),
        "a-pendente": _no("a-pendente", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        "z-revisao": _no("z-revisao", TipoNo.TASK, {"status": StatusTask.PRONTO_PARA_REVISAO.value}),
    }
    arestas = {
        "p1": _aresta("p1", "sess-1", "a-pendente", TipoAresta.PRODUZ),
        "p2": _aresta("p2", "sess-1", "z-revisao", TipoAresta.PRODUZ),
    }

    tarefas = FilaDeTrabalho(GrafoView(GrafoEstado(nos=nos, arestas=arestas))).proximas_tarefas("sess-1")

    assert [tarefa.id for tarefa in tarefas] == ["z-revisao", "a-pendente"]


def test_fila_de_sessao_inexistente_e_vazia_edge_case() -> None:
    """Caso de borda: sessão desconhecida devolve fila vazia, não erro."""
    assert FilaDeTrabalho(_sessao_com_tres_tarefas()).proximas_tarefas("fantasma") == ()


def test_fila_explica_cada_tarefa_que_ficou_de_fora_nominal() -> None:
    """Fila vazia sem motivo deixa o agente tão parado quanto a ausência de fila."""
    fila = FilaDeTrabalho(_sessao_com_tres_tarefas(), {"t-livre": "agente-a"})

    motivos = {impedida.id: impedida.motivo for impedida in fila.tarefas_impedidas("sess-1")}

    assert motivos == {
        "t-livre": MotivoDeImpedimento.POSSE_DE_OUTRO,
        "t-dependente": MotivoDeImpedimento.DEPENDENCIA_PENDENTE,
        "t-bloqueada": MotivoDeImpedimento.DUVIDA_ABERTA,
    }


def test_tarefa_concluida_e_reportada_como_tal_edge_case() -> None:
    """Caso de borda: o que já acabou não é impedimento, e o motivo diz isso."""
    view = GrafoView(_estado_com_tres_tarefas(StatusTask.CONCLUIDO.value))

    impedidas = {i.id: i.motivo for i in FilaDeTrabalho(view).tarefas_impedidas("sess-1")}

    assert impedidas["t-livre"] == MotivoDeImpedimento.CONCLUIDA


def test_toda_tarefa_da_sessao_aparece_em_um_dos_dois_lados_edge_case() -> None:
    """Caso de borda: nenhuma tarefa some entre a fila e a lista de impedidas."""
    fila = FilaDeTrabalho(_sessao_com_tres_tarefas())

    executaveis = {tarefa.id for tarefa in fila.proximas_tarefas("sess-1")}
    impedidas = {impedida.id for impedida in fila.tarefas_impedidas("sess-1")}

    assert executaveis | impedidas == {"t-livre", "t-dependente", "t-bloqueada"}
    assert executaveis & impedidas == set()
