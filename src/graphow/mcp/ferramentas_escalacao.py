"""Ferramentas MCP do caminho de volta: da resposta humana até o agente.

Depois de `abrir_questao` o agente ficava cego. Não havia ferramenta de espera,
nem lista das próprias dúvidas, nem notificação: ele fazia polling com
`expandir_no` ou encerrava a sessão, e nada registrava que uma execução ficara
pendente de retomada. Ver achado A-06.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, TipoNo
from graphow.mcp.espera import PoliticaEspera, Relogio, RelogioMonotonico
from graphow.mcp.submissao import ContextoFerramentaMCP, extrair_ramo

CAMPO_AUTOR_DA_QUESTAO: str = "aberta_por"


@dataclass(frozen=True)
class DescricaoQuestao:
    """Instantâneo de uma dúvida aberta pelo agente e do que houve com ela."""

    id: str
    pergunta: str
    status: str
    resposta: str
    respondida_por: str

    @classmethod
    def de_no(cls, no: NoGrafo) -> "DescricaoQuestao":
        """Projeta o nó Question na forma que a ferramenta devolve."""
        return cls(
            id=no.id,
            pergunta=no.rotulo,
            status=str(no.obter_propriedade("status", StatusQuestion.ABERTA.value)),
            resposta=str(no.obter_propriedade("resposta", "")),
            respondida_por=str(no.obter_propriedade("respondida_por", "")),
        )

    def em_dicionario(self) -> dict[str, str]:
        """Forma serializável para a resposta MCP."""
        return {
            "id": self.id,
            "pergunta": self.pergunta,
            "status": self.status,
            "resposta": self.resposta,
            "respondida_por": self.respondida_por,
        }

    @property
    def foi_encerrada(self) -> bool:
        """Uma dúvida deixa de bloquear quando sai do status 'aberta'."""
        return self.status != StatusQuestion.ABERTA.value


class FerramentasEscalacao:
    """Consulta e espera pelas respostas às dúvidas abertas por esta sessão."""

    def __init__(
        self,
        contexto: ContextoFerramentaMCP,
        relogio: Relogio | None = None,
        politica: PoliticaEspera | None = None,
    ) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._relogio: Relogio = relogio or RelogioMonotonico()
        self._politica: PoliticaEspera = politica or PoliticaEspera()

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de escalação aos seus executores."""
        return {
            "minhas_questoes": self.minhas_questoes,
            "aguardar_resposta": self.aguardar_resposta,
        }

    def minhas_questoes(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Lista as dúvidas abertas por este autor, com resposta quando houver."""
        filtro_status = argumentos.get("status")
        descricoes = [
            descricao
            for descricao in self._coletar_questoes_do_autor(extrair_ramo(dict(argumentos)))
            if filtro_status is None or descricao.status == str(filtro_status)
        ]
        return {
            "sucesso": True,
            "total": len(descricoes),
            "questoes": [descricao.em_dicionario() for descricao in descricoes],
        }

    def _coletar_questoes_do_autor(self, ramo_id: str) -> tuple[DescricaoQuestao, ...]:
        """Reúne, em ordem estável, as Questions cujo autor é esta sessão."""
        view = self._contexto.kernel.obter_view(ramo_id)
        autor = self._contexto.identidade.autor
        minhas = [
            no
            for no in view.listar_nos_por_tipo(TipoNo.QUESTION)
            if str(no.obter_propriedade(CAMPO_AUTOR_DA_QUESTAO, "")) == autor
        ]
        return tuple(DescricaoQuestao.de_no(no) for no in sorted(minhas, key=lambda no: no.id))

    def aguardar_resposta(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Bloqueia até a dúvida ser encerrada pelo humano ou o prazo expirar."""
        id_questao = str(argumentos["id_questao"])
        ramo_id = extrair_ramo(dict(argumentos))
        prazo = self._politica.prazo_valido(argumentos.get("timeout_segundos"))
        limite = self._relogio.agora() + prazo
        while True:
            veredito = self._conferir_uma_vez(id_questao, ramo_id)
            if veredito is not None:
                return veredito
            if self._relogio.agora() >= limite:
                return self._relatar_expiracao(id_questao, ramo_id, prazo)
            self._relogio.aguardar(self._politica.intervalo_segundos)

    def _conferir_uma_vez(self, id_questao: str, ramo_id: str) -> dict[str, Any] | None:
        """Uma leitura da projeção: devolve a resposta final ou None para insistir."""
        no = self._contexto.kernel.obter_view(ramo_id).obter_no(id_questao)
        if no is None or no.tipo != TipoNo.QUESTION:
            return {
                "sucesso": False,
                "id_questao": id_questao,
                "erro": f"Question '{id_questao}' nao existe neste ramo",
            }
        descricao = DescricaoQuestao.de_no(no)
        if not descricao.foi_encerrada:
            return None
        return {"sucesso": True, "expirou": False, **descricao.em_dicionario()}

    def _relatar_expiracao(self, id_questao: str, ramo_id: str, prazo: float) -> dict[str, Any]:
        """Devolve o estado corrente e instrui o agente sobre a retomada."""
        no = self._contexto.kernel.obter_view(ramo_id).obter_no(id_questao)
        descricao = DescricaoQuestao.de_no(no) if no is not None else None
        return {
            "sucesso": False,
            "expirou": True,
            "id_questao": id_questao,
            "aguardou_segundos": prazo,
            "status": descricao.status if descricao else StatusQuestion.ABERTA.value,
            "mensagem": (
                "A duvida segue aberta. Retome com 'aguardar_resposta' ou "
                "consulte 'minhas_questoes' na proxima sessao."
            ),
        }
