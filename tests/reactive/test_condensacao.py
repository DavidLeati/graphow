"""A sessão encerra e o grafo pede a própria condensação como trabalho.

O comportamento é cobrado pelo efeito, não pela intenção: a proposta passa
pelos quatro portões de verdade e a Task precisa aparecer na fila da sessão.
"""

from typing import Any

import pytest

from graphow.context.fechamento import ACAO_DE_CONDENSACAO
from graphow.core.events import EventoLog
from graphow.core.types import OrigemEvento, PapelAutor, StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.fila_trabalho import FilaDeTrabalho
from graphow.reactive.condensacao import (
    ACAO_DE_CONDENSAR,
    AUTOR_DO_CONDENSADOR,
    ROTEIRO_DA_CONDENSACAO,
    ROTEIRO_DA_CONDENSACAO_COM_ARBITRO,
    SessaoEncerradaBehavior,
    eh_tarefa_de_condensacao,
)
from graphow.reactive.engine import MotorReativo
from graphow.reactive.montagem import ligar_motor_reativo_padrao, montar_comportamentos_padrao


def _no(id_no: str, tipo: TipoNo, **propriedades: Any) -> ItemPatch:
    """Operação de criação de nó com rótulo igual ao id."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": dict(propriedades)},
    )


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO) -> tuple[str, ...]:
    """Escreve sob o papel informado e devolve os eventos gerados."""
    dados = DadosPropostaPatch(autor="autor-teste", papel=papel, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem
    return recibo.eventos_gerados


def _kernel_com_sessao(com_trabalho: bool = True, governanca: dict[str, Any] | None = None) -> WriteKernel:
    """Hierarquia com uma sessão ativa que produziu (ou não) uma decisão; o Projeto pode declarar a governança."""
    kernel = montar_kernel_em_memoria()
    propriedades = {"governanca": governanca} if governanca else {}
    operacoes = [
        _no("proj", TipoNo.PROJETO, **propriedades),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO, status=StatusSessao.ATIVA.value),
        _aresta("setor", "sess", TipoAresta.CONTEM),
    ]
    if com_trabalho:
        operacoes.extend([_no("dec-1", TipoNo.DECISION), _aresta("sess", "dec-1", TipoAresta.PRODUZ)])
    _submeter(kernel, operacoes)
    return kernel


def _encerrar(kernel: WriteKernel) -> EventoLog:
    """O humano encerra a sessão; devolve o evento que registrou o status."""
    gerados = _submeter(
        kernel,
        [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/sess/propriedades/status", value=StatusSessao.CONCLUIDA.value)],
    )
    evento = kernel.obter_evento(gerados[0])
    assert evento is not None
    return evento


def _motor(kernel: WriteKernel) -> MotorReativo:
    """Motor só com o comportamento sob teste."""
    motor = MotorReativo(kernel)
    motor.registrar_comportamento(SessaoEncerradaBehavior())
    return motor


def _tarefas_de_condensacao(kernel: WriteKernel) -> list:  # type: ignore[type-arg]
    """Tasks de condensar presentes na projeção."""
    return [no for no in kernel.obter_view().listar_nos_por_tipo(TipoNo.TASK) if eh_tarefa_de_condensacao(no)]


def test_sessao_encerrada_abre_a_tarefa_de_condensacao_nominal() -> None:
    """A Task nasce pendurada na sessão, assinada como planejador e com origem comportamento."""
    kernel = _kernel_com_sessao()
    motor = _motor(kernel)

    motor.processar_evento(_encerrar(kernel))

    tarefas = _tarefas_de_condensacao(kernel)
    assert len(tarefas) == 1
    tarefa = tarefas[0]
    assert tarefa.obter_propriedade("acao") == ACAO_DE_CONDENSAR
    assert tarefa.obter_propriedade("id_alvo") == "sess"
    assert ACAO_DE_CONDENSACAO in str(tarefa.obter_propriedade("descricao"))
    assert tarefa.proveniencia.autor == AUTOR_DO_CONDENSADOR
    assert tarefa.proveniencia.papel == PapelAutor.PLANEJADOR.value
    assert tarefa.proveniencia.origem == OrigemEvento.COMPORTAMENTO.value
    assert motor.recusas_registradas == ()


def test_tarefa_de_condensacao_entra_na_fila_da_sessao_nominal() -> None:
    """É por `proximas_tarefas` que o agente descobre o pedido."""
    kernel = _kernel_com_sessao()
    _motor(kernel).processar_evento(_encerrar(kernel))

    fila = FilaDeTrabalho(kernel.obter_view()).proximas_tarefas("sess")

    assert len(fila) == 1
    assert fila[0].rotulo == "Condensar sessao: sess"
    assert fila[0].status == StatusTask.PENDENTE.value


def test_encerrar_duas_vezes_nao_pede_duas_condensacoes_edge_case() -> None:
    """Caso de borda: a Task pendente já é o pedido; repetir o status não repete o pedido."""
    kernel = _kernel_com_sessao()
    motor = _motor(kernel)
    motor.processar_evento(_encerrar(kernel))

    motor.processar_evento(_encerrar(kernel))

    assert len(_tarefas_de_condensacao(kernel)) == 1


def test_sessao_sem_trabalho_nao_pede_condensacao_edge_case() -> None:
    """Caso de borda: uma sessão vazia não tem o que condensar."""
    kernel = _kernel_com_sessao(com_trabalho=False)

    _motor(kernel).processar_evento(_encerrar(kernel))

    assert _tarefas_de_condensacao(kernel) == []


def test_mudanca_de_status_que_nao_encerra_e_ignorada_edge_case() -> None:
    """Caso de borda: reabrir a sessão não pede nada."""
    kernel = _kernel_com_sessao()
    gerados = _submeter(
        kernel,
        [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/sess/propriedades/status", value=StatusSessao.ATIVA.value)],
    )
    evento = kernel.obter_evento(gerados[0])
    assert evento is not None

    assert SessaoEncerradaBehavior().avaliar(evento, kernel.obter_view()) is None


def test_fim_pelo_harness_abre_a_condensacao_quando_o_motor_esta_ligado_nominal() -> None:
    """O hook de fim de sessão passa a pedir a condensação, sem depender do processo web."""
    kernel = _kernel_com_sessao()
    ligar_motor_reativo_padrao(kernel)

    ServicoHarness(kernel).registrar(PedidoDeCicloDeVida(fase=FaseDoHarness.FIM, id_sessao="sess", resumo="feito"))

    assert "MotorReativo" in kernel.observadores_registrados
    assert len(_tarefas_de_condensacao(kernel)) == 1


def test_comportamento_faz_parte_da_montagem_padrao_nominal() -> None:
    """A condensação é comportamento nativo do produto, não opção."""
    nomes = {comportamento.nome for comportamento in montar_comportamentos_padrao()}

    assert "SessaoEncerrada" in nomes


def test_revisor_condensa_com_deriva_de_para_evidencia_nominal() -> None:
    """O par Note -> Evidence passou a existir: a condensação aponta para o achado."""
    kernel = _kernel_com_sessao()
    _submeter(kernel, [_no("ev-1", TipoNo.EVIDENCE), _aresta("sess", "ev-1", TipoAresta.PRODUZ)])

    _submeter(
        kernel,
        [
            _no("nota-cond", TipoNo.NOTE, acao=ACAO_DE_CONDENSACAO, id_alvo="sess", corpo="Vigora dec-1 por ev-1."),
            _aresta("sess", "nota-cond", TipoAresta.PRODUZ),
            _aresta("nota-cond", "dec-1", TipoAresta.DERIVA_DE),
            _aresta("nota-cond", "ev-1", TipoAresta.DERIVA_DE),
        ],
        PapelAutor.REVISOR,
    )

    view = kernel.obter_view()
    destinos = {aresta.destino_id for aresta in view.obter_arestas_saida("nota-cond", TipoAresta.DERIVA_DE)}
    assert destinos == {"dec-1", "ev-1"}


@pytest.mark.parametrize(
    ("valor", "roteiro"),
    [("humano", ROTEIRO_DA_CONDENSACAO), ("arbitro", ROTEIRO_DA_CONDENSACAO_COM_ARBITRO)],
)
def test_roteiro_da_condensacao_reflete_a_politica_de_promover_aprendizado_nominal(valor: str, roteiro: str) -> None:
    """Com promover_aprendizado=arbitro o roteiro diz quem promove; com humano fica como antes."""
    governanca = {"preset": "personalizada", "personalizada": {"promover_aprendizado": valor}}
    kernel = _kernel_com_sessao(governanca=governanca)

    _motor(kernel).processar_evento(_encerrar(kernel))

    descricao = str(_tarefas_de_condensacao(kernel)[0].obter_propriedade("descricao"))
    assert descricao == roteiro
    assert ("arbitro" in descricao) is (valor == "arbitro")
    assert ("nunca global" in descricao) is (valor == "arbitro")
