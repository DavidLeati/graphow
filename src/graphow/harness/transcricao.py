"""O consumo de uma execução lido da transcrição que o ambiente grava: tokens, modelos e tarefas.

O Run do harness guardava modelo, resumo e motivo, e nenhum token: comparar
configurações de modelo pelo que o harness grava era palpite. O ambiente anota
o `usage` de cada resposta do modelo na transcrição, mas repete a anotação em
cada bloco de conteúdo da mesma mensagem (dezenove entradas para seis
mensagens, medido numa transcrição real); a soma ingênua contaria em dobro.
Aqui cada mensagem conta uma vez, pelo seu id.

A forma da transcrição é interna ao ambiente e muda entre versões. A leitura é
defensiva: linha ilegível é ignorada, arquivo ausente devolve None, e o Run fica
sem tokens em vez de ficar com um número inventado.

Das chamadas a `assumir_tarefa` saem também os autores MCP: a resposta da
ferramenta traz o autor da conexão, que leva um sufixo por conexão. Um Run com
dois autores é um subagente cujo servidor MCP reiniciou no meio do trabalho, e
foi assim que a posse de uma tarefa ficou órfã.

A duração sai das pontas: toda entrada traz `timestamp`, e só a primeira e a
última datadas importam. O Run do subagente é um evento só, no fim dele, e sem
isto não tinha duração; a de um goal real foi lida à mão, rodada por rodada.

Sem consumo, a leitura diz por quê: arquivo ausente e arquivo que não se lê
são problemas diferentes, e antes os dois viravam o mesmo None.

Da transcrição sai também a cota do plano que a raiz declarou em texto: a do
despacho, na primeira mensagem do usuário, e a última que o modelo escreveu.
Qual delas vale depende de quem é o Run; ver harness/linha_de_cota.py.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from graphow.harness.linha_de_cota import MARCAS_DA_COTA, CotaDeclarada, ultima_cota

CHAVES_DE_USO: Mapping[str, str] = {
    "input_tokens": "tokens_entrada",
    "output_tokens": "tokens_saida",
    "cache_read_input_tokens": "tokens_cache_leitura",
    "cache_creation_input_tokens": "tokens_cache_criacao",
}
MODELO_SINTETICO: str = "<synthetic>"
SUFIXO_DE_ASSUMIR_TAREFA: str = "__assumir_tarefa"
CAMPO_AUTOR_DO_RECIBO: str = "autor"
# Só estas linhas interessam; as outras nem passam pelo decodificador.
MARCAS_DE_LINHA_UTIL: tuple[str, ...] = ('"usage"', SUFIXO_DE_ASSUMIR_TAREFA, '"tool_result"', *MARCAS_DA_COTA)
# Toda linha traz o instante; só se decodificam as das pontas, até achar um válido.
MARCA_DE_INSTANTE: str = '"timestamp"'
# O prompt do despacho é a primeira entrada do usuário; só a cabeça é decodificada até achá-la.
MARCA_DE_USUARIO: str = '"user"'
CAMPO_MOTIVO_SEM_CONSUMO: str = "motivo_sem_consumo"
MOTIVO_TRANSCRICAO_AUSENTE: str = "transcricao_ausente"
MOTIVO_ERRO_DE_LEITURA: str = "erro_de_leitura"


@dataclass(frozen=True)
class ConsumoDaTranscricao:
    """O que uma execução gastou e em que trabalhou, pronto para virar propriedades do Run."""

    tokens: Mapping[str, int] = field(default_factory=dict)
    mensagens_de_modelo: int = 0
    modelos: tuple[str, ...] = field(default_factory=tuple)
    tarefas: tuple[str, ...] = field(default_factory=tuple)
    autores_mcp: tuple[str, ...] = field(default_factory=tuple)
    inicio: datetime | None = None
    fim: datetime | None = None
    cota_do_despacho: CotaDeclarada | None = None
    ultima_cota_escrita: CotaDeclarada | None = None

    @property
    def modelo_principal(self) -> str:
        """O modelo que mais respondeu; vazio quando nenhum respondeu."""
        return self.modelos[0] if self.modelos else ""

    def em_propriedades(self) -> dict[str, Any]:
        """As propriedades do Run: tokens por categoria, modelos, tarefas assumidas, com que autores e quando."""
        return {
            **dict(self.tokens),
            "mensagens_de_modelo": self.mensagens_de_modelo,
            "modelos_usados": list(self.modelos),
            "tarefas": list(self.tarefas),
            "autores_mcp": list(self.autores_mcp),
            **self._duracao(),
        }

    def _duracao(self) -> dict[str, Any]:
        """Início, fim e duração em segundos; nada quando a transcrição não trouxe instante."""
        if self.inicio is None or self.fim is None:
            return {}
        return {
            "inicio": _em_iso(self.inicio),
            "fim": _em_iso(self.fim),
            "duracao_s": int((self.fim - self.inicio).total_seconds()),
        }


@dataclass(frozen=True)
class LeituraDaTranscricao:
    """O consumo lido ou, sem ele, o motivo: quem mede separa o arquivo ausente do ilegível."""

    consumo: ConsumoDaTranscricao | None = None
    motivo_sem_consumo: str = ""


class AcumuladorDeConsumo:
    """Soma a transcrição entrada por entrada, contando cada mensagem do modelo uma vez só."""

    def __init__(self) -> None:
        self._usos: dict[str, Mapping[str, Any]] = {}
        self._modelos: dict[str, str] = {}
        self._tarefas: list[str] = []
        self._chamadas_de_assumir: set[str] = set()
        self._autores: list[str] = []
        self._inicio: datetime | None = None
        self._fim: datetime | None = None
        self._cota_do_despacho: CotaDeclarada | None = None
        self._ultima_cota: CotaDeclarada | None = None

    def abrir_com(self, despacho: Mapping[str, Any]) -> None:
        """Lê a cota do prompt de despacho, a primeira entrada do usuário na transcrição do subagente."""
        mensagem = despacho.get("message")
        if isinstance(mensagem, dict):
            self._cota_do_despacho = ultima_cota("\n".join(_textos_do_conteudo(mensagem.get("content"))))

    def marcar_instante(self, entrada: Mapping[str, Any]) -> bool:
        """Estende a janela da execução até o instante da entrada; False quando ela não traz um válido."""
        instante = ler_instante(entrada.get("timestamp"))
        if instante is None:
            return False
        self._inicio = min(self._inicio or instante, instante)
        self._fim = max(self._fim or instante, instante)
        return True

    def acrescentar(self, entrada: Mapping[str, Any]) -> None:
        """Registra o uso, o modelo e as tarefas de uma resposta do modelo, e o autor que a ferramenta devolveu."""
        self.marcar_instante(entrada)
        mensagem = entrada.get("message")
        if not isinstance(mensagem, dict):
            return
        if entrada.get("type") == "user":
            self._autores.extend(_autores_devolvidos(mensagem.get("content"), self._chamadas_de_assumir))
            return
        if entrada.get("type") != "assistant":
            return
        identificador = str(mensagem.get("id") or entrada.get("uuid") or len(self._usos))
        if isinstance(mensagem.get("usage"), dict):
            self._usos[identificador] = mensagem["usage"]
        modelo = mensagem.get("model")
        if isinstance(modelo, str) and modelo and modelo != MODELO_SINTETICO:
            self._modelos[identificador] = modelo
        chamadas = _chamadas_de_assumir(mensagem.get("content"))
        self._chamadas_de_assumir.update(id_chamada for id_chamada, _ in chamadas if id_chamada)
        self._tarefas.extend(id_task for _, id_task in chamadas)
        self._ultima_cota = ultima_cota("\n".join(_textos_do_conteudo(mensagem.get("content")))) or self._ultima_cota

    def consolidar(self) -> ConsumoDaTranscricao:
        """Os totais do que foi acrescentado."""
        tokens = {
            destino: sum(_inteiro(uso.get(origem)) for uso in self._usos.values())
            for origem, destino in CHAVES_DE_USO.items()
        }
        modelos = tuple(modelo for modelo, _ in Counter(self._modelos.values()).most_common())
        return ConsumoDaTranscricao(
            tokens=tokens,
            mensagens_de_modelo=len(self._usos),
            modelos=modelos,
            tarefas=tuple(dict.fromkeys(self._tarefas)),
            autores_mcp=tuple(dict.fromkeys(self._autores)),
            inicio=self._inicio,
            fim=self._fim,
            cota_do_despacho=self._cota_do_despacho,
            ultima_cota_escrita=self._ultima_cota,
        )


def ler_consumo(caminho: Path) -> ConsumoDaTranscricao | None:
    """O consumo da transcrição no caminho; None quando o arquivo não existe ou não se lê."""
    return ler_transcricao(caminho).consumo


def ler_transcricao(caminho: Path) -> LeituraDaTranscricao:
    """O consumo da transcrição no caminho, ou o motivo de não haver um."""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return LeituraDaTranscricao(motivo_sem_consumo=MOTIVO_TRANSCRICAO_AUSENTE)
    except OSError:
        return LeituraDaTranscricao(motivo_sem_consumo=MOTIVO_ERRO_DE_LEITURA)
    linhas = texto.splitlines()
    acumulador = AcumuladorDeConsumo()
    for linha in linhas:
        if any(marca in linha for marca in MARCAS_DE_LINHA_UTIL):
            acumulador.acrescentar(_carregar(linha))
    _marcar_pontas(acumulador, linhas)
    _abrir_com_o_despacho(acumulador, linhas)
    return LeituraDaTranscricao(consumo=acumulador.consolidar())


def _marcar_pontas(acumulador: AcumuladorDeConsumo, linhas: list[str]) -> None:
    """A primeira e a última entrada datadas; o miolo não passa pelo decodificador só pelo instante."""
    for ordem in (linhas, reversed(linhas)):
        datadas = (linha for linha in ordem if MARCA_DE_INSTANTE in linha)
        next((linha for linha in datadas if acumulador.marcar_instante(_carregar(linha))), None)


def _abrir_com_o_despacho(acumulador: AcumuladorDeConsumo, linhas: list[str]) -> None:
    """A primeira entrada do usuário, decodificando da cabeça só até achá-la."""
    candidatas = (_carregar(linha) for linha in linhas if MARCA_DE_USUARIO in linha)
    despacho = next((entrada for entrada in candidatas if entrada.get("type") == "user"), None)
    if despacho is not None:
        acumulador.abrir_com(despacho)


def localizar_transcricao_do_subagente(caminhos: Mapping[str, str], id_agente: str) -> Path | None:
    """A transcrição do subagente: a que o hook indicar, ou a pasta `subagents` da sessão.

    O ambiente grava a transcrição principal em `<projeto>/<sessao>.jsonl` e a de
    cada subagente em `<projeto>/<sessao>/subagents/agent-<id>.jsonl`.
    """
    candidatos = [caminhos.get("agent_transcript_path", ""), caminhos.get("transcript_path", "")]
    principal = caminhos.get("transcript_path", "")
    if principal and id_agente:
        candidatos.append(str(Path(principal).with_suffix("") / "subagents" / f"agent-{id_agente}.jsonl"))
    existentes = [Path(candidato) for candidato in candidatos if candidato and _eh_do_agente(candidato, id_agente)]
    return next((caminho for caminho in existentes if caminho.is_file()), None)


def _eh_do_agente(candidato: str, id_agente: str) -> bool:
    """A transcrição do subagente leva o id dele no nome; a principal, não."""
    return bool(id_agente) and id_agente in Path(candidato).name


def _chamadas_de_assumir(conteudo: object) -> tuple[tuple[str, str], ...]:
    """O id de cada chamada a `assumir_tarefa`, de qualquer servidor graphow, com o id da Task."""
    if not isinstance(conteudo, list):
        return ()
    blocos = (
        bloco
        for bloco in conteudo
        if isinstance(bloco, dict) and bloco.get("type") == "tool_use"
        and str(bloco.get("name", "")).endswith(SUFIXO_DE_ASSUMIR_TAREFA)
    )
    return tuple(
        (str(bloco.get("id") or ""), str(bloco["input"]["id_task"]))
        for bloco in blocos
        if isinstance(bloco.get("input"), dict) and bloco["input"].get("id_task")
    )


def _autores_devolvidos(conteudo: object, chamadas: set[str]) -> tuple[str, ...]:
    """O autor que cada resposta de `assumir_tarefa` devolveu, pelo id da chamada que ela responde."""
    if not isinstance(conteudo, list):
        return ()
    respostas = (
        bloco.get("content")
        for bloco in conteudo
        if isinstance(bloco, dict) and bloco.get("type") == "tool_result" and str(bloco.get("tool_use_id", "")) in chamadas
    )
    recibos = (_carregar(texto) for resposta in respostas for texto in _textos_do_conteudo(resposta))
    return tuple(str(recibo[CAMPO_AUTOR_DO_RECIBO]) for recibo in recibos if recibo.get(CAMPO_AUTOR_DO_RECIBO))


def _textos_do_conteudo(resposta: object) -> tuple[str, ...]:
    """Os textos de uma mensagem ou de uma resposta de ferramenta, que o ambiente grava como texto solto ou como blocos."""
    if isinstance(resposta, str):
        return (resposta,)
    if not isinstance(resposta, list):
        return ()
    return tuple(str(bloco.get("text", "")) for bloco in resposta if isinstance(bloco, dict) and bloco.get("type") == "text")


def _carregar(linha: str) -> Mapping[str, Any]:
    """Uma entrada da transcrição, ou o recibo que uma ferramenta devolveu; o que não é objeto JSON vira vazio."""
    try:
        valor = json.loads(linha)
    except json.JSONDecodeError:
        return {}
    return valor if isinstance(valor, dict) else {}


def ler_instante(valor: object) -> datetime | None:
    """O instante ISO 8601 de uma entrada, em UTC; o que não se lê como instante vira None."""
    if not isinstance(valor, str) or not valor:
        return None
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instante.astimezone(timezone.utc) if instante.tzinfo else instante.replace(tzinfo=timezone.utc)


def _em_iso(instante: datetime) -> str:
    """O instante em ISO 8601, UTC, com milissegundos e o Z que o ambiente usa."""
    return instante.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _inteiro(valor: object) -> int:
    """Contagem de tokens como inteiro; o que não é número conta zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
