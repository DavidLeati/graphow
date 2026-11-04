"""T3a5.1: o nome de programa montado na hora, que vira git sem citar a palavra, é recusado pelo hook.

São as sondas H1 e H2 da revisão da T3g2 e da T3a4: no Git Bash, `gi$()t -C
../humano checkout -- .` apagou a mudança não commitada de um repositório de
brinquedo, e nenhuma regra de `--disallowedTools` casa com esses comandos.
"""

from pathlib import Path

import pytest

from graphow.orquestrador.git_no_comando import decidir
from graphow.orquestrador.hook_do_git import CODIGO_DE_RECUSA
from graphow.orquestrador.trava_do_git import gravar_hook_da_trava, regras_que_negam_git

from tests.orquestrador.regras_do_claude_code import regras_que_casam
from tests.orquestrador.test_hook_do_git import _rodar_hook

# H1: o nome do git montado sem a palavra git.
MONTADOS: tuple[str, ...] = (
    "gi$()t -C ../humano checkout -- .",
    "gi${x:-}t -C ../humano checkout -- .",
    "g$@it -C ../humano checkout -- .",
    "/mingw64/bin/g?t.exe -C ../humano checkout -- .",
)
# H2: o `git.py`, que não cita git, com a extensão tirada na hora.
PELO_GIT_PY: tuple[str, ...] = (
    "v=git.py; ${v%.py} -C ../humano checkout -- .",
    "$(basename git.py .py) -C ../humano checkout -- .",
)
# A mesma classe pelas outras formas do cartão, num executor, no `find -exec`, no `hash -p` e dentro de uma função.
DA_MESMA_CLASSE: tuple[str, ...] = (
    "g$*it commit -qam x", "gi$'t' commit -qam x", "gi`echo`t commit -qam x", "g$1it commit -qam x", 'gi$""t commit -qam x',
    "{g..g}it commit -qam x", "gi[t] commit -qam x", "/usr/bin/gi*t commit -qam x", "gi$((0))t commit -qam x",
    "env gi$()t commit -qam x", "timeout 5 g$@it push", "xargs gi$()t add", "find . -exec gi$()t add {} \\;",
    'hash -p "$(command -v gi)t" g; g commit -qam x', "function f { git commit -qam x; }; f",
)
# A variável pura no nome segue liberada (opaca, recusada só quando o comando cita git), e as chaves sem expansão também.
LIBERADOS: tuple[str, ...] = (
    '"$PY" -m pytest -q', '"${PY}" -m pytest -q', "$PY -m pytest", '"$VENV/bin/python" -m pytest',
    "timeout $T python -m pytest", "xargs -I{} git log -1 {}", "find . -name '*.py' -exec grep -n x {} +",
    "git log --oneline @{u}..", "ls *.py | head -3",
)


@pytest.mark.parametrize("comando", MONTADOS + PELO_GIT_PY)
def test_nome_do_git_montado_na_hora_e_recusado_pelo_hook_edge_case(comando: str) -> None:
    """T3a5.1 (H1, H2): nenhuma regra casa com o disfarce, e o hook o recusa pelo nome montado."""
    decisao = decidir(comando)

    assert regras_que_casam(comando, regras_que_negam_git(("Bash",))) == []
    assert not decisao.permitido
    assert "nome do programa" in decisao.motivo and "quem commita e o orquestrador" in decisao.motivo


@pytest.mark.parametrize("comando", DA_MESMA_CLASSE)
def test_nome_montado_por_outra_expansao_ou_noutro_lugar_e_recusado_edge_case(comando: str) -> None:
    """T3a5.1: `$*`, `$'...'`, crase, `$1`, `$""`, chaves com `..`, glob e conta no nome; no executor, no `find -exec`,
    no `hash -p`; e o git no corpo de `function f { ... }`, que a trava lia como argumento de `f`."""
    decisao = decidir(comando)

    assert not decisao.permitido
    assert "quem commita e o orquestrador" in decisao.motivo


@pytest.mark.parametrize("comando", LIBERADOS)
def test_variavel_pura_no_nome_do_programa_segue_liberada_nominal(comando: str) -> None:
    """T3a5.1: `"$PY" -m pytest` passa, e com ele `${PY}`, `"$VENV/bin/python"`, o `{}` do xargs e do find e o `@{u}`."""
    assert decidir(comando).permitido, decidir(comando).motivo


def test_hook_do_settings_recusa_o_nome_montado_e_libera_o_py_nominal(tmp_path: Path) -> None:
    """T3a5.1: o hook chamado como o Claude Code o chama recusa `gi$()t -C ../humano checkout -- .` e libera `"$PY"`."""
    configuracao = gravar_hook_da_trava(tmp_path / "estado" / "goal-x")
    (tmp_path / "clone").mkdir()

    recusado = _rodar_hook(configuracao, MONTADOS[0], tmp_path / "clone")
    liberado = _rodar_hook(configuracao, '"$PY" -m pytest -q', tmp_path / "clone")

    assert recusado.returncode == CODIGO_DE_RECUSA and "nome do programa" in recusado.stderr.decode("utf-8")
    assert liberado.returncode == 0 and liberado.stderr == b""
