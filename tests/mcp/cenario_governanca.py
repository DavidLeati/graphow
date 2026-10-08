"""Cenário compartilhado dos testes de governança na camada MCP.

Dois projetos com a mesma forma (Projeto, Setor, Sessao, Task com posse alheia,
Decision), para que a política de um se compare com a do outro.
"""

from typing import Any

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer

DONO_DA_POSSE: str = "executor-alheio#abc123"
AUTOR_DO_AGENTE: str = "executor-1"
AUTOR_DO_ARBITRO: str = "arbitro-1"
PRESETS_FIXOS: tuple[str, ...] = ("governanca_maxima", "arbitragem_maxima")


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """Operação de criação de nó."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _operacoes_do_projeto(sufixo: str) -> list[ItemPatch]:
    """Projeto, Setor, Sessao, Task pendente e Decision, todos ligados."""
    projeto, setor, sessao = f"proj-{sufixo}", f"setor-{sufixo}", f"sess-{sufixo}"
    return [
        _no(projeto, TipoNo.PROJETO),
        _no(setor, TipoNo.SETOR),
        _aresta(projeto, setor, TipoAresta.CONTEM),
        _no(sessao, TipoNo.SESSAO),
        _aresta(setor, sessao, TipoAresta.CONTEM),
        _no(f"task-{sufixo}", TipoNo.TASK, {"status": "pendente"}),
        _aresta(sessao, f"task-{sufixo}", TipoAresta.PRODUZ),
        _no(f"dec-{sufixo}", TipoNo.DECISION),
        _aresta(sessao, f"dec-{sufixo}", TipoAresta.PRODUZ),
    ]


def montar_kernel() -> WriteKernel:
    """Dois projetos, 'a' e 'b', escritos pelo humano, com posse alheia na Task de cada um."""
    kernel = montar_kernel_em_memoria()
    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=_operacoes_do_projeto("a") + _operacoes_do_projeto("b"),
                justificativa="cenario",
            )
        )
    )
    assert recibo.sucesso, recibo.mensagem
    for sufixo in ("a", "b"):
        assert kernel.adquirir_lock_task(f"task-{sufixo}", DONO_DA_POSSE)
    return kernel


def servidor(kernel: WriteKernel, papel: str, autor: str = "") -> GraphowMCPServer:
    """Servidor MCP sobre o kernel, sob o papel informado."""
    padrao = AUTOR_DO_ARBITRO if papel == "arbitro" else AUTOR_DO_AGENTE if papel != "humano" else "david"
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar(autor or padrao, papel))


def definir_preset_global(kernel: WriteKernel, preset: str) -> None:
    """O humano grava o preset global."""
    resposta = servidor(kernel, "humano").executar_ferramenta(
        "configurar_governanca", {"escopo": "global", "preset": preset}
    )
    assert resposta["sucesso"] is True, resposta


def definir_preset_do_projeto(kernel: WriteKernel, id_projeto: str, preset: str) -> None:
    """O humano grava o preset de um Projeto."""
    resposta = servidor(kernel, "humano").executar_ferramenta(
        "configurar_governanca", {"escopo": id_projeto, "preset": preset}
    )
    assert resposta["sucesso"] is True, resposta


def aprovar_plano(kernel: WriteKernel, id_goal: str, papel: str = "humano", autor: str = "") -> None:
    """Aprova o plano do Goal: o executor só assume Task de Goal que tem um plano vigente."""
    resposta = servidor(kernel, papel, autor).executar_ferramenta("aprovar_plano", {"id_goal": id_goal})
    assert resposta["sucesso"] is True, resposta


def abrir_questao_como_agente(kernel: WriteKernel, sufixo: str = "a") -> str:
    """Um executor abre uma dúvida que bloqueia a Task do projeto; devolve o id."""
    resposta = servidor(kernel, "executor").executar_ferramenta(
        "abrir_questao",
        {"pergunta": "Posso seguir?", "id_no_bloqueado": f"task-{sufixo}", "id_sessao": f"sess-{sufixo}"},
    )
    assert resposta["sucesso"] is True, resposta
    return str(resposta["id_questao"])


def registrar_aprendizado_como_agente(kernel: WriteKernel, sufixo: str = "a") -> str:
    """Um executor registra um aprendizado na sessão do projeto; devolve o id."""
    resposta = servidor(kernel, "executor").executar_ferramenta(
        "registrar_aprendizado",
        {"afirmacao": "Licao", "id_sessao": f"sess-{sufixo}", "origens": [f"dec-{sufixo}"]},
    )
    assert resposta["sucesso"] is True, resposta
    return str(resposta["id_aprendizado"])


def chamadas_do_gesto(kernel: WriteKernel) -> dict[str, dict[str, Any]]:
    """Uma chamada válida de cada ferramenta que depende da política, sobre o projeto 'a'.

    As Questions e o Aprendizado são abertos por um executor, de modo que o
    árbitro não esbarra no anti-autoconflito.
    """
    return {
        "responder_questao": {"id_questao": abrir_questao_como_agente(kernel), "resposta": "Siga"},
        "promover_aprendizado": {"id_aprendizado": registrar_aprendizado_como_agente(kernel)},
        "encerrar_sessao": {"id_sessao": "sess-a"},
        "excluir_projeto": {"id_projeto": "proj-a"},
        "excluir_em_lote": {"ids_nos": ["dec-a"]},
    }
