"""Leitura do JSON que o ambiente entrega na entrada padrão do hook.

O arquivo de hooks chamava `graphow harness` com `$CLAUDE_SESSION_ID` e
`$CLAUDE_MODEL`. Essas variáveis não existem: o hook recebe um objeto JSON na
entrada padrão e o identificador da sessão vem em `session_id`. Com a variável
vazia o comando escrevia no caminho `/nos/` e terminava em `IndexError` em vez
de recusar. Aqui a entrada é lida onde ela de fato chega, sem depender de `jq`
no PATH nem de variáveis que o ambiente nunca definiu.
"""

from dataclasses import dataclass
import json
import sys
from typing import IO, Any

CHAVE_SESSAO: str = "session_id"
CHAVE_MODELO: str = "model"
# O diretório em que o hook rodou nomeia o ambiente padrão da memória: o
# Projeto com o nome do repositório e o Setor `Memoria` dentro dele.
CHAVE_DIRETORIO: str = "cwd"
CHAVES_DE_IDENTIFICACAO_DO_MODELO: tuple[str, ...] = ("id", "display_name")

# O payload de início traz `source`; o de fim traz `reason`. Nenhum dos dois é
# garantido, e a ausência não impede o registro da execução.
CHAVES_DE_RESUMO: tuple[str, ...] = ("reason", "source", "hook_event_name")

MODELO_DESCONHECIDO: str = "desconhecido"


@dataclass(frozen=True)
class EntradaDeHook:
    """Os campos do payload do hook que o Graphow aproveita."""

    id_sessao: str = ""
    modelo: str = MODELO_DESCONHECIDO
    resumo: str = ""
    diretorio: str = ""

    @property
    def tem_sessao(self) -> bool:
        """Informa se a entrada trouxe um identificador de sessão utilizável."""
        return bool(self.id_sessao)


def interpretar_entrada_de_hook(texto: str) -> EntradaDeHook:
    """Converte o corpo do hook em DTO, tolerando entrada ausente ou malformada."""
    dados = _carregar_objeto(texto)
    if dados is None:
        return EntradaDeHook()
    return EntradaDeHook(
        id_sessao=str(dados.get(CHAVE_SESSAO, "")).strip(),
        modelo=_extrair_modelo(dados.get(CHAVE_MODELO)),
        resumo=_extrair_resumo(dados),
        diretorio=str(dados.get(CHAVE_DIRETORIO, "") or "").strip(),
    )


def ler_entrada_de_hook(fonte: IO[str]) -> EntradaDeHook:
    """Lê e interpreta o payload do hook a partir de um fluxo de texto."""
    return interpretar_entrada_de_hook(fonte.read())


def preparar_fluxos_do_hook(entrada: IO[str] | None = None, saida: IO[str] | None = None) -> None:
    """Põe a entrada e a saída padrão em UTF-8: o ambiente fala UTF-8, e o Windows abre os canos em cp1252.

    Sem isto um `cwd` com acento chega trocado, e a vista de retomada sai com
    os aprendizados corrompidos no contexto do agente. Fluxos que não sabem se
    reconfigurar, como os de teste, ficam como estão.
    """
    for fluxo in (entrada or sys.stdin, saida or sys.stdout):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8", errors="replace")


def _carregar_objeto(texto: str) -> dict[str, Any] | None:
    """Desserializa o corpo, devolvendo None para entrada vazia ou JSON inválido."""
    if not texto.strip():
        return None
    try:
        valor = json.loads(texto)
    except json.JSONDecodeError:
        return None
    return valor if isinstance(valor, dict) else None


def _extrair_modelo(valor: object) -> str:
    """Aceita o modelo como texto simples ou como objeto com identificador."""
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    if not isinstance(valor, dict):
        return MODELO_DESCONHECIDO
    return _primeiro_texto(valor, CHAVES_DE_IDENTIFICACAO_DO_MODELO) or MODELO_DESCONHECIDO


def _extrair_resumo(dados: dict[str, Any]) -> str:
    """Usa o motivo, a origem ou o nome do evento como resumo da fase."""
    return _primeiro_texto(dados, CHAVES_DE_RESUMO)


def _primeiro_texto(dados: dict[str, Any], chaves: tuple[str, ...]) -> str:
    """Primeiro valor textual não vazio entre as chaves consultadas, em ordem."""
    candidatos = (dados.get(chave) for chave in chaves)
    textos = [valor.strip() for valor in candidatos if isinstance(valor, str) and valor.strip()]
    return textos[0] if textos else ""
