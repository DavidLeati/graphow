"""Segundo projeto do corpus: mede se um aprendizado do primeiro chega a uma tarefa do segundo.

Três aprendizados são destilados na sessão do primeiro projeto e promovidos
pelo humano de três formas: um vale para todo projeto, um vale só para o
primeiro projeto mas casa lexicalmente com uma tarefa do segundo, e um vale só
para o primeiro projeto e não casa com nada. As três tarefas do segundo projeto
dependem, cada uma, de um deles. É o que mede se herança mais léxico atravessam
projetos, e onde um índice semântico teria o que fazer.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from graphow.avaliacao.cenario_memoria import AUTOR_HUMANO, montar_cenario_com_memoria
from graphow.avaliacao.tarefas_gravadas import ID_PROJETO, ID_SESSAO, DescricaoDeNo, Ligacao
from graphow.context.aprendizados_aplicaveis import MECANISMO_HERANCA, MECANISMO_LEXICO
from graphow.context.memoria import ALCANCE_GLOBAL, CAMPO_ALCANCE, CAMPO_COMO_APLICAR
from graphow.core.types import PapelAutor, StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel

ID_PROJETO_SEGUNDO: str = "proj-segundo"
ID_SETOR_SEGUNDO: str = "setor-segundo"
ID_SESSAO_SEGUNDA: str = "sess-segunda"
ID_APRENDIZADO_GLOBAL: str = "apr-corte-por-secao"
ID_APRENDIZADO_LEXICO: str = "apr-eviccao-por-lru"
ID_APRENDIZADO_ISOLADO: str = "apr-posse-no-portao"
MECANISMO_NENHUM: str = "nenhum"


@dataclass(frozen=True)
class TarefaEntreProjetos:
    """Uma tarefa do segundo projeto e o aprendizado do primeiro de que ela depende."""

    id: str
    titulo: str
    descricao: str
    id_aprendizado_esperado: str
    mecanismo_esperado: str


@dataclass(frozen=True)
class AprendizadoGravado:
    """Um aprendizado do corpus: a afirmação, como aplicar, de onde saiu e onde vale."""

    id: str
    afirmacao: str
    como_aplicar: str
    id_origem: str
    vale_para: str = ""
    global_: bool = False


TAREFAS_ENTRE_PROJETOS: tuple[TarefaEntreProjetos, ...] = (
    TarefaEntreProjetos(
        id="t2-spans",
        titulo="Exportar os spans do kernel em NDJSON",
        descricao="Cada submissao ao PatchBoard vira um span com os atributos GenAI.",
        id_aprendizado_esperado=ID_APRENDIZADO_GLOBAL,
        mecanismo_esperado=MECANISMO_HERANCA,
    ),
    TarefaEntreProjetos(
        id="t2-cache",
        titulo="Definir a politica de eviccao do cache de vistas",
        descricao="O cache de vistas materializadas cresce sem teto e precisa de politica.",
        id_aprendizado_esperado=ID_APRENDIZADO_LEXICO,
        mecanismo_esperado=MECANISMO_LEXICO,
    ),
    TarefaEntreProjetos(
        id="t2-migracao",
        titulo="Migrar o banco antigo para o diretorio de dados",
        descricao="Copiar os eventos preservando a origem intacta.",
        id_aprendizado_esperado=ID_APRENDIZADO_ISOLADO,
        mecanismo_esperado=MECANISMO_NENHUM,
    ),
)

APRENDIZADOS_GRAVADOS: tuple[AprendizadoGravado, ...] = (
    AprendizadoGravado(
        id=ID_APRENDIZADO_GLOBAL,
        afirmacao="Nao corte a vista linha a linha pelo fim: descarte por secao e encolha a vizinhanca por dentro",
        como_aplicar="Sob pressao de orcamento, desca a escada de corte por prioridade e nunca corte a lista de vizinhos",
        id_origem="dec-t07-vista-0",
        global_=True,
    ),
    AprendizadoGravado(
        id=ID_APRENDIZADO_LEXICO,
        afirmacao="Politica de eviccao de cache: LRU por contagem com teto, nao TTL estrito",
        como_aplicar="Ao dimensionar um cache, prefira LRU por contagem; TTL expulsa o que ainda serve",
        id_origem="t09-escalacao",
        vale_para=ID_PROJETO,
    ),
    AprendizadoGravado(
        id=ID_APRENDIZADO_ISOLADO,
        afirmacao="A posse de tarefa vive no InvariantGate porque e concorrencia",
        como_aplicar="Serialize a escrita por lock no portao de invariantes, nao na ferramenta",
        id_origem="dec-t06-posse-0",
        vale_para=ID_PROJETO,
    ),
)


def montar_cenario_entre_projetos() -> WriteKernel:
    """O cenário com memória, mais os aprendizados promovidos e o segundo projeto."""
    kernel = montar_cenario_com_memoria()
    _submeter(kernel, _operacoes_de_aprendizados())
    _submeter(kernel, _operacoes_do_segundo_projeto())
    return kernel


def _operacoes_de_aprendizados() -> tuple[ItemPatch, ...]:
    """Os três aprendizados, destilados na sessão do primeiro projeto e promovidos pelo humano."""
    operacoes: list[ItemPatch] = []
    for aprendizado in APRENDIZADOS_GRAVADOS:
        operacoes.extend(_operacoes_de_um_aprendizado(aprendizado))
    return tuple(operacoes)


def _operacoes_de_um_aprendizado(aprendizado: AprendizadoGravado) -> tuple[ItemPatch, ...]:
    """Nó, vínculo com a sessão, origem e a promoção que o humano lhe deu."""
    propriedades = {CAMPO_COMO_APLICAR: aprendizado.como_aplicar}
    if aprendizado.global_:
        propriedades[CAMPO_ALCANCE] = ALCANCE_GLOBAL
    operacoes = [
        _no(aprendizado.id, TipoNo.APRENDIZADO, DescricaoDeNo(aprendizado.afirmacao, propriedades)),
        _aresta(f"p-{aprendizado.id}", Ligacao(ID_SESSAO, aprendizado.id, TipoAresta.PRODUZ)),
        _aresta(f"d-{aprendizado.id}", Ligacao(aprendizado.id, aprendizado.id_origem, TipoAresta.DERIVA_DE)),
    ]
    if aprendizado.vale_para:
        ligacao = Ligacao(aprendizado.id, aprendizado.vale_para, TipoAresta.VALE_PARA)
        operacoes.append(_aresta(f"v-{aprendizado.id}", ligacao))
    return tuple(operacoes)


def _operacoes_do_segundo_projeto() -> tuple[ItemPatch, ...]:
    """Projeto, setor, sessão e as três tarefas que dependem de memória do primeiro projeto."""
    sessao = DescricaoDeNo("Sprint do segundo projeto", {"status": StatusSessao.ATIVA.value})
    operacoes = [
        _no(ID_PROJETO_SEGUNDO, TipoNo.PROJETO, DescricaoDeNo("Segundo projeto", {"nivel_autonomia": "estrito"})),
        _no(ID_SETOR_SEGUNDO, TipoNo.SETOR, DescricaoDeNo("Plataforma")),
        _aresta("c-setor-segundo", Ligacao(ID_PROJETO_SEGUNDO, ID_SETOR_SEGUNDO, TipoAresta.CONTEM)),
        _no(ID_SESSAO_SEGUNDA, TipoNo.SESSAO, sessao),
        _aresta("c-sessao-segunda", Ligacao(ID_SETOR_SEGUNDO, ID_SESSAO_SEGUNDA, TipoAresta.CONTEM)),
    ]
    for tarefa in TAREFAS_ENTRE_PROJETOS:
        descricao = DescricaoDeNo(tarefa.titulo, {"status": StatusTask.PENDENTE.value, "descricao": tarefa.descricao})
        operacoes.append(_no(tarefa.id, TipoNo.TASK, descricao))
        operacoes.append(_aresta(f"p-{tarefa.id}", Ligacao(ID_SESSAO_SEGUNDA, tarefa.id, TipoAresta.PRODUZ)))
    return tuple(operacoes)


def _no(id_no: str, tipo: TipoNo, descricao: DescricaoDeNo) -> ItemPatch:
    """Operação de criação de nó com rótulo e propriedades declarados."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={
            "id": id_no,
            "tipo": tipo.value,
            "rotulo": descricao.rotulo,
            "propriedades": dict(descricao.propriedades),
        },
    )


def _aresta(id_aresta: str, ligacao: Ligacao) -> ItemPatch:
    """Operação de criação de aresta tipada entre dois nós."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={
            "id": id_aresta,
            "origem_id": ligacao.origem,
            "destino_id": ligacao.destino,
            "tipo": ligacao.tipo.value,
        },
    )


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch]) -> None:
    """O humano monta o terreno; os portões precisam aceitar o cenário inteiro."""
    dados = DadosPropostaPatch(
        autor=AUTOR_HUMANO,
        papel=PapelAutor.HUMANO,
        operacoes=tuple(operacoes),
        justificativa="Montagem do segundo projeto do cenario gravado",
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    if not recibo.sucesso:
        raise RuntimeError(f"Cenario entre projetos recusado pelo kernel: {recibo.mensagem}")
