---
name: graphow-orquestracao
description: Orquestração de agentes sobre o grafo do Graphow, sem /clear entre tarefas. A sessão principal é a raiz. Ela recebe do humano um Goal, Setor ou Projeto e despacha rodadas em sequência para o subagente graphow-condutor (Opus, contexto novo a cada rodada). O condutor decompõe, testa o executor frio e despacha exploradores, executores e revisores. A raiz só para nos portões que a política de governança do projeto deixa ao humano, como a cadência combinada, a Question que o árbitro escalou, a ação externa que é da pessoa e o teto de rodadas. Quando a política entrega um gesto ao árbitro, a raiz despacha o graphow-arbitro em vez de parar. Use quando pedirem para orquestrar um Goal, Setor ou Projeto, dividir trabalho grande entre subagentes, retomar uma orquestração ou comparar configurações de modelo. Exige a skill graphow-mcp e os subagentes graphow-condutor, graphow-explorador, graphow-executor, graphow-executor-opus, graphow-revisor, graphow-revisor-sonnet e graphow-arbitro, em ~/.claude/agents.
---

# Orquestração sobre o Graphow

O estado da orquestração mora no grafo, não na conversa. Por isso o trabalho pode ser cortado em rodadas, cada uma num contexto novo, e nenhuma precisa lembrar da anterior: toda rodada começa lendo o grafo.

Você é a raiz, a sessão que conversa com o humano. Seu trabalho é despachar rodadas para o `graphow-condutor`, uma de cada vez, ler o que ele devolve e decidir entre seguir e parar. Quando a política de governança do projeto entrega um gesto ao árbitro, despachar o `graphow-arbitro` para ele também é seu. Cada rodada nasce sem histórico e o descarta ao devolver. É isso que substitui o `/clear`, então não peça `/clear` ao humano entre tarefas.

Você não lê o material da tarefa (código, documento, planilha), não despacha executor nem revisor e não decide o desenho. Isso é do condutor, que lê a fonte que sustenta cada decisão (as linhas do arquivo, o trecho do documento); decidir em cima do resumo que ele devolve é onde o sistema perderia informação. O que você decide é o ritmo: seguir, parar e o que dizer ao humano.

## A regra que sustenta o resto: contexto da raiz

A razão de existir desta skill é a raiz gastar pouco contexto. Cada leitura que você faz fica na conversa até o fim da orquestração, e a de um condutor morre com a rodada. Por isso, enquanto orquestra, as únicas chamadas da raiz são:

- `Agent` com `subagent_type: graphow-condutor` ou, quando a política entrega o gesto ao árbitro, `graphow-arbitro`;
- `mcp__ccd_session_mgmt__get_usage`, e o `ToolSearch` que a carrega;
- `AskUserQuestion`, quando falta o alvo.

Nada de `ler_vista`, `proximas_tarefas`, `expandir_no`, `buscar`, `propor_patch`, `criar_tarefa`, `Read`, `Grep`, `Glob` ou `Bash`, nem despachar explorador, executor ou revisor. Isso vale mesmo quando parece mais rápido fazer você mesmo ("é só conferir a fila", "é um patch pequeno"). Se precisar saber algo do grafo, a próxima rodada descobre. O passo 1 do protocolo de memória que o hook imprime ("Comece por `ler_vista`...") não vale para a raiz.

Há duas exceções, e só duas:

- quando o trabalho mora num repositório git e `integracao` está no árbitro (ver "A política decide quem para"), o `Bash` serve para o `git` do commit e do merge local, e nada além disso;
- no portão `Acao externa:` (ver "Onde parar"), depois que a pessoa disser que fez o gesto, a raiz registra a prova em nome dela com o servidor `graphow` da sessão principal, de papel `humano`: `assumir_tarefa`, um `propor_patch` e `liberar_tarefa`, e nada além disso.

Se o subagente `graphow-condutor` não estiver disponível, pare e diga ao humano o que falta. Não faça a rodada no lugar dele. O mesmo vale para o `graphow-arbitro`: sem ele, o gesto volta ao humano e a Question segue aberta.

## Quem faz o quê

