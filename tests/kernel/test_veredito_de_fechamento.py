"""O agente só conclui uma Task com veredito de revisão aprovado: a regra do kernel, fora da política."""

from typing import Any

import pytest

from graphow.core.falhas import CategoriaFalhaMAST, ModoFalhaMAST, categoria_de
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog, ProvenienciaNo
from graphow.core.orquestracao import ACAO_ACEITE_APOS_REPROVACAO, ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.invariant_gate import InvariantGate
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao

EXECUTOR: str = "executor-1"
LOCKS: dict[str, str] = {"t1": EXECUTOR}


def _no(id_no: str, tipo: TipoNo, papel: str, seq: int = 0, **propriedades: object) -> NoGrafo:
    """Nó já gravado, escrito pelo `papel` na posição `seq` do log."""
    return NoGrafo(id_no, tipo, id_no, propriedades, proveniencia=ProvenienciaNo(autor=papel, papel=papel), ordem=OrdemNoLog(seq, seq))


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Aresta de id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ArestaGrafo(id_aresta, origem, destino, tipo)


class Cenario:
    """Sessão, Task `t1` e Artifact `art-1` que deriva dela; acrescenta julgamentos, correções e aceites."""

    def __init__(self, **propriedades_da_task: object) -> None:
        status = {"status": StatusTask.PRONTO_PARA_REVISAO.value, **propriedades_da_task}
        self.nos: dict[str, NoGrafo] = {
            "sess-1": _no("sess-1", TipoNo.SESSAO, "humano"),
            "t1": _no("t1", TipoNo.TASK, "planejador", **status),
            "art-1": _no("art-1", TipoNo.ARTIFACT, "executor"),
        }
        self.arestas: dict[str, ArestaGrafo] = {}
        self.liga("art-1", "t1", TipoAresta.DERIVA_DE)

    def liga(self, origem: str, destino: str, tipo: TipoAresta) -> "Cenario":
        """Cria a aresta entre as pontas."""
        aresta = _aresta(origem, destino, tipo)
        self.arestas[aresta.id] = aresta
        return self

    def julga(self, id_no: str, veredito: str, seq: int, *, papel: str = "revisor", alvo: str = "t1") -> "Cenario":
        """Evidence de revisão gravada pelo `papel`, derivada do alvo."""
        self.nos[id_no] = _no(id_no, TipoNo.EVIDENCE, papel, seq, veredito=veredito)
        return self.liga(id_no, alvo, TipoAresta.DERIVA_DE)

    def corrige(self, id_task: str, id_veredito: str, **propriedades: object) -> "Cenario":
        """Task de correção da Evidence de rejeição, com o status dado por `propriedades`."""
        self.nos[id_task] = _no(id_task, TipoNo.TASK, "planejador", corrige=id_veredito, **propriedades)
        return self

    def aceita(self, id_decisao: str, *, alvo: str = "t1", justificada_por: str = "", papel: str = "planejador") -> "Cenario":
        """Decision de aceite pelo teto, criada pelo `papel`, que orienta o alvo e é justificada pela Evidence."""
        self.nos[id_decisao] = _no(id_decisao, TipoNo.DECISION, papel, acao=ACAO_ACEITE_APOS_REPROVACAO)
        self.liga(id_decisao, alvo, TipoAresta.ORIENTA)
        return self.liga(justificada_por, id_decisao, TipoAresta.JUSTIFICA) if justificada_por else self

    def estado(self) -> GrafoEstado:
        """O estado do grafo, na versão 100 do log."""
        return GrafoEstado(nos=dict(self.nos), arestas=dict(self.arestas), versao_log=100)


def _concluir(
    *, papel: PapelAutor = PapelAutor.EXECUTOR, extras: tuple[ItemPatch, ...] = (), inteiro: bool = False
) -> PropostaPatch:
    """O lote que conclui `t1`, na propriedade isolada ou reescrevendo o nó inteiro, com operações a mais."""
    if inteiro:
        propriedades = {"status": StatusTask.CONCLUIDO.value}
        valor: dict[str, Any] = {"id": "t1", "tipo": TipoNo.TASK.value, "rotulo": "T1", "propriedades": propriedades}
        fechar = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1", value=valor)
    else:
        fechar = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.CONCLUIDO.value)
    return PropostaPatch.criar(DadosPropostaPatch(autor=EXECUTOR, papel=papel, operacoes=[*extras, fechar]))


