"""Ferramentas MCP de posse de tarefa: adquirir e devolver a escrita exclusiva.

`adquirir_lock_task` existia na API Python e nenhuma das ferramentas MCP a
chamava: qualquer executor concluía qualquer Task, inclusive a de outro, e dois
executores na mesma tarefa não colidiam. Estas duas ferramentas realizam o item
"leitura paralela, escrita serializada" na superfície que os agentes usam.
"""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.core.types import StatusTask
from graphow.mcp.construcao_operacoes import montar_operacao_definir_propriedade
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)


class FerramentasPosse:
    """Aquisição e devolução do direito exclusivo de escrever numa Task."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de posse aos seus executores."""
        return {
            "assumir_tarefa": self.assumir_tarefa,
            "liberar_tarefa": self.liberar_tarefa,
        }

    def assumir_tarefa(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Adquire o lock da Task e a move para 'em_andamento' no mesmo gesto."""
        id_task = str(argumentos["id_task"])
        autor = self._contexto.identidade.autor
        ja_era_nosso = self._contexto.kernel.obter_dono_do_lock(id_task) == autor
        if not self._contexto.kernel.adquirir_lock_task(id_task, autor):
            return self._recusar_por_dono_atual(id_task)
        recibo = self._marcar_em_andamento(id_task, argumentos)
        if not recibo["sucesso"] and not ja_era_nosso:
            self._contexto.kernel.liberar_lock_task(id_task, autor)
        return recibo

    def _recusar_por_dono_atual(self, id_task: str) -> dict[str, Any]:
        """Informa quem detém a tarefa, para o agente escolher outra da fila."""
        dono = self._contexto.kernel.obter_dono_do_lock(id_task)
        return {
            "sucesso": False,
            "id_task": id_task,
            "dono_atual": dono,
            "erro": (
                f"A tarefa '{id_task}' ja foi assumida por '{dono}'. "
                "Use 'proximas_tarefas' para escolher outra disponivel."
            ),
        }

    def _marcar_em_andamento(
        self,
        id_task: str,
        argumentos: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Registra no grafo que a tarefa passou a ter um responsável ativo."""
        pedido = PedidoSubmissaoMCP(
            operacoes=(
                montar_operacao_definir_propriedade(id_task, "status", StatusTask.EM_ANDAMENTO.value),
                montar_operacao_definir_propriedade(
                    id_task, "assumida_por", self._contexto.identidade.autor
                ),
            ),
            justificativa=f"Posse da tarefa {id_task}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_task": id_task},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def liberar_tarefa(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Devolve o lock da Task, deixando o status como está.

        O humano devolve a posse de qualquer um. Um subagente que morre sem
        liberar deixa a tarefa presa a um autor que não volta mais, e nenhum
        agente a tira dali: só o dono do grafo.
        """
        id_task = str(argumentos["id_task"])
        autor = self._autor_que_libera(id_task)
        liberado = self._contexto.kernel.liberar_lock_task(id_task, autor)
        if liberado:
            mensagem = "Posse devolvida" if autor == self._contexto.identidade.autor else f"Posse de '{autor}' devolvida"
            return {"sucesso": True, "id_task": id_task, "mensagem": mensagem}
        return {
            "sucesso": False,
            "id_task": id_task,
            "dono_atual": self._contexto.kernel.obter_dono_do_lock(id_task),
            "erro": f"A tarefa '{id_task}' nao esta sob a posse de '{autor}'",
        }

    def _autor_que_libera(self, id_task: str) -> str:
        """Em sessão humana, o dono atual do lock; em sessão de agente, o próprio autor."""
        identidade = self._contexto.identidade
        dono = self._contexto.kernel.obter_dono_do_lock(id_task)
        if identidade.eh_humano and dono:
            return dono
        return identidade.autor
