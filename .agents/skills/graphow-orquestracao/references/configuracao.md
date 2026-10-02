# Configuração da orquestração

O Graphow fixa o papel na abertura da conexão MCP, e nenhum argumento de ferramenta o muda. Por isso cada papel tem o próprio servidor: o condutor fala com um servidor de `planejador`, cada executor com um de `executor`, cada revisor com um de `revisor` e o árbitro com um de `arbitro`. O explorador não tem servidor, porque não escreve no grafo, e a raiz também não precisa de um.

## 1. Onde a skill e os subagentes moram

A skill é versionada no repositório do graphow, em `.agents/skills/graphow-orquestracao`, e os subagentes que ela usa ficam em `.agents/agents`: `graphow-condutor`, `graphow-explorador`, `graphow-executor`, `graphow-executor-opus`, `graphow-revisor`, `graphow-revisor-sonnet` e `graphow-arbitro`. O ambiente só os encontra em `~/.claude`. Copie os dois de um checkout do graphow e repita a cópia a cada atualização:

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

Os de executor e revisor seguem o mesmo formato, com `--papel executor` e `--papel revisor`; o do árbitro, `graphow-arbitro`, usa `--papel arbitro --autor arbitro`. O papel `arbitro` não dá poder por si só: a sessão cria só `Evidence`, `Decision` e `Note`, e o resto vem da política de governança do projeto do alvo, que o humano grava (`configurar_governanca`, ou a aba Configurações do `graphow web`). Sem política gravada vale a `governanca_maxima`, e o servidor do árbitro recusa todo gesto. Os dois revisores usam o mesmo servidor, `graphow-revisor`, e diferem no autor: `revisor-opus` e `revisor-sonnet`. `--autor-por-conexao` dá a cada invocação uma posse e uma autoria próprias (`executor-sonnet#3f9a1c`, `condutor#a81c02`): sem isso, dois executores em paralelo dividiriam a posse de qualquer tarefa, e o log não diria qual condutor tomou qual decisão.

Subagente aninhado sobe o próprio servidor. Isso foi testado em 2026-09-23: um `graphow-executor` despachado de dentro de outro subagente listou as ferramentas `mcp__graphow-executor` e leu a vista do projeto.

## 3. Hooks

Copie para o `settings.json` do Claude Code os três hooks do arquivo `.agents/hooks/graphow_harness_hooks.json` do repositório do graphow:

- `SessionStart` abre a Sessao da raiz e imprime a vista de retomada, com o id que a raiz passa ao condutor;
- `SessionEnd` fecha a Sessao e grava no `Run` os tokens da raiz e a última linha `Cota:` que ela escreveu;
- `SubagentStop` grava um `Run` por subagente, inclusive os aninhados que o condutor despacha, com os tokens, o modelo, as tarefas que ele assumiu, início, fim e duração e, no do condutor, a linha `Cota:` do despacho. Sem tokens, o `Run` diz por quê em `motivo_sem_consumo`:

```powershell
graphow harness --fase subagente --entrada-hook
```

Sem o `SubagentStop`, `graphow orquestracao-medir` só enxerga o custo da raiz.

## 4. Permissões

Para as rodadas não pararem em pedido de permissão, libere no `settings.json` as ferramentas dos quatro servidores de subagente: `mcp__graphow-condutor`, `mcp__graphow-executor`, `mcp__graphow-revisor` e `mcp__graphow-arbitro`. Com `ramo_base` gravado (seção 5), libere também `Bash(graphow base-colisoes *)`, que o condutor roda ao situar a rodada. Edição de arquivo pelos executores segue a política do projeto. Condutor, revisor, árbitro e explorador não editam. Com `integracao` no árbitro, a raiz commita e faz o merge local, e libere para ela `Bash(git status *)`, `Bash(git add *)`, `Bash(git commit *)`, `Bash(git merge *)` e `Bash(git diff *)`, sem `git push`.

## 5. Ramo base

Quando o trabalho de um Goal vai ser integrado num ramo que anda em paralelo, o condutor confere a cada rodada o que esse ramo ganhou. Num goal real, o ramo base `stage` ganhou migrations com os mesmos números que o Goal usava, e só se soube no merge, dias depois. Para ligar a conferência, o humano grava duas propriedades no Goal, no Setor ou no Projeto:

- `ramo_base`: o ramo em que o Goal vai ser integrado, `origin/stage` ou `stage`. Com remoto, o comando faz `git fetch` dele antes de comparar;
- `caminhos_de_colisao`: a lista de globs dos caminhos em que dois ramos colidem sem tocar o mesmo arquivo, como `["**/migrations/*.py"]`. `**/` vale zero ou mais diretórios; `*` e `?` não atravessam `/`.

O Goal herda cada uma do Setor que contém a sessão que o produziu e, na falta, do Projeto; as duas se resolvem uma a uma. O Projeto costuma levar os globs, e o Goal que vai para outro ramo grava só o `ramo_base` dele. Sem `ramo_base`, nada é conferido.

Grave pelo canvas (`graphow web`): selecione o nó, e em Propriedades use "Adicionar propriedade", com a lista escrita em JSON. Ou por `propor_patch` numa sessão com servidor de papel `humano`:

```json
{"justificativa": "Integracao do hub no stage", "operacoes": [
  {"op": "replace", "path": "/nos/proj-hub/propriedades/ramo_base", "value": "origin/stage"},
  {"op": "replace", "path": "/nos/proj-hub/propriedades/caminhos_de_colisao", "value": ["**/migrations/*.py"]}
]}
```

Para conferir à mão, na raiz do repositório do Goal:

```powershell
graphow base-colisoes --goal goal-x
```

Cada colisão sai numa linha, `<arquivo do ramo base> x <caminho do goal>`: um arquivo que o ramo base ganhou desde o merge-base, que casa com um glob e está no mesmo diretório de um caminho do Goal que casa com o mesmo glob. Os caminhos do Goal são os `arquivos_alvo` das tarefas abertas e os `arquivos` dos Artifacts. O código de saída é 0 sem colisão (ou sem `ramo_base`), 1 com colisão e 2 quando não deu para conferir. `--sem-fetch` compara com a cópia local do ramo remoto, e `--repo` aponta outro repositório.

Com colisão, a rodada devolve `Integrar:`. Com `integracao` no humano, a raiz para: o merge do ramo base e a renumeração são dele, ou da sessão principal a pedido dele. Com `integracao` no árbitro, a raiz commita o trabalho e faz o merge local, e só para se o merge conflitar ou a colisão pedir renumerar, que é editar código. O push é sempre do humano.

## 6. Sem interface

A raiz roda o laço inteiro numa chamada só e para no primeiro portão, então uma sessão não interativa basta:

```powershell
claude -p --model opus --permission-mode acceptEdits --allowedTools "Agent,Skill,Read,Glob,Grep,mcp__graphow-condutor,mcp__graphow-executor,mcp__graphow-revisor,Bash(python *),Bash(git status *),Bash(git diff *),Bash(git log *),Bash(graphow base-colisoes *)" --max-budget-usd 20 "Use a skill graphow-orquestracao no Setor setor-x, com cadencia setor."
```

A chamada termina num portão (`nada_a_fazer`, teto, Goal concluído na cadência `goal`) e deixa o próprio `Run`, e a medição soma todos. Ajuste o `--allowedTools` aos comandos com que os critérios do projeto se provam. Sem permissão, o modo não interativo recusa a ferramenta em vez de perguntar. `--max-budget-usd` é o teto duro de custo da chamada.

O `claude -p` precisa de credencial própria do CLI, porque a do app desktop só vale para as sessões do app. Com a credencial do CLI vencida, a chamada fica repetindo o erro de API sem imprimir nada. Gere uma com `claude setup-token` e passe-a em `CLAUDE_CODE_OAUTH_TOKEN`.

Para testar a skill sem tocar no banco real, aponte `GRAPHOW_DB` para um arquivo temporário. Os servidores MCP dos subagentes e os hooks herdam a variável do processo `claude`. Numa sessão do app, o caminho é o `env` do `.claude/settings.json` do projeto de teste. A documentação não garante que esse `env` chegue aos hooks e aos servidores, então confira a linha `Banco:` que o hook imprime antes de despachar qualquer coisa.

## 7. Conferir

```powershell
graphow banco-info
graphow orquestracao-medir --goal goal-x
graphow orquestracao-medir --goal goal-x --por-rodada
```

O primeiro diz qual banco as instâncias estão usando. Raiz, subagentes e hooks precisam do mesmo, então nenhum deles recebe `--db` apontando para outro lugar. O segundo mostra o que o Goal custou e rendeu até aqui, e o terceiro, rodada por rodada, com a duração e a cota. Rodada sem duração ou com cota `?` é hook que não gravou ou linha `Cota:` que faltou.
