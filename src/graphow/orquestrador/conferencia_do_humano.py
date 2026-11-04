"""A conferência do repositório do humano depois de cada sessão de papel: a perda para o laço, o avanço segue.

O orquestrador trabalha num clone para o humano seguir trabalhando ao lado,
e não há como saber quem mexeu no repositório dele durante a sessão. Por isso
a conferência (orquestrador/foto_do_humano.py, a foto de antes e a de depois)
mira a perda de trabalho, e não toda mudança. É perda, que para o laço em
FALHA com o motivo `repositorio_do_humano_mexido`, a salvaguarda e o comando
que a recupera:
- o arquivo listado antes (mudado ou não rastreado) que sumiu, ou cujo
  conteúdo voltou ao do HEAD ou do índice de antes; o que o humano commitou
  segue na árvore e não conta;
- o arquivo rastreado que sumiu sem a remoção ir a um commit;
- a entrada do índice com mudança preparada que voltou à do HEAD ou saiu;
- a ref apagada ou que andou fora de fast-forward;
- um arquivo que muda o que o git roda (orquestrador/arquivos_do_git.py: a
  configuração, os includes, os hooks, o exclude e o reflog do stash): um
  `core.hooksPath` plantado roda código do agente no próximo commit do
  humano, e um `core.fsmonitor`, no próximo `git status`.
Esses arquivos são lidos primeiro, em bytes, antes de qualquer git no
repositório do humano; mudou algum, a parada vem dali, sem rodar mais git, e
diz qual arquivo mudou. Só com eles iguais a foto de depois roda o git.
É avanço, que segue com uma Note no livro-razão: o arquivo novo ou que mudou
para um conteúdo novo, a entrada nova no índice, a ref nova ou que andou por
fast-forward e a troca de HEAD, com as mudanças carregadas. Cada linha tem o
seu caso em tests/orquestrador/test_conferencia_do_humano.py.

O lado seguro tem custo: do humano, também param o `git stash` (o arquivo
volta ao HEAD), o `commit --amend`, o rebase, o `git config`, a edição da
configuração global ou de um hook versionado (husky, `.githooks/`) e o `mv`
de arquivo mudado ou solto; de outro Goal, o rebase da branch dele.
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.orquestrador.arquivos_do_git import AUSENTE, conteudo_do_arquivo, ler_os_arquivos_do_git
from graphow.orquestrador.foto_do_humano import NAO_RASTREADO, FotoDoHumano, fotografar_o_humano, soltos_da_salvaguarda
from graphow.orquestrador.git_da_foto import e_ancestral_no_humano
from graphow.orquestrador.salvaguarda_do_humano import Salvaguarda, comandos_de_recuperacao

MOTIVO_DA_PARADA: str = "repositorio_do_humano_mexido"
LIMITE_DE_MUDANCAS_NA_PARADA: int = 20
NO_HEAD: str = "voltou ao conteudo do HEAD ou do indice de antes da sessao"
SUMIU: str = "sumiu da arvore sem ir a um commit"
# Uma mudança da conferência: se é perda e o texto.
Mudanca = tuple[bool, str]


@dataclass(frozen=True)
class HumanoMexido:
    """O que mudou no repositório do humano durante a sessão, separado em perda e avanço, e a salvaguarda de antes dela.

    `soltos_perdidos` são os não rastreados que sumiram, os que a árvore da salvaguarda devolve; `git_mexido` diz que um
    arquivo que muda o git mudou, e `arvore_conferida`, que a foto de depois rodou (não roda quando aquele mudou).
    """

    repositorio: Path
    perdas: tuple[str, ...]
    avancos: tuple[str, ...]
    salvaguarda: Salvaguarda
    soltos_perdidos: tuple[str, ...] = ()
    git_mexido: bool = False
    arvore_conferida: bool = True

    @property
    def recuperar(self) -> tuple[str, ...]:
        """Os comandos que devolvem o de antes da sessão: o `fetch` da pasta da salvaguarda, o `stash apply` do rastreado e o
        `restore` do não rastreado."""
        return comandos_de_recuperacao(self.repositorio, self.salvaguarda, self.soltos_perdidos)


def resumo(mudancas: tuple[str, ...]) -> tuple[str, ...]:
    """As primeiras mudanças e quantas sobram."""
    sobra = len(mudancas) - LIMITE_DE_MUDANCAS_NA_PARADA
    return (*mudancas[:LIMITE_DE_MUDANCAS_NA_PARADA], *([f"e mais {sobra}"] if sobra > 0 else []))


# Quem guarda no livro-razão o repositório do humano que mudou: o papel, a fatia (vazia fora delas) e o que mudou.
RegistroDoHumanoMexido = Callable[[str, str, HumanoMexido], None]


class RepositorioDoHumanoMexido(GraphowError):
    """O repositório do humano perdeu trabalho durante a sessão de papel: o laço para em FALHA."""


def conferir_o_humano(antes: FotoDoHumano | None, papel: str, fatia: str, *, registrar: RegistroDoHumanoMexido | None = None) -> None:
    """Depois da sessão, a foto refeita; o que mudou vai ao livro-razão, e a perda para o laço (`RepositorioDoHumanoMexido`)."""
    if antes is None:
        return
    mexido = conferir_os_arquivos_do_git(antes) or conferir_as_fotos(
        antes, fotografar_o_humano(antes.repositorio, antes.listados, vigia=antes.vigia))
    if not mexido.perdas and not mexido.avancos:
        return
    if registrar is not None:
        registrar(papel, fatia, mexido)
    if mexido.perdas:
        raise RepositorioDoHumanoMexido(
            mensagem_da_parada(mexido, papel), {"repositorio": str(mexido.repositorio), "salvaguarda": mexido.salvaguarda.stash or "nenhuma",
                                                "soltos": mexido.salvaguarda.soltos or "nenhuma",
                                                "guardada_em": mexido.salvaguarda.pasta or "nenhuma"}
        )


def conferir_os_arquivos_do_git(antes: FotoDoHumano) -> HumanoMexido | None:
    """Os arquivos que mudam o git, relidos em bytes, sem processo; None quando nenhum mudou. Mudou algum, a perda são eles,
    e os não rastreados que sumiram vêm da leitura de cada um, também sem git."""
    mudancas = _do_git(antes.do_git, ler_os_arquivos_do_git(antes.vigia))
    if not mudancas:
        return None
    soltos = tuple(caminho for caminho in soltos_da_salvaguarda(antes) if conteudo_do_arquivo(antes.repositorio / caminho) == AUSENTE)
    return HumanoMexido(antes.repositorio, tuple(texto for _, texto in mudancas), (), antes.salvaguarda, soltos, git_mexido=True,
                        arvore_conferida=False)


def conferir_as_fotos(antes: FotoDoHumano, depois: FotoDoHumano) -> HumanoMexido:
    """O que mudou de uma foto para a outra, separado em perda e avanço."""
    e_ancestral = partial(e_ancestral_no_humano, antes.repositorio)
    do_git = _do_git(antes.do_git, depois.do_git)
    mudancas = [*_refs(antes, depois, e_ancestral), *_cabeca(antes, depois), *_arquivos(antes, depois), *do_git]
    soltos = tuple(caminho for caminho in soltos_da_salvaguarda(antes) if depois.conteudos.get(caminho) == AUSENTE)
    return HumanoMexido(antes.repositorio, tuple(texto for perda, texto in mudancas if perda),
                        tuple(texto for perda, texto in mudancas if not perda), antes.salvaguarda, soltos, git_mexido=bool(do_git))


def mensagem_da_parada(mexido: HumanoMexido, papel: str) -> str:
    """O motivo, a perda, a salvaguarda e os comandos que a recuperam."""
    partes = ([f"o commit {mexido.salvaguarda.stash} (as mudancas rastreadas)"] if mexido.salvaguarda.stash else []) + (
        [f"a arvore {mexido.salvaguarda.soltos} (os nao rastreados)"] if mexido.salvaguarda.soltos and mexido.soltos_perdidos else [])
    recuperar = ", depois ".join(f"`{comando}`" for comando in mexido.recuperar)
    salvaguarda = (f"A salvaguarda de antes da sessao e {' e '.join(partes)}, guardada fora do repositorio, em "
                   f"{mexido.salvaguarda.pasta}: recupere com {recuperar}." if partes
                   else "Antes da sessao nao havia o que salvaguardar desses arquivos.")
    return (f"{MOTIVO_DA_PARADA}: o repositorio do humano ({mexido.repositorio}) "
            f"{'teve mudado o que o git roda' if mexido.git_mexido else 'perdeu trabalho'} durante a sessao do {papel}: "
            f"{'; '.join(resumo(mexido.perdas))}. {salvaguarda}{_aviso_do_git(mexido)} Se foi voce quem mexeu durante a sessao, "
            "confira e rode o Goal de novo; se nao, a sessao mexeu fora do clone do Goal, e o que ela fez la nao foi desfeito.")


def _aviso_do_git(mexido: HumanoMexido) -> str:
    """O aviso dos arquivos que mudam o git: sem salvaguarda, e antes de qualquer git no repositório, inclusive a recuperação."""
    if not mexido.git_mexido:
        return ""
    conferida = "" if mexido.arvore_conferida else (" A conferencia parou antes de rodar git nesse repositorio: a arvore e o "
                                                     "indice nao foram conferidos.")
    return (f"{conferida} Os arquivos que mudam o que o git roda nao tem salvaguarda: confira-os e desfaca a mudanca antes de "
            "rodar qualquer git nesse repositorio, inclusive os comandos de recuperacao, que rodariam o que foi plantado.")


def _refs(antes: FotoDoHumano, depois: FotoDoHumano, e_ancestral: Callable[[str, str], bool]) -> Iterator[Mudanca]:
    """A ref apagada ou que andou fora de fast-forward é perda; a nova e a que andou por fast-forward, avanço."""
    for nome in sorted(set(antes.refs) | set(depois.refs)):
        era, agora = antes.refs.get(nome, ""), depois.refs.get(nome, "")
        if era == agora:
            continue
        if not agora or not era:
            yield (not agora, f"ref {nome} " + (f"apagada (era {era})" if era else f"nova ({agora})"))
            continue
        avancou = e_ancestral(era, agora)
        yield (not avancou, f"ref {nome} andou {'por' if avancou else 'fora de'} fast-forward ({era} -> {agora})")


def _cabeca(antes: FotoDoHumano, depois: FotoDoHumano) -> list[Mudanca]:
    """A troca de branch ou de commit do HEAD é avanço: as mudanças que ela não carregou contam nos arquivos."""
    return [] if antes.cabeca == depois.cabeca else [(False, f"HEAD: {antes.cabeca} -> {depois.cabeca}")]


def _arquivos(antes: FotoDoHumano, depois: FotoDoHumano) -> Iterator[Mudanca]:
    """Cada caminho listado numa das fotos: o conteúdo na árvore e, com mudança preparada, a entrada do índice."""
    for caminho in sorted(set(antes.listados) | set(depois.listados)):
        if caminho not in antes.listados:
            yield _listado_so_depois(caminho, antes, depois)
            continue
        yield from (mudanca for mudanca in (_na_arvore(caminho, antes, depois), _no_indice(caminho, antes, depois)) if mudanca)


def _listado_so_depois(caminho: str, antes: FotoDoHumano, depois: FotoDoHumano) -> Mudanca:
    """O caminho limpo ou novo antes, listado depois: o rastreado que sumiu é perda; o resto, avanço."""
    if caminho not in antes.indice:
        return False, f"{caminho} apareceu"
    if depois.conteudos.get(caminho) == AUSENTE:
        return True, f"{caminho} {SUMIU}"
    return False, f"{caminho} mudou para um conteudo novo"


def _na_arvore(caminho: str, antes: FotoDoHumano, depois: FotoDoHumano) -> Mudanca | None:
    """O conteúdo do arquivo listado antes: igual, nada; sumiu ou voltou ao do HEAD ou do índice, perda; novo, avanço."""
    agora = depois.conteudos.get(caminho, AUSENTE)
    if agora == antes.conteudos.get(caminho, AUSENTE):
        return None
    if agora == AUSENTE:
        return True, f"{caminho} {SUMIU}"
    era = antes.listados[caminho]
    objeto, da_arvore = _objeto_na_arvore(caminho, depois), era.no_indice if era.xy[1:] == "." else ""
    if objeto and objeto != da_arvore and objeto in (era.no_head, era.no_indice):
        return True, f"{caminho} {NO_HEAD}"
    return False, f"{caminho} mudou para um conteudo novo"


def _objeto_na_arvore(caminho: str, depois: FotoDoHumano) -> str:
    """O objeto que a árvore tem agora, quando o git o sabe: o do índice, se o arquivo está igual a ele; vazio se não."""
    agora = depois.listados.get(caminho)
    if agora is not None:
        return agora.no_indice if agora.tipo in ("1", "2") and agora.xy[1:] == "." else ""
    entradas = depois.indice.get(caminho, ())
    return entradas[0].split(" ")[1] if len(entradas) == 1 else ""


def _no_indice(caminho: str, antes: FotoDoHumano, depois: FotoDoHumano) -> Mudanca | None:
    """A entrada do índice com mudança preparada antes: igual, nada; voltou à do HEAD ou saiu, perda; nova, avanço."""
    era = antes.listados[caminho]
    entradas, agora = antes.indice.get(caminho, ()), depois.indice.get(caminho, ())
    if era.tipo == NAO_RASTREADO or era.xy[:1] == "." or agora == entradas:
        return None
    if not agora or agora == (era.entrada_do_head,):
        return True, f"indice {caminho}: a entrada {'saiu' if not agora else 'voltou a do HEAD'}"
    return False, f"indice {caminho}: entrada nova"


def _do_git(antes: Mapping[str, str], depois: Mapping[str, str]) -> list[Mudanca]:
    """O arquivo que muda o git e que apareceu, mudou ou sumiu: sempre perda."""
    nomes = sorted(set(antes) | set(depois))
    return [(True, f"{nome} mudou ({antes.get(nome, AUSENTE)} -> {depois.get(nome, AUSENTE)})")
            for nome in nomes if antes.get(nome, AUSENTE) != depois.get(nome, AUSENTE)]