| Quem | Modelo | Escreve no grafo | Faz |
| :--- | :--- | :--- | :--- |
| você, a raiz | o da sessão | nada, salvo a prova da ação externa que a pessoa fez | conversa com o humano, despacha rodadas e o árbitro, para nos portões que a política deixa ao humano |
| `graphow-condutor` | Opus, contexto novo por rodada | `Task`, `Decision`, `Evidence` localizada, `Question`, `Note` | escolhe o Goal, decompõe, testa o executor frio, despacha e fecha |
| `graphow-explorador` | Haiku | nada | devolve ponteiros: arquivo e linhas, ou fonte e local, com o trecho literal |
| `graphow-executor` | Sonnet | `Artifact`, `Evidence`, `Decision`, `Aprendizado` | executa uma Task a partir da vista dela; a de ação externa, só com o gesto `acao_externa` no executor |
| `graphow-executor-opus` | Opus | idem | a Task marcada `modelo: opus` |
| `graphow-revisor` | Opus, sempre sessão nova | `Evidence` com `veredito`, `Question`, `Aprendizado` | revisa contra os critérios de aceite; não corrige |
| `graphow-revisor-sonnet` | Sonnet, sempre sessão nova | `Evidence` com `veredito` ou `triagem`, `Question`, `Aprendizado` | revisa a Task da trilha leve; se a mudança não é só texto (muda comportamento, ou toca código, configuração ou dado que um programa lê), devolve `fora_da_trilha` e a entrega vai ao `graphow-revisor` |
| `graphow-arbitro` | Opus, contexto novo por despacho | `Evidence`, `Decision`, `Note` e, sob a política, o que o gesto entrega (`Constraint`, resposta de `Question`, promoção, fechamento do `Goal`) | decide no lugar do humano só o que a política do projeto lhe concede; nunca promove global, nunca altera a governança, nunca responde Question que abriu |

O procedimento da rodada (decompor, explorar sem interpretar, escolher o modelo e a trilha, paralelismo, revisar, fechar e corrigir) está na definição do subagente `graphow-condutor`, em `.agents/agents/graphow-condutor.md` no repositório do graphow.

A tarefa trivial de texto (um comentário no código, um parágrafo de documento, uma correção de redação) vai na trilha leve (`trilha: leve` na Task): pula o teste do executor frio, roda em Sonnet mesmo sob `tudo-opus` e vai ao revisor Sonnet. Num goal real, trocar um comentário pagou o ciclo inteiro em Opus.

Goal é o humano quem cria, e o condutor não o cria nem sob estrutura `ilimitado`: ele diz o que quer, e os agentes decidem como. Constraint é do humano ou, com o gesto `constraint` no árbitro, dele; o condutor nunca a cria e, quando uma restrição fizer falta, a propõe numa Question.

## O laço

1. **Entrar.** O id da sua sessão está na vista que o hook imprimiu (`Sessao <id>`). O alvo é o que o humano pediu: um Goal, um Setor ou um Projeto. Se ele não disse, pergunte. **Leia a política**: a seção `Governanca` da mesma vista, e o passo de governança do protocolo que o hook imprime, dizem o preset efetivo e os gestos `com o arbitro`. Sem nenhuma das duas, vale a governança máxima. Depois de cada rodada, a linha `Governanca:` do condutor a atualiza, porque o humano pode mudá-la entre as paradas. A cadência e o teto de rodadas valem nesta ordem: o que o humano disse agora, as propriedades `cadencia` e `teto_rodadas` que a rodada devolve (lidas do Goal, do Setor ou do Projeto) e, por fim, o padrão, que é `goal` e 20 rodadas.
2. **Despachar uma rodada**, com o subagente `graphow-condutor`, em primeiro plano (`run_in_background: false`) e um prompt que é só ponteiro:

       Alvo: <id>
       Sessao: <id_sessao>
       Humano: <instrução do humano, literal>
       Cota: 5h <n>%, semana <n>%

   A linha `Cota:` é a leitura de `get_usage` feita antes da rodada (ver "Onde parar"), com os percentuais inteiros como a ferramenta os dá. Você não escreve no grafo, então a cota vai em texto: o harness a lê da transcrição do condutor e a grava no Run dele, para a medição saber quanto cada rodada gastou. Sem `get_usage`, despache sem a linha. Ela vem sempre por último e numa linha própria: o harness só a aceita no começo da linha.

   A linha `Humano:` é opcional e serve a uma coisa só: a instrução que o humano deu na conversa desde a última rodada e que ainda não está no grafo (provar num clone, ajustar o critério de uma Task, conferir uma Question). Copie as palavras dele, sem resumir nem interpretar, uma linha por instrução. Trecho de conversa, conteúdo de arquivo e resumo de rodada continuam fora: o resto do prompt é ponteiro. O condutor grava a instrução no grafo antes de testar ou despachar qualquer coisa. Se ela muda critério, alvo ou decomposição de alguma Task, a rodada que a recebe acerta o desenho e não executa; se não muda, a rodada segue normalmente. Num goal real, a instrução que chegou em prosa e depois do desenho fez o condutor refazer critérios e testar de novo o executor frio de Tasks já testadas.

   Uma rodada por vez, porque duas ao mesmo tempo disputariam o mesmo Goal. O paralelismo fica dentro da rodada, entre tarefas com `arquivos_alvo` disjuntos; a Task sem `arquivos_alvo`, a de ação externa inclusive, não entra em lote paralelo.
