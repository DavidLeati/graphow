"""O papel `orquestrador` pode o que o laço precisa, não pode as reservas do humano, e nenhum MCP o alcança."""

from collections.abc import Sequence
from typing import Any

import pytest

from graphow.api.cli_parser import construir_parser
from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.papel_do_orquestrador import validar_escrita_do_orquestrador
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP

ORQUESTRADOR: PapelAutor = PapelAutor.ORQUESTRADOR


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch], papel: PapelAutor = ORQUESTRADOR) -> ResultadoSubmissao:
    """Um lote sob o papel dado."""
    autor = "humano-teste" if papel == PapelAutor.HUMANO else "graphow-orquestrar"
    dados = DadosPropostaPatch(autor=autor, papel=papel, operacoes=tuple(operacoes), justificativa="teste")
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


def _produzido(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> list[ItemPatch]:
    """O nó de trabalho pendurado na Sessao do orquestrador."""
    return [_no(id_no, tipo, propriedades), _aresta("sess", id_no, TipoAresta.PRODUZ)]


def _kernel_com_goal_e_fatias() -> WriteKernel:
    """Projeto, Setor, Sessao, Goal com critério e decisão, e duas fatias, a segunda dependendo da primeira."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        [
            _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
            _no("sess", TipoNo.SESSAO, {"status": "ativa"}), _aresta("setor", "sess", TipoAresta.CONTEM),
            *_produzido("goal", TipoNo.GOAL, {"status": "pendente"}),
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
    verificacao = _submeter(
        kernel, [*_produzido("ver-1", TipoNo.EVIDENCE, {"veredito": "aprovado", "commit": "abc123"}),
                 _aresta("ver-1", "goal", TipoAresta.DERIVA_DE)],
    )
    fechamento = _submeter(kernel, [_propriedade("goal", "status", "concluido"), _propriedade("sess", "status", "concluida")])

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


def test_correcao_depois_do_plano_aprovado_entra_pela_verificacao_rejeitada_nominal() -> None:
    """Com o plano aprovado pelo humano, a Task de correção vale por `corrige` na Evidence rejeitada."""
    kernel = _kernel_com_goal_e_fatias()
    entrada = {"versao": 1, "seq": kernel.obter_view().versao_log, "aprovado_por": "humano-teste", "papel": "humano"}
    aprovacao = ItemPatch(OperacaoPatch.REPLACE, "/nos/goal/propriedades/planos", [entrada])
    assert _submeter(kernel, [aprovacao], PapelAutor.HUMANO).sucesso
    rejeitada = [*_produzido("ver-1", TipoNo.EVIDENCE, {"veredito": "rejeitado"}), _aresta("ver-1", "goal", TipoAresta.DERIVA_DE)]
    assert _submeter(kernel, rejeitada).sucesso

    sem_ligacao = _submeter(kernel, [*_produzido("c-1", TipoNo.TASK, {"status": "pendente"}), _aresta("goal", "c-1", TipoAresta.DECOMPOE)])
    correcao = _submeter(
        kernel, [*_produzido("c-2", TipoNo.TASK, {"status": "pendente", "corrige": "ver-1"}), _aresta("goal", "c-2", TipoAresta.DECOMPOE)]
    )

    assert not sem_ligacao.sucesso
    assert correcao.sucesso, correcao.mensagem


@pytest.mark.parametrize(
    "operacoes",
    [
        _produzido("apr", TipoNo.APRENDIZADO),
        _produzido("q-fechada", TipoNo.QUESTION, {"status": "respondida"}),
        [_propriedade("proj", "governanca", {"preset": "arbitragem_maxima"})],
        [_propriedade("proj", "nivel_autonomia", "ilimitado")],
        [_propriedade("goal", "planos", [])],
        [_propriedade("goal", "respostas_de_desvio", [])],
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


def test_governanca_fica_fora_do_contrato_edge_case() -> None:
    """Caso de borda: o contrato recusa criar a Governanca, que o SchemaGate já recusaria pela forma."""
    proposta = PropostaPatch.criar(
        DadosPropostaPatch(autor="graphow-orquestrar", papel=ORQUESTRADOR, operacoes=(_no("gov", TipoNo.GOVERNANCA),))
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
