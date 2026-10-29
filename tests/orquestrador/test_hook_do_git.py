"""O hook PreToolUse da trava do git: a tabela de comandos e o hook chamado como o Claude Code o chama."""

import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from graphow.orquestrador.git_no_comando import decidir
from graphow.orquestrador.hook_do_git import CODIGO_DE_RECUSA, decisao_da_entrada, responder
from graphow.orquestrador.trava_do_git import gravar_hook_da_trava

PERMITIDOS: tuple[str, ...] = (
    "git status",
    "git status --porcelain=v1 -uno",
    "git diff --stat HEAD~1 -- src/",
    "git diff --cached --name-only",
    "git log --oneline -5 --format='%h %s'",
    'git log --grep="fix(core)" --since=2.weeks',
    "git show HEAD:README.md",
    "git blame -L 10,20 src/a.py",
    "git ls-files -m --exclude-standard",
    "git rev-parse --abbrev-ref HEAD",
    "git --no-pager log -3",
    "git -C sub status",
    "git status && git diff | head -20",
    "cd sub && git log -1 2>&1 > /tmp/saida.txt",
    "echo $(git rev-parse HEAD)",
    "bash -c 'git log -1 --stat'",
    "grep -rn 'git commit' src",
    "echo git commit",
    "python -m pytest -q -p no:cacheprovider",
    "cat > f.py <<'EOF'\nimport os\n# git commit -am x\nEOF",
    "diff <(git show HEAD:a.py) a.py",
    "[ -f x ] && git status",
    "command -v git",
    "x=$(git status --short); echo $x",
    "echo ok # && git commit",
    "for f in a b; do git diff $f; done",
    'timeout 600 python -c "print([1, 2])"',
    "watch -n 5 'git status --short'",
)
RECUSADOS: tuple[str, ...] = (
    "git commit -m x",
    "git add .",
    "git push origin main",
    "FOO=1 git commit -am x",
    "cd x && git add .",
    "npm test || git reset --hard",
    "git status; git stash",
    "env git push",
    "env FOO=1 git commit",
    "command git commit",
    "exec git push",
    "/usr/bin/git commit",
    '"C:\\Program Files\\Git\\cmd\\git.exe" add .',
    "GIT.EXE COMMIT",
    'g"i"t commit',
    "(git commit)",
    "{ git commit; }",
    'bash -c "git commit -am x"',
    "sh -c 'cd x && git push'",
    "bash -lc 'git status && git checkout -- .'",
    "git -c user.name=x commit",
    "git -c core.pager=cat log",
    "git -C . commit",
    "GIT_DIR=/outro git log",
    "echo `git push`",
    "echo \"$(git commit -am x)\"",
    "git log $(git stash)",
    "$(echo git) commit",
    "$GIT commit",
    "xargs git add",
    "find . -name '*.py' -exec git add {} \\;",
    "timeout 10 git push",
    "env -S 'git push'",
    "watch 'git commit -am x'",
    "eval 'git commit'",
    "bash <<'EOF'\ngit commit -am x\nEOF",
    "echo 'git commit' | bash",
    'cmd /c "git commit"',
    'powershell -NoProfile -Command "git push"',
    "if git diff --quiet; then git commit -am x; fi",
    "git \\\n  commit",
    "git checkout -- arquivo.py",
    "git config user.name",
    'git status "',
    "git",
)


@pytest.mark.parametrize("comando", PERMITIDOS)
def test_leitura_do_git_e_comando_sem_git_passam_nominal(comando: str) -> None:
    """T3a.1: as leituras, com as opções delas, e o que não invoca git passam."""
    assert decidir(comando).permitido, decidir(comando).motivo


@pytest.mark.parametrize("comando", RECUSADOS)
def test_git_de_escrita_disfarcado_e_o_ilegivel_sao_recusados_edge_case(comando: str) -> None:
    """T3a.1: o git de escrita é recusado com prefixo, encadeado, embrulhado ou por caminho; o que não se lê também."""
    decisao = decidir(comando)

    assert not decisao.permitido
    assert "quem commita e o orquestrador" in decisao.motivo


