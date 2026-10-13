"""O papel `orquestrador` pode o que o laço precisa no Goal que conduz, e nada fora dele nem nas reservas do humano."""

from collections.abc import Sequence
from typing import Any

import pytest

from graphow.api.cli_parser import construir_parser
from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.papel_do_orquestrador import sessao_do_goal, validar_escrita_do_orquestrador
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP

ORQUESTRADOR: PapelAutor = PapelAutor.ORQUESTRADOR
SESSAO: str = sessao_do_goal("goal")
CONDUCAO: dict[str, Any] = {"orquestracao": {"modo": "autonomo"}}


def _submeter(
    kernel: WriteKernel, operacoes: Sequence[ItemPatch], papel: PapelAutor = ORQUESTRADOR, *, goal: str = "goal"
) -> ResultadoSubmissao:
    """Um lote sob o papel dado; o do orquestrador diz o Goal que conduz."""
    autor = "humano-teste" if papel == PapelAutor.HUMANO else "graphow-orquestrar"
    conduzido = goal if papel == ORQUESTRADOR else None
    dados = DadosPropostaPatch(autor=autor, papel=papel, operacoes=tuple(operacoes), justificativa="teste", goal_conduzido=conduzido)
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """Cria um nó com as propriedades dadas."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Cria a aresta tipada entre os dois nós."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}", valor)


def _propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """Escreve uma propriedade de nó existente."""
    return ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_no}/propriedades/{chave}", valor)


def _produzido(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None, *, sessao: str = SESSAO) -> list[ItemPatch]:
    """O nó de trabalho pendurado na Sessao do orquestrador para o Goal."""
    return [_no(id_no, tipo, propriedades), _aresta(sessao, id_no, TipoAresta.PRODUZ)]


def _prova_do_fechamento(id_goal: str = "goal", sessao: str = SESSAO) -> list[ItemPatch]:
    """A ponta da branch, um critério e a verificação final limpa nela, com ele atendido: o que o kernel exige para fechar."""
    id_ver, id_criterio = f"ver-{id_goal}", f"criterio-{id_goal}"
    propriedades = {"acao": "verificacao_do_goal", "numero": 1, "final": True, "veredito": "aprovado", "commit_do_codigo": "abc123",
                    "pareceres": [{"id": "C1", "no": id_criterio, "veredito": "atende", "prova": "aceite verde"}]}
    return [_propriedade(id_goal, "ponta_do_ramo", {"commit": "abc123", "commit_do_codigo": "abc123"}),
            *_produzido(id_criterio, TipoNo.CRITERIO, {"codigo": "C1", "texto": "c", "verificacao": "teste"}, sessao=sessao),
            _aresta(id_criterio, id_goal, TipoAresta.ESCOPA),
            *_produzido(id_ver, TipoNo.EVIDENCE, propriedades, sessao=sessao), _aresta(id_ver, id_goal, TipoAresta.DERIVA_DE)]


def _kernel_com_goal_e_fatias() -> WriteKernel:
    """Projeto, Setor, a Sessao do Goal, o Goal conduzido com critério e decisão, e duas fatias."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        [
            _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
            _no(SESSAO, TipoNo.SESSAO, {"status": "ativa"}), _aresta("setor", SESSAO, TipoAresta.CONTEM),
            *_produzido("goal", TipoNo.GOAL, {"status": "pendente", **CONDUCAO}),
            *_produzido("crit-1", TipoNo.CONSTRAINT, {"tipo": "criterio_aceite"}), _aresta("crit-1", "goal", TipoAresta.ESCOPA),
            *_produzido("dec-1", TipoNo.DECISION, {"motivo": "pedido do humano"}), _aresta("dec-1", "goal", TipoAresta.ORIENTA),
            *_produzido("f1", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "f1", TipoAresta.DECOMPOE),
            *_produzido("f2", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "f2", TipoAresta.DECOMPOE),
            _aresta("f2", "f1", TipoAresta.DEPENDE_DE),
        ],
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _concluir_fatia(kernel: WriteKernel, id_task: str) -> ResultadoSubmissao:
    """Grava o commit da fatia como Artifact e conclui a Task, sem posse nem revisor."""
    return _submeter(
        kernel,
        [
            _propriedade(id_task, "status", "em_andamento"),
            *_produzido(f"art-{id_task}", TipoNo.ARTIFACT, {"commit": "abc123"}),
            _aresta(f"art-{id_task}", id_task, TipoAresta.DERIVA_DE),
            _propriedade(id_task, "status", "concluido"),
        ],
    )


