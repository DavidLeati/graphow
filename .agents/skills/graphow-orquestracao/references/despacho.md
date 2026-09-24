# Despacho: o que cada subagente recebe e devolve

O prompt de despacho é ponteiro, não especificação. Tudo o que o subagente precisa saber está no grafo, e ele chega lá pela vista do nó que você aponta. Se você sentir vontade de explicar a tarefa no prompt, é o teste do executor frio falhando: registre o que falta no grafo e despache só o ponteiro.

## O que vai em cada prompt

| Subagente | Prompt | Devolve |
| :--- | :--- | :--- |
| `graphow-explorador` | `Pergunta: <onde está X?>` e, se souber, `Comece por: <pasta>` | `PONTEIROS` ou `NAO ENCONTRADO` |
| `graphow-executor` ou `graphow-executor-opus` | `Task: <id>` e `Sessao: <id>` | `RESULTADO: ...` |
| `graphow-revisor` | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...` |
| `graphow-executor` (fechamento) | `Fechar: <id>, <id>` e `Sessao: <id>` | `RESULTADO: fechadas` |

`Sessao` é sempre a sua sessão atual: os nós que o subagente cria nascem produzidos por ela, e é por ela que a medição atribui o custo ao Goal.

Nunca vai no prompt: trecho da conversa, conteúdo de arquivo, decisão tomada (ela está no grafo, ligada por `orienta`), critério de aceite (está em `criterio_pronto`), nem o que o executor anterior fez (está no Artifact e nas Evidence).

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

Antes de registrar um ponteiro como Evidence, leia você mesmo as linhas (`Read` com `offset` e `limit`). O trecho da Evidence é o que você leu, não o que o explorador colou.

## O retorno do executor

    RESULTADO: pronto_para_revisao | bloqueada | fora_do_alvo | falhou | fechadas
    Task: <id>
    Artifact: <ids>
    Evidence: <ids>
    Decision: <ids>
    Questao: <id>
    Saida longa: <caminho>
    Resumo: <no máximo três linhas>

| Resultado | O que fazer |
| :--- | :--- |
| `pronto_para_revisao` | despache o revisor com o Artifact |
| `bloqueada` | há Question aberta, ou a posse é de outro; espere o humano ou encerre a sessão dizendo o id |
| `fora_do_alvo` | acerte `arquivos_alvo` na Task (por `propor_patch`), confira o paralelismo e despache de novo |
| `falhou` | leia a Evidence da falha; decida se a tarefa precisa de desenho novo (Decision) ou de modelo mais forte |
| `fechadas` | as tarefas estão `concluido`; siga para o passo de encerrar a sessão |

## O retorno do revisor

    VEREDITO: aprovado | rejeitado | duvida
    Artifact: <id>
    Task: <id>
    Evidence: <id do veredito>
    Criterios nao atendidos: <um por linha, com o id da Evidence que prova>
    Questao: <id>
    Resumo: <no máximo três linhas>

A Evidence do veredito deriva do Artifact e da Task, e cada critério não atendido tem uma Evidence localizada com o trecho que o prova. A Task de correção, criada com `id_tarefa_pai` na tarefa rejeitada, alcança essas Evidence em dois saltos: o executor da correção as lê na vista, sem que você as repita no prompt.

## Mais de um despacho por vez

Despache as tarefas paralelas numa única mensagem, uma chamada por tarefa, só depois de conferir que os `arquivos_alvo` são disjuntos e que nenhuma depende de outra. O explorador pode rodar em paralelo com qualquer coisa: ele não edita nem escreve no grafo.
