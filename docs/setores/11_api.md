# Setor 11 — Linha de Comando e Transporte

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.api`

Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.

## Inventário

10 módulos · 1834 linhas · 12 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`api/cli.py`](#apicli) | 155 | Interface de Linha de Comando (CLI) para operação do Graphow. |
| [`api/cli_bancada.py`](#apiclibancada) | 278 | O subcomando `graphow bancada`: rodar uma arquitetura nas demandas do laboratório, auditar e comparar. |
| [`api/cli_execucao.py`](#apicliexecucao) | 323 | Despacho e execução dos subcomandos da linha de comando do Graphow. |
| [`api/cli_execucao_grafo.py`](#apicliexecucaografo) | 246 | Manipuladores dos subcomandos que operam sobre um grafo já aberto. |
| [`api/cli_orquestrar.py`](#apicliorquestrar) | 244 | O subcomando `graphow orquestrar`: rodar um Goal de uma spec ou do gerente, aprovar o plano e ver o status. |
| [`api/cli_parser.py`](#apicliparser) | 354 | Construção do analisador de argumentos da linha de comando do Graphow. |
| [`api/cli_setup.py`](#apiclisetup) | 117 | O subcomando `graphow setup`: o ambiente do Claude Code inteiro num comando só. |
| [`api/console.py`](#apiconsole) | 71 | Adaptadores de escrita em console imunes a limitações de codificação do terminal. |
| [`api/sse_transport.py`](#apissetransport) | 36 | Transporte de eventos para visualizadores de Canvas via SSE / AG-UI Protocol. |

## `api/cli.py`

Interface de Linha de Comando (CLI) para operação do Graphow.

### `GraphowCLI`

*serviço* — Implementação dos comandos de terminal da CLI Graphow.

- `criar_task(titulo: str, id_sessao: str, autor: str) -> str` — Cria uma nova Task vinculada à Sessão e devolve o identificador gerado.
- `listar_tasks(ramo_id: str) -> tuple[ResumoTask, ...]` — Consulta as tarefas existentes no ramo sem alterar estado algum.
- `montar_sumario_grafo(ramo_id: str) -> str` — Retorna sumário textual legível do estado do grafo.
- `rastrear_linhagem(id_no: str, ramo_id: str) -> tuple[str, ...]` — Rastreia os passos causais do nó até o Goal raiz.
- `iniciar_servidor_web(porta: int, host: str) -> None` — Inicia o servidor web da interface visual interativa.

### `ResumoTask`

*DTO imutável* — Projeção imutável de uma tarefa para exibição na linha de comando.

**Campos:** `id: str`, `rotulo: str`, `status: str`

### Funções do módulo

- `main(argumentos: Sequence[str] | None) -> int` — Ponto de entrada principal da linha de comando; a saída que não é console sai em UTF-8.
- `descrever_localizacao_banco(localizacao: LocalizacaoBanco) -> tuple[str, ...]` — Monta as linhas de diagnóstico sobre onde o banco de eventos reside.

## `api/cli_bancada.py`

O subcomando `graphow bancada`: rodar uma arquitetura nas demandas do laboratório, auditar e comparar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_COM_ERRO` | `int` | `1` |
| `TODOS_OS_PROJETOS` | `str` | `'todos'` |
| `TEMPO_LIMITE_DA_RODADA_MIN` | `float` | `120.0` |
| `TEMPO_LIMITE_DO_AUDITOR_MIN` | `float` | `60.0` |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |

### `_Dependencias`

*DTO imutável* — O registro de arquiteturas e o executor de sessão; o executor só nasce quando uma ação roda sessão.

**Campos:** `registro: RegistroDeArquiteturas`, `sessoes: ExecutorDeSessao | None`

- `executor() -> ExecutorDeSessao` — O executor injetado, ou o que acha o claude em GRAPHOW_CLAUDE ou no PATH.

### Funções do módulo

- `registrar_comando_de_bancada(subparsers: argparse._SubParsersAction, parser_base: argparse.ArgumentParser) -> None` — Registra `graphow bancada` e as ações dele.
- `executar_bancada(argumentos: argparse.Namespace, console: EscritorConsole) -> int` — Executa a ação pedida; o registro e o executor de sessão podem vir de fora, nos testes.

## `api/cli_execucao.py`

Despacho e execução dos subcomandos da linha de comando do Graphow.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_FALHA_DOMINIO` | `int` | `1` |
| `RAIZ_PROJETO` | `Path` | `Path(__file__).resolve().parents[3]` |
| `RAIZ_CODIGO_FONTE` | `Path` | `RAIZ_PROJETO / 'src' / 'graphow'` |
| `RAIZ_DOCUMENTACAO` | `Path` | `RAIZ_PROJETO / 'docs'` |
| `COMANDOS_COM_PROTOCOLO_NA_SAIDA_PADRAO` | `frozenset[str]` | `frozenset({'mcp'})` |

### `ContextoExecucao`

*DTO imutável* — Dependências resolvidas para a execução de um subcomando.

**Campos:** `argumentos: argparse.Namespace`, `localizacao_banco: LocalizacaoBanco`, `console: EscritorConsole`

### `ExecutorLinhaDeComando`

*serviço* — Resolve dependências de infraestrutura e executa o subcomando solicitado.

- `executar(argumentos: argparse.Namespace) -> int` — Executa o subcomando e devolve o código de saída do processo.

### Funções do módulo

- `escolher_console(comando: str | None, injetado: EscritorConsole | None) -> EscritorConsole` — O console injetado vale sempre; sem ele, o comando de protocolo escreve na saída de erro.

## `api/cli_execucao_grafo.py`

Manipuladores dos subcomandos que operam sobre um grafo já aberto.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_FALHA_DOMINIO` | `int` | `1` |

