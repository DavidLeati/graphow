# Setor 11 — Linha de Comando e Transporte

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.api`

Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.

## Inventário

13 módulos · 2011 linhas · 20 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`api/cli.py`](#apicli) | 154 | Interface de Linha de Comando (CLI) para operação do Graphow. |
| [`api/cli_bancada.py`](#apiclibancada) | 220 | O subcomando `graphow bancada`: rodar uma arquitetura nas demandas do laboratório, auditar e comparar. |
| [`api/cli_execucao.py`](#apicliexecucao) | 323 | Despacho e execução dos subcomandos da linha de comando do Graphow. |
| [`api/cli_execucao_grafo.py`](#apicliexecucaografo) | 255 | Manipuladores dos subcomandos que operam sobre um grafo já aberto. |
| [`api/cli_orquestrar.py`](#apicliorquestrar) | 157 | O subcomando `graphow orquestrar`: rodar um Goal de uma spec ou do gerente, aprovar o plano e ver o status. |
| [`api/cli_parser.py`](#apicliparser) | 380 | Construção do analisador de argumentos da linha de comando do Graphow. |
| [`api/cli_setup.py`](#apiclisetup) | 117 | O subcomando `graphow setup`: o ambiente do Claude Code inteiro num comando só. |
| [`api/colisoes_base.py`](#apicolisoesbase) | 96 | O cruzamento puro entre o que o ramo base ganhou e o que o Goal toca. |
| [`api/conferencia_base.py`](#apiconferenciabase) | 101 | `graphow base-colisoes`: o que o ramo base ganhou e colide com o Goal, dito cedo. |
| [`api/console.py`](#apiconsole) | 55 | Adaptadores de escrita em console imunes a limitações de codificação do terminal. |
| [`api/git_ramo_base.py`](#apigitramobase) | 107 | O que o ramo base ganhou desde que o ramo do Goal saiu dele, perguntado ao git. |
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

- `main(argumentos: Sequence[str] | None) -> int` — Ponto de entrada principal da linha de comando.
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

*DTO imutável* — O que a CLI já abriu: o kernel, a conexão do banco, o console e onde o banco mora.

**Campos:** `kernel: WriteKernel`, `conexao: sqlite3.Connection`, `console: EscritorConsole`, `pasta_do_banco: Path`, `executor: ExecutorDeSessao | None`

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

## `api/colisoes_base.py`

O cruzamento puro entre o que o ramo base ganhou e o que o Goal toca.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TOKENS_DE_GLOB` | `re.Pattern[str]` | `re.compile('\\*\\*/|\\*\\*|\\*|\\?|[^*?]+')` |
| `TRADUCAO_DE_CURINGAS` | `dict[str, str]` | `{'**/': '(?:.*/)?', '**': '.*', '*': '[^/]*', '?': '[^/]'}` |
| `SEPARADOR_DE_REMOTO` | `str` | `'/'` |

### `Colisao`

*DTO imutável* — Um arquivo que o ramo base ganhou e o caminho do Goal com que ele colide.

**Campos:** `arquivo_da_base: str`, `caminho_do_goal: str`

- `formatar() -> str` — A linha que o comando imprime: `<arquivo do ramo base> x <caminho do goal>`.

### Funções do módulo

- `normalizar_caminho(caminho: str) -> str` — O caminho relativo à raiz do repositório como o git o escreve: barra normal e sem `./` na frente.
- `casa_glob(caminho: str, glob: str) -> bool` — O caminho inteiro casa com o glob.
- `nos_caminhos_de_colisao(arquivos: Iterable[str], globs: Iterable[str]) -> tuple[str, ...]` — Os arquivos que casam com algum dos globs, normalizados e em ordem.
- `cruzar_colisoes(arquivos_da_base: Iterable[str], caminhos_do_goal: Iterable[str], globs: Iterable[str]) -> tuple[Colisao, ...]` — Cada par que colide, uma vez só e em ordem.
- `separar_remoto(ramo_base: str, remotos: Iterable[str]) -> tuple[str, str]` — O remoto e o ramo dentro dele, quando `ramo_base` começa por um remoto; senão, vazio e o próprio ramo.

## `api/conferencia_base.py`

`graphow base-colisoes`: o que o ramo base ganhou e colide com o Goal, dito cedo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SEM_COLISAO` | `int` | `0` |
| `CODIGO_COM_COLISAO` | `int` | `1` |
| `CODIGO_CONFERENCIA_IMPOSSIVEL` | `int` | `2` |

### `PedidoDeConferencia`

*DTO imutável* — O Goal conferido, o repositório em que o git roda e se o ramo remoto é atualizado antes.

**Campos:** `id_goal: str`, `repositorio: Path`, `buscar: bool`

### `RelatorioDeColisoes`

*DTO imutável* — As linhas que o comando imprime e o código com que ele sai.

**Campos:** `linhas: tuple[str, ...]`, `codigo: int`

### Funções do módulo

- `conferir_colisoes(view: GrafoView, pedido: PedidoDeConferencia) -> RelatorioDeColisoes` — Resolve o ramo base do Goal, pergunta ao git o que ele ganhou e cruza com o que o Goal toca.

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

## `api/git_ramo_base.py`

O que o ramo base ganhou desde que o ramo do Goal saiu dele, perguntado ao git.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXECUTAVEL_DO_GIT` | `str` | `'git'` |
| `SEPARADOR_NULO` | `str` | `'\x00'` |
| `FILTRO_DO_QUE_O_RAMO_GANHOU` | `str` | `'--diff-filter=ACMR'` |
| `TAMANHO_DO_SHA_CURTO` | `int` | `12` |

### `ComparacaoComBase`

*DTO imutável* — O merge-base com o ramo base e o que o ramo base ganhou desde ele.

**Campos:** `merge_base: str`, `arquivos: tuple[str, ...]`, `aviso: str`

### `ExecutorGit`

*DTO imutável* — Roda o git dentro de um repositório e devolve a saída, ou recusa com o erro dele.

**Campos:** `repositorio: Path`

- `rodar() -> str` — A saída padrão do comando; `FalhaDoGit` com a saída de erro quando ele falha.

### `FalhaDoGit` (GraphowError)

*serviço* — O git não respondeu o que a conferência precisa: sem ele, ela não diz nada.

### `GitIndisponivel` (FalhaDoGit)

*serviço* — O executável do git não rodou.

### `GitRecusou` (FalhaDoGit)

*serviço* — O git rodou e saiu com erro; o contexto traz a saída de erro dele.

### Funções do módulo

- `comparar_com_ramo_base(git: ExecutorGit, ramo_base: str) -> ComparacaoComBase` — Atualiza o ramo base se pedido, acha o merge-base com o HEAD e lista o que o ramo base ganhou.

## `api/sse_transport.py`

Transporte de eventos para visualizadores de Canvas via SSE / AG-UI Protocol.

### `SSETransport`

*serviço* — Formatador e gerador de stream de eventos Server-Sent Events compatível com AG-UI.

- `formatar_evento_sse(evento: EventoLog) -> str` — Formata um EventoLog no padrão Server-Sent Events.
- `gerar_stream_ag_ui(eventos: Sequence[EventoLog]) -> Iterator[str]` — Gera iterador de mensagens SSE a partir de uma sequência de eventos.