def test_orquestrador_grava_o_goal_conclui_fatias_e_fecha_sem_posse_nem_revisor_nominal() -> None:
    """O laço inteiro no kernel: plano, fatias concluídas, verificação ligada ao Goal e o Goal fechado."""
    kernel = _kernel_com_goal_e_fatias()

    assert _concluir_fatia(kernel, "f1").sucesso
    assert _concluir_fatia(kernel, "f2").sucesso
    verificacao = _submeter(kernel, _prova_do_fechamento())
    fechamento = _submeter(kernel, [_propriedade("goal", "status", "concluido"), _propriedade(SESSAO, "status", "concluida")])

    assert verificacao.sucesso, verificacao.mensagem
    assert fechamento.sucesso, fechamento.mensagem
    view = kernel.obter_view()
    assert view.obter_no("goal").obter_propriedade("status") == "concluido"
    assert view.obter_no("f2").proveniencia.papel == "orquestrador"


def test_duvida_aberta_pausa_a_fatia_ate_o_humano_responder_nominal() -> None:
    """A Question que o orquestrador abre trava a Task também para ele; a resposta é do humano."""
    kernel = _kernel_com_goal_e_fatias()
    abertura = _submeter(kernel, [*_produzido("q-1", TipoNo.QUESTION, {"status": "aberta"}), _aresta("q-1", "f1", TipoAresta.BLOQUEIA)])

    travada = _concluir_fatia(kernel, "f1")
    resposta = _submeter(kernel, [_propriedade("q-1", "status", "respondida")], PapelAutor.HUMANO)

    assert abertura.sucesso, abertura.mensagem
    assert not travada.sucesso
    assert travada.modo_de_falha == ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE.value
    assert resposta.sucesso
    assert _concluir_fatia(kernel, "f1").sucesso


def test_regras_do_escopo_governado_nao_valem_para_o_goal_que_o_orquestrador_conduz_nominal() -> None:
    """Num Goal conduzido com plano aprovado pelo escopo governado, a fatia do orquestrador entra sem ligação de escopo.

    O plano do orquestrador é dele; a isenção é só do papel orquestrador, no
    Goal que ele conduz: o humano que cria a mesma Task sem ligação segue
    recusado pelo escopo.
    """
    kernel = _kernel_com_goal_e_fatias()
    entrada = {"versao": 1, "seq": kernel.obter_view().versao_log, "aprovado_por": "humano-teste", "papel": "humano"}
    aprovacao = ItemPatch(OperacaoPatch.REPLACE, "/nos/goal/propriedades/planos", [entrada])
    assert _submeter(kernel, [aprovacao], PapelAutor.HUMANO).sucesso

    do_orquestrador = _submeter(kernel, [*_produzido("c-1", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "c-1", TipoAresta.DECOMPOE)])
    do_humano = _submeter(
        kernel, [*_produzido("c-2", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "c-2", TipoAresta.DECOMPOE)], PapelAutor.HUMANO
    )

    assert do_orquestrador.sucesso, do_orquestrador.mensagem
    assert not do_humano.sucesso
    assert do_humano.modo_de_falha == ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE.value