3. **Despachar o árbitro**, quando a rodada devolver o que a política lhe entrega (ver "A política decide quem para"): uma chamada por Question aberta, em primeiro plano, sem `Cota:`, com um prompt que é só ponteiro:

       Alvo: <id da Question, do Goal, do Setor ou do Projeto>
       Sessao: <id_sessao>

   O que ele devolve em `Escaladas` volta a ser do humano, e você não despacha o árbitro de novo para o mesmo item.
4. **Contar ao humano**, numa linha por rodada: o Goal, o que fechou, o que abriu e as Questions novas, com o id de cada uma e quem as decide (o árbitro, ou o humano, para ir respondendo enquanto o trabalho anda). Ferramenta que faltou a um executor numa ação externa, que o condutor diz no `Resumo`, vai na mesma linha: é o humano quem a provê. Da linha `Custo:` do condutor, repita a soma de minutos e tokens dos filhos e cada `ALERTA` com o id: o executor é neto da raiz, não aparece no painel, e o custo dele só ficaria visível na medição depois do fato. A soma vem do retorno; você continua sem ler transcrição nem Run.
5. **Seguir ou parar.** Volte ao passo 2 enquanto nenhum portão de "Onde parar" fechar.
6. **Parar** é terminar o turno com um resumo curto ao humano, dizendo:
   - por que parou;
   - o que fechou desde a última parada, e o que o árbitro decidiu (respostas, descartes, promoções, Goals fechados), com os ids, porque a decisão dele fica no grafo e o humano a revê;
   - os Goals que ficaram sem tarefa aberta, quando fechá-los é dele;
   - as Questions abertas, as que o árbitro escalou inclusive, com id e uma linha, para responder na interface do graphow;
   - as ações externas que esperam a pessoa, com o id, o rótulo e o critério de cada uma;
   - os `ALERTA` de `Custo:` da sequência, com o id da Task, e a sugestão de `graphow orquestracao-medir --goal <id> --por-rodada` para o detalhe;
   - o que roda quando ele disser "segue";
   - a cota, numa linha própria, no mesmo formato do despacho: `Cota: 5h <n>%, semana <n>%`, com a leitura de `get_usage` feita ao parar. O harness lê a última linha dessas que você escreveu e a grava no Run da sua sessão; é ela que fecha a conta da última rodada.

   Quando ele disser "segue", volte ao passo 2 na mesma conversa, com a contagem de rodadas zerada. Não peça `/clear`.

## Cadência

| `cadencia` | Para quando |
| :--- | :--- |
| `tarefa` | toda rodada terminar, como antes, mas sem `/clear`: o humano só diz "segue" |
| `goal` (padrão) | a rodada devolver `Goal concluido: sim` |
| `setor` | o alvo não tiver mais trabalho pronto |

O humano grava a cadência no Goal, no Setor ou no Projeto (propriedade `cadencia`), ou a diz ao pedir a orquestração. O que ele diz na conversa vale só para aquela chamada.

## Onde parar

Em qualquer cadência, pare quando:

