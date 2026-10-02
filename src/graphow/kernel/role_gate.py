"""Portão 2: Validação de Contratos de Permissão por Papel (Role Gate).

O portão avalia três superfícies, não uma: a criação de nós, a edição e remoção
de nós, e a camada de arestas — que antes retornava sucesso para qualquer papel
e deixava um executor reescopar a própria tarefa. A camada de arestas vive em
kernel/permissao_de_aresta.py, com o dono por tipo e por par de tipos.
"""

from collections.abc import Sequence
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.governanca import PROPRIEDADE_GOVERNANCA_DO_PROJETO, Gesto, PoliticaGovernanca
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import NivelAutonomiaProjeto, PapelAutor, StatusQuestion, StatusTask, TipoNo
from graphow.kernel.gestos_de_no import ContextoPermissaoEdicao, GestosDeNo
from graphow.kernel.matriz_papeis import (
    PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO,
    PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO,
    STATUS_DE_QUESTION_ESCRITOS_POR_AGENTES,
    TIPOS_CUJA_REMOCAO_EXIGE_HUMANO,
    TIPOS_EDITAVEIS_PELO_SISTEMA,
    TIPOS_EXCLUSIVOS_DO_HUMANO,
    TIPOS_LIBERADOS_POR_GESTO,
)
from graphow.kernel.patch_models import (
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)
from graphow.kernel.permissao_de_aresta import (
    SEGMENTOS_DE_ELEMENTO_INTEIRO,
    ContextoPapel,
    PermissaoDeAresta,
    descrever_reserva_do_gesto,
)
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral, projetar_lote
from graphow.kernel.veredito_reservado import validar_escrita_de_veredito

SEGMENTOS_DE_UMA_PROPRIEDADE: int = 4


