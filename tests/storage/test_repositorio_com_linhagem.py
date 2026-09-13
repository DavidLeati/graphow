"""Testes unitários para a composição de leitura entre um ramo e sua herança."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.storage.composicao import ConjuntoRepositorios, montar_repositorios_em_memoria
from graphow.storage.linhagem_ramo import DefinicaoRamo


def _evento(seq: int, id_no: str, ramo_id: str = "main") -> EventoLog:
    """Monta um evento de criação de nó com a sequência e o ramo informados."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": id_no, "tipo": "Task", "rotulo": id_no},
        origem=OrigemEvento.HUMANO,
        ramo_id=ramo_id,
    )
    return EventoLog.criar(dados)


def _montar_com_fork(seq_corte: int) -> ConjuntoRepositorios:
    """Cria main com três eventos e um ramo derivado cortado na posição indicada."""
    repositorios = montar_repositorios_em_memoria()
    repositorios.eventos.append_eventos([_evento(1, "n1"), _evento(2, "n2"), _evento(3, "n3")])
    repositorios.ramos.registrar(DefinicaoRamo("filho", "main", seq_corte))
    return repositorios


def test_leitura_do_ramo_derivado_inclui_o_prefixo_herdado_nominal() -> None:
    """O ramo enxerga os eventos do pai até o corte, sem tê-los copiado."""
    repositorios = _montar_com_fork(seq_corte=2)
    ids = [evento.payload["id"] for evento in repositorios.eventos.ler_eventos("filho")]
    assert ids == ["n1", "n2"]


def test_ramo_derivado_soma_eventos_proprios_nominal() -> None:
    """Eventos próprios aparecem depois do prefixo, na ordem de sequência."""
    repositorios = _montar_com_fork(seq_corte=2)
    repositorios.eventos.append_evento(_evento(3, "proprio", ramo_id="filho"))

    ids = [evento.payload["id"] for evento in repositorios.eventos.ler_eventos("filho")]
    assert ids == ["n1", "n2", "proprio"]
    assert [evento.payload["id"] for evento in repositorios.eventos.ler_eventos("main")] == ["n1", "n2", "n3"]


def test_ultimo_seq_considera_o_corte_mesmo_sem_eventos_proprios_edge_case() -> None:
    """Caso de borda: um fork recém-criado já continua a numeração do pai."""
    repositorios = _montar_com_fork(seq_corte=2)
    assert repositorios.eventos.obter_ultimo_seq("filho") == 2


def test_leitura_ate_seq_respeita_o_recorte_edge_case() -> None:
    """Caso de borda: a janela até uma sequência corta também o prefixo herdado."""
    repositorios = _montar_com_fork(seq_corte=3)
    ids = [evento.payload["id"] for evento in repositorios.eventos.ler_eventos_ate_seq("filho", 1)]
    assert ids == ["n1"]


def test_leitura_desde_seq_ignora_o_que_ja_foi_projetado_edge_case() -> None:
    """Caso de borda: a leitura incremental devolve apenas o delta pendente."""
    repositorios = _montar_com_fork(seq_corte=3)
    repositorios.eventos.append_evento(_evento(4, "proprio", ramo_id="filho"))

    ids = [evento.payload["id"] for evento in repositorios.eventos.ler_eventos_desde_seq("filho", 2)]
    assert ids == ["n3", "proprio"]


def test_listagem_inclui_ramo_declarado_sem_eventos_proprios_edge_case() -> None:
    """Caso de borda: um fork sem escrita própria já aparece na lista de ramos."""
    repositorios = _montar_com_fork(seq_corte=2)
    assert repositorios.eventos.listar_ramos() == ["filho", "main"]


def test_ramo_raiz_nao_herda_nada() -> None:
    """Sem definição de linhagem, o ramo devolve apenas os próprios eventos."""
    repositorios = _montar_com_fork(seq_corte=2)
    repositorios.eventos.append_evento(_evento(1, "isolado", ramo_id="outro"))
    ids = [evento.payload["id"] for evento in repositorios.eventos.ler_eventos("outro")]
    assert ids == ["isolado"]