### `DependenciasComandosGrafo`

*DTO imutável* — Dependências já construídas que os subcomandos de grafo consomem.

**Campos:** `cli: GraphowCLI`, `kernel: WriteKernel`, `console: EscritorConsole`, `store: SQLiteEventStore | None`

### `ManipuladorComandosGrafo`

*serviço* — Executa subcomandos que exigem um kernel de escrita já construído.

- `executar(argumentos: argparse.Namespace, localizacao: LocalizacaoBanco) -> int` — Encaminha para o manipulador correspondente ao subcomando informado.

## `api/cli_orquestrar.py`

O subcomando `graphow orquestrar`: rodar um Goal de uma spec ou do gerente, aprovar o plano e ver o status.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_FECHADO` | `int` | `0` |
| `CODIGO_FALHA` | `int` | `1` |
| `CODIGO_PARADO` | `int` | `3` |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |
| `PASTA_DO_ESTADO` | `str` | `'orquestrar'` |

### `AmbienteDoOrquestrar`

*DTO imutável* — O que a CLI já abriu: o kernel, a conexão do banco e a trava dela, o console e onde o banco mora.

**Campos:** `kernel: WriteKernel`, `conexao: sqlite3.Connection`, `console: EscritorConsole`, `pasta_do_banco: Path`, `executor: ExecutorDeSessao | None`, `trava: 'threading.RLock | None'`

### Funções do módulo

- `registrar_comando_de_orquestrar(subparsers: argparse._SubParsersAction, parser_base: argparse.ArgumentParser) -> None` — Registra `graphow orquestrar` e as opções dele.
- `executar_orquestrar(argumentos: argparse.Namespace, ambiente: AmbienteDoOrquestrar) -> int` — Executa a ação pedida e devolve o código de saída.

## `api/cli_parser.py`

Construção do analisador de argumentos da linha de comando do Graphow.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DESCRICAO_PROGRAMA` | `str` | `'Graphow - Substrato de Grafo Agentico Bilateral'` |
| `PAPEIS_ACEITOS_NO_MCP` | `tuple[str, ...]` | `(PapelAutor.HUMANO.value,)` |
| `FASES_ACEITAS_NO_HARNESS` | `tuple[str, ...]` | `tuple((fase.value for fase in FaseDoHarness))` |

### Funções do módulo

- `construir_parser() -> argparse.ArgumentParser` — Monta o analisador completo com todos os subcomandos registrados.

## `api/cli_setup.py`

O subcomando `graphow setup`: o ambiente do Claude Code inteiro num comando só.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_EM_DIA` | `int` | `0` |
| `CODIGO_DESATUALIZADO` | `int` | `1` |
| `ARQUIVO_DE_SETTINGS` | `str` | `'settings.json'` |
| `OPCOES_DE_MODO` | `tuple[tuple[str, str], ...]` | `(('--escrever-settings', 'Mescla hooks e permissoes no settings.json, c…` |

### Funções do módulo

- `registrar_comando_de_setup(subparsers: argparse._SubParsersAction, parser_base: argparse.ArgumentParser) -> None` — Registra o setup do ambiente, que não toca o banco.
- `executar_setup(argumentos: argparse.Namespace, console: EscritorConsole, raiz_padrao: Path) -> int` — Instala ou confere o ambiente e imprime o que segue manual.

## `api/console.py`

Adaptadores de escrita em console imunes a limitações de codificação do terminal.

### `EscritorConsole` (ABC)

*contrato* — Contrato de saída textual da linha de comando.

- `escrever_linha(texto: str) -> None` `[abstract]` — Emite uma linha de texto para o operador.

### `EscritorConsoleEmMemoria` (EscritorConsole)

*serviço* — Captura as linhas emitidas, para asserção determinística em testes.

- `escrever_linha(texto: str) -> None` — Acumula a linha na lista interna.
- `linhas() -> tuple[str, ...]` `[property]` — Cópia imutável das linhas emitidas até agora.

### `EscritorConsolePadrao` (EscritorConsole)

*serviço* — Escreve no fluxo do processo sem jamais falhar por caractere não representável.

- `escrever_linha(texto: str) -> None` — Escreve a linha substituindo caracteres que a codificação não suporta.

### Funções do módulo

- `saida_em_utf8(fluxos: Sequence[TextIO] | None) -> None` — Põe em UTF-8 a saída padrão e a de erro que não são console; o fluxo que não sabe se reconfigurar fica.

## `api/sse_transport.py`

Transporte de eventos para visualizadores de Canvas via SSE / AG-UI Protocol.

### `SSETransport`

*serviço* — Formatador e gerador de stream de eventos Server-Sent Events compatível com AG-UI.

- `formatar_evento_sse(evento: EventoLog) -> str` — Formata um EventoLog no padrão Server-Sent Events.
- `gerar_stream_ag_ui(eventos: Sequence[EventoLog]) -> Iterator[str]` — Gera iterador de mensagens SSE a partir de uma sequência de eventos.

