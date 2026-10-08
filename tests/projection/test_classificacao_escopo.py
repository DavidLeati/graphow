"""Testes da classe de escopo de cada Task: uma por classe, e o alvo de tipo errado não conta."""

from typing import Any

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.classificacao_escopo import (
    ClasseDeEscopo,
    classificar_tarefa,
    classificar_tarefa_vigente,
    ligacao_valida,
    ligacoes_faltantes,
    raiz_da_cadeia,
)
from graphow.projection.graph_view import GrafoView

SEQ_DO_PLANO = 10
TARDE = 20


class _Grafo:
    """Montador de estado de teste: nós com `seq` de criação e arestas com id derivado."""

    def __init__(self) -> None:
        self.nos: dict[str, NoGrafo] = {}
        self.arestas: dict[str, ArestaGrafo] = {}

    def no(self, id_no: str, tipo_no: TipoNo, seq: int = TARDE, **propriedades: Any) -> "_Grafo":
        """Acrescenta um nó."""
        self.nos[id_no] = NoGrafo(
            id=id_no, tipo=tipo_no, rotulo=id_no, propriedades=propriedades, ordem=OrdemNoLog(seq_criacao=seq)
        )
        return self

    def liga(self, origem: str, tipo_aresta: TipoAresta, destino: str) -> "_Grafo":
        """Acrescenta uma aresta."""
        id_aresta = f"{origem}-{tipo_aresta.value}-{destino}"
        self.arestas[id_aresta] = ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo_aresta)
        return self

    def task_sob_o_goal(self, id_task: str, seq: int = TARDE, **propriedades: Any) -> "_Grafo":
        """Task pendurada no Goal por `decompoe`."""
        return self.no(id_task, TipoNo.TASK, seq, **propriedades).liga("g", TipoAresta.DECOMPOE, id_task)

    def view(self) -> GrafoView:
        """A vista sobre o que foi montado."""
        return GrafoView(GrafoEstado(nos=self.nos, arestas=self.arestas))


def _cenario(planos: list[dict[str, Any]] | None = None) -> _Grafo:
    """Goal com plano humano em SEQ_DO_PLANO, um critério de aceite e uma Task do plano."""
    planos = planos if planos is not None else [{"versao": 1, "seq": SEQ_DO_PLANO, "aprovado_por": "david", "papel": "humano"}]
    grafo = _Grafo().no("g", TipoNo.GOAL, 1, planos=planos)
    grafo.no("g-outro", TipoNo.GOAL, 1)
    grafo.no("crit", TipoNo.CONSTRAINT, 1, tipo="criterio_aceite").liga("crit", TipoAresta.ESCOPA, "g")
    grafo.no("crit-fora", TipoNo.CONSTRAINT, 1, tipo="criterio_aceite").liga("crit-fora", TipoAresta.ESCOPA, "g-outro")
    grafo.no("front", TipoNo.CONSTRAINT, 1, tipo="fronteira").liga("front", TipoAresta.ESCOPA, "g")
    grafo.no("ev-rej", TipoNo.EVIDENCE, 3, veredito="rejeitado")
    grafo.no("ev-ok", TipoNo.EVIDENCE, 3, veredito="aprovado")
    grafo.task_sob_o_goal("t-plano", seq=5)
    return grafo


def _classe(grafo: _Grafo, id_task: str) -> ClasseDeEscopo:
    """A classe da Task relativa à referência."""
    return classificar_tarefa(grafo.view(), id_task)


def test_task_do_plano_e_a_subdivisao_dela_nominal() -> None:
    """A Task nascida até o seq do plano é `plano`; a filha por `decompoe`, nascida depois, é `b1`."""
    grafo = _cenario().no("t-sub", TipoNo.TASK).liga("t-plano", TipoAresta.DECOMPOE, "t-sub")
    grafo.no("t-neta", TipoNo.TASK).liga("t-sub", TipoAresta.DECOMPOE, "t-neta")

    assert _classe(grafo, "t-plano") == ClasseDeEscopo.PLANO
    assert _classe(grafo, "t-sub") == ClasseDeEscopo.B1
    assert _classe(grafo, "t-neta") == ClasseDeEscopo.B1


