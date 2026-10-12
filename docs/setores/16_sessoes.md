# Setor 16 — Sessões claude -p

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.sessoes`

Roda uma sessão `claude -p` pelo caminho único: acha o executável (GRAPHOW_CLAUDE, depois o PATH), monta o comando com saída stream-json, tira do ambiente as variáveis da sessão mãe, aplica o GRAPHOW_DB pedido, espera até o tempo limite, grava o stream num arquivo e devolve o resultado tipado (sessão, texto final, erro, custo, tokens, duração e turnos). Não depende do grafo: é a peça sobre a qual a bancada e o orquestrador rodam agentes.

## Inventário

5 módulos · 558 linhas · 8 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`sessoes/executavel.py`](#sessoesexecutavel) | 46 | Onde está o executável do Claude Code: `GRAPHOW_CLAUDE`, depois o PATH. |
| [`sessoes/leitura_stream.py`](#sessoesleiturastream) | 197 | O que o stream-json de uma sessão `claude -p` diz dela: quem é, o que respondeu e quanto custou. |
| [`sessoes/pedido.py`](#sessoespedido) | 79 | O pedido de uma sessão `claude -p`: o comando que ela recebe e o ambiente em que roda. |
| [`sessoes/sessao_claude.py`](#sessoessessaoclaude) | 227 | Roda uma sessão `claude -p` com tempo limite e devolve o resultado tipado. |

## `sessoes/executavel.py`

Onde está o executável do Claude Code: `GRAPHOW_CLAUDE`, depois o PATH.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VARIAVEL_DO_EXECUTAVEL` | `str` | `'GRAPHOW_CLAUDE'` |
| `NOME_NO_PATH` | `str` | `'claude'` |

### `ExecutavelAusente` (GraphowError)

*serviço* — Não há executável do Claude Code para rodar a sessão.

### Funções do módulo

- `descobrir_executavel(ambiente: Mapping[str, str]) -> Path` — O executável que `GRAPHOW_CLAUDE` indica, ou o `claude` do PATH do ambiente dado.

## `sessoes/leitura_stream.py`