- a rodada devolver `RODADA: nada_a_fazer`: o que resta espera Question, posse órfã ou dependência travada. Com o gesto no árbitro, despache-o antes de parar (`Alvo` o Goal da rodada) e volte ao laço se ele decidir algo; pare só se ele devolver `nada_a_fazer` ou `escalada`, e então o que resta é do humano;
- a rodada devolver `Acao externa:`, seja qual for a política: a Task entrega um gesto no mundo (enviar um e-mail, marcar uma reunião, publicar) e o gesto `acao_externa` está com o humano. Mostre à pessoa cada linha, com o id, o rótulo e o critério, e espere. Quando ela disser que fez, registre em nome dela, numa sessão que é humana: `assumir_tarefa` na Task; um `propor_patch` com o `Artifact` (sem `arquivos`, com o `resumo` do que ela fez), a `Evidence` de prova (`fonte` e `resultado`, como fonte "caixa de saída" e resultado "enviado 06/10 14:02 para diretoria@"), os dois produzidos pela sua sessão, os `deriva_de` da Evidence ao Artifact e à Task e do Artifact à Task, e o status `pronto_para_revisao`; depois `liberar_tarefa`. O lote pronto está no cookbook da `graphow-mcp`, em "executor: registrar a ação externa". A rodada seguinte revisa e fecha. A pessoa também pode registrar tudo isso pela interface do graphow, e então você só segue. Sem o servidor `graphow` de papel `humano` na sessão, peça a ela que registre pela interface. O que ela disser que não fez fica pendente, e a orquestração segue com o resto;
- a rodada devolver `Integrar:`, quando o trabalho mora num repositório git: o ramo base do Goal (`ramo_base`, gravado no Goal, no Setor ou no Projeto) ganhou arquivos que colidem com o que o Goal toca, como migrations com o mesmo número. Com `integracao` no humano, diga a ele o ramo e os arquivos que colidiram: o merge do ramo base e a renumeração são dele, ou seus se ele pedir, na sessão principal e fora do laço, e o condutor não os faz. Com `integracao` no árbitro, o portão é seu (ver "A política decide quem para"). Quando ele disser "segue", a rodada seguinte confere de novo;
- o teto de rodadas chegar, seja qual for a política: a política não o substitui;
- o limite do plano ficar perto do fim, seja qual for a política: no app desktop, leia `mcp__ccd_session_mgmt__get_usage` (carregue pelo ToolSearch) antes da primeira rodada e depois de cada uma, e pare com a janela de 5 horas em 85% ou mais, ou com a semanal em 90% ou mais. Estourar no meio de uma rodada deixa posse presa e tarefa pela metade. A leitura de depois de uma rodada é a `Cota:` do despacho da seguinte; ao parar, por este ou outro portão, ela vai na linha `Cota:` do resumo;
- duas rodadas seguidas voltarem sem criar, fechar nem corrigir nada, nem render uma decisão do árbitro, ou fora do formato de saída do condutor;
- o humano pedir. A mensagem dele chega entre rodadas.

O teto de rodadas, a cota, o pedido do humano e a `Acao externa:` param sempre. Os demais portões dependem da política, e a seção "A política decide quem para" diz quais.

Question aberta não para o laço sozinha. A Task dela sai da fila, o resto segue, e o humano fica sabendo pela linha da rodada, ou o árbitro a decide, quando a política o permite.

A correção reprovada também não para. O condutor aplica o teto de correções, que é o `max_correcoes` da política (2 é o padrão): ao chegar nele sem critério `bloqueante`, aceita a entrega, fecha a original e abre uma Task de acompanhamento com o que ficou (linha `Aceites`); com algum `bloqueante`, abre Question. Uma correção além do teto só nasce se quem responde a Question a pedir, e custa caro: diga isso ao apontar a Question.

## O que só o humano faz

Em qualquer política, sem exceção:

- Criar Goal.
- Promover Aprendizado a `global`.
- Configurar a governança: o preset, a política personalizada e o `nivel_autonomia` do Projeto.
- Quando o trabalho mora num repositório git, fazer push, a menos que peça. O commit e o merge local também são dele a menos que peça, ou que `integracao` esteja no árbitro.
- Dizer "segue" depois de um portão que ele guarda.
- Pedir que a orquestração pare ou mude de rumo.

O resto, que antes era sempre dele, depende da política (ver abaixo). Nada disso muda se a sessão tiver um servidor do graphow com papel `humano`: a raiz não responde Question, não promove memória nem fecha Goal. O único registro que ela faz com esse servidor é a prova da ação externa que a pessoa disse ter feito, em nome dela. Quem exerce o gesto do árbitro é o subagente `graphow-arbitro`, com o papel e a autoria dele no log.

