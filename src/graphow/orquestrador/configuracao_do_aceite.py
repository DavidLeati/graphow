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

Enquanto a configuração do aceite está na área, uma marca na pasta do git do
clone lista o que trocou. O processo que cai no meio da rodada deixa a marca,
e a retomada volta esses arquivos à ponta antes de qualquer passo
(`restaurar_a_configuracao_entregue`, no começo de `Orquestrador._rodar`).
Sem isso, o pedido do humano atendido na retomada commitava a área com
`git add -A`, e a configuração do aceite ia para a branch do Goal no lugar
da entregue (sonda 2 da revisão da T2b+T2a2).
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Any

from graphow.orquestrador.aceite_intocado import SECOES_DE_TESTE, e_configuracao_de_teste
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.saida_do_aceite import dentro_do_aceite

CHAVES_DE_TESTE_DO_PACOTE: tuple[str, ...] = ("jest", "mocha", "vitest", "ava")
# Quanto do diff da configuração de teste vai ao verificador.
LIMITE_DO_DIFF_DA_CONFIGURACAO: int = 4000
# O arquivo, na pasta do git do clone, que lista o que a rodada do aceite trocou enquanto ela roda.
MARCA_DA_TROCA: str = "graphow-configuracao-do-aceite.json"


@contextmanager
def configuracao_do_aceite(area: Path, commit_do_aceite: str) -> Iterator[tuple[str, ...]]:
    """Enquanto o bloco roda, a configuração de teste é a do commit do aceite; devolve o que trocou e, no fim, volta à ponta."""
    trocas = trocas_da_configuracao(area, commit_do_aceite) if commit_do_aceite else {}
    _marcar(area, trocas)
    for caminho, conteudo in trocas.items():
        _escrever(area / caminho, conteudo)
    try:
        yield tuple(sorted(trocas))
    finally:
        _voltar_a_ponta(area, trocas)
        _marca(area).unlink(missing_ok=True)


def restaurar_a_configuracao_entregue(area: Path) -> tuple[str, ...]:
    """O que a rodada do aceite trocou e não desfez (o processo caiu no meio dela) volta à ponta; devolve o que voltou."""
    marca = _marca(area)
    if not marca.is_file():
        return ()
    trocados = tuple(str(caminho) for caminho in json.loads(marca.read_text(encoding="utf-8")))
    _voltar_a_ponta(area, dict.fromkeys(trocados))
    marca.unlink()
    return trocados


def _marca(area: Path) -> Path:
    """Onde fica a marca da troca: na pasta do git do clone, que nenhum commit leva e nenhum descarte apaga."""
    return area / GitDoGoal(area).rodar("rev-parse", "--git-path", MARCA_DA_TROCA).strip()


def _marcar(area: Path, trocas: Mapping[str, str | None]) -> None:
    """A marca com os caminhos trocados, gravada por inteiro (num arquivo à parte e depois renomeado) antes da troca."""
    if not trocas:
        return
    marca = _marca(area)
    provisoria = marca.with_name(marca.name + ".tmp")
    provisoria.write_text(json.dumps(sorted(trocas)), encoding="utf-8")
    os.replace(provisoria, marca)


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


def diff_da_configuracao(area: Path, commit_do_aceite: str) -> str:
    """O diff, do commit do aceite à ponta, de cada arquivo que configura o teste (conftest, pyproject, pytest.ini, setup.cfg...).

    O verificador julgava a diferença de configuração sem vê-la: o conftest
    que põe um módulo falso em `sys.modules`, junto do layout `src/`,
    passava por layout legítimo e fechava o Goal com o código errado (sonda 4
    da revisão da T2i+T2g). O diff inteiro do arquivo vai, a parte que não é
    de teste inclusive; o que passa do limite vai cortado, com o comando.
    """
    git = GitDoGoal(area)
    mudados = git.rodar("-c", "core.quotepath=false", "diff", "--name-only", "--no-renames", commit_do_aceite, "HEAD").splitlines()
    caminhos = [caminho for caminho in mudados if caminho and not dentro_do_aceite(caminho) and _de_teste(caminho)]
    if not caminhos:
        return ""
    diff = git.rodar("diff", "--no-color", "--no-ext-diff", "--no-renames", commit_do_aceite, "HEAD", "--",
                     *(f":(literal){caminho}" for caminho in caminhos)).strip()
    if len(diff) <= LIMITE_DO_DIFF_DA_CONFIGURACAO:
        return diff
    return (diff[:LIMITE_DO_DIFF_DA_CONFIGURACAO] + f"\n[cortado em {LIMITE_DO_DIFF_DA_CONFIGURACAO} caracteres; o resto com "
            f"`git diff {commit_do_aceite[:12]} HEAD -- {' '.join(caminhos)}`]")


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
