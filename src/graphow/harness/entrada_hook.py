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

# O payload de início traz `source`; o de fim traz `reason`. É o motivo do
# disparo: vai para o Run, e nunca para o resumo da sessão, que é o que alguém
# declara. Nenhum dos dois é garantido, e a ausência não impede o registro.
CHAVES_DE_MOTIVO: tuple[str, ...] = ("reason", "source", "hook_event_name")

# A transcrição é de onde o harness lê os tokens da execução. No SubagentStop o
# payload diz também qual subagente terminou, e às vezes onde está a transcrição dele.
CHAVE_TRANSCRICAO: str = "transcript_path"
CHAVE_TRANSCRICAO_DO_AGENTE: str = "agent_transcript_path"
CHAVE_ID_AGENTE: str = "agent_id"
CHAVE_TIPO_AGENTE: str = "agent_type"

MODELO_DESCONHECIDO: str = "desconhecido"


@dataclass(frozen=True)
class EntradaDeHook:
    """Os campos do payload do hook que o Graphow aproveita."""

    id_sessao: str = ""
    modelo: str = MODELO_DESCONHECIDO
    motivo: str = ""
    diretorio: str = ""
    transcricao: str = ""
    transcricao_do_agente: str = ""
    id_agente: str = ""
    tipo_agente: str = ""

    @property
    def tem_sessao(self) -> bool:
        """Informa se a entrada trouxe um identificador de sessão utilizável."""
        return bool(self.id_sessao)

    def caminhos_de_transcricao(self) -> dict[str, str]:
        """Os caminhos como o ambiente os nomeia, para quem procura a transcrição de um subagente."""
        return {CHAVE_TRANSCRICAO: self.transcricao, CHAVE_TRANSCRICAO_DO_AGENTE: self.transcricao_do_agente}


def interpretar_entrada_de_hook(texto: str) -> EntradaDeHook:
    """Converte o corpo do hook em DTO, tolerando entrada ausente ou malformada."""
    dados = _carregar_objeto(texto)
    if dados is None:
        return EntradaDeHook()
    return EntradaDeHook(
        id_sessao=str(dados.get(CHAVE_SESSAO, "")).strip(),
        modelo=_extrair_modelo(dados.get(CHAVE_MODELO)),
        motivo=_extrair_motivo(dados),
        diretorio=_texto(dados, CHAVE_DIRETORIO),
        transcricao=_texto(dados, CHAVE_TRANSCRICAO),
        transcricao_do_agente=_texto(dados, CHAVE_TRANSCRICAO_DO_AGENTE),
        id_agente=_texto(dados, CHAVE_ID_AGENTE),
        tipo_agente=_texto(dados, CHAVE_TIPO_AGENTE),
    )


def _texto(dados: dict[str, Any], chave: str) -> str:
    """O valor da chave como texto sem espaços nas pontas; vazio quando ausente."""
    return str(dados.get(chave, "") or "").strip()


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


def _extrair_motivo(dados: dict[str, Any]) -> str:
    """O motivo do disparo: a razão do fim, a origem do início ou o nome do evento."""
    return _primeiro_texto(dados, CHAVES_DE_MOTIVO)


def _primeiro_texto(dados: dict[str, Any], chaves: tuple[str, ...]) -> str:
    """Primeiro valor textual não vazio entre as chaves consultadas, em ordem."""
    candidatos = (dados.get(chave) for chave in chaves)
    textos = [valor.strip() for valor in candidatos if isinstance(valor, str) and valor.strip()]
    return textos[0] if textos else ""
