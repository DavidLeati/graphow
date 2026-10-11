"""Os tokens de uma execução, somados das transcrições que o Claude Code grava em disco.

O stream-json de uma sessão com subagentes não traz tudo o que eles gastaram,
e o `modelUsage` do resultado só existe quando a sessão chega ao fim. As
transcrições, sim: o Claude Code grava a da sessão em
`<projetos>/<pasta do projeto>/<sessão>.jsonl` e a de cada subagente em
`<sessão>/subagents/`. A busca é pelo id da sessão em qualquer pasta de
projeto, porque o nome da pasta deriva do caminho de trabalho e a regra dessa
derivação é do Claude Code.

A definição de tokens é a do laboratório (`graphow-lab/_runs/base.py`), para que
a linha de base seja comparável: entrada, saída e as duas de cache somadas,
cada mensagem do modelo contada uma vez, pela primeira entrada dela na
transcrição. O Claude Code repete a mensagem em uma entrada por bloco de
conteúdo, e só a última traz a saída final; contar pela primeira deixa de fora
uns 0,5% dos tokens, todos de saída. O desvio é o mesmo em toda arquitetura e
não muda a comparação; a última entrada também é somada, para conferir o custo
(ver `graphow.bancada.medicao`).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from graphow.harness.transcricao import ler_instante
from graphow.sessoes.leitura_stream import eventos_do_stream

PASTA_DE_PROJETOS_PADRAO: Path = Path.home() / ".claude" / "projects"
EXTENSAO_DA_TRANSCRICAO: str = ".jsonl"
CHAVES_DE_USO: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


@dataclass(frozen=True)
class TokensDasTranscricoes:
    """Os tokens contados pela primeira entrada de cada mensagem (a medida) e pela última (a conferência)."""

    pela_primeira: int = 0
    pela_ultima: int = 0
    arquivos: int = 0

    def somar(self, outro: "TokensDasTranscricoes") -> "TokensDasTranscricoes":
        """As duas contagens e os arquivos somados."""
        return TokensDasTranscricoes(
            self.pela_primeira + outro.pela_primeira, self.pela_ultima + outro.pela_ultima, self.arquivos + outro.arquivos
        )


def localizar_transcricoes(raiz: Path, sessao: str) -> tuple[Path, ...]:
    """A transcrição da sessão e as dos subagentes dela, em qualquer pasta de projeto sob a raiz."""
    if not sessao or not raiz.is_dir():
        return ()
    principais = sorted(raiz.glob(f"*/{sessao}{EXTENSAO_DA_TRANSCRICAO}"))
    subagentes = sorted(raiz.glob(f"*/{sessao}/**/*{EXTENSAO_DA_TRANSCRICAO}"))
    return (*principais, *subagentes)


def contar_tokens(arquivos: Iterable[Path], ate: datetime | None = None) -> TokensDasTranscricoes:
    """Os tokens das transcrições; com `ate`, só as mensagens até esse instante."""
    total = TokensDasTranscricoes()
    for arquivo in arquivos:
        total = total.somar(_contar_arquivo(arquivo, ate))
    return total


def _contar_arquivo(arquivo: Path, ate: datetime | None) -> TokensDasTranscricoes:
    """Uma transcrição: cada mensagem pela primeira e pela última entrada, dentro do corte."""
    primeiras: dict[str, Mapping[str, Any]] = {}
    ultimas: dict[str, Mapping[str, Any]] = {}
    with arquivo.open(encoding="utf-8", errors="replace") as linhas:
        for entrada in eventos_do_stream(linhas):
            identificador, uso = _uso_da_resposta(entrada, ate)
            if uso is not None:
                primeiras.setdefault(identificador, uso)
                ultimas[identificador] = uso
    return TokensDasTranscricoes(_somar_usos(primeiras.values()), _somar_usos(ultimas.values()), 1)


def _uso_da_resposta(entrada: Mapping[str, Any], ate: datetime | None) -> tuple[str, Mapping[str, Any] | None]:
    """O id e o uso de uma resposta do modelo dentro do corte; nada para o resto."""
    mensagem = entrada.get("message")
    if entrada.get("type") != "assistant" or not isinstance(mensagem, dict) or not isinstance(mensagem.get("usage"), dict):
        return "", None
    instante = ler_instante(entrada.get("timestamp"))
    if ate is not None and instante is not None and instante > ate:
        return "", None
    return str(mensagem.get("id") or entrada.get("uuid") or id(entrada)), mensagem["usage"]


def _somar_usos(usos: Iterable[Mapping[str, Any]]) -> int:
    """As quatro categorias de cada uso, somadas; o que não é inteiro conta zero."""
    return sum(_inteiro(uso.get(chave)) for uso in usos for chave in CHAVES_DE_USO)


def _inteiro(valor: object) -> int:
    """Contagem de tokens como inteiro."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
