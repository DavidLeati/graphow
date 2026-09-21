# Conexão ao servidor MCP do Graphow

O servidor fala JSON-RPC 2.0 sobre transporte `stdio`. Duas decisões são tomadas aqui, na linha de comando, e nenhuma delas pode ser mudada depois pelo agente.

`--papel` é obrigatório. Sem ele o processo sai com erro de argumento antes do aperto de mão, e o cliente recebe um `JSONDecodeError` no lugar de uma mensagem útil. Os valores aceitos são `planejador`, `executor`, `revisor` e `humano`; reserve `humano` para as sessões que você mesmo conduz.

`--db` é opcional e perigoso quando mal apontado. Sem ele o banco vai para o diretório de dados do usuário (`%LOCALAPPDATA%\graphow` no Windows), que é o certo. Apontar para pasta sincronizada por nuvem coloca o log append-only sob um sincronizador que não conhece transação. Confira o caminho resolvido com `graphow banco-info`.

## O bloco de configuração

Todos os harnesses usam o mesmo formato. Com o pacote instalado (`pip install -e .`), o comando é o executável:

```json
{
  "mcpServers": {
    "graphow": {
      "command": "graphow",
      "args": ["mcp", "--papel", "executor", "--autor", "agente-cursor"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

Rodando direto do código-fonte, sem instalar, troque o comando pelo módulo e aponte o `PYTHONPATH` para `src`:

```json
{
  "mcpServers": {
    "graphow": {
      "command": "python",
      "args": [
        "-m", "graphow.mcp.stdio_server",
        "--papel", "executor",
        "--autor", "agente-cursor"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/david/Documents/graphow/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Mude `--autor` por harness: é o identificador que vai para o log de eventos e o que aparece quando o kernel recusa a escrita de quem não detém a posse da tarefa.

| Harness | Arquivo de configuração |
| :--- | :--- |
| Antigravity | `~/.gemini/config/mcp_config.json` |
| Cursor | `.cursor/mcp.json` no projeto |
| Claude Desktop | `%APPDATA%\Anthropic\Claude\claude_desktop_config.json` |
| Arena Coliseu | `arena/.mcp.json` |

A Arena roda sobre banco isolado, e é o único caso em que vale passar `--db`:

```json
"args": [
  "mcp", "--papel", "executor", "--autor", "agente-arena",
  "--db", "C:\\Users\\david\\Documents\\arena\\arena_graphow.db"
]
```

## A skill do agente

A skill `graphow-mcp` (esta pasta) é o detalhe do protocolo: cookbook de patches, matriz de papéis e roteiro. Instale-a no diretório de skills do ambiente, onde todo projeto a vê, e rode de novo depois de atualizar o graphow, porque a cópia não se atualiza sozinha:

```powershell
graphow skill-instalar
```

O padrão é `~/.claude/skills`; `--destino` aponta outro diretório, e `--origem` outra pasta de skill quando o pacote não foi instalado de um checkout do repositório. O essencial do protocolo chega ao agente mesmo sem a skill: o hook de início o imprime no contexto, e o servidor MCP o declara em `instructions`.

## Teste rápido

```powershell
python .agents/skills/graphow-mcp/scripts/test_mcp_client.py
```

O script sobe o servidor em banco temporário, confere o aperto de mão e a lista de ferramentas, e verifica que uma sessão de executor recebe recusa ao chamar `responder_questao`.

## Hooks de ciclo de vida

O servidor MCP cobre o que o agente pede. Quando a sessão começou e quando terminou entra por outro caminho: o subcomando `graphow harness`, chamado pelos hooks do ambiente. Sem essa fiação, os eventos `execucao_solicitada`, `execucao_iniciada` e `execucao_concluida` existem no vocabulário e nunca são emitidos.

O bloco pronto para colar no `settings.json` do Claude Code está em [`graphow_harness_hooks.json`](../../../hooks/graphow_harness_hooks.json). Ele usa `--entrada-hook`, que lê o JSON do hook na entrada padrão e tira dali o `session_id`:

```powershell
graphow harness --fase inicio --entrada-hook
```

Nada precisa existir no grafo antes do primeiro hook. Sem `--setor`, a sessão nasce no ambiente padrão da memória do repositório em que o hook rodou (o `cwd` do payload): o `Projeto` com o nome da pasta do repositório e o `Setor` `Memoria` dentro dele, criados na primeira sessão e reaproveitados nas seguintes. Um worktree do git conta como o repositório principal. Passe `--setor <id>` só se quiser a sessão em outro Setor.

O id da sessão não chega por variável de ambiente. A primeira versão do arquivo passava `$CLAUDE_SESSION_ID`, que o ambiente nunca define: o comando chegava com a sessão vazia e terminava em erro dentro do kernel. Em harness onde você já conhece o id, declare-o:

```powershell
graphow harness --fase inicio --sessao sess-01 --modelo opus-5
graphow harness --fase progresso --sessao sess-01
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"
```

`--sessao` e `--entrada-hook` são mutuamente exclusivos, e um dos dois é obrigatório. O comando roda dentro do hook, então é curto e não interativo de propósito: qualquer espera ali atrasa o agente. A identidade é a do harness, papel `sistema`, que registra a própria `Sessao`, a telemetria `Run` e, na falta de um Setor configurado, o ambiente padrão; nada do grafo de trabalho.
