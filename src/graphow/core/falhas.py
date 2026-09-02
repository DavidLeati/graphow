"""Vocabulário de modos de falha, na taxonomia MAST (Cemri et al., 2025).

O classificador lia a mensagem de erro em português e decidia por substring:
"ciclo", "permissão", "orçamento". Funcionava até a primeira reescrita de texto,
e nada avisava quando quebrasse. O vocabulário passa a ser declarado no portão
que recusa, e a mensagem volta a ser só o que ela é — texto para quem lê.

Os três macro-grupos são os do MAST. Os modos são o refinamento do Graphow
dentro deles: cada recusa que o kernel sabe emitir tem um nome estável aqui.
Ver achado A-13.
"""

from collections.abc import Mapping
from enum import Enum


class CategoriaFalhaMAST(str, Enum):
    """3 macro-categorias de falha em sistemas multi-agente conforme MAST."""

    DESIGN_DO_SISTEMA = "design_do_sistema"
    DESALINHAMENTO_DE_AGENTE = "desalinhamento_de_agente"
    VERIFICACAO_DE_TAREFA = "verificacao_de_tarefa"


class ModoFalhaMAST(str, Enum):
    """Modos específicos de falha que os portões do kernel sabem recusar."""

    VIOLACAO_PERMISSAO_PAPEL = "violacao_permissao_papel"
    PROTOTYPE_POLLUTION = "prototype_pollution"
    CICLO_DEPENDENCIA = "ciclo_dependencia"
    FECHAMENTO_COM_BLOQUEIO_PENDENTE = "fechamento_com_bloqueio_pendente"
    ESTOURO_ORCAMENTO_TOKENS = "estouro_orcamento_tokens"
    TIPO_DESCONHECIDO = "tipo_desconhecido"
    CONFLITO_CONCORRENCIA_LOCK = "conflito_concorrencia_lock"
    POSSE_DE_TAREFA_AUSENTE = "posse_de_tarefa_ausente"
    CAMINHO_INVALIDO = "caminho_invalido"
    ESTRUTURA_INCOMPLETA = "estrutura_incompleta"
    REFERENCIA_INEXISTENTE = "referencia_inexistente"
    PAR_DE_ARESTA_INVALIDO = "par_de_aresta_invalido"
    OUTRO = "outro"


CATEGORIA_POR_MODO: Mapping[ModoFalhaMAST, CategoriaFalhaMAST] = {
    ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL: CategoriaFalhaMAST.DESALINHAMENTO_DE_AGENTE,
    ModoFalhaMAST.PROTOTYPE_POLLUTION: CategoriaFalhaMAST.DESALINHAMENTO_DE_AGENTE,
    ModoFalhaMAST.CICLO_DEPENDENCIA: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE: CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA,
    ModoFalhaMAST.ESTOURO_ORCAMENTO_TOKENS: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.TIPO_DESCONHECIDO: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.CONFLITO_CONCORRENCIA_LOCK: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.POSSE_DE_TAREFA_AUSENTE: CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA,
    ModoFalhaMAST.CAMINHO_INVALIDO: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.ESTRUTURA_INCOMPLETA: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.REFERENCIA_INEXISTENTE: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.PAR_DE_ARESTA_INVALIDO: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
    ModoFalhaMAST.OUTRO: CategoriaFalhaMAST.DESIGN_DO_SISTEMA,
}


def categoria_de(modo: ModoFalhaMAST) -> CategoriaFalhaMAST:
    """Macro-categoria MAST à qual o modo pertence, sem consulta a texto."""
    return CATEGORIA_POR_MODO.get(modo, CategoriaFalhaMAST.DESIGN_DO_SISTEMA)