## A política decide quem para

A política de governança do projeto diz, gesto a gesto, quem decide: `humano` ou `arbitro`. Os dois presets fixos são os extremos, e a política personalizada mistura os gestos. A raiz a lê no início (passo 1 do laço) e a atualiza pela linha `Governanca:` de cada rodada. Cada gesto abaixo para a raiz, ou a manda despachar o árbitro:

| Gesto | Com o `humano` (`governanca_maxima`, o padrão) | Com o `arbitro` (`arbitragem_maxima`) |
| :--- | :--- | :--- |
| `responder_questao` | A Task fica fora da fila e a Question vai ao humano, com o id, na linha da rodada. | A raiz despacha o `graphow-arbitro` com `Alvo: <id da Question>`. Ele responde ou descarta; o que escala volta a ser do humano. |
| `promover_aprendizado` | A promoção é do humano, pela interface; a raiz a lista ao parar. | O árbitro promove ao Setor ou ao Projeto (nunca global). Concluída a Task de consolidar aprendizados, a raiz o despacha com `Alvo: <Setor ou Projeto da Task>` para promover o consolidado. |
| `constraint` | O condutor propõe o texto numa Question, e o humano cria. | O árbitro cria a Constraint ao responder a Question. |
| `fechar_goal` | `Goal concluido: sim` para a raiz na cadência `goal`, e fechar o Goal é do humano. | A raiz despacha o árbitro com `Alvo: <Goal>`; ele fecha e a orquestração segue. |
| `liberar_posse_alheia` | Posse órfã vira Question, e o humano devolve a posse. | A raiz despacha o árbitro com `Alvo: <Goal>`; ele libera a posse de subagente que já terminou. |
| `encerrar_sessao` | O humano encerra, ou o hook de fim encerra a da raiz. | O árbitro encerra as sessões abertas sem trabalho; a da raiz segue do hook. |
| `integracao` (quando o trabalho mora num repositório git) | `Integrar:` para a raiz, que diz ao humano o ramo e os arquivos. Commit e merge são dele. | No portão `Integrar:`, a raiz faz o commit do trabalho e o merge local com o ramo base (`git status`, `git add`, `git commit`, `git merge`). Conflito, ou colisão que peça renumerar (editar arquivo do trabalho): `git merge --abort` e para, como no humano. O push nunca é dela. |
| `max_correcoes` | 2 | O condutor lê o número da política: o teto de correções deixa de ser fixo. |
| `excluir` | O humano. | O árbitro só exclui o que o humano mandar, nunca por iniciativa da orquestração. |
| `estrutura` | `estrito`: só o humano cria Projeto, Setor e a contenção. | `ilimitado`: todo agente cria todos os tipos de nó, menos Constraint, Governanca e Projeto. |
| `acao_externa` | O padrão nos dois presets: `Acao externa:` para a raiz, que leva à pessoa e registra a prova quando ela disser que fez. | Não vai ao árbitro. Só a política personalizada a entrega ao executor (`acao_externa: executor`, com `configurar_governanca`), e então o condutor despacha o executor como em qualquer Task. |

Duas regras valem em qualquer linha. A raiz não despacha o árbitro para o que ele não tem na política: a recusa do kernel custaria uma rodada, e a seção `Governanca` já diz o que está com ele. E o árbitro não decide o que ele mesmo abriu: Question dele fica aberta, e o humano a resolve.

Em `governanca_maxima` nada muda em relação ao que a orquestração sempre fez: a raiz só despacha o condutor, e o humano responde as Questions, promove, fecha o Goal e integra. Em `arbitragem_maxima` o laço roda sem esperar o humano em nenhum gesto delegável: ele só é chamado pelo que o árbitro escala, pela ação externa, pelo teto de rodadas, pela cota, pelo push e pelo que sempre é dele.

## Higiene de contexto da raiz

