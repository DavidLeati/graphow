"""O vocabulário do aceite no centro: o que o kernel e o orquestrador leem e escrevem do Critério, do Achado e da verificação.

Não são termos da ontologia (o SchemaGate não valida propriedades), mas o
kernel lê estes nomes para recusar o fechamento do Goal sem verificação limpa
no commit atual (kernel/fechamento_do_goal.py), e o orquestrador os escreve
(orquestrador/). Ficam aqui, no núcleo, para o kernel não depender do
orquestrador e as duas pontas não divergirem.
"""

# A Evidence de verificação do Goal: a ação que a identifica, o número dela na
# ordem do Goal, o marco que ela verifica e se é a verificação final, sobre o
# Goal inteiro.
ACAO_DA_VERIFICACAO: str = "verificacao_do_goal"
CAMPO_ACAO: str = "acao"
CAMPO_NUMERO: str = "numero"
CAMPO_MARCO: str = "marco"
CAMPO_FINAL: str = "final"
CAMPO_VEREDITO: str = "veredito"
CAMPO_COMMIT: str = "commit"
# O commit do código: o último commit que mudou algo além do documento do Goal.
# O orquestrador commita as pendências no documento depois de verificar, e esse
# commit não muda o que foi verificado.
CAMPO_COMMIT_DO_CODIGO: str = "commit_do_codigo"
# Os pareceres da verificação, um por critério e por decisão: o código (C1), o
# nó do livro-razão, o veredito e a prova.
CAMPO_PARECERES: str = "pareceres"
CAMPO_NO_DO_PARECER: str = "no"
VEREDITO_LIMPO: str = "aprovado"
VEREDITO_COM_BLOQUEANTE: str = "rejeitado"

# No Goal: a ponta da branch do Goal, como o orquestrador a viu no git, com o
# commit do código dela; e o plano, com o nó de cada critério.
CAMPO_PONTA_DO_RAMO: str = "ponta_do_ramo"
CAMPO_PLANO: str = "plano"
CAMPO_CRITERIOS_DO_PLANO: str = "criterios"
CAMPO_CONDUCAO: str = "orquestracao"

# O Critério: o código, o texto, como se prova e o estado que as verificações lhe dão.
CAMPO_CODIGO: str = "codigo"
CAMPO_TEXTO: str = "texto"
CAMPO_VERIFICACAO: str = "verificacao"
CAMPO_ESTADO: str = "estado"
VERIFICACAO_POR_TESTE: str = "teste"
VERIFICACAO_POR_CHECAGEM: str = "checagem"
VERIFICACOES_DE_CRITERIO: tuple[str, ...] = (VERIFICACAO_POR_TESTE, VERIFICACAO_POR_CHECAGEM)
ESTADO_PENDENTE: str = "pendente"
VEREDITO_QUE_ATENDE: str = "atende"
VEREDITO_PARCIAL: str = "parcial"
VEREDITO_NAO_ATENDE: str = "nao_atende"
VEREDITOS_DE_CRITERIO: tuple[str, ...] = (VEREDITO_QUE_ATENDE, VEREDITO_PARCIAL, VEREDITO_NAO_ATENDE)
ESTADOS_DO_CRITERIO: tuple[str, ...] = (ESTADO_PENDENTE, *VEREDITOS_DE_CRITERIO)
# O que o orquestrador escreve no Critério que o gerente gravou: o resto do nó é do humano.
CAMPO_TESTES_DE_ACEITE: str = "testes_de_aceite"
CAMPO_CHECAGEM: str = "checagem"
CAMPO_JA_ATENDIDO: str = "ja_atendido"
CAMPO_COMMIT_DO_ACEITE: str = "commit_do_aceite"
PROPRIEDADES_DERIVADAS_DO_CRITERIO: frozenset[str] = frozenset(
    {CAMPO_ESTADO, CAMPO_TESTES_DE_ACEITE, CAMPO_CHECAGEM, CAMPO_JA_ATENDIDO, CAMPO_COMMIT_DO_ACEITE}
)

# O Achado: a gravidade que o código decide, e o estado. O bloqueante nasce
# aberto, fica corrigido quando a fatia de correção entrega e resolvido quando a
# verificação seguinte do marco sai limpa; o humano pode descartá-lo. O
# acompanhamento nasce pendente e fica como pendência visível do Goal.
CAMPO_GRAVIDADE: str = "gravidade"
GRAVIDADE_BLOQUEANTE: str = "bloqueante"
GRAVIDADE_ACOMPANHAMENTO: str = "acompanhamento"
GRAVIDADES: tuple[str, ...] = (GRAVIDADE_BLOQUEANTE, GRAVIDADE_ACOMPANHAMENTO)
ESTADO_ABERTO: str = "aberto"
ESTADO_CORRIGIDO: str = "corrigido"
ESTADO_RESOLVIDO: str = "resolvido"
ESTADO_DESCARTADO: str = "descartado"
ESTADO_DO_ACOMPANHAMENTO: str = "pendente"
ESTADOS_QUE_ENCERRAM_O_BLOQUEANTE: frozenset[str] = frozenset({ESTADO_RESOLVIDO, ESTADO_DESCARTADO})
