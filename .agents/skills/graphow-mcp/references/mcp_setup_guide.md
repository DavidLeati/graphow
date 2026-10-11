# Conexão ao servidor MCP do Graphow

O servidor fala JSON-RPC 2.0 sobre transporte `stdio`. Duas decisões são tomadas aqui, na linha de comando, e nenhuma delas pode ser mudada depois pelo agente.

`--papel` é obrigatório, e o único valor aceito é `humano`: o servidor é o da sessão que você conduz (a do gerente, por exemplo). Sem ele o processo sai com erro de argumento antes do aperto de mão, e o cliente recebe um `JSONDecodeError` no lugar de uma mensagem útil. Os servidores por papel (`planejador`, `executor`, `revisor`, `arbitro`) saíram com os subagentes da orquestração antiga: os agentes do `graphow orquestrar` rodam sem MCP do graphow, recebem o briefing montado por código e devolvem JSON, e quem grava no grafo é o orquestrador, com o papel `orquestrador`, que nenhum servidor alcança. `sistema` é do harness e também não abre sessão MCP.

`--db` é opcional e perigoso quando mal apontado. Sem ele o banco vai para o diretório de dados do usuário (`%LOCALAPPDATA%\graphow` no Windows), que é o certo. Apontar para pasta sincronizada por nuvem coloca o log append-only sob um sincronizador que não conhece transação. Confira o caminho resolvido com `graphow banco-info`.

## Claude Code

No Claude Code, `graphow setup` imprime o comando que registra o servidor da sessão principal, com o caminho absoluto do executável já resolvido:

```powershell
graphow setup
```

O comando impresso tem esta forma, e roda uma vez por usuário:

```powershell
claude mcp add --scope user graphow -- "<executavel>" mcp --papel humano --autor <voce>
```

`<executavel>` é o caminho do `graphow` do seu venv (`.venv/Scripts/graphow.exe` no Windows, `.venv/bin/graphow` no Linux e no macOS). O papel é `humano` porque é a sessão que você conduz. As permissões que o setup grava liberam só as ferramentas de leitura desse servidor (`ler_vista`, `expandir_no`, `buscar`, `proximas_tarefas`, `minhas_questoes`, `aguardar_resposta`): os gestos do humano, como responder Question e promover Aprendizado, continuam pedindo sua confirmação a cada vez.

## O bloco de configuração dos outros ambientes

Todos os outros ambientes usam o mesmo formato. Com o pacote instalado (`pip install -e .`), o comando é o executável. Use o caminho absoluto quando o venv não estiver no PATH do processo que sobe o servidor, o que é o caso comum nos apps desktop:

