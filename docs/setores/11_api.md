# Setor 11 — Linha de Comando e Transporte

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.api`

Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.

## Inventário

7 módulos · 829 linhas · 10 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`api/cli.py`](#apicli) | 154 | Interface de Linha de Comando (CLI) para operação do Graphow. |
| [`api/cli_execucao.py`](#apicliexecucao) | 246 | Despacho e execução dos subcomandos da linha de comando do Graphow. |
| [`api/cli_execucao_grafo.py`](#apicliexecucaografo) | 133 | Manipuladores dos subcomandos que operam sobre um grafo já aberto. |
| [`api/cli_parser.py`](#apicliparser) | 195 | Construção do analisador de argumentos da linha de comando do Graphow. |
| [`api/console.py`](#apiconsole) | 55 | Adaptadores de escrita em console imunes a limitações de codificação do terminal. |
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

## `api/cli_execucao.py`

Despacho e execução dos subcomandos da linha de comando do Graphow.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_FALHA_DOMINIO` | `int` | `1` |
| `RAIZ_PROJETO` | `Path` | `Path(__file__).resolve().parents[3]` |
| `RAIZ_CODIGO_FONTE` | `Path` | `RAIZ_PROJETO / 'src' / 'graphow'` |
| `RAIZ_DOCUMENTACAO` | `Path` | `RAIZ_PROJETO / 'docs'` |

### `ContextoExecucao`

*DTO imutável* — Dependências resolvidas para a execução de um subcomando.

**Campos:** `argumentos: argparse.Namespace`, `localizacao_banco: LocalizacaoBanco`, `console: EscritorConsole`

### `ExecutorLinhaDeComando`

*serviço* — Resolve dependências de infraestrutura e executa o subcomando solicitado.

- `executar(argumentos: argparse.Namespace) -> int` — Executa o subcomando e devolve o código de saída do processo.

## `api/cli_execucao_grafo.py`

Manipuladores dos subcomandos que operam sobre um grafo já aberto.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_FALHA_DOMINIO` | `int` | `1` |

### `DependenciasComandosGrafo`

*DTO imutável* — Dependências já construídas que os subcomandos de grafo consomem.

**Campos:** `cli: GraphowCLI`, `kernel: WriteKernel`, `console: EscritorConsole`

### `ManipuladorComandosGrafo`

*serviço* — Executa subcomandos que exigem um kernel de escrita já construído.

- `executar(argumentos: argparse.Namespace, localizacao: LocalizacaoBanco) -> int` — Encaminha para o manipulador correspondente ao subcomando informado.

## `api/cli_parser.py`

Construção do analisador de argumentos da linha de comando do Graphow.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DESCRICAO_PROGRAMA` | `str` | `'Graphow - Substrato de Grafo Agentico Bilateral'` |
| `PAPEIS_ACEITOS_NO_MCP` | `tuple[str, ...]` | `(PapelAutor.PLANEJADOR.value, PapelAutor.EXECUTOR.value, PapelAutor.REV…` |
| `FASES_ACEITAS_NO_HARNESS` | `tuple[str, ...]` | `tuple((fase.value for fase in FaseDoHarness))` |

### Funções do módulo

- `construir_parser() -> argparse.ArgumentParser` — Monta o analisador completo com todos os subcomandos registrados.

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

## `api/sse_transport.py`

Transporte de eventos para visualizadores de Canvas via SSE / AG-UI Protocol.

### `SSETransport`

*serviço* — Formatador e gerador de stream de eventos Server-Sent Events compatível com AG-UI.

- `formatar_evento_sse(evento: EventoLog) -> str` — Formata um EventoLog no padrão Server-Sent Events.
- `gerar_stream_ag_ui(eventos: Sequence[EventoLog]) -> Iterator[str]` — Gera iterador de mensagens SSE a partir de uma sequência de eventos.

