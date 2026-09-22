"""Os aprendizados de um alcance se acumulam e o grafo pede a própria consolidação como trabalho.

Cobrado pelo efeito, como a condensação: a proposta passa pelos quatro portões
de verdade, a Task aparece na fila da sessão que abre, e o pedido não se repete.
"""

from graphow.core.events import EventoLog
from graphow.core.types import OrigemEvento, PapelAutor, StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.fila_trabalho import FilaDeTrabalho
from graphow.reactive.consolidacao import (
    ACAO_DE_CONSOLIDAR,
    AUTOR_DO_CONSOLIDADOR,
    LIMITE_DE_VIGENTES_POR_ALCANCE,
    AprendizadosAcumuladosBehavior,
    eh_tarefa_de_consolidacao,
)
from graphow.reactive.engine import MotorReativo
from graphow.reactive.montagem import ligar_motor_reativo_padrao, montar_comportamentos_padrao


def _no(id_no: str, tipo: TipoNo, **propriedades: str) -> ItemPatch:
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


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch]) -> tuple[str, ...]:
    """Escreve como humano e devolve os eventos gerados."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem
    return recibo.eventos_gerados


def _aprendizado(numero: int, alcance: str = "proj") -> list[ItemPatch]:
    """Um Aprendizado da sessão antiga, derivado da decisão e promovido ao alcance (Projeto ou global)."""
    id_no = f"apr-{numero:02d}"
    propriedades = {"como_aplicar": "aplique"}
    if alcance == "global":
        propriedades["alcance"] = "global"
    operacoes = [
        _no(id_no, TipoNo.APRENDIZADO, **propriedades),
        _aresta("sess-antiga", id_no, TipoAresta.PRODUZ),
        _aresta(id_no, "dec-1", TipoAresta.DERIVA_DE),
    ]
    if alcance != "global":
        operacoes.append(_aresta(id_no, alcance, TipoAresta.VALE_PARA))
    return operacoes


def _kernel_com_vigentes(quantidade: int, alcance: str = "proj") -> WriteKernel:
    """Projeto, Setor e uma sessão antiga, encerrada, que produziu os aprendizados promovidos."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            _no("proj", TipoNo.PROJETO),
            _no("setor", TipoNo.SETOR),
            _aresta("proj", "setor", TipoAresta.CONTEM),
            _no("sess-antiga", TipoNo.SESSAO, status=StatusSessao.CONCLUIDA.value),
            _aresta("setor", "sess-antiga", TipoAresta.CONTEM),
            _no("dec-1", TipoNo.DECISION),
            _aresta("sess-antiga", "dec-1", TipoAresta.PRODUZ),
        ],
    )
    for numero in range(quantidade):
        _submeter(kernel, _aprendizado(numero, alcance))
    return kernel


def _abrir_sessao(kernel: WriteKernel, id_sessao: str = "sess-nova") -> EventoLog:
    """Uma sessão nova nasce no Setor; devolve o evento que a criou."""
    gerados = _submeter(
        kernel,
        [_no(id_sessao, TipoNo.SESSAO, status=StatusSessao.ATIVA.value), _aresta("setor", id_sessao, TipoAresta.CONTEM)],
    )
    evento = kernel.obter_evento(gerados[0])
    assert evento is not None
    return evento


def _motor(kernel: WriteKernel) -> MotorReativo:
    """Motor só com o comportamento sob teste."""
    motor = MotorReativo(kernel)
    motor.registrar_comportamento(AprendizadosAcumuladosBehavior())
    return motor


def _tarefas(kernel: WriteKernel) -> list:  # type: ignore[type-arg]
    """Tasks de consolidar presentes na projeção."""
    return [no for no in kernel.obter_view().listar_nos_por_tipo(TipoNo.TASK) if eh_tarefa_de_consolidacao(no)]


