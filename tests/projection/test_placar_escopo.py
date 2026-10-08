"""Testes do placar de escopo: gatilhos K e M, inanição, respostas de desvio, veredito pendente e o texto da 4.7."""

from typing import Any

import pytest

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog, ProvenienciaNo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.placar_escopo import (
    LimiaresDeDesvio,
    PlacarDeEscopo,
    gatilhos_disparados,
    montar_placar,
)

SEQ_DO_PLANO = 10
TARDE = 20
LIMIARES = LimiaresDeDesvio(por_raiz=3, por_goal=5)
PLANO_HUMANO = {"versao": 1, "seq": SEQ_DO_PLANO, "aprovado_por": "david", "papel": "humano"}


class _Grafo:
    """Montador de estado de teste: nós com `seq` de criação, proveniência e arestas com id derivado."""

    def __init__(self, planos: list[dict[str, Any]] | None = None, **goal: Any) -> None:
        self.nos: dict[str, NoGrafo] = {}
        self.arestas: dict[str, ArestaGrafo] = {}
        self.no("g", TipoNo.GOAL, 1, **({"planos": planos} if planos else {}), **goal)
        self.no("crit", TipoNo.CONSTRAINT, 1, tipo="criterio_aceite").liga("crit", TipoAresta.ESCOPA, "g")

    def no(self, id_no: str, tipo_no: TipoNo, seq: int = TARDE, papel: str = "", **propriedades: Any) -> "_Grafo":
        """Acrescenta um nó criado no `seq` dado, por um papel."""
        self.nos[id_no] = NoGrafo(
            id=id_no,
            tipo=tipo_no,
            rotulo=id_no,
            propriedades=propriedades,
            proveniencia=ProvenienciaNo(autor="x", papel=papel),
            ordem=OrdemNoLog(seq_criacao=seq),
        )
        return self

    def liga(self, origem: str, tipo_aresta: TipoAresta, destino: str) -> "_Grafo":
        """Acrescenta uma aresta."""
        id_aresta = f"{origem}-{tipo_aresta.value}-{destino}"
        self.arestas[id_aresta] = ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo_aresta)
        return self

    def b3(self, id_task: str, motivo: str, seq: int, **extra: Any) -> "_Grafo":
        """Task emergente de critério, motivada por um nó; `papel` e `status` vêm em `extra`."""
        papel = extra.pop("papel", "executor")
        self.no(id_task, TipoNo.TASK, seq, papel, atende_criterio="crit", **extra)
        return self.liga("g", TipoAresta.DECOMPOE, id_task).liga(id_task, TipoAresta.MOTIVADA_POR, motivo)

    def seq(self, id_raiz: str, primeiro: int, quantas: int, **extra: Any) -> "_Grafo":
        """Várias B3 da mesma raiz, em `seq` consecutivos."""
        for i in range(quantas):
            self.b3(f"{id_raiz}-t{i}", id_raiz, primeiro + i, **extra)
        return self

    def responde(self, **resposta: Any) -> "_Grafo":
        """Acrescenta uma resposta de desvio ao Goal."""
        antigas = list(self.nos["g"].propriedades.get("respostas_de_desvio", []))
        self.nos["g"] = self.nos["g"].com_propriedades({"respostas_de_desvio": [*antigas, resposta]})
        return self

    def placar(self, limiares: LimiaresDeDesvio = LIMIARES) -> PlacarDeEscopo:
        """O placar do Goal."""
        return montar_placar(GrafoView(GrafoEstado(nos=self.nos, arestas=self.arestas)), "g", limiares)


def _com_plano() -> _Grafo:
    """Goal com plano humano, duas Tasks do plano (uma concluída) e duas decisões de origem."""
    grafo = _Grafo([PLANO_HUMANO]).no("d1", TipoNo.DECISION, 1).no("d2", TipoNo.DECISION, 1)
    grafo.no("t-plano", TipoNo.TASK, 5, status="concluido", fase="F1").liga("g", TipoAresta.DECOMPOE, "t-plano")
    grafo.no("t-plano2", TipoNo.TASK, 6, status="pendente", fase="F3").liga("g", TipoAresta.DECOMPOE, "t-plano2")
    return grafo