```json
{
  "mcpServers": {
    "graphow": {
      "command": "graphow",
      "args": ["mcp", "--papel", "humano", "--autor", "voce"],
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
        "--papel", "humano",
        "--autor", "voce"
      ],
      "env": {
        "PYTHONPATH": "<checkout do graphow>/src",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Mude `--autor` por harness: é o identificador que vai para o log de eventos. A saída padrão do `graphow mcp` é só o canal JSON-RPC: o diagnóstico (`Banco: ...`) vai para a saída de erro.

| Ambiente | Arquivo de configuração |
| :--- | :--- |
| Claude Code | `claude mcp add` (acima); fica em `~/.claude.json` |
| Antigravity | `~/.gemini/config/mcp_config.json` |
| Cursor | `.cursor/mcp.json` no projeto |
| Claude Desktop | `%APPDATA%\Anthropic\Claude\claude_desktop_config.json` |
| Arena Coliseu | `arena/.mcp.json` |

A Arena roda sobre banco isolado, e é o único caso em que vale passar `--db`:

```json
"args": [
  "mcp", "--papel", "humano", "--autor", "arena",
  "--db", "<pasta da arena>/arena_graphow.db"
]
```

## A skill do agente

A skill `graphow-mcp` (esta pasta) é o detalhe do protocolo: cookbook de patches, matriz de papéis e roteiro. `graphow setup` a instala em `~/.claude/skills`, junto da `graphow-gerente`, e remove as cópias que versões anteriores instalaram (a skill `graphow-orquestracao` e os subagentes). Rode de novo depois de atualizar o graphow, porque a cópia não se atualiza sozinha; para só saber se ela envelheceu:

```powershell
graphow setup --conferir
```

Com outro diretório de skills, instale só esta skill:

```powershell
graphow skill-instalar --destino ~/.claude/skills
```

Os dois comandos leem a skill do checkout em que o pacote foi instalado com `pip install -e .`. Instalado de outro jeito, o pacote não sabe onde está `.agents/`, e a recusa pede `--origem`. O essencial do protocolo chega ao agente mesmo sem a skill: o hook de início o imprime no contexto, e o servidor MCP o declara em `instructions`.

## Teste rápido

```powershell
python .agents/skills/graphow-mcp/scripts/test_mcp_client.py
```

O script sobe o servidor em banco temporário, confere o aperto de mão e a lista de ferramentas, e verifica que um servidor com papel de agente (`--papel executor`) é recusado na abertura.

## Hooks de ciclo de vida

O servidor MCP cobre o que o agente pede. Quando a sessão começou e quando terminou entra por outro caminho: o subcomando `graphow harness`, chamado pelos hooks do ambiente. Sem essa fiação, os eventos `execucao_solicitada`, `execucao_iniciada` e `execucao_concluida` existem no vocabulário e nunca são emitidos.

No Claude Code, `graphow setup --escrever-settings` grava os dois hooks no `~/.claude/settings.json` com o caminho absoluto do executável, troca o hook do harness que já estiver lá e guarda o arquivo anterior em `settings.json.graphow.bak`. Sem a opção, o setup imprime o bloco para colar. A mesma fiação, com `graphow` sem caminho, está em [`graphow_harness_hooks.json`](../../../hooks/graphow_harness_hooks.json); colada como está, ela só funciona se o venv estiver no PATH do processo do Claude Code. Os hooks chamam `--entrada-hook`, que lê o JSON do hook na entrada padrão e tira dali o `session_id`:

```powershell
graphow harness --fase inicio --entrada-hook
```

Nada precisa existir no grafo antes do primeiro hook. Sem `--setor`, a sessão nasce no ambiente padrão da memória da pasta de trabalho em que o hook rodou (o `cwd` do payload): o `Projeto` com o nome dessa pasta e o `Setor` `Memoria` dentro dele, criados na primeira sessão e reaproveitados nas seguintes. Quando a pasta mora num repositório git, o nome é o da raiz do repositório, e um worktree conta como o repositório principal. Passe `--setor <id>` só se quiser a sessão em outro Setor.

O id da sessão não chega por variável de ambiente. A primeira versão do arquivo passava `$CLAUDE_SESSION_ID`, que o ambiente nunca define: o comando chegava com a sessão vazia e terminava em erro dentro do kernel. Em harness onde você já conhece o id, declare-o:

```powershell
graphow harness --fase inicio --sessao sess-01 --modelo opus-5
graphow harness --fase progresso --sessao sess-01
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"
```

O `SessionEnd` também lê a transcrição da sessão (`transcript_path`) e grava no `Run` os tokens por categoria (entrada, saída, leitura e criação de cache), o modelo que de fato respondeu e quantas mensagens o modelo mandou, cada uma contada uma vez. Sem transcrição legível o `Run` fica sem tokens, em vez de ficar com zero inventado. O hook `SubagentStop`, que gravava um `Run` por subagente do condutor, saiu com a orquestração por subagentes; a fase `subagente` do harness segue aceita só para um hook antigo ainda instalado não falhar, e `graphow setup --escrever-settings` o remove.

`--sessao` e `--entrada-hook` são mutuamente exclusivos, e um dos dois é obrigatório. O comando roda dentro do hook, então é curto e não interativo de propósito: qualquer espera ali atrasa o agente. A identidade é a do harness, papel `sistema`, que registra a própria `Sessao`, a telemetria `Run` e, na falta de um Setor configurado, o ambiente padrão; nada do grafo de trabalho.
