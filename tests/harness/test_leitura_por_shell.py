"""Os caminhos lidos por comandos de shell: só leitores conhecidos, só o que parece caminho, e na dúvida nada."""

import pytest

from graphow.harness.leitura_por_shell import caminhos_lidos_no_comando


@pytest.mark.parametrize(
    ("comando", "esperados"),
    [
        ('cd /c/x; sed -n 1,80p src/a.py; grep -n "x" -r src/b.py | head', ("src/a.py", "src/b.py")),
        ("cat a.py > /tmp/o.txt", ("a.py",)),
        ("cat a.py 2>&1 >> out.txt && wc -l b.py c.md", ("a.py", "b.py", "c.md")),
        ('rg -e "x" src/a.py lib', ("src/a.py",)),
        ("tail -n 40 C:/repo/log.txt || head -20 docs/x.md", ("C:/repo/log.txt", "docs/x.md")),
        (r'Get-Content "C:\a b\x.py" -TotalCount 5', (r"C:\a b\x.py",)),
        (r'Select-String -Pattern "x/y" -Path src\m.py', (r"src\m.py",)),
    ],
)
def test_leitores_conhecidos_dao_os_caminhos_lidos_nominal(comando: str, esperados: tuple[str, ...]) -> None:
    """Os comandos reais do executor: pipes e `;` separam, a flag e o redirecionamento não contam."""
    assert caminhos_lidos_no_comando(comando) == esperados


@pytest.mark.parametrize(
    "comando",
    [
        "grep -rn 'src/a.py' tests",
        "sed s/a/b/ ",
        'sed -i "s/a/b/" a.py',
        "head -n 20 $HOME/a.py",
        "tail -5 *.py",
        "git diff src/a.py",
        "echo hi > a.py",
        "python -m pytest tests/x.py",
        "cat <<EOF\ncat segredo.py\nEOF",
        'cat "a.py',
    ],
)
def test_na_duvida_nao_se_colhe_nada_edge_case(comando: str) -> None:
    """Caso de borda: padrão do grep, script do sed, edição, variável, curinga, não leitor, heredoc e aspas abertas."""
    assert caminhos_lidos_no_comando(comando) == ()
