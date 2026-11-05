"""A conferência do repositório do humano no fim de cada janela da foto: a perda para o laço, o avanço segue.

O orquestrador trabalha num clone para o humano seguir trabalhando ao lado,
e não há como saber quem mexeu no repositório dele durante a sessão. Por isso
a conferência (orquestrador/foto_do_humano.py, a foto de antes e a de depois)
mira a perda de trabalho, e não toda mudança. É perda, que para o laço em
FALHA com o motivo `repositorio_do_humano_mexido`, a salvaguarda e o comando
que a recupera:
- o conteúdo de antes de um arquivo listado (mudado ou não rastreado) que não
  está mais em lugar nenhum, nem na árvore, nem no índice novo, nem, no mesmo
  caminho, no HEAD novo ou na ponta de uma ref que andou na sessão, quando o
  arquivo sumiu ou agora tem um conteúdo que o git já tinha antes da sessão
  (o do HEAD, o do índice ou o de uma ponta de antes, no mesmo caminho). É o
  `checkout -- .`, o `checkout -f` e o `switch --discard-changes` de outra
  branch e o `reset --hard` para um descendente. O humano que commita e troca
  de branch não perde nada: o conteúdo está na ponta que andou. E o que ele
  escreve de novo (e commita) não é um conteúdo que o git já tinha;
- o mesmo para o conteúdo preparado no índice, que sai ou dá lugar a um que o
  git já tinha sem ficar na árvore, no índice, no HEAD nem numa ponta que andou;
- o arquivo rastreado limpo que sumiu sem a remoção ir a um commit;
- a ref apagada, ou que andou fora de fast-forward, salvo a branch de outro
  Goal do grafo no mesmo repositório que o rebase dele refez: o par de antes e
  de depois segue os rebases que o orquestrador dele registrou (Evidence
  `rebase_do_goal`, lida do grafo pelo leitor que a conferência recebe), e todo
  commit que sai da história traz `Graphow-Goal: <aquele Goal>` no bloco de
  trailers. Sem o leitor, a ref fora de fast-forward é perda;
- um arquivo que muda o que o git roda (orquestrador/arquivos_do_git.py: a
  configuração, os includes, os hooks, o exclude e o reflog do stash): um
  `core.hooksPath` plantado roda código do agente no próximo commit do
  humano, e um `core.fsmonitor`, no próximo `git status`.
Esses arquivos são lidos primeiro, em bytes, antes de qualquer git no
repositório do humano; mudou algum, a parada vem dali, sem rodar mais git, e
diz qual arquivo mudou. Só com eles iguais a foto de depois roda o git.
É avanço, que segue com uma Note no livro-razão: o arquivo novo ou que mudou
para um conteúdo novo (ou cujo conteúdo de antes ficou num commit), a entrada
nova no índice, a ref nova, a que andou por fast-forward ou que o rebase de
outro Goal refez e a troca de HEAD, com as mudanças carregadas. Cada linha tem
o seu caso em tests/orquestrador/test_conferencia_do_humano.py. A janela
(orquestrador/janela_do_humano.py) diz quando a foto de antes é tirada e
quando a conferência roda, e o que rodou no meio (orquestrador/humano_mexido.py).

O lado seguro tem custo: do humano, também param o `git stash` (o reflog
muda), o `commit --amend`, o rebase, o `git config`, a edição da configuração
global ou de um hook versionado (husky, `.githooks/`) e o `mv` de arquivo
mudado ou solto.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache, partial
from pathlib import Path

from graphow.orquestrador.arquivos_do_git import AUSENTE, conteudo_do_arquivo, ler_os_arquivos_do_git
from graphow.orquestrador.foto_do_humano import (
    NAO_RASTREADO,
    FotoDoHumano,
    commits_sem_o_goal,
    fotografar_o_humano,
    objetos_nos_commits,
    soltos_da_salvaguarda,
)
from graphow.orquestrador.git_da_foto import e_ancestral_no_humano
from graphow.orquestrador.git_do_goal import TRAILER_DO_GOAL
from graphow.orquestrador.humano_mexido import (
    HumanoMexido,
    RegistroDoHumanoMexido,
    RepositorioDoHumanoMexido,
    mensagem_da_parada,
    resumo,
)

NO_HEAD: str = "voltou ao conteudo do HEAD ou do indice de antes da sessao"
SUMIU: str = "sumiu da arvore sem ir a um commit"
SOBRESCRITO: str = "foi sobrescrito por um conteudo que o git ja tinha, e o de antes nao ficou em commit nem no indice"
NOVO: str = "mudou para um conteudo novo"
TROCADA: str = "foi trocada por um conteudo que o git ja tinha"
# Uma mudança da conferência: se é perda e o texto.
Mudanca = tuple[bool, str]


@dataclass(frozen=True)
class RamoDeOutroGoal:
    """A branch (`refs/heads/<ramo>`) de outro Goal do grafo no mesmo repositório e o par (antes, depois) de cada rebase que o
    orquestrador dele registrou, pela ordem."""

    goal: str
    ref: str
    rebases: tuple[tuple[str, str], ...] = ()


# Quem lê do grafo as branches dos outros Goals do repositório dado (orquestrador/registro_do_rebase.py).
LeitorDosOutrosGoals = Callable[[Path], Sequence[RamoDeOutroGoal]]


@dataclass(frozen=True)
class _Conferencia:
    """As duas fotos e o que a conferência consulta no git do humano: a história, as branches dos outros Goals (lidas do grafo
    uma vez, só quando uma ref anda fora de fast-forward) e o objeto de cada caminho nos commits de antes e de depois."""

    antes: FotoDoHumano
    depois: FotoDoHumano
    e_ancestral: Callable[[str, str], bool]
    ramos: Callable[[], Mapping[str, RamoDeOutroGoal]]
    objetos: Mapping[tuple[str, str], str] = field(default_factory=dict)


def conferir_o_humano(antes: FotoDoHumano | None, papel: str, fatia: str, *, registrar: RegistroDoHumanoMexido | None = None,
                      outros_goals: LeitorDosOutrosGoals | None = None) -> None:
    """Depois da sessão, a foto refeita; o que mudou vai ao livro-razão, e a perda para o laço (`RepositorioDoHumanoMexido`)."""
    relatar(mexido_desde(antes, outros_goals), papel, fatia, registrar=registrar)


def mexido_desde(antes: FotoDoHumano | None, outros_goals: LeitorDosOutrosGoals | None = None) -> HumanoMexido | None:
    """O que mudou desde a foto de antes: os arquivos do git relidos e, iguais eles, a foto refeita; None sem foto."""
    if antes is None:
        return None
    return conferir_os_arquivos_do_git(antes) or conferir_as_fotos(
        antes, fotografar_o_humano(antes.repositorio, antes.listados, vigia=antes.vigia), outros_goals)


def relatar(mexido: HumanoMexido | None, papel: str, fatia: str, *, registrar: RegistroDoHumanoMexido | None = None) -> None:
    """O que mudou vai ao livro-razão, e a perda para o laço (`RepositorioDoHumanoMexido`); sem mudança, nada."""
    if mexido is None or (not mexido.perdas and not mexido.avancos):
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


def conferir_as_fotos(antes: FotoDoHumano, depois: FotoDoHumano, outros_goals: LeitorDosOutrosGoals | None = None) -> HumanoMexido:
    """O que mudou de uma foto para a outra, separado em perda e avanço; sem o leitor dos outros Goals, nenhuma ref fora de
    fast-forward é o rebase de um deles."""
    conferencia = _conferencia(antes, depois, outros_goals)
    do_git = _do_git(antes.do_git, depois.do_git)
    mudancas = [*_refs(conferencia), *_cabeca(antes, depois), *_arquivos(conferencia), *do_git]
    soltos = tuple(caminho for caminho in soltos_da_salvaguarda(antes) if depois.conteudos.get(caminho) == AUSENTE)
    trocou = antes.cabeca != depois.cabeca or any(perda and (SOBRESCRITO in texto or TROCADA in texto) for perda, texto in mudancas)
    return HumanoMexido(antes.repositorio, tuple(texto for perda, texto in mudancas if perda),
                        tuple(texto for perda, texto in mudancas if not perda), antes.salvaguarda, soltos, git_mexido=bool(do_git),
                        cabeca_de_antes=antes.cabeca if trocou else "")


def _conferencia(antes: FotoDoHumano, depois: FotoDoHumano, outros_goals: LeitorDosOutrosGoals | None) -> _Conferencia:
    """O que a conferência consulta: o objeto, nos commits de antes e de depois, de cada caminho que mudou para um conteúdo que
    o git sabe (ou sumiu), num processo só, e nenhum quando não há caminho assim."""
    ramos = cache(lambda: {ramo.ref: ramo for ramo in (outros_goals(antes.repositorio) if outros_goals is not None else ())})
    conferencia = _Conferencia(antes, depois, partial(e_ancestral_no_humano, antes.repositorio), ramos)
    caminhos = [caminho for caminho in antes.listados if _pede_os_commits(caminho, antes, depois)]
    commits = {antes.cabeca.rpartition(" ")[2], *antes.refs.values(), *(commit for _, commit in _pontas_de_depois(antes, depois))}
    return replace(conferencia, objetos=objetos_nos_commits(antes.repositorio, ((c, caminho) for caminho in caminhos for c in commits)))


def _pede_os_commits(caminho: str, antes: FotoDoHumano, depois: FotoDoHumano) -> bool:
    """O arquivo listado antes que sumiu ou mudou para um conteúdo que o git sabe, ou cuja entrada preparada no índice mudou."""
    era, agora = antes.listados[caminho], depois.conteudos.get(caminho, AUSENTE)
    na_arvore = agora != antes.conteudos.get(caminho, AUSENTE) and (agora == AUSENTE or bool(_objeto_na_arvore(caminho, depois)))
    return na_arvore or (era.tipo != NAO_RASTREADO and era.xy[:1] != "." and antes.indice.get(caminho) != depois.indice.get(caminho))


def _pontas_de_depois(antes: FotoDoHumano, depois: FotoDoHumano) -> tuple[tuple[str, str], ...]:
    """Onde o conteúdo de antes pode ter ido: o HEAD novo e a ponta de cada ref nova ou que andou, com o nome para a mensagem."""
    refs = ((f"em {nome}", commit) for nome, commit in sorted(depois.refs.items()) if antes.refs.get(nome) != commit)
    return (("no HEAD", depois.cabeca.rpartition(" ")[2]), *refs)


def _refs(conferencia: _Conferencia) -> Iterator[Mudanca]:
    """A ref apagada é perda; a que andou fora de fast-forward também, salvo o rebase de outro Goal; a nova e a que andou por
    fast-forward, avanço."""
    antes, depois = conferencia.antes, conferencia.depois
    for nome in sorted(set(antes.refs) | set(depois.refs)):
        era, agora = antes.refs.get(nome, ""), depois.refs.get(nome, "")
        if era == agora:
            continue
        if not agora or not era:
            yield (not agora, f"ref {nome} " + (f"apagada (era {era})" if era else f"nova ({agora})"))
            continue
        avancou = conferencia.e_ancestral(era, agora)
        yield (False, f"ref {nome} andou por fast-forward ({era} -> {agora})") if avancou else _fora_de_fast_forward(nome, conferencia)


def _fora_de_fast_forward(nome: str, conferencia: _Conferencia) -> Mudanca:
    """A ref fora de fast-forward é perda, salvo a branch de outro Goal (pelo nome exato) que os rebases registrados dele levam
    de antes a depois sem tirar da história commit sem o trailer dele."""
    era, agora = conferencia.antes.refs[nome], conferencia.depois.refs[nome]
    texto, ramo = f"ref {nome} andou fora de fast-forward ({era} -> {agora})", conferencia.ramos().get(nome)
    if ramo is None:
        return True, texto
    if not _refeita_pelos_rebases((era, agora), ramo, conferencia.e_ancestral):
        return True, f"{texto}; e a branch do Goal {ramo.goal}, mas nenhum rebase registrado dele a leva ate ali"
    alheios = commits_sem_o_goal(conferencia.antes.repositorio, era, agora, goal=ramo.goal)
    if alheios is None or alheios:
        sem = ", ".join(resumo(alheios)) if alheios else "o git nao listou os commits"
        return True, f"{texto}; e a branch do Goal {ramo.goal}, mas saiu da historia commit sem {TRAILER_DO_GOAL}: {ramo.goal} ({sem})"
    return False, f"ref {nome} refeita pelo rebase do Goal {ramo.goal} ({era} -> {agora})"


def _refeita_pelos_rebases(par: tuple[str, str], ramo: RamoDeOutroGoal, e_ancestral: Callable[[str, str], bool]) -> bool:
    """De antes a depois pelos rebases registrados do Goal: cada um parte da ponta de então (ou de um commit depois dela, o Goal
    que commitou antes do rebase), e o último chega a depois (ou a um commit antes dele, o Goal que commitou depois)."""
    era, agora = par
    ponta = era
    for de, para in ramo.rebases:
        if de == ponta or e_ancestral(ponta, de):
            ponta = para
    return ponta != era and (ponta == agora or e_ancestral(ponta, agora))


def _cabeca(antes: FotoDoHumano, depois: FotoDoHumano) -> list[Mudanca]:
    """A troca de branch ou de commit do HEAD é avanço: as mudanças que ela não carregou contam nos arquivos."""
    return [] if antes.cabeca == depois.cabeca else [(False, f"HEAD: {antes.cabeca} -> {depois.cabeca}")]


def _arquivos(conferencia: _Conferencia) -> Iterator[Mudanca]:
    """Cada caminho listado numa das fotos: o conteúdo na árvore e, com mudança preparada, a entrada do índice."""
    antes, depois = conferencia.antes, conferencia.depois
    for caminho in sorted(set(antes.listados) | set(depois.listados)):
        if caminho not in antes.listados:
            yield _listado_so_depois(caminho, antes, depois)
            continue
        yield from (mudanca for mudanca in (_na_arvore(caminho, conferencia), _no_indice(caminho, conferencia)) if mudanca)


def _listado_so_depois(caminho: str, antes: FotoDoHumano, depois: FotoDoHumano) -> Mudanca:
    """O caminho limpo ou novo antes, listado depois: o rastreado que sumiu é perda; o resto, avanço."""
    if caminho not in antes.indice:
        return False, f"{caminho} apareceu"
    if depois.conteudos.get(caminho) == AUSENTE:
        return True, f"{caminho} {SUMIU}"
    return False, f"{caminho} {NOVO}"


def _na_arvore(caminho: str, conferencia: _Conferencia) -> Mudanca | None:
    """O conteúdo do arquivo listado antes: igual, nada; sumido ou trocado por um que o git já tinha, sem que o de antes esteja
    no índice, no HEAD ou numa ponta que andou, perda; o resto, avanço."""
    antes, depois = conferencia.antes, conferencia.depois
    agora = depois.conteudos.get(caminho, AUSENTE)
    if agora == antes.conteudos.get(caminho, AUSENTE):
        return None
    era, novo = antes.listados[caminho], _objeto_na_arvore(caminho, depois)
    if agora != AUSENTE and not _ja_tinha(conferencia, caminho, novo):
        return False, f"{caminho} {NOVO}"
    onde = _onde_esta(conferencia, caminho, _conteudo_de_antes(caminho, antes))
    if onde:
        return False, f"{caminho} {'sumiu' if agora == AUSENTE else 'mudou'}, e o conteudo de antes esta {onde}"
    return True, f"{caminho} {SUMIU if agora == AUSENTE else NO_HEAD if novo in (era.no_head, era.no_indice) else SOBRESCRITO}"


def _no_indice(caminho: str, conferencia: _Conferencia) -> Mudanca | None:
    """A entrada do índice com mudança preparada antes: igual, nada; saída ou trocada por uma que o git já tinha, sem que o
    conteúdo preparado esteja na árvore, no índice, no HEAD ou numa ponta que andou, perda; o resto, avanço."""
    antes, depois = conferencia.antes, conferencia.depois
    era = antes.listados[caminho]
    entradas, agora = antes.indice.get(caminho, ()), depois.indice.get(caminho, ())
    if era.tipo == NAO_RASTREADO or era.xy[:1] == "." or agora == entradas:
        return None
    if agora and not _ja_tinha(conferencia, caminho, agora[0].split(" ")[1] if len(agora) == 1 else ""):
        return False, f"indice {caminho}: entrada nova"
    na_arvore = bool(era.no_indice) and era.xy[1:] == "." and depois.conteudos.get(caminho) == antes.conteudos.get(caminho)
    onde = "na arvore" if na_arvore else _onde_esta(conferencia, caminho, era.no_indice)
    if onde:
        return False, f"indice {caminho}: a entrada {'saiu' if not agora else 'mudou'}, e o conteudo preparado esta {onde}"
    volta = "saiu" if not agora else "voltou a do HEAD" if agora == (era.entrada_do_head,) else TROCADA
    return True, f"indice {caminho}: a entrada {volta}"


def _conteudo_de_antes(caminho: str, antes: FotoDoHumano) -> str:
    """O objeto do conteúdo do arquivo antes da sessão: o do índice, se a árvore estava igual a ele; senão, o da foto."""
    era = antes.listados[caminho]
    return era.no_indice if era.tipo in ("1", "2") and era.xy[1:] == "." else antes.objetos.get(caminho, "")


def _ja_tinha(conferencia: _Conferencia, caminho: str, objeto: str) -> bool:
    """O objeto já estava no git antes da sessão, no mesmo caminho: no HEAD, no índice ou na ponta de uma ref."""
    era, antes = conferencia.antes.listados[caminho], conferencia.antes
    commits = (antes.cabeca.rpartition(" ")[2], *antes.refs.values())
    nas_pontas = any(conferencia.objetos.get((commit, caminho)) == objeto for commit in commits)
    return bool(objeto) and (objeto in (era.no_head, era.no_indice) or nas_pontas)


def _onde_esta(conferencia: _Conferencia, caminho: str, objeto: str) -> str:
    """Onde o conteúdo de antes está agora, no mesmo caminho: no índice, no HEAD ou na ponta de uma ref que andou; vazio se em
    lugar nenhum (ou se a foto de antes não sabe o objeto dele)."""
    if not objeto:
        return ""
    if any(entrada.split(" ")[1:2] == [objeto] for entrada in conferencia.depois.indice.get(caminho, ())):
        return "no indice"
    pontas = _pontas_de_depois(conferencia.antes, conferencia.depois)
    return next((onde for onde, commit in pontas if conferencia.objetos.get((commit, caminho)) == objeto), "")


def _objeto_na_arvore(caminho: str, depois: FotoDoHumano) -> str:
    """O objeto que a árvore tem agora, quando o git o sabe: o do índice, se o arquivo está igual a ele; vazio se não."""
    agora = depois.listados.get(caminho)
    if agora is not None:
        return agora.no_indice if agora.tipo in ("1", "2") and agora.xy[1:] == "." else ""
    entradas = depois.indice.get(caminho, ())
    return entradas[0].split(" ")[1] if len(entradas) == 1 else ""


def _do_git(antes: Mapping[str, str], depois: Mapping[str, str]) -> list[Mudanca]:
    """O arquivo que muda o git e que apareceu, mudou ou sumiu: sempre perda."""
    nomes = sorted(set(antes) | set(depois))
    return [(True, f"{nome} mudou ({antes.get(nome, AUSENTE)} -> {depois.get(nome, AUSENTE)})")
            for nome in nomes if antes.get(nome, AUSENTE) != depois.get(nome, AUSENTE)]
