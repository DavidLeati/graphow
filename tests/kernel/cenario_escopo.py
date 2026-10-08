"""Cenário compartilhado dos testes do plano aprovado e da resposta de desvio, sobre um kernel de verdade.

O RoleGate decide por papel e política, e o InvariantGate confere a forma da
entrada contra o `versao_log`: os dois só se exercem juntos, por uma
submissão que passa pelos quatro portões.
"""

from typing import Any

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from tests.kernel.cenario_governanca import criar_aresta, criar_no, escrever
from tests.mcp.cenario_governanca import servidor

AUTORES: dict[PapelAutor, str] = {
    PapelAutor.HUMANO: "david",
    PapelAutor.PLANEJADOR: "planejador-1",
    PapelAutor.EXECUTOR: "executor-1#aaaa",
    PapelAutor.REVISOR: "revisor-1",
    PapelAutor.ARBITRO: "arbitro-1#bbbb",
}
AGENTES: tuple[PapelAutor, ...] = (PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR)


def montar_kernel_com_goal(preset: str | None = None, personalizada: dict[str, str] | None = None) -> WriteKernel:
    """Projeto, Setor, Sessão, o Goal `goal` com a Task `t1` sob ele e a Task `solta` sem Goal.

    `preset` e `personalizada` vão para a política global, pelo humano.
    """
    kernel = montar_kernel_em_memoria()
    operacoes = (
        criar_no("proj", TipoNo.PROJETO),
        criar_no("setor", TipoNo.SETOR),
        criar_aresta("cont-proj-setor", "proj", "setor", TipoAresta.CONTEM),
        criar_no("sess", TipoNo.SESSAO),
        criar_aresta("cont-setor-sess", "setor", "sess", TipoAresta.CONTEM),
        criar_no("goal", TipoNo.GOAL, status="em_andamento"),
        criar_aresta("prod-goal", "sess", "goal", TipoAresta.PRODUZ),
        criar_no("t1", TipoNo.TASK, status="pendente"),
        criar_aresta("prod-t1", "sess", "t1", TipoAresta.PRODUZ),
        criar_aresta("dec-goal-t1", "goal", "t1", TipoAresta.DECOMPOE),
        criar_no("solta", TipoNo.TASK, status="pendente"),
        criar_aresta("prod-solta", "sess", "solta", TipoAresta.PRODUZ),
        criar_no("dec-1", TipoNo.DECISION),
        criar_aresta("prod-dec-1", "sess", "dec-1", TipoAresta.PRODUZ),
    )
    assert submeter(kernel, PapelAutor.HUMANO, *operacoes).sucesso
    if preset is not None:
        pedido: dict[str, Any] = {"escopo": "global", "preset": preset}
        if personalizada:
            pedido["personalizada"] = personalizada
        recibo = servidor(kernel, "humano").executar_ferramenta("configurar_governanca", pedido)
        assert recibo["sucesso"] is True, recibo
    return kernel


def submeter(kernel: WriteKernel, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
    """Submete o lote sob o papel, com o autor padrão dele."""
    dados = DadosPropostaPatch(autor=AUTORES[papel], papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def definir_lista(campo: str, valor: Any, id_goal: str = "goal") -> ItemPatch:
    """A escrita da lista inteira do Goal, como o `propor_patch` livre a faria."""
    return escrever(OperacaoPatch.REPLACE, id_goal, campo, valor)


def entrada_do_plano(kernel: WriteKernel, quem: PapelAutor, **sobrescritas: Any) -> dict[str, Any]:
    """A entrada certa para a próxima versão do plano, no log de agora, com os campos trocados."""
    estado = kernel.obter_estado()
    anteriores = estado.nos["goal"].propriedades.get("planos") or []
    entrada: dict[str, Any] = {
        "versao": len(anteriores) + 1,
        "seq": estado.versao_log,
        "aprovado_por": AUTORES[quem],
        "papel": quem.value,
    }
    return {**entrada, **sobrescritas}


def entrada_da_resposta(kernel: WriteKernel, quem: PapelAutor, **sobrescritas: Any) -> dict[str, Any]:
    """A entrada certa para uma resposta de desvio, no log de agora, com os campos trocados."""
    entrada: dict[str, Any] = {
        "seq": kernel.obter_estado().versao_log,
        "respondido_por": AUTORES[quem],
        "papel": quem.value,
        "raiz": None,
        "resposta": "seguir",
    }
    return {**entrada, **sobrescritas}


def lista_do_goal(kernel: WriteKernel, campo: str) -> list[dict[str, Any]]:
    """O valor gravado do campo no Goal, vazio quando ausente."""
    return list(kernel.obter_estado().nos["goal"].propriedades.get(campo) or [])
