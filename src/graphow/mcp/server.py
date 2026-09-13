"""Servidor de Protocolo MCP (Model Context Protocol) para interação com agentes."""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.context.materializer import MaterializadorContexto
from graphow.core.exceptions import GraphowError
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.ferramentas_escalacao import FerramentasEscalacao
from graphow.mcp.ferramentas_exclusao import FerramentasExclusao
from graphow.mcp.ferramentas_leitura import FerramentasLeitura
from graphow.mcp.ferramentas_navegacao import FerramentasNavegacao
from graphow.mcp.ferramentas_posse import FerramentasPosse
from graphow.mcp.ferramentas_trabalho import FerramentasTrabalho
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP, PoliticaIdentidadeMCP
from graphow.mcp.submissao import ContextoFerramentaMCP
from graphow.mcp.tool_definitions import DEFINICOES_FERRAMENTAS_MCP

ManipuladorFerramenta = Callable[[Mapping[str, Any]], dict[str, Any]]

# O papel do autor vem da sessão, nunca dos argumentos. Aceitar o campo em silêncio
# faria o agente crer que ele surte efeito; recusá-lo torna a garantia observável.
CAMPO_PAPEL_RECUSADO: str = "papel"


class GraphowMCPServer:
    """Servidor MCP que disponibiliza ferramentas para agentes IA lerem e mutarem o grafo."""

    def __init__(
        self,
        kernel: WriteKernel,
        identidade: IdentidadeSessaoMCP,
        materializador: MaterializadorContexto | None = None,
    ) -> None:
        self._identidade: IdentidadeSessaoMCP = identidade
        self._politica: PoliticaIdentidadeMCP = PoliticaIdentidadeMCP()
        contexto = ContextoFerramentaMCP(kernel=kernel, identidade=identidade)
        self._manipuladores: dict[str, ManipuladorFerramenta] = self._montar_manipuladores(
            contexto, materializador
        )

    def _montar_manipuladores(
        self,
        contexto: ContextoFerramentaMCP,
        materializador: MaterializadorContexto | None,
    ) -> dict[str, ManipuladorFerramenta]:
        """Agrega os manipuladores de todos os grupos de ferramentas disponíveis."""
        grupos = (
            FerramentasLeitura(contexto, materializador).obter_manipuladores(),
            FerramentasNavegacao(contexto).obter_manipuladores(),
            FerramentasTrabalho(contexto).obter_manipuladores(),
            FerramentasPosse(contexto).obter_manipuladores(),
            FerramentasEscalacao(contexto).obter_manipuladores(),
            FerramentasExclusao(contexto).obter_manipuladores(),
        )
        agregado: dict[str, ManipuladorFerramenta] = {}
        for grupo in grupos:
            agregado.update(grupo)
        return agregado

    @property
    def identidade(self) -> IdentidadeSessaoMCP:
        """Identidade imutável sob a qual esta sessão opera."""
        return self._identidade

    def listar_ferramentas(self) -> list[dict[str, Any]]:
        """Retorna os metadados de todas as ferramentas MCP disponíveis."""
        return list(DEFINICOES_FERRAMENTAS_MCP)

    def executar_ferramenta(self, nome_ferramenta: str, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Executa a ferramenta MCP sob a identidade da sessão e retorna resposta estruturada."""
        recusa = self._recusar_se_invalida(nome_ferramenta, argumentos)
        if recusa is not None:
            return recusa
        return self._executar_manipulador(self._manipuladores[nome_ferramenta], nome_ferramenta, argumentos)

    def _recusar_se_invalida(
        self,
        nome_ferramenta: str,
        argumentos: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Aplica as recusas anteriores à execução: ferramenta, papel declarado e autorização."""
        if nome_ferramenta not in self._manipuladores:
            return {"sucesso": False, "erro": f"Ferramenta desconhecida: '{nome_ferramenta}'"}
        if CAMPO_PAPEL_RECUSADO in argumentos:
            return {
                "sucesso": False,
                "erro": (
                    "O campo 'papel' nao e aceito. O papel desta sessao e "
                    f"'{self._identidade.papel.value}' e foi fixado na abertura do servidor."
                ),
            }
        autorizacao = self._politica.autorizar(nome_ferramenta, self._identidade)
        if not autorizacao.autorizado:
            return {"sucesso": False, "erro": autorizacao.motivo}
        return None

    def _executar_manipulador(
        self,
        manipulador: ManipuladorFerramenta,
        nome_ferramenta: str,
        argumentos: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Invoca o manipulador convertendo falhas conhecidas em respostas estruturadas."""
        try:
            return manipulador(argumentos)
        except GraphowError as erro:
            return {"sucesso": False, "erro": erro.formatar_para_llm()}
        except KeyError as erro:
            return {"sucesso": False, "erro": f"Argumento obrigatorio ausente em '{nome_ferramenta}': {erro}"}
        except ValueError as erro:
            return {"sucesso": False, "erro": f"Argumento invalido em '{nome_ferramenta}': {erro}"}
