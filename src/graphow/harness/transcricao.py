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
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

CHAVES_DE_USO: Mapping[str, str] = {
    "input_tokens": "tokens_entrada",
    "output_tokens": "tokens_saida",
    "cache_read_input_tokens": "tokens_cache_leitura",
    "cache_creation_input_tokens": "tokens_cache_criacao",
}
MODELO_SINTETICO: str = "<synthetic>"
SUFIXO_DE_ASSUMIR_TAREFA: str = "__assumir_tarefa"
# Só estas linhas interessam; as outras nem passam pelo decodificador.
MARCAS_DE_LINHA_UTIL: tuple[str, ...] = ('"usage"', SUFIXO_DE_ASSUMIR_TAREFA)


@dataclass(frozen=True)
class ConsumoDaTranscricao:
    """O que uma execução gastou e em que trabalhou, pronto para virar propriedades do Run."""

    tokens: Mapping[str, int] = field(default_factory=dict)
    mensagens_de_modelo: int = 0
    modelos: tuple[str, ...] = field(default_factory=tuple)
    tarefas: tuple[str, ...] = field(default_factory=tuple)

    @property
    def modelo_principal(self) -> str:
        """O modelo que mais respondeu; vazio quando nenhum respondeu."""
        return self.modelos[0] if self.modelos else ""

    def em_propriedades(self) -> dict[str, Any]:
        """As propriedades do Run: tokens por categoria, modelos e as tarefas assumidas."""
        return {
            **dict(self.tokens),
            "mensagens_de_modelo": self.mensagens_de_modelo,
            "modelos_usados": list(self.modelos),
            "tarefas": list(self.tarefas),
        }


class AcumuladorDeConsumo:
    """Soma a transcrição entrada por entrada, contando cada mensagem do modelo uma vez só."""

    def __init__(self) -> None:
        self._usos: dict[str, Mapping[str, Any]] = {}
        self._modelos: dict[str, str] = {}
        self._tarefas: list[str] = []

    def acrescentar(self, entrada: Mapping[str, Any]) -> None:
        """Registra o uso, o modelo e as tarefas assumidas de uma entrada de resposta do modelo."""
        mensagem = entrada.get("message")
        if entrada.get("type") != "assistant" or not isinstance(mensagem, dict):
            return
        identificador = str(mensagem.get("id") or entrada.get("uuid") or len(self._usos))
        if isinstance(mensagem.get("usage"), dict):
            self._usos[identificador] = mensagem["usage"]
        modelo = mensagem.get("model")
        if isinstance(modelo, str) and modelo and modelo != MODELO_SINTETICO:
            self._modelos[identificador] = modelo
        self._tarefas.extend(_tarefas_assumidas(mensagem.get("content")))

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
        )


def ler_consumo(caminho: Path) -> ConsumoDaTranscricao | None:
    """O consumo da transcrição no caminho; None quando o arquivo não existe ou não se lê."""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    acumulador = AcumuladorDeConsumo()
    for linha in texto.splitlines():
        if any(marca in linha for marca in MARCAS_DE_LINHA_UTIL):
            acumulador.acrescentar(_carregar(linha))
    return acumulador.consolidar()


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


def _tarefas_assumidas(conteudo: object) -> tuple[str, ...]:
    """Os ids de Task das chamadas a `assumir_tarefa`, de qualquer servidor graphow."""
    if not isinstance(conteudo, list):
        return ()
    chamadas = (
        bloco.get("input")
        for bloco in conteudo
        if isinstance(bloco, dict) and bloco.get("type") == "tool_use"
        and str(bloco.get("name", "")).endswith(SUFIXO_DE_ASSUMIR_TAREFA)
    )
    return tuple(str(entrada["id_task"]) for entrada in chamadas if isinstance(entrada, dict) and entrada.get("id_task"))


def _carregar(linha: str) -> Mapping[str, Any]:
    """Uma entrada da transcrição; a linha que não é objeto JSON vira entrada vazia."""
    try:
        valor = json.loads(linha)
    except json.JSONDecodeError:
        return {}
    return valor if isinstance(valor, dict) else {}


def _inteiro(valor: object) -> int:
    """Contagem de tokens como inteiro; o que não é número conta zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
