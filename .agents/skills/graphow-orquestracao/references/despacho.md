# Despacho: o que cada subagente recebe e devolve

O prompt de despacho é ponteiro, não especificação. Tudo o que o subagente precisa saber está no grafo, e ele chega lá pela vista do nó que recebe. Se der vontade de explicar a tarefa no prompt, é o teste do executor frio falhando: registre no grafo o que falta e despache só o ponteiro.

## Quem despacha quem

A raiz despacha o condutor e, quando a política de governança do projeto entrega um gesto ao árbitro, o `graphow-arbitro`. O condutor despacha o explorador, os executores e os revisores: o `graphow-revisor` para a Task da trilha completa e o `graphow-revisor-sonnet` para a da trilha leve. A revisão de escopo de uma decisão-raiz também é do condutor e vai sempre ao `graphow-revisor` (Opus), nunca ao Sonnet. Toda chamada do condutor vai em primeiro plano (`run_in_background: false`): em segundo plano ele terminaria antes do filho, e a rodada voltaria pela metade. Isso foi testado em 2026-09-23: o subagente do meio devolveu "Waiting for the nested agent to complete..." e saiu antes do filho acabar.

## O que vai em cada prompt

| Subagente | Quem despacha | Prompt | Devolve |
| :--- | :--- | :--- | :--- |
| `graphow-condutor` | a raiz | `Alvo: <id de Goal, Setor ou Projeto>`, `Sessao: <id>`, se o humano deu instrução nova, uma `Humano: <instrução literal>` por instrução e, se houver a leitura, `Cota: 5h <n>%, semana <n>%` | `RODADA: ...` |
| `graphow-explorador` | o condutor | `Pergunta: <onde está X?>` e, se souber, `Comece por: <pasta ou fonte>` | `PONTEIROS` ou `NAO ENCONTRADO` |
| `graphow-executor` ou `graphow-executor-opus` | o condutor | `Task: <id>` e `Sessao: <id>` | `RESULTADO: ...` |
| `graphow-revisor` | o condutor | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...` |
| `graphow-revisor-sonnet` | o condutor, para a Task `trilha: leve` | `Artifact: <id>` e `Sessao: <id>` | `VEREDITO: ...`, inclusive `fora_da_trilha` |
| `graphow-revisor` (revisão de escopo) | o condutor, para a raiz de decisão que passou de K sem veredito de escopo | `Alvo: <id da raiz>`, `Goal: <id>` e `Sessao: <id>` | `ESCOPO: ...` |
| `graphow-executor` (fechamento) | o condutor | `Fechar: <id>, <id>` e `Sessao: <id>` | `RESULTADO: fechadas`, ou `bloqueada` com os ids que o kernel recusou por `fechamento_sem_veredito_aprovado`; retoma a posse de outro executor quando o veredito vigente da tarefa é `aprovado`; fecha também a tarefa aceita pelo teto de correções, quando a Decision de aceite é legítima e a posse está livre |
| `graphow-arbitro` | a raiz | `Alvo: <id de Question, Goal, Setor ou Projeto>` e `Sessao: <id>`; o Goal como alvo serve também a `aprovar_plano` e a `responder_desvio` | `ARBITRAGEM: ...` |

`Sessao` é sempre a sessão da raiz, e o condutor a repassa sem mudar. Os nós que os subagentes criam nascem produzidos por ela, e é por ela que a medição atribui o custo ao Goal.

`Cota` é a leitura de `get_usage` que a raiz fez antes da rodada, as janelas de 5 horas e semanal, sempre neste formato:

    Alvo: goal-42
    Sessao: 7f3c...
    Cota: 5h 40%, semana 12%

A raiz não escreve no grafo, então a cota vai em texto: o harness lê essa linha na primeira mensagem da transcrição do condutor e a grava no Run dele, e `graphow orquestracao-medir --por-rodada` tira dela quanto cada rodada gastou. O condutor ignora a linha e não a repassa. Sem `get_usage` (no `claude -p`, por exemplo), o despacho vai sem ela.

`Humano` é a instrução que o humano deu na conversa desde a última rodada e que o grafo ainda não tem, copiada literal, uma linha por instrução, antes da `Cota`:

    Alvo: goal-42
    Sessao: 7f3c...
    Humano: prova num clone do ambiente de teste, em dia útil
    Humano: confere as duas Questions sem resposta antes de seguir
    Cota: 5h 40%, semana 12%

O condutor a grava no grafo antes de qualquer teste ou despacho. Se ela muda critério, alvo ou decomposição de alguma Task, ele acerta o desenho e devolve `RODADA: decomposicao` sem executar, e a execução vai para a rodada seguinte, sobre o desenho já acertado; se não muda, a rodada segue normalmente. A `Cota` fica por último, por ordem: o harness só aceita a cota no começo da linha, então a que uma `Humano` citasse no meio do texto não conta.

Nunca vai no prompt: trecho da conversa (a instrução literal na linha `Humano` é a exceção, e só ela), conteúdo de arquivo ou de documento, resumo de rodada, decisão tomada (ela está no grafo, ligada por `orienta`), critério de aceite (está em `criterio_pronto`), nem o que o executor anterior fez (está no Artifact e nas Evidence).

## O retorno do condutor

    RODADA: decomposicao | execucao | nada_a_fazer
    Goal: <id> | <rótulo>
    Cadencia: <valor gravado no grafo>
    Teto: <teto_rodadas gravado no grafo>
    Criadas: <ids das Task criadas>
    Fechadas: <ids>
    Correcoes: <id rejeitada> -> <id correção>
    Aceites: <id original> -> <id Task de acompanhamento>
    Questoes: <id> na <id Task>: <uma linha> | cruza a fronteira: sim | nao | talvez
    Propostas: <id da Note> | <rótulo> | origens: <ids>
    Integrar: <ramo_base> ganhou <arquivos do ramo base que colidiram>
    Acao externa: <id Task> | <rótulo> | criterio: <criterio_pronto>
    Plano: nao_aprovado | nova_versao | <n> Tasks: <id> <rótulo> [fase] depende_de <ids>; ...
    Desvio: <gatilhos disparados e raízes sem veredito de escopo, lidos do placar> | nenhum
    Revisao de escopo: <id da raiz> -> cabe | nao_cabe | parcial (<id da Evidence>)
    Governanca: <a linha da seção Governanca da vista do Goal, como está>
    Fila: <n> prontas, <m> impedidas (<motivos>)
    Goal concluido: sim | nao
    Custo: <id Task ou Artifact> <subagente> <min> min, <n> ferramentas, <tokens> tok; ...
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
| `Acao externa` | portão humano, em qualquer política: uma linha por Task de `entrega: acao_externa` pronta com o gesto `acao_externa` no humano. O condutor não despachou executor para ela e seguiu com as outras tarefas. A raiz mostra à pessoa a tarefa e o critério e espera. Quando ela disser que fez, a raiz registra em nome dela, pelo servidor `graphow` de papel `humano`: `assumir_tarefa`, um `propor_patch` com o `Artifact` (sem `arquivos`, com `resumo`), a `Evidence` de prova (`fonte` e `resultado`, com `deriva_de` ao Artifact e à Task) e o status `pronto_para_revisao`, e `liberar_tarefa`. A rodada seguinte revisa e fecha. A pessoa também pode registrar pela interface |
| `Integrar` | portão, quando o trabalho mora num repositório git: o ramo base ganhou arquivos que colidem com o que o Goal toca, e o condutor segurou as tarefas nesses caminhos. Com `integracao` no humano, para e diz a ele o ramo e os arquivos: o merge e a renumeração são dele, ou da sessão principal se ele pedir. Com `integracao` no árbitro, a raiz commita e faz o merge local, e para só se ele conflitar ou pedir renumerar (editar arquivo do trabalho). Em ambos, no "segue" a rodada seguinte confere de novo com `graphow base-colisoes`; o push nunca é da raiz |
| `Plano` | `nao_aprovado`: o Goal não tem `aprovar_plano`, e o condutor não despachou executor (o kernel o recusaria). A linha traz a decomposição. `nova_versao`: a decomposição ganhou uma onda nova, listada pelos ids, que pede outra versão. Com o gesto no humano, a raiz mostra a decomposição, pede `aprovar_plano` e para; com o gesto no árbitro, despacha-o com `Alvo: <Goal>`. Não despacha execução para o Goal até a aprovação |
| `Desvio` | `nenhum`, ou os gatilhos disparados (`K em <raiz> (n/K)`, `M (n/M)`, `inanição`) e as raízes sem veredito de escopo, como o placar da vista do Goal os diz. Com gatilho disparado e `responder_desvio` no humano (o default de todos os presets), é portão em qualquer cadência: a raiz para e mostra o placar. Com o gesto no árbitro (só a política personalizada), despacha-o com `Alvo: <Goal>` em vez de parar. Uma vez por gatilho (tipo e raiz) |
| `Revisao de escopo` | o condutor despachou o revisor para a raiz e o veredito já está no grafo. A raiz o repete na linha em que mostra o placar ao humano, ou ao árbitro. Não bloqueia nada |
| `Custo` | o que cada filho da rodada gastou, lido pelo condutor do bloco de uso do retorno: o executor é neto da raiz e não aparece no painel. A raiz soma minutos e tokens na linha da rodada e repete cada `ALERTA` com o id (executor acima de ~40 min ou ~100 ferramentas: a Task estourou o tamanho). Ao parar, lista os `ALERTA` da sequência e sugere `graphow orquestracao-medir --goal <id> --por-rodada` para o detalhe. Não para por isso |
| fora do formato, ou o condutor falhou | tenta mais uma rodada; na segunda seguida, para |

## A pergunta ao explorador

Pergunte onde, nunca o quê nem se está certo:

- "onde a taxa de compra é convertida em fator de desconto?"
- "onde o calendário de dias úteis é carregado e com que feriados?"
- "quais chamadores usam `taxa_para_fator`?"
- "em que ata a diretoria aprovou o índice de reajuste, e com que número?"

A resposta vem assim, e só assim:

    PONTEIROS
    1. arquivo: src/precos/fator.py
       linhas: 40-42
       relevancia: é a função chamada quando a taxa de compra entra no preço
       trecho:
           def taxa_para_fator(taxa: float, dias: int) -> float:
               """Desconto."""
               return (1 + taxa) ** (-dias / 252)

Fora de arquivo com linhas, o ponteiro vem na forma de fonte genérica, com `local` livre no lugar de `linhas`:

    2. fonte: https://www.ibge.gov.br/indicadores/ipca
       local: tabela de variação acumulada em 12 meses, linha set/2026
       relevancia: é o índice que o contrato manda aplicar no reajuste
       trecho:
           set/2026 | 4,42

Um documento salvo na base de trabalho, como `atas/2026-10-03-diretoria.md`, é arquivo e vem com `linhas`.

Antes de registrar um ponteiro como Evidence, o condutor lê ele mesmo a fonte (as linhas do arquivo com `Read` e `offset` e `limit`, o trecho do documento). O trecho da Evidence é o que ele leu, não o que o explorador colou.

## O retorno do executor

    RESULTADO: pronto_para_revisao | posse_perdida | bloqueada | fora_do_alvo | falta_contexto | falta_ferramenta | acao_externa_do_humano | falhou | fechadas
    Task: <id>
    Artifact: <ids>
    Evidence: <ids>
    Decision: <ids>
    Questao: <id>
    Pergunta: <onde está X?>
    Ferramenta: <o que falta>
    Saida longa: <caminho>
    Resumo: <no máximo três linhas>

| Resultado | O que o condutor faz |
| :--- | :--- |
| `pronto_para_revisao` | despacha o revisor com o Artifact: o `graphow-revisor-sonnet` se a Task é `leve`, o `graphow-revisor` nas demais |
| `posse_perdida` | o servidor do executor reiniciou e a posse ficou com o autor antigo; Artifact e Evidence estão gravados. Despacha o revisor com o Artifact, como em `pronto_para_revisao`; aprovada, o fechamento retoma a posse órfã; rejeitada, Question para o humano devolver a posse antes da correção |
| `bloqueada` | há Question aberta, ou a posse é de outro; segue com o resto do lote |
| `fora_do_alvo` | acerta `arquivos_alvo` na Task (por `propor_patch`); ela volta numa rodada seguinte |
| `falta_contexto` | o executor precisou de material fora da vista (código, documento, planilha) e parou sem procurar, com a posse liberada. Despacha o explorador com a `Pergunta`, lê a fonte apontada e registra a Evidence localizada com `deriva_de` para a Task; com ela registrada, despacha a Task de novo nesta rodada, se couber, senão na seguinte. Na segunda vez na mesma Task, redesenha (Decision ou divisão) ou abre Question |
| `falta_ferramenta` | o executor tinha o gesto `acao_externa`, mas não a ferramenta para fazê-la (a linha `Ferramenta:` diz qual), e liberou a posse. Não despacha de novo: diz no `Resumo` a Task e a ferramenta que falta, e a raiz leva ao humano |
| `acao_externa_do_humano` | o kernel recusou ao executor a Task de ação externa, porque o gesto `acao_externa` está com o humano. Devolve a Task na linha `Acao externa:` e segue com o resto |
| `falhou` | lê a Evidence da falha; desenho novo vira Decision, modelo mais forte vira `modelo: opus`; sem saída, Question |
| `fechadas` | as tarefas estão `concluido`; a rodada devolve |

## O retorno do revisor

    VEREDITO: aprovado | rejeitado | duvida | fora_da_trilha
    Artifact: <id>
    Task: <id>
    Evidence: <id do veredito, ou da triagem>
    Fora da trilha: <arquivo:linhas e o que a mudança faz>
    Criterios nao atendidos: <um por linha: gravidade, o critério e o id da Evidence que prova>
    Questao: <id>
    Resumo: <no máximo três linhas>

A Evidence do veredito deriva do Artifact e da Task, e cada critério não atendido tem uma Evidence localizada, com uma das duas formas de ponteiro (arquivo e linhas, ou fonte e local) e o trecho que o prova, e a `gravidade`: `bloqueante` (segurança, permissão, dado em produção ou o critério central da tarefa) ou `acompanhamento` (borda, caso raro, teste que falta, texto). A verificação que sustenta o veredito é o que prova o critério: rodar os testes quando a entrega é código; ler o documento e conferir números e fontes quando é texto, dado ou análise; na ação externa, julgar se a `fonte` e o `resultado` da prova batem com o critério. A Task de correção, criada com `id_tarefa_pai` na tarefa rejeitada, alcança essas Evidence em dois saltos: o executor da correção as lê na vista, sem que o condutor as repita no prompt.

`fora_da_trilha` só vem do `graphow-revisor-sonnet`: a mudança da Task leve não é só texto. Num repositório git, ele faz a triagem por `git status` e `git diff`. Quando a entrega não é código, confere só que os arquivos alterados são os do Artifact e que nenhum é código, configuração ou dado que um programa lê; sem git, lê os arquivos do Artifact inteiros. Ele não aprova nem rejeita. Registra uma Evidence com `triagem: fora_da_trilha` e o trecho que sai do texto, sem a propriedade `veredito`, para ela não virar o veredito vigente da tarefa nem entrar na contagem da medição. O condutor marca `trilha: completa` na Task (por `propor_patch`) e despacha o `graphow-revisor` com o mesmo Artifact; o veredito que vale é o dele.

## A revisão de escopo

Quando o placar da vista do Goal lista "Decisões sem veredito de escopo", o condutor despacha o `graphow-revisor` uma vez por raiz, no máximo três por rodada, todas numa mensagem só e em primeiro plano:

    Alvo: <id da raiz: a Decision, Task, Evidence ou Question de onde a cadeia de motivada_por parte>
    Goal: <id do Goal>
    Sessao: <id>

A linha `Alvo:` no lugar de `Artifact:` é o que diz ao revisor que a revisão é de escopo. Ele julga a decisão junto das Tasks que ela gerou contra as Constraints `criterio_aceite` e `fronteira` do Goal, e devolve:

    ESCOPO: cabe | nao_cabe | parcial
    Alvo: <id da raiz>
    Evidence: <id do veredito de escopo>
    Tasks: <ids que cabem> | <ids que não cabem>
    Resumo: <no máximo três linhas: o critério que a raiz atende ou a fronteira que cruza>

A Evidence do veredito de escopo tem `acao: veredito_de_escopo`, `deriva_de` para a raiz, e o parecer em `parecer_de_escopo` (não em `veredito`, que é o do fechamento da Task) com o `motivo`. O kernel a lê para tirar a raiz de "decisões sem veredito". O parecer não bloqueia Task alguma. O condutor relê o placar depois da revisão e devolve `Desvio:` já sem a raiz julgada, mais a linha `Revisao de escopo:`.

## O retorno do árbitro

    ARBITRAGEM: executada | escalada | nada_a_fazer
    Alvo: <id> | <rótulo>
    Respondidas: <id da Question> -> <a resposta em uma linha>
    Descartadas: <id da Question>: <motivo>
    Escaladas: <id da Question, do Aprendizado ou o gesto>: <o que o humano decide, com as opções>
    Constraints: <id> escopa <id do Goal ou da Task>
    Promovidos: <id do Aprendizado> -> <id do Setor ou do Projeto>
    Goal fechado: <id>
    Plano aprovado: <id do Goal> v<n> (sem referencia humana)
    Desvio respondido: <raiz ou Goal> -> <a resposta em uma linha>
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
| `Plano aprovado` | o executor está destravado. A versão do árbitro não é referência do desvio; o `(sem referencia humana)` avisa que o Goal ainda não tem plano aprovado por humano, e a raiz o conta ao humano na linha da rodada |
| `Desvio respondido` | a resposta aparece marcada no placar e não zera o contador do humano. A raiz o conta ao humano e não despacha o árbitro de novo para o mesmo gatilho |

O árbitro devolve poucas linhas e o resto fica no grafo, como o do condutor. A raiz não lê a vista da Question para conferi-lo.

## Mais de um despacho por vez

O condutor despacha as tarefas paralelas numa única mensagem, uma chamada por tarefa, todas em primeiro plano, depois de conferir que os `arquivos_alvo` são disjuntos e que nenhuma depende de outra. Task sem `arquivos_alvo`, a de ação externa inclusive, não entra em lote paralelo. O explorador pode rodar em paralelo com qualquer coisa: ele não edita nem escreve no grafo. Duas rodadas ao mesmo tempo, não: a raiz despacha uma de cada vez. O árbitro nunca roda junto de uma rodada do condutor, porque as Questions e as posses que ele decide são as que a rodada deixou: a raiz o despacha entre as rodadas, uma Question por vez.
