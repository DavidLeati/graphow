"""O catálogo de governança publicado para a interface: gestos, valores aceitos e presets.

A tela de configurações oferece gestos, valores e presets. Uma cópia dessas
listas no JavaScript divergiria do portão na primeira mudança de política, e a
tela passaria a oferecer justamente o que o kernel recusa. Por isso ela
pergunta aqui, e a resposta sai das mesmas tabelas que a política aplica; só a
descrição curta de cada gesto é texto da interface.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from graphow.core.governanca import (
    GESTOS_INTEIROS,
    GESTOS_POR_PAPEL,
    PRESETS_FIXOS,
    VALORES_ACEITOS,
    Gesto,
    PresetDoProjeto,
    PresetGovernanca,
)
from graphow.core.leituras_inteiras import LEITURAS_INTEIRAS
from graphow.core.orquestracao import CAMPO_CAMINHOS_DE_COLISAO, CAMPO_RAMO_BASE
from graphow.kernel.planejamento_governanca import (
    CADENCIAS_ACEITAS,
    CAMPO_CADENCIA,
    CAMPO_GRAVACAO_DO_GERENTE,
    CAMPO_TETO_RODADAS,
    GRAVACAO_APOS_APROVACAO,
    GRAVACOES_DO_GERENTE_ACEITAS,
    TETO_DE_RODADAS_MINIMO,
    VALOR_HERDAR,
)

# Domínio inteiro até este tamanho vai como lista de opções; acima, a tela pede um número entre minimo e maximo.
MAIOR_DOMINIO_EM_LISTA: int = 10

DESCRICOES_DOS_GESTOS: Mapping[Gesto, str] = MappingProxyType({
    Gesto.RESPONDER_QUESTAO: "Responder ou descartar uma dúvida aberta (Question)",
    Gesto.PROMOVER_APRENDIZADO: "Dar alcance a um Aprendizado, de um Setor, de um Projeto ou global",
    Gesto.CONSTRAINT: "Criar uma restrição inviolável (Constraint)",
    Gesto.ESTRUTURA: "Criar Projeto, Setor e a camada de contenção: estrito só para o humano, ilimitado para todo agente",
    Gesto.EXCLUIR: "Excluir nós e arestas do grafo",
    Gesto.FECHAR_GOAL: "Marcar um Goal como concluído",
    Gesto.ENCERRAR_SESSAO: "Encerrar uma Sessão",
    Gesto.LIBERAR_POSSE_ALHEIA: "Liberar a posse de uma tarefa que é de outro autor",
    Gesto.INTEGRACAO: "Quando a entrega é código num repositório: commitar e integrar no ramo base (merge local); o push segue humano",
    Gesto.MAX_CORRECOES: "Reprovações em cadeia antes do teto: a de ordem N já escala (2 = a original e a primeira correção)",
    Gesto.ACAO_EXTERNA: "Executar a tarefa que é um gesto no mundo, sem arquivo (enviar e-mail, marcar reunião): só o humano, ou também o executor, quando ele tem as ferramentas",
    Gesto.APROVAR_PLANO: "Aprovar o plano de um Goal, que vira a referência do escopo: o trabalho que nasce depois precisa se ligar a ele",
    Gesto.RESPONDER_DESVIO: "Responder ao alerta de desvio do plano; só a resposta do humano zera o contador do Goal",
    Gesto.LIMIAR_DESVIO_POR_RAIZ: "Quantas Tasks emergentes uma mesma decisão gera antes de o desvio disparar (menor vale mais restrito)",
    Gesto.LIMIAR_DESVIO_POR_GOAL: "Quantas Tasks emergentes o Goal acumula, desde a última resposta do humano, antes de o desvio disparar",
    Gesto.TETO_EXPANSAO: "Tasks emergentes admitidas num Goal até um responder_desvio; acima disso o kernel recusa a Task nova. 0 desliga",
})

DESCRICOES_DOS_PRESETS: Mapping[str, str] = MappingProxyType({
    PresetGovernanca.GOVERNANCA_MAXIMA.value: "Todos os gestos são do humano; o agente propõe e a pessoa decide",
    PresetGovernanca.ARBITRAGEM_MAXIMA.value: "O árbitro faz todos os gestos que a política pode delegar",
    PresetGovernanca.PERSONALIZADA.value: "Você escolhe, gesto a gesto, quem decide; é o único preset editável",
    VALOR_HERDAR: "Só no Projeto: vale a política global, e cada gesto pode ser sobrescrito",
})

DESCRICOES_DA_OPERACAO: Mapping[str, str] = MappingProxyType({
    CAMPO_CADENCIA: "Quando a orquestração para e devolve a palavra ao humano",
    CAMPO_TETO_RODADAS: "Quantas rodadas a orquestração roda antes de parar",
    CAMPO_RAMO_BASE: "Só quando o trabalho mora num repositório git: o ramo em que o Goal vai ser integrado",
    CAMPO_CAMINHOS_DE_COLISAO: "Só com ramo base: globs dos caminhos em que dois ramos colidem sem tocar o mesmo arquivo",
    CAMPO_GRAVACAO_DO_GERENTE: "Quando o gerente grava a definição da demanda: depois da aprovação ou a cada confirmação",
})


def montar_catalogo_de_governanca() -> dict[str, Any]:
    """Gestos com os valores aceitos, presets com os valores fixos e o vocabulário operacional."""
    return {
        "gestos": [_descrever_gesto(gesto) for gesto in Gesto],
        "presets": [_descrever_preset(preset.value) for preset in PresetGovernanca],
        "presets_do_projeto": [_descrever_preset(preset.value) for preset in PresetDoProjeto],
        "valor_herdar": VALOR_HERDAR,
        "operacao": _descrever_operacao(),
    }


def _descrever_gesto(gesto: Gesto) -> dict[str, Any]:
    """O gesto com a descrição curta e os valores que a política aceita para ele."""
    return {
        "gesto": gesto.value,
        "descricao": DESCRICOES_DOS_GESTOS[gesto],
        "decide_por_papel": gesto in GESTOS_POR_PAPEL,
        "valores": _valores_do_gesto(gesto),
        **_dominio_inteiro(gesto),
    }


def _dominio_inteiro(gesto: Gesto) -> dict[str, int]:
    """Mínimo, máximo e padrão do gesto que é um número; vazio nos demais."""
    if gesto not in GESTOS_INTEIROS:
        return {}
    leitura = LEITURAS_INTEIRAS[gesto.value]
    return {"minimo": leitura.minimo, "maximo": leitura.maximo, "padrao": leitura.padrao}


def _valores_do_gesto(gesto: Gesto) -> list[Any]:
    """Os valores aceitos do gesto, em ordem estável."""
    if gesto in GESTOS_INTEIROS:
        leitura = LEITURAS_INTEIRAS[gesto.value]
        return list(range(leitura.minimo, leitura.maximo + 1)) if leitura.maximo <= MAIOR_DOMINIO_EM_LISTA else []
    return sorted(VALORES_ACEITOS[gesto])


def _descrever_preset(nome: str) -> dict[str, Any]:
    """O preset com a descrição e, nos fixos, o valor de cada gesto."""
    fixo = _valores_fixos(nome)
    return {
        "preset": nome,
        "descricao": DESCRICOES_DOS_PRESETS[nome],
        "fixo": fixo is not None,
        "valores": {gesto.value: valor for gesto, valor in fixo.items()} if fixo is not None else None,
    }


def _valores_fixos(nome: str) -> Mapping[Gesto, Any] | None:
    """Os valores de um preset fixo, ou None para a personalizada e o `herdar`."""
    try:
        return PRESETS_FIXOS.get(PresetGovernanca(nome))
    except ValueError:
        return None


def _descrever_operacao() -> dict[str, Any]:
    """As propriedades operacionais do Projeto, com a descrição e o domínio de cada uma."""
    return {
        CAMPO_CADENCIA: {"descricao": DESCRICOES_DA_OPERACAO[CAMPO_CADENCIA], "valores": list(CADENCIAS_ACEITAS)},
        CAMPO_TETO_RODADAS: {
            "descricao": DESCRICOES_DA_OPERACAO[CAMPO_TETO_RODADAS],
            "minimo": TETO_DE_RODADAS_MINIMO,
        },
        CAMPO_RAMO_BASE: {"descricao": DESCRICOES_DA_OPERACAO[CAMPO_RAMO_BASE]},
        CAMPO_CAMINHOS_DE_COLISAO: {"descricao": DESCRICOES_DA_OPERACAO[CAMPO_CAMINHOS_DE_COLISAO]},
        CAMPO_GRAVACAO_DO_GERENTE: {
            "descricao": DESCRICOES_DA_OPERACAO[CAMPO_GRAVACAO_DO_GERENTE],
            "valores": list(GRAVACOES_DO_GERENTE_ACEITAS),
            "padrao": GRAVACAO_APOS_APROVACAO,
        },
    }
