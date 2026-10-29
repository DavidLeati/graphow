"""Os testes de aceite rodam sempre da cópia intocada, sem arquivo solto do executor em `aceite/` nem configuração solta.

Mudar o teste de aceite não é o único jeito de neutralizá-lo: um
`aceite/conftest.py` que pula tudo, um `conftest.py` na raiz, o `addopts` do
pyproject, um `sitecustomize.py`, um módulo `pytest.py` que imita o runner
(na T2a, o que imprimia "1 passed" dava verde), um arquivo ignorado pelo git
(que o commit não mostra), ou as flags `skip-worktree` e `assume-unchanged`
do índice, que escondem a mudança do `git status`. As defesas, em camadas:

- antes de rodar os testes de aceite, `aceite/` volta ao commit do aceite, e o
  que o executor pôs lá (ignorado inclusive) sai; a configuração de teste
  solta (não versionada ou ignorada) em qualquer lugar sai também;
- a fatia que mexe em `aceite/`, ignorado inclusive, é recusada;
- a fatia que cria um arquivo ou uma pasta com o nome do módulo do runner
  ou de um que o pytest importa ao subir (`pytest`, `_pytest`, `pluggy`,
  `iniconfig`, `packaging`, `unittest`, como `.py` ou como pasta), em
  qualquer pasta fora do ambiente, é recusada sempre: qualquer pasta pode
  entrar no `sys.path` (a raiz, `src/`, o `pythonpath` do pytest, a pasta de
  cada teste sem `__init__.py`). E o aceite em Python roda com `-P`, sem a
  pasta atual no `sys.path` (orquestrador/saida_do_aceite.py);
- a configuração de teste versionada que o executor mudou não é recusada: o
  aceite roda com ela, sem contar como verde o teste pulado ou o que não
  rodou, e de novo com a do commit do aceite; o teste que muda de resultado
  vai ao verificador julgar (orquestrador/aceite_no_commit.py), e a fatia que
  a mudou vai à revisão de risco como sinal;
- antes do commit, as flags do índice são conferidas: as que houver são
  limpas e a fatia falha.

As pastas de dependências instaladas (`node_modules`, ambientes virtuais) não
são varridas: são do ambiente, e não do executor.
"""

from collections.abc import Iterable, Mapping, Sequence
import json
import os
from pathlib import Path
import shutil
import tomllib
from typing import Any

from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.saida_do_aceite import PASTA_DO_ACEITE, dentro_do_aceite, e_cache

NOMES_DE_CONFIGURACAO: frozenset[str] = frozenset({
    "conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml", "tox.ini", "sitecustomize.py", "usercustomize.py",
    ".mocharc.js", ".mocharc.cjs", ".mocharc.mjs", ".mocharc.json", ".mocharc.jsonc", ".mocharc.yml", ".mocharc.yaml", ".babelrc",
})
PREFIXOS_DE_CONFIGURACAO: tuple[str, ...] = ("jest.config.", "vitest.config.", "vitest.workspace.", "babel.config.", "jest.setup.")
SUFIXOS_DE_CONFIGURACAO: tuple[str, ...] = (".pth",)
# O módulo com o nome do runner, ou de um que ele importa ao subir, toma o lugar dele numa pasta do sys.path.
SOMBRAS_DO_RUNNER: frozenset[str] = frozenset({
    "pytest.py", "pytest", "_pytest.py", "_pytest", "pluggy.py", "pluggy", "iniconfig.py", "iniconfig", "packaging.py", "packaging",
    "unittest.py", "unittest", "py.py",
})
# Os arquivos que só em parte são configuração de teste: muda só se a parte de teste mudou.
SECOES_DE_TESTE: Mapping[str, tuple[str, ...]] = {"pyproject.toml": ("tool", "pytest"), "setup.cfg": ("tool:pytest",),
                                                  "package.json": ("scripts", "jest", "mocha", "vitest", "ava")}
PASTAS_DO_AMBIENTE: frozenset[str] = frozenset({"node_modules", ".venv", "venv", ".tox", ".nox", ".git", "site-packages"})


def _do_ambiente(caminho: str) -> bool:
    """O caminho está numa pasta de dependências instaladas (de qualquer ambiente virtual, pelo site-packages), fora de aceite/."""
    return bool(set(caminho.replace("\\", "/").split("/")) & PASTAS_DO_AMBIENTE) and not dentro_do_aceite(caminho)