@pytest.mark.parametrize(
    "operacoes",
    [
        _produzido("apr", TipoNo.APRENDIZADO),
        _produzido("q-fechada", TipoNo.QUESTION, {"status": "respondida"}),
        [_propriedade("proj", "governanca", {"preset": "arbitragem_maxima"})],
        [_propriedade("proj", "nivel_autonomia", "ilimitado")],
        [_propriedade("goal", "planos", [])],
        [_propriedade("goal", "respostas_de_desvio", [])],
        [_propriedade("goal", "aprovacao_do_plano", {"papel": "humano", "por": "orquestrador"})],
        [ItemPatch(OperacaoPatch.REMOVE, "/nos/f2")],
        [ItemPatch(OperacaoPatch.REMOVE, "/arestas/depende_de-f2-f1")],
    ],
)
def test_reservas_do_humano_ficam_fora_do_contrato_edge_case(operacoes: list[ItemPatch]) -> None:
    """Caso de borda: governança, memória, plano aprovado, resposta e remoção são do humano."""
    kernel = _kernel_com_goal_e_fatias()

    recibo = _submeter(kernel, operacoes)

    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
    assert "orquestrador" in recibo.mensagem


def _kernel_com_nos_do_humano() -> WriteKernel:
    """O Goal do gerente com uma Decision e uma Constraint do humano, ainda não adotado."""
    kernel = montar_kernel_em_memoria()
    humano = [
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-h", TipoNo.SESSAO), _aresta("setor", "sess-h", TipoAresta.CONTEM),
        _no("goal", TipoNo.GOAL), _aresta("sess-h", "goal", TipoAresta.PRODUZ),
        _no("dec-h", TipoNo.DECISION), _aresta("sess-h", "dec-h", TipoAresta.PRODUZ),
        _no("crit-h", TipoNo.CONSTRAINT, {"tipo": "criterio_aceite"}), _aresta("sess-h", "crit-h", TipoAresta.PRODUZ),
    ]
    assert _submeter(kernel, humano, PapelAutor.HUMANO).sucesso
    return kernel


def _adocao() -> list[ItemPatch]:
    """Adotar o Goal do gerente: a Sessao do orquestrador no Setor, a spec e a configuração do laço."""
    return [
        _no(SESSAO, TipoNo.SESSAO, {"status": "ativa"}), _aresta("setor", SESSAO, TipoAresta.CONTEM),
        _propriedade("goal", "spec", "texto"), _propriedade("goal", "orquestracao", {"modo": "autonomo"}),
    ]


@pytest.mark.parametrize(
    "operacao",
    [
        ItemPatch(OperacaoPatch.REPLACE, "/nos/dec-h/rotulo", "decisao reescrita"),
        _propriedade("dec-h", "motivo", "outro motivo"),
        _propriedade("crit-h", "tipo", "fronteira"),
        _propriedade("setor", "descricao", "outro"),
        ItemPatch(OperacaoPatch.REPLACE, "/nos/goal/rotulo", "outro titulo"),
        _propriedade("goal", "status", "concluido"),
        _aresta("dec-h", "goal", TipoAresta.ORIENTA),
    ],
)
def test_orquestrador_nao_mexe_no_que_e_do_humano_edge_case(operacao: ItemPatch) -> None:
    """Caso de borda: rótulo e propriedades dos nós do humano, o Goal que ele não conduz e a aresta entre dois nós do humano."""
    kernel = _kernel_com_nos_do_humano()

    recibo = _submeter(kernel, [operacao])

    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_adocao_do_goal_do_gerente_abre_o_alcance_do_orquestrador_nominal() -> None:
    """Adotar grava a Sessao, `spec` e `orquestracao`; depois disso o Goal é conduzido, e o laço o fecha."""
    kernel = _kernel_com_nos_do_humano()

    adocao = _submeter(kernel, _adocao())
    fatia = _submeter(kernel, [*_produzido("f1", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "f1", TipoAresta.DECOMPOE)])
    prova = _submeter(kernel, _prova_do_fechamento())
    fechamento = _submeter(kernel, [_propriedade("goal", "status", "concluido")])

    assert adocao.sucesso, adocao.mensagem
    assert fatia.sucesso, fatia.mensagem
    assert prova.sucesso, prova.mensagem
    assert fechamento.sucesso, fechamento.mensagem


