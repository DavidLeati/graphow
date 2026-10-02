"""Ferramentas MCP de posse de tarefa: adquirir e devolver a escrita exclusiva.

`adquirir_lock_task` existia na API Python e nenhuma das ferramentas MCP a
chamava: qualquer executor concluía qualquer Task, inclusive a de outro, e dois
executores na mesma tarefa não colidiam. Estas duas ferramentas realizam o item
"leitura paralela, escrita serializada" na superfície que os agentes usam.
"""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.core.governanca import Gesto
from graphow.core.orquestracao import VEREDITO_APROVADO
from graphow.core.types import PapelAutor, StatusTask
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.mcp.construcao_operacoes import montar_operacao_definir_propriedade
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)
from graphow.projection.revisao import veredito_vigente

# Na Task e no recibo: de quem o executor retomou a posse órfã.
CAMPO_POSSE_RETOMADA_DE: str = "posse_retomada_de"
# No recibo de assumir_tarefa: o autor da conexão que pediu a posse.
CAMPO_AUTOR: str = "autor"


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
        """Adquire o lock da Task e a move para 'em_andamento' no mesmo gesto.

        O recibo diz sempre o autor desta conexão, aceito ou recusado. É o que
        o harness lê da transcrição para gravar no Run: dois autores no mesmo
        Run mostram que o servidor MCP do subagente reiniciou no meio.
        """
        return {**self._assumir(argumentos), CAMPO_AUTOR: self._contexto.identidade.autor}

    def _assumir(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """A posse livre ou já nossa se adquire; a de outro só se retoma."""
        id_task = str(argumentos["id_task"])
        autor = self._contexto.identidade.autor
        ja_era_nosso = self._contexto.kernel.obter_dono_do_lock(id_task) == autor
        if not self._contexto.kernel.adquirir_lock_task(id_task, autor):
            return self._retomar_posse_orfa(id_task, argumentos)
        recibo = self._marcar_em_andamento(id_task, argumentos)
        if not recibo["sucesso"] and not ja_era_nosso:
            self._contexto.kernel.liberar_lock_task(id_task, autor)
        return recibo

    def _retomar_posse_orfa(self, id_task: str, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Passa ao executor a posse de uma tarefa que a revisão já aprovou.

        A posse é do autor da conexão, e o autor leva um sufixo aleatório por
        conexão. O executor cujo servidor MCP reinicia no meio da tarefa volta
        com outro nome e perde a própria posse; o executor que depois vem fechar
        a tarefa aprovada encontrava o lock de um autor que não existe mais, e
        só o humano o soltava. Com a revisão aprovada, o trabalho de quem
        detinha o lock acabou: o executor retoma a posse, e o lote que marca a
        tarefa diz de quem, na justificativa e na propriedade que fica no log.
        """
        kernel = self._contexto.kernel
        autor = self._contexto.identidade.autor
        dono = kernel.obter_dono_do_lock(id_task)
        if not dono or not self._pode_retomar(id_task, argumentos):
            return self._recusar_por_dono_atual(id_task)
        if not kernel.transferir_lock_task(id_task, dono, autor):
            return self._recusar_por_dono_atual(id_task)
        recibo = self._marcar_em_andamento(id_task, argumentos, retomada_de=dono)
        if not recibo["sucesso"]:
            kernel.transferir_lock_task(id_task, autor, dono)
            return recibo
        return {**recibo, CAMPO_POSSE_RETOMADA_DE: dono}

    def _pode_retomar(self, id_task: str, argumentos: Mapping[str, Any]) -> bool:
        """Só o executor retoma, porque fechar é dele, e só a tarefa cujo veredito vigente aprova."""
        if self._contexto.identidade.papel != PapelAutor.EXECUTOR:
            return False
        view = self._contexto.kernel.obter_view(extrair_ramo(dict(argumentos)))
        return veredito_vigente(view, id_task) == VEREDITO_APROVADO

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
        *,
        retomada_de: str = "",
    ) -> dict[str, Any]:
        """Registra no grafo que a tarefa passou a ter um responsável ativo.

        A justificativa não chega ao log; a retomada vai também como
        propriedade da Task, para quem lê o log saber de quem a posse saiu.
        """
        operacoes = [
            montar_operacao_definir_propriedade(id_task, "status", StatusTask.EM_ANDAMENTO.value),
            montar_operacao_definir_propriedade(id_task, "assumida_por", self._contexto.identidade.autor),
        ]
        justificativa = f"Posse da tarefa {id_task}"
        if retomada_de:
            operacoes.append(montar_operacao_definir_propriedade(id_task, CAMPO_POSSE_RETOMADA_DE, retomada_de))
            justificativa += f": posse orfa retomada de {retomada_de}: revisao aprovada"
        pedido = PedidoSubmissaoMCP(
            operacoes=tuple(operacoes),
            justificativa=justificativa,
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_task": id_task},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def liberar_tarefa(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Devolve o lock da Task, deixando o status como está.

        O humano devolve a posse de qualquer um, e o árbitro também quando a
        política do projeto lhe entrega `liberar_posse_alheia`. Um subagente que morre sem
        liberar deixa a tarefa presa a um autor que não volta mais. Se a
        revisão já aprovou a tarefa, o executor que vem fechá-la a retoma em
        `assumir_tarefa`; fora disso nenhum agente a tira dali, só o dono do
        grafo.
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
        """O dono atual do lock para quem pode liberar posse alheia; para os demais, o próprio autor.

        O humano pode sempre; o árbitro, quando a política do projeto da Task
        lhe entrega o gesto `liberar_posse_alheia`.
        """
        identidade = self._contexto.identidade
        dono = self._contexto.kernel.obter_dono_do_lock(id_task)
        if dono and self._pode_liberar_posse_alheia(id_task):
            return dono
        return identidade.autor

    def _pode_liberar_posse_alheia(self, id_task: str) -> bool:
        """Diz se o papel da sessão tem o gesto `liberar_posse_alheia` na política do projeto da Task."""
        papel = self._contexto.identidade.papel
        if papel == PapelAutor.HUMANO:
            return True
        if papel != PapelAutor.ARBITRO:
            return False
        estado = self._contexto.kernel.obter_estado()
        politica = resolver_politica_do_no(id_task, estado, RastreadorProjetoAncestral())
        return politica.permite(Gesto.LIBERAR_POSSE_ALHEIA, papel)