def _tipos(placar: PlacarDeEscopo) -> set[tuple[str, str | None]]:
    """Os gatilhos disparados como (tipo, raiz)."""
    return {(gatilho.tipo, gatilho.raiz) for gatilho in gatilhos_disparados(placar)}


def test_goal_sem_plano_tem_tudo_como_emergente_edge_case() -> None:
    """Sem plano aprovado nenhuma Task é do plano: toda Task sem ligação conta como emergente."""
    grafo = _Grafo().no("t1", TipoNo.TASK, 1).no("t2", TipoNo.TASK, 2)
    grafo.liga("g", TipoAresta.DECOMPOE, "t1").liga("g", TipoAresta.DECOMPOE, "t2")

    placar = grafo.placar()

    assert placar.referencia is None
    assert placar.contagem_por_classe["sem_ligacao"] == 2
    assert placar.emergentes_para_m == 2
    assert placar.plano.total == 0
    assert placar.linhas()[0].startswith("Escopo: sem plano aprovado por humano")


def test_plano_humano_e_plano_do_arbitro_nominal() -> None:
    """A referência é a versão humana; a Task do plano do árbitro conta como emergente."""
    arbitro = {"versao": 2, "seq": 30, "aprovado_por": "arb", "papel": "arbitro"}
    grafo = _Grafo([PLANO_HUMANO, arbitro]).no("t-arb", TipoNo.TASK, 25).liga("g", TipoAresta.DECOMPOE, "t-arb")

    placar = grafo.placar()

    assert placar.referencia is not None and placar.referencia.versao == 1
    assert [versao.versao for versao in placar.versoes_do_arbitro] == [2]
    assert placar.emergentes_para_m == 1
    assert placar.linhas()[0] == "Escopo: plano_v1 (humano, seq 10) · v2 pelo árbitro"


@pytest.mark.parametrize(("quantas", "dispara"), [(3, False), (4, True)])
def test_k_dispara_na_primeira_alem_do_limiar_nominal(quantas: int, dispara: bool) -> None:
    """Com K = 3 a quarta B3 da mesma raiz dispara, a terceira não."""
    placar = _com_plano().seq("d1", 20, quantas).placar()

    assert (("raiz", "d1") in _tipos(placar)) is dispara
    assert placar.raizes[0].contador_k == quantas


def test_m_pega_a_expansao_fragmentada_nominal() -> None:
    """Seis raízes com uma B3 cada: nenhuma passa de K, o Goal passa de M = 5."""
    grafo = _com_plano()
    for i in range(6):
        grafo.no(f"dx{i}", TipoNo.DECISION, 1).b3(f"t{i}", f"dx{i}", 20 + i)

    placar = grafo.placar()

    assert _tipos(placar) == {("goal", None)}
    assert placar.emergentes_para_m == 6


def test_m_nao_dispara_no_limiar_exato_edge_case() -> None:
    """Cinco B3 de cinco raízes: no limiar, ainda sem alerta."""
    grafo = _com_plano()
    for i in range(5):
        grafo.no(f"dx{i}", TipoNo.DECISION, 1).b3(f"t{i}", f"dx{i}", 20 + i)

    assert _tipos(grafo.placar()) == set()


def test_task_humana_nao_conta_para_m_mas_conta_para_k_nominal() -> None:
    """Seis B3 criadas por humano: M fica zerado, mas a raiz passa de K."""
    placar = _com_plano().seq("d1", 20, 6, papel="humano").placar()

    assert placar.emergentes_para_m == 0
    assert _tipos(placar) == {("raiz", "d1")}


def test_resposta_humana_zera_m_e_a_raiz_respondida_nominal() -> None:
    """A resposta humana a uma raiz zera o contador do Goal e o K dela; a outra raiz segue contando."""
    grafo = _com_plano().no("d3", TipoNo.DECISION, 1)
    grafo.seq("d1", 20, 4).seq("d2", 30, 3).b3("t-d3", "d3", 40)
    assert ("goal", None) in _tipos(grafo.placar())

    placar = grafo.responde(seq=50, respondido_por="david", papel="humano", raiz="d1", resposta="segue").placar()

    por_raiz = {raiz.raiz: raiz.contador_k for raiz in placar.raizes}
    assert por_raiz == {"d1": 0, "d2": 3, "d3": 1}
    assert _tipos(placar) == set()
    assert placar.emergentes_para_m == 0


