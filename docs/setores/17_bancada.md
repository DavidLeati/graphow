# Setor 17 — Bancada de Medição

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.bancada`

O portão de cada fase da reestruturação: as três demandas do laboratório rodadas do zero por arquitetura e auditadas do mesmo jeito. Lê os dados versionados em `bancada/` (semente, spec, sondas, prompts e linha de base) e recria o repositório de cada execução com o mesmo hash do laboratório. Não toca o banco do usuário: cada execução tem o seu.

## Inventário

11 módulos · 1282 linhas · 19 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`bancada/arquiteturas.py`](#bancadaarquiteturas) | 108 | As arquiteturas que a bancada sabe rodar, registradas por nome. |
| [`bancada/auditoria.py`](#bancadaauditoria) | 148 | `graphow bancada auditar`: o auditor do laboratório numa sessão `claude -p`, e o placar extraído do relatório. |
| [`bancada/entrega.py`](#bancadaentrega) | 71 | O estado git da entrega: o ramo de trabalho, os commits depois da semente e a árvore suja. |
| [`bancada/execucao.py`](#bancadaexecucao) | 147 | `graphow bancada rodar`: monta a execução, roda a arquitetura e grava `execucao.json`. |
| [`bancada/formatacao.py`](#bancadaformatacao) | 45 | Números da bancada como o relatório do laboratório os escreve: vírgula decimal e ponto de milhar. |
| [`bancada/medicao.py`](#bancadamedicao) | 218 | Custo, tokens e minutos de uma execução, com as definições do laboratório. |
| [`bancada/placar.py`](#bancadaplacar) | 175 | `graphow bancada placar`: as execuções de uma saída contra a linha de base, com a variação de cada número. |
| [`bancada/projetos.py`](#bancadaprojetos) | 165 | Os dados versionados da bancada: projetos, prompts e linha de base, lidos de `bancada/`. |
| [`bancada/semente.py`](#bancadasemente) | 93 | O repositório de uma execução, recriado da semente com o mesmo hash do laboratório. |
| [`bancada/transcricoes.py`](#bancadatranscricoes) | 103 | Os tokens de uma execução, somados das transcrições que o Claude Code grava em disco. |

## `bancada/arquiteturas.py`

As arquiteturas que a bancada sabe rodar, registradas por nome.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOME_DA_ENXUTA` | `str` | `'enxuta'` |
| `MODELO_DA_ENXUTA` | `str` | `'opus'` |
| `PERMISSAO_DA_ENXUTA` | `str` | `'bypassPermissions'` |
| `PASTA_DAS_SESSOES` | `str` | `'sessoes'` |

### `Arquitetura` (Protocol)

*serviço* — O que a bancada exige de uma arquitetura: um nome e rodar a execução montada.

**Campos:** `nome: str`

- `executar(pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]` — Roda o projeto e devolve as sessões, na ordem em que rodaram.

### `ArquiteturaEnxuta`

*serviço* — Uma sessão Opus, sem graphow, com o prompt de processo fixo do laboratório.

**Campos:** `nome: str`

- `pedido_de_sessao(pedido: PedidoDeExecucao) -> PedidoDeSessao` — A sessão única: o prompt preenchido com a spec ao lado do repositório e o ramo do projeto.
- `executar(pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]` — Roda a sessão única.

### `PedidoDeExecucao`

*DTO imutável* — A execução montada que a arquitetura recebe: onde está cada coisa e quanto tempo ela tem.

**Campos:** `projeto: ProjetoDaBancada`, `bancada: Bancada`, `diretorio: Path`, `repositorio: Path`, `spec: Path`, `banco: Path`, `tempo_limite_s: float`

- `pasta_das_sessoes() -> Path` `[property]` — Onde cada sessão grava o stream e a saída de erro.

### `RegistroDeArquiteturas`

*serviço* — As arquiteturas por nome, cada uma com a fábrica que a cria.

- `nomes() -> tuple[str, ...]` `[property]` — Os nomes registrados, em ordem alfabética.
- `registrar(nome: str, fabrica: Callable[[], Arquitetura]) -> None` — Registra a arquitetura; o mesmo nome duas vezes é engano e recusa.
- `criar(nome: str) -> Arquitetura` — A arquitetura pelo nome; a recusa lista as registradas.

### Funções do módulo

