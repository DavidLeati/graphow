"""Portão 2: Validação de Contratos de Permissão por Papel (Role Gate).

O portão avalia três superfícies, não uma: a criação de nós, a edição e remoção
de nós, e a camada de arestas — que antes retornava sucesso para qualquer papel
e deixava um executor reescopar a própria tarefa. Ver achados A-01 a A-03.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import NivelAutonomiaProjeto, PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import (
    STATUS_DE_QUESTION_RESERVADOS_AO_HUMANO,
    TIPOS_CUJA_REMOCAO_EXIGE_HUMANO,
    TIPOS_EDITAVEIS_PELO_SISTEMA,
    TIPOS_EXCLUSIVOS_DO_HUMANO,
    DonosDeAresta,
    obter_donos_de_aresta,
    obter_donos_sob_autonomia_ilimitada,
)
from graphow.kernel.patch_models import (
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral, projetar_lote

SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2


@dataclass(frozen=True)
class ContextoPapel:
    """Estado compartilhado por todas as verificações de uma mesma proposta.

    `estado_com_lote` inclui os nós e arestas que o próprio lote cria: é o que
    permite resolver o projeto ancestral de uma Sessao recém-criada pela aresta
    `contem` que veio junto, em vez de por chaves dentro do valor do nó (A-05).
    """

    proposta: PropostaPatch
    estado: GrafoEstado
    estado_com_lote: GrafoEstado


@dataclass(frozen=True)
class ContextoPermissaoEdicao:
    """DTO imutável para parâmetros de validação de permissão de edição."""

    segmentos: Sequence[str]
    item: ItemPatch
    contexto: ContextoPapel


class RoleGate:
    """Portão que impõe as regras de permissão de escrita conforme o papel do autor.

    Um projeto com autonomia ilimitada amplia os tipos de nó que um agente pode
    criar, mas nunca dispensa as invariantes duras: apenas o humano governa
    `Constraint`, encerra uma `Question` e estrutura a camada de navegação.
    """

    NOS_CRIACAO_PERMITIDOS: dict[PapelAutor, frozenset[TipoNo]] = {
        PapelAutor.HUMANO: frozenset(TipoNo),
        PapelAutor.PLANEJADOR: frozenset({TipoNo.TASK, TipoNo.DECISION, TipoNo.QUESTION, TipoNo.NOTE}),
        PapelAutor.EXECUTOR: frozenset(
            {TipoNo.ARTIFACT, TipoNo.EVIDENCE, TipoNo.DECISION, TipoNo.QUESTION, TipoNo.NOTE}
        ),
        PapelAutor.REVISOR: frozenset({TipoNo.EVIDENCE, TipoNo.QUESTION, TipoNo.NOTE}),
        # O harness registra a sessao em que roda e a propria telemetria; nada do
        # grafo de trabalho. Ver harness/identidade_harness.py.
        PapelAutor.SISTEMA: frozenset({TipoNo.RUN, TipoNo.SESSAO}),
    }

    # Sob autonomia ilimitada o agente ganha a camada de navegação e os nós de
    # trabalho, jamais os tipos reservados ao humano.
    NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA: frozenset[TipoNo] = frozenset(TipoNo) - TIPOS_EXCLUSIVOS_DO_HUMANO

    def __init__(self, rastreador: RastreadorProjetoAncestral | None = None) -> None:
        self._rastreador: RastreadorProjetoAncestral = rastreador or RastreadorProjetoAncestral()

    def validar(self, proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
        """Avalia se todas as operações da proposta estão autorizadas para o papel."""
        if proposta.papel == PapelAutor.HUMANO:
            return ResultadoValidacao.sucesso()
        contexto = ContextoPapel(
            proposta=proposta,
            estado=estado,
            estado_com_lote=projetar_lote(proposta.operacoes, estado),
        )
        for item in proposta.operacoes:
            resultado_item = self._validar_permissao_item(item, contexto)
            if not resultado_item.aprovado:
                return resultado_item
        return ResultadoValidacao.sucesso()

    def _validar_permissao_item(self, item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao:
        """Verifica a permissão de um item específico de patch."""
        segmentos: list[str] = [seg for seg in item.path.split("/") if seg]
        if not segmentos:
            return ResultadoValidacao.sucesso()
        if segmentos[0] == "arestas":
            return self._validar_permissao_aresta(segmentos, item, contexto)
        if segmentos[0] != "nos":
            return ResultadoValidacao.sucesso()
        if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO and item.op == OperacaoPatch.ADD:
            return self._validar_permissao_criacao_no(item, contexto)
        ctx = ContextoPermissaoEdicao(segmentos=tuple(segmentos), item=item, contexto=contexto)
        return self._validar_permissao_edicao_no(ctx)

    def _validar_permissao_aresta(
        self,
        segmentos: Sequence[str],
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> ResultadoValidacao:
        """Consulta a matriz de donos de aresta para a operação e o papel correntes."""
        tipo = self._identificar_tipo_de_aresta(segmentos, item, contexto.estado)
        if tipo is None:
            return ResultadoValidacao.sucesso()
        eh_remocao = item.op == OperacaoPatch.REMOVE
        donos = self._donos_aplicaveis(tipo, item, contexto)
        if donos.autoriza(contexto.proposta.papel, eh_remocao):
            return ResultadoValidacao.sucesso()
        return self._recusar_aresta(tipo, contexto.proposta.papel, eh_remocao)

    def _donos_aplicaveis(
        self,
        tipo: TipoAresta,
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> DonosDeAresta:
        """Amplia os donos quando a aresta pertence a um projeto autônomo.

        Sem isto a autonomia ilimitada voltaria a ser inerte por outro
        caminho: o agente criaria o nó Setor e seria barrado na aresta
        `contem` que o prende ao Projeto. Ver achado A-05.
        """
        if not self._aresta_sob_autonomia_ilimitada(item, contexto):
            return obter_donos_de_aresta(tipo)
        return obter_donos_sob_autonomia_ilimitada(tipo)

    def _aresta_sob_autonomia_ilimitada(
        self,
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> bool:
        """Rastreia o projeto a partir das duas pontas declaradas da aresta."""
        for id_ponta in self._pontas_da_aresta(item):
            projeto = self._rastreador.rastrear(id_ponta, contexto.estado_com_lote)
            if projeto is not None and self._projeto_eh_ilimitado(projeto, contexto.estado_com_lote):
                return True
        return False

    def _pontas_da_aresta(self, item: ItemPatch) -> tuple[str, ...]:
        """Identificadores de origem e destino declarados no valor da aresta."""
        if not isinstance(item.value, dict):
            return ()
        pontas = (item.value.get("origem_id"), item.value.get("destino_id"))
        return tuple(str(ponta) for ponta in pontas if ponta)

    def _recusar_aresta(
        self,
        tipo: TipoAresta,
        papel: PapelAutor,
        eh_remocao: bool,
    ) -> ResultadoValidacao:
        """Explica ao agente quem detém a aresta que ele tentou mexer."""
        verbo = "remover" if eh_remocao else "criar"
        donos = obter_donos_de_aresta(tipo)
        autorizados = sorted(p.value for p in (donos.remocao if eh_remocao else donos.adicao))
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' não pode {verbo} aresta '{tipo.value}'",
            "RoleGate",
            {"tipo_aresta": tipo.value, "papeis_autorizados": ", ".join(autorizados)},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _identificar_tipo_de_aresta(
        self,
        segmentos: Sequence[str],
        item: ItemPatch,
        estado: GrafoEstado,
    ) -> TipoAresta | None:
        """Lê o tipo do valor proposto ou, na remoção, da aresta já projetada."""
        declarado = item.value.get("tipo") if isinstance(item.value, dict) else None
        if declarado is not None:
            return self._converter_tipo_de_aresta(declarado)
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO:
            return None
        aresta = estado.arestas.get(segmentos[1])
        return aresta.tipo if aresta is not None else None

    def _converter_tipo_de_aresta(self, declarado: Any) -> TipoAresta | None:
        """Converte o tipo textual, deixando a forma inválida para o SchemaGate."""
        try:
            return TipoAresta(declarado)
        except ValueError:
            return None

    def _validar_permissao_criacao_no(
        self,
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> ResultadoValidacao:
        """Valida se o papel pode criar o tipo de nó especificado no destino."""
        if not isinstance(item.value, dict) or "tipo" not in item.value:
            return ResultadoValidacao.falha(
                "Nó inválido para validação de papel",
                "RoleGate",
                modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
            )
        tipo_no = TipoNo(item.value["tipo"])
        if tipo_no in self._tipos_permitidos_para(item, contexto):
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Papel '{contexto.proposta.papel.value}' não possui permissão para criar nó do tipo '{tipo_no.value}'",
            "RoleGate",
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _tipos_permitidos_para(self, item: ItemPatch, contexto: ContextoPapel) -> frozenset[TipoNo]:
        """Determina o conjunto de tipos criáveis, considerando a autonomia do projeto."""
        base = self.NOS_CRIACAO_PERMITIDOS.get(contexto.proposta.papel, frozenset())
        if not self._opera_sob_autonomia_ilimitada(item, contexto):
            return base
        return base | self.NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA

    def _opera_sob_autonomia_ilimitada(self, item: ItemPatch, contexto: ContextoPapel) -> bool:
        """Verifica se a operação recai sob um projeto marcado como autônomo."""
        id_alvo = self._identificar_alvo_do_item(item)
        if id_alvo is None:
            return False
        projeto = self._rastreador.rastrear(id_alvo, contexto.estado_com_lote)
        return projeto is not None and self._projeto_eh_ilimitado(projeto, contexto.estado_com_lote)

    def _identificar_alvo_do_item(self, item: ItemPatch) -> str | None:
        """Extrai o identificador do nó que a operação cria, a partir do caminho."""
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO:
            return None
        return segmentos[1]

    def _projeto_eh_ilimitado(self, projeto_id: str, estado: GrafoEstado) -> bool:
        """Checa se o nó de projeto possui configuração de autonomia ilimitada."""
        projeto = estado.nos.get(projeto_id)
        if projeto is None or projeto.tipo != TipoNo.PROJETO:
            return False
        nivel = str(projeto.propriedades.get("nivel_autonomia", "")).lower()
        return nivel == NivelAutonomiaProjeto.ILIMITADO.value

    def _validar_permissao_edicao_no(self, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Valida se o papel pode editar ou remover campos específicos do nó."""
        papel = ctx.contexto.proposta.papel
        no_existente = ctx.contexto.estado.nos.get(ctx.segmentos[1])
        if no_existente is None:
            return ResultadoValidacao.sucesso()
        if no_existente.tipo in TIPOS_EXCLUSIVOS_DO_HUMANO:
            return ResultadoValidacao.falha(
                f"Papel '{papel.value}' não pode alterar nós de '{no_existente.tipo.value}'",
                "RoleGate",
                modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
            )
        resultado_remocao = self._validar_remocao_de_no(no_existente, ctx)
        if not resultado_remocao.aprovado:
            return resultado_remocao
        return self._validar_regras_especificas_papel(no_existente, ctx.item, papel)

    def _validar_remocao_de_no(
        self,
        no: NoGrafo,
        ctx: ContextoPermissaoEdicao,
    ) -> ResultadoValidacao:
        """Impede que um agente apague o nó que registra a escalação ao humano."""
        eh_remocao_inteira = (
            ctx.item.op == OperacaoPatch.REMOVE
            and len(ctx.segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO
        )
        if not eh_remocao_inteira or no.tipo not in TIPOS_CUJA_REMOCAO_EXIGE_HUMANO:
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Papel '{ctx.contexto.proposta.papel.value}' não pode remover nós de '{no.tipo.value}'. "
            "Somente uma sessao humana encerra uma escalacao",
            "RoleGate",
            {"id_no": no.id, "tipo": no.tipo.value},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _validar_regras_especificas_papel(
        self,
        no: NoGrafo,
        item: ItemPatch,
        papel: PapelAutor,
    ) -> ResultadoValidacao:
        """Checa restrições proibitivas específicas por papel."""
        if papel == PapelAutor.SISTEMA and no.tipo not in TIPOS_EDITAVEIS_PELO_SISTEMA:
            return ResultadoValidacao.falha(
                "Sistema só pode alterar nós de telemetria e a própria Sessao",
                "RoleGate",
                modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
            )
        if self._encerra_questao(no, item):
            return ResultadoValidacao.falha(
                f"Papel '{papel.value}' não pode encerrar a Question '{no.id}'. "
                "Use 'abrir_questao' e aguarde a resposta humana",
                "RoleGate",
                {"id_questao": no.id},
                modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
            )
        if not self._eh_fechamento_de_task(no, item):
            return ResultadoValidacao.sucesso()
        if papel in (PapelAutor.PLANEJADOR, PapelAutor.REVISOR):
            return ResultadoValidacao.falha(
                f"Papel '{papel.value}' não pode fechar/concluir Task",
                "RoleGate",
                modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
            )
        return ResultadoValidacao.sucesso()

    def _encerra_questao(self, no: NoGrafo, item: ItemPatch) -> bool:
        """Identifica a gravação de um status que dá a dúvida por encerrada."""
        if no.tipo != TipoNo.QUESTION:
            return False
        return self._extrair_status_proposto(item) in STATUS_DE_QUESTION_RESERVADOS_AO_HUMANO

    def _extrair_status_proposto(self, item: ItemPatch) -> str | None:
        """Lê o status escrito, seja na propriedade isolada, seja no nó inteiro."""
        if item.path.endswith("/propriedades/status"):
            return str(item.value) if item.value is not None else None
        if not isinstance(item.value, dict):
            return None
        propriedades = item.value.get("propriedades")
        if not isinstance(propriedades, dict) or "status" not in propriedades:
            return None
        return str(propriedades["status"])

    def _eh_fechamento_de_task(self, no: NoGrafo, item: ItemPatch) -> bool:
        """Identifica a operação que marca uma Task como concluída."""
        if no.tipo != TipoNo.TASK:
            return False
        return "status" in item.path and item.value == StatusTask.CONCLUIDO.value


def descrever_tipos_permitidos(papel: PapelAutor) -> tuple[str, ...]:
    """Consulta auxiliar que lista, em ordem estável, os tipos criáveis por um papel."""
    permitidos: frozenset[TipoNo] = RoleGate.NOS_CRIACAO_PERMITIDOS.get(papel, frozenset())
    return tuple(sorted(tipo.value for tipo in permitidos))
