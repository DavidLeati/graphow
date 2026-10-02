# Despacho: o que cada subagente recebe e devolve

O prompt de despacho é ponteiro, não especificação. Tudo o que o subagente precisa saber está no grafo, e ele chega lá pela vista do nó que recebe. Se der vontade de explicar a tarefa no prompt, é o teste do executor frio falhando: registre no grafo o que falta e despache só o ponteiro.

## Quem despacha quem

A raiz despacha o condutor e, quando a política de governança do projeto entrega um gesto ao árbitro, o `graphow-arbitro`. O condutor despacha o explorador, os executores e os revisores: o `graphow-revisor` para a Task da trilha completa e o `graphow-revisor-sonnet` para a da trilha leve. Toda chamada do condutor vai em primeiro plano (`run_in_background: false`): em segundo plano ele terminaria antes do filho, e a rodada voltaria pela metade. Isso foi testado em 2026-09-23: o subagente do meio devolveu "Waiting for the nested agent to complete..." e saiu antes do filho acabar.

## O que vai em cada prompt

| Subagente | Quem despacha | Prompt | Devolve |
| :--- | :--- | :--- | :--- |
| `graphow-condutor` | a raiz | `Alvo: <id de Goal, Setor ou Projeto>`, `Sessao: <id>` e, se houver a leitura, `Cota: 5h <n>%, semana <n>%` | `RODADA: ...` |
| `graphow-explorador` | o condutor | `Pergunta: <onde está X?>` e, se souber, `Comece por: <pasta>` | `PONTEIROS` ou `NAO ENCONTRADO` |
| `graphow-executor` ou `graphow-executor-opus` | o condutor | `Task: <id>` e `Sessao: <id>` | `RESULTADO: ...` |
| `graphow-revisor` | o condutor | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...` |
| `graphow-revisor-sonnet` | o condutor, para a Task `trilha: leve` | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...`, inclusive `fora_da_trilha` |
| `graphow-executor` (fechamento) | o condutor | `Fechar: <id>, <id>` e `Sessao: <id>` | `RESULTADO: fechadas`, ou `bloqueada` com os ids que o kernel recusou por `fechamento_sem_veredito_aprovado`; retoma a posse de outro executor quando o veredito vigente da tarefa é `aprovado`; fecha também a tarefa aceita pelo teto de correções, quando a Decision de aceite é legítima e a posse está livre |
| `graphow-arbitro` | a raiz | `Alvo: <id de Question, Goal, Setor ou Projeto>` e `Sessao: <id>` | `ARBITRAGEM: ...` |

`Sessao` é sempre a sessão da raiz, e o condutor a repassa sem mudar. Os nós que os subagentes criam nascem produzidos por ela, e é por ela que a medição atribui o custo ao Goal.

`Cota` é a leitura de `get_usage` que a raiz fez antes da rodada, as janelas de 5 horas e semanal, sempre neste formato:

    Alvo: goal-42
    Sessao: 7f3c...
    Cota: 5h 40%, semana 12%

A raiz não escreve no grafo, então a cota vai em texto: o harness lê essa linha na primeira mensagem da transcrição do condutor e a grava no Run dele, e `graphow orquestracao-medir --por-rodada` tira dela quanto cada rodada gastou. O condutor ignora a linha e não a repassa. Sem `get_usage` (no `claude -p`, por exemplo), o despacho vai sem ela.

Nunca vai no prompt: trecho da conversa, conteúdo de arquivo, decisão tomada (ela está no grafo, ligada por `orienta`), critério de aceite (está em `criterio_pronto`), nem o que o executor anterior fez (está no Artifact e nas Evidence).

## O retorno do condutor

    RODADA: decomposicao | execucao | nada_a_fazer
    Goal: <id> | <rótulo>
    Cadencia: <valor gravado no grafo>
    Teto: <teto_rodadas gravado no grafo>
    Criadas: <ids das Task criadas>
    Fechadas: <ids>
    Correcoes: <id rejeitada> -> <id correção>
    Aceites: <id original> -> <id Task de acompanhamento>
    Questoes: <id> na <id Task>: <uma linha>
    Integrar: <ramo_base> ganhou <arquivos do ramo base que colidiram>
    Fila: <n> prontas, <m> impedidas (<motivos>)
    Governanca: <a linha da seção Governanca da vista do Goal>
    Goal concluido: sim | nao
    Resumo: <no máximo três linhas>

