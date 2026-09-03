"""Ferramentas MCP de leitura e inspeção do grafo, sem efeitos colaterais."""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.mcp.submissao import ContextoFerramentaMCP, extrair_ramo
from graphow.projection.fila_trabalho import FilaDeTrabalho

ORCAMENTO_TOKENS_PADRAO: int = 1500


class FerramentasLeitura:
    """Consultas do agente sobre o grafo, materializadas sob orçamento de tokens."""

    def __init__(
        self,
        contexto: ContextoFerramentaMCP,
        materializador: MaterializadorContexto | None = None,
    ) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de leitura aos seus executores."""
        return {
            "ler_vista": self.ler_vista,
            "expandir_no": self.expandir_no,
            "buscar": self.buscar,
            "proximas_tarefas": self.proximas_tarefas,
        }

    def proximas_tarefas(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Devolve as tarefas executáveis da sessão, em ordem estável de atendimento."""
        ramo = extrair_ramo(dict(argumentos))
        fila = FilaDeTrabalho(
            self._contexto.kernel.obter_view(ramo),
            self._contexto.kernel.listar_locks_ativos(),
        )
        id_sessao = str(argumentos["id_sessao"])
        tarefas = fila.proximas_tarefas(id_sessao)
        return {
            "sucesso": True,
            "total": len(tarefas),
            "tarefas": [tarefa.em_dicionario() for tarefa in tarefas],
            "impedidas": [impedida.em_dicionario() for impedida in fila.tarefas_impedidas(id_sessao)],
        }

    def ler_vista(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Materializa o subgrafo focal usando a política do papel da sessão."""
        requisicao = RequisicaoVista(
            id_alvo=str(argumentos["id_alvo"]),
            papel=self._contexto.identidade.papel,
            orcamento_tokens=int(argumentos.get("orcamento_tokens", ORCAMENTO_TOKENS_PADRAO)),
        )
        view = self._contexto.kernel.obter_view(extrair_ramo(dict(argumentos)))
        vista = self._materializador.materializar(requisicao, view)
        return {
            "sucesso": True,
            "conteudo": vista.conteudo_formatado,
            "tokens_estimados": vista.tokens_estimados,
            "orcamento": vista.orcamento_tokens,
            "vizinhos_expansiveis": list(vista.vizinhos_expansiveis),
        }

    def expandir_no(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Devolve a ficha completa de um nó específico e suas arestas incidentes."""
        view = self._contexto.kernel.obter_view(extrair_ramo(dict(argumentos)))
        detalhes = self._materializador.expandir_no(str(argumentos["id_no"]), view)
        return {"sucesso": True, "detalhes": detalhes}

    def buscar(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Pesquisa textual sobre rótulos e propriedades, filtrada por tipos da ontologia."""
        view = self._contexto.kernel.obter_view(extrair_ramo(dict(argumentos)))
        encontrados = view.buscar_nos(str(argumentos["termo"]), self._converter_tipos(argumentos.get("tipos_no")))
        return {
            "sucesso": True,
            "total": len(encontrados),
            "resultados": [self._resumir(no) for no in encontrados],
        }

    def _resumir(self, no: NoGrafo) -> dict[str, Any]:
        """Linha de resultado com a posição no log, para o agente ordenar o que achou.

        Sem `seq_criacao` a busca devolvia um conjunto sem ordem alguma: nada ali
        dizia qual nó veio antes de qual.
        """
        return {
            "id": no.id,
            "tipo": no.tipo.value,
            "rotulo": no.rotulo,
            "seq_criacao": no.ordem.seq_criacao,
        }

    def _converter_tipos(self, tipos_recebidos: object) -> list[TipoNo] | None:
        """Converte a lista textual de tipos em membros da ontologia, ou None."""
        if not isinstance(tipos_recebidos, (list, tuple)) or not tipos_recebidos:
            return None
        return [TipoNo(str(tipo).strip().capitalize()) for tipo in tipos_recebidos]
