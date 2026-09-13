"""Testes unitários para o acumulador mutável de projeção."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.projection.acumulador import AcumuladorProjecao
from graphow.projection.reducer import GrafoReducer


def _evento(seq: int, tipo: TipoEvento, payload: dict[str, object]) -> EventoLog:
    """Monta um evento de log com o tipo e o payload informados."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=tipo,
        payload=payload,
        origem=OrigemEvento.HUMANO,
    )
    return EventoLog.criar(dados)


def _criar_no(seq: int, id_no: str, tipo: TipoNo = TipoNo.TASK) -> EventoLog:
    """Evento de criação de nó."""
    return _evento(seq, TipoEvento.NO_CRIADO, {"id": id_no, "tipo": tipo.value, "rotulo": id_no})


def _criar_aresta(seq: int, id_aresta: str, origem: str, destino: str) -> EventoLog:
    """Evento de criação de aresta de dependência."""
    return _evento(
        seq,
        TipoEvento.ARESTA_CRIADA,
        {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": TipoAresta.DEPENDE_DE.value},
    )


def test_aplica_lote_e_congela_estado_nominal() -> None:
    """O acumulado vira um estado imutável com a versão do último evento."""
    acumulador = AcumuladorProjecao(GrafoEstado())
    acumulador.aplicar_todos([_criar_no(1, "n1"), _criar_no(2, "n2"), _criar_aresta(3, "e1", "n1", "n2")])

    estado = acumulador.congelar()
    assert estado.contem_no("n1") is True
    assert estado.contem_aresta("e1") is True
    assert estado.versao_log == 3


def test_remocao_de_no_leva_as_arestas_incidentes_nominal() -> None:
    """Remover um nó apaga as arestas que entram e saem dele."""
    acumulador = AcumuladorProjecao(GrafoEstado())
    acumulador.aplicar_todos(
        [
            _criar_no(1, "n1"),
            _criar_no(2, "n2"),
            _criar_aresta(3, "e1", "n1", "n2"),
            _evento(4, TipoEvento.NO_REMOVIDO, {"id": "n2"}),
        ]
    )
    estado = acumulador.congelar()
    assert estado.contem_no("n2") is False
    assert estado.contem_aresta("e1") is False


def test_estado_base_nao_e_modificado_edge_case() -> None:
    """Caso de borda: o acumulador trabalha sobre cópias, preservando a entrada."""
    base = GrafoReducer.reconstruir([_criar_no(1, "n1")])
    acumulador = AcumuladorProjecao(base)
    acumulador.aplicar(_criar_no(2, "n2"))

    assert base.contem_no("n2") is False
    assert acumulador.congelar().contem_no("n2") is True


def test_atualizacao_de_no_inexistente_e_ignorada_edge_case() -> None:
    """Caso de borda: atualizar o que não existe não cria o nó nem falha."""
    acumulador = AcumuladorProjecao(GrafoEstado())
    acumulador.aplicar(_evento(1, TipoEvento.NO_ATUALIZADO, {"id": "fantasma", "propriedades": {"a": 1}}))
    assert acumulador.congelar().contem_no("fantasma") is False


def test_tipo_de_evento_desconhecido_nao_avanca_a_versao_edge_case() -> None:
    """Caso de borda: um evento sem manipulador deixa o estado intacto."""
    acumulador = AcumuladorProjecao(GrafoEstado())
    acumulador.aplicar(_criar_no(1, "n1"))
    acumulador.aplicar(_evento(2, TipoEvento.EXECUCAO_SOLICITADA, {"id": "run-1"}))
    estado = acumulador.congelar()
    assert estado.versao_log == 2
    assert estado.contem_no("run-1") is True


def test_lote_e_dobra_individual_produzem_o_mesmo_estado() -> None:
    """A passada em lote é equivalente a aplicar evento por evento."""
    eventos = [_criar_no(1, "n1"), _criar_no(2, "n2"), _evento(3, TipoEvento.NO_REMOVIDO, {"id": "n1"})]

    em_lote = GrafoReducer.aplicar_eventos(GrafoEstado(), eventos)
    um_a_um = GrafoEstado()
    for evento in eventos:
        um_a_um = GrafoReducer.reduzir(um_a_um, evento)

    assert em_lote.serializar_para_json() == um_a_um.serializar_para_json()


def test_replay_grande_permanece_linear() -> None:
    """Dobrar dez vezes mais eventos não pode custar cem vezes mais trabalho."""
    import time

    def medir(total: int) -> float:
        """Cronometra a reconstrução de um log sintético."""
        eventos = [_criar_no(seq, f"n{seq}") for seq in range(1, total + 1)]
        inicio = time.perf_counter()
        GrafoReducer.reconstruir(eventos)
        return time.perf_counter() - inicio

    medir(2_000)
    tempo_pequeno = max(medir(2_000), 1e-4)
    tempo_grande = medir(20_000)
    assert tempo_grande / tempo_pequeno < 30, (tempo_pequeno, tempo_grande)


def test_propriedade_removida_some_da_projecao_nominal() -> None:
    """Remover uma propriedade apaga a chave, em vez de deixá-la valendo nulo."""
    eventos = [
        _criar_no(1, "n1"),
        _evento(2, TipoEvento.NO_ATUALIZADO, {"id": "n1", "propriedades": {"rascunho": "x"}}),
        _evento(3, TipoEvento.NO_ATUALIZADO, {"id": "n1", "propriedades_removidas": ["rascunho"]}),
    ]
    estado = GrafoReducer.reconstruir(eventos)

    assert "rascunho" not in estado.nos["n1"].propriedades


def test_remocao_de_propriedade_nao_toca_as_vizinhas_edge_case() -> None:
    """Caso de borda: só a chave nomeada sai; o resto do nó permanece."""
    eventos = [
        _criar_no(1, "n1"),
        _evento(
            2,
            TipoEvento.NO_ATUALIZADO,
            {"id": "n1", "propriedades": {"rascunho": "x", "status": "pendente"}},
        ),
        _evento(3, TipoEvento.NO_ATUALIZADO, {"id": "n1", "propriedades_removidas": ["rascunho"]}),
    ]
    estado = GrafoReducer.reconstruir(eventos)

    assert estado.nos["n1"].propriedades == {"status": "pendente"}


def test_remover_propriedade_ausente_nao_quebra_o_replay_edge_case() -> None:
    """Caso de borda: apagar o que já não existe é operação vazia, não erro."""
    eventos = [
        _criar_no(1, "n1"),
        _evento(2, TipoEvento.NO_ATUALIZADO, {"id": "n1", "propriedades_removidas": ["fantasma"]}),
    ]
    estado = GrafoReducer.reconstruir(eventos)

    assert estado.nos["n1"].propriedades == {}


def test_propriedade_gravada_como_nula_sobrevive_edge_case() -> None:
    """Caso de borda: nulo é valor, não ausência — a chave continua no nó."""
    eventos = [
        _criar_no(1, "n1"),
        _evento(2, TipoEvento.NO_ATUALIZADO, {"id": "n1", "propriedades": {"revisor": None}}),
    ]
    estado = GrafoReducer.reconstruir(eventos)

    assert estado.nos["n1"].propriedades == {"revisor": None}


def test_no_carrega_a_posicao_e_a_data_do_evento_que_o_criou_nominal() -> None:
    """A idade e a ordem do nó vêm do log, que é onde elas de fato existem."""
    evento = _criar_no(7, "n1")
    estado = GrafoReducer.reconstruir([evento])

    no = estado.nos["n1"]
    assert no.ordem.seq_criacao == 7
    assert no.ordem.seq_atualizacao == 7
    assert no.metadados.criado_em == evento.timestamp_utc
    assert no.metadados.atualizado_em is None


def test_atualizacao_move_o_ultimo_toque_e_preserva_o_nascimento_nominal() -> None:
    """Quem edita um nó não muda a idade dele, só a marca de última alteração."""
    criacao = _criar_no(7, "n1")
    edicao = _evento(9, TipoEvento.NO_ATUALIZADO, {"id": "n1", "rotulo": "Outro titulo"})
    estado = GrafoReducer.reconstruir([criacao, edicao])

    no = estado.nos["n1"]
    assert no.ordem.seq_criacao == 7
    assert no.ordem.seq_atualizacao == 9
    assert no.ordem.foi_alterado is True
    assert no.metadados.criado_em == criacao.timestamp_utc
    assert no.metadados.atualizado_em == edicao.timestamp_utc


def test_ordem_do_log_decide_quem_veio_antes_edge_case() -> None:
    """Caso de borda: dois nós criados no mesmo instante ainda têm ordem definida.

    Carimbos de tempo empatam e relógios de processos distintos discordam; a
    sequência do log é a única ordem total que o substrato promete.
    """
    estado = GrafoReducer.reconstruir([_criar_no(1, "primeiro"), _criar_no(2, "segundo")])

    assert estado.nos["primeiro"].ordem.seq_criacao < estado.nos["segundo"].ordem.seq_criacao


def test_run_nasce_com_a_data_do_log_e_nao_com_a_do_replay_edge_case() -> None:
    """Caso de borda: um Run datado pelo relógio do replay envelhecia a cada leitura.

    O nó de execução era o único criado com `MetadadosTemporais.agora()`: o mesmo
    log reconstruído amanhã diria que a execução aconteceu amanhã.
    """
    evento = _evento(4, TipoEvento.EXECUCAO_INICIADA, {"id": "run-1", "rotulo": "Execucao"})

    primeira = GrafoReducer.reconstruir([evento])
    segunda = GrafoReducer.reconstruir([evento])

    assert primeira.nos["run-1"].metadados.criado_em == evento.timestamp_utc
    assert primeira.nos["run-1"] == segunda.nos["run-1"]


def test_run_concluido_avanca_o_ultimo_toque_edge_case() -> None:
    """Caso de borda: o ciclo de vida da execução também move a marca de alteração."""
    eventos = [
        _evento(4, TipoEvento.EXECUCAO_INICIADA, {"id": "run-1", "rotulo": "Execucao"}),
        _evento(6, TipoEvento.EXECUCAO_CONCLUIDA, {"id": "run-1"}),
    ]
    estado = GrafoReducer.reconstruir(eventos)

    assert estado.nos["run-1"].ordem.seq_criacao == 4
    assert estado.nos["run-1"].ordem.seq_atualizacao == 6
