"""Corpus de dez tarefas gravadas, com o grafo que as cerca.

O plano fixa "tokens por tarefa bem-sucedida" como a métrica desde a Fase 3 e
prevê o harness de avaliação na Fase 8. Não havia tarefa gravada nem medição: o
único número existente era "447 para 184 tokens" de uma vista, numa mensagem de
commit. Este módulo é o corpus que faltava — dez tarefas com restrições,
decisões, evidências, dependências e uma escalação, montadas sempre da mesma
forma para que a medição seja comparável entre execuções. Ver achado A-15.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel

ID_PROJETO: str = "proj-avaliacao"
ID_SETOR: str = "setor-engenharia"
ID_SESSAO: str = "sess-avaliacao"
ID_GOAL: str = "goal-substrato"
ORCAMENTO_PADRAO_DA_MEDICAO: int = 1500


@dataclass(frozen=True)
class TarefaGravada:
    """Uma tarefa do corpus, com o que basta para medi-la de forma repetível."""

    id: str
    titulo: str
    criterio_pronto: str
    papel: PapelAutor = PapelAutor.EXECUTOR
    concluida: bool = True
    depende_de: str = ""
    pergunta_escalada: str = ""
    orcamento_tokens: int = ORCAMENTO_PADRAO_DA_MEDICAO
    decisoes: tuple[str, ...] = field(default_factory=tuple)
    evidencias: tuple[str, ...] = field(default_factory=tuple)

    @property
    def id_questao(self) -> str:
        """Identificador da Question de escalação desta tarefa, se houver."""
        return f"quest-{self.id}"


@dataclass(frozen=True)
class DescricaoDeNo:
    """Rótulo e propriedades de um nó a criar, agrupados para caber na assinatura."""

    rotulo: str
    propriedades: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Ligacao:
    """As duas pontas e o tipo de uma aresta a criar."""

    origem: str
    destino: str
    tipo: TipoAresta


TAREFAS_GRAVADAS: tuple[TarefaGravada, ...] = (
    TarefaGravada(
        id="t01-parser",
        titulo="Escrever o parser de JSON Patch RFC 6902",
        criterio_pronto="Todas as seis operacoes do RFC reconhecidas e testadas",
        decisoes=("Usar dataclass frozen para o item de patch",),
    ),
    TarefaGravada(
        id="t02-sanitizador",
        titulo="Barrar chaves de prototype pollution no sanitizador",
        criterio_pronto="Patch com __proto__ recusado antes de qualquer portao",
        depende_de="t01-parser",
        evidencias=("Varredura de 40 payloads maliciosos sem escape",),
    ),
    TarefaGravada(
        id="t03-schema-gate",
        titulo="Validar pares de aresta contra a ontologia",
        criterio_pronto="Aresta fora da tabela recusada com mensagem acionavel",
        depende_de="t01-parser",
        decisoes=("A tabela de pares vive no SchemaGate, nao no modelo",),
    ),
    TarefaGravada(
        id="t04-role-gate",
        titulo="Impor a matriz de papeis sobre nos e arestas",
        criterio_pronto="Executor recusado ao mexer em Constraint, Question e escopo",
        depende_de="t03-schema-gate",
        decisoes=("Criar e remover sao poderes distintos por tipo de aresta",),
        evidencias=("Sonda de 17 casos: nenhum caminho de fuga aceito",),
    ),
    TarefaGravada(
        id="t05-invariantes",
        titulo="Impedir conclusao de tarefa com duvida aberta",
        criterio_pronto="Fechamento recusado com modo de falha nomeado",
        depende_de="t04-role-gate",
    ),
    TarefaGravada(
        id="t06-posse",
        titulo="Serializar a escrita por posse de tarefa",
        criterio_pronto="Segundo executor colide no kernel em vez de sobrescrever",
        depende_de="t04-role-gate",
        decisoes=("Posse e concorrencia, entao vive no InvariantGate",),
    ),
    TarefaGravada(
        id="t07-vista",
        titulo="Materializar a vista de contexto sob orcamento",
        criterio_pronto="Vista da tarefa cabe no orcamento com restricoes preservadas",
        evidencias=("Sessao de 60 tarefas: 60 vizinhos a 800 tokens",),
        decisoes=("A vizinhanca encolhe por dentro antes de qualquer descarte",),
    ),
    TarefaGravada(
        id="t08-fila",
        titulo="Publicar a fila de tarefas executaveis da sessao",
        criterio_pronto="Consulta devolve apenas o que esta liberado, em ordem estavel",
        depende_de="t05-invariantes",
    ),
    TarefaGravada(
        id="t09-escalacao",
        titulo="Abrir e aguardar a resposta de uma duvida bloqueante",
        criterio_pronto="Agente retoma o trabalho apos a resposta humana",
        pergunta_escalada="Politica de eviccao: TTL estrito ou LRU por contagem?",
        depende_de="t07-vista",
    ),
    TarefaGravada(
        id="t10-harness",
        titulo="Emitir o ciclo de vida de execucao pelos hooks",
        criterio_pronto="Solicitada, iniciada e concluida aparecem no log",
        concluida=False,
        papel=PapelAutor.REVISOR,
    ),
)


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch]) -> None:
    """Escreve o cenário sob a identidade humana, que monta o terreno."""
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=tuple(operacoes),
        justificativa="Montagem do cenario gravado de avaliacao",
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))


def _no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch:
    """Operação de criação de nó sem propriedades de domínio."""
    return _no_com(id_no, tipo, DescricaoDeNo(rotulo=rotulo))


def _no_com(id_no: str, tipo: TipoNo, descricao: "DescricaoDeNo") -> ItemPatch:
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


def _aresta(id_aresta: str, ligacao: "Ligacao") -> ItemPatch:
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


def _montar_navegacao() -> tuple[ItemPatch, ...]:
    """Projeto, setor, sessão, objetivo e as duas restrições que os escopam."""
    projeto = DescricaoDeNo("Graphow", {"nivel_autonomia": "estrito"})
    sessao = DescricaoDeNo("Sprint de avaliacao", {"status": "ativa"})
    inviolavel = {"inviolavel": "true"}
    return (
        _no_com(ID_PROJETO, TipoNo.PROJETO, projeto),
        _no(ID_SETOR, TipoNo.SETOR, "Engenharia"),
        _aresta("c-setor", Ligacao(ID_PROJETO, ID_SETOR, TipoAresta.CONTEM)),
        _no_com(ID_SESSAO, TipoNo.SESSAO, sessao),
        _aresta("c-sessao", Ligacao(ID_SETOR, ID_SESSAO, TipoAresta.CONTEM)),
        _no(ID_GOAL, TipoNo.GOAL, "Substrato bilateral confiavel"),
        _aresta("p-goal", Ligacao(ID_SESSAO, ID_GOAL, TipoAresta.PRODUZ)),
        _no_com("const-zero-deps", TipoNo.CONSTRAINT, DescricaoDeNo("Zero dependencias externas", inviolavel)),
        _aresta("e-const-1", Ligacao("const-zero-deps", ID_GOAL, TipoAresta.ESCOPA)),
        _no_com("const-forma", TipoNo.CONSTRAINT, DescricaoDeNo("400 linhas por arquivo, 30 por funcao", inviolavel)),
        _aresta("e-const-2", Ligacao("const-forma", ID_GOAL, TipoAresta.ESCOPA)),
    )


def _montar_tarefa(tarefa: TarefaGravada) -> tuple[ItemPatch, ...]:
    """Task, vínculo com a sessão, decomposição e dependência declarada."""
    status = StatusTask.CONCLUIDO.value if tarefa.concluida else StatusTask.PENDENTE.value
    descricao = DescricaoDeNo(
        tarefa.titulo, {"status": status, "criterio_pronto": tarefa.criterio_pronto}
    )
    operacoes = [
        _no_com(tarefa.id, TipoNo.TASK, descricao),
        _aresta(f"p-{tarefa.id}", Ligacao(ID_SESSAO, tarefa.id, TipoAresta.PRODUZ)),
        _aresta(f"dec-{tarefa.id}", Ligacao(ID_GOAL, tarefa.id, TipoAresta.DECOMPOE)),
    ]
    if tarefa.depende_de:
        ligacao = Ligacao(tarefa.id, tarefa.depende_de, TipoAresta.DEPENDE_DE)
        operacoes.append(_aresta(f"dep-{tarefa.id}", ligacao))
    return tuple(operacoes)


def _montar_contexto_da_tarefa(tarefa: TarefaGravada) -> tuple[ItemPatch, ...]:
    """Decisões, evidências e a escalação que cercam a tarefa gravada."""
    operacoes: list[ItemPatch] = []
    for indice, decisao in enumerate(tarefa.decisoes):
        operacoes.extend(_montar_apoio(f"dec-{tarefa.id}-{indice}", TipoNo.DECISION, decisao))
    for indice, evidencia in enumerate(tarefa.evidencias):
        operacoes.extend(_montar_apoio(f"ev-{tarefa.id}-{indice}", TipoNo.EVIDENCE, evidencia))
    return tuple(operacoes) + _montar_escalacao(tarefa)


def _montar_apoio(id_no: str, tipo: TipoNo, rotulo: str) -> tuple[ItemPatch, ...]:
    """Cria um nó de apoio e o vínculo `produz` que o liga à sessão."""
    return (
        _no(id_no, tipo, rotulo),
        _aresta(f"p-{id_no}", Ligacao(ID_SESSAO, id_no, TipoAresta.PRODUZ)),
    )


def _montar_escalacao(tarefa: TarefaGravada) -> tuple[ItemPatch, ...]:
    """A Question que travou a tarefa e a resposta humana que a destravou."""
    if not tarefa.pergunta_escalada:
        return ()
    propriedades = {
        "status": StatusQuestion.RESPONDIDA.value,
        "aberta_por": "agente-executor",
        "respondida_por": "david",
        "resposta": "LRU por contagem, com teto de 512 entradas",
    }
    descricao = DescricaoDeNo(tarefa.pergunta_escalada, propriedades)
    return (
        _no_com(tarefa.id_questao, TipoNo.QUESTION, descricao),
        _aresta(f"p-{tarefa.id_questao}", Ligacao(ID_SESSAO, tarefa.id_questao, TipoAresta.PRODUZ)),
        _aresta(f"b-{tarefa.id_questao}", Ligacao(tarefa.id_questao, tarefa.id, TipoAresta.BLOQUEIA)),
    )


def montar_cenario_gravado() -> WriteKernel:
    """Reconstrói o grafo das dez tarefas sempre da mesma forma, do zero."""
    kernel = montar_kernel_em_memoria()
    _submeter(kernel, _montar_navegacao())
    for tarefa in TAREFAS_GRAVADAS:
        _submeter(kernel, _montar_tarefa(tarefa))
    for tarefa in TAREFAS_GRAVADAS:
        _submeter(kernel, _montar_contexto_da_tarefa(tarefa))
    return kernel
