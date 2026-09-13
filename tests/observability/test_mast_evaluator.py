"""Testes unitários para MASTEvaluator."""

from graphow.kernel.patch_models import ResultadoValidacao
from graphow.observability.mast_evaluator import (
    CategoriaFalhaMAST,
    MASTEvaluator,
    ModoFalhaMAST,
)


def test_mast_evaluator_aprovado_retorna_none_nominal() -> None:
    """Testa que validação aprovada não gera diagnóstico de falha."""
    res = ResultadoValidacao.sucesso()
    diag = MASTEvaluator.classificar_resultado(res)
    assert diag is None


def test_mast_evaluator_classifica_desalinhamento_papel_edge_case() -> None:
    """Caso de borda: erro de permissão é classificado como DESALINHAMENTO_DE_AGENTE."""
    res = ResultadoValidacao.falha("Papel 'executor' não possui permissão para criar nó", "RoleGate")
    diag = MASTEvaluator.classificar_resultado(res)
    assert diag is not None
    assert diag.categoria == CategoriaFalhaMAST.DESALINHAMENTO_DE_AGENTE
    assert diag.modo == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL


def test_mast_evaluator_classifica_ciclo_e_bloqueio_edge_case() -> None:
    """Caso de borda: detecção de ciclo como DESIGN_DO_SISTEMA e bloqueio como VERIFICACAO_DE_TAREFA."""
    res_ciclo = ResultadoValidacao.falha("Aresta criaria um ciclo proibido", "InvariantGate")
    diag_ciclo = MASTEvaluator.classificar_resultado(res_ciclo)
    assert diag_ciclo is not None
    assert diag_ciclo.categoria == CategoriaFalhaMAST.DESIGN_DO_SISTEMA
    assert diag_ciclo.modo == ModoFalhaMAST.CICLO_DEPENDENCIA

    res_bloq = ResultadoValidacao.falha("Task possui Question aberta bloqueante", "InvariantGate")
    diag_bloq = MASTEvaluator.classificar_resultado(res_bloq)
    assert diag_bloq is not None
    assert diag_bloq.categoria == CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA
    assert diag_bloq.modo == ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE
