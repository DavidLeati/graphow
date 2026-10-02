"""Ferramentas MCP da camada de navegação: Projeto, Setor e Sessão."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.governanca import (
    CHAVE_PERSONALIZADA,
    CHAVE_PRESET,
    ID_GOVERNANCA_GLOBAL,
    PROPRIEDADE_GOVERNANCA_DO_PROJETO,
    Gesto,
    PoliticaGovernanca,
    validar_configuracao_do_projeto,
    validar_configuracao_global,
)
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.kernel.politica_governanca import resolver_politica_do_projeto, resolver_politica_global
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
ESCOPO_GLOBAL: str = "global"
VALOR_HERDAR: str = "herdar"
ROTULO_DA_GOVERNANCA_GLOBAL: str = "Governanca global"


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
            "configurar_governanca": self.configurar_governanca,
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
        """Ajusta o `nivel_autonomia` de um projeto (legado de `configurar_governanca`). Restrito a sessões humanas."""
        id_projeto = str(argumentos["id_projeto"])
        nivel = str(argumentos["nivel_autonomia"])
        pedido = PedidoSubmissaoMCP(
            operacoes=(montar_operacao_definir_propriedade(id_projeto, "nivel_autonomia", nivel),),
            justificativa=f"Ajuste de autonomia para {nivel}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_projeto": id_projeto},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def configurar_governanca(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Grava a política de governança do escopo e devolve a política efetiva e a origem de cada gesto.

        Só o humano chega aqui. A `personalizada` recebida é mesclada na salva e
        nunca apagada ao trocar de preset; no Projeto, o valor 'herdar' apaga a
        sobrescrita do gesto.
        """
        escopo = str(argumentos["escopo"])
        ramo = extrair_ramo(dict(argumentos))
        estado = self._contexto.kernel.obter_estado(ramo)
        plano = (
            _planejar_global(argumentos, estado)
            if escopo == ESCOPO_GLOBAL
            else _planejar_projeto(escopo, argumentos, estado)
        )
        if isinstance(plano, str):
            return {"sucesso": False, "erro": plano}
        pedido = PedidoSubmissaoMCP(
            operacoes=plano,
            justificativa=f"Configuracao de governanca do escopo {escopo}",
            ramo_id=ramo,
            identificadores_criados={"escopo": escopo},
        )
        resposta = self._submissor.submeter_e_relatar(pedido)
        if resposta["sucesso"]:
            resposta.update(self._descrever_politica_efetiva(escopo, ramo))
        return resposta

    def _descrever_politica_efetiva(self, escopo: str, ramo: str) -> dict[str, Any]:
        """A política que vale no escopo depois da gravação, com a origem de cada gesto."""
        estado = self._contexto.kernel.obter_estado(ramo)
        if escopo == ESCOPO_GLOBAL:
            return _descrever_politica(resolver_politica_global(estado))
        politica = resolver_politica_do_projeto(escopo, estado)
        return _descrever_politica(politica)

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


def _descrever_politica(politica: PoliticaGovernanca) -> dict[str, Any]:
    """Política efetiva em forma serializável: o valor e a origem de cada gesto."""
    return {
        "politica_efetiva": {gesto.value: politica.valor(gesto) for gesto in Gesto},
        "origens": {gesto.value: politica.origem(gesto) for gesto in Gesto},
    }


def _planejar_global(
    argumentos: Mapping[str, Any],
    estado: GrafoEstado,
) -> tuple[ItemPatch, ...] | str:
    """As operações que gravam a política global, ou o texto da recusa."""
    recebida = _personalizada_recebida(argumentos)
    if isinstance(recebida, str):
        return recebida
    existente = estado.nos.get(ID_GOVERNANCA_GLOBAL)
    guardada = dict(existente.propriedades.get(CHAVE_PERSONALIZADA) or {}) if existente else {}
    configuracao = {CHAVE_PRESET: argumentos.get(CHAVE_PRESET), CHAVE_PERSONALIZADA: {**guardada, **recebida}}
    problemas = validar_configuracao_global(configuracao)
    if problemas:
        return _recusar_configuracao(problemas)
    if existente is None:
        no = EspecificacaoNo(
            id=ID_GOVERNANCA_GLOBAL,
            tipo=TipoNo.GOVERNANCA,
            rotulo=ROTULO_DA_GOVERNANCA_GLOBAL,
            propriedades=configuracao,
        )
        return (montar_operacao_criar_no(no),)
    return tuple(
        montar_operacao_definir_propriedade(ID_GOVERNANCA_GLOBAL, chave, valor) for chave, valor in configuracao.items()
    )


def _planejar_projeto(
    id_projeto: str,
    argumentos: Mapping[str, Any],
    estado: GrafoEstado,
) -> tuple[ItemPatch, ...] | str:
    """As operações que gravam a política do Projeto, ou o texto da recusa."""
    projeto = estado.nos.get(id_projeto)
    if projeto is None or projeto.tipo != TipoNo.PROJETO:
        return f"O escopo '{id_projeto}' nao e 'global' nem o id de um Projeto existente neste ramo"
    recebida = _personalizada_recebida(argumentos)
    if isinstance(recebida, str):
        return recebida
    declarada = projeto.propriedades.get(PROPRIEDADE_GOVERNANCA_DO_PROJETO)
    guardada = dict((declarada or {}).get(CHAVE_PERSONALIZADA) or {}) if isinstance(declarada, Mapping) else {}
    apagadas = {gesto for gesto, valor in recebida.items() if valor == VALOR_HERDAR}
    sobrescritas = {gesto: valor for gesto, valor in {**guardada, **recebida}.items() if gesto not in apagadas}
    problemas = _gestos_desconhecidos_a_herdar(apagadas)
    configuracao = {CHAVE_PRESET: argumentos.get(CHAVE_PRESET), CHAVE_PERSONALIZADA: sobrescritas}
    problemas += validar_configuracao_do_projeto(configuracao)
    if problemas:
        return _recusar_configuracao(problemas)
    return (montar_operacao_definir_propriedade(id_projeto, PROPRIEDADE_GOVERNANCA_DO_PROJETO, configuracao),)


def _gestos_desconhecidos_a_herdar(gestos: set[str]) -> list[str]:
    """Problemas de 'herdar' pedido para um gesto que não existe: apagar o que não existe seria silêncio."""
    conhecidos = {gesto.value for gesto in Gesto}
    return [f"gesto desconhecido {gesto!r}" for gesto in sorted(gestos) if gesto not in conhecidos]


def _personalizada_recebida(argumentos: Mapping[str, Any]) -> Mapping[str, Any] | str:
    """A `personalizada` declarada na chamada (ausente, vazia), ou o texto da recusa se não for um objeto."""
    recebida = argumentos.get(CHAVE_PERSONALIZADA)
    if recebida is None:
        return {}
    if isinstance(recebida, Mapping):
        return recebida
    return _recusar_configuracao(validar_configuracao_global({CHAVE_PERSONALIZADA: recebida}))


def _recusar_configuracao(problemas: list[str]) -> str:
    """O texto da recusa de uma configuração de governança inválida."""
    return "Configuracao de governanca invalida: " + "; ".join(problemas)
