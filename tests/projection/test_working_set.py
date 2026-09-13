"""Testes do escopo ativo: sementes, raio e contêineres arrastados junto."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta
from graphow.projection.reducer import GrafoReducer
from graphow.projection.working_set import RAIO_MAXIMO, CalculadoraDeEscopoAtivo


def _no(seq: int, id_no: str, tipo: str, rotulo: str, **propriedades: str) -> EventoLog:
    """Evento de criação de nó, com propriedades opcionais."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": rotulo, "propriedades": dict(propriedades)}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _aresta(seq: int, origem: str, destino: str, tipo: TipoAresta) -> EventoLog:
    """Evento de criação de aresta entre dois nós."""
    payload = {"id": f"{origem}->{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, payload))


def _cenario() -> GrafoEstado:
    """Sessão com uma tarefa aberta, uma concluída e evidências a distâncias diferentes."""
    return GrafoReducer.reconstruir([
        _no(1, "proj", "Projeto", "Projeto"),
        _no(2, "sess", "Sessao", "Sessao"),
        _no(3, "aberta", "Task", "Aberta", status=StatusTask.PENDENTE.value),
        _no(4, "fechada", "Task", "Fechada", status=StatusTask.CONCLUIDO.value),
        _no(5, "art-perto", "Artifact", "Artefato da aberta"),
        _no(6, "evi-longe", "Evidence", "Evidencia do artefato"),
        _aresta(7, "proj", "sess", TipoAresta.CONTEM),
        _aresta(8, "sess", "aberta", TipoAresta.PRODUZ),
        _aresta(9, "sess", "fechada", TipoAresta.PRODUZ),
        _aresta(10, "aberta", "art-perto", TipoAresta.DERIVA_DE),
        _aresta(11, "art-perto", "evi-longe", TipoAresta.DERIVA_DE),
    ])


def test_sementes_sao_tarefas_abertas_e_duvidas_sem_resposta() -> None:
    """Uma tarefa concluída não é semente; ela só entra por proximidade."""
    escopo = CalculadoraDeEscopoAtivo(_cenario()).calcular(raio=0)

    assert escopo.sementes == frozenset({"aberta"})
    assert escopo.contem("fechada") is False


def test_raio_zero_ainda_traz_os_conteineres_da_semente() -> None:
    """Um nó solto na tela, sem a sessão dele, perde o contexto de navegação."""
    escopo = CalculadoraDeEscopoAtivo(_cenario()).calcular(raio=0)

    assert escopo.contem("aberta") is True
    assert escopo.contem("sess") is True
    assert escopo.contem("proj") is True


def test_raio_um_alcanca_o_vizinho_direto_e_para_ali() -> None:
    """O raio é o que separa um recorte útil de trazer o grafo de volta."""
    escopo = CalculadoraDeEscopoAtivo(_cenario()).calcular(raio=1)

    assert escopo.contem("art-perto") is True
    assert escopo.contem("evi-longe") is False


def test_raio_dois_alcanca_o_vizinho_do_vizinho() -> None:
    """Cada salto a mais amplia o recorte; é o custo que o padrão evita."""
    escopo = CalculadoraDeEscopoAtivo(_cenario()).calcular(raio=2)

    assert escopo.contem("evi-longe") is True


def test_questao_aberta_tambem_e_semente() -> None:
    """O que espera o humano é trabalho aberto tanto quanto uma tarefa."""
    estado = GrafoReducer.reconstruir([
        _no(1, "q", "Question", "Duvida", status=StatusQuestion.ABERTA.value),
        _no(2, "t", "Task", "Feita", status=StatusTask.CONCLUIDO.value),
    ])

    escopo = CalculadoraDeEscopoAtivo(estado).calcular()

    assert escopo.sementes == frozenset({"q"})


def test_grafo_sem_trabalho_aberto_produz_escopo_vazio() -> None:
    """Sem semente não há recorte: a tela precisa mostrar tudo, não nada."""
    estado = GrafoReducer.reconstruir([
        _no(1, "t", "Task", "Feita", status=StatusTask.CONCLUIDO.value),
    ])

    escopo = CalculadoraDeEscopoAtivo(estado).calcular()

    assert escopo.esta_vazio is True
    assert escopo.ids == frozenset()


def test_contencao_nao_e_percorrida_como_aresta_de_trabalho() -> None:
    """Percorrer `contem` traria o projeto inteiro em dois saltos."""
    estado = GrafoReducer.reconstruir([
        _no(1, "proj", "Projeto", "Projeto"),
        _no(2, "setor", "Setor", "Setor"),
        _no(3, "outro-setor", "Setor", "Outro setor"),
        _no(4, "t", "Task", "Aberta", status=StatusTask.PENDENTE.value),
        _no(5, "longe", "Artifact", "Artefato do outro setor"),
        _aresta(6, "proj", "setor", TipoAresta.CONTEM),
        _aresta(7, "proj", "outro-setor", TipoAresta.CONTEM),
        _aresta(8, "setor", "t", TipoAresta.PRODUZ),
        _aresta(9, "outro-setor", "longe", TipoAresta.PRODUZ),
    ])

    escopo = CalculadoraDeEscopoAtivo(estado).calcular(raio=2)

    assert escopo.contem("longe") is False


def test_raio_e_saneado_entre_zero_e_o_teto() -> None:
    """Raio negativo ou absurdo não pode virar travessia sem fim."""
    calculadora = CalculadoraDeEscopoAtivo(_cenario())

    assert calculadora.calcular(raio=-3).raio == 0
    assert calculadora.calcular(raio=999).raio == RAIO_MAXIMO
