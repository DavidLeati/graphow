"""Ferramentas MCP da memória em camadas: encerrar a sessão, registrar e promover aprendizados.

Encerrar a sessão é o gesto que separa a memória de curto prazo da de longo
prazo: é dele que o fechamento determinístico passa a abrir a vista e que o
motor reativo pede a condensação. Registrar um aprendizado é destilar o que
sobrevive ao projeto, com a origem obrigatória. Promover é dar-lhe alcance, e
isso fica com o humano. Consolidar é registrar com `substitui`: um aprendizado
que absorve vários, com a aresta para cada absorvido no mesmo lote; o absorvido
só sai da vista quando o humano promove o consolidado.
"""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.context.memoria import ALCANCE_GLOBAL, CAMPO_ALCANCE, CAMPO_COMO_APLICAR, ja_vale_para
from graphow.core.types import StatusSessao, TipoAresta, TipoNo
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

CAMPO_RESUMO: str = "resumo"
CAMPO_ORIGENS: str = "origens"
CAMPO_SUBSTITUI: str = "substitui"


class FerramentasMemoria:
    """Operações que movem conhecimento entre as camadas de memória do grafo."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de memória aos seus executores."""
        return {
            "encerrar_sessao": self.encerrar_sessao,
            "registrar_aprendizado": self.registrar_aprendizado,
            "promover_aprendizado": self.promover_aprendizado,
        }

    def encerrar_sessao(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Fecha a Sessao e devolve o fechamento que a vista dela passa a abrir."""
        id_sessao = str(argumentos["id_sessao"])
        ramo = extrair_ramo(dict(argumentos))
        sessao = self._contexto.kernel.obter_view(ramo).obter_no(id_sessao)
        if sessao is None or sessao.tipo != TipoNo.SESSAO:
            return {"sucesso": False, "erro": f"Sessao '{id_sessao}' nao existe neste ramo"}
        pedido = PedidoSubmissaoMCP(
            operacoes=self._operacoes_de_encerramento(id_sessao, argumentos),
            justificativa=f"Encerramento da sessao {id_sessao}",
            ramo_id=ramo,
            identificadores_criados={"id_sessao": id_sessao},
        )
        resposta = self._submissor.submeter_e_relatar(pedido)
        if resposta["sucesso"]:
            resposta["fechamento"] = self._descrever_fechamento(id_sessao, ramo)
        return resposta

    def _operacoes_de_encerramento(self, id_sessao: str, argumentos: Mapping[str, Any]) -> tuple[ItemPatch, ...]:
        """Status concluida e, quando declarado, o resumo de quem encerra."""
        operacoes = [montar_operacao_definir_propriedade(id_sessao, "status", StatusSessao.CONCLUIDA.value)]
        resumo = str(argumentos.get(CAMPO_RESUMO, "") or "").strip()
        if resumo:
            operacoes.append(montar_operacao_definir_propriedade(id_sessao, CAMPO_RESUMO, resumo))
        return tuple(operacoes)

    def _descrever_fechamento(self, id_sessao: str, ramo: str) -> dict[str, object]:
        """O esqueleto determinístico da sessão recém-fechada, para quem encerrou conferir."""
        resumo = self._contexto.kernel.obter_view(ramo).obter_resumo(id_sessao)
        if resumo is None:
            return {}
        return resumo.fechamento.em_dicionario()

    def registrar_aprendizado(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Cria o Aprendizado pendurado na sessão, derivado de cada origem e substituindo os que consolida."""
        afirmacao = str(argumentos["afirmacao"]).strip()
        origens = self._origens_declaradas(argumentos)
        if not afirmacao or not origens:
            return {
                "sucesso": False,
                "erro": "Um aprendizado precisa de 'afirmacao' e de ao menos uma origem em "
                "'origens': os ids dos nos de onde ele saiu",
            }
        id_aprendizado = str(argumentos.get("id_aprendizado") or gerar_identificador("apr"))
        pedido = PedidoSubmissaoMCP(
            operacoes=self._operacoes_de_registro(id_aprendizado, argumentos, origens),
            justificativa=f"Registro de aprendizado: {afirmacao}",
            ramo_id=extrair_ramo(dict(argumentos)),
            identificadores_criados={"id_aprendizado": id_aprendizado},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _origens_declaradas(self, argumentos: Mapping[str, Any]) -> tuple[str, ...]:
        """Ids de origem informados, sem vazios e sem repetição, na ordem declarada."""
        return self._ids_declarados(argumentos, CAMPO_ORIGENS)

    def _ids_declarados(self, argumentos: Mapping[str, Any], campo: str) -> tuple[str, ...]:
        """Ids informados no campo, sem vazios e sem repetição, na ordem declarada."""
        brutos = argumentos.get(campo, [])
        if not isinstance(brutos, (list, tuple)):
            return ()
        return tuple(dict.fromkeys(str(item).strip() for item in brutos if str(item).strip()))

    def _operacoes_de_registro(
        self,
        id_aprendizado: str,
        argumentos: Mapping[str, Any],
        origens: tuple[str, ...],
    ) -> tuple[ItemPatch, ...]:
        """O nó, o vínculo com a sessão, uma aresta de origem por nó de onde saiu e uma de substituição por absorvido."""
        especificacao = EspecificacaoNo(
            id=id_aprendizado,
            tipo=TipoNo.APRENDIZADO,
            rotulo=str(argumentos["afirmacao"]).strip(),
            propriedades={CAMPO_COMO_APLICAR: str(argumentos.get(CAMPO_COMO_APLICAR, "") or "").strip()},
        )
        producao = EspecificacaoAresta(
            id=f"prod-{id_aprendizado}",
            origem_id=str(argumentos["id_sessao"]),
            destino_id=id_aprendizado,
            tipo=TipoAresta.PRODUZ,
        )
        cabeca = (montar_operacao_criar_no(especificacao), montar_operacao_criar_aresta(producao))
        absorvidos = self._ids_declarados(argumentos, CAMPO_SUBSTITUI)
        return cabeca + self._derivacoes(id_aprendizado, origens) + self._substituicoes(id_aprendizado, absorvidos)

    def _derivacoes(self, id_aprendizado: str, origens: tuple[str, ...]) -> tuple[ItemPatch, ...]:
        """Uma aresta `deriva_de` por origem: é o que o InvariantGate exige no mesmo lote."""
        return tuple(
            montar_operacao_criar_aresta(
                EspecificacaoAresta(
                    id=f"deriv-{id_aprendizado}-{origem}",
                    origem_id=id_aprendizado,
                    destino_id=origem,
                    tipo=TipoAresta.DERIVA_DE,
                )
            )
            for origem in origens
        )

    def _substituicoes(self, id_aprendizado: str, absorvidos: tuple[str, ...]) -> tuple[ItemPatch, ...]:
        """Uma aresta `substitui` por absorvido: a consolidação, que só vale na vista quando o humano promover."""
        return tuple(
            montar_operacao_criar_aresta(
                EspecificacaoAresta(
                    id=f"subst-{id_aprendizado}-{antigo}",
                    origem_id=id_aprendizado,
                    destino_id=antigo,
                    tipo=TipoAresta.SUBSTITUI,
                )
            )
            for antigo in absorvidos
        )

    def promover_aprendizado(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Dá alcance ao Aprendizado: `vale_para` um Projeto ou Setor, ou a marca global."""
        id_aprendizado = str(argumentos["id_aprendizado"])
        id_alvo = str(argumentos.get("id_alvo", "") or "").strip()
        eh_global = bool(argumentos.get("global", False))
        if not id_alvo and not eh_global:
            return {"sucesso": False, "erro": "Informe 'id_alvo' (um Projeto ou Setor) ou 'global': true"}
        ramo = extrair_ramo(dict(argumentos))
        if id_alvo and ja_vale_para(id_aprendizado, id_alvo, self._contexto.kernel.obter_view(ramo)):
            id_alvo = ""
        pedido = PedidoSubmissaoMCP(
            operacoes=self._operacoes_de_promocao(id_aprendizado, id_alvo, eh_global),
            justificativa=f"Promocao do aprendizado {id_aprendizado}",
            ramo_id=ramo,
            identificadores_criados={"id_aprendizado": id_aprendizado},
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _operacoes_de_promocao(self, id_aprendizado: str, id_alvo: str, eh_global: bool) -> tuple[ItemPatch, ...]:
        """A marca global como propriedade e o alcance por contêiner como aresta."""
        operacoes: list[ItemPatch] = []
        if eh_global:
            operacoes.append(montar_operacao_definir_propriedade(id_aprendizado, CAMPO_ALCANCE, ALCANCE_GLOBAL))
        if id_alvo:
            alcance = EspecificacaoAresta(
                id=f"vale-{id_aprendizado}-{id_alvo}",
                origem_id=id_aprendizado,
                destino_id=id_alvo,
                tipo=TipoAresta.VALE_PARA,
            )
            operacoes.append(montar_operacao_criar_aresta(alcance))
        return tuple(operacoes)
