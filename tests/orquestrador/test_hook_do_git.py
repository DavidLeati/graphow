"""O hook PreToolUse da trava do git: a tabela de comandos e o hook chamado como o Claude Code o chama."""

import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from graphow.orquestrador.git_no_comando import decidir
from graphow.orquestrador.hook_do_git import CODIGO_DE_RECUSA, decisao_da_entrada, responder
from graphow.orquestrador.trava_do_git import gravar_hook_da_trava, regras_que_negam_git

from tests.orquestrador.regras_do_claude_code import regras_que_casam

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
# T3a2: as leituras e as formas comuns que a T3a recusava e travavam fatias (sonda H2 da revisão).
LIBERADOS_NA_T3A2: tuple[str, ...] = (
    "git branch --show-current",
    "git branch -a -v",
    "git branch --list 'fase-*'",
    "git grep -n somar",
    "git ls-tree -r HEAD",
    "git rev-list --count HEAD",
    "git merge-base HEAD main",
    "git cat-file -p HEAD",
    "git stash list",
    "git stash show -p",
    "git remote -v",
    "git -c core.quotepath=off status",
    "git -c color.ui=never log -1",
    'case "$x" in a) echo 1;; esac',
    "case $1 in\n  a|b)\n    echo 1\n    ;;\n  *) git status;;\nesac",
    "if [ -f x ]; then case $1 in a) echo;; esac; fi",
    '"$PY" -m pytest -q',
    "find . -name '*.py' | xargs grep -n git",
    "timeout $T python -m pytest",
    "git log --format='%h|%s' | awk -F'|' '{print $1}'",
    "git diff | sed -n '1,5p'",
    "source .venv/Scripts/activate",
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
# T3a2: o git disfarçado que a T3a liberava (sondas H1, H1b e H1c da revisão; os sete primeiros commitaram de verdade).
COMMIT: str = "git commit -q --allow-empty -m invasor"
RECUSADOS_NA_T3A2: tuple[str, ...] = (
    f"coproc {COMMIT}; wait",
    f"coproc NOME {{ {COMMIT}; }}",
    f"bash /dev/stdin <<< '{COMMIT}'",
    f"source /dev/stdin <<< '{COMMIT}'",
    f". <(echo {COMMIT})",
    f"bash <(echo {COMMIT})",
    f"sh /dev/fd/0 <<< '{COMMIT}'",
    f"powershell -NoProfile -Command \"iex '{COMMIT}'\"",
    "pwsh -ExecutionPolicy Bypass -enc ZwBpAHQAIABjAG8AbQBtAGkAdAA=",
    f'hash -p "$(command -v git)" g; g {COMMIT[4:]}',
    "hash -p /bin/bash b; b -c 'echo'",
    f"coproc git -c core.hooksPath=/nada {COMMIT[4:]}; wait",
    "wsl git commit -am x",
    "npx -c 'git commit -am x'",
    "npm exec -- git commit -am x",
    "git-flow feature start x",
    "git-receive-pack .",
    "echo x | sed '1e git commit -am x'",
    "sed -n 's/.*/git commit -am x/e' f",
    "awk 'BEGIN{system(\"git commit -am x\")}'",
    "awk '{print | \"git commit -am x\"}' f",
    "git log -1 --format=%H HEAD~1 --output=.git/refs/heads/main",
    "git diff --outp=.git/refs/heads/main",
    "git grep -O vim somar",
    "git branch novo",
    "git stash",
    "git remote add outro x",
    "git -c core.pager=x log",
    "git -c core.fsmonitor=x status",
    "git -c core.hooksPath=x status",
    "git -c alias.st=x st",
    "git -c diff.x.command=y diff",
    "case x in a) git commit -am x;; esac",
    "echo 'git commit' | bash -s",
)
# T3a3: as leituras que seguiam recusadas e o `-C .` da sonda R1.
LIBERADOS_NA_T3A3: tuple[str, ...] = (
    "git --version",
    "git version",
    "git describe --tags --always",
    "git tag -l",
    "git tag --list 'v*' --sort=-creatordate",
    "git tag",
    "git tag --contains HEAD",
    "git config --get user.name",
    "git config --get-all remote.origin.url",
    "git config --list --show-origin",
    "git show-ref --heads",
    "git check-ignore -v build/",
    "git -C . status",
)
RECUSADOS_NA_T3A3: tuple[str, ...] = (
    "git tag v1",
    "git tag -d v1",
    "git tag -l -d v1",
    "git tag -a v1 -m x",
    "git config user.name x",
    "git config --get user.name --add x",
    "git config --unset user.name",
    "git config -e",
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


@pytest.mark.parametrize("comando", LIBERADOS_NA_T3A2)
def test_leituras_e_formas_comuns_que_travavam_fatias_passam_nominal(comando: str) -> None:
    """T3a2.3: as leituras do dia a dia (`branch --show-current`, `grep`, `stash list`...), `case`, `"$PY"`, `xargs grep git`."""
    assert decidir(comando).permitido, decidir(comando).motivo


@pytest.mark.parametrize("comando", RECUSADOS_NA_T3A2)
def test_git_disfarcado_por_executor_entrada_ou_opcao_que_grava_e_recusado_edge_case(comando: str) -> None:
    """T3a2.3: coproc, source, `<(...)`, /dev/stdin, PowerShell, hash -p, wsl, npx -c, git-*, sed e, awk system, --output."""
    decisao = decidir(comando)

    assert not decisao.permitido
    assert "quem commita e o orquestrador" in decisao.motivo


@pytest.mark.parametrize("comando", LIBERADOS_NA_T3A3)
def test_leituras_que_seguiam_recusadas_passam_nominal(comando: str) -> None:
    """T3a3.5: `--version`, `describe`, `tag -l`, `config --get`, `show-ref`, `check-ignore` e `git -C . status`."""
    assert decidir(comando).permitido, decidir(comando).motivo


@pytest.mark.parametrize("comando", RECUSADOS_NA_T3A3)
def test_tag_e_config_que_gravam_sao_recusados_edge_case(comando: str) -> None:
    """T3a3.5: a tag criada ou apagada e a configuração gravada seguem recusadas."""
    decisao = decidir(comando)

    assert not decisao.permitido
    assert "quem commita e o orquestrador" in decisao.motivo


@pytest.mark.parametrize("comando", (*PERMITIDOS, *LIBERADOS_NA_T3A2, *LIBERADOS_NA_T3A3))
def test_nenhuma_regra_do_disallowed_tools_casa_com_o_que_o_hook_libera_nominal(comando: str) -> None:
    """T3a3.2 (R1): o que o hook libera não casa, pelo prefixo e como o Claude Code casa, com regra de `--disallowedTools`.

    A sessão real aplica as regras antes do hook: uma que casasse recusaria a
    leitura liberada (`git branch --show-current`, `git -C . status`).
    """
    assert decidir(comando).permitido
    assert regras_que_casam(comando, regras_que_negam_git(("Bash",))) == []


@pytest.mark.parametrize(("comando", "casa"), [
    ("git push origin main", True), ("git push", True), ("FOO=1 git push", True), ("timeout 30 git push", True),
    ("nice -n 5 nohup git push", True), ("cd x && git push", True), ('echo "$(git push)"', True),
    ("for f in a; do git push; done", True), ("xargs git push", True), ("command git push", True),
    ("git -C . push origin main", False), ("/usr/bin/git push", False), ("sh -c 'git push'", False),
    ("git pushx", False), ("xargs -n1 git push", False), ("echo git push", False),
])
def test_leitura_das_regras_casa_como_a_documentacao_do_claude_code_edge_case(comando: str, casa: bool) -> None:
    """Caso de borda: a leitura que o teste usa casa `Bash(git push:*)` nos exemplos da documentação de permissões."""
    assert bool(regras_que_casam(comando, ("Bash(git push:*)",))) is casa


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
