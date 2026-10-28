"""A segunda rodada do aceite: com a configuração de teste do commit do aceite, quando o executor a mudou.

O executor pode precisar mudar a configuração de teste do projeto (um
`conftest.py` com uma fixture, o `addopts` do pyproject, o script de teste do
package.json), e a suíte do plano e o aceite rodam com o que ele deixou
(orquestrador/aceite_no_commit.py). Quando ela mudou, o aceite roda também com
a do commit do aceite: enquanto essa rodada roda, cada arquivo de
configuração de teste volta ao que era naquele commit, quem nasceu depois sai
e quem foi apagado volta; nos arquivos mistos (pyproject.toml, setup.cfg,
package.json) só a parte de teste volta, e o resto (as dependências, o `type`
do pacote) fica como o executor deixou. Depois, a área volta à ponta. O teste
que dá resultado diferente nas duas rodadas vai ao verificador, que julga se
a mudança é legítima; a fatia que a fez vai à revisão de risco, como sinal.
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any

from graphow.orquestrador.aceite_intocado import SECOES_DE_TESTE, e_configuracao_de_teste
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.saida_do_aceite import dentro_do_aceite

CHAVES_DE_TESTE_DO_PACOTE: tuple[str, ...] = ("jest", "mocha", "vitest", "ava")


@contextmanager
def configuracao_do_aceite(area: Path, commit_do_aceite: str) -> Iterator[tuple[str, ...]]:
    """Enquanto o bloco roda, a configuração de teste é a do commit do aceite; devolve o que trocou e, no fim, volta à ponta."""
    trocas = trocas_da_configuracao(area, commit_do_aceite) if commit_do_aceite else {}
    for caminho, conteudo in trocas.items():
        _escrever(area / caminho, conteudo)
    try:
        yield tuple(sorted(trocas))
    finally:
        _voltar_a_ponta(area, trocas)


def trocas_da_configuracao(area: Path, commit_do_aceite: str) -> dict[str, str | None]:
    """O conteúdo que cada arquivo de configuração de teste tem de ter durante o aceite (None: o arquivo sai)."""
    git = GitDoGoal(area)
    na_ponta, no_aceite = _arquivos(git, "HEAD"), _arquivos(git, commit_do_aceite)
    trocas: dict[str, str | None] = {}
    candidatos = (c for c in sorted(na_ponta | no_aceite) if not dentro_do_aceite(c) and _de_teste(c))
    for caminho in candidatos:
        agora, antes = _conteudo(git, "HEAD", caminho), _conteudo(git, commit_do_aceite, caminho)
        desejado = antes if e_configuracao_de_teste(caminho) else _misto(caminho, agora, antes)
        if desejado != agora:
            trocas[caminho] = desejado
    return trocas


def _de_teste(caminho: str) -> bool:
    """O arquivo é de configuração de teste, ou um misto que pode ter a parte de teste."""
    return e_configuracao_de_teste(caminho) or Path(caminho).name in SECOES_DE_TESTE


def _misto(caminho: str, agora: str | None, antes: str | None) -> str | None:
    """O misto da ponta com a parte de teste do commit do aceite; o que não existe na ponta fica como está."""
    return MISTOS[Path(caminho).name](agora, antes or "") if agora is not None else None


def _arquivos(git: GitDoGoal, revisao: str) -> set[str]:
    """Os arquivos versionados na revisão."""
    return set(git.rodar("-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", revisao).splitlines())


def _conteudo(git: GitDoGoal, revisao: str, caminho: str) -> str | None:
    """O texto do arquivo na revisão; None quando ele não existe nela."""
    feito = git.tentar("show", f"{revisao}:{caminho}")
    return feito.saida if feito.codigo == 0 else None


def _escrever(caminho: Path, conteudo: str | None) -> None:
    """O arquivo com o conteúdo dado, ou fora da área."""
    if conteudo is None:
        caminho.unlink(missing_ok=True)
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")


def _voltar_a_ponta(area: Path, trocas: Mapping[str, str | None]) -> None:
    """Cada arquivo trocado volta ao da ponta; o que não existe nela sai."""
    git = GitDoGoal(area)
    na_ponta = _arquivos(git, "HEAD")
    for caminho in trocas:
        if caminho in na_ponta:
            git.rodar("checkout", "HEAD", "--", caminho)
        else:
            (area / caminho).unlink(missing_ok=True)


def _tabelas(texto: str, de_teste: Callable[[str], bool]) -> tuple[list[str], list[str]]:
    """As linhas fora das tabelas de teste e as das tabelas de teste, de um TOML ou de um .cfg."""
    fora: list[str] = []
    dentro: list[str] = []
    atual = fora
    for linha in texto.splitlines():
        cabecalho = linha.strip()
        if cabecalho.startswith("[") and cabecalho.endswith("]"):
            atual = dentro if de_teste(cabecalho.strip("[]").strip()) else fora
        atual.append(linha)
    return fora, dentro


def _com_as_tabelas_do_aceite(de_teste: Callable[[str], bool]) -> Callable[[str, str], str]:
    """O arquivo da ponta com as tabelas de teste trocadas pelas do commit do aceite."""
    def misturar(agora: str, antes: str) -> str:
        fora, da_ponta = _tabelas(agora, de_teste)
        _, do_aceite = _tabelas(antes, de_teste)
        if [linha.strip() for linha in da_ponta if linha.strip()] == [linha.strip() for linha in do_aceite if linha.strip()]:
            return agora
        return "\n".join([*fora, *do_aceite]).rstrip("\n") + "\n"
    return misturar


def _pacote_com_o_teste_do_aceite(agora: str, antes: str) -> str:
    """O package.json da ponta com os scripts de teste e as configurações de jest, mocha, vitest e ava do commit do aceite."""
    try:
        atual: dict[str, Any] = json.loads(agora)
        do_aceite: dict[str, Any] = json.loads(antes) if antes else {}
    except json.JSONDecodeError:
        return antes or agora
    scripts = {k: v for k, v in dict(atual.get("scripts") or {}).items() if "test" not in k}
    scripts.update({k: v for k, v in dict(do_aceite.get("scripts") or {}).items() if "test" in k})
    misturado = {**{k: v for k, v in atual.items() if k not in CHAVES_DE_TESTE_DO_PACOTE},
                 **{k: do_aceite[k] for k in CHAVES_DE_TESTE_DO_PACOTE if k in do_aceite}}
    if scripts or "scripts" in atual:
        misturado["scripts"] = scripts
    resultado = json.dumps(misturado, ensure_ascii=False, indent=2) + "\n"
    return agora if json.loads(resultado) == atual else resultado


MISTOS: Mapping[str, Callable[[str, str], str]] = {
    "pyproject.toml": _com_as_tabelas_do_aceite(lambda nome: nome.startswith("tool.pytest")),
    "setup.cfg": _com_as_tabelas_do_aceite(lambda nome: nome == "tool:pytest"),
    "package.json": _pacote_com_o_teste_do_aceite,
}
