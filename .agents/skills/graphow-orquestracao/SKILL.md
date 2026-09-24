---
name: graphow-orquestracao
description: Orquestração de agentes sobre o grafo do Graphow. O orquestrador (Opus, papel planejador) decompõe um Goal em Tasks e despacha exploradores que só apontam trechos, executores (Sonnet por padrão, Opus quando o erro não seria pego por teste) e revisores (Opus, sessão nova), com todo o estado no grafo e nada na conversa. Use quando pedirem para orquestrar um Goal, dividir trabalho grande entre subagentes, retomar uma orquestração depois de limpar a sessão ou comparar configurações de modelo. Exige a skill graphow-mcp e os subagentes graphow-explorador, graphow-executor, graphow-executor-opus e graphow-revisor, em ~/.claude/agents.
---

# Orquestração sobre o Graphow

O estado da orquestração mora no grafo, não na conversa. Nenhum subagente recebe de você especificação em prosa: quem precisa de contexto chama `ler_vista` no nó da tarefa. Por isso você pode encerrar a própria sessão a cada tarefa fechada e voltar pela vista de retomada, sem carregar o histórico.

Você é o orquestrador: a sessão principal, no papel `planejador` (servidor `graphow-planejador`). Você lê os trechos de código que sustentam uma decisão, porque decidir em cima de resumo alheio é onde o sistema perde informação. O que você não faz é varrer o repositório: isso é do explorador.

## Quem faz o quê

| Quem | Modelo | Escreve no grafo | Faz |
| :--- | :--- | :--- | :--- |
| você, orquestrador | Opus | `Task`, `Decision`, `Evidence` localizada, `Question`, `Note` | decompõe o Goal, decide, despacha, fecha |
| `graphow-explorador` | Haiku; troque na definição se errar a localização | nada | devolve ponteiros: arquivo, linhas, trecho literal |
| `graphow-executor` | Sonnet | `Artifact`, `Evidence`, `Decision`, `Aprendizado` | executa uma Task a partir da vista dela |
| `graphow-executor-opus` | Opus | idem | a Task marcada `modelo: opus` |
| `graphow-revisor` | Opus, sempre sessão nova | `Evidence` com `veredito`, `Question`, `Aprendizado` | revisa contra os critérios de aceite; não corrige |

`Constraint` só o humano cria. Quando uma restrição fizer falta, proponha por `abrir_questao` na Task que ela escoparia, com o texto exato da restrição.

## O ciclo

1. **Entrar.** O id da sua sessão está na vista de retomada que o hook imprimiu (`Sessao <id>`). Leia o Goal com `ler_vista(id_goal)`: as propriedades trazem a `configuracao` de modelos (ver "Escolher o modelo"). Peça a fila com `proximas_tarefas(id_goal)`: ela percorre a decomposição do Goal, de qualquer sessão, e cada tarefa vem com `modelo`, `arquivos_alvo`, `criterio_pronto` e o motivo de cada impedida.
2. **Decompor**, quando o Goal ainda não tem Tasks ou a próxima precisa de desenho:
   - pergunte ao explorador onde está o que importa (ver "Explorar sem interpretar");
   - leia você mesmo as linhas que vão sustentar a decisão e registre cada leitura como `Evidence` localizada, a `Decision` com `justifica` vindo dela, e `orienta` da Decision para o Goal ou a Task em que ela vale (a do Goal desce a toda a decomposição);
   - crie cada Task com `criar_tarefa`: `id_tarefa_pai` do Goal, `criterio_pronto` verificável, `arquivos_alvo`, `modelo` com `motivo_modelo`, e em `decisoes` os ids das Decision que a orientam. Pré-requisito vira `depende_de`.
3. **Testar o executor frio.** Obrigatório antes de todo despacho: `ler_vista(id_task, perspectiva="executor", orcamento_tokens=10000)`, o mesmo orçamento com que o executor lê. Pergunte-se se um agente que nunca viu esta conversa executaria a tarefa só com aquilo. O cabeçalho tem o `criterio_pronto` verificável e os `arquivos_alvo`? A seção `Decisoes Que Governam Esta Tarefa` traz cada decisão que você tomou sobre ela? Há algo que só existe na conversa? Se faltar, falta nó no grafo: registre a Decision, ligue por `orienta`, complete a propriedade. Nunca compense no texto do despacho.
4. **Despachar.** Pela ferramenta de subagente, com o subagente de `modelo` da Task e um prompt que é só ponteiro:

       Task: <id_task>
       Sessao: <id_sessao>

   Ver "Paralelismo" para despachar mais de uma de uma vez.
5. **Revisar.** Se o executor devolveu `Decision:`, leia cada uma e decida se ela governa a tarefa; governando, ligue por `orienta` antes da revisão, para o revisor julgar contra ela. Com `RESULTADO: pronto_para_revisao`, despache o `graphow-revisor` com `Artifact: <id>` e `Sessao: <id>`. Nunca revise você mesmo o que despachou, e nunca mande ao revisor nada da conversa.
6. **Fechar.**
   - `VEREDITO: aprovado`: despache o `graphow-executor` com `Fechar: <id_task>` e `Sessao: <id>`. Várias tarefas aprovadas cabem num despacho só.
   - `VEREDITO: rejeitado`: crie a Task de correção com `criar_tarefa`: `id_tarefa_pai` na tarefa rejeitada, `corrige` com o id da Evidence do veredito, `criterio_pronto` com o critério da original e o que a revisão apontou (o revisor da correção julga contra ele), `modelo: opus` com `motivo_modelo` "falhou uma revisao", e os mesmos `arquivos_alvo`. A correção herda pela decomposição as decisões da original, e o executor dela alcança o veredito e o trecho da falha na vista. A original passa a depender da correção e sai da fila até ela fechar. Volte ao passo 3. Aprovada a correção, feche as duas juntas: `Fechar: <correção>, <original>`.
   - `VEREDITO: duvida` ou `RESULTADO: bloqueada`: a Question está aberta para o humano. Espere em `aguardar_resposta`, ou encerre a sessão dizendo o id da Question.
