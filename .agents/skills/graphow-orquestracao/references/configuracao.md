# Configuração da orquestração

O Graphow fixa o papel na abertura da conexão MCP, e nenhum argumento de ferramenta o muda. Por isso cada papel tem o próprio servidor: o condutor fala com um servidor de `planejador`, cada executor com um de `executor` e cada revisor com um de `revisor`. O explorador não tem servidor, porque não escreve no grafo, e a raiz também não precisa de um.

## 1. Onde a skill e os subagentes moram

A skill é versionada no repositório do graphow, em `.agents/skills/graphow-orquestracao`, e os subagentes que ela usa ficam em `.agents/agents`: `graphow-condutor`, `graphow-explorador`, `graphow-executor`, `graphow-executor-opus` e `graphow-revisor`. O ambiente só os encontra em `~/.claude`. Copie os dois de um checkout do graphow e repita a cópia a cada atualização:

```powershell
Copy-Item -Recurse -Force .agents/skills/graphow-orquestracao ~/.claude/skills/
Copy-Item -Force .agents/agents/graphow-*.md ~/.claude/agents/
```

`graphow skill-instalar` instala só a `graphow-mcp`, que esta skill exige e que o condutor pré-carrega (`skills: [graphow-mcp]`).

Os subagentes sobem o servidor com `graphow mcp --autor-por-conexao`, e a rodada usa `perspectiva` em `ler_vista`, `orienta` e as propriedades de orquestração de `criar_tarefa`. Tudo isso precisa estar no código que o executável `graphow` roda. Com uma versão anterior, o servidor do subagente recusa a opção e não sobe.

## 2. Servidores

A raiz não escreve no grafo e não precisa de servidor do graphow. Se o projeto tiver um no `.mcp.json`, ela pode usá-lo para ler, e só isso. Com `--papel humano`, o servidor deixaria a raiz responder às próprias dúvidas e promover a própria memória, e a skill proíbe as duas coisas.

Cada subagente declara o seu servidor dentro da própria definição, e o ambiente o liga quando o subagente começa e o desliga quando ele termina. O do condutor:

```yaml
mcpServers:
  - graphow-condutor:
      type: stdio
      command: graphow
      args: ["mcp", "--papel", "planejador", "--autor", "condutor", "--autor-por-conexao"]
```

Os de executor e revisor seguem o mesmo formato, com `--papel executor` e `--papel revisor`. `--autor-por-conexao` dá a cada invocação uma posse e uma autoria próprias (`executor-sonnet#3f9a1c`, `condutor#a81c02`): sem isso, dois executores em paralelo dividiriam a posse de qualquer tarefa, e o log não diria qual condutor tomou qual decisão.

Subagente aninhado sobe o próprio servidor. Isso foi testado em 2026-09-23: um `graphow-executor` despachado de dentro de outro subagente listou as ferramentas `mcp__graphow-executor` e leu a vista do projeto.

## 3. Hooks

Copie para o `settings.json` do Claude Code os três hooks do arquivo `.agents/hooks/graphow_harness_hooks.json` do repositório do graphow:

- `SessionStart` abre a Sessao da raiz e imprime a vista de retomada, com o id que a raiz passa ao condutor;
- `SessionEnd` fecha a Sessao e grava no `Run` os tokens da raiz;
- `SubagentStop` grava um `Run` por subagente, inclusive os aninhados que o condutor despacha, com os tokens, o modelo e as tarefas que ele assumiu:

```powershell
graphow harness --fase subagente --entrada-hook
```

Sem o `SubagentStop`, `graphow orquestracao-medir` só enxerga o custo da raiz.

## 4. Permissões

Para as rodadas não pararem em pedido de permissão, libere no `settings.json` as ferramentas dos três servidores de subagente: `mcp__graphow-condutor`, `mcp__graphow-executor` e `mcp__graphow-revisor`. Edição de arquivo pelos executores segue a política do projeto. Condutor, revisor e explorador não editam.

## 5. Sem interface

A raiz roda o laço inteiro numa chamada só e para no primeiro portão, então uma sessão não interativa basta:

```powershell
claude -p --model opus --permission-mode acceptEdits --allowedTools "Agent,Skill,Read,Glob,Grep,mcp__graphow-condutor,mcp__graphow-executor,mcp__graphow-revisor,Bash(python *),Bash(git status *),Bash(git diff *),Bash(git log *)" --max-budget-usd 20 "Use a skill graphow-orquestracao no Setor setor-x, com cadencia setor."
```

A chamada termina num portão (`nada_a_fazer`, teto, Goal concluído na cadência `goal`) e deixa o próprio `Run`, e a medição soma todos. Ajuste o `--allowedTools` aos comandos com que os critérios do projeto se provam. Sem permissão, o modo não interativo recusa a ferramenta em vez de perguntar. `--max-budget-usd` é o teto duro de custo da chamada.

O `claude -p` precisa de credencial própria do CLI, porque a do app desktop só vale para as sessões do app. Com a credencial do CLI vencida, a chamada fica repetindo o erro de API sem imprimir nada. Gere uma com `claude setup-token` e passe-a em `CLAUDE_CODE_OAUTH_TOKEN`.

Para testar a skill sem tocar no banco real, aponte `GRAPHOW_DB` para um arquivo temporário. Os servidores MCP dos subagentes e os hooks herdam a variável do processo `claude`. Numa sessão do app, o caminho é o `env` do `.claude/settings.json` do projeto de teste. A documentação não garante que esse `env` chegue aos hooks e aos servidores, então confira a linha `Banco:` que o hook imprime antes de despachar qualquer coisa.

## 6. Conferir

```powershell
graphow banco-info
graphow orquestracao-medir --goal goal-x
```

O primeiro diz qual banco as instâncias estão usando. Raiz, subagentes e hooks precisam do mesmo, então nenhum deles recebe `--db` apontando para outro lugar. O segundo mostra o que o Goal custou e rendeu até aqui.