def _kernel_com_dois_goals_e_o_humano() -> WriteKernel:
    """Dois Goals conduzidos no mesmo Setor (A e B, cada um com a Sessao e uma fatia) e um Goal do humano com Decision e Task."""
    kernel = _kernel_com_nos_do_humano()
    assert _submeter(kernel, [
        _no("h-task", TipoNo.TASK, {"status": "pendente"}), _aresta("sess-h", "h-task", TipoAresta.PRODUZ),
        _aresta("goal", "h-task", TipoAresta.DECOMPOE),
        _no("h-goal2", TipoNo.GOAL, {"status": "pendente"}), _aresta("sess-h", "h-goal2", TipoAresta.PRODUZ),
    ], PapelAutor.HUMANO).sucesso
    for nome in ("a", "b"):
        id_goal, sessao = f"goal-{nome}", sessao_do_goal(f"goal-{nome}")
        recibo = _submeter(kernel, [
            _no(sessao, TipoNo.SESSAO, {"status": "ativa"}), _aresta("setor", sessao, TipoAresta.CONTEM),
            *_produzido(id_goal, TipoNo.GOAL, {"status": "pendente", **CONDUCAO}, sessao=sessao),
            *_produzido(f"{id_goal}-dec", TipoNo.DECISION, {"motivo": "plano"}, sessao=sessao),
            *_produzido(f"{id_goal}-q", TipoNo.QUESTION, {"status": "aberta"}, sessao=sessao),
            *_produzido(f"{id_goal}-f1", TipoNo.TASK, {"status": "pendente"}, sessao=sessao),
            _aresta(id_goal, f"{id_goal}-f1", TipoAresta.DECOMPOE),
        ], goal=id_goal)
        assert recibo.sucesso, recibo.mensagem
    return kernel


@pytest.mark.parametrize(
    ("operacoes", "goal", "trecho"),
    [
        ([_aresta("goal-a-dec", "dec-h", TipoAresta.SUBSTITUI)], "goal-a", "nao cria aresta 'substitui'"),
        ([_aresta("goal-a-q", "h-task", TipoAresta.BLOQUEIA)], "goal-a", "'h-task' esta fora do Goal"),
        ([_aresta("goal-a", "h-task", TipoAresta.DECOMPOE)], "goal-a", "'h-task' esta fora do Goal"),
        ([_aresta("goal-a-dec", "h-goal2", TipoAresta.ORIENTA)], "goal-a", "'h-goal2' esta fora do Goal"),
        ([_aresta("goal-a-q", "goal-b-f1", TipoAresta.BLOQUEIA)], "goal-a", "'goal-b-f1' esta fora do Goal"),
        ([_propriedade("goal-b", "status", "concluido")], "goal-a", "'goal-b' esta fora do Goal"),
        ([_propriedade("goal-b-f1", "status", "concluido")], "goal-a", "'goal-b-f1' esta fora do Goal"),
        (_produzido("intruso", TipoNo.NOTE, sessao=sessao_do_goal("goal-b")), "goal-a", "'intruso' nasce fora do Goal"),
        ([_no("solto", TipoNo.NOTE)], "goal-a", "'solto' nasce fora do Goal"),
        (_produzido("t-h", TipoNo.TASK, sessao=sessao_do_goal("goal-a")) + [_aresta("h-goal2", "t-h", TipoAresta.DECOMPOE)],
         "h-goal2", "nao e conduzido pelo orquestrador"),
    ],
)
def test_lote_do_orquestrador_fica_dentro_do_goal_que_conduz_edge_case(operacoes: list[ItemPatch], goal: str, trecho: str) -> None:
    """Caso de borda: aresta para nó do humano ou de outro Goal, lote do Goal A no Goal B e Goal que ele não conduz."""
    kernel = _kernel_com_dois_goals_e_o_humano()

    recibo = _submeter(kernel, operacoes, goal=goal)

    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
    assert trecho in recibo.mensagem, recibo.mensagem


