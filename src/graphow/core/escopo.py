"""Convenções do escopo governado: as propriedades e os valores que as regras de escopo leem.

Escopo governado é o que fecha o trabalho de um Goal ao que o humano aprovou. O
plano aprovado (`Goal.planos`) é a referência, e a Task que nasce depois dele
só entra se disser de que nasceu, por `motivada_por`, ou se for subdivisão,
correção, acompanhamento, integração ou reversão. Os desvios contam por raiz de
cadeia e por Goal, e quem os responde é um gesto da política (`responder_desvio`).
Propriedades de nó não passam pelo SchemaGate: estes nomes são convenção, e
ficam aqui para o kernel, as projeções e as ferramentas lerem os mesmos.
"""

# Constraint.tipo: o critério de aceite que abre a porta da Task emergente e a
# fronteira que delimita o que o Goal não toca.
CAMPO_TIPO_CONSTRAINT: str = "tipo"
CONSTRAINT_CRITERIO_ACEITE: str = "criterio_aceite"
CONSTRAINT_FRONTEIRA: str = "fronteira"

# Note.acao: a descoberta fora dos critérios vira proposta, não Task.
ACAO_PROPOSTA_FORA_DO_GOAL: str = "proposta_fora_do_goal"

# Evidence.acao: o veredito da revisão de escopo sobre uma raiz de decisão.
ACAO_VEREDITO_DE_ESCOPO: str = "veredito_de_escopo"

# Task.atende_criterio: o id do Constraint de critério que a Task emergente atende.
CAMPO_ATENDE_CRITERIO: str = "atende_criterio"

# Task.fase: agrupamento opcional do plano, só para apresentação.
CAMPO_FASE: str = "fase"

# Goal.planos: versões do plano aprovado, só crescem. Goal.respostas_de_desvio:
# as respostas ao placar de desvio, também só crescem.
CAMPO_PLANOS: str = "planos"
CAMPO_RESPOSTAS_DE_DESVIO: str = "respostas_de_desvio"
