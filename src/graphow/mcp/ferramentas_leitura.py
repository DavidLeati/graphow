"""Ferramentas MCP de leitura e inspeção do grafo, sem efeitos colaterais."""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.types import TipoNo
from graphow.mcp.submissao import ContextoFerramentaMCP, extrair_ramo
from graphow.projection.fila_trabalho import FilaDeTrabalho
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import LIMITE_PADRAO_DE_RESULTADOS, CriterioBusca
from graphow.projection.working_set import RAIO_PADRAO, EscopoAtivo

ORCAMENTO_TOKENS_PADRAO: int = 1500
ESCOPO_ATIVO: str = "ativo"


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
            escopo_ativo=self._pediu_escopo_ativo(argumentos),
            raio_do_escopo=int(argumentos.get("raio_do_escopo", RAIO_PADRAO)),
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
        """Pesquisa textual ranqueada, cortada no limite e sempre com o total.

        O corte só existe porque há ranking: cortar uma lista sem ordem devolveria
        resultados arbitrários, e o agente perderia o que procurava sem ficar
        sabendo. `total` e `truncado` dizem quando vale a pena refinar o termo.
        """
        view = self._contexto.kernel.obter_view(extrair_ramo(dict(argumentos)))
        tipos, invalidos = self._converter_tipos(argumentos.get("tipos_no"))
        if invalidos:
            return {"sucesso": False, "mensagem": f"Tipos de no desconhecidos: {', '.join(invalidos)}"}
        criterio = CriterioBusca(
            termo=str(argumentos["termo"]),
            tipos=tipos,
            limite=int(argumentos.get("limite", LIMITE_PADRAO_DE_RESULTADOS)),
        )
        resultado = view.buscar_ranqueado(criterio, self._resolver_escopo(argumentos, view))
        return {"sucesso": True, **resultado.em_dicionario()}

    def _pediu_escopo_ativo(self, argumentos: Mapping[str, Any]) -> bool:
        """O escopo ativo é opção do chamador; o padrão do agente é ver tudo."""
        return str(argumentos.get("escopo", "")).strip().lower() == ESCOPO_ATIVO

    def _resolver_escopo(self, argumentos: Mapping[str, Any], view: GrafoView) -> EscopoAtivo | None:
        """Calcula o recorte ativo apenas quando a chamada pediu por ele."""
        if not self._pediu_escopo_ativo(argumentos):
            return None
        return view.calcular_escopo_ativo(int(argumentos.get("raio_do_escopo", RAIO_PADRAO)))

    def _converter_tipos(self, tipos_recebidos: object) -> tuple[tuple[TipoNo, ...], tuple[str, ...]]:
        """Converte a lista textual em membros da ontologia, separando os inválidos.

        Antes, um tipo desconhecido levantava `ValueError` cru e a ferramenta
        respondia com um erro de servidor em vez de dizer o que estava errado.
        """
        if not isinstance(tipos_recebidos, (list, tuple)) or not tipos_recebidos:
            return ((), ())
        convertidos: list[TipoNo] = []
        invalidos: list[str] = []
        for bruto in tipos_recebidos:
            self._acumular_tipo(str(bruto), convertidos, invalidos)
        return (tuple(convertidos), tuple(invalidos))

    def _acumular_tipo(self, bruto: str, aceitos: list[TipoNo], invalidos: list[str]) -> None:
        """Classifica um tipo textual entre aceito pela ontologia e desconhecido."""
        try:
            aceitos.append(TipoNo(bruto.strip().capitalize()))
        except ValueError:
            invalidos.append(bruto)