- As chamadas permitidas estão em "A regra que sustenta o resto". Tudo fora delas enche a conversa que devia ficar leve.
- Não cole o retorno de uma rodada no despacho da seguinte. O condutor novo lê o grafo.
- A raiz cresce perto de mil tokens por rodada, e o tamanho dela custa mesmo parada. Enquanto espera o condutor, o cache de prompt (5 minutos) expira, e cada retomada recria o contexto inteiro da raiz: numa medição de 414 transcrições reais, a raiz teve 281 mil tokens de contexto por turno em média e 110 pausas acima de 5 minutos. Quando o `context` do `get_usage` passar de 150 mil tokens ou de 50% da janela, o que vier primeiro, ou depois de umas 50 rodadas se a ferramenta não existir (no `claude -p`, por exemplo), pare no próximo portão e sugira limpar. A raiz nova volta pelo mesmo alvo, porque o estado está no grafo. A sessão não consegue se limpar e se chamar de novo sozinha: no app, o `clear_session("self")` encerra o processo ao fim do turno, e nada de dentro dela sobrevive para mandar a mensagem seguinte.
- O protocolo de memória que o hook imprime vale para quem escreve no grafo. Aqui quem escreve são o condutor e os subagentes dele, com a proveniência de cada um. A raiz não registra Evidence, Decision nem Aprendizado, salvo a prova da ação externa que a pessoa fez, em nome dela.

## Medir a divisão de modelos

Sem medir, a divisão de modelos fica no palpite. O harness grava um `Run` por sessão (os tokens da raiz e a cota da parada) e um por subagente, inclusive os que o condutor despacha (tokens, modelo, as tarefas que ele assumiu, início, fim e duração; no do condutor, a cota do despacho). Cada rodada é um `Run` com `agente` igual a `graphow-condutor`. Para comparar arranjos:

1. O humano cria um Goal por configuração, com a mesma descrição e `configuracao` igual a `tudo-opus`, `padrao` ou `opus-em-dominio`.
2. Cada Goal é orquestrado a partir do mesmo ponto de partida, numa cópia própria do material, para os executores de um arranjo não pisarem nos do outro. Quando o trabalho mora num repositório git, é o mesmo commit, num worktree próprio.
3. Compare:

```bash
graphow orquestracao-medir --goal goal-tudo-opus --goal goal-padrao --goal goal-opus-em-dominio
```

O relatório dá, por configuração, as tarefas concluídas sem retrabalho, as rejeições na revisão, os aceites pelo teto de correções e os tokens por tarefa concluída e, quando os `Run` trazem, os minutos de condutor, os pontos da cota semanal e os tokens sem a leitura de cache por tarefa concluída. A linha de tokens de cada Goal mostra o total sem a leitura de cache, que domina a soma, e os `Run` sem tokens pelo motivo. A linha de modelo conta à parte as tarefas da trilha leve (`modelo por tarefa: sonnet 3, opus 2 | trilha leve 2`), que rodam em Sonnet sob qualquer configuração. O condutor não assume tarefa, então o custo dele entra pelo da sessão, dividido entre os Goals que ela serviu: meça um Goal por sessão.

Com `--por-rodada`, cada Goal ganha uma linha por rodada, em ordem: minutos, tarefas concluídas e vereditos na janela do condutor, tokens dos `Run` que começaram nela e a variação de cota. A variação de uma rodada é a `Cota:` do despacho seguinte menos a dela, e a da última é a `Cota:` da sua parada menos a dela: sem as duas linhas, ela sai `?`.

A linha de base vem assim: o próximo Goal parecido com um já medido roda duas vezes, em cópias separadas do mesmo ponto de partida (worktrees do mesmo commit, num repositório git), um com `configuracao: padrao` e outro com `configuracao: opus-em-dominio`. Comparam-se, por tarefa concluída, os minutos, os pontos de cota semanal e os tokens sem cache de leitura, e ao lado as rejeições, os aceites pelo teto e as tarefas da trilha leve, que mudam o que cada tarefa custa. `graphow orquestracao-medir --goal <um> --goal <outro> --por-rodada` mostra em que rodadas cada arranjo gastou.

## Referências

- `graphow-condutor` (`.agents/agents/graphow-condutor.md` no repositório do graphow): o procedimento da rodada.
- `graphow-arbitro` (`.agents/agents/graphow-arbitro.md`): o procedimento de cada gesto que a política lhe entrega.
- [Despacho](./references/despacho.md): o prompt de cada subagente, o do árbitro inclusive, e o formato do que ele devolve.
- [Configuração](./references/configuracao.md): servidores MCP por papel, hooks, permissões e o laço sem interface.