def e_configuracao_de_teste(caminho: str) -> bool:
    """O caminho, relativo à raiz, é de um arquivo que muda como os testes rodam (pelo nome)."""
    partes = caminho.replace("\\", "/").strip("/").split("/")
    nome = partes[-1]
    return (
        nome in NOMES_DE_CONFIGURACAO or nome.startswith(PREFIXOS_DE_CONFIGURACAO) or nome.endswith(SUFIXOS_DE_CONFIGURACAO)
        or partes[0] in SOMBRAS_DO_RUNNER
    )


def configuracoes_mudadas(area: Path, caminhos: Iterable[str], *, antes: str) -> tuple[str, ...]:
    """Dos caminhos mudados desde o commit `antes`, os de configuração de teste (no pyproject e afins, só a parte de teste)."""
    return tuple(sorted({caminho for caminho in caminhos if _muda_os_testes(area, caminho, antes=antes)}))


def _muda_os_testes(area: Path, caminho: str, *, antes: str) -> bool:
    """O arquivo é de configuração de teste, ou é um dos mistos com a parte de teste mudada."""
    if e_configuracao_de_teste(caminho):
        return True
    nome = Path(caminho).name
    if nome not in SECOES_DE_TESTE:
        return False
    anterior = GitDoGoal(area).tentar("show", f"{antes}:{caminho}").saida
    atual = (area / caminho).read_text(encoding="utf-8", errors="replace") if (area / caminho).is_file() else ""
    return _secao(nome, anterior) != _secao(nome, atual)


def _secao(nome: str, conteudo: str) -> object:
    """A parte de teste do arquivo misto; o conteúdo inteiro quando ele não se lê (o que não se lê muda tudo)."""
    try:
        if nome == "pyproject.toml":
            return tomllib.loads(conteudo).get("tool", {}).get("pytest") if conteudo else None
        if nome == "package.json":
            dados: Mapping[str, Any] = json.loads(conteudo) if conteudo else {}
            scripts = {chave: valor for chave, valor in dados.get("scripts", {}).items() if "test" in chave}
            return [scripts, *(dados.get(chave) for chave in SECOES_DE_TESTE[nome][1:])]
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, AttributeError):
        return conteudo
    return _secao_ini(conteudo, "[tool:pytest]")


def _secao_ini(conteudo: str, cabecalho: str) -> str:
    """As linhas da seção do .cfg, do cabeçalho até a seção seguinte."""
    linhas = conteudo.splitlines()
    inicio = next((n for n, linha in enumerate(linhas) if linha.strip().lower() == cabecalho), None)
    if inicio is None:
        return ""
    fim = next((n for n in range(inicio + 1, len(linhas)) if linhas[n].strip().startswith("[")), len(linhas))
    return "\n".join(linhas[inicio:fim])


def sombra_do_runner(caminho: str) -> str:
    """O trecho do caminho até o primeiro nome que sombreia o runner (`src/pytest.py`, `tests/unittest`); vazio sem ele."""
    partes = caminho.replace("\\", "/").strip("/").split("/")
    indice = next((n for n, parte in enumerate(partes) if parte in SOMBRAS_DO_RUNNER), None)
    return "/".join(partes[: indice + 1]) if indice is not None and not _do_ambiente(caminho) else ""


def tirar_sombras_do_runner(area: Path, caminhos: Iterable[str], *, antes: str) -> tuple[str, ...]:
    """As sombras do runner que não existiam no commit `antes`, entre os caminhos e os arquivos fora do git: saem do disco.

    A sombra sai já, como as flags do índice: a ignorada pelo git ficaria na
    área e recusaria a tentativa seguinte também.
    """
    git = GitDoGoal(area)
    sombras = {sombra for caminho in (*caminhos, *_fora_do_git(area)) if (sombra := sombra_do_runner(caminho))}
    novas = tuple(sorted(sombra for sombra in sombras if git.tentar("cat-file", "-e", f"{antes}:{sombra}").codigo != 0))
    for sombra in novas:
        _apagar(area / sombra)
    return novas