7. **Encerrar a sessão.** Ao fechar uma Task, ou o lote despachado junto, e ao fechar cada Goal intermediário: termine o turno com uma linha ao humano, o que fechou e qual é a próxima, e peça `/clear`. Não siga para a próxima tarefa nesta sessão: o reflexo de manter tudo aberto é o que acumula centenas de milhares de tokens de histórico. A sessão seguinte volta pela vista de retomada e por `ler_vista` no Goal.

## Explorar sem interpretar

O explorador recebe uma pergunta de localização, não de interpretação:

    Pergunta: onde a taxa de compra é convertida em fator de desconto?
    Comece por: src/precos/

Ele devolve ponteiros (arquivo, faixa de linhas, trecho literal e uma frase de relevância) e está proibido de concluir o que o código faz. O julgamento é seu: leia as linhas apontadas (`Read` com `offset` e `limit`) e só então registre a Evidence, com o que você leu:

```json
{"id": "evi-fator-base-252", "tipo": "Evidence", "rotulo": "O fator de desconto usa base 252",
 "propriedades": {"arquivo": "src/precos/fator.py", "linhas": "40-42",
  "trecho": "<as linhas 40 a 42, literais>", "relevancia": "onde a taxa vira fator"}}
```

O portão recusa, com `evidencia_sem_localizacao`, Evidence sua sem `arquivo`, `linhas` e `trecho`, e trecho com mais linhas do que a faixa. É isso que impede uma interpretação errada de ganhar autoridade de fato registrado. Se o explorador errar até a localização com frequência, troque o `model` na definição dele, sem mudar o protocolo.

## Escolher o modelo

Marque na Task, com `modelo` e `motivo_modelo`; a escolha fica auditável no log.

- `sonnet` é o padrão.
- `opus` quando o erro não seria pego por teste: lógica de domínio (precificação, apuração, convenções de calendário), mudança que atravessa vários módulos, ou tarefa que já falhou uma revisão.

A propriedade `configuracao` do Goal pode sobrepor a regra, para comparar arranjos: `tudo-opus` marca toda Task com `opus`; `opus-em-dominio` usa `opus` só nas de domínio; `padrao`, ou a ausência dela, segue a regra acima.

## Paralelismo

Só roda em paralelo o que não tem `depende_de` entre si e tem `arquivos_alvo` disjuntos. Tarefa sem `arquivos_alvo` nunca roda em paralelo: complete a propriedade antes. Em código muito acoplado, uma tarefa depois da outra rende mais do que três executores disputando os mesmos módulos.

Despache as paralelas numa só mensagem, uma chamada de subagente por tarefa. Cada executor sobe o próprio servidor MCP, com posse própria (`--autor-por-conexao`), e `assumir_tarefa` impede a colisão no grafo. O que impede dois agentes no mesmo arquivo é a sua checagem de `arquivos_alvo`, feita antes do despacho. O executor que precisar de arquivo fora do alvo para e devolve `fora_do_alvo`: acerte a Task e despache de novo quando o arquivo estiver livre.

## Higiene de contexto

- Todo retorno de subagente cabe em cerca de 1.500 tokens; saída longa de teste ou de consulta vai para arquivo, e volta o caminho com um resumo. As definições dos subagentes já dizem isso.
- Não cole retorno de subagente no grafo nem em outro despacho. O que vale guardar vira nó, com a proveniência de quem o registrou.
- Não abra arquivos inteiros para "ter contexto". Leia as linhas que sustentam a decisão que você vai registrar.
- Encerre a sessão a cada Task ou Goal fechado (passo 7).

## Quando travar

- Ambiguidade que você não resolve lendo código: `abrir_questao` na Task e `aguardar_resposta`.
- `proximas_tarefas` mostra uma tarefa impedida por `posse_de_outro` cujo subagente já terminou: a posse ficou órfã. Abra uma Question pedindo ao humano que devolva a posse (`liberar_tarefa` numa sessão humana devolve a de qualquer autor).
- Commit e push ficam com o humano, a menos que ele peça.

## Fechamento e memória

Executor e revisor registram `Aprendizado`, com `deriva_de`, quando algo vale além da tarefa. Você não registra: peça no despacho seguinte se notar um. Promover continua com o humano.

## Medir a divisão de modelos

Sem medir, a divisão de modelos fica no palpite. O harness grava um `Run` por sessão (seus tokens) e um por subagente (tokens, modelo e as tarefas que ele assumiu). Para comparar arranjos:

1. O humano cria um Goal por configuração, com a mesma descrição e `configuracao` igual a `tudo-opus`, `padrao` ou `opus-em-dominio`.
2. Cada Goal é orquestrado a partir do mesmo commit, num worktree próprio do git, para os executores de um arranjo não pisarem nos do outro.
3. Compare:

```bash
graphow orquestracao-medir --goal goal-tudo-opus --goal goal-padrao --goal goal-opus-em-dominio
```

O relatório dá, por configuração, as tarefas concluídas sem retrabalho, as rejeições na revisão e os tokens por tarefa concluída.

## Referências

- [Despacho](./references/despacho.md): o prompt de cada subagente e o formato do que ele devolve.
- [Configuração](./references/configuracao.md): servidores MCP por papel, hooks, permissões e o laço sem interface.
