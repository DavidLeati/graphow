"""A árvore que a conferência da fatia julga é a que o commit leva (revisão da T3g2, G1 e G3).

O índice é o que diz o que está rastreado: o arquivo que a base commitou com
`git add -f` contra o .gitignore só segue no `git add -A` enquanto está nele.
Na fatia de conflito, o índice fica na árvore mesclada até o commit; na fatia
normal, no HEAD, que já o rastreia.
"""

from pathlib import Path

import pytest

from graphow.orquestrador import execucao_da_fatia, modelo_do_goal as m, rebase_no_clone
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_base_que_andou import SOMA_DA_BASE_QUE_CONFLITA, SOMA_RESOLVIDA, ExecutorQueAndaABase, _roteiro_limpo
from tests.orquestrador.test_fatia_de_conflito import _fatia_de_conflito, _roteiro_com_a_fatia

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SETTINGS_DO_HUMANO: str = '{"permissions": {"allow": []}}\n'
SETTINGS_DO_EXECUTOR: str = '{"editor.tabSize": 4}\n'


def _commit(repositorio: Path, arquivos: dict[str, str], mensagem: str, *, forcar: bool = False) -> None:
    """O commit dos arquivos na branch aberta; com `forcar`, eles entram com `git add -f`, contra o .gitignore."""
    for nome, conteudo in arquivos.items():
        (repositorio / nome).parent.mkdir(parents=True, exist_ok=True)
        (repositorio / nome).write_text(conteudo, encoding="utf-8", newline="\n")
    git(repositorio, "add", "-A", *(["-f", *arquivos] if forcar else []))
    git(repositorio, "commit", "-q", "-m", mensagem)


def _humano_forca_depois_do_verificador(bancada: Bancada, ignorado: str) -> ExecutorQueAndaABase:
    """Depois da caçada, o humano muda soma.py (o conflito) e commita, com `git add -f`, o arquivo que o .gitignore ignora."""
    def humano() -> None:
        _commit(bancada.repositorio, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA}, "Humano muda a soma")
        _commit(bancada.repositorio, {ignorado: SETTINGS_DO_HUMANO}, "Humano forca o arquivo ignorado", forcar=True)
    return ExecutorQueAndaABase(bancada.executor, "verificador", humano)


def _espiar_a_conferencia(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """As árvores que a conferência da fatia comparou com a referência (`mudados_desde`), na ordem das tentativas."""
    julgadas: list[str] = []
    dentro: list[bool] = []
    guardar, mudados_desde = rebase_no_clone.guardar_a_arvore, rebase_no_clone.mudados_desde

    def guardar_espiado(area: Path) -> str:
        arvore = guardar(area)
        julgadas.extend([arvore] if dentro else [])
        return arvore

    def conferir(area: Path, referencia: str) -> tuple[str, ...]:
        dentro.append(True)
        try:
            return mudados_desde(area, referencia)
        finally:
            dentro.pop()

    monkeypatch.setattr(rebase_no_clone, "guardar_a_arvore", guardar_espiado)
    monkeypatch.setattr(execucao_da_fatia, "mudados_desde", conferir)
    return julgadas


def test_settings_ignorado_e_forcado_pela_base_chega_a_main_com_a_arvore_conferida_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3g4.1 (G3): o .gitignore ignora .claude/ e a base força o settings; a fatia de conflito o leva à main, e o commit
    dela tem a árvore, hash a hash, que a conferência julgou."""
    julgadas = _espiar_a_conferencia(monkeypatch)
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    _commit(bancada.repositorio, {".gitignore": ".claude/\n"}, "Ignora o .claude")
    executor = _humano_forca_depois_do_verificador(bancada, ".claude/settings.json")

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "show", "main:.claude/settings.json") == SETTINGS_DO_HUMANO
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_RESOLVIDA
    conflito = _fatia_de_conflito(bancada)
    assert conflito.status == "concluido" and conflito.falhas == 0
    commit = conflito.texto(m.CAMPO_COMMIT)
    assert julgadas and julgadas[-1] == git(bancada.repositorio, "rev-parse", f"{commit}^{{tree}}").strip()


def test_arquivo_ignorado_e_forcado_pela_base_fora_do_claude_nao_recusa_a_fatia_de_conflito_edge_case(tmp_path: Path) -> None:
    """T3g4.2 (G1): a base força um .vscode/settings.json que o .gitignore ignora; ele não conta como base desfeita, a fatia
    passa de primeira e ele chega à main."""
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    _commit(bancada.repositorio, {".gitignore": ".vscode/\n"}, "Ignora o .vscode")
    executor = _humano_forca_depois_do_verificador(bancada, ".vscode/settings.json")

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "show", "main:.vscode/settings.json") == SETTINGS_DO_HUMANO
    conflito = _fatia_de_conflito(bancada)
    assert conflito.status == "concluido" and conflito.falhas == 0, conflito.texto(m.CAMPO_ULTIMO_ERRO)


def test_fatia_normal_que_muda_o_arquivo_ignorado_e_rastreado_o_leva_ao_commit_nominal(tmp_path: Path) -> None:
    """T3g4 (item 2): na fatia normal o índice é o HEAD, que rastreia o .vscode/settings.json forçado; a mudança do executor
    nele vai ao commit da fatia e à main."""
    roteiro = _roteiro_limpo()
    roteiro["executor"][1] = executor_pronto({"README.md": "# brinquedo\nUse somar(a, b).\n",
                                              ".vscode/settings.json": SETTINGS_DO_EXECUTOR})
    bancada = montar_bancada(tmp_path, roteiro)
    _commit(bancada.repositorio, {".gitignore": ".vscode/\n", ".vscode/settings.json": SETTINGS_DO_HUMANO}, "Forca", forcar=True)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "show", "main:.vscode/settings.json") == SETTINGS_DO_EXECUTOR
