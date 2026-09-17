"""Testes do fechamento determinístico: o que vigora, o que segue aberto, o último artefato."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusQuestion, StatusSessao, TipoAresta
from graphow.projection.fechamento import FechamentoDeSubarvore, calcular_fechamento
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


def _montar_sessao_encerrada() -> GrafoEstado:
    """Sessão com decisões (uma substituída), duas dúvidas, uma restrição e dois artefatos."""
    eventos = [
        _no(1, "sess", "Sessao", "Fatia 2", status=StatusSessao.CONCLUIDA.value),
        _no(2, "dec-a", "Decision", "Transacao unica"),
        _no(3, "dec-velha", "Decision", "Rollup incremental"),
        _no(4, "dec-b", "Decision", "Lock por tarefa"),
        _no(5, "q-aberta", "Question", "TTL estrito?", status=StatusQuestion.ABERTA.value),
        _no(6, "q-resp", "Question", "LRU?", status=StatusQuestion.RESPONDIDA.value),
        _no(7, "const", "Constraint", "Zero dependencias"),
        _no(8, "art-1", "Artifact", "kernel v1"),
        _no(9, "art-2", "Artifact", "kernel v2"),
    ]
    filhos = ("dec-a", "dec-velha", "dec-b", "q-aberta", "q-resp", "const", "art-1", "art-2")
    eventos.extend(_aresta(10 + indice, "sess", filho, TipoAresta.PRODUZ) for indice, filho in enumerate(filhos))
    eventos.append(_aresta(30, "dec-b", "dec-velha", TipoAresta.SUBSTITUI))
    return GrafoReducer.reconstruir(eventos)


def _fechamento_da_sessao() -> FechamentoDeSubarvore:
    """O fechamento que o rollup calcula para a sessão do cenário."""
    resumo = IndiceDeRollup.calcular(_montar_sessao_encerrada()).obter("sess")
    assert resumo is not None
    return resumo.fechamento


def test_decisao_substituida_nao_vigora_nominal() -> None:
    """A aresta `substitui` governa o que o fechamento chama de vigente."""
    fechamento = _fechamento_da_sessao()

    assert fechamento.decisoes_vigentes == ("dec-a", "dec-b")
    assert fechamento.decisoes_substituidas == 1


def test_ultimo_artefato_e_o_mais_recente_no_log_nominal() -> None:
    """Onde o trabalho parou é o artefato que nasceu por último na ordem total."""
    fechamento = _fechamento_da_sessao()

    assert fechamento.ultimo_artefato == "art-2"
    assert fechamento.seq_ultimo_artefato == 9


def test_so_a_duvida_sem_resposta_segue_aberta_nominal() -> None:
    """A dúvida respondida já não é pendência de quem retoma."""
    assert _fechamento_da_sessao().questoes_abertas == ("q-aberta",)


def test_restricoes_entram_no_fechamento_nominal() -> None:
    """A restrição sobrevive à sessão: quem retoma precisa vê-la antes de agir."""
    assert _fechamento_da_sessao().restricoes == ("const",)


def test_fechamento_descreve_em_duas_linhas_curtas_nominal() -> None:
    """É o que a linha de sessão do panorama passa a carregar."""
    linhas = _fechamento_da_sessao().descrever()

    assert len(linhas) == 2
    assert "vigora: dec-a, dec-b" in linhas[0]
    assert "aberto: 1 duvidas" in linhas[0]
    assert "restricoes: const" in linhas[0]
    assert linhas[1] == "ultimo artefato: art-2 (log #9)"


def test_fechamento_vazio_nao_descreve_nada_edge_case() -> None:
    """Caso de borda: uma sessão sem decisão nem artefato não ganha linha em branco."""
    assert FechamentoDeSubarvore().descrever() == ()
    assert FechamentoDeSubarvore().esta_vazio is True


def test_excedente_de_decisoes_e_contado_e_nao_listado_edge_case() -> None:
    """Caso de borda: sete decisões viram cinco nomes e um contador."""
    fechamento = FechamentoDeSubarvore(decisoes_vigentes=tuple(f"dec-{indice}" for indice in range(7)))

    linha = fechamento.descrever()[0]

    assert "dec-4" in linha
    assert "dec-5" not in linha
    assert "(+2)" in linha


def test_fechamento_sem_decisao_diz_nenhuma_edge_case() -> None:
    """Caso de borda: artefato sem decisão alguma ainda descreve, sem inventar decisão."""
    fechamento = FechamentoDeSubarvore(ultimo_artefato="art-9", seq_ultimo_artefato=4)

    assert "vigora: nenhuma" in fechamento.descrever()[0]


def test_calculo_direto_ignora_nos_de_outros_tipos_nominal() -> None:
    """Tasks e Notes não entram no esqueleto: ele é sobre decisão, dúvida, restrição e entrega."""
    estado = _montar_sessao_encerrada()

    fechamento = calcular_fechamento(tuple(estado.nos.values()), frozenset({"dec-velha"}))

    assert fechamento.decisoes_vigentes == ("dec-a", "dec-b")
    assert fechamento.ultimo_artefato == "art-2"


def test_resumo_do_rollup_serializa_o_fechamento_nominal() -> None:
    """O canvas e a REST recebem o fechamento junto do agregado da subárvore."""
    resumo = IndiceDeRollup.calcular(_montar_sessao_encerrada()).obter("sess")
    assert resumo is not None

    serializado = resumo.em_dicionario()["fechamento"]

    assert serializado["ultimo_artefato"] == "art-2"
    assert serializado["decisoes_vigentes"] == ["dec-a", "dec-b"]