O que o stream-json de uma sessão `claude -p` diz dela: quem é, o que respondeu e quanto custou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPO_RESULTADO` | `str` | `'result'` |
| `TIPO_SISTEMA` | `str` | `'system'` |
| `SUBTIPO_INICIO` | `str` | `'init'` |
| `TIPO_LIMITE_DE_USO` | `str` | `'rate_limit_event'` |
| `STATUS_DO_LIMITE_REJEITADO` | `str` | `'rejected'` |
| `CHAVES_DO_MODEL_USAGE` | `Mapping[str, str]` | `{'entrada': 'inputTokens', 'saida': 'outputTokens', 'cache_leitura': 'c…` |

### `LeituraDoStream`

*DTO imutável* — A sessão que o stream abriu e o último resultado dela, quando houve um.

**Campos:** `session_id: str`, `modelo: str`, `resultado: ResultadoDoStream | None`, `limite_rejeitado: Mapping[str, Any] | None`

### `ResultadoDoStream`

*DTO imutável* — Um evento `result`: o fim de uma invocação do `claude -p`.

**Campos:** `session_id: str`, `texto: str`, `is_error: bool`, `subtipo: str`, `custo_usd: float`, `turnos: int`, `duracao_ms: int | None`, `tokens_por_modelo: Mapping[str, UsoDeTokens]`, `saida_estruturada: Any`, `erro_da_api: str`, `status_do_erro: int | None`, `razao_do_fim: str`

- `tokens() -> UsoDeTokens` `[property]` — O `modelUsage` somado entre os modelos.

### `UsoDeTokens`

*DTO imutável* — Tokens nas quatro categorias que o Claude Code conta; o total é a soma delas.

**Campos:** `entrada: int`, `saida: int`, `cache_leitura: int`, `cache_criacao: int`

- `total() -> int` `[property]` — Entrada, saída e as duas de cache somadas: a medida de tokens da bancada.
- `somar(outro: 'UsoDeTokens') -> 'UsoDeTokens'` — Categoria a categoria.
- `em_dicionario() -> dict[str, int]` — As categorias e o total, para gravar em JSON.

### Funções do módulo

- `eventos_do_stream(linhas: Iterable[str]) -> Iterator[Mapping[str, Any]]` — Cada linha que é um objeto JSON; o resto (vazia, truncada, texto solto) fica de fora.
- `ler_stream(linhas: Iterable[str]) -> LeituraDoStream` — A sessão do `system/init` e o último `result` do stream.
- `ler_resultado(evento: Mapping[str, Any]) -> ResultadoDoStream` — Os campos de um evento `result` que a bancada usa, com o que faltar zerado.

## `sessoes/pedido.py`

O pedido de uma sessão `claude -p`: o comando que ela recebe e o ambiente em que roda.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VARIAVEL_DO_BANCO` | `str` | `'GRAPHOW_DB'` |
| `PREFIXOS_REMOVIDOS` | `tuple[str, ...]` | `('CLAUDE',)` |
| `NOMES_REMOVIDOS` | `frozenset[str]` | `frozenset({'AI_AGENT', 'BAGGAGE'})` |
| `ARGUMENTOS_DE_SAIDA` | `tuple[str, ...]` | `('--output-format', 'stream-json', '--verbose')` |
| `SUFIXO_DA_SAIDA_DE_ERRO` | `str` | `'.err'` |
| `TEMPO_LIMITE_PADRAO_S` | `float` | `3600.0` |

### `PedidoDeSessao`

*DTO imutável* — O que uma sessão precisa para rodar e onde ela grava o que fez.

**Campos:** `prompt: str`, `pasta: Path`, `arquivo_stream: Path`, `modelo: str`, `modo_de_permissao: str`, `ferramentas_permitidas: tuple[str, ...]`, `retomar: str`, `banco_graphow: Path | None`, `tempo_limite_s: float`, `argumentos_extras: tuple[str, ...]`, `ambiente_extra: Mapping[str, str]`

- `arquivo_erro() -> Path` `[property]` — A saída de erro do processo, ao lado do stream.

### Funções do módulo

- `montar_comando(executavel: Sequence[str], pedido: PedidoDeSessao) -> tuple[str, ...]` — A linha de comando da sessão; o prompt fica de fora, porque vai pela entrada padrão.
- `limpar_ambiente(ambiente: Mapping[str, str], pedido: PedidoDeSessao) -> dict[str, str]` — O ambiente da sessão: o recebido sem as variáveis da sessão mãe, com o banco pedido e os extras.

## `sessoes/sessao_claude.py`

Roda uma sessão `claude -p` com tempo limite e devolve o resultado tipado.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NO_WINDOWS` | `bool` | `os.name == 'nt'` |
| `TEMPO_DO_TASKKILL_S` | `float` | `30.0` |

### `ExecutorDeSessao`

*serviço* — Lança o `claude -p` de cada pedido e espera por ele até o tempo limite.

- `comando_de(pedido: PedidoDeSessao) -> tuple[str, ...]` — A linha de comando que o pedido gera, sem rodar nada.
- `rodar(pedido: PedidoDeSessao) -> ResultadoDeSessao` — Roda a sessão, grava o stream e devolve o resultado lido dele.

### `FalhaAoAbrirSessao` (GraphowError)

*serviço* — O processo da sessão não chegou a rodar.

### `ResultadoDeSessao`

*DTO imutável* — O que a sessão fez, lido do stream, e como o processo terminou.

**Campos:** `comando: tuple[str, ...]`, `arquivo_stream: Path`, `inicio: datetime`, `fim: datetime`, `codigo_saida: int | None`, `tempo_esgotado: bool`, `leitura: LeituraDoStream`

- `session_id() -> str` `[property]` — A sessão que o stream abriu; vazio quando ele não chegou a abrir.
- `texto_final() -> str` `[property]` — A resposta final da sessão.
- `is_error() -> bool` `[property]` — Erro no resultado, no processo ou no tempo.
- `motivo_do_erro() -> str` `[property]` — Por que a sessão deu errado, com cada forma que aconteceu; vazio quando deu certo.
- `saida_estruturada() -> Any` `[property]` — O `structured_output` do resultado, quando a sessão rodou com `--json-schema`; None sem ele.
- `custo_usd() -> float | None` `[property]` — O custo que o resultado declarou (acumulado da sessão, se ela foi retomada); None sem resultado.
- `tokens() -> UsoDeTokens | None` `[property]` — O `modelUsage` do resultado: sessão e subagentes, acumulado como o custo; None sem resultado.
- `turnos() -> int | None` `[property]` — Os turnos que o resultado declarou; None sem resultado.
- `duracao_s() -> float` `[property]` — O tempo de parede, do lançamento do processo ao fim dele.
- `em_dicionario() -> dict[str, Any]` — O resumo da sessão, para gravar em JSON ao lado do stream.

### Funções do módulo

- `matar_arvore(processo: subprocess.Popen[bytes]) -> None` — O processo e os descendentes dele, a partir do PID; o próprio processo morre de qualquer jeito.
- `em_iso(instante: datetime) -> str` — O instante em ISO 8601 com fuso, em segundos.

