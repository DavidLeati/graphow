"""Testes unitários para a conversão de JSON Patch em eventos do log."""

from graphow.core.events import TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch


def _proposta(operacoes: list[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO) -> PropostaPatch:
    """Monta uma proposta com as operações e o papel informados."""
    dados = DadosPropostaPatch(
        autor="david", papel=papel, operacoes=tuple(operacoes), justificativa="conversao"
    )
    return PropostaPatch.criar(dados)


def test_numera_eventos_a_partir_da_sequencia_base_nominal() -> None:
    """As sequências continuam de onde o log parou, sem lacunas."""
    operacoes = [
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/n1", value={"id": "n1", "tipo": TipoNo.TASK.value}),
        ItemPatch(
            op=OperacaoPatch.ADD,
            path="/arestas/e1",
            value={"id": "e1", "origem_id": "s1", "destino_id": "n1", "tipo": TipoAresta.PRODUZ.value},
        ),
    ]
    eventos = ConversorPatchParaEventos().converter(_proposta(operacoes), seq_base=41)
    assert [evento.seq for evento in eventos] == [42, 43]
    assert eventos[0].tipo_evento == TipoEvento.NO_CRIADO
    assert eventos[1].tipo_evento == TipoEvento.ARESTA_CRIADA


def test_atualizacao_de_rotulo_e_de_propriedade_geram_payloads_distintos_nominal() -> None:
    """Rótulo e propriedade viajam em campos diferentes do payload."""
    operacoes = [
        ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/n1/rotulo", value="Novo titulo"),
        ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/n1/propriedades/status", value="concluido"),
    ]
    eventos = ConversorPatchParaEventos().converter(_proposta(operacoes), seq_base=0)
    assert eventos[0].payload == {"id": "n1", "rotulo": "Novo titulo"}
    assert eventos[1].payload == {"id": "n1", "propriedades": {"status": "concluido"}}


def test_origem_reflete_o_papel_do_autor_nominal() -> None:
    """Propostas humanas e de agentes registram origens distintas no log."""
    operacao = [ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/n1")]
    conversor = ConversorPatchParaEventos()
    evento_humano = conversor.converter(_proposta(operacao, PapelAutor.HUMANO), 0)[0]
    evento_agente = conversor.converter(_proposta(operacao, PapelAutor.EXECUTOR), 0)[0]
    assert evento_humano.origem == OrigemEvento.HUMANO
    assert evento_agente.origem == OrigemEvento.HARNESS


def test_caminho_fora_da_ontologia_nao_gera_evento_edge_case() -> None:
    """Caso de borda: caminhos que não são de nós nem de arestas são ignorados."""
    operacoes = [
        ItemPatch(op=OperacaoPatch.ADD, path="/metadados/qualquer", value=1),
        ItemPatch(op=OperacaoPatch.ADD, path="/", value=1),
    ]
    assert ConversorPatchParaEventos().converter(_proposta(operacoes), 0) == ()


def test_operacao_de_aresta_nao_suportada_nao_gera_evento_edge_case() -> None:
    """Caso de borda: substituir uma aresta inteira não tem evento correspondente."""
    operacoes = [ItemPatch(op=OperacaoPatch.REPLACE, path="/arestas/e1", value={"id": "e1"})]
    assert ConversorPatchParaEventos().converter(_proposta(operacoes), 0) == ()


def test_numeracao_ignora_operacoes_descartadas_edge_case() -> None:
    """Caso de borda: operações sem evento não consomem posições de sequência."""
    operacoes = [
        ItemPatch(op=OperacaoPatch.ADD, path="/metadados/x", value=1),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/n1", value={"id": "n1", "tipo": TipoNo.NOTE.value}),
    ]
    eventos = ConversorPatchParaEventos().converter(_proposta(operacoes), seq_base=7)
    assert [evento.seq for evento in eventos] == [8]


def test_remover_propriedade_declara_a_remocao_no_payload_nominal() -> None:
    """A intenção de apagar viaja no evento, não escondida num valor nulo.

    Inferir a remoção do valor confundiria 'apagar a chave' com 'gravar nulo', e
    nulo é um valor que alguém pode legitimamente querer escrever.
    """
    operacao = ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/n1/propriedades/rascunho")
    eventos = ConversorPatchParaEventos().converter(_proposta([operacao]), seq_base=0)

    assert eventos[0].tipo_evento == TipoEvento.NO_ATUALIZADO
    assert eventos[0].payload == {"id": "n1", "propriedades_removidas": ["rascunho"]}


def test_gravar_propriedade_nula_nao_vira_remocao_edge_case() -> None:
    """Caso de borda: um REPLACE com valor nulo escreve nulo, não apaga a chave."""
    operacao = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/n1/propriedades/revisor", value=None)
    eventos = ConversorPatchParaEventos().converter(_proposta([operacao]), seq_base=0)

    assert eventos[0].payload == {"id": "n1", "propriedades": {"revisor": None}}


def test_remover_o_no_inteiro_nao_vira_remocao_de_propriedade_edge_case() -> None:
    """Caso de borda: o caminho curto continua sendo exclusão de nó."""
    operacao = ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/n1")
    eventos = ConversorPatchParaEventos().converter(_proposta([operacao]), seq_base=0)

    assert eventos[0].tipo_evento == TipoEvento.NO_REMOVIDO