def test_resposta_humana_so_zera_a_raiz_que_respondeu_edge_case() -> None:
    """A B3 posterior à resposta soma de novo, e a raiz não respondida mantém a contagem."""
    grafo = _com_plano().seq("d1", 20, 4).seq("d2", 30, 4)
    grafo.responde(seq=50, respondido_por="david", papel="humano", raiz="d1", resposta="ok")
    grafo.b3("t-depois", "d1", 60)

    por_raiz = {raiz.raiz: raiz.contador_k for raiz in grafo.placar().raizes}

    assert por_raiz == {"d1": 1, "d2": 4}


def test_resposta_humana_sem_raiz_zera_todas_as_raizes_edge_case() -> None:
    """Quem responde ao placar sem nomear raiz viu todas: nenhuma segue disparando K."""
    grafo = _com_plano().seq("d1", 20, 4).seq("d2", 30, 4)
    grafo.responde(seq=50, respondido_por="david", papel="humano", raiz=None, resposta="segue o plano")

    placar = grafo.placar()

    assert {raiz.raiz: raiz.contador_k for raiz in placar.raizes} == {"d1": 0, "d2": 0}
    assert _tipos(placar) == set()


def test_resposta_do_arbitro_aparece_marcada_e_nao_zera_nada_nominal() -> None:
    """A resposta do árbitro fica no placar com a marca e deixa K e M como estavam."""
    grafo = _com_plano().seq("d1", 20, 6)
    grafo.responde(seq=50, respondido_por="arb", papel="arbitro", raiz="d1", resposta="dispensado")

    placar = grafo.placar()

    assert placar.respostas_de_desvio[0].do_arbitro
    assert placar.em_dicionario()["respostas_de_desvio"][0]["do_arbitro"] is True
    assert _tipos(placar) == {("raiz", "d1"), ("goal", None)}
    assert "[árbitro: não zera]" in "\n".join(placar.linhas_de_desvio())


def test_aprovacao_humana_de_plano_zera_m_nominal() -> None:
    """Um novo plano humano é a nova referência e zera o contador; as B3 anteriores deixam de contar."""
    novo = {"versao": 2, "seq": 45, "aprovado_por": "david", "papel": "humano"}
    grafo = _Grafo([PLANO_HUMANO, novo]).no("d1", TipoNo.DECISION, 1).seq("d1", 20, 6)

    placar = grafo.placar()

    assert placar.referencia is not None and placar.referencia.versao == 2
    assert _tipos(placar) == set()


def test_inanicao_plano_parado_enquanto_o_emergente_anda_nominal() -> None:
    """Task do plano ainda pendente e mais de K emergentes já fora de `pendente` disparam a inanição."""
    ocioso = LimiaresDeDesvio(por_raiz=3, por_goal=50)
    grafo = _com_plano()
    for i in range(4):
        grafo.no(f"dx{i}", TipoNo.DECISION, 1).b3(f"t{i}", f"dx{i}", 20 + i, status="em_andamento")

    assert _tipos(grafo.placar(ocioso)) == {("inanicao", None)}


def test_sem_inanicao_se_o_plano_nao_tem_pendente_edge_case() -> None:
    """Com o plano inteiro iniciado, o emergente que anda não é inanição."""
    ocioso = LimiaresDeDesvio(por_raiz=3, por_goal=50)
    grafo = _com_plano()
    grafo.nos["t-plano2"] = grafo.nos["t-plano2"].com_propriedades({"status": "em_andamento"})
    for i in range(4):
        grafo.no(f"dx{i}", TipoNo.DECISION, 1).b3(f"t{i}", f"dx{i}", 20 + i, status="em_andamento")

    assert _tipos(grafo.placar(ocioso)) == set()