def _veredito_no_lote(id_no: str, veredito: str, alvo: str = "art-1") -> tuple[ItemPatch, ...]:
    """Cria no lote a Evidence de revisão, produzida pela sessão e derivada do alvo."""
    return (
        ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={
            "id": id_no, "tipo": TipoNo.EVIDENCE.value, "rotulo": id_no, "propriedades": {"veredito": veredito},
        }),
        ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/prod-{id_no}", value={
            "id": f"prod-{id_no}", "origem_id": "sess-1", "destino_id": id_no, "tipo": TipoAresta.PRODUZ.value,
        }),
        ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/deriva-{id_no}", value={
            "id": f"deriva-{id_no}", "origem_id": id_no, "destino_id": alvo, "tipo": TipoAresta.DERIVA_DE.value,
        }),
    )


def _validar(proposta: PropostaPatch, cenario: Cenario) -> ResultadoValidacao:
    """Passa o lote pelo InvariantGate com `t1` na posse do executor."""
    return InvariantGate().validar(proposta, cenario.estado(), LOCKS)


def _recusado_por_falta_de_veredito(resultado: ResultadoValidacao) -> bool:
    """A recusa é a do veredito, no portão certo e com o modo próprio."""
    return (
        not resultado.aprovado
        and resultado.modo == ModoFalhaMAST.FECHAMENTO_SEM_VEREDITO_APROVADO
        and resultado.portao_falha == "InvariantGate"
    )


def test_executor_sem_veredito_nao_conclui_a_task_nominal() -> None:
    """Sem revisão nenhuma, o executor é recusado, e a mensagem diz o que falta."""
    resultado = _validar(_concluir(), Cenario())

    assert _recusado_por_falta_de_veredito(resultado)
    mensagem = str(resultado.mensagem_erro)
    assert "veredito" in mensagem and "aprovado" in mensagem and "deriva_de" in mensagem and "Artifact" in mensagem
    assert resultado.contexto_detalhado == {"id_task": "t1"}


def test_o_modo_de_falha_e_de_verificacao_de_tarefa_nominal() -> None:
    """O modo novo cai na família de verificação, como as outras recusas de fechamento."""
    assert categoria_de(ModoFalhaMAST.FECHAMENTO_SEM_VEREDITO_APROVADO) == CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA


def test_executor_com_veredito_reprovado_nao_conclui_edge_case() -> None:
    """Caso de borda: rejeitado não é aprovado."""
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), Cenario().julga("ev-1", "rejeitado", 10)))


@pytest.mark.parametrize("papel", ["revisor", "humano", "arbitro"])
def test_executor_com_veredito_aprovado_de_quem_julga_conclui_nominal(papel: str) -> None:
    """Com a revisão aprovada, de quem julga, ligada à Task, o fechamento passa."""
    assert _validar(_concluir(), Cenario().julga("ev-1", "aprovado", 10, papel=papel)).aprovado is True


@pytest.mark.parametrize("papel", ["executor", "planejador", "sistema", ""])
def test_aprovacao_de_quem_nao_julga_nao_conta_edge_case(papel: str) -> None:
    """Caso de borda: a Evidence aprovada pelo próprio executor, ou sem proveniência, não abre o fechamento."""
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), Cenario().julga("ev-1", "aprovado", 10, papel=papel)))


