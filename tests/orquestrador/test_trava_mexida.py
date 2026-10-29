"""A sessão de papel não desliga o hook da trava do git: nem pelo `.claude/` do clone, nem reescrevendo o settings do hook."""

import json
from pathlib import Path
import sys

from graphow.core.types import TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.trava_do_git import ARQUIVO_DO_HOOK, configuracao_do_hook

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import SOMA_CERTA, VERIFICAR, Bancada, executor_pronto, montar_bancada, roteiro_completo

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
DESLIGA: str = '{"disableAllHooks": true}'
# O executor que confere, de dentro da sessão, o `.claude/` do clone: o que há nele vai ao registro do falso.
VER_O_CLAUDE: str = "import os; print(sorted(os.listdir('.claude')) if os.path.isdir('.claude') else 'sem .claude')"


def _rodar(bancada: Bancada) -> None:
    """O Goal da spec no modo autônomo, até fechar."""
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    assert parada.fechou, parada.mensagem


def _notas_da_trava(bancada: Bancada) -> list[dict[str, object]]:
    """As Notes de trava mexida do livro-razão."""
    notas = bancada.kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    return [dict(nota.propriedades) for nota in notas if nota.propriedades.get("acao") == m.ACAO_DA_TRAVA_MEXIDA]


def _settings_recebidos(bancada: Bancada, papel: str) -> list[dict[str, object]]:
    """O settings do hook que cada sessão do papel leu ao abrir."""
    return [json.loads(chamada["settings"]) for chamada in bancada.chamadas(papel)]


def _primeira_fatia_falhou_com(bancada: Bancada, trecho: str) -> str:
    """A primeira fatia falhou uma vez, com o trecho no erro; devolve o .patch dela."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    fatia = estado.fatias[0]
    assert fatia.falhas == 1 and trecho in fatia.texto(m.CAMPO_ULTIMO_ERRO), fatia.texto(m.CAMPO_ULTIMO_ERRO)
    return fatia.texto(m.CAMPO_PATCH)


def test_fatia_que_cria_claude_settings_que_desliga_o_hook_e_recusada_edge_case(tmp_path: Path) -> None:
    """T3a2.1: o `.claude/settings.json` com `disableAllHooks: true` que a fatia criou a recusa, e sai do clone.

    O settings passado a cada sessão traz `disableAllHooks: false`, que vence o
    do projeto; a tentativa seguinte abre sem o `.claude/` e fecha o Goal.
    """
    roteiro = roteiro_completo()
    criou = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR, ".claude/settings.json": DESLIGA})
    certa = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}, comandos=[[sys.executable, "-c", VER_O_CLAUDE]])
    roteiro["executor"] = [criou, certa, *roteiro["executor"][1:]]
    bancada = montar_bancada(tmp_path, roteiro)

    _rodar(bancada)

    patch = _primeira_fatia_falhou_com(bancada, "a sessao criou ou mudou em .claude/ .claude/settings.json")
    assert ".claude/settings.json" in Path(patch).read_text(encoding="utf-8")
    assert all(settings["disableAllHooks"] is False for settings in _settings_recebidos(bancada, "executor"))
    assert bancada.chamadas("executor")[1]["comandos"][0]["saida"].strip() == "sem .claude"
    [nota] = _notas_da_trava(bancada)
    assert nota["papel"] == "executor" and ".claude/settings.json" in str(nota["motivo"])
    assert ".claude/settings.json" not in git(bancada.repositorio, "ls-files")


def test_claude_da_base_do_humano_continua_e_o_hook_segue_ligado_nominal(tmp_path: Path) -> None:
    """T3a2.1: o `.claude/` que já está na base é do humano: fica no clone em toda sessão, sem recusa nem Note.

    Mesmo com `disableAllHooks: true` nele, cada sessão recebe o hook com
    `disableAllHooks: false`, que vence o do projeto.
    """
    bancada = montar_bancada(tmp_path, _com_o_claude_visto(roteiro_completo()))
    (bancada.repositorio / ".claude").mkdir()
    (bancada.repositorio / ".claude" / "settings.json").write_text(DESLIGA, encoding="utf-8", newline="\n")
    git(bancada.repositorio, "add", ".claude")
    git(bancada.repositorio, "commit", "-q", "-m", "claude do humano")

    _rodar(bancada)

    assert _notas_da_trava(bancada) == []
    assert all(chamada["comandos"][0]["saida"].strip() == "['settings.json']" for chamada in bancada.chamadas("executor"))
    assert all(settings["disableAllHooks"] is False for settings in _settings_recebidos(bancada, "verificador"))
    assert git(bancada.repositorio, "show", "main:.claude/settings.json") == DESLIGA


def _com_o_claude_visto(roteiro: dict[str, list[dict[str, object]]]) -> dict[str, list[dict[str, object]]]:
    """O roteiro com cada executor listando o `.claude/` do clone de dentro da sessão."""
    roteiro["executor"] = [{**resposta, "comandos": [[sys.executable, "-c", VER_O_CLAUDE]]} for resposta in roteiro["executor"]]
    return roteiro


def test_sessao_que_reescreve_o_settings_do_hook_perde_o_trabalho_e_a_seguinte_o_recebe_integro_edge_case(tmp_path: Path) -> None:
    """T3a2.2 (sonda H4): o executor reescreve `../settings-da-trava.json` com `{}`, um comando que o hook libera.

    A tentativa não vale: o trabalho vai ao .patch, conta como falha e o motivo
    fica no livro-razão. A sessão seguinte recebe o settings regravado, com o
    hook PreToolUse e o `disableAllHooks: false`, e o Goal fecha.
    """
    roteiro = roteiro_completo()
    reescreve = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR, f"../{ARQUIVO_DO_HOOK}": "{}"})
    roteiro["executor"] = [reescreve, *roteiro["executor"]]
    bancada = montar_bancada(tmp_path, roteiro)

    _rodar(bancada)

    primeira, segunda = bancada.chamadas("executor")[:2]
    settings = Path(primeira["argv"][primeira["argv"].index("--settings") + 1])
    assert settings == Path(primeira["cwd"]).parent / ARQUIVO_DO_HOOK
    patch = _primeira_fatia_falhou_com(bancada, "a sessao reescreveu ou apagou o settings do hook da trava")
    assert "soma.py" in Path(patch).read_text(encoding="utf-8")
    assert json.loads(segunda["settings"]) == configuracao_do_hook()
    assert all(json.loads(chamada["settings"]) == configuracao_do_hook() for chamada in bancada.chamadas())
    assert json.loads(settings.read_text(encoding="utf-8")) == configuracao_do_hook()
    [nota] = _notas_da_trava(bancada)
    assert nota["papel"] == "executor" and "settings do hook" in str(nota["motivo"])
