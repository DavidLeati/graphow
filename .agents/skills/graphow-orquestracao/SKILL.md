---
name: graphow-orquestracao
description: Orquestração de agentes sobre o grafo do Graphow, sem /clear entre tarefas. A sessão principal é a raiz. Ela recebe do humano um Goal, Setor ou Projeto e despacha rodadas em sequência para o subagente graphow-condutor (Opus, contexto novo a cada rodada). O condutor decompõe, testa o executor frio e despacha exploradores, executores e revisores. A raiz só para nos portões humanos, como a cadência combinada, o trabalho travado em Question e o teto de rodadas. Use quando pedirem para orquestrar um Goal, Setor ou Projeto, dividir trabalho grande entre subagentes, retomar uma orquestração ou comparar configurações de modelo. Exige a skill graphow-mcp e os subagentes graphow-condutor, graphow-explorador, graphow-executor, graphow-executor-opus e graphow-revisor, em ~/.claude/agents.
---

# Orquestração sobre o Graphow

O estado da orquestração mora no grafo, não na conversa. Por isso o trabalho pode ser cortado em rodadas, cada uma num contexto novo, e nenhuma precisa lembrar da anterior: toda rodada começa lendo o grafo.

Você é a raiz, a sessão que conversa com o humano. Seu trabalho é despachar rodadas para o `graphow-condutor`, uma de cada vez, ler o que ele devolve e decidir entre seguir e parar. Cada rodada nasce sem histórico e o descarta ao devolver. É isso que substitui o `/clear`, então não peça `/clear` ao humano entre tarefas.

Você não lê código de tarefa, não despacha executor nem revisor e não decide o desenho. Isso é do condutor, que lê as linhas que sustentam cada decisão; decidir em cima do resumo que ele devolve é onde o sistema perderia informação. O que você decide é o ritmo: seguir, parar e o que dizer ao humano.

## Quem faz o quê

| Quem | Modelo | Escreve no grafo | Faz |
| :--- | :--- | :--- | :--- |
| você, a raiz | o da sessão | nada | conversa com o humano, despacha rodadas, para nos portões |
| `graphow-condutor` | Opus, contexto novo por rodada | `Task`, `Decision`, `Evidence` localizada, `Question`, `Note` | escolhe o Goal, decompõe, testa o executor frio, despacha e fecha |
| `graphow-explorador` | Haiku | nada | devolve ponteiros: arquivo, linhas, trecho literal |
| `graphow-executor` | Sonnet | `Artifact`, `Evidence`, `Decision`, `Aprendizado` | executa uma Task a partir da vista dela |
| `graphow-executor-opus` | Opus | idem | a Task marcada `modelo: opus` |
| `graphow-revisor` | Opus, sempre sessão nova | `Evidence` com `veredito`, `Question`, `Aprendizado` | revisa contra os critérios de aceite; não corrige |

O procedimento da rodada (decompor, explorar sem interpretar, escolher o modelo, paralelismo, revisar, fechar e corrigir) está na definição do subagente `graphow-condutor`, em `.agents/agents/graphow-condutor.md` no repositório do graphow.

Goal e Constraint só o humano cria: ele diz o que quer, e os agentes decidem como. Quando uma restrição fizer falta, o condutor a propõe numa Question.

## O laço

1. **Entrar.** O id da sua sessão está na vista que o hook imprimiu (`Sessao <id>`). O alvo é o que o humano pediu: um Goal, um Setor ou um Projeto. Se ele não disse, pergunte. A cadência e o teto de rodadas valem nesta ordem: o que o humano disse agora, as propriedades `cadencia` e `teto_rodadas` que a rodada devolve (lidas do Goal, do Setor ou do Projeto) e, por fim, o padrão, que é `goal` e 20 rodadas.
2. **Despachar uma rodada**, com o subagente `graphow-condutor`, em primeiro plano (`run_in_background: false`) e um prompt que é só ponteiro:

       Alvo: <id>
       Sessao: <id_sessao>

   Uma rodada por vez, porque duas ao mesmo tempo disputariam o mesmo Goal. O paralelismo fica dentro da rodada, entre tarefas com arquivos disjuntos.
