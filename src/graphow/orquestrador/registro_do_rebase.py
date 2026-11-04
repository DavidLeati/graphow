"""O rebase no livro-razão: a Evidence dele, a ponta nova, os commits novos das fatias e dos Artifact, e a retomada depois da queda.

O rebase da branch do Goal sobre a base que andou (orquestrador/base_que_andou.py,
e o commit da fatia de conflito, orquestrador/fatia_de_conflito.py) troca os
hashes dos commits do Goal. O registro vem antes das refs, num lote só:

- a Evidence `rebase_do_goal`, que deriva do Goal: de que base, para que base,
  as duas pontas e os dois commits do código, o commit novo de cada antigo e o
  de cada fatia, os arquivos que a ponta mudou, os que algum critério cobre, se
  a verificação final segue valendo e, quando houve, a fatia de conflito;
- a fatia e o Artifact de cada commit antigo passam a apontar para o novo; o
  Artifact guarda o de antes em `commit_antes_do_rebase` e a Evidence em
  `rebase` (os `arquivos` dele ficam: o rebase limpo não os muda, e o commit
  da fatia de conflito leva o Goal inteiro);
- a ponta do Goal vai à nova. O rebase que não mudou arquivo de critério deixa
  nela, em `equivalente_a`, o commit do código que a verificação viu (e os que
  já eram equivalentes a ele): o kernel e o laço aceitam a verificação feita
  num deles (kernel/fechamento_do_goal.py, orquestrador/verificacao_do_goal.py).

- o commit dos testes de aceite (o do Goal, o da configuração e o de cada
  Criterio) passa ao que o rebase fez dele, achado pelo trailer
  `Graphow-Task: aceite-…` dos dois lados (`aceites_refeitos`): a verificação
  refeita roda o aceite desse commit e compara a configuração de teste com a
  dele, que já tem a da base, e não mostra o que a base mudou como do Goal. O
  Goal guarda, em `aceite_antes_do_rebase`, o commit de antes de cada um: a
  aprovação do humano e os desacordos gravados com o de antes seguem valendo
  (orquestrador/leitura_do_goal.py). O aceite que o rebase não refez (a fatia
  de conflito que não o reaplicou limpo) fica com o commit de antes.

O processo que cai entre o registro e as refs deixa o livro-razão à frente do
git: antes de preparar a área, `retomar_o_rebase` desfaz o rebase pela metade e
leva as refs que ficaram para trás ao último registrado.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core import aceite as a
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.correcoes import normalizar_caminho
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.git_do_goal import TRAILER_DA_TASK, GitDoGoal, commits_entre
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.livro_razao import aresta, propriedade
from graphow.orquestrador.rebase_no_clone import RebaseNoClone, mover_as_refs, recuperar_o_clone
from graphow.orquestrador.tipo_da_verificacao import arquivos_dos_criterios
from graphow.projection.graph_view import GrafoView

ACAO_DO_REBASE: str = "rebase_do_goal"
CAMPO_COMMIT_ANTES_DO_REBASE: str = "commit_antes_do_rebase"
CAMPO_REBASE: str = "rebase"
CAMPO_COMMIT_ANTES: str = "commit_antes"
PREFIXO_DO_ACEITE: str = "aceite-"
CAMPOS_DO_COMMIT_DO_ACEITE: tuple[str, ...] = ("commit", "commit_da_configuracao")


def registrar_o_rebase(contexto: ContextoDoGoal, estado: EstadoDoGoal, feito: RebaseNoClone, *, conflito: str = "") -> str:
    """A Evidence do rebase, a ponta nova e os commits novos das fatias e dos Artifact, num lote; devolve o id da Evidence."""
    git, documento = contexto.git, caminho_do_documento(contexto.configuracao.slug)
    codigo_antes, codigo_depois = _codigo_em(git, feito.antes, documento), _codigo_em(git, feito.depois, documento)
    cobertos = cobertos_pelo_rebase(estado, git, feito.arquivos)
    vale = not cobertos and not conflito
    equivalentes = [codigo_antes, *equivalentes_da_ponta(estado.propriedades, codigo_antes)] if vale else []
    ponta = {m.CAMPO_COMMIT: feito.depois, m.CAMPO_COMMIT_DO_CODIGO: codigo_depois,
             **({a.CAMPO_EQUIVALENTE_A: equivalentes} if equivalentes else {})}
    numero = len(rebases_do_goal(contexto.livro.view(), contexto.id_goal)) + 1
    id_evidencia, pares, aceites = f"rebase-{contexto.id_goal}-{numero}", dict(feito.pares), aceites_refeitos(contexto, feito)
    propriedades = {
        "acao": ACAO_DO_REBASE, "base": contexto.configuracao.base, "base_antes": feito.base_antes, "base_depois": feito.base_depois,
        CAMPO_COMMIT_ANTES: feito.antes, m.CAMPO_COMMIT: feito.depois, "commit_do_codigo_antes": codigo_antes,
        m.CAMPO_COMMIT_DO_CODIGO: codigo_depois, "commits": [{"antes": antes, "depois": depois} for antes, depois in feito.pares],
        "fatias": [{"task": f.id, "antes": f.texto(m.CAMPO_COMMIT), "depois": pares[f.texto(m.CAMPO_COMMIT)]}
                   for f in estado.fatias if f.texto(m.CAMPO_COMMIT) in pares],
        "arquivos": list(feito.arquivos), "cobertos": list(cobertos), "verificacao_vale": vale, "fatia_de_conflito": conflito,
        "aceites": [{"antes": antes, "depois": depois} for antes, depois in aceites.items()],
    }
    rotulo = f"Rebase {numero} do Goal sobre {contexto.configuracao.base} ({feito.base_depois[:12]}), ponta em {feito.depois[:12]}"
    contexto.livro.gravar(
        [*contexto.livro.produzido(id_evidencia, TipoNo.EVIDENCE, rotulo, propriedades=propriedades),
         aresta(id_evidencia, contexto.id_goal, TipoAresta.DERIVA_DE), propriedade(contexto.id_goal, m.CAMPO_PONTA_DO_RAMO, ponta),
         *_commits_novos(contexto, estado, pares, id_evidencia=id_evidencia), *_aceite_novo(contexto.id_goal, estado, aceites)],
        rotulo,
    )
    return id_evidencia


def _commits_novos(contexto: ContextoDoGoal, estado: EstadoDoGoal, pares: Mapping[str, str], *, id_evidencia: str) -> list[ItemPatch]:
    """A fatia e o Artifact de cada commit que o rebase refez passam a apontar para o commit novo."""
    fatias = [propriedade(f.id, m.CAMPO_COMMIT, pares[f.texto(m.CAMPO_COMMIT)]) for f in estado.fatias if f.texto(m.CAMPO_COMMIT) in pares]
    artefatos = [(no.id, str(no.obter_propriedade(m.CAMPO_COMMIT) or "")) for no in _artefatos(contexto.livro.view(), contexto.livro.id_sessao)]
    return [*fatias, *(item for id_no, antigo in artefatos if antigo in pares for item in (
        propriedade(id_no, m.CAMPO_COMMIT, pares[antigo]), propriedade(id_no, CAMPO_COMMIT_ANTES_DO_REBASE, antigo),
        propriedade(id_no, CAMPO_REBASE, id_evidencia)))]


def aceites_refeitos(contexto: ContextoDoGoal, feito: RebaseNoClone) -> dict[str, str]:
    """O commit novo de cada commit dos testes de aceite do Goal, pelo trailer `Graphow-Task: aceite-…` de antes e de depois."""
    antigos = _aceites_em(contexto, feito.base_antes, feito.antes)
    novos = _aceites_em(contexto, feito.base_depois, feito.depois)
    return {antigos[tarefa]: novos[tarefa] for tarefa in antigos if tarefa in novos and antigos[tarefa] != novos[tarefa]}


def _aceites_em(contexto: ContextoDoGoal, base: str, ponta: str) -> dict[str, str]:
    """O commit de cada aceite de `base..ponta`, pelo valor do trailer `Graphow-Task` (o que começa com `aceite-`)."""
    commits = ((commit.valor_do_trailer(TRAILER_DA_TASK), commit.hash) for commit in commits_entre(contexto.area, base, ponta))
    return {tarefa: hash_do_commit for tarefa, hash_do_commit in commits if tarefa.startswith(PREFIXO_DO_ACEITE)}


def _aceite_novo(id_goal: str, estado: EstadoDoGoal, refeitos: Mapping[str, str]) -> list[ItemPatch]:
    """O commit do aceite e o da configuração no Goal, e o de cada Criterio, passam ao refeito; o Goal guarda o de antes."""
    if not refeitos:
        return []
    aceite = dict(estado.aceite or {})
    aceite.update({campo: refeitos[str(aceite[campo])] for campo in CAMPOS_DO_COMMIT_DO_ACEITE if str(aceite.get(campo)) in refeitos})
    gravado = estado.propriedades.get(a.CAMPO_ACEITE_ANTES_DO_REBASE)
    antes = {str(k): refeitos.get(str(v), str(v)) for k, v in gravado.items()} if isinstance(gravado, Mapping) else {}
    nos = ((str(c.get("no") or ""), estado.commits_do_aceite.get(str(c.get("id")), "")) for c in (estado.plano or {}).get("criterios", []))
    return [propriedade(id_goal, m.CAMPO_ACEITE, aceite), propriedade(id_goal, a.CAMPO_ACEITE_ANTES_DO_REBASE, {**antes, **refeitos}),
            *(propriedade(id_no, a.CAMPO_COMMIT_DO_ACEITE, refeitos[commit]) for id_no, commit in nos if id_no and commit in refeitos)]


def _artefatos(view: GrafoView, id_sessao: str) -> list[NoGrafo]:
    """Os Artifact que a Sessao do orquestrador do Goal produziu."""
    nos = (view.obter_no(saida.destino_id) for saida in view.obter_arestas_saida(id_sessao, TipoAresta.PRODUZ))
    return [no for no in nos if no is not None and no.tipo == TipoNo.ARTIFACT]


def _codigo_em(git: GitDoGoal, commit: str, documento: str) -> str:
    """O commit do código a partir do commit dado: o último que mudou algo além do documento do Goal."""
    return git.rodar("log", "-1", "--format=%H", commit, "--", ".", f":(exclude){documento}").strip() or commit


def cobertos_pelo_rebase(estado: EstadoDoGoal, git: GitDoGoal, arquivos: Sequence[str]) -> tuple[str, ...]:
    """Dos arquivos que o rebase mudou na ponta, os que algum critério cobre."""
    cobertos = {normalizar_caminho(caminho) for caminho in arquivos_dos_criterios(estado, git)}
    return tuple(caminho for caminho in arquivos if normalizar_caminho(caminho) in cobertos)


def equivalentes_da_ponta(propriedades: Mapping[str, Any], codigo: str) -> tuple[str, ...]:
    """Os commits do código que a ponta gravada dá por equivalentes ao dado; vazio quando ela é de outro commit."""
    ponta = propriedades.get(m.CAMPO_PONTA_DO_RAMO)
    if not isinstance(ponta, Mapping) or ponta.get(m.CAMPO_COMMIT_DO_CODIGO) != codigo:
        return ()
    lista = ponta.get(a.CAMPO_EQUIVALENTE_A)
    return tuple(str(item) for item in lista) if isinstance(lista, list) else ()


def rebases_do_goal(view: GrafoView, id_goal: str) -> tuple[NoGrafo, ...]:
    """As Evidence de rebase que o orquestrador gravou derivando do Goal, pela ordem do log."""
    origens = (view.obter_no(entrada.origem_id) for entrada in view.obter_arestas_entrada(id_goal, TipoAresta.DERIVA_DE))
    rebases = [no for no in origens if no is not None and no.obter_propriedade("acao") == ACAO_DO_REBASE
               and no.proveniencia.papel == PapelAutor.ORQUESTRADOR.value]
    return tuple(sorted(rebases, key=lambda no: (no.ordem.seq_criacao or 0, no.id)))


def retomar_o_rebase(contexto: ContextoDoGoal) -> None:
    """Antes de preparar a área: o rebase pela metade sai, e o último registrado leva as refs que ficaram para trás."""
    if not (contexto.area / ".git").is_dir():
        return
    recuperar_o_clone(contexto.area, contexto.configuracao.ramo)
    rebases = rebases_do_goal(contexto.livro.view(), contexto.id_goal)
    if rebases:
        antes, depois = (str(rebases[-1].obter_propriedade(chave) or "") for chave in (CAMPO_COMMIT_ANTES, m.CAMPO_COMMIT))
        mover_as_refs(contexto.area_do_goal, antes, depois)