def test_aresta_que_ja_existe_nao_se_edita_edge_case() -> None:
    """Caso de borda: trocar a ponta de uma aresta é refazer a ligação; o contrato a recusa antes de qualquer forma."""
    kernel = _kernel_com_dois_goals_e_o_humano()
    troca = ItemPatch(OperacaoPatch.REPLACE, "/arestas/decompoe-goal-a-goal-a-f1/destino_id", "h-task")
    proposta = PropostaPatch.criar(DadosPropostaPatch(autor="graphow-orquestrar", papel=ORQUESTRADOR, operacoes=(troca,), goal_conduzido="goal-a"))

    resultado = validar_escrita_do_orquestrador(proposta, kernel.obter_view().estado)

    assert not resultado.aprovado
    assert "nao edita aresta" in (resultado.mensagem_erro or "")


def test_lote_sem_o_goal_conduzido_e_recusado_edge_case() -> None:
    """Caso de borda: o lote do orquestrador que não diz o Goal que conduz não passa, nem para o próprio Goal."""
    kernel = _kernel_com_goal_e_fatias()
    dados = DadosPropostaPatch(autor="graphow-orquestrar", papel=ORQUESTRADOR, operacoes=(_propriedade("f1", "status", "em_andamento"),))

    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert not recibo.sucesso
    assert "diz o Goal que conduz" in recibo.mensagem


def test_cada_goal_do_mesmo_setor_segue_no_proprio_lote_nominal() -> None:
    """Dois Goals conduzidos no mesmo Setor: cada lote fecha a fatia e o Goal dele."""
    kernel = _kernel_com_dois_goals_e_o_humano()

    for nome in ("a", "b"):
        id_goal = f"goal-{nome}"
        operacoes = [_propriedade(f"{id_goal}-f1", "status", "concluido"), *_prova_do_fechamento(id_goal, sessao_do_goal(id_goal))]
        assert _submeter(kernel, operacoes, goal=id_goal).sucesso
        recibo = _submeter(kernel, [_propriedade(id_goal, "status", "concluido")], goal=id_goal)
        assert recibo.sucesso, recibo.mensagem


def test_governanca_fica_fora_do_contrato_edge_case() -> None:
    """Caso de borda: o contrato recusa criar a Governanca, que o SchemaGate já recusaria pela forma."""
    proposta = PropostaPatch.criar(
        DadosPropostaPatch(autor="graphow-orquestrar", papel=ORQUESTRADOR, operacoes=(_no("gov", TipoNo.GOVERNANCA),), goal_conduzido="goal")
    )

    resultado = validar_escrita_do_orquestrador(proposta, GrafoEstado())

    assert not resultado.aprovado
    assert resultado.modo == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL


def test_orquestrador_nao_encerra_a_duvida_que_abriu_edge_case() -> None:
    """Caso de borda: responder ao executor é do humano, mesmo para quem abriu a Question."""
    kernel = _kernel_com_goal_e_fatias()
    assert _submeter(kernel, [*_produzido("q-1", TipoNo.QUESTION, {"status": "aberta"}), _aresta("q-1", "f1", TipoAresta.BLOQUEIA)]).sucesso

    recibo = _submeter(kernel, [_propriedade("q-1", "status", "descartada")])

    assert not recibo.sucesso
    assert kernel.obter_view().obter_no("q-1").obter_propriedade("status") == "aberta"


def test_nenhuma_sessao_mcp_abre_com_o_papel_do_orquestrador_edge_case() -> None:
    """Caso de borda: nem a identidade da sessão nem a linha de comando do servidor aceitam o papel."""
    with pytest.raises(ErroPermissaoPapel):
        IdentidadeSessaoMCP.criar("agente", "orquestrador")
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["mcp", "--papel", "orquestrador"])
