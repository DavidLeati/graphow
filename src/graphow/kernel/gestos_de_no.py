"""Gestos de governança que o RoleGate aplica aos nós: quem os faz é decidido pela política do projeto.

Cada gesto (responder uma Question, governar Constraint, excluir, fechar Goal,
encerrar Sessão) era só do humano. A política de governança do projeto do nó o
reserva ao humano ou o entrega ao árbitro, e este módulo é a leitura dela no
portão de nós. A política vem só do estado do grafo (`resolver_politica_do_no`),
então o replay do log repete o veredito.

As arestas têm o gesto delas em kernel/permissao_de_aresta.py.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.governanca import Gesto, PoliticaGovernanca
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.matriz_papeis import (
    STATUS_DE_QUESTION_ESCRITOS_PELO_ARBITRO,
    STATUS_QUE_ENCERRA_SESSAO,
    STATUS_QUE_FECHA_GOAL,
    TIPOS_LIBERADOS_POR_GESTO,
    eh_autoria_propria,
)
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, ResultadoValidacao
from graphow.kernel.permissao_de_aresta import ContextoPapel, descrever_reserva_do_gesto
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral

CAMINHO_DO_STATUS: str = "/propriedades/status"


@dataclass(frozen=True)
class ContextoPermissaoEdicao:
    """DTO imutável para parâmetros de validação de permissão de edição."""

    segmentos: Sequence[str]
    item: ItemPatch
    contexto: ContextoPapel


class GestosDeNo:
    """Aplica os gestos da política de governança às operações sobre nós."""

    def __init__(self, rastreador: RastreadorProjetoAncestral) -> None:
        self._rastreador: RastreadorProjetoAncestral = rastreador

    def politica_do_no(self, id_no: str, contexto: ContextoPapel) -> PoliticaGovernanca:
        """Política efetiva do projeto do nó, lida só do estado do grafo."""
        return resolver_politica_do_no(id_no, contexto.estado_com_lote, self._rastreador)

    def exigir(self, gesto: Gesto, id_no: str, contexto: ContextoPapel, *, o_que: str) -> ResultadoValidacao:
        """Aprova se a política do projeto do nó entrega o gesto ao papel; senão diz qual falta."""
        politica = self.politica_do_no(id_no, contexto)
        papel = contexto.proposta.papel
        if politica.permite(gesto, papel):
            return ResultadoValidacao.sucesso()
        return self._falha(
            f"Papel '{papel.value}' nao pode {o_que}. {descrever_reserva_do_gesto(gesto, politica)}",
            {"gesto": gesto.value, "id_no": id_no},
        )

    def validar_status_na_criacao(
        self,
        tipo_no: TipoNo,
        item: ItemPatch,
        contexto: ContextoPapel,
    ) -> ResultadoValidacao:
        """Goal nascido concluído e Sessão nascida encerrada passam pelo gesto que os fecharia."""
        valor: dict[str, Any] = item.value if isinstance(item.value, dict) else {}
        status = str(dict(valor.get("propriedades") or {}).get("status", ""))
        id_no = str(valor.get("id"))
        if tipo_no == TipoNo.GOAL and status == STATUS_QUE_FECHA_GOAL:
            return self.exigir(Gesto.FECHAR_GOAL, id_no, contexto, o_que=f"criar o Goal '{id_no}' ja concluido")
        if tipo_no == TipoNo.SESSAO and status == STATUS_QUE_ENCERRA_SESSAO:
            return self._exigir_do_nao_sistema(
                Gesto.ENCERRAR_SESSAO, id_no, contexto, o_que=f"criar a Sessao '{id_no}' ja encerrada"
            )
        return ResultadoValidacao.sucesso()

    def validar_tipo_exclusivo(self, no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Constraint e Governanca são do humano; o gesto `constraint` abre o primeiro ao árbitro.

        O Governanca nunca abre: ele guarda a política que decide os gestos.
        """
        papel = ctx.contexto.proposta.papel
        gesto = TIPOS_LIBERADOS_POR_GESTO.get(no.tipo)
        politica = self.politica_do_no(no.id, ctx.contexto) if gesto is not None else None
        if gesto is not None and politica is not None and politica.permite(gesto, papel):
            return ResultadoValidacao.sucesso()
        reserva = f". {descrever_reserva_do_gesto(gesto, politica)}" if gesto and politica else ""
        return self._falha(f"Papel '{papel.value}' não pode alterar nós de '{no.tipo.value}'{reserva}")

    def validar_exclusao(self, no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """A exclusão que o gesto `excluir` entrega ao árbitro, menos a da Question que ele abriu.

        Apagar a dúvida é a forma mais direta de encerrá-la: quem a abriu não a
        encerra, nem por remoção. A cascata de arestas sai junto com o nó.
        """
        autor = ctx.contexto.proposta.autor
        if no.tipo == TipoNo.QUESTION and eh_autoria_propria(autor, no.propriedades.get("aberta_por")):
            motivo = "Foi o proprio autor quem abriu a Question, e encerrar a propria duvida seria julgar em causa propria"
            return self.recusar_remocao(no, ctx, motivo)
        return ResultadoValidacao.sucesso()

    def recusar_remocao(self, no: NoGrafo, ctx: ContextoPermissaoEdicao, motivo: str) -> ResultadoValidacao:
        """Diz que o papel não remove aquele tipo de nó, e por quê."""
        return self._falha(
            f"Papel '{ctx.contexto.proposta.papel.value}' não pode remover nós de '{no.tipo.value}'. {motivo}",
            {"id_no": no.id, "tipo": no.tipo.value},
        )

    def validar_encerramento_de_questao(self, no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Encerrar a Question é o gesto `responder_questao`: do humano, ou do árbitro se a política o entrega.

        O árbitro escreve só `respondida` ou `descartada` (ou remove o status), e
        não encerra a Question que ele mesmo abriu.
        """
        papel = ctx.contexto.proposta.papel
        politica = self.politica_do_no(no.id, ctx.contexto)
        if not politica.permite(Gesto.RESPONDER_QUESTAO, papel):
            return self.recusar_encerramento_de_questao(no.id, papel, politica)
        if ctx.item.op != OperacaoPatch.REMOVE and str(ctx.item.value) not in STATUS_DE_QUESTION_ESCRITOS_PELO_ARBITRO:
            permitidos = " ou ".join(repr(status) for status in sorted(STATUS_DE_QUESTION_ESCRITOS_PELO_ARBITRO))
            return self._falha(
                f"Papel '{papel.value}' so encerra a Question '{no.id}' com o status {permitidos}",
                {"id_questao": no.id},
            )
        if eh_autoria_propria(ctx.contexto.proposta.autor, no.propriedades.get("aberta_por")):
            return self._falha(
                f"Papel '{papel.value}' nao pode encerrar a Question '{no.id}': foi ele quem a abriu, "
                "e encerrar a propria duvida seria julgar em causa propria",
                {"id_questao": no.id},
            )
        return ResultadoValidacao.sucesso()

    def recusar_encerramento_de_questao(
        self,
        id_questao: str,
        papel: PapelAutor,
        politica: PoliticaGovernanca | None = None,
    ) -> ResultadoValidacao:
        """Explica que só a resposta do humano, ou do árbitro que a política autoriza, encerra a dúvida."""
        reserva = f". {descrever_reserva_do_gesto(Gesto.RESPONDER_QUESTAO, politica)}" if politica else ""
        return self._falha(
            f"Papel '{papel.value}' não pode encerrar a Question '{id_questao}'. "
            f"Use 'abrir_questao' e aguarde a resposta humana{reserva}",
            {"id_questao": id_questao},
        )

    def validar_status_que_exige_gesto(self, no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao:
        """Fechar um Goal e encerrar uma Sessão, por escrita de status, são gestos da política.

        Até aqui nenhum portão os guardava: qualquer agente concluía o Goal e
        encerrava a Sessão por `propor_patch`. O harness (`sistema`) segue
        encerrando a Sessão que abriu, sempre.
        """
        item = ctx.item
        if not item.path.endswith(CAMINHO_DO_STATUS):
            return ResultadoValidacao.sucesso()
        if no.tipo == TipoNo.GOAL and item.op != OperacaoPatch.REMOVE and str(item.value) == STATUS_QUE_FECHA_GOAL:
            return self.exigir(Gesto.FECHAR_GOAL, no.id, ctx.contexto, o_que=f"fechar o Goal '{no.id}'")
        if no.tipo == TipoNo.SESSAO:
            return self._exigir_do_nao_sistema(
                Gesto.ENCERRAR_SESSAO, no.id, ctx.contexto, o_que=f"escrever o status da Sessao '{no.id}'"
            )
        return ResultadoValidacao.sucesso()

    def _exigir_do_nao_sistema(
        self,
        gesto: Gesto,
        id_no: str,
        contexto: ContextoPapel,
        *,
        o_que: str,
    ) -> ResultadoValidacao:
        """Como `exigir`, mas o harness (`sistema`) passa sempre: ele encerra a Sessão que abriu."""
        if contexto.proposta.papel == PapelAutor.SISTEMA:
            return ResultadoValidacao.sucesso()
        return self.exigir(gesto, id_no, contexto, o_que=o_que)

    def _falha(self, mensagem: str, detalhes: dict[str, str] | None = None) -> ResultadoValidacao:
        """Recusa do RoleGate por violação de permissão de papel."""
        return ResultadoValidacao.falha(
            mensagem,
            "RoleGate",
            detalhes,
            modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
        )
