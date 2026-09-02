# Guia de Configuração do Servidor MCP do Graphow

O servidor MCP do Graphow opera sobre transporte `stdio` utilizando mensagens JSON-RPC 2.0 padrão.

> **`--papel` é obrigatório.** É aqui, e só aqui, que o papel do agente é definido:
> a partir da abertura da sessão ele fica imutável e nenhum argumento de ferramenta
> pode alterá-lo. Reserve `--papel humano` para sessões que você mesmo conduz.
>
> **Não aponte `--db` para uma pasta sincronizada por nuvem.** Sem `--db`, o banco é
> resolvido para o diretório de dados do usuário (`%LOCALAPPDATA%\graphow` no Windows).
> Confira com `graphow banco-info`.

Abaixo estão os modelos de configuração para integração em diferentes harnesses e plataformas.

---

## 1. Antigravity (`~/.gemini/config/mcp_config.json`)

Para habilitar as ferramentas do Graphow diretamente no Antigravity:

```json
{
  "mcpServers": {
    "graphow": {
      "command": "python",
      "args": [
        "-m",
        "graphow.mcp.stdio_server",
        "--papel",
        "executor",
        "--autor",
        "agente-antigravity"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/david/OneDrive/Documentos/graphow/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 2. Cursor IDE (`.cursor/mcp.json`)

Para disponibilizar as ferramentas para agentes no Cursor Composer:

```json
{
  "mcpServers": {
    "graphow": {
      "command": "python",
      "args": [
        "-m",
        "graphow.mcp.stdio_server",
        "--papel",
        "executor",
        "--autor",
        "agente-cursor"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 3. Claude Desktop (`claude_desktop_config.json`)

Localização no Windows: `%APPDATA%\Anthropic\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "graphow": {
      "command": "python",
      "args": [
        "-m",
        "graphow.mcp.stdio_server",
        "--papel",
        "executor",
        "--autor",
        "agente-antigravity"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/david/OneDrive/Documentos/graphow/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 4. Ambiente de Testes & Arena Coliseu (`arena/.mcp.json`)

Para uso no banco isolado de RPG/estresse multi-agente. `--papel` é obrigatório
aqui como em qualquer outra configuração: sem ele o servidor sai com erro de
argumento antes de responder ao aperto de mão, e o cliente recebe um
`JSONDecodeError` em vez de uma mensagem útil.

```json
{
  "mcpServers": {
    "graphow-arena": {
      "command": "python",
      "args": [
        "-m",
        "graphow.mcp.stdio_server",
        "--papel",
        "executor",
        "--autor",
        "agente-arena",
        "--db",
        "C:\\Users\\david\\OneDrive\\Documentos\\arena\\arena_graphow.db"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 5. Teste Manual Rápido via CLI

Você pode validar se o servidor stdio está respondendo através do comando:

```powershell
python .agents/skills/graphow-mcp/scripts/test_mcp_client.py
```

---

## 6. Hooks de Ciclo de Vida (`graphow harness`)

O servidor MCP cobre o que o agente **pede**. O que o agente **faz** — quando a
sessão começou, quando terminou — entra pelo subcomando `graphow harness`,
chamado pelos hooks de sessão do ambiente. Sem essa fiação, os eventos
`execucao_solicitada`, `execucao_iniciada` e `execucao_concluida` existiam no
vocabulário e nunca eram emitidos.

O arquivo [`../../../hooks/graphow_harness_hooks.json`](../../../hooks/graphow_harness_hooks.json)
traz o bloco pronto para copiar no `settings.json` do Claude Code. Ele usa
`--entrada-hook`, que lê o JSON do hook na entrada padrão e tira de lá o
`session_id`:

```powershell
graphow harness --fase inicio --entrada-hook --setor setor-engenharia
```

O hook **não** recebe o id da sessão em variável de ambiente. A primeira versão
deste arquivo passava `$CLAUDE_SESSION_ID`, que o ambiente nunca define: o
comando chegava com a sessão vazia e terminava em erro dentro do kernel. Em
outros harnesses, onde você já conhece o id, declare-o:

```powershell
graphow harness --fase inicio --sessao sess-01 --setor setor-engenharia --modelo opus-5
graphow harness --fase progresso --sessao sess-01
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"
```

`--sessao` e `--entrada-hook` são mutuamente exclusivos, e um dos dois é
obrigatório: sem nenhum, o analisador recusa antes de tocar no grafo.

O comando é curto e não interativo de propósito: ele roda dentro do hook, e
qualquer espera ali atrasaria o agente. A identidade é a do harness (papel
`sistema`), que só pode registrar a própria `Sessao` e a telemetria `Run`.
