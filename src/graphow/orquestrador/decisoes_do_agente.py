"""O modo autônomo não tem humano no meio: o executor decide, e o teste de aceite errado se refaz sozinho, uma vez.

Na bancada, o executor do api-tarefas abriu uma dúvida (o teste de aceite de
C13 não passava com o próprio comando) e o Goal parou em
`aguardando_resposta`, no modo autônomo, onde ninguém responde. Agora, nesse
modo:

- o schema do executor não oferece `duvida`; a incerteza que ele resolve pela
  spec vai em `decisoes` (questão, decisão, motivo), e o orquestrador grava
  cada uma como Decision "decidida pelo agente", que orienta a fatia e aparece
  no `--status` e no documento do Goal para o humano revisar;
- a única parada é `teste_errado`: o executor diz o critério e o porquê, a
  fatia volta à fila sem falha, e o laço pede ao autor de aceite que refaça os
  testes daquele critério, uma vez por critério, com o argumento do executor
  no briefing. Se o autor os mantém, o porquê dele volta ao executor, e o
  desacordo vai à verificação, que julga; o segundo `teste_errado` do mesmo
  critério não refaz de novo: a fatia segue como entregue.

No modo supervisionado tudo fica como estava: a dúvida vira Question, e a do
teste errado só refaz o teste quando o humano responde que sim (`refazer`).
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.documento_do_goal import TITULO_DAS_DECISOES_DO_AGENTE, caminho_do_documento, com_secao, gravar_se_mudou
from graphow.orquestrador.leitura_do_goal import FatiaRegistrada
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta
from graphow.orquestrador.pedidos_do_humano import CAMPO_DECIDIDA_PELO_AGENTE, DecisaoDoAgente, ler_decisoes_do_agente

CAMPO_TESTE_ERRADO: str = "teste_errado"
CAMPO_RESPOSTA_DO_AUTOR: str = "resposta_do_autor_de_aceite"
CAMPO_DESACORDO: str = "desacordo_sobre_o_teste"
CAMPO_CRITERIOS_REFEITOS: str = "criterios_refeitos_pelo_agente"
# O refazer pedido pelo humano cujo teste novo não falhou antes da implementação: ficou o antigo, e a verificação julga.
CAMPO_REFEITO_SEM_VERMELHO: str = "refeito_sem_vermelho"
PREFIXO_DO_PEDIDO_AUTOMATICO: str = "auto-"


def operacoes_das_decisoes(livro: LivroRazaoDoGoal, id_task: str, tentativa: int, *,
                           decisoes: Sequence[Mapping[str, Any]]) -> list[ItemPatch]:
    """Cada decisão do executor como Decision marcada como do agente, que orienta a fatia."""
    operacoes: list[ItemPatch] = []
    for indice, decisao in enumerate(decisoes, start=1):
        id_no = f"dec-agente-{id_task}-t{tentativa}-{indice}"
        propriedades = {CAMPO_DECIDIDA_PELO_AGENTE: True, "fatia": id_task, "questao": str(decisao.get("questao", "")),
                        "texto": str(decisao.get("decisao", "")), "motivo": str(decisao.get("motivo", ""))}
        rotulo = f"Decidida pelo agente: {propriedades['texto'][:120]}"
        operacoes += livro.produzido(id_no, TipoNo.DECISION, rotulo, propriedades=propriedades)
        operacoes.append(aresta(id_no, id_task, TipoAresta.ORIENTA))
    return operacoes


def linhas_das_decisoes(decisoes: Sequence[DecisaoDoAgente], novas: Sequence[Mapping[str, Any]] = (), *, fatia: str = "",
                        codigos: Mapping[str, str] | None = None) -> list[str]:
    """As decisões do agente para o documento: a fatia pelo código dela (F1), a questão, a decisão e o motivo."""
    nomes = codigos or {}
    todas = [*((nomes.get(d.fatia, d.fatia), d.questao, d.decisao, d.motivo) for d in decisoes),
             *((fatia, str(n.get("questao", "")), str(n.get("decisao", "")), str(n.get("motivo", ""))) for n in novas)]
    return [f"- ({origem}) {questao} -> {decisao.rstrip('.')}. Motivo: {motivo}" for origem, questao, decisao, motivo in todas]


def documentar_decisoes(contexto: ContextoDoGoal, fatia: FatiaRegistrada, novas: Sequence[Mapping[str, Any]]) -> None:
    """A seção das decisões do agente no documento do Goal, com as novas, para entrar no commit da fatia."""
    if not novas:
        return
    caminho = contexto.area / caminho_do_documento(contexto.configuracao.slug)
    if caminho.is_file():
        codigos = {registrada.id: registrada.codigo for registrada in contexto.estado().fatias}
        linhas = linhas_das_decisoes(ler_decisoes_do_agente(contexto.livro.view(), contexto.id_goal), novas, fatia=fatia.codigo,
                                     codigos=codigos)
        gravar_se_mudou(caminho, com_secao(caminho.read_text(encoding="utf-8"), TITULO_DAS_DECISOES_DO_AGENTE, linhas))
