"""Ferramentas MCP da camada de trabalho: tarefas, questões e patches livres."""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.core.types import StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.mcp.construcao_operacoes import (
    EspecificacaoAresta,
    EspecificacaoNo,
    gerar_identificador,
    montar_operacao_criar_aresta,
    montar_operacao_criar_no,
    montar_operacao_definir_propriedade,
)
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)


class FerramentasTrabalho:
    """Operações do agente sobre o grafo de intenção e execução."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de trabalho aos seus executores."""
        return {
            "criar_tarefa": self.criar_tarefa,
            "abrir_questao": self.abrir_questao,
            "responder_questao": self.responder_questao,
            "concluir_tarefa": self.concluir_tarefa,
            "propor_patch": self.propor_patch,
        }

    def criar_tarefa(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Cria uma Task com aresta 'produz' e hierarquias opcionais."""
        id_task = str(argumentos.get("id_task") or gerar_identificador("task"))
        titulo = str(argumentos["titulo"])
        operacoes = self._montar_operacoes_tarefa(id_task, titulo, argumentos)
        pedido = PedidoSubmissaoMCP(
            operacoes=operacoes,
            justificativa=f"Criacao de tarefa: {titulo}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_task": id_task},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _montar_operacoes_tarefa(
        self,
        id_task: str,
        titulo: str,
        argumentos: Mapping[str, Any],
    ) -> tuple[ItemPatch, ...]:
        """Monta a criação da Task, o vínculo com a Sessão e as arestas opcionais."""
        especificacao = EspecificacaoNo(
            id=id_task,
            tipo=TipoNo.TASK,
            rotulo=titulo,
            propriedades={
                "status": StatusTask.PENDENTE.value,
                "descricao": str(argumentos.get("descricao", "")),
                "criterio_pronto": str(argumentos.get("criterio_pronto", "")),
            },
        )
        producao = EspecificacaoAresta(
            id=f"prod-{id_task}",
            origem_id=str(argumentos["id_sessao"]),
            destino_id=id_task,
            tipo=TipoAresta.PRODUZ,
        )
        base = (montar_operacao_criar_no(especificacao), montar_operacao_criar_aresta(producao))
        return base + self._montar_arestas_opcionais_tarefa(id_task, argumentos)

    def _montar_arestas_opcionais_tarefa(
        self,
        id_task: str,
        argumentos: Mapping[str, Any],
    ) -> tuple[ItemPatch, ...]:
        """Monta as arestas de decomposição e dependência quando solicitadas."""
        operacoes: list[ItemPatch] = []
        id_pai = argumentos.get("id_tarefa_pai")
        if id_pai:
            decomposicao = EspecificacaoAresta(
                id=f"dec-{id_task}", origem_id=str(id_pai), destino_id=id_task, tipo=TipoAresta.DECOMPOE
            )
            operacoes.append(montar_operacao_criar_aresta(decomposicao))
        id_dependencia = argumentos.get("depende_de")
        if id_dependencia:
            dependencia = EspecificacaoAresta(
                id=f"dep-{id_task}", origem_id=id_task, destino_id=str(id_dependencia), tipo=TipoAresta.DEPENDE_DE
            )
            operacoes.append(montar_operacao_criar_aresta(dependencia))
        return tuple(operacoes)

    def abrir_questao(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Abre uma Question e a aresta 'bloqueia' que trava a tarefa até resposta humana."""
        id_questao = gerar_identificador("quest")
        pergunta = str(argumentos["pergunta"])
        operacoes = self._montar_operacoes_questao(id_questao, pergunta, argumentos)
        pedido = PedidoSubmissaoMCP(
            operacoes=operacoes,
            justificativa=f"Bloqueio por duvida: {pergunta}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_questao": id_questao},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _montar_operacoes_questao(
        self,
        id_questao: str,
        pergunta: str,
        argumentos: Mapping[str, Any],
    ) -> tuple[ItemPatch, ...]:
        """Monta a Question, o vínculo com a Sessão e o bloqueio da tarefa alvo."""
        producao = EspecificacaoAresta(
            id=f"produz-{id_questao}",
            origem_id=str(argumentos["id_sessao"]),
            destino_id=id_questao,
            tipo=TipoAresta.PRODUZ,
        )
        bloqueio = EspecificacaoAresta(
            id=f"bloq-{id_questao}",
            origem_id=id_questao,
            destino_id=str(argumentos["id_no_bloqueado"]),
            tipo=TipoAresta.BLOQUEIA,
        )
        return (
            montar_operacao_criar_no(self._especificar_questao(id_questao, pergunta)),
            montar_operacao_criar_aresta(producao),
            montar_operacao_criar_aresta(bloqueio),
        )

    def _especificar_questao(self, id_questao: str, pergunta: str) -> EspecificacaoNo:
        """Descreve o nó Question registrando quem o abriu e sob qual papel."""
        return EspecificacaoNo(
            id=id_questao,
            tipo=TipoNo.QUESTION,
            rotulo=pergunta,
            propriedades={
                "status": StatusQuestion.ABERTA.value,
                "aberta_por": self._contexto.identidade.autor,
                "papel_de_quem_abriu": self._contexto.identidade.papel.value,
            },
        )

    def responder_questao(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Registra a resposta humana e destrava a tarefa. Restrito a sessões humanas."""
        id_questao = str(argumentos["id_questao"])
        resposta = str(argumentos["resposta"])
        operacoes = (
            montar_operacao_definir_propriedade(id_questao, "status", StatusQuestion.RESPONDIDA.value),
            montar_operacao_definir_propriedade(id_questao, "resposta", resposta),
            montar_operacao_definir_propriedade(id_questao, "respondida_por", self._contexto.identidade.autor),
        )
        pedido = PedidoSubmissaoMCP(
            operacoes=operacoes,
            justificativa=f"Resposta a questao: {resposta}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_questao": id_questao},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def concluir_tarefa(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Transiciona a Task para concluído, se nenhuma Question aberta a bloquear."""
        id_task = str(argumentos["id_task"])
        justificativa = str(argumentos.get("justificativa", f"Conclusao da tarefa {id_task}"))
        pedido = PedidoSubmissaoMCP(
            operacoes=(montar_operacao_definir_propriedade(id_task, "status", StatusTask.CONCLUIDO.value),),
            justificativa=justificativa,
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_task": id_task},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def propor_patch(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Submete um lote livre de operações RFC 6902 aos quatro portões."""
        operacoes = tuple(self._converter_operacao(bruta) for bruta in argumentos.get("operacoes", []))
        pedido = PedidoSubmissaoMCP(
            operacoes=operacoes,
            justificativa=str(argumentos.get("justificativa", "")),
            ramo_id=extrair_ramo(dict(argumentos)),
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _converter_operacao(self, operacao_bruta: Mapping[str, Any]) -> ItemPatch:
        """Converte o dicionário recebido do agente em uma operação tipada."""
        return ItemPatch(
            op=OperacaoPatch(operacao_bruta["op"]),
            path=str(operacao_bruta["path"]),
            value=operacao_bruta.get("value"),
            from_path=operacao_bruta.get("from_path"),
        )
