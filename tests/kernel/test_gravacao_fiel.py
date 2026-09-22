"""O que os portões aprovam é o que o log grava.

Os portões liam o lote com o próprio parser, e o conversor e o acumulador
gravavam outra coisa. Cada caso de borda aqui é um lote que passava pelos
quatro portões e deixava no log algo diferente do que dizia. Tudo roda num
kernel em memória: nada toca o banco.
"""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

AGENTE: str = "agente"
CAMINHO_DO_STATUS: str = "/nos/task/propriedades/status"


def _no(id_no: str, tipo: TipoNo, **propriedades: str) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": dict(propriedades)}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado do tipo e das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _submeter(kernel: WriteKernel, *operacoes: ItemPatch, papel: PapelAutor = PapelAutor.EXECUTOR) -> ResultadoSubmissao:
    """Submete o lote sob o papel pedido, em nome do agente que tem a posse da Task."""
    dados = DadosPropostaPatch(autor=AGENTE, papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _kernel_com_trabalho() -> WriteKernel:
    """Sessao com uma Note, uma Constraint e uma Task travada por dúvida aberta, sob posse do agente."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        _no("nota", TipoNo.NOTE),
        _aresta("sess", "nota", TipoAresta.PRODUZ),
        _no("regra", TipoNo.CONSTRAINT),
        _aresta("sess", "regra", TipoAresta.PRODUZ),
        _no("task", TipoNo.TASK, status="pendente"),
        _aresta("sess", "task", TipoAresta.PRODUZ),
        _no("duvida", TipoNo.QUESTION, status="aberta"),
        _aresta("sess", "duvida", TipoAresta.PRODUZ),
        _aresta("duvida", "task", TipoAresta.BLOQUEIA),
        papel=PapelAutor.HUMANO,
    )
    assert recibo.sucesso, recibo.mensagem
    assert kernel.adquirir_lock_task("task", AGENTE)
    return kernel


def _ultimo_seq(kernel: WriteKernel) -> int:
    """Posição do log do ramo principal, lida do repositório e não da projeção."""
    return kernel.repositorio.obter_ultimo_seq("main")


def test_add_em_subcaminho_de_aresta_nao_envenena_o_log_edge_case() -> None:
    """Caso de borda: `add` em '/arestas/x/y' com tipo inválido ficava gravado e quebrava toda leitura.

    O SchemaGate só validava a criação de aresta em caminho de dois segmentos, e
    o conversor transformava qualquer `add` em '/arestas/...' em ARESTA_CRIADA.
    O acumulador estourava no tipo depois do `append_eventos`, e cada leitura
    seguinte do ramo estourava de novo.
    """
    kernel = _kernel_com_trabalho()
    seq = _ultimo_seq(kernel)
    valor = {"id": "x", "origem_id": "sess", "destino_id": "nota", "tipo": "tipo_fantasma"}

    recibo = _submeter(kernel, ItemPatch(op=OperacaoPatch.ADD, path="/arestas/x/y", value=valor))

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.CAMINHO_INVALIDO.value
    assert _ultimo_seq(kernel) == seq
    assert "x" not in kernel.obter_estado().arestas


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, PapelAutor.EXECUTOR])
def test_propriedades_que_nao_sao_objeto_sao_recusadas_sem_gravar_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: `"propriedades": "x"` passava pelos portões e estourava na projeção.

    Para o humano, o RoleGate nem antevê o lote, e o evento ficava gravado antes
    de o acumulador estourar no `dict("x")`. Para o executor, a antevisão do
    RoleGate estourava antes de gravar, mas como exceção, e não como recusa.
    """
    kernel = _kernel_com_trabalho()
    seq = _ultimo_seq(kernel)
    valor = {"id": "n9", "tipo": TipoNo.NOTE.value, "propriedades": "x"}

    recibo = _submeter(
        kernel,
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/n9", value=valor),
        _aresta("sess", "n9", TipoAresta.PRODUZ),
        papel=papel,
    )

    assert recibo.modo_de_falha == ModoFalhaMAST.ESTRUTURA_INCOMPLETA.value
    assert _ultimo_seq(kernel) == seq
    assert kernel.obter_estado().contem_no("n9") is False


def test_add_sobre_no_existente_nao_troca_o_tipo_edge_case() -> None:
    """Caso de borda: o executor não edita uma Constraint, mas a recriava como Note.

    O acumulador trata `add` de id existente como substituição, e o RoleGate só
    olhava o tipo novo, que o executor pode criar.
    """
    kernel = _kernel_com_trabalho()

    recibo = _submeter(kernel, _no("regra", TipoNo.NOTE))

    assert recibo.modo_de_falha == ModoFalhaMAST.ELEMENTO_JA_EXISTENTE.value
    assert "'regra'" in recibo.mensagem
    assert kernel.obter_estado().nos["regra"].tipo == TipoNo.CONSTRAINT


def test_add_sobre_aresta_existente_nao_desfaz_a_contencao_edge_case() -> None:
    """Caso de borda: a `produz` que o executor não pode remover era trocada por uma `deriva_de`.

    Com o mesmo id, o `add` substituía a aresta e a Note ficava sem pai: o
    InvariantGate só confere a hierarquia de nó criado no lote.
    """
    kernel = _kernel_com_trabalho()
    id_producao = f"{TipoAresta.PRODUZ.value}-sess-nota"
    valor = {"id": id_producao, "origem_id": "nota", "destino_id": "task", "tipo": TipoAresta.DERIVA_DE.value}

    recibo = _submeter(kernel, ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_producao}", value=valor))

    assert recibo.modo_de_falha == ModoFalhaMAST.ELEMENTO_JA_EXISTENTE.value
    assert kernel.obter_estado().arestas[id_producao].tipo == TipoAresta.PRODUZ


def test_mesmo_id_criado_duas_vezes_no_lote_e_recusado_edge_case() -> None:
    """Caso de borda: a segunda criação do mesmo id no lote trocava a primeira, de Note para Evidence."""
    kernel = _kernel_com_trabalho()

    recibo = _submeter(kernel, _no("n2", TipoNo.NOTE), _aresta("sess", "n2", TipoAresta.PRODUZ), _no("n2", TipoNo.EVIDENCE))

    assert recibo.modo_de_falha == ModoFalhaMAST.ELEMENTO_JA_EXISTENTE.value
    assert kernel.obter_estado().contem_no("n2") is False


def test_remover_e_recriar_o_mesmo_no_no_lote_nao_cria_orfao_edge_case() -> None:
    """Caso de borda: `remove` e `add` do mesmo id no lote recriavam a Note sem pai.

    O InvariantGate contava a `produz` antiga como contenção, mas a remoção do
    nó a apagava junto com ele.
    """
    kernel = _kernel_com_trabalho()

    recibo = _submeter(kernel, ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/nota"), _no("nota", TipoNo.NOTE))

    assert recibo.modo_de_falha == ModoFalhaMAST.ELEMENTO_JA_EXISTENTE.value
    assert kernel.obter_view().obter_arestas_entrada("nota", TipoAresta.PRODUZ)


def test_recriar_em_outro_lote_depois_de_remover_nominal() -> None:
    """O caminho para recriar um id continua aberto: remover num lote e criar, pendurado, no seguinte."""
    kernel = _kernel_com_trabalho()
    assert _submeter(kernel, ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/nota"), papel=PapelAutor.HUMANO).sucesso

    recibo = _submeter(kernel, _no("nota", TipoNo.NOTE), _aresta("sess", "nota", TipoAresta.PRODUZ))

    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("operacao", [OperacaoPatch.TEST, OperacaoPatch.MOVE, OperacaoPatch.COPY])
def test_operacao_sem_gravacao_fiel_nao_conclui_task_bloqueada_edge_case(operacao: OperacaoPatch) -> None:
    """Caso de borda: `test`, `move` e `copy` no status concluíam a Task travada por dúvida aberta.

    O conversor transformava toda op que não fosse `add` ou `remove` em escrita,
    e o InvariantGate só procurava o fechamento em `add` e `replace`.
    """
    kernel = _kernel_com_trabalho()

    recibo = _submeter(kernel, ItemPatch(op=operacao, path=CAMINHO_DO_STATUS, value="concluido"))

    assert recibo.modo_de_falha == ModoFalhaMAST.CAMINHO_INVALIDO.value
    assert kernel.obter_estado().nos["task"].propriedades["status"] == "pendente"


def test_replace_no_status_segue_barrado_pela_duvida_nominal() -> None:
    """A forma aceita continua sob a regra da dúvida bloqueante: só o desvio fechava a Task."""
    kernel = _kernel_com_trabalho()

    recibo = _submeter(kernel, ItemPatch(op=OperacaoPatch.REPLACE, path=CAMINHO_DO_STATUS, value="concluido"))

    assert recibo.modo_de_falha == ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE.value