- `registro_padrao() -> RegistroDeArquiteturas` — O registro com as arquiteturas que existem hoje: só a enxuta.

## `bancada/auditoria.py`

`graphow bancada auditar`: o auditor do laboratório numa sessão `claude -p`, e o placar extraído do relatório.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARQUIVO_DA_AUDITORIA` | `str` | `'auditoria.json'` |
| `PASTA_DA_AUDITORIA` | `str` | `'auditoria'` |
| `MODELO_DO_AUDITOR` | `str` | `'opus'` |
| `PERMISSAO_DO_AUDITOR` | `str` | `'bypassPermissions'` |
| `TEMPO_LIMITE_DO_AUDITOR_S` | `float` | `3600.0` |
| `MARCA_DO_PLACAR` | `str` | `'PLACAR'` |
| `PADRAO_DOS_CRITERIOS` | `re.Pattern[str]` | `re.compile('atende\\D{0,3}(\\d+)\\s*/\\s*parcial\\D{0,3}(\\d+)\\s*/\\s*…` |
| `PADRAO_DAS_SONDAS` | `re.Pattern[str]` | `re.compile('ok\\D{0,3}(\\d+)\\s*/\\s*defeitos?\\D{0,3}(\\d+)', re.IGNOR…` |
| `PADRAO_DOS_BLOQUEANTES` | `re.Pattern[str]` | `re.compile('bloqueantes?\\D{0,3}(\\d+)', re.IGNORECASE)` |
| `PADRAO_DE_ITEM` | `re.Pattern[str]` | `re.compile('^\\s*(?:[-*]|\\d+[.)])\\s+(?P<texto>.+)$')` |

### `Placar`

*DTO imutável* — A linha `PLACAR:` do auditor, em números.

**Campos:** `atende: int`, `parcial: int`, `nao_atende: int`, `sondas_ok: int`, `sondas_defeito: int`, `bloqueantes: int`, `linha: str`

- `em_dicionario() -> dict[str, Any]` — O placar para gravar em JSON, com a linha original.

### Funções do módulo

- `extrair_placar(texto: str) -> Placar | None` — O último `PLACAR:` legível do relatório; None quando nenhum traz os números.
- `bloqueantes_listados(texto: str) -> tuple[str, ...]` — Os itens de lista depois da última linha `PLACAR:`, onde o prompt pede os defeitos bloqueantes.
- `pedido_do_auditor(execucao: Path, bancada: Bancada, tempo_limite_s: float) -> PedidoDeSessao` — A sessão do auditor sobre a execução: prompt preenchido, pasta da execução e banco próprio.
- `auditar(execucao: Path, pedido: PedidoDeSessao, sessoes: ExecutorDeSessao) -> dict[str, Any]` — Roda o auditor, guarda prompt e relatório e grava `auditoria.json` com o placar.

## `bancada/entrega.py`

O estado git da entrega: o ramo de trabalho, os commits depois da semente e a árvore suja.

### `EstadoDaEntrega`

*DTO imutável* — Onde a entrega está no repositório da execução.

**Campos:** `ramo: str`, `ramo_existe: bool`, `ramo_atual: str`, `commits: int`, `arvore_suja: bool`

- `em_dicionario() -> dict[str, object]` — O estado para gravar em JSON.

### Funções do módulo

- `ler_estado_da_entrega(repositorio: Path, projeto: ProjetoDaBancada) -> EstadoDaEntrega` — O ramo de trabalho, os commits nele depois da semente, o ramo do HEAD e se há mudança fora de commit.
- `descrever_ramo(estado: EstadoDaEntrega) -> str` — O ramo como o prompt do auditor o recebe, com a ressalva quando o trabalho não está nele.

## `bancada/execucao.py`

`graphow bancada rodar`: monta a execução, roda a arquitetura e grava `execucao.json`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARQUIVO_DA_EXECUCAO` | `str` | `'execucao.json'` |
| `NOME_DO_BANCO` | `str` | `'graphow.db'` |
| `VERSAO_DO_REGISTRO` | `int` | `1` |
| `FORMATO_DO_CARIMBO` | `str` | `'%Y%m%d-%H%M%S'` |

### `ConfiguracaoDaRodada`

*DTO imutável* — O que vale para todas as execuções de uma rodada: onde gravar, de onde ler e quanto esperar.

**Campos:** `bancada: Bancada`, `saida: Path`, `raiz_das_transcricoes: Path | None`, `tempo_limite_s: float`, `carimbo: str`

### `ExecucaoGravada`

*DTO imutável* — Uma execução terminada: a pasta dela e o que foi gravado em `execucao.json`.

**Campos:** `diretorio: Path`, `registro: dict[str, Any]`

### Funções do módulo

- `montar_execucao(arquitetura: str, projeto: ProjetoDaBancada, configuracao: ConfiguracaoDaRodada) -> PedidoDeExecucao` — A pasta da execução, com o repositório da semente, a spec ao lado e o caminho do banco.
- `rodar_execucao(arquitetura: Arquitetura, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> ExecucaoGravada` — Roda a arquitetura na execução montada, mede e grava `execucao.json`.
- `rodar_projetos(arquitetura: Callable[[], Arquitetura], projetos: Sequence[ProjetoDaBancada], configuracao: ConfiguracaoDaRodada) -> tuple[ExecucaoGravada, ...]` — Cada projeto na sua execução; mais de um roda em paralelo, um por linha de execução.
- `gravar_json(caminho: Path, dados: dict[str, Any]) -> None` — O registro em JSON legível, UTF-8 e fim de linha LF.
- `ler_json(caminho: Path) -> dict[str, Any]` — Um registro da bancada; ausente ou ilegível recusa com o caminho.

## `bancada/formatacao.py`

Números da bancada como o relatório do laboratório os escreve: vírgula decimal e ponto de milhar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TOKENS_POR_MILHAO` | `float` | `1000000.0` |
| `SEM_VALOR` | `str` | `'-'` |

### Funções do módulo

- `formatar_dinheiro(valor: float | None) -> str` — `US$ 5,03`.
- `formatar_tokens(valor: int | None) -> str` — `6,2 M`, a forma do relatório.
- `formatar_inteiro(valor: int | None) -> str` — `6.160.643`.
- `formatar_minutos(valor: float | None) -> str` — `20,0 min`.
- `formatar_variacao(valor: float | None, base: float | None) -> str` — A variação em relação à base: percentual, ou a diferença absoluta quando a base é zero.

## `bancada/medicao.py`

Custo, tokens e minutos de uma execução, com as definições do laboratório.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MARCA_DO_LABORATORIO` | `str` | `'_lab'` |
| `MARCA_DE_INICIO` | `str` | `'inicio'` |
| `MARCA_DE_FIM` | `str` | `'fim'` |
| `FONTE_TRANSCRICOES` | `str` | `'transcricoes'` |
| `FONTE_MODEL_USAGE` | `str` | `'model_usage'` |
| `FONTE_MISTA` | `str` | `'transcricoes_e_model_usage'` |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |

### `Invocacao`

*DTO imutável* — Uma chamada de `claude -p`: a sessão, quando começou, quando acabou e o resultado que deu.

**Campos:** `sessao: str`, `inicio: datetime | None`, `fim: datetime | None`, `resultado: ResultadoDoStream | None`

### `Medicao`

*DTO imutável* — Custo, tokens e minutos de uma execução, e de onde saíram os tokens.

**Campos:** `custo_usd: float`, `tokens: int`, `fonte_dos_tokens: str`, `minutos: float | None`, `sessoes: tuple[str, ...]`

- `em_dicionario() -> dict[str, Any]` — Os números como a bancada os grava, com o custo em centavos e os minutos com uma casa.

### `_LeitorDoLog`

*serviço* — Junta os eventos de um log do laboratório em invocações, marca a marca.

- `acrescentar(evento: Mapping[str, Any]) -> None` — Marca de início abre, marca de fim fecha; init e result preenchem a invocação aberta.

### Funções do módulo

- `invocacoes_do_log(linhas: Iterable[str]) -> tuple[Invocacao, ...]` — As invocações de um log do laboratório: cada par de marcas e o que veio entre elas.
- `ler_log(caminho: Path) -> tuple[Invocacao, ...]` — As invocações do log em disco.
- `medir(invocacoes: Sequence[Invocacao], raiz_das_transcricoes: Path | None) -> Medicao` — Custo, tokens e minutos das invocações, com as transcrições achadas sob a raiz.
- `minutos_das_invocacoes(invocacoes: Sequence[Invocacao]) -> float | None` — Do primeiro início ao último fim; None quando falta algum instante.
- `contar_sessoes_retomadas(invocacoes: Sequence[Invocacao]) -> int` — Quantas sessões tiveram mais de um resultado: as que o laboratório contou em dobro.

## `bancada/placar.py`

`graphow bancada placar`: as execuções de uma saída contra a linha de base, com a variação de cada número.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVE_DO_COMPARAVEL` | `str` | `'comparavel'` |
| `CAMPOS_DO_COMPARAVEL` | `tuple[str, ...]` | `('custo_usd', 'tokens', 'minutos')` |
| `CABECALHO_DOS_NUMEROS` | `str` | `'| Execucao | Projeto | US$ | Tokens | Min | Commits | Criterios | Sond…` |
| `ALINHAMENTO_DOS_NUMEROS` | `str` | `'| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |'` |
| `CABECALHO_DAS_VARIACOES` | `str` | `'| Execucao | Contra | US$ | Tokens | Min | Commits | Atende (fracao) |…` |
| `ALINHAMENTO_DAS_VARIACOES` | `str` | `'| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |'` |
| `CAMPOS_DA_VARIACAO` | `tuple[str, ...]` | `('custo_usd', 'tokens', 'minutos', 'commits', 'fracao_atende', 'sondas_…` |

### `LinhaDoPlacar`

*DTO imutável* — Uma execução, ou uma referência da linha de base, num projeto.

**Campos:** `rotulo: str`, `arquitetura: str`, `projeto: str`, `numeros: Numeros`, `observacao: str`

### `Numeros`

*DTO imutável* — O que o placar compara de uma execução; o que não foi medido fica None.

**Campos:** `custo_usd: float | None`, `tokens: int | None`, `minutos: float | None`, `commits: int | None`, `atende: int | None`, `parcial: int | None`, `nao_atende: int | None`, `sondas_ok: int | None`, `sondas: int | None`, `bloqueantes: int | None`

- `fracao_atende() -> float | None` `[property]` — Os critérios atendidos sobre os julgados: o que se compara entre auditorias.

### Funções do módulo

- `ler_execucoes(saida: Path) -> tuple[LinhaDoPlacar, ...]` — Toda execução da saída (ou a própria saída, se for uma execução), em ordem de nome.
- `ler_linha_de_base(caminho: Path) -> dict[tuple[str, str], LinhaDoPlacar]` — As referências da linha de base por arquitetura e projeto, com o comparável onde houver.
- `formatar_placar(execucoes: Sequence[LinhaDoPlacar], base: Mapping[tuple[str, str], LinhaDoPlacar]) -> tuple[str, ...]` — A tabela dos números, a das variações contra cada arquitetura de base e as observações.

## `bancada/projetos.py`

Os dados versionados da bancada: projetos, prompts e linha de base, lidos de `bancada/`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAIZ_DA_BANCADA_PADRAO` | `Path` | `Path(__file__).resolve().parents[3] / 'bancada'` |
| `PASTA_DOS_PROJETOS` | `str` | `'projetos'` |
| `PASTA_DAS_ARQUITETURAS` | `str` | `'arquiteturas'` |
| `ARQUIVO_DO_PROJETO` | `str` | `'projeto.json'` |
| `ARQUIVO_DA_SPEC` | `str` | `'spec.md'` |
| `ARQUIVO_DAS_SONDAS` | `str` | `'sondas.md'` |
| `PASTA_DA_SEMENTE` | `str` | `'semente'` |
| `ARQUIVO_DO_AUDITOR` | `str` | `'auditor.md'` |
| `ARQUIVO_DA_LINHA_DE_BASE` | `str` | `'linha-de-base.json'` |
| `EXTENSAO_DO_MODELO` | `str` | `'.md'` |
| `PADRAO_DE_MARCADOR` | `re.Pattern[str]` | `re.compile('\\{([A-Z][A-Z_]*)\\}')` |
| `PADRAO_DE_AUTOR` | `re.Pattern[str]` | `re.compile('^(?P<nome>[^<]+?)\\s*<(?P<email>[^>]+)>$')` |

### `Bancada`

*DTO imutável* — A pasta `bancada/`: onde os projetos, os prompts e a linha de base estão.

**Campos:** `raiz: Path`

- `linha_de_base() -> Path` `[property]` — Os números do laboratório contra os quais o placar compara.
- `projetos() -> tuple[ProjetoDaBancada, ...]` — Todo projeto com `projeto.json`, em ordem de nome.
- `projeto(nome: str) -> ProjetoDaBancada` — O projeto pelo nome; a recusa lista os que existem.
- `modelo_da_arquitetura(nome: str) -> str` — O prompt modelo de uma arquitetura que roda por prompt, como a enxuta.
- `modelo_do_auditor() -> str` — O prompt modelo do auditor, com `{REPO}`, `{SPEC}`, `{RAMO}` e `{SONDAS}`.

### `ErroDaBancada` (GraphowError)

*serviço* — Os dados da bancada não servem para o que foi pedido.

### `ProjetoDaBancada`

*DTO imutável* — Uma demanda do laboratório: a pasta dela, o ramo de trabalho e a semente.

**Campos:** `nome: str`, `descricao: str`, `ramo: str`, `semente: Semente`, `pasta: Path`

- `spec() -> Path` `[property]` — O pedido, as perguntas do analista e as respostas do humano.
- `sondas() -> Path` `[property]` — Os casos que deram defeito numa das implementações, que o auditor confere em todas.
- `pasta_da_semente() -> Path` `[property]` — A árvore do commit inicial, sem `.git`.
- `texto_das_sondas() -> str` — A lista de sondas como entra no prompt do auditor, sem a quebra final.

### `Semente`

*DTO imutável* — O commit inicial do projeto no laboratório: o que o repositório da execução reproduz.

**Campos:** `commit: str`, `arvore: str`, `ramo: str`, `mensagem: str`, `autor: str`, `data: str`

- `nome_do_autor() -> str` `[property]` — O nome antes do e-mail em `Nome <email>`.
- `email_do_autor() -> str` `[property]` — O e-mail entre os sinais de `Nome <email>`.

### Funções do módulo

- `preencher_modelo(modelo: str, valores: Mapping[str, str]) -> str` — O modelo com cada `{NOME}` trocado pelo valor; marcador ou valor sobrando recusa.

## `bancada/semente.py`

O repositório de uma execução, recriado da semente com o mesmo hash do laboratório.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXECUTAVEL_DO_GIT` | `str` | `'git'` |
| `VARIAVEIS_DE_OUTRO_REPOSITORIO` | `frozenset[str]` | `frozenset({'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'})` |
| `CONFIGURACAO_DO_COMMIT_DA_SEMENTE` | `tuple[str, ...]` | `('-c', 'core.autocrlf=false', '-c', 'commit.gpgsign=false')` |

### `GitDaBancada`

*DTO imutável* — Roda o git num repositório da bancada, com ambiente próprio, e devolve a saída.

**Campos:** `repositorio: Path`, `ambiente: Mapping[str, str] | None`

- `rodar() -> str` — A saída padrão; `ErroDaBancada` com a saída de erro quando o git falha.

### Funções do módulo

- `criar_repositorio(projeto: ProjetoDaBancada, destino: Path) -> str` — Copia a semente para o destino, faz o commit inicial e devolve o hash dele, conferido.

## `bancada/transcricoes.py`

Os tokens de uma execução, somados das transcrições que o Claude Code grava em disco.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DE_PROJETOS_PADRAO` | `Path` | `Path.home() / '.claude' / 'projects'` |
| `EXTENSAO_DA_TRANSCRICAO` | `str` | `'.jsonl'` |
| `CHAVES_DE_USO` | `tuple[str, ...]` | `('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_cre…` |

### `TokensDasTranscricoes`

*DTO imutável* — Os tokens contados pela primeira entrada de cada mensagem (a medida) e pela última (a conferência).

**Campos:** `pela_primeira: int`, `pela_ultima: int`, `arquivos: int`

- `somar(outro: 'TokensDasTranscricoes') -> 'TokensDasTranscricoes'` — As duas contagens e os arquivos somados.

### Funções do módulo

- `localizar_transcricoes(raiz: Path, sessao: str) -> tuple[Path, ...]` — A transcrição da sessão e as dos subagentes dela, em qualquer pasta de projeto sob a raiz.
- `contar_tokens(arquivos: Iterable[Path], ate: datetime | None) -> TokensDasTranscricoes` — Os tokens das transcrições; com `ate`, só as mensagens até esse instante.

