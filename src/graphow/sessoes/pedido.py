"""O pedido de uma sessão `claude -p`: o comando que ela recebe e o ambiente em que roda.

O prompt vai pela entrada padrão, como nos scripts do laboratório: não passa
pelo limite de tamanho da linha de comando do Windows nem pela citação do
shell. A saída é sempre `stream-json` com `--verbose`, a única forma em que o
`claude -p` diz, evento a evento, o que a sessão fez, e da qual sai o custo.

O ambiente perde as variáveis `CLAUDE*`, `AI_AGENT` e `BAGGAGE`. Uma sessão
aberta de dentro de outra (o app desktop, um terminal do Claude Code) herda
delas a identidade da sessão mãe, e o `claude -p` filho se comporta como
subprocesso dela. Sem elas, a sessão é nova e independente.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

VARIAVEL_DO_BANCO: str = "GRAPHOW_DB"
PREFIXOS_REMOVIDOS: tuple[str, ...] = ("CLAUDE",)
NOMES_REMOVIDOS: frozenset[str] = frozenset({"AI_AGENT", "BAGGAGE"})
ARGUMENTOS_DE_SAIDA: tuple[str, ...] = ("--output-format", "stream-json", "--verbose")
SUFIXO_DA_SAIDA_DE_ERRO: str = ".err"
TEMPO_LIMITE_PADRAO_S: float = 3600.0


@dataclass(frozen=True)
class PedidoDeSessao:
    """O que uma sessão precisa para rodar e onde ela grava o que fez.

    `banco_graphow`, quando dado, vira o `GRAPHOW_DB` da sessão: os hooks do
    graphow instalados no Claude Code rodam em toda sessão, e sem isto
    escreveriam no banco do usuário. `argumentos_extras` vão ao fim do
    comando, para o que este pedido ainda não nomeia, e `ambiente_extra`
    entra no ambiente já limpo (o orquestrador põe ali a trava de git do
    executor).
    """

    prompt: str
    pasta: Path
    arquivo_stream: Path
    modelo: str = ""
    modo_de_permissao: str = ""
    ferramentas_permitidas: tuple[str, ...] = ()
    retomar: str = ""
    banco_graphow: Path | None = None
    tempo_limite_s: float = TEMPO_LIMITE_PADRAO_S
    argumentos_extras: tuple[str, ...] = ()
    ambiente_extra: Mapping[str, str] = field(default_factory=dict)

    @property
    def arquivo_erro(self) -> Path:
        """A saída de erro do processo, ao lado do stream."""
        return self.arquivo_stream.with_name(self.arquivo_stream.name + SUFIXO_DA_SAIDA_DE_ERRO)


def montar_comando(executavel: Sequence[str], pedido: PedidoDeSessao) -> tuple[str, ...]:
    """A linha de comando da sessão; o prompt fica de fora, porque vai pela entrada padrão."""
    opcionais = (
        ("--model", pedido.modelo),
        ("--permission-mode", pedido.modo_de_permissao),
        ("--allowedTools", ",".join(pedido.ferramentas_permitidas)),
        ("--resume", pedido.retomar),
    )
    pares = tuple(parte for opcao, valor in opcionais if valor for parte in (opcao, valor))
    return (*executavel, "-p", *pares, *ARGUMENTOS_DE_SAIDA, *pedido.argumentos_extras)


def limpar_ambiente(ambiente: Mapping[str, str], pedido: PedidoDeSessao) -> dict[str, str]:
    """O ambiente da sessão: o recebido sem as variáveis da sessão mãe, com o banco pedido e os extras."""
    limpo = {nome: valor for nome, valor in ambiente.items() if not _eh_da_sessao_mae(nome)}
    if pedido.banco_graphow is not None:
        limpo[VARIAVEL_DO_BANCO] = str(pedido.banco_graphow)
    return {**limpo, **pedido.ambiente_extra}


def _eh_da_sessao_mae(nome: str) -> bool:
    """`CLAUDE*`, `AI_AGENT` e `BAGGAGE`, sem distinguir caixa, como o Windows não distingue."""
    maiusculo = nome.upper()
    return maiusculo in NOMES_REMOVIDOS or maiusculo.startswith(PREFIXOS_REMOVIDOS)
