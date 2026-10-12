"""O limite de uso da conta e o erro passageiro da API: não são falha do papel, nem da fatia.

Na bancada, a janela de uso da conta estourou no meio do Goal: as quatro
invocações da fatia seguinte saíram em dez segundos, sem custo, com
`api_error: usage_limit_reached`, e a fatia gastou as duas tentativas e virou
pendência, como se o executor tivesse falhado. O orquestrador agora reconhece
pelo stream (orquestrador/../sessoes/leitura_stream.py) duas coisas:

- o limite de uso (o `rate_limit_event` recusado, ou `usage_limit_reached`):
  não adianta insistir; o laço para com o motivo `limite_de_uso`, a tentativa
  em curso não conta, e o Goal se retoma depois da hora em que a janela volta;
- o erro passageiro (o 429 que não é o limite de uso, o 529 da sobrecarga e
  os 5xx): a mesma invocação se repete depois de uma espera crescente; se não
  passar, o laço para do mesmo jeito, retomável;
- o 4xx permanente (pedido inválido, sem permissão): não adianta esperar; é
  falha da sessão, com o erro da API no motivo.
"""

from dataclasses import dataclass
from datetime import datetime

from graphow.core.exceptions import GraphowError
from graphow.sessoes.sessao_claude import ResultadoDeSessao

ERRO_DO_LIMITE_DE_USO: str = "usage_limit_reached"
RAZAO_DO_ERRO_DA_API: str = "api_error"
STATUS_DO_LIMITE_DE_TAXA: int = 429
STATUS_DO_ERRO_DO_SERVIDOR: int = 500
STATUS_DA_SOBRECARGA: int = 529
ERRO_DA_SOBRECARGA: str = "overloaded_error"


class LimiteDaApi(GraphowError):
    """A API recusou a sessão (o limite de uso, ou o erro que não passou com as esperas): o laço para, retomável."""


@dataclass(frozen=True)
class FalhaDaApi:
    """O que a API disse: se é o limite de uso da conta, o que foi e quando a janela volta."""

    limite_de_uso: bool
    descricao: str
    volta_em: str = ""


def falha_da_api(resultado: ResultadoDeSessao) -> FalhaDaApi | None:
    """A falha da API que o stream da invocação mostra; None quando a sessão não esbarrou nela, ou esbarrou e terminou bem.

    O `rate_limit_event` recusado no meio de um stream que termina com um
    `result` de sucesso não anula o sucesso. Só são passageiros o 429 que
    não é o limite de uso, o 529 (sobrecarga) e os 5xx; o 4xx é permanente e
    vira falha da sessão, sem espera, com o erro dito no motivo.
    """
    leitura = resultado.leitura
    fim = leitura.resultado
    if fim is not None and not fim.is_error:
        return None
    limite = leitura.limite_rejeitado
    if limite is not None or (fim is not None and fim.erro_da_api == ERRO_DO_LIMITE_DE_USO):
        tipo = str(limite.get("rateLimitType", "")) if limite else ""
        volta = _hora(limite.get("resetsAt")) if limite else ""
        return FalhaDaApi(True, f"limite de uso da conta{f' ({tipo})' if tipo else ''}", volta)
    if fim is None:
        return None
    status = fim.status_do_erro or 0
    passageiro = status in (STATUS_DO_LIMITE_DE_TAXA, STATUS_DA_SOBRECARGA) or status >= STATUS_DO_ERRO_DO_SERVIDOR \
        or fim.erro_da_api == ERRO_DA_SOBRECARGA
    return FalhaDaApi(False, f"erro da API ({status or '-'} {fim.erro_da_api or fim.razao_do_fim})") if passageiro else None


def _hora(valor: object) -> str:
    """A hora local em que a janela de uso volta, do `resetsAt` em segundos; vazio sem ele."""
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return ""
    return datetime.fromtimestamp(float(valor)).astimezone().strftime("%Y-%m-%d %H:%M")


def recusa(falha: FalhaDaApi, papel: str) -> LimiteDaApi:
    """A exceção que para o laço, com o que a API disse e quando retomar."""
    quando = f"; a janela volta em {falha.volta_em}" if falha.volta_em else ""
    return LimiteDaApi(f"A sessao do {papel} esbarrou no {falha.descricao}{quando}", {"papel": papel, "volta_em": falha.volta_em})