def test_aprovacao_de_executor_nao_apaga_a_rejeicao_do_revisor_edge_case() -> None:
    """Caso de borda: a rejeição do revisor segue vigente por cima da aprovação posterior do executor."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10).julga("ev-eu", "aprovado", 20, papel="executor")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def test_veredito_aprovado_do_artifact_da_task_vale_nominal() -> None:
    """O revisor deriva o veredito do Artifact: ele conta para a Task do Artifact."""
    assert _validar(_concluir(), Cenario().julga("ev-1", "aprovado", 10, alvo="art-1")).aprovado is True


def test_veredito_aprovado_no_mesmo_lote_de_quem_julga_conta_edge_case() -> None:
    """Caso de borda: o árbitro que cria a Evidence aprovada junto com o fechamento já vale."""
    proposta = _concluir(papel=PapelAutor.ARBITRO, extras=_veredito_no_lote("ev-novo", "aprovado"))

    assert _validar(proposta, Cenario()).aprovado is True


def test_veredito_aprovado_no_mesmo_lote_do_executor_nao_conta_edge_case() -> None:
    """Caso de borda: o executor não cria a própria aprovação no lote que fecha a Task."""
    proposta = _concluir(extras=_veredito_no_lote("ev-novo", "aprovado"))

    assert _recusado_por_falta_de_veredito(_validar(proposta, Cenario()))


def test_veredito_reprovado_no_mesmo_lote_recusa_edge_case() -> None:
    """Caso de borda: criar a revisão reprovada no lote do fechamento não abre a porta."""
    proposta = _concluir(papel=PapelAutor.ARBITRO, extras=_veredito_no_lote("ev-novo", "rejeitado"))

    assert _recusado_por_falta_de_veredito(_validar(proposta, Cenario()))


def test_aprovado_no_lote_vence_a_reprovacao_antiga_edge_case() -> None:
    """Caso de borda: a Evidence nova é o último julgamento, mesmo sem posição no log."""
    proposta = _concluir(papel=PapelAutor.ARBITRO, extras=_veredito_no_lote("ev-novo", "aprovado"))

    assert _validar(proposta, Cenario().julga("ev-velho", "rejeitado", 90)).aprovado is True


def test_aprovado_removido_no_mesmo_lote_nao_conta_edge_case() -> None:
    """Caso de borda: o lote que apaga a aprovação não pode usá-la para fechar."""
    remover = ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/ev-1")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(extras=(remover,)), Cenario().julga("ev-1", "aprovado", 10)))


def test_reprovado_depois_de_aprovado_volta_a_recusar_edge_case() -> None:
    """Caso de borda: só o último julgamento vale, e ele reprova."""
    cenario = Cenario().julga("ev-ok", "aprovado", 10).julga("ev-no", "rejeitado", 20)

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def test_aprovado_depois_de_reprovado_conclui_edge_case() -> None:
    """Caso de borda: a aprovação posterior à rejeição libera o fechamento."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10).julga("ev-ok", "aprovado", 20)

    assert _validar(_concluir(), cenario).aprovado is True


def test_status_dentro_do_no_inteiro_tambem_exige_veredito_edge_case() -> None:
    """Caso de borda: reescrever a Task inteira com `concluido` não contorna a regra."""
    assert _recusado_por_falta_de_veredito(_validar(_concluir(inteiro=True), Cenario()))
    assert _validar(_concluir(inteiro=True), Cenario().julga("ev-1", "aprovado", 10)).aprovado is True


def test_humano_conclui_sem_veredito_nominal() -> None:
    """O humano é o dono do grafo e está isento."""
    assert _validar(_concluir(papel=PapelAutor.HUMANO), Cenario()).aprovado is True


@pytest.mark.parametrize("acao", [ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR])
def test_tarefa_de_manutencao_da_memoria_fecha_sem_veredito_nominal(acao: str) -> None:
    """Condensar a sessão e consolidar aprendizados não têm revisor: o executor as fecha."""
    assert _validar(_concluir(), Cenario(acao=acao)).aprovado is True


def test_outra_acao_nao_isenta_a_task_edge_case() -> None:
    """Caso de borda: só as duas ações abertas pelo grafo ficam isentas."""
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), Cenario(acao="revisar_artefatos")))


def test_mover_o_status_para_outro_valor_nao_exige_veredito_nominal() -> None:
    """A regra é do fechamento: pronto_para_revisao segue livre para o executor."""
    operacao = ItemPatch(
        op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.PRONTO_PARA_REVISAO.value
    )
    proposta = PropostaPatch.criar(DadosPropostaPatch(autor=EXECUTOR, papel=PapelAutor.EXECUTOR, operacoes=[operacao]))

    assert _validar(proposta, Cenario()).aprovado is True


