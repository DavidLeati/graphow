"""Controlador REST da governança: o que a tela de configurações lê e o que o humano grava nela.

A política decide quem faz cada gesto (o humano ou o árbitro), e a tela precisa
ler o catálogo, a configuração guardada e a política efetiva com a origem de
cada gesto, gravá-las pelo mesmo planejamento que o MCP usa, auditar o que o
árbitro fez e liberar a posse de uma tarefa. A escrita é sempre humana: a
identidade é a do servidor, e o meta-portão do kernel recusa qualquer outra.
"""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from graphow.core.events import EventoLog
from graphow.core.governanca import CHAVE_PERSONALIZADA, CHAVE_PRESET, ID_GOVERNANCA_GLOBAL
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, PropostaPatch
from graphow.kernel.planejamento_governanca import (
    ESCOPO_GLOBAL,
    ErroDeConfiguracaoDeGovernanca,
    com_preset_salvo,
    configuracao_salva,
    descrever_politica,
    descrever_politica_efetiva,
    ler_operacao_do_projeto,
    planejar_configuracao,
    planejar_operacao,
)
from graphow.kernel.politica_governanca import resolver_politica_global
from graphow.kernel.write_kernel import WriteKernel
from graphow.web.catalogo_governanca import montar_catalogo_de_governanca
from graphow.web.dto import RequisicaoGovernanca, RespostaHttpWeb
from graphow.web.identidade_web import IdentidadeSessaoWeb

LIMITE_PADRAO_DA_AUDITORIA: int = 50
LIMITE_MAXIMO_DA_AUDITORIA: int = 500
CAMPOS_DE_ID_TOCADO: tuple[str, ...] = ("id", "origem_id", "destino_id")
MENSAGEM_SEM_CAMPOS: str = "Informe ao menos um de: preset, personalizada, operacao"
MENSAGEM_SEM_CAMPOS_GLOBAL: str = "Informe ao menos um de: preset, personalizada"


