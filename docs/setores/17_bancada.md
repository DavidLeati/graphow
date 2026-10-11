# Setor 17 — Bancada de Medição

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.bancada`

O portão de cada fase da reestruturação: as três demandas do laboratório rodadas do zero por arquitetura e auditadas do mesmo jeito. Lê os dados versionados em `bancada/` (semente, spec, sondas, prompts e linha de base) e recria o repositório de cada execução com o mesmo hash do laboratório. Não toca o banco do usuário: cada execução tem o seu.

## Inventário

3 módulos · 267 linhas · 5 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`bancada/projetos.py`](#bancadaprojetos) | 165 | Os dados versionados da bancada: projetos, prompts e linha de base, lidos de `bancada/`. |
| [`bancada/semente.py`](#bancadasemente) | 93 | O repositório de uma execução, recriado da semente com o mesmo hash do laboratório. |

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

