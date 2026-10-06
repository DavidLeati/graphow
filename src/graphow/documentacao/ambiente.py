"""Configuração do Claude Code para o graphow: hooks, permissões e servidor da sessão.

Os hooks e os subagentes chamavam `graphow` sem caminho. Com o pacote num venv,
o executável só está no PATH de quem ativou o venv, e o processo do app desktop
não o acha: o hook falhava calado e a memória não chegava. Os blocos daqui saem
com o caminho do executável que está rodando, prontos para colar no
settings.json ou para o `graphow setup` mesclar nele.
"""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import sys

NOME_DO_EXECUTAVEL: str = "graphow"
NOME_DO_SERVIDOR_DA_SESSAO: str = "graphow"
TEMPO_LIMITE_DO_HOOK_S: int = 10

# Evento do Claude Code e a fase do `graphow harness` que ele dispara.
FASES_DOS_HOOKS: tuple[tuple[str, str], ...] = (
    ("SessionStart", "inicio"),
    ("SessionEnd", "fim"),
    ("SubagentStop", "subagente"),
)

# A sessão principal só lê sem perguntar: o servidor dela tem papel humano, e
# responder Question ou promover Aprendizado passa pela confirmação de quem a conduz.
FERRAMENTAS_DE_LEITURA_DA_SESSAO: tuple[str, ...] = (
    "ler_vista",
    "expandir_no",
    "buscar",
    "proximas_tarefas",
    "minhas_questoes",
    "aguardar_resposta",
)
SERVIDORES_DOS_SUBAGENTES: tuple[str, ...] = (
    "graphow-condutor",
    "graphow-executor",
    "graphow-revisor",
    "graphow-arbitro",
)
COMANDOS_DE_MEDICAO: tuple[str, ...] = ("base-colisoes", "orquestracao-medir", "transcricao-medir")

PADRAO_COMANDO_DO_AGENTE: re.Pattern[str] = re.compile(
    rf"^(?P<prefixo>[ \t]*command:[ \t]*){NOME_DO_EXECUTAVEL}(?=[ \t]*\r?$)", re.MULTILINE
)


def resolver_executavel() -> str:
    """O graphow ao lado do interpretador que roda (o do venv), senão o do PATH, senão o nome."""
    pasta = Path(sys.executable).parent
    for candidato in (pasta / f"{NOME_DO_EXECUTAVEL}.exe", pasta / NOME_DO_EXECUTAVEL):
        if candidato.is_file():
            return candidato.as_posix()
    no_path = shutil.which(NOME_DO_EXECUTAVEL)
    return Path(no_path).as_posix() if no_path else NOME_DO_EXECUTAVEL


def fixar_executavel_no_agente(definicao: str, executavel: str) -> str:
    """Troca o `command: graphow` do servidor MCP do subagente pelo caminho do executável."""
    if executavel == NOME_DO_EXECUTAVEL:
        return definicao
    return PADRAO_COMANDO_DO_AGENTE.sub(lambda casamento: f'{casamento["prefixo"]}"{executavel}"', definicao)


@dataclass(frozen=True)
class ConfiguracaoDoAmbiente:
    """O executável que hooks e servidores chamam e o autor da sessão principal."""

    executavel: str
    autor: str

    def hooks(self) -> dict[str, list[dict[str, object]]]:
        """Os três hooks do harness, no formato do bloco `hooks` do settings.json."""
        return {evento: [{"hooks": [self.hook(fase)]}] for evento, fase in FASES_DOS_HOOKS}

    def hook(self, fase: str) -> dict[str, object]:
        """Um hook de comando com argumentos em lista, sem shell no meio para citar caminho."""
        return {
            "type": "command",
            "command": self.executavel,
            "args": ["harness", "--fase", fase, "--entrada-hook"],
            "timeout": TEMPO_LIMITE_DO_HOOK_S,
        }

    def permissoes(self) -> tuple[str, ...]:
        """O que a orquestração usa sem parar em pedido de permissão."""
        leitura = tuple(f"mcp__{NOME_DO_SERVIDOR_DA_SESSAO}__{nome}" for nome in FERRAMENTAS_DE_LEITURA_DA_SESSAO)
        subagentes = tuple(f"mcp__{servidor}" for servidor in SERVIDORES_DOS_SUBAGENTES)
        medicao = tuple(f"Bash({NOME_DO_EXECUTAVEL} {comando} *)" for comando in COMANDOS_DE_MEDICAO)
        return leitura + subagentes + medicao

    def bloco_do_settings(self) -> dict[str, object]:
        """O trecho do settings.json que liga hooks e permissões."""
        return {"permissions": {"allow": list(self.permissoes())}, "hooks": self.hooks()}

    def comando_do_servidor_da_sessao(self) -> str:
        """O `claude mcp add` que registra, uma vez por usuário, o servidor da sessão principal."""
        return (
            f'claude mcp add --scope user {NOME_DO_SERVIDOR_DA_SESSAO} -- "{self.executavel}" '
            f"mcp --papel humano --autor {self.autor}"
        )