def soltos_que_mudam_os_testes(area: Path) -> tuple[str, ...]:
    """Os arquivos fora do git (não versionados ou ignorados) que estão em aceite/, que configuram os testes ou sombreiam o runner."""
    return tuple(caminho for caminho in _fora_do_git(area) if (dentro_do_aceite(caminho) and not e_cache(caminho))
                 or e_configuracao_de_teste(caminho) or sombra_do_runner(caminho))


def _fora_do_git(area: Path) -> list[str]:
    """Cada arquivo não versionado ou ignorado da área; as pastas ignoradas são varridas, menos as do ambiente."""
    git = GitDoGoal(area)
    soltos = git.rodar("-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard").splitlines()
    ignorados = git.rodar("-c", "core.quotepath=false", "ls-files", "--others", "--ignored", "--exclude-standard",
                          "--directory").splitlines()
    arquivos = [linha for linha in [*soltos, *ignorados] if linha and not linha.endswith("/") and not _do_ambiente(linha)]
    for pasta in (linha.rstrip("/") for linha in ignorados if linha.endswith("/")):
        arquivos += _varrer(area, pasta)
    return arquivos


def _varrer(area: Path, pasta: str) -> list[str]:
    """Os arquivos da pasta ignorada, sem entrar nas pastas do ambiente."""
    if _do_ambiente(pasta):
        return []
    achados: list[str] = []
    for raiz, pastas, nomes in os.walk(area / pasta):
        relativa = Path(raiz).relative_to(area).as_posix()
        pastas[:] = [nome for nome in pastas if not _do_ambiente(f"{relativa}/{nome}")]
        achados += [f"{relativa}/{nome}" for nome in nomes]
    return achados


def preparar_o_aceite(area: Path, commit_do_aceite: str) -> tuple[str, ...]:
    """Antes de rodar os testes de aceite: aceite/ como no commit do aceite e a configuração solta fora; diz o que tirou."""
    git = GitDoGoal(area)
    soltos = soltos_que_mudam_os_testes(area)
    for caminho in soltos:
        _apagar(area / caminho)
    if commit_do_aceite:
        git.tentar("checkout", commit_do_aceite, "--", f"{PASTA_DO_ACEITE}/")
        git.tentar("clean", "-q", "-fdx", "--", f"{PASTA_DO_ACEITE}/")
    sinalizados = flags_do_indice(area)
    limpar_flags(area, sinalizados)
    return (*soltos, *sinalizados)


def _apagar(caminho: Path) -> None:
    """O arquivo, ou a pasta inteira, sai do disco."""
    if caminho.is_dir():
        shutil.rmtree(caminho, ignore_errors=True)
    else:
        caminho.unlink(missing_ok=True)


def forcar_o_aceite_no_indice(area: Path) -> tuple[str, ...]:
    """Os arquivos de aceite/ que o .gitignore do projeto ignora entram no índice à força (`git add -f`); devolve quais.

    Sem isso, o commit do aceite não os levava, a cópia intocada não os tinha,
    e a limpeza de aceite/ antes de rodar o aceite os apagava.
    """
    git = GitDoGoal(area)
    ignorados = git.rodar("-c", "core.quotepath=false", "ls-files", "--others", "--ignored", "--exclude-standard", "--",
                          f"{PASTA_DO_ACEITE}/").splitlines()
    forcados = tuple(caminho for caminho in ignorados if caminho and not e_cache(caminho))
    if forcados:
        git.rodar("add", "-f", "--", *forcados)
    return forcados


def flags_do_indice(area: Path) -> tuple[str, ...]:
    """Os arquivos com `skip-worktree` (S) ou `assume-unchanged` (letra minúscula) no índice: mudança que o status esconde."""
    linhas = GitDoGoal(area).rodar("-c", "core.quotepath=false", "ls-files", "-v").splitlines()
    return tuple(linha[2:] for linha in linhas if len(linha) > 2 and (linha[0] == "S" or linha[0].islower()))


def limpar_flags(area: Path, arquivos: Sequence[str]) -> None:
    """Tira as flags do índice dos arquivos, para o git voltar a ver o que mudou neles."""
    if arquivos:
        git = GitDoGoal(area)
        git.rodar("update-index", "--no-assume-unchanged", "--", *arquivos)
        git.rodar("update-index", "--no-skip-worktree", "--", *arquivos)