class GovernancaWebController:
    """Lê a governança do ramo para a tela e recebe do humano a configuração, a auditoria e a liberação de posse."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeSessaoWeb | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb()

    def obter_global(self, ramo_id: str = "main") -> RespostaHttpWeb:
        """Catálogo, configuração global guardada e política global efetiva."""
        estado = self._kernel.obter_estado(ramo_id)
        corpo = {
            "sucesso": True,
            "ramo_id": ramo_id,
            "versao_log": estado.versao_log,
            "catalogo": montar_catalogo_de_governanca(),
            "configuracao": configuracao_salva(ESCOPO_GLOBAL, estado),
            "declarada": ID_GOVERNANCA_GLOBAL in estado.nos,
            **descrever_politica_efetiva(ESCOPO_GLOBAL, estado),
        }
        return RespostaHttpWeb(corpo)

    def obter_projeto(self, id_projeto: str, ramo_id: str = "main") -> RespostaHttpWeb:
        """Configuração do Projeto, política efetiva com a origem de cada gesto e propriedades operacionais."""
        estado = self._kernel.obter_estado(ramo_id)
        projeto = estado.nos.get(id_projeto)
        if projeto is None or projeto.tipo != TipoNo.PROJETO:
            return _nao_encontrado(f"Projeto '{id_projeto}' nao encontrado neste ramo")
        corpo = {
            "sucesso": True,
            "ramo_id": ramo_id,
            "versao_log": estado.versao_log,
            "id_projeto": id_projeto,
            "rotulo": projeto.rotulo,
            "configuracao": configuracao_salva(id_projeto, estado),
            "operacao": ler_operacao_do_projeto(projeto),
            "politica_global": descrever_politica(resolver_politica_global(estado))["politica_efetiva"],
            **descrever_politica_efetiva(id_projeto, estado),
        }
        return RespostaHttpWeb(corpo)

    def gravar_global(self, req: RequisicaoGovernanca) -> RespostaHttpWeb:
        """Grava a política global; a personalizada é mesclada na guardada e nunca apagada."""
        if req.preset is None and req.personalizada is None:
            return _recusa_de_corpo(MENSAGEM_SEM_CAMPOS_GLOBAL)
        estado = self._kernel.obter_estado(req.ramo_id)
        argumentos = {CHAVE_PRESET: req.preset, CHAVE_PERSONALIZADA: req.personalizada}
        try:
            plano = planejar_configuracao(ESCOPO_GLOBAL, com_preset_salvo(ESCOPO_GLOBAL, argumentos, estado), estado)
        except ErroDeConfiguracaoDeGovernanca as erro:
            return _recusa_de_configuracao(erro)
        return self._submeter_e_descrever(ESCOPO_GLOBAL, plano, req.ramo_id)

    def gravar_projeto(self, id_projeto: str, req: RequisicaoGovernanca) -> RespostaHttpWeb:
        """Grava a política do Projeto e, no mesmo lote, as propriedades operacionais."""
        if req.preset is None and req.personalizada is None and req.operacao is None:
            return _recusa_de_corpo(MENSAGEM_SEM_CAMPOS)
        estado = self._kernel.obter_estado(req.ramo_id)
        projeto = estado.nos.get(id_projeto)
        if projeto is None or projeto.tipo != TipoNo.PROJETO:
            return _nao_encontrado(f"Projeto '{id_projeto}' nao encontrado neste ramo")
        try:
            plano = _planejar_do_projeto(id_projeto, req, estado)
        except ErroDeConfiguracaoDeGovernanca as erro:
            return _recusa_de_configuracao(erro)
        return self._submeter_e_descrever(id_projeto, plano, req.ramo_id)

    def obter_auditoria(self, limite: int = LIMITE_PADRAO_DA_AUDITORIA, ramo_id: str = "main") -> RespostaHttpWeb:
        """Os eventos que o árbitro escreveu, os mais recentes primeiro, cortados no limite."""
        limite = max(1, min(limite, LIMITE_MAXIMO_DA_AUDITORIA))
        do_arbitro = [e for e in self._kernel.repositorio.ler_eventos(ramo_id) if e.papel == PapelAutor.ARBITRO]
        recentes = sorted(do_arbitro, key=lambda evento: evento.seq, reverse=True)[:limite]
        corpo = {
            "sucesso": True,
            "ramo_id": ramo_id,
            "total": len(do_arbitro),
            "limite": limite,
            "eventos": [_descrever_evento_de_auditoria(evento) for evento in recentes],
        }
        return RespostaHttpWeb(corpo)

    def liberar_posse(self, id_task: str, ramo_id: str = "main") -> RespostaHttpWeb:
        """Libera o lock da Task de qualquer dono: é o gesto humano que destrava o subagente que não voltou."""
        no = self._kernel.obter_estado(ramo_id).nos.get(id_task)
        if no is None or no.tipo != TipoNo.TASK:
            return _nao_encontrado(f"Task '{id_task}' nao encontrada neste ramo")
        dono = self._kernel.obter_dono_do_lock(id_task)
        if not dono or not self._kernel.liberar_lock_task(id_task, dono):
            corpo = {"sucesso": False, "id_task": id_task, "mensagem": f"A tarefa '{id_task}' nao esta sob posse de ninguem"}
            return RespostaHttpWeb(corpo, HTTPStatus.CONFLICT)
        corpo = {"sucesso": True, "id_task": id_task, "dono_anterior": dono, "mensagem": f"Posse de '{dono}' devolvida"}
        return RespostaHttpWeb(corpo)

    def _submeter_e_descrever(self, escopo: str, plano: Sequence[ItemPatch], ramo_id: str) -> RespostaHttpWeb:
        """Submete o lote sob a identidade do servidor e devolve a política efetiva que ele produziu."""
        if not plano:
            return self._descrever_gravacao(escopo, "Nada a gravar", ramo_id)
        dados = DadosPropostaPatch(
            autor=self._identidade.autor,
            papel=PapelAutor(self._identidade.papel_textual),
            operacoes=tuple(plano),
            justificativa=f"Configuracao de governanca do escopo {escopo}",
            ramo_id=ramo_id,
        )
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        if not recibo.sucesso:
            corpo = {"sucesso": False, "mensagem": recibo.mensagem, "versao_log": recibo.versao_log, "problemas": []}
            return RespostaHttpWeb(corpo, HTTPStatus.BAD_REQUEST)
        return self._descrever_gravacao(escopo, recibo.mensagem, ramo_id)

    def _descrever_gravacao(self, escopo: str, mensagem: str, ramo_id: str) -> RespostaHttpWeb:
        """O recibo de uma gravação com a configuração guardada e a política efetiva que passou a valer."""
        estado = self._kernel.obter_estado(ramo_id)
        corpo = {
            "sucesso": True,
            "mensagem": mensagem,
            "versao_log": estado.versao_log,
            "configuracao": configuracao_salva(escopo, estado),
            **descrever_politica_efetiva(escopo, estado),
        }
        if escopo != ESCOPO_GLOBAL:
            corpo["operacao"] = ler_operacao_do_projeto(estado.nos[escopo])
        return RespostaHttpWeb(corpo)


def _planejar_do_projeto(id_projeto: str, req: RequisicaoGovernanca, estado: GrafoEstado) -> tuple[ItemPatch, ...]:
    """A configuração, quando o corpo a traz, e as propriedades operacionais, no mesmo lote.

    Só `operacao` no corpo não regrava a configuração: reescrever o que não
    mudou custaria um evento no log sem dizer nada.
    """
    plano: tuple[ItemPatch, ...] = ()
    if req.preset is not None or req.personalizada is not None:
        argumentos = com_preset_salvo(id_projeto, {CHAVE_PRESET: req.preset, CHAVE_PERSONALIZADA: req.personalizada}, estado)
        plano += planejar_configuracao(id_projeto, argumentos, estado)
    if req.operacao is not None:
        plano += planejar_operacao(id_projeto, req.operacao, estado)
    return plano


def _descrever_evento_de_auditoria(evento: EventoLog) -> dict[str, Any]:
    """O evento do árbitro como a tela o lista: posição no log, instante, autor, tipo e o que foi tocado.

    A justificativa do lote não chega ao log (só o recibo a vê), então ela
    viaja nula: o campo existe para a tela acendê-lo no dia em que o log a guardar.
    """
    return {
        "seq": evento.seq,
        "instante": evento.timestamp_utc,
        "autor": evento.autor,
        "papel": evento.papel.value,
        "tipo": evento.tipo_evento.value,
        "justificativa": None,
        "ids_tocados": _ids_tocados(evento.payload),
    }


def _ids_tocados(payload: Mapping[str, Any]) -> list[str]:
    """Os ids que o payload do evento nomeia: o nó ou aresta e, na aresta, as duas pontas."""
    return [str(payload[campo]) for campo in CAMPOS_DE_ID_TOCADO if payload.get(campo)]


def _nao_encontrado(mensagem: str) -> RespostaHttpWeb:
    """A resposta 404 de um alvo que não existe neste ramo."""
    return RespostaHttpWeb({"sucesso": False, "mensagem": mensagem}, HTTPStatus.NOT_FOUND)


def _recusa_de_corpo(mensagem: str) -> RespostaHttpWeb:
    """A resposta 400 de um corpo sem nada a gravar."""
    return RespostaHttpWeb({"sucesso": False, "mensagem": mensagem, "problemas": [mensagem]}, HTTPStatus.BAD_REQUEST)


def _recusa_de_configuracao(erro: ErroDeConfiguracaoDeGovernanca) -> RespostaHttpWeb:
    """A resposta 400 de uma configuração inválida, com cada problema que o planejamento apontou."""
    corpo = {"sucesso": False, "mensagem": str(erro), "problemas": list(erro.problemas)}
    return RespostaHttpWeb(corpo, HTTPStatus.BAD_REQUEST)