def test_correcao_exige_evidence_rejeitada_nominal() -> None:
    """`corrige` para Evidence rejeitada é correção; para uma aprovada, ou sem `corrige`, não."""
    grafo = _cenario().task_sob_o_goal("t-corr", corrige="ev-rej")
    grafo.task_sob_o_goal("t-corr-aprovada", corrige="ev-ok")
    grafo.task_sob_o_goal("t-corr-fantasma", corrige="nao-existe")
    grafo.task_sob_o_goal("t-corr-em-task", corrige="t-plano")

    assert _classe(grafo, "t-corr") == ClasseDeEscopo.CORRECAO
    assert _classe(grafo, "t-corr-aprovada") == ClasseDeEscopo.SEM_LIGACAO
    assert _classe(grafo, "t-corr-fantasma") == ClasseDeEscopo.SEM_LIGACAO
    assert _classe(grafo, "t-corr-em-task") == ClasseDeEscopo.SEM_LIGACAO


def test_task_chamada_correcao_sem_corrige_e_sem_ligacao_edge_case() -> None:
    """Caso de borda: o rótulo não faz a classe, só a ligação."""
    grafo = _cenario()
    grafo.nos["t-nome"] = NoGrafo(id="t-nome", tipo=TipoNo.TASK, rotulo="Correção do relatório", ordem=OrdemNoLog(seq_criacao=TARDE))
    grafo.liga("g", TipoAresta.DECOMPOE, "t-nome")

    assert _classe(grafo, "t-nome") == ClasseDeEscopo.SEM_LIGACAO


def test_acompanhamento_exige_decisao_de_aceite_justificada_pela_evidence_nominal() -> None:
    """`acompanha` só conta com a Decision aceite_apos_reprovacao que a Evidence rejeitada justifica."""
    grafo = _cenario().no("dec-aceite", TipoNo.DECISION, acao="aceite_apos_reprovacao")
    grafo.liga("ev-rej", TipoAresta.JUSTIFICA, "dec-aceite")
    grafo.task_sob_o_goal("t-acomp").liga("t-acomp", TipoAresta.ACOMPANHA, "ev-rej")
    grafo.no("ev-rej2", TipoNo.EVIDENCE, veredito="rejeitado")
    grafo.task_sob_o_goal("t-sem-decisao").liga("t-sem-decisao", TipoAresta.ACOMPANHA, "ev-rej2")
    grafo.no("dec-outra", TipoNo.DECISION, acao="outra").liga("ev-ok", TipoAresta.JUSTIFICA, "dec-outra")
    grafo.task_sob_o_goal("t-acomp-ok").liga("t-acomp-ok", TipoAresta.ACOMPANHA, "ev-ok")

    assert _classe(grafo, "t-acomp") == ClasseDeEscopo.ACOMPANHAMENTO
    assert _classe(grafo, "t-sem-decisao") == ClasseDeEscopo.SEM_LIGACAO
    assert _classe(grafo, "t-acomp-ok") == ClasseDeEscopo.SEM_LIGACAO


def test_integracao_exige_task_do_mesmo_goal_com_artifact_nominal() -> None:
    """`integra` conta para Task do mesmo Goal com Artifact; sem Artifact ou de outro Goal, não."""
    grafo = _cenario().no("art", TipoNo.ARTIFACT, 6).liga("art", TipoAresta.DERIVA_DE, "t-plano")
    grafo.task_sob_o_goal("t-int").liga("t-int", TipoAresta.INTEGRA, "t-plano")
    grafo.task_sob_o_goal("t-sem-art", seq=6)
    grafo.task_sob_o_goal("t-int-sem-art").liga("t-int-sem-art", TipoAresta.INTEGRA, "t-sem-art")
    grafo.no("t-alheia", TipoNo.TASK).liga("g-outro", TipoAresta.DECOMPOE, "t-alheia")
    grafo.no("art2", TipoNo.ARTIFACT).liga("art2", TipoAresta.DERIVA_DE, "t-alheia")
    grafo.task_sob_o_goal("t-int-alheia").liga("t-int-alheia", TipoAresta.INTEGRA, "t-alheia")

    assert _classe(grafo, "t-int") == ClasseDeEscopo.INTEGRACAO
    assert _classe(grafo, "t-int-sem-art") == ClasseDeEscopo.SEM_LIGACAO
    assert _classe(grafo, "t-int-alheia") == ClasseDeEscopo.SEM_LIGACAO


