"""Testes do índice de rollup: agregação por subárvore, ciclos e órfãos."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta
from graphow.projection.reducer import GrafoReducer
from graphow.projection.rollup import IndiceDeRollup


def _no(seq: int, id_no: str, tipo: str, rotulo: str, **propriedades: str) -> EventoLog:
    """Evento de criação de nó, com propriedades opcionais."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": rotulo, "propriedades": dict(propriedades)}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _aresta(seq: int, origem: str, destino: str, tipo: TipoAresta) -> EventoLog:
    """Evento de criação de aresta entre dois nós."""
    payload = {"id": f"{origem}->{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, payload))


def _montar_projeto_com_dois_setores() -> GrafoEstado:
    """Projeto com dois setores: um encerrado e outro com trabalho aberto."""
    eventos = [
        _no(1, "proj", "Projeto", "Projeto"),
        _no(2, "setor-a", "Setor", "Setor encerrado"),
        _no(3, "setor-b", "Setor", "Setor com pendencia"),
        _no(4, "t1", "Task", "Feita", status=StatusTask.CONCLUIDO.value),
        _no(5, "t2", "Task", "Feita tambem", status=StatusTask.CONCLUIDO.value),
        _no(6, "t3", "Task", "Aberta", status=StatusTask.PENDENTE.value),
        _aresta(7, "proj", "setor-a", TipoAresta.CONTEM),
        _aresta(8, "proj", "setor-b", TipoAresta.CONTEM),
        _aresta(9, "setor-a", "t1", TipoAresta.PRODUZ),
        _aresta(10, "setor-b", "t2", TipoAresta.PRODUZ),
        _aresta(11, "setor-b", "t3", TipoAresta.PRODUZ),
    ]
    return GrafoReducer.reconstruir(eventos)


def test_rollup_agrega_tarefas_da_subarvore_inteira() -> None:
    """O resumo do projeto soma as tarefas de todos os setores abaixo dele."""
    indice = IndiceDeRollup.calcular(_montar_projeto_com_dois_setores())

    resumo = indice.obter("proj")
    assert resumo is not None
    assert resumo.tarefas_totais == 3
    assert resumo.tarefas_concluidas == 2
    assert resumo.tarefas_abertas == 1
    assert resumo.total_nos == 6


def test_rollup_distingue_conteiner_encerrado_de_conteiner_com_pendencia() -> None:
    """A marca de trabalho aberto é o que orienta a descida do agente."""
    indice = IndiceDeRollup.calcular(_montar_projeto_com_dois_setores())

    encerrado = indice.obter("setor-a")
    pendente = indice.obter("setor-b")
    assert encerrado is not None and pendente is not None
    assert encerrado.tem_trabalho_aberto is False
    assert pendente.tem_trabalho_aberto is True


def test_rollup_nao_devolve_resumo_para_no_folha() -> None:
    """Uma Task sem filhos não é contêiner e não recebe resumo."""
    indice = IndiceDeRollup.calcular(_montar_projeto_com_dois_setores())

    assert indice.obter("t1") is None
    assert indice.eh_container("t1") is False
    assert indice.eh_container("setor-a") is True


def test_rollup_conta_questoes_abertas_e_ignora_respondidas() -> None:
    """Só a dúvida sem resposta conta: a respondida já não trava ninguém."""
    eventos = [
        _no(1, "sess", "Sessao", "Sessao"),
        _no(2, "q1", "Question", "Aberta", status=StatusQuestion.ABERTA.value),
        _no(3, "q2", "Question", "Respondida", status=StatusQuestion.RESPONDIDA.value),
        _aresta(4, "sess", "q1", TipoAresta.PRODUZ),
        _aresta(5, "sess", "q2", TipoAresta.PRODUZ),
    ]
    indice = IndiceDeRollup.calcular(GrafoReducer.reconstruir(eventos))

    resumo = indice.obter("sess")
    assert resumo is not None
    assert resumo.questoes_abertas == 1
    assert resumo.tem_trabalho_aberto is True


def test_rollup_nao_conta_duas_vezes_no_alcancado_por_dois_pais() -> None:
    """A contenção é um DAG: somar contagens contaria o mesmo nó duas vezes."""
    eventos = [
        _no(1, "proj", "Projeto", "Projeto"),
        _no(2, "sess-a", "Sessao", "Sessao A"),
        _no(3, "sess-b", "Sessao", "Sessao B"),
        _no(4, "t1", "Task", "Compartilhada", status=StatusTask.PENDENTE.value),
        _aresta(5, "proj", "sess-a", TipoAresta.CONTEM),
        _aresta(6, "proj", "sess-b", TipoAresta.CONTEM),
        _aresta(7, "sess-a", "t1", TipoAresta.PRODUZ),
        _aresta(8, "sess-b", "t1", TipoAresta.PRODUZ),
    ]
    indice = IndiceDeRollup.calcular(GrafoReducer.reconstruir(eventos))

    resumo = indice.obter("proj")
    assert resumo is not None
    assert resumo.tarefas_totais == 1
    assert resumo.total_nos == 4


def test_rollup_termina_mesmo_com_ciclo_de_contencao() -> None:
    """Um `decompoe` circular não pode travar nem estourar a pilha."""
    eventos = [
        _no(1, "t1", "Task", "Uma", status=StatusTask.PENDENTE.value),
        _no(2, "t2", "Task", "Outra", status=StatusTask.PENDENTE.value),
        _aresta(3, "t1", "t2", TipoAresta.DECOMPOE),
        _aresta(4, "t2", "t1", TipoAresta.DECOMPOE),
    ]
    indice = IndiceDeRollup.calcular(GrafoReducer.reconstruir(eventos))

    resumo = indice.obter("t1")
    assert resumo is not None
    assert resumo.total_nos >= 1
    assert resumo.tarefas_totais >= 1


def test_rollup_lista_nos_sem_pai_por_contencao() -> None:
    """Órfãos sumiriam calados numa tela colapsada: o índice os nomeia."""
    eventos = [
        _no(1, "proj", "Projeto", "Projeto"),
        _no(2, "sess", "Sessao", "Sessao"),
        _no(3, "evi-solta", "Evidence", "Evidencia sem pai"),
        _aresta(4, "proj", "sess", TipoAresta.CONTEM),
    ]
    indice = IndiceDeRollup.calcular(GrafoReducer.reconstruir(eventos))

    assert indice.nos_orfaos == ("evi-solta",)


def test_resumo_descreve_progresso_em_uma_linha_curta() -> None:
    """A linha de panorama precisa caber na casa de dez tokens."""
    indice = IndiceDeRollup.calcular(_montar_projeto_com_dois_setores())

    descricao = indice.obter("setor-b").descrever()  # type: ignore[union-attr]
    assert "1/2 tarefas concluidas" in descricao
    assert "1 abertas" in descricao
