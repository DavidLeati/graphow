# Despacho: o que cada subagente recebe e devolve

O prompt de despacho é ponteiro, não especificação. Tudo o que o subagente precisa saber está no grafo, e ele chega lá pela vista do nó que recebe. Se der vontade de explicar a tarefa no prompt, é o teste do executor frio falhando: registre no grafo o que falta e despache só o ponteiro.

## Quem despacha quem

A raiz despacha só o condutor. O condutor despacha o explorador, os executores e o revisor. Toda chamada do condutor vai em primeiro plano (`run_in_background: false`): em segundo plano ele terminaria antes do filho, e a rodada voltaria pela metade. Isso foi testado em 2026-09-23: o subagente do meio devolveu "Waiting for the nested agent to complete..." e saiu antes do filho acabar.

## O que vai em cada prompt

| Subagente | Quem despacha | Prompt | Devolve |
| :--- | :--- | :--- | :--- |
| `graphow-condutor` | a raiz | `Alvo: <id de Goal, Setor ou Projeto>` e `Sessao: <id>` | `RODADA: ...` |
| `graphow-explorador` | o condutor | `Pergunta: <onde está X?>` e, se souber, `Comece por: <pasta>` | `PONTEIROS` ou `NAO ENCONTRADO` |
| `graphow-executor` ou `graphow-executor-opus` | o condutor | `Task: <id>` e `Sessao: <id>` | `RESULTADO: ...` |
| `graphow-revisor` | o condutor | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...` |
| `graphow-executor` (fechamento) | o condutor | `Fechar: <id>, <id>` e `Sessao: <id>` | `RESULTADO: fechadas` |

`Sessao` é sempre a sessão da raiz, e o condutor a repassa sem mudar. Os nós que os subagentes criam nascem produzidos por ela, e é por ela que a medição atribui o custo ao Goal.

Nunca vai no prompt: trecho da conversa, conteúdo de arquivo, decisão tomada (ela está no grafo, ligada por `orienta`), critério de aceite (está em `criterio_pronto`), nem o que o executor anterior fez (está no Artifact e nas Evidence).

## O retorno do condutor

    RODADA: decomposicao | execucao | nada_a_fazer
    Goal: <id> | <rótulo>
    Cadencia: <valor gravado no grafo>
    Teto: <teto_rodadas gravado no grafo>
    Criadas: <ids das Task criadas>
    Fechadas: <ids>
    Correcoes: <id rejeitada> -> <id correção>
    Questoes: <id> na <id Task>: <uma linha>
    Fila: <n> prontas, <m> impedidas (<motivos>)
    Goal concluido: sim | nao
    Resumo: <no máximo três linhas>

| Retorno | O que a raiz faz |
| :--- | :--- |
| `decomposicao` ou `execucao` | conta ao humano numa linha e segue, salvo portão |
| `Goal concluido: sim` | com cadência `goal`, para; com `setor`, segue para outro Goal do alvo |
| `nada_a_fazer` | para e diz ao humano o que espera por ele |
| `Questoes` | diz o id ao humano na linha da rodada; não para por isso |
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

    RESULTADO: pronto_para_revisao | bloqueada | fora_do_alvo | falhou | fechadas
    Task: <id>
    Artifact: <ids>
    Evidence: <ids>
    Decision: <ids>
    Questao: <id>
    Saida longa: <caminho>
    Resumo: <no máximo três linhas>

| Resultado | O que o condutor faz |
| :--- | :--- |
| `pronto_para_revisao` | despacha o revisor com o Artifact |
| `bloqueada` | há Question aberta, ou a posse é de outro; segue com o resto do lote |
| `fora_do_alvo` | acerta `arquivos_alvo` na Task (por `propor_patch`); ela volta numa rodada seguinte |
| `falhou` | lê a Evidence da falha; desenho novo vira Decision, modelo mais forte vira `modelo: opus`; sem saída, Question |
| `fechadas` | as tarefas estão `concluido`; a rodada devolve |

## O retorno do revisor

    VEREDITO: aprovado | rejeitado | duvida
    Artifact: <id>
    Task: <id>
    Evidence: <id do veredito>
    Criterios nao atendidos: <um por linha, com o id da Evidence que prova>
    Questao: <id>
    Resumo: <no máximo três linhas>

A Evidence do veredito deriva do Artifact e da Task, e cada critério não atendido tem uma Evidence localizada com o trecho que o prova. A Task de correção, criada com `id_tarefa_pai` na tarefa rejeitada, alcança essas Evidence em dois saltos: o executor da correção as lê na vista, sem que o condutor as repita no prompt.

## Mais de um despacho por vez

O condutor despacha as tarefas paralelas numa única mensagem, uma chamada por tarefa, todas em primeiro plano, depois de conferir que os `arquivos_alvo` são disjuntos e que nenhuma depende de outra. O explorador pode rodar em paralelo com qualquer coisa: ele não edita nem escreve no grafo. Duas rodadas ao mesmo tempo, não: a raiz despacha uma de cada vez.