def test_reversao_exige_decisao_substituida_ou_revogada_nominal() -> None:
    """`desfaz` conta para Decision substituída ou revogada; para uma viva, ou para Task, não."""
    grafo = _cenario().no("d-velha", TipoNo.DECISION).no("d-nova", TipoNo.DECISION)
    grafo.liga("d-nova", TipoAresta.SUBSTITUI, "d-velha")
    grafo.no("d-revogada", TipoNo.DECISION, status="revogada").no("d-viva", TipoNo.DECISION, status="ativa")
    for id_task, alvo in (("t-r1", "d-velha"), ("t-r2", "d-revogada"), ("t-r3", "d-viva"), ("t-r4", "t-plano")):
        grafo.task_sob_o_goal(id_task).liga(id_task, TipoAresta.DESFAZ, alvo)

    classes = [_classe(grafo, f"t-r{n}") for n in (1, 2, 3, 4)]

    assert classes == [ClasseDeEscopo.REVERSAO, ClasseDeEscopo.REVERSAO, ClasseDeEscopo.SEM_LIGACAO, ClasseDeEscopo.SEM_LIGACAO]


def test_emergente_b3_exige_motivo_e_criterio_do_goal_nominal() -> None:
    """B3 pede `motivada_por` e `atende_criterio` apontando critério de aceite que escopa o Goal."""
    grafo = _cenario().no("dec", TipoNo.DECISION)
    grafo.task_sob_o_goal("t-b3", atende_criterio="crit").liga("t-b3", TipoAresta.MOTIVADA_POR, "dec")
    grafo.task_sob_o_goal("t-sem-criterio").liga("t-sem-criterio", TipoAresta.MOTIVADA_POR, "dec")
    grafo.task_sob_o_goal("t-sem-motivo", atende_criterio="crit")

    assert _classe(grafo, "t-b3") == ClasseDeEscopo.B3
    assert _classe(grafo, "t-sem-criterio") == ClasseDeEscopo.SEM_LIGACAO
    assert _classe(grafo, "t-sem-motivo") == ClasseDeEscopo.SEM_LIGACAO


def test_b3_com_alvo_de_tipo_errado_nao_conta_edge_case() -> None:
    """Caso de borda: fronteira, critério de outro Goal, motivo em Artifact ou critério inexistente não abrem a porta."""
    grafo = _cenario().no("art", TipoNo.ARTIFACT).no("dec", TipoNo.DECISION)
    casos = {"t-front": ("front", "dec"), "t-fora": ("crit-fora", "dec"), "t-art": ("crit", "art"), "t-nada": ("sumiu", "dec")}
    for id_task, (criterio, motivo) in casos.items():
        grafo.task_sob_o_goal(id_task, atende_criterio=criterio).liga(id_task, TipoAresta.MOTIVADA_POR, motivo)

    assert {_classe(grafo, id_task) for id_task in casos} == {ClasseDeEscopo.SEM_LIGACAO}


def test_task_fora_de_goal_edge_case() -> None:
    """Caso de borda: sem Goal acima não há plano a medir; nó que não é Task também é `fora_de_goal`."""
    grafo = _cenario().no("t-solta", TipoNo.TASK)

    assert _classe(grafo, "t-solta") == ClasseDeEscopo.FORA_DE_GOAL
    assert _classe(grafo, "ev-rej") == ClasseDeEscopo.FORA_DE_GOAL
    assert _classe(grafo, "inexistente") == ClasseDeEscopo.FORA_DE_GOAL