| Retorno | O que a raiz faz |
| :--- | :--- |
| `decomposicao` ou `execucao` | conta ao humano numa linha e segue, salvo portão |
| `Governanca` | a política vigente do projeto, para a raiz decidir quem para: com `todos os gestos com o humano`, tudo o que o árbitro faria é do humano; com `com o arbitro: ...`, a raiz despacha o `graphow-arbitro` para cada gesto listado |
| `Goal concluido: sim` | com `fechar_goal` no humano e cadência `goal`, para; com `setor`, segue para outro Goal do alvo. Com `fechar_goal` no árbitro, despacha o árbitro com `Alvo: <Goal>` e segue conforme a cadência |
| `nada_a_fazer` | com o gesto no árbitro, despacha-o antes de parar e volta ao laço se ele decidir algo; senão, para e diz ao humano o que espera por ele |
| `Correcoes` | diz ao humano na linha da rodada; não para por isso |
| `Aceites` | a correção foi reprovada de novo só com critérios de acompanhamento: o condutor fechou a original e abriu a Task de acompanhamento com o que ficou. Diz as duas ao humano na linha da rodada; não para por isso |
| `Questoes` | com `responder_questao` no humano, diz o id ao humano na linha da rodada; com o gesto no árbitro, despacha-o com `Alvo: <id da Question>` e diz na linha quem a decidiu. Não para por isso |
| `Integrar` | portão: o ramo base ganhou arquivos que colidem com o que o Goal toca, e o condutor segurou as tarefas nesses caminhos. Com `integracao` no humano, para e diz a ele o ramo e os arquivos: o merge e a renumeração são dele, ou da sessão principal se ele pedir. Com `integracao` no árbitro, a raiz commita e faz o merge local, e para só se ele conflitar ou pedir renumerar. Em ambos, no "segue" a rodada seguinte confere de novo com `graphow base-colisoes`; o push nunca é da raiz |
| fora do formato, ou o condutor falhou | tenta mais uma rodada; na segunda seguida, para |

## A pergunta ao explorador

Pergunte onde, nunca o quê nem se está certo:

- "onde a taxa de compra é convertida em fator de desconto?"
- "onde o calendário de dias úteis é carregado e com que feriados?"
- "quais chamadores usam `taxa_para_fator`?"

A resposta vem assim, e só assim:

    PONTEIROS
    1. arquivo: src/precos/fator.py
       linhas: 40-42
       relevancia: é a função chamada quando a taxa de compra entra no preço
       trecho:
           def taxa_para_fator(taxa: float, dias: int) -> float:
               """Desconto."""
               return (1 + taxa) ** (-dias / 252)

Antes de registrar um ponteiro como Evidence, o condutor lê ele mesmo as linhas (`Read` com `offset` e `limit`). O trecho da Evidence é o que ele leu, não o que o explorador colou.

## O retorno do executor

    RESULTADO: pronto_para_revisao | posse_perdida | bloqueada | fora_do_alvo | falhou | fechadas
    Task: <id>
    Artifact: <ids>
    Evidence: <ids>
    Decision: <ids>
    Questao: <id>
    Saida longa: <caminho>
    Resumo: <no máximo três linhas>

| Resultado | O que o condutor faz |
| :--- | :--- |
| `pronto_para_revisao` | despacha o revisor com o Artifact: o `graphow-revisor-sonnet` se a Task é `leve`, o `graphow-revisor` nas demais |
| `posse_perdida` | o servidor do executor reiniciou e a posse ficou com o autor antigo; Artifact e Evidence estão gravados. Despacha o revisor com o Artifact, como em `pronto_para_revisao`; aprovada, o fechamento retoma a posse órfã; rejeitada, Question para o humano devolver a posse antes da correção |
| `bloqueada` | há Question aberta, ou a posse é de outro; segue com o resto do lote |
| `fora_do_alvo` | acerta `arquivos_alvo` na Task (por `propor_patch`); ela volta numa rodada seguinte |
| `falhou` | lê a Evidence da falha; desenho novo vira Decision, modelo mais forte vira `modelo: opus`; sem saída, Question |
| `fechadas` | as tarefas estão `concluido`; a rodada devolve |