def test_sessao_que_abre_num_alcance_lotado_recebe_a_tarefa_de_consolidar_nominal() -> None:
    """A Task nasce pendurada na sessão que abre, lista os vigentes e é assinada como planejador."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    motor = _motor(kernel)

    motor.processar_evento(_abrir_sessao(kernel))

    tarefas = _tarefas(kernel)
    assert len(tarefas) == 1
    tarefa = tarefas[0]
    assert tarefa.obter_propriedade("acao") == ACAO_DE_CONSOLIDAR
    assert tarefa.obter_propriedade("id_alvo") == "proj"
    assert "apr-12" in str(tarefa.obter_propriedade("descricao"))
    assert "substitui" in str(tarefa.obter_propriedade("descricao"))
    assert tarefa.proveniencia.autor == AUTOR_DO_CONSOLIDADOR
    assert tarefa.proveniencia.papel == PapelAutor.PLANEJADOR.value
    assert tarefa.proveniencia.origem == OrigemEvento.COMPORTAMENTO.value
    assert motor.recusas_registradas == ()
    fila = FilaDeTrabalho(kernel.obter_view()).proximas_tarefas("sess-nova")
    assert [item.rotulo for item in fila] == ["Consolidar aprendizados: proj"]
    assert fila[0].status == StatusTask.PENDENTE.value


def test_no_limite_nao_pede_consolidacao_edge_case() -> None:
    """Caso de borda: o limite é o teto que ainda cabe; só o excedente pede."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE)

    _motor(kernel).processar_evento(_abrir_sessao(kernel))

    assert _tarefas(kernel) == []


def test_substituido_por_promovido_nao_conta_como_vigente_edge_case() -> None:
    """Caso de borda: consolidar reduz a conta; o absorvido por um promovido já não pesa."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    _submeter(kernel, [_aresta("apr-00", "apr-01", TipoAresta.SUBSTITUI)])

    _motor(kernel).processar_evento(_abrir_sessao(kernel))

    assert _tarefas(kernel) == []


def test_pedido_pendente_nao_se_repete_em_outra_sessao_edge_case() -> None:
    """Caso de borda: enquanto a Task está aberta, cada sessão nova não pede de novo."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    motor = _motor(kernel)
    evento = _abrir_sessao(kernel)
    motor.processar_evento(evento)

    motor.processar_evento(evento)
    motor.processar_evento(_abrir_sessao(kernel, "sess-outra"))

    assert len(_tarefas(kernel)) == 1


def test_reabrir_a_sessao_tambem_pede_nominal() -> None:
    """A sessão retomada volta a `ativa` pelo harness; o pedido chega a ela do mesmo jeito."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    _abrir_sessao(kernel)
    _submeter(kernel, [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/sess-nova/propriedades/status", value="concluida")])
    gerados = _submeter(
        kernel, [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/sess-nova/propriedades/status", value="ativa")]
    )
    evento = kernel.obter_evento(gerados[0])
    assert evento is not None

    _motor(kernel).processar_evento(evento)

    assert len(_tarefas(kernel)) == 1


def test_alcance_global_tambem_e_consolidado_nominal() -> None:
    """Os globais valem em toda sessão: lotados, a Task nasce onde a sessão abrir."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1, alcance="global")

    _motor(kernel).processar_evento(_abrir_sessao(kernel))

    tarefas = _tarefas(kernel)
    assert len(tarefas) == 1
    assert tarefas[0].obter_propriedade("id_alvo") == "global"
    assert tarefas[0].rotulo == "Consolidar aprendizados globais"


def test_inicio_pelo_harness_abre_a_consolidacao_com_o_motor_ligado_nominal() -> None:
    """O hook de início abre a sessão; o motor ligado no mesmo processo pede a consolidação nela."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    ligar_motor_reativo_padrao(kernel)

    ServicoHarness(kernel).registrar(PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor="setor"))

    assert len(_tarefas(kernel)) == 1
    fila = FilaDeTrabalho(kernel.obter_view()).proximas_tarefas("sess-hook")
    assert [item.rotulo for item in fila] == ["Consolidar aprendizados: proj"]


def test_comportamento_faz_parte_da_montagem_padrao_nominal() -> None:
    """A consolidação é comportamento nativo do produto, não opção."""
    nomes = {comportamento.nome for comportamento in montar_comportamentos_padrao()}

    assert "AprendizadosAcumulados" in nomes


def test_evento_que_nao_abre_sessao_e_ignorado_edge_case() -> None:
    """Caso de borda: um aprendizado a mais não dispara nada; só a sessão que abre pede."""
    kernel = _kernel_com_vigentes(LIMITE_DE_VIGENTES_POR_ALCANCE + 1)
    gerados = _submeter(kernel, _aprendizado(99))
    evento = kernel.obter_evento(gerados[0])
    assert evento is not None

    assert AprendizadosAcumuladosBehavior().avaliar(evento, kernel.obter_view()) is None
