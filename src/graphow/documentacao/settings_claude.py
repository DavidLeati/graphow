"""Mescla dos hooks e das permissões do graphow no settings.json do Claude Code.

Colar o bloco à mão deixava duas armadilhas: o comando sem caminho, que o hook
do app desktop não acha, e a fiação duplicada quando alguém colava de novo
depois de atualizar. A mescla troca o hook do harness que já estiver lá, acrescenta só as
permissões que faltam, não toca no resto do arquivo e guarda uma cópia antes
de escrever.
"""

from dataclasses import dataclass
import json
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.documentacao.ambiente import NOME_DO_EXECUTAVEL, ConfiguracaoDoAmbiente

SUFIXO_DA_COPIA: str = ".graphow.bak"
SUBCOMANDO_DO_HARNESS: str = "harness"


class SettingsInvalido(GraphowError):
    """O settings.json existe mas não é um objeto JSON: a mescla não sobrescreve o que não entende."""


@dataclass(frozen=True)
class ResultadoDaMescla:
    """Onde a mescla escreveu, a cópia que guardou e as permissões que acrescentou."""

    caminho: Path
    copia: Path | None
    permissoes_acrescentadas: tuple[str, ...]


def e_hook_do_harness(hook: object) -> bool:
    """Reconhece o hook do graphow harness nas duas formas: comando inteiro ou executável com args."""
    if not isinstance(hook, dict):
        return False
    comando = str(hook.get("command", ""))
    argumentos = hook.get("args", [])
    partes = comando.split() + ([str(argumento) for argumento in argumentos] if isinstance(argumentos, list) else [])
    return NOME_DO_EXECUTAVEL in comando and SUBCOMANDO_DO_HARNESS in partes


def _grupo_sem_o_harness(grupo: object) -> bool:
    """Um grupo de hooks que não contém nenhum hook do harness, e que por isso fica."""
    if not isinstance(grupo, dict):
        return True
    return not any(e_hook_do_harness(hook) for hook in grupo.get("hooks", []))


class MescladorDeSettings:
    """Lê o settings.json, mescla a configuração do graphow e grava, com cópia do anterior."""

    def __init__(self, caminho: Path, configuracao: ConfiguracaoDoAmbiente) -> None:
        self._caminho: Path = caminho
        self._configuracao: ConfiguracaoDoAmbiente = configuracao

    def mesclar(self) -> ResultadoDaMescla:
        """Escreve o settings mesclado e devolve o que mudou."""
        atual = self._ler()
        acrescentadas = self._mesclar_permissoes(atual)
        self._mesclar_hooks(atual)
        copia = self._guardar_copia()
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho.write_text(json.dumps(atual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return ResultadoDaMescla(caminho=self._caminho, copia=copia, permissoes_acrescentadas=acrescentadas)

    def _ler(self) -> dict[str, object]:
        """O settings atual, ou um objeto vazio quando o arquivo ainda não existe."""
        if not self._caminho.is_file():
            return {}
        try:
            conteudo = json.loads(self._caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise SettingsInvalido(
                f"{self._caminho} nao e JSON valido ({erro.msg}, linha {erro.lineno}): corrija-o antes do setup",
                {"caminho": str(self._caminho)},
            ) from erro
        if not isinstance(conteudo, dict):
            raise SettingsInvalido(f"{self._caminho} nao e um objeto JSON", {"caminho": str(self._caminho)})
        return conteudo

    def _mesclar_permissoes(self, atual: dict[str, object]) -> tuple[str, ...]:
        """Acrescenta ao `permissions.allow` só o que ainda não está lá, na ordem da configuração."""
        permissoes = atual.setdefault("permissions", {})
        if not isinstance(permissoes, dict):
            raise SettingsInvalido("'permissions' do settings.json nao e um objeto", {"caminho": str(self._caminho)})
        permitidas = permissoes.setdefault("allow", [])
        faltando = tuple(regra for regra in self._configuracao.permissoes() if regra not in permitidas)
        permitidas.extend(faltando)
        return faltando

    def _mesclar_hooks(self, atual: dict[str, object]) -> None:
        """Troca o hook do harness de cada evento pelo novo, preservando os hooks de outras ferramentas."""
        hooks = atual.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise SettingsInvalido("'hooks' do settings.json nao e um objeto", {"caminho": str(self._caminho)})
        for evento, grupos in self._configuracao.hooks().items():
            mantidos = [grupo for grupo in hooks.get(evento, []) if _grupo_sem_o_harness(grupo)]
            hooks[evento] = mantidos + grupos

    def _guardar_copia(self) -> Path | None:
        """Copia o settings anterior para o lado, antes de sobrescrever."""
        if not self._caminho.is_file():
            return None
        copia = self._caminho.with_name(self._caminho.name + SUFIXO_DA_COPIA)
        copia.write_bytes(self._caminho.read_bytes())
        return copia