class RoleGate:
    """Portão que impõe as regras de permissão de escrita conforme o papel do autor.

    Um projeto com estrutura ilimitada amplia os tipos de nó que um agente pode
    criar, mas nunca dispensa as invariantes duras: o `Governanca` e a política
    do projeto são sempre do humano. Os demais gestos que antes eram só dele
    (responder uma `Question`, promover um Aprendizado, governar `Constraint`,
    excluir, fechar Goal, encerrar Sessão) a política do projeto do alvo
    reserva ao humano ou entrega ao árbitro; nenhum outro papel os ganha.
    """

    NOS_CRIACAO_PERMITIDOS: dict[PapelAutor, frozenset[TipoNo]] = {
        PapelAutor.HUMANO: frozenset(TipoNo),
        # Registra Aprendizado quem detém `deriva_de`: executor e revisor. Um
        # Aprendizado nasce apontando para a origem, e a camada de proveniência
        # do trabalho segue fechada a quem só planeja. O que nenhum agente pode
        # é promovê-lo.
        # A Evidence do planejador é o que ele leu no código para decidir: o
        # explorador só aponta trechos, e o julgamento fica com quem planeja. O
        # InvariantGate exige dela arquivo, linhas e trecho (kernel/localizacao.py).
        PapelAutor.PLANEJADOR: frozenset(
            {TipoNo.TASK, TipoNo.DECISION, TipoNo.QUESTION, TipoNo.NOTE, TipoNo.EVIDENCE}
        ),
        PapelAutor.EXECUTOR: frozenset(
            {TipoNo.ARTIFACT, TipoNo.EVIDENCE, TipoNo.DECISION, TipoNo.QUESTION, TipoNo.NOTE, TipoNo.APRENDIZADO}
        ),
        PapelAutor.REVISOR: frozenset({TipoNo.EVIDENCE, TipoNo.QUESTION, TipoNo.NOTE, TipoNo.APRENDIZADO}),
        # O árbitro, por si só, registra só o que sustenta um julgamento. Os
        # poderes extras (Constraint, remover, responder, promover, fechar,
        # encerrar) vêm da política de governança do projeto do alvo.
        PapelAutor.ARBITRO: frozenset({TipoNo.EVIDENCE, TipoNo.DECISION, TipoNo.NOTE}),
        # O harness registra a sessao em que roda, a propria telemetria e, quando
        # o humano nao configurou um Setor, o ambiente padrao da memoria: o
        # Projeto do repositorio e o Setor `Memoria`. Nada do grafo de trabalho,
        # e nenhum papel de agente alcanca `sistema`. Ver harness/ambiente_padrao.py.
        PapelAutor.SISTEMA: frozenset({TipoNo.RUN, TipoNo.SESSAO, TipoNo.PROJETO, TipoNo.SETOR}),
    }

    # Sob estrutura ilimitada o agente ganha a camada de navegação e os nós de
    # trabalho, jamais os tipos reservados ao humano. O Projeto fica de fora: ele
    # é a raiz, nenhum agente o cria, e um Projeto novo herdaria a política
    # global sem ter pai que o prenda a um projeto estrito.
    NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA: frozenset[TipoNo] = (
        frozenset(TipoNo) - TIPOS_EXCLUSIVOS_DO_HUMANO - {TipoNo.PROJETO}
    )

    def __init__(self, rastreador: RastreadorProjetoAncestral | None = None) -> None:
        self._rastreador: RastreadorProjetoAncestral = rastreador or RastreadorProjetoAncestral()
        self._arestas: PermissaoDeAresta = PermissaoDeAresta(self._rastreador)
        self._gestos: GestosDeNo = GestosDeNo(self._rastreador)

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
            return self._arestas.validar(segmentos, item, contexto)
        if segmentos[0] != "nos":
            return ResultadoValidacao.sucesso()
        resultado_veredito = validar_escrita_de_veredito(segmentos, item, contexto)
        if not resultado_veredito.aprovado:
            return resultado_veredito
        if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO and item.op == OperacaoPatch.ADD:
            return self._validar_permissao_criacao_no(item, contexto)
        ctx = ContextoPermissaoEdicao(segmentos=tuple(segmentos), item=item, contexto=contexto)
        return self._validar_permissao_edicao_no(ctx)

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
        resultado_reservadas = self._validar_propriedades_na_criacao(tipo_no, item, contexto)
        if not resultado_reservadas.aprovado:
            return resultado_reservadas
        if tipo_no in self._tipos_permitidos_para(item, contexto):
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Papel '{contexto.proposta.papel.value}' não possui permissão para criar nó do tipo "
            f"'{tipo_no.value}'{self._reserva_do_tipo_governado(tipo_no, item, contexto)}",
            "RoleGate",
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _reserva_do_tipo_governado(self, tipo_no: TipoNo, item: ItemPatch, contexto: ContextoPapel) -> str:
        """Para o tipo que um gesto governa, diz de quem o gesto é na política do projeto."""
        gesto = TIPOS_LIBERADOS_POR_GESTO.get(tipo_no)
        if gesto is None:
            return ""
        politica = self._gestos.politica_do_no(str(item.value.get("id")), contexto)
        return f". {descrever_reserva_do_gesto(gesto, politica)}"

    def _validar_propriedades_na_criacao(
        self,
        tipo_no: TipoNo,
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> ResultadoValidacao:
        """O nó nasce sem o que só o humano escreve: alcance, status fechado, autonomia, política.

        O Projeto que um agente criasse com autonomia ilimitada se julgava sob
        a própria autonomia: a antevisão do lote já o continha, e o RoleGate
        liberava a criação que ela mesma tornava possível. O mesmo vale para a
        `governanca`: o meta-portão é sempre do humano. O Goal e a Sessão
        nascem abertos; nascer fechado é o gesto de fechar ou encerrar.
        """
        papel = contexto.proposta.papel
        propriedades = item.value.get("propriedades") if isinstance(item.value, dict) else None
        declaradas = propriedades if isinstance(propriedades, dict) else {}
        if tipo_no == TipoNo.APRENDIZADO and PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO & set(declaradas):
            return self._recusar_alcance(papel)
        status = str(declaradas.get("status", StatusQuestion.ABERTA.value))
        if tipo_no == TipoNo.QUESTION and status not in STATUS_DE_QUESTION_ESCRITOS_POR_AGENTES:
            return self._gestos.recusar_encerramento_de_questao(str(item.value.get("id")), papel)
        if tipo_no == TipoNo.PROJETO:
            return self._validar_propriedades_de_projeto_na_criacao(declaradas, papel)
        return self._gestos.validar_status_na_criacao(tipo_no, item, contexto)

    def _validar_propriedades_de_projeto_na_criacao(
        self,
        declaradas: dict[str, Any],
        papel: PapelAutor,
    ) -> ResultadoValidacao:
        """O Projeto criado por agente declara só o nível estrito e nenhuma `governanca`."""
        nivel = str(declaradas.get("nivel_autonomia", NivelAutonomiaProjeto.ESTRITO.value))
        if nivel != NivelAutonomiaProjeto.ESTRITO.value:
            return self._recusar_autonomia(papel)
        if PROPRIEDADE_GOVERNANCA_DO_PROJETO in declaradas:
            return self._recusar_governanca_do_projeto(papel)
        return ResultadoValidacao.sucesso()

    def _tipos_permitidos_para(self, item: ItemPatch, contexto: ContextoPapel) -> frozenset[TipoNo]:
        """Determina o conjunto de tipos criáveis, considerando a política do projeto do alvo.

        A política amplia por dois caminhos: a estrutura ilimitada entrega a
        camada de navegação e os nós de trabalho a todos os agentes, e um gesto
        entrega ao árbitro o tipo que ele governa (Constraint).
        """
        papel = contexto.proposta.papel
        tipos = self.NOS_CRIACAO_PERMITIDOS.get(papel, frozenset())
        id_alvo = self._identificar_alvo_do_item(item)
        if id_alvo is None:
            return tipos
        politica = self._gestos.politica_do_no(id_alvo, contexto)
        if politica.estrutura_ilimitada:
            tipos = tipos | self.NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA
        liberados = {tipo for tipo, gesto in TIPOS_LIBERADOS_POR_GESTO.items() if politica.permite(gesto, papel)}
        return tipos | liberados

    def _identificar_alvo_do_item(self, item: ItemPatch) -> str | None:
        """Extrai o identificador do nó que a operação cria, a partir do caminho."""
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO:
            return None
        return segmentos[1]

    def _validar_permissao_edicao_no(self, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Valida se o papel pode editar ou remover campos específicos do nó."""
        papel = ctx.contexto.proposta.papel
        no_existente = ctx.contexto.estado.nos.get(ctx.segmentos[1])
        if no_existente is None:
            return ResultadoValidacao.sucesso()
        if no_existente.tipo in TIPOS_EXCLUSIVOS_DO_HUMANO:
            resultado_exclusivo = self._gestos.validar_tipo_exclusivo(no_existente, ctx)
            if not resultado_exclusivo.aprovado:
                return resultado_exclusivo
        resultado_remocao = self._validar_remocao_de_no(no_existente, ctx)
        if not resultado_remocao.aprovado:
            return resultado_remocao
        resultado_alcance = self._validar_alcance_de_aprendizado(no_existente, ctx.item, papel)
        if not resultado_alcance.aprovado:
            return resultado_alcance
        reservadas_do_projeto = PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO
        if no_existente.tipo == TipoNo.PROJETO and self._escreve_propriedade(ctx.segmentos, reservadas_do_projeto):
            if ctx.segmentos[-1] == PROPRIEDADE_GOVERNANCA_DO_PROJETO:
                return self._recusar_governanca_do_projeto(papel)
            return self._recusar_autonomia(papel)
        return self._validar_regras_especificas_papel(no_existente, ctx)

    def _escreve_propriedade(self, segmentos: Sequence[str], chaves: frozenset[str]) -> bool:
        """Reconhece a operação em `/nos/<id>/propriedades/<chave>` sobre uma das chaves."""
        return len(segmentos) == SEGMENTOS_DE_UMA_PROPRIEDADE and segmentos[-1] in chaves

    def _recusar_autonomia(self, papel: PapelAutor) -> ResultadoValidacao:
        """Explica que ampliar a autonomia do projeto é gesto do humano."""
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' nao pode escrever 'nivel_autonomia' num Projeto. "
            "Ajustar a autonomia e prerrogativa do humano: use 'configurar_autonomia_projeto'",
            "RoleGate",
            {"propriedades_reservadas": ", ".join(sorted(PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO))},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _recusar_governanca_do_projeto(self, papel: PapelAutor) -> ResultadoValidacao:
        """Explica que a política de governança do projeto é do humano, em qualquer política."""
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' nao pode escrever 'governanca' num Projeto. "
            "A politica de governanca e prerrogativa do humano, sem delegacao ao arbitro",
            "RoleGate",
            {"propriedades_reservadas": ", ".join(sorted(PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO))},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _validar_alcance_de_aprendizado(
        self,
        no: NoGrafo,
        item: ItemPatch,
        papel: PapelAutor,
    ) -> ResultadoValidacao:
        """Só o humano escreve o alcance de um Aprendizado: promover é dele."""
        segmentos = item.path.split("/")[1:]
        if no.tipo != TipoNo.APRENDIZADO:
            return ResultadoValidacao.sucesso()
        if not self._escreve_propriedade(segmentos, PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO):
            return ResultadoValidacao.sucesso()
        return self._recusar_alcance(papel)

    def _recusar_alcance(self, papel: PapelAutor) -> ResultadoValidacao:
        """Explica que promover um aprendizado é prerrogativa do humano."""
        return ResultadoValidacao.falha(
            f"Papel '{papel.value}' nao pode escrever 'alcance' num Aprendizado. "
            "Promover e prerrogativa do humano: use 'promover_aprendizado'",
            "RoleGate",
            {"propriedades_reservadas": ", ".join(sorted(PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO))},
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )

    def _validar_remocao_de_no(
        self,
        no: NoGrafo,
        ctx: ContextoPermissaoEdicao,
    ) -> ResultadoValidacao:
        """Um agente remove só o tipo de nó que cria, e só se a cascata não levar o que ele não remove.

        Sem isso o executor apagava qualquer Task, Decision ou Goal, e a
        projeção levava junto as arestas do nó: a `bloqueia` que o travava, a
        `escopa` da Constraint, a `produz` que pendura o trabalho da Sessão.
        Duas exceções vêm da política: a Constraint se remove pelo gesto
        `constraint`, e qualquer outro tipo (Question e Aprendizado inclusive)
        pelo gesto `excluir`, que leva a cascata inteira.
        """
        eh_remocao_inteira = (
            ctx.item.op == OperacaoPatch.REMOVE
            and len(ctx.segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO
        )
        if not eh_remocao_inteira:
            return ResultadoValidacao.sucesso()
        if no.tipo in TIPOS_LIBERADOS_POR_GESTO:
            return self._arestas.validar_remocao_em_cascata(no.id, ctx.contexto)
        politica = self._gestos.politica_do_no(no.id, ctx.contexto)
        if politica.permite(Gesto.EXCLUIR, ctx.contexto.proposta.papel):
            return self._gestos.validar_exclusao(no, ctx)
        motivo = self._motivo_da_remocao_recusada(no, ctx, politica)
        if motivo is not None:
            return self._gestos.recusar_remocao(no, ctx, motivo)
        return self._arestas.validar_remocao_em_cascata(no.id, ctx.contexto)

    def _motivo_da_remocao_recusada(
        self,
        no: NoGrafo,
        ctx: ContextoPermissaoEdicao,
        politica: PoliticaGovernanca,
    ) -> str | None:
        """Por que o papel não remove o tipo de nó, ou None quando a regra do tipo o deixa."""
        reserva = descrever_reserva_do_gesto(Gesto.EXCLUIR, politica)
        if no.tipo in TIPOS_CUJA_REMOCAO_EXIGE_HUMANO:
            return f"Somente uma sessao humana encerra uma escalacao. {reserva}"
        if no.tipo not in self._tipos_permitidos_para(ctx.item, ctx.contexto):
            return f"Um agente remove apenas o tipo de no que pode criar. {reserva}"
        return None

    def _validar_regras_especificas_papel(self, no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Checa restrições proibitivas específicas por papel."""
        item = ctx.item
        papel = ctx.contexto.proposta.papel
        if papel == PapelAutor.SISTEMA and no.tipo not in TIPOS_EDITAVEIS_PELO_SISTEMA:
            return ResultadoValidacao.falha(
                "Sistema só pode alterar nós de telemetria e a própria Sessao",
                "RoleGate",
                modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
            )
        if self._encerra_questao(no, item):
            return self._gestos.validar_encerramento_de_questao(no, ctx)
        resultado_de_gesto = self._gestos.validar_status_que_exige_gesto(no, ctx)
        if not resultado_de_gesto.aprovado:
            return resultado_de_gesto
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
        """Identifica a escrita de status que tira a dúvida do estado aberto.

        Remover o status também encerra: sem ele o InvariantGate não acha
        status 'aberta' e deixa concluir a Task.
        """
        if no.tipo != TipoNo.QUESTION or not item.path.endswith("/propriedades/status"):
            return False
        return item.op == OperacaoPatch.REMOVE or str(item.value) not in STATUS_DE_QUESTION_ESCRITOS_POR_AGENTES

    def _eh_fechamento_de_task(self, no: NoGrafo, item: ItemPatch) -> bool:
        """Identifica a operação que marca uma Task como concluída."""
        if no.tipo != TipoNo.TASK:
            return False
        return "status" in item.path and item.value == StatusTask.CONCLUIDO.value


def descrever_tipos_permitidos(papel: PapelAutor) -> tuple[str, ...]:
    """Consulta auxiliar que lista, em ordem estável, os tipos criáveis por um papel."""
    permitidos: frozenset[TipoNo] = RoleGate.NOS_CRIACAO_PERMITIDOS.get(papel, frozenset())
    return tuple(sorted(tipo.value for tipo in permitidos))