def test_tabela_tem_ao_menos_trinta_comandos_nominal() -> None:
    """T3a.1: a tabela tem pelo menos 30 comandos, entre permitidos e recusados."""
    assert len(PERMITIDOS) + len(RECUSADOS) >= 30 and len(PERMITIDOS) >= 10 and len(RECUSADOS) >= 20


def test_motivo_diz_qual_git_foi_recusado_nominal() -> None:
    """O agente lê no motivo o subcomando recusado e o que passa."""
    motivo = decidir("cd x && FOO=1 git commit -am y").motivo

    assert "git commit recusado" in motivo and "status, diff, log, show, blame, ls-files, rev-parse" in motivo


def test_evento_que_nao_e_do_bash_passa_e_o_ilegivel_e_recusado_edge_case() -> None:
    """A ferramenta que não é Bash passa; o evento sem comando, ou que não é JSON, é recusado."""
    assert decisao_da_entrada(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "a"}})).permitido
    assert not decisao_da_entrada(json.dumps({"tool_name": "Bash", "tool_input": {}})).permitido
    assert not decisao_da_entrada("nao e json").permitido
    assert not decisao_da_entrada("[1, 2]").permitido


def test_responder_sai_com_dois_e_o_motivo_no_stderr_edge_case() -> None:
    """A recusa sai com código 2 e o motivo em UTF-8 no stderr; a liberação sai com 0 e nada no stderr."""
    erro = io.BytesIO()
    evento = {"tool_name": "Bash", "tool_input": {"command": "git push # ação"}}

    assert responder(io.BytesIO(json.dumps(evento).encode("utf-8")), erro) == CODIGO_DE_RECUSA
    assert "git push recusado" in erro.getvalue().decode("utf-8")
    vazio = io.BytesIO()
    assert responder(io.BytesIO(b'{"tool_name": "Bash", "tool_input": {"command": "git status"}}'), vazio) == 0
    assert vazio.getvalue() == b""


def _rodar_hook(configuracao: Path, comando: str, pasta: Path) -> subprocess.CompletedProcess[bytes]:
    """Roda o hook do settings como o Claude Code roda um hook de forma exec: o JSON do evento na entrada padrão."""
    [hook] = json.loads(configuracao.read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["hooks"]
    evento = {"session_id": "s", "cwd": str(pasta), "permission_mode": "bypassPermissions",
              "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": comando}}
    ambiente = {**os.environ, "PYTHONPATH": str(pasta), "GRAPHOW_DB": str(pasta / "descartavel.db")}
    return subprocess.run([hook["command"], *hook["args"]], input=json.dumps(evento).encode("utf-8"), cwd=pasta,
                          env=ambiente, capture_output=True, timeout=hook["timeout"], check=False)


def test_hook_pela_entrada_padrao_recusa_commit_disfarcado_e_libera_status_nominal(tmp_path: Path) -> None:
    """T3a.3: o hook do settings, chamado com o JSON na entrada padrão, recusa o commit disfarçado e libera o status.

    A pasta corrente e o PYTHONPATH têm um `graphow` plantado que liberaria
    tudo: quem responde é o módulo do pacote, não o do clone.
    """
    plantado = tmp_path / "clone" / "graphow" / "orquestrador"
    plantado.mkdir(parents=True)
    (plantado.parent / "__init__.py").write_text("", encoding="utf-8")
    (plantado / "__init__.py").write_text("", encoding="utf-8")
    (plantado / "hook_do_git.py").write_text("def responder() -> int:\n    return 0\n", encoding="utf-8")
    configuracao = gravar_hook_da_trava(tmp_path / "estado" / "goal-x")

    recusado = _rodar_hook(configuracao, "cd sub && FOO=1 env /usr/bin/git -C . commit -am x", tmp_path / "clone")
    liberado = _rodar_hook(configuracao, "git status --short", tmp_path / "clone")

    assert recusado.returncode == CODIGO_DE_RECUSA, recusado.stderr
    assert "git commit recusado" in recusado.stderr.decode("utf-8")
    assert liberado.returncode == 0 and liberado.stderr == b""