def test_correcao_aprovada_supera_a_rejeicao_da_original_nominal() -> None:
    """A original rejeitada fecha quando a correção que aponta a rejeição tem veredito aprovado."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10).corrige("t1c", "ev-no").julga("ev-c", "aprovado", 20, alvo="t1c")

    assert _validar(_concluir(), cenario).aprovado is True


def test_correcao_nao_aprovada_nao_supera_a_rejeicao_edge_case() -> None:
    """Caso de borda: sem veredito, ou reprovada, a correção não libera a original."""
    sem_veredito = Cenario().julga("ev-no", "rejeitado", 10).corrige("t1c", "ev-no")
    reprovada = Cenario().julga("ev-no", "rejeitado", 10).corrige("t1c", "ev-no").julga("ev-c", "rejeitado", 20, alvo="t1c")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), sem_veredito))
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), reprovada))


def test_correcao_de_outra_evidencia_nao_supera_edge_case() -> None:
    """Caso de borda: a correção aprovada de uma rejeição antiga não vale para a rejeição vigente."""
    cenario = (
        Cenario().julga("ev-velha", "rejeitado", 10).julga("ev-no", "rejeitado", 20)
        .corrige("t1c", "ev-velha").julga("ev-c", "aprovado", 30, alvo="t1c")
    )

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def test_cadeia_de_correcoes_segue_ate_a_aprovada_edge_case() -> None:
    """Caso de borda: a correção rejeitada, corrigida por outra aprovada, libera toda a cadeia."""
    cenario = (
        Cenario().julga("ev-no", "rejeitado", 10).corrige("t1c", "ev-no")
        .julga("ev-c1", "rejeitado", 20, alvo="t1c").corrige("t1cc", "ev-c1").julga("ev-c2", "aprovado", 30, alvo="t1cc")
    )

    assert _validar(_concluir(), cenario).aprovado is True


def test_ciclo_na_cadeia_de_correcoes_nao_supera_nem_trava_edge_case() -> None:
    """Caso de borda: duas Tasks que se corrigem entre si terminam em recusa, sem recursão infinita."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10).corrige("t1c", "ev-no").julga("ev-c", "rejeitado", 20, alvo="t1c")
    cenario.nos["t1"] = _no("t1", TipoNo.TASK, "planejador", corrige="ev-c", status=StatusTask.PRONTO_PARA_REVISAO.value)

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def _com_aceite(**opcoes: str) -> Cenario:
    """Rejeitada duas vezes, com a Decision de aceite pelo teto que orienta `t1`."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10)
    return cenario.aceita("dec-aceite", justificada_por="ev-no", **opcoes)


@pytest.mark.parametrize("papel", ["planejador", "humano", "arbitro"])
def test_aceite_pelo_teto_de_quem_pode_aceitar_libera_o_fechamento_nominal(papel: str) -> None:
    """A Decision de aceite do condutor, justificada pelo veredito vigente, libera o executor."""
    assert _validar(_concluir(), _com_aceite(papel=papel)).aprovado is True


@pytest.mark.parametrize("papel", ["executor", "revisor", "sistema", ""])
def test_aceite_de_quem_nao_pode_aceitar_nao_libera_edge_case(papel: str) -> None:
    """Caso de borda: o executor não se aceita sozinho, e a Decision sem proveniência de aceitador não conta."""
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), _com_aceite(papel=papel)))


def test_aceite_sem_justifica_do_veredito_vigente_nao_libera_edge_case() -> None:
    """Caso de borda: sem a `justifica` vinda da Evidence vigente, ou vinda de outra, a Decision não vale."""
    sem_justifica = Cenario().julga("ev-no", "rejeitado", 10).aceita("dec-aceite")
    de_outra = Cenario().julga("ev-velha", "rejeitado", 5).julga("ev-no", "rejeitado", 10).aceita("dec-aceite", justificada_por="ev-velha")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), sem_justifica))
    assert _recusado_por_falta_de_veredito(_validar(_concluir(), de_outra))


def test_aceite_que_nao_orienta_a_task_nao_libera_edge_case() -> None:
    """Caso de borda: a Decision de aceite orienta outra Task, e `t1` segue sem veredito aprovado."""
    cenario = Cenario().julga("ev-no", "rejeitado", 10)
    cenario.nos["t2"] = _no("t2", TipoNo.TASK, "planejador")
    cenario.aceita("dec-aceite", alvo="t2", justificada_por="ev-no")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def test_decision_de_outra_acao_nao_e_aceite_edge_case() -> None:
    """Caso de borda: só a ação `aceite_apos_reprovacao` libera."""
    cenario = _com_aceite()
    cenario.nos["dec-aceite"] = _no("dec-aceite", TipoNo.DECISION, "planejador", acao="outra")

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))


def test_aceite_nao_vale_depois_de_um_veredito_novo_edge_case() -> None:
    """Caso de borda: o aceite justificava a rejeição antiga; a rejeição nova pede outro aceite."""
    cenario = _com_aceite().julga("ev-nova", "rejeitado", 50)

    assert _recusado_por_falta_de_veredito(_validar(_concluir(), cenario))
