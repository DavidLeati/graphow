"""Configuração do Claude Code para o graphow: hooks, permissões e servidor da sessão.

Os hooks chamavam `graphow` sem caminho. Com o pacote num venv, o executável
só está no PATH de quem ativou o venv, e o processo do app desktop não o acha:
o hook falhava calado e a memória não chegava. Os blocos daqui saem com o
caminho do executável que está rodando, prontos para colar no settings.json ou
para o `graphow setup` mesclar nele.

O que versões anteriores mesclavam para a orquestração por subagentes (as
permissões dos servidores MCP de cada papel e o hook SubagentStop, que gravava
um Run por subagente que o condutor despachava) fica listado como obsoleto: a
mescla o tira do settings.json.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

NOME_DO_EXECUTAVEL: str = "graphow"
NOME_DO_SERVIDOR_DA_SESSAO: str = "graphow"
TEMPO_LIMITE_DO_HOOK_S: int = 10

# Evento do Claude Code e a fase do `graphow harness` que ele dispara.
FASES_DOS_HOOKS: tuple[tuple[str, str], ...] = (
    ("SessionStart", "inicio"),
    ("SessionEnd", "fim"),
)
# Eventos cujo hook do harness a mescla remove do settings.json.
EVENTOS_DE_HOOK_OBSOLETOS: tuple[str, ...] = ("SubagentStop",)

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
COMANDOS_DE_MEDICAO: tuple[str, ...] = ("base-colisoes", "orquestracao-medir", "transcricao-medir")
# As permissões dos servidores MCP por papel dos subagentes que saíram: a mescla as remove.
PERMISSOES_OBSOLETAS: tuple[str, ...] = (
    "mcp__graphow-condutor",
    "mcp__graphow-executor",
    "mcp__graphow-revisor",
    "mcp__graphow-arbitro",
)


def resolver_executavel() -> str:
    """O graphow ao lado do interpretador que roda (o do venv), senão o do PATH, senão o nome."""
    pasta = Path(sys.executable).parent
    for candidato in (pasta / f"{NOME_DO_EXECUTAVEL}.exe", pasta / NOME_DO_EXECUTAVEL):
        if candidato.is_file():
            return candidato.as_posix()
    no_path = shutil.which(NOME_DO_EXECUTAVEL)
    return Path(no_path).as_posix() if no_path else NOME_DO_EXECUTAVEL


@dataclass(frozen=True)
class ConfiguracaoDoAmbiente:
    """O executável que hooks e servidor chamam e o autor da sessão principal."""

    executavel: str
    autor: str

    def hooks(self) -> dict[str, list[dict[str, object]]]:
        """Os hooks do harness, no formato do bloco `hooks` do settings.json."""
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
        """O que a sessão do humano usa sem parar em pedido de permissão: ler o grafo e medir."""
        leitura = tuple(f"mcp__{NOME_DO_SERVIDOR_DA_SESSAO}__{nome}" for nome in FERRAMENTAS_DE_LEITURA_DA_SESSAO)
        medicao = tuple(f"Bash({NOME_DO_EXECUTAVEL} {comando} *)" for comando in COMANDOS_DE_MEDICAO)
        return leitura + medicao

    def bloco_do_settings(self) -> dict[str, object]:
        """O trecho do settings.json que liga hooks e permissões."""
        return {"permissions": {"allow": list(self.permissoes())}, "hooks": self.hooks()}

    def comando_do_servidor_da_sessao(self) -> str:
        """O `claude mcp add` que registra, uma vez por usuário, o servidor da sessão principal."""
        return (
            f'claude mcp add --scope user {NOME_DO_SERVIDOR_DA_SESSAO} -- "{self.executavel}" '
            f"mcp --papel humano --autor {self.autor}"
        )
