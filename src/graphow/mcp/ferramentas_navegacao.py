"""Ferramentas MCP da camada de navegação: Projeto, Setor e Sessão."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
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

NIVEL_AUTONOMIA_PADRAO: str = "estrito"


@dataclass(frozen=True)
class PedidoContainerFilho:
    """Parâmetros de criação de um contêiner subordinado a outro na hierarquia."""

    id_filho: str
    tipo_filho: TipoNo
    id_pai: str
    rotulo: str


class FerramentasNavegacao:
    """Criação dos contêineres hierárquicos que organizam o grafo de trabalho."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de navegação aos seus executores."""
        return {
            "criar_projeto": self.criar_projeto,
            "criar_setor": self.criar_setor,
            "criar_sessao": self.criar_sessao,
            "configurar_autonomia_projeto": self.configurar_autonomia_projeto,
        }

    def criar_projeto(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Cria o nó Projeto raiz definindo o nível de autonomia dos agentes."""
        id_projeto = str(argumentos.get("id_projeto") or gerar_identificador("proj"))
        rotulo = str(argumentos["rotulo"])
        especificacao = EspecificacaoNo(
            id=id_projeto,
            tipo=TipoNo.PROJETO,
            rotulo=rotulo,
            propriedades={
                "nivel_autonomia": str(argumentos.get("nivel_autonomia", NIVEL_AUTONOMIA_PADRAO)),
                "descricao": str(argumentos.get("descricao", "")),
            },
        )
        pedido = PedidoSubmissaoMCP(
            operacoes=(montar_operacao_criar_no(especificacao),),
            justificativa=f"Criacao de projeto: {rotulo}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_projeto": id_projeto},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def criar_setor(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Cria o Setor e a aresta de contenção que o liga ao Projeto."""
        id_setor = str(argumentos.get("id_setor") or gerar_identificador("setor"))
        pedido_container = PedidoContainerFilho(
            id_filho=id_setor,
            tipo_filho=TipoNo.SETOR,
            id_pai=str(argumentos["id_projeto"]),
            rotulo=str(argumentos["rotulo"]),
        )
        pedido = PedidoSubmissaoMCP(
            operacoes=self._montar_operacoes_container(pedido_container),
            justificativa=f"Criacao de setor: {pedido_container.rotulo}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_setor": id_setor},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def criar_sessao(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Cria a Sessão e a aresta de contenção que a liga ao Setor."""
        id_sessao = str(argumentos.get("id_sessao") or gerar_identificador("sess"))
        pedido_container = PedidoContainerFilho(
            id_filho=id_sessao,
            tipo_filho=TipoNo.SESSAO,
            id_pai=str(argumentos["id_setor"]),
            rotulo=str(argumentos["rotulo"]),
        )
        pedido = PedidoSubmissaoMCP(
            operacoes=self._montar_operacoes_container(pedido_container),
            justificativa=f"Criacao de sessao: {pedido_container.rotulo}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_sessao": id_sessao},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def configurar_autonomia_projeto(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Ajusta o nível de autonomia de um projeto. Restrito a sessões humanas."""
        id_projeto = str(argumentos["id_projeto"])
        nivel = str(argumentos["nivel_autonomia"])
        pedido = PedidoSubmissaoMCP(
            operacoes=(montar_operacao_definir_propriedade(id_projeto, "nivel_autonomia", nivel),),
            justificativa=f"Ajuste de autonomia para {nivel}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_projeto": id_projeto},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _montar_operacoes_container(self, pedido: PedidoContainerFilho) -> tuple[ItemPatch, ...]:
        """Monta a criação do contêiner e a aresta 'contem' vinda do pai."""
        especificacao_no = EspecificacaoNo(id=pedido.id_filho, tipo=pedido.tipo_filho, rotulo=pedido.rotulo)
        especificacao_aresta = EspecificacaoAresta(
            id=f"contem-{pedido.id_filho}",
            origem_id=pedido.id_pai,
            destino_id=pedido.id_filho,
            tipo=TipoAresta.CONTEM,
        )
        return (
            montar_operacao_criar_no(especificacao_no),
            montar_operacao_criar_aresta(especificacao_aresta),
        )
