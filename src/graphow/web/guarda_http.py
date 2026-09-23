"""Guarda das requisições do canvas: de onde vêm, e se podem escrever como o humano.

O servidor escreve todo lote como o humano do servidor, e não pedia prova
nenhuma de quem chamava. Qualquer site aberto no navegador mandava um `POST`
com `Content-Type: text/plain`, que o navegador envia sem preflight, e criava
uma Constraint ou promovia um aprendizado como 'david (humano)'. E um domínio
que apontasse para 127.0.0.1 (DNS rebinding) lia o grafo inteiro, porque o
`Host` não era conferido.

Três conferências, na entrada de toda requisição:

- `Host` nomeia este servidor: um nome de loopback ou o host em que ele foi
  aberto. Aberto em todas as interfaces (`0.0.0.0`), qualquer nome passa, e a
  proteção da escrita fica com o token.
- `Origin`, quando vem, é a própria origem da página: `http://<Host>`.
- Escrita (`POST`, `PUT`, `DELETE`) traz o token da sessão no cabeçalho
  `X-Graphow-Token` e o corpo em `application/json`. Um cabeçalho próprio força
  o preflight, que este servidor não atende; o token vale mesmo se ele passar.

O token nasce com o servidor e chega à página por `/api/identity`, que só a
própria origem lê: o navegador não entrega a resposta a outro site.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
import secrets
import urllib.parse

CABECALHO_DO_TOKEN: str = "X-Graphow-Token"
METODOS_DE_ESCRITA: frozenset[str] = frozenset({"POST", "PUT", "DELETE"})
HOSTS_DE_LOOPBACK: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})
HOSTS_DE_TODAS_AS_INTERFACES: frozenset[str] = frozenset({"0.0.0.0", "::", ""})
TIPO_JSON: str = "application/json"


@dataclass(frozen=True)
class RecusaDaGuarda:
    """Por que a requisição não passou, com o status que a resposta leva."""

    status: HTTPStatus
    mensagem: str


@dataclass(frozen=True)
class GuardaHTTP:
    """Confere Host, Origin e, na escrita, o token e o tipo do corpo."""

    hosts_aceitos: frozenset[str]
    aceita_qualquer_host: bool = False
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))

    @classmethod
    def para_o_host(cls, host: str) -> "GuardaHTTP":
        """A guarda do servidor aberto nesse host, com um token novo."""
        return cls(
            hosts_aceitos=HOSTS_DE_LOOPBACK | {host.lower()},
            aceita_qualquer_host=host in HOSTS_DE_TODAS_AS_INTERFACES,
        )

    def avaliar(self, metodo: str, cabecalhos: Mapping[str, str]) -> RecusaDaGuarda | None:
        """Devolve a recusa da requisição, ou None quando ela pode seguir."""
        host = cabecalhos.get("Host", "")
        if not self._host_aceito(host):
            return RecusaDaGuarda(HTTPStatus.FORBIDDEN, f"Host '{host}' nao e este servidor")
        origem = cabecalhos.get("Origin")
        if origem is not None and origem != f"http://{host}":
            return RecusaDaGuarda(HTTPStatus.FORBIDDEN, f"Origem '{origem}' nao pode chamar este servidor")
        if metodo.upper() not in METODOS_DE_ESCRITA:
            return None
        return self._avaliar_escrita(cabecalhos)

    def _host_aceito(self, host: str) -> bool:
        """O nome do cabeçalho Host, sem a porta, é um dos nomes deste servidor."""
        if self.aceita_qualquer_host:
            return bool(host)
        nome = urllib.parse.urlsplit(f"//{host}").hostname or ""
        return nome in self.hosts_aceitos

    def _avaliar_escrita(self, cabecalhos: Mapping[str, str]) -> RecusaDaGuarda | None:
        """Escrita exige o token da sessão e o corpo em JSON."""
        enviado = cabecalhos.get(CABECALHO_DO_TOKEN, "")
        if not secrets.compare_digest(enviado.encode("utf-8"), self.token.encode("utf-8")):
            return RecusaDaGuarda(
                HTTPStatus.FORBIDDEN,
                f"Escrita sem o token desta sessao no cabecalho '{CABECALHO_DO_TOKEN}' (ver /api/identity)",
            )
        tipo = cabecalhos.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != TIPO_JSON:
            return RecusaDaGuarda(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, f"Corpo da escrita deve ser '{TIPO_JSON}'")
        return None