def test_referencia_e_vigente_divergem_quando_o_arbitro_replaneja_nominal() -> None:
    """A Task da versão do árbitro é `plano` na vigente e continua emergente na referência humana."""
    planos = [
        {"versao": 1, "seq": SEQ_DO_PLANO, "aprovado_por": "david", "papel": "humano"},
        {"versao": 2, "seq": 30, "aprovado_por": "arbitro", "papel": "arbitro"},
    ]
    grafo = _cenario(planos).task_sob_o_goal("t-onda", seq=25)

    assert classificar_tarefa(grafo.view(), "t-onda") == ClasseDeEscopo.SEM_LIGACAO
    assert classificar_tarefa_vigente(grafo.view(), "t-onda") == ClasseDeEscopo.PLANO


def test_sem_plano_humano_toda_task_e_emergente_edge_case() -> None:
    """Caso de borda: sem aprovação humana nem a Task mais antiga é `plano` na referência."""
    grafo = _cenario(planos=[])

    assert _classe(grafo, "t-plano") == ClasseDeEscopo.SEM_LIGACAO
    assert ligacao_valida(grafo.view(), "t-plano")


def test_ligacao_valida_e_ligacoes_faltantes_nominal() -> None:
    """O kernel recusa a Task solta depois do plano e lista as ligações aceitas."""
    grafo = _cenario().task_sob_o_goal("t-solta").task_sob_o_goal("t-corr", corrige="ev-rej")
    view = grafo.view()

    assert not ligacao_valida(view, "t-solta")
    assert len(ligacoes_faltantes(view, "t-solta")) == 6
    assert any("atende_criterio" in texto for texto in ligacoes_faltantes(view, "t-solta"))
    assert ligacao_valida(view, "t-corr") and ligacoes_faltantes(view, "t-corr") == ()
    assert ligacao_valida(view, "t-plano")


def test_raiz_da_cadeia_sobe_motivada_por_nominal() -> None:
    """A raiz é o nó sem `motivada_por` saindo; no próprio nó raiz, ele mesmo."""
    grafo = _cenario().no("dec-a", TipoNo.DECISION).no("dec-b", TipoNo.DECISION)
    grafo.task_sob_o_goal("t1").liga("t1", TipoAresta.MOTIVADA_POR, "dec-a")
    grafo.liga("dec-b", TipoAresta.MOTIVADA_POR, "t1")
    grafo.task_sob_o_goal("t2").liga("t2", TipoAresta.MOTIVADA_POR, "dec-b")

    assert raiz_da_cadeia(grafo.view(), "t2") == "dec-a"
    assert raiz_da_cadeia(grafo.view(), "dec-a") == "dec-a"


def test_raiz_da_cadeia_em_ciclo_e_com_dois_motivos_edge_case() -> None:
    """Caso de borda: o ciclo devolve o menor identificador dele, de qualquer entrada; dois motivos seguem o menor."""
    grafo = _cenario().no("a", TipoNo.DECISION).no("b", TipoNo.DECISION).no("c", TipoNo.DECISION)
    grafo.liga("b", TipoAresta.MOTIVADA_POR, "c").liga("c", TipoAresta.MOTIVADA_POR, "b")
    grafo.task_sob_o_goal("t").liga("t", TipoAresta.MOTIVADA_POR, "c")
    grafo.task_sob_o_goal("t2").liga("t2", TipoAresta.MOTIVADA_POR, "c").liga("t2", TipoAresta.MOTIVADA_POR, "a")

    assert raiz_da_cadeia(grafo.view(), "t") == "b"
    assert raiz_da_cadeia(grafo.view(), "b") == "b"
    assert raiz_da_cadeia(grafo.view(), "c") == "b"
    assert raiz_da_cadeia(grafo.view(), "t2") == "a"
