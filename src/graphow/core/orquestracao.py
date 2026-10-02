"""Propriedades que a orquestração grava na Task, no Goal, na Evidence de revisão e na Decision de aceite.

Não são termos da ontologia: o SchemaGate não valida propriedades e a assinatura
da ontologia não as cobre. São a convenção que o orquestrador escreve por
`criar_tarefa`, que a fila de trabalho devolve e que a medição lê, declarada num
lugar só para as três pontas não divergirem.
"""

from collections.abc import Mapping
from typing import Any

# Na Task: o modelo que deve executá-la e por quê, os arquivos que ela toca
# (é o que decide o paralelismo) e, na tarefa de correção, a Evidence de
# revisão que a motivou. O critério de aceite é o `criterio_pronto` de sempre.
CAMPO_MODELO: str = "modelo"
CAMPO_MOTIVO_DO_MODELO: str = "motivo_modelo"
CAMPO_ARQUIVOS_ALVO: str = "arquivos_alvo"
CAMPO_CORRIGE: str = "corrige"
CAMPO_CRITERIO_PRONTO: str = "criterio_pronto"

# Na Task: a trilha que ela percorre. A leve serve a tarefa trivial, só texto,
# comentário ou documentação: pula o teste do executor frio, roda em Sonnet e
# vai ao revisor Sonnet. Ausente vale como completa, que é a trilha de sempre.
CAMPO_TRILHA: str = "trilha"
TRILHA_LEVE: str = "leve"
TRILHA_COMPLETA: str = "completa"
TRILHAS: frozenset[str] = frozenset({TRILHA_LEVE, TRILHA_COMPLETA})

# No Goal: o rótulo da configuração de modelos com que ele foi orquestrado,
# para a medição comparar o mesmo conjunto de tarefas sob arranjos diferentes.
CAMPO_CONFIGURACAO: str = "configuracao"

# No Goal, no Setor ou no Projeto, gravadas pelo humano: o ramo do git em que
# o trabalho do Goal vai ser integrado (`origin/stage` ou `stage`) e os globs
# dos caminhos em que dois ramos colidem sem tocar o mesmo arquivo, como as
# migrations numeradas de um mesmo diretório. O Goal herda cada uma do Setor e
# depois do Projeto quando não a traz.
CAMPO_RAMO_BASE: str = "ramo_base"
CAMPO_CAMINHOS_DE_COLISAO: str = "caminhos_de_colisao"

# No Artifact: os arquivos que o executor alterou para entregar a tarefa.
CAMPO_ARQUIVOS: str = "arquivos"

# Na Evidence do revisor: o que ele concluiu contra os critérios da tarefa.
CAMPO_VEREDITO: str = "veredito"
VEREDITO_APROVADO: str = "aprovado"
VEREDITO_REJEITADO: str = "rejeitado"

# Na Evidence do revisor Sonnet, quando o diff de uma Task da trilha leve muda
# comportamento: ele não julga, e a Task vai ao revisor Opus. Fica fora de
# `veredito` de propósito, para não virar o veredito vigente da tarefa nem
# entrar na contagem de aprovações e rejeições da medição.
CAMPO_TRIAGEM: str = "triagem"
TRIAGEM_FORA_DA_TRILHA: str = "fora_da_trilha"

# Na Decision do condutor que aceita a entrega depois da segunda reprovação,
# quando nenhum critério não atendido é bloqueante: é por ela que a medição
# conta os aceites pelo teto de correções.
CAMPO_ACAO: str = "acao"
ACAO_ACEITE_APOS_REPROVACAO: str = "aceite_apos_reprovacao"

# Na Task que o próprio grafo abre, sem revisor, para manter a memória: condensar
# a sessão e consolidar aprendizados. O kernel as isenta do veredito de revisão
# para fechar, porque ninguém as reviria e a memória travaria.
ACAO_DE_CONDENSAR: str = "condensar_sessao"
ACAO_DE_CONSOLIDAR: str = "consolidar_aprendizados"
ACOES_ABERTAS_PELO_GRAFO: frozenset[str] = frozenset({ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR})


def ler_textos(valor: object) -> tuple[str, ...]:
    """Lista de textos não vazios, sem repetição e na ordem dada; um texto solto vira lista de um."""
    brutos = [valor] if isinstance(valor, str) else valor if isinstance(valor, (list, tuple)) else []
    return tuple(dict.fromkeys(str(item).strip() for item in brutos if str(item).strip()))


def ler_texto(propriedades: Mapping[str, Any], chave: str) -> str:
    """O valor textual da propriedade, sem espaços nas pontas; vazio quando ausente."""
    return str(propriedades.get(chave, "") or "").strip()