3. **Contar ao humano**, numa linha por rodada: o Goal, o que fechou, o que abriu e as Questions novas, com o id de cada uma, para ele ir respondendo enquanto o trabalho anda.
4. **Seguir ou parar.** Volte ao passo 2 enquanto nenhum portão de "Onde parar" fechar.
5. **Parar** é terminar o turno com um resumo curto ao humano, dizendo:
   - por que parou;
   - o que fechou desde a última parada;
   - os Goals que ficaram sem tarefa aberta (fechar o Goal é dele);
   - as Questions abertas, com id e uma linha, para responder na interface do graphow;
   - o que roda quando ele disser "segue".

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

- a rodada devolver `RODADA: nada_a_fazer`: o que resta espera Question, posse órfã ou dependência travada;
- o teto de rodadas chegar;
- o limite do plano ficar perto do fim: no app desktop, leia `mcp__ccd_session_mgmt__get_usage` (carregue pelo ToolSearch) depois de cada rodada e pare com a janela de 5 horas em 85% ou mais, ou com a semanal em 90% ou mais. Estourar no meio de uma rodada deixa posse presa e tarefa pela metade. Diga os percentuais no resumo da parada;
- duas rodadas seguidas voltarem sem criar, fechar nem corrigir nada, ou fora do formato de saída do condutor;
- o humano pedir. A mensagem dele chega entre rodadas.

Question aberta não para o laço sozinha. A Task dela sai da fila, o resto segue, e o humano fica sabendo pela linha da rodada.

## O que só o humano faz

- Criar Goal e Constraint.
- Responder Question.
- Promover Aprendizado.
- Fechar o Goal.
- Fazer commit e push, a menos que peça.

Nada disso muda se a sessão tiver um servidor do graphow com papel `humano`: a raiz não responde Question nem promove memória.

## Higiene de contexto da raiz

- Não abra código, não chame explorador, executor nem revisor, e não leia a vista das tarefas: isso enche a conversa que devia ficar leve.
- Não cole o retorno de uma rodada no despacho da seguinte. O condutor novo lê o grafo.
- A raiz cresce perto de mil tokens por rodada. Quando o `context` do `get_usage` passar de 50% da janela, ou depois de umas 50 rodadas se a ferramenta não existir (no `claude -p`, por exemplo), pare no próximo portão e sugira limpar. A raiz nova volta pelo mesmo alvo, porque o estado está no grafo. A sessão não consegue se limpar e se chamar de novo sozinha: no app, o `clear_session("self")` encerra o processo ao fim do turno, e nada de dentro dela sobrevive para mandar a mensagem seguinte.
- O protocolo de memória que o hook imprime vale para quem escreve no grafo. Aqui quem escreve são o condutor e os subagentes dele, com a proveniência de cada um. A raiz não registra Evidence, Decision nem Aprendizado.

## Medir a divisão de modelos

Sem medir, a divisão de modelos fica no palpite. O harness grava um `Run` por sessão (os tokens da raiz) e um por subagente, inclusive os que o condutor despacha (tokens, modelo e as tarefas que ele assumiu). Para comparar arranjos:

1. O humano cria um Goal por configuração, com a mesma descrição e `configuracao` igual a `tudo-opus`, `padrao` ou `opus-em-dominio`.
2. Cada Goal é orquestrado a partir do mesmo commit, num worktree próprio do git, para os executores de um arranjo não pisarem nos do outro.
3. Compare:

```bash
graphow orquestracao-medir --goal goal-tudo-opus --goal goal-padrao --goal goal-opus-em-dominio
```

O relatório dá, por configuração, as tarefas concluídas sem retrabalho, as rejeições na revisão e os tokens por tarefa concluída. O condutor não assume tarefa, então o custo dele entra pelo da sessão, dividido entre os Goals que ela serviu: meça um Goal por sessão.

## Referências

- `graphow-condutor` (`.agents/agents/graphow-condutor.md` no repositório do graphow): o procedimento da rodada.
- [Despacho](./references/despacho.md): o prompt de cada subagente e o formato do que ele devolve.
- [Configuração](./references/configuracao.md): servidores MCP por papel, hooks, permissões e o laço sem interface.