## O retorno do revisor

    VEREDITO: aprovado | rejeitado | duvida | fora_da_trilha
    Artifact: <id>
    Task: <id>
    Evidence: <id do veredito, ou da triagem>
    Fora da trilha: <arquivo:linhas e o que o trecho muda>
    Criterios nao atendidos: <um por linha: gravidade, o critério e o id da Evidence que prova>
    Questao: <id>
    Resumo: <no máximo três linhas>

A Evidence do veredito deriva do Artifact e da Task, e cada critério não atendido tem uma Evidence localizada com o trecho que o prova e a `gravidade`: `bloqueante` (segurança, permissão, dado em produção ou o critério central da tarefa) ou `acompanhamento` (borda, caso raro, teste que falta, texto). A Task de correção, criada com `id_tarefa_pai` na tarefa rejeitada, alcança essas Evidence em dois saltos: o executor da correção as lê na vista, sem que o condutor as repita no prompt.

`fora_da_trilha` só vem do `graphow-revisor-sonnet`: o diff da Task leve muda comportamento. Ele não aprova nem rejeita. Registra uma Evidence com `triagem: fora_da_trilha` e o trecho que muda comportamento, sem a propriedade `veredito`, para ela não virar o veredito vigente da tarefa nem entrar na contagem da medição. O condutor marca `trilha: completa` na Task (por `propor_patch`) e despacha o `graphow-revisor` com o mesmo Artifact; o veredito que vale é o dele.

## O retorno do árbitro

    ARBITRAGEM: executada | escalada | nada_a_fazer
    Alvo: <id> | <rótulo>
    Respondidas: <id da Question> -> <a resposta em uma linha>
    Descartadas: <id da Question>: <motivo>
    Escaladas: <id da Question, do Aprendizado ou o gesto>: <o que o humano decide, com as opções>
    Constraints: <id> escopa <id do Goal ou da Task>
    Promovidos: <id do Aprendizado> -> <id do Setor ou do Projeto>
    Goal fechado: <id>
    Posses liberadas: <id da Task> (era de <autor>)
    Sessoes encerradas: <ids>
    Decision: <ids>
    Evidence: <ids>
    Resumo: <no máximo três linhas>

| Retorno | O que a raiz faz |
| :--- | :--- |
| `executada` | conta ao humano numa linha o que o árbitro decidiu, com os ids, e segue o laço: a Task da Question respondida volta à fila da rodada seguinte |
| `Escaladas` | a Question segue aberta e é do humano: entra no resumo da parada, com a pergunta e as opções do árbitro. A raiz não despacha o árbitro de novo para o mesmo item |
| `escalada` | não decidiu nada: o item é do humano, e a raiz o trata como Question aberta no humano |
| `nada_a_fazer` | a política não lhe entrega o gesto, ou não há o que decidir; a raiz volta à regra do humano para aquele gesto |
| `Decision` | a Decision que sustenta a resposta nasceu sem `orienta`, que é do planejador: o condutor a lê na rodada seguinte e liga à Task se ela governa |
| `Constraints`, `Goal fechado` | a raiz as conta ao humano na linha da rodada: são decisões que ele reverá |

O árbitro devolve poucas linhas e o resto fica no grafo, como o do condutor. A raiz não lê a vista da Question para conferi-lo.

## Mais de um despacho por vez

O condutor despacha as tarefas paralelas numa única mensagem, uma chamada por tarefa, todas em primeiro plano, depois de conferir que os `arquivos_alvo` são disjuntos e que nenhuma depende de outra. O explorador pode rodar em paralelo com qualquer coisa: ele não edita nem escreve no grafo. Duas rodadas ao mesmo tempo, não: a raiz despacha uma de cada vez. O árbitro nunca roda junto de uma rodada do condutor, porque as Questions e as posses que ele decide são as que a rodada deixou: a raiz o despacha entre as rodadas, uma Question por vez.