def test_veredito_de_escopo_tira_a_raiz_das_pendentes_nominal() -> None:
    """Só o veredito criado depois da Task que passou de K tira a raiz de `sem_veredito`."""
    grafo = _com_plano().seq("d1", 20, 4)
    assert grafo.placar().sem_veredito == ("d1",)

    grafo.no("ev-velho", TipoNo.EVIDENCE, 22, acao="veredito_de_escopo").liga("ev-velho", TipoAresta.DERIVA_DE, "d1")
    assert grafo.placar().sem_veredito == ("d1",)

    grafo.no("ev-novo", TipoNo.EVIDENCE, 30, acao="veredito_de_escopo").liga("ev-novo", TipoAresta.DERIVA_DE, "d1")
    assert grafo.placar().sem_veredito == ()


def test_reversao_entra_na_raiz_e_nao_dispara_gatilho_nominal() -> None:
    """Muitas reversões somam na raiz da decisão desfeita e não contam para K nem para M."""
    grafo = _com_plano().no("d-nova", TipoNo.DECISION, 2).liga("d-nova", TipoAresta.SUBSTITUI, "d1")
    for i in range(6):
        grafo.no(f"rev{i}", TipoNo.TASK, 20 + i).liga("g", TipoAresta.DECOMPOE, f"rev{i}")
        grafo.liga(f"rev{i}", TipoAresta.DESFAZ, "d1")

    placar = grafo.placar()

    assert placar.raizes[0].custo.reversoes == 6
    assert placar.contagem_por_classe["reversao"] == 6
    assert _tipos(placar) == set()


def test_as_cinco_linhas_da_secao_4_7_nominal() -> None:
    """O texto traz escopo, plano com fase, contagem, raiz que mais gerou com veredito pendente e cadeia."""
    arbitro = [{"versao": v, "seq": 15 + v, "aprovado_por": "arb", "papel": "arbitro"} for v in (2, 3)]
    grafo = _Grafo([PLANO_HUMANO, *arbitro]).no("d1", TipoNo.DECISION, 1)
    grafo.no("t-plano", TipoNo.TASK, 5, status="concluido").liga("g", TipoAresta.DECOMPOE, "t-plano")
    grafo.no("t-fim", TipoNo.TASK, 6, fase="F3").liga("g", TipoAresta.DECOMPOE, "t-fim")
    grafo.seq("d1", 30, 4, arquivos_alvo=["a.py"])

    linhas = grafo.placar().linhas()

    assert linhas == (
        "Escopo: plano_v1 (humano, seq 10) · v2-v3 pelo árbitro",
        "Plano: 2 Tasks · 1 concluídas · 1 sem começar (fase F3)",
        "Desde a referência: B1 0 · B3 4 · correção 0 · integração 0 · reversão 0",
        "Raiz que mais gerou: d1 · 4 Tasks B3 · 1 alvo · veredito de escopo pendente",
        "Cadeia mais longa: 1",
    )


def test_em_dicionario_traz_o_que_a_web_precisa_nominal() -> None:
    """O dicionário expõe referência, plano, raízes, gatilhos e limiares."""
    dicionario = _com_plano().seq("d1", 20, 4).placar().em_dicionario()

    assert dicionario["referencia"]["seq"] == SEQ_DO_PLANO
    assert dicionario["plano"]["sem_comecar_por_fase"] == {"F3": 1}
    assert dicionario["raiz_que_mais_gerou"] == "d1"
    assert dicionario["sem_veredito"] == ["d1"]
    assert dicionario["limiares"] == {"por_raiz": 3, "por_goal": 5}
    assert [g["tipo"] for g in dicionario["gatilhos_disparados"]] == ["raiz"]


def test_linhas_curtas_cabem_em_tres_linhas_nominal() -> None:
    """Referência com os emergentes, os gatilhos disparados (K e M) e as decisões sem veredito."""
    grafo = _com_plano().seq("d1", 20, 6)

    assert grafo.placar().linhas_curtas() == (
        "Escopo: plano_v1 (humano, seq 10) · emergentes desde a referência: 6",
        "Gatilhos disparados: K em d1 (6/3); M (6/5)",
        "Decisões sem veredito de escopo: d1",
    )


def test_linhas_curtas_sem_desvio_sao_uma_linha_edge_case() -> None:
    """Caso de borda: sem emergente a versão curta é a linha de referência e nada mais."""
    assert _com_plano().placar().linhas_curtas() == ("Escopo: plano_v1 (humano, seq 10) · emergentes desde a referência: 0",)
