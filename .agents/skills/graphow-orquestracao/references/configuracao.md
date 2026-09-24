# Configuração da orquestração

O Graphow fixa o papel na abertura da conexão MCP, e nenhum argumento de ferramenta o muda. Por isso cada papel tem o próprio servidor: o orquestrador fala com o servidor do `planejador`, cada executor com um servidor de `executor`, cada revisor com um de `revisor`. O explorador não tem servidor: ele não escreve no grafo.

## 1. Onde a skill e os subagentes moram

A skill é versionada no repositório do graphow, em `.agents/skills/graphow-orquestracao`, e os subagentes que ela despacha ficam em `.agents/agents` (`graphow-explorador`, `graphow-executor`, `graphow-executor-opus` e `graphow-revisor`). O ambiente só os encontra em `~/.claude`. Copie os dois de um checkout do graphow e repita a cópia a cada atualização:

```powershell
Copy-Item -Recurse -Force .agents/skills/graphow-orquestracao ~/.claude/skills/
Copy-Item -Force .agents/agents/graphow-*.md ~/.claude/agents/
```

`graphow skill-instalar` instala só a `graphow-mcp`, que esta skill exige.

Os subagentes sobem o servidor com `graphow mcp --autor-por-conexao`, e a skill usa `perspectiva` em `ler_vista`, `orienta` e as propriedades de orquestração de `criar_tarefa`. Tudo isso precisa estar no código que o executável `graphow` roda; com uma versão anterior, o servidor do subagente recusa a opção e não sobe.

## 2. O servidor do orquestrador

No `.mcp.json` do projeto que vai ser orquestrado:

```json
{
  "mcpServers": {
    "graphow-planejador": {
      "command": "graphow",
      "args": ["mcp", "--papel", "planejador", "--autor", "orquestrador"]
    }
  }
}
```

Na sessão do orquestrador, este é o único servidor do graphow. Um servidor com `--papel humano` na mesma sessão deixaria o orquestrador responder às próprias dúvidas e promover a própria memória; um de `executor` deixaria ele concluir tarefas que ele mesmo planejou.

Os servidores de executor e revisor não entram no `.mcp.json`. Cada definição de subagente declara o seu, dentro dela:

```yaml
mcpServers:
  - graphow-executor:
      type: stdio
      command: graphow
      args: ["mcp", "--papel", "executor", "--autor", "executor-sonnet", "--autor-por-conexao"]
```

O ambiente conecta esse servidor quando o subagente começa e o desliga quando ele termina, e a sessão principal não vê as ferramentas dele. `--autor-por-conexao` dá a cada invocação uma posse própria (`executor-sonnet#3f9a1c`): sem isso, dois executores em paralelo dividiriam a posse de qualquer tarefa.

## 3. Hooks

Copie para o `settings.json` do Claude Code os três hooks do arquivo `.agents/hooks/graphow_harness_hooks.json` do repositório do graphow:

- `SessionStart` abre a Sessao e imprime a vista de retomada, que é por onde o orquestrador volta depois de `/clear`;
- `SessionEnd` fecha a Sessao e grava no `Run` os tokens do orquestrador;
- `SubagentStop` grava um `Run` por subagente, com os tokens, o modelo e as tarefas que ele assumiu:

```powershell
graphow harness --fase subagente --entrada-hook
```

Sem o `SubagentStop`, `graphow orquestracao-medir` só enxerga o custo do orquestrador.

## 4. Permissões

Para os despachos não pararem em pedidos de permissão, libere no `settings.json` as ferramentas dos três servidores: `mcp__graphow-planejador`, `mcp__graphow-executor` e `mcp__graphow-revisor`. Edição de arquivo pelos executores segue a política do projeto; o revisor e o explorador não editam.

## 5. Uma sessão por tarefa, sem interface

A skill manda encerrar a sessão ao fechar cada tarefa, e o humano limpa com `/clear`. Sem ninguém à frente, o mesmo efeito vem de uma sessão não interativa por tarefa: cada invocação abre e fecha a própria Sessao pelos hooks, e a seguinte volta pela vista de retomada.

```powershell
claude -p --model opus "Use a skill graphow-orquestracao no Goal goal-x: feche a proxima Task e pare."
```

Repita enquanto `proximas_tarefas` do Goal tiver tarefa pronta. Cada rodada deixa o próprio `Run`, e a medição soma todos.

## 6. Conferir

```powershell
graphow banco-info
graphow orquestracao-medir --goal goal-x
```

O primeiro diz qual banco as instâncias estão usando: orquestrador, subagentes e hooks precisam do mesmo, então nenhum deles recebe `--db` apontando para outro lugar. O segundo mostra o que o Goal custou e rendeu até aqui.
