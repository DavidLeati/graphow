# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

5 módulos · 692 linhas · 13 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 115 | Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem. |
| [`orquestrador/git_do_goal.py`](#orquestradorgitdogoal) | 228 | O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração. |
| [`orquestrador/saidas.py`](#orquestradorsaidas) | 256 | A saída de cada papel como objeto tipado, com a conferência que o schema não faz. |
| [`orquestrador/validacao_json.py`](#orquestradorvalidacaojson) | 81 | Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam. |

## `orquestrador/esquemas.py`

Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEL_PLANEJADOR` | `str` | `'planejador'` |
| `PAPEL_EXECUTOR` | `str` | `'executor'` |
| `PAPEL_VERIFICADOR` | `str` | `'verificador'` |
| `PAPEIS` | `tuple[str, ...]` | `(PAPEL_PLANEJADOR, PAPEL_EXECUTOR, PAPEL_VERIFICADOR)` |
| `PASTA_DOS_PROMPTS` | `Path` | `Path(__file__).parent / 'prompts'` |
| `LIMITE_DO_PROMPT_BYTES` | `int` | `5 * 1024` |
| `VERIFICACOES_DE_CRITERIO` | `tuple[str, ...]` | `('teste', 'checagem')` |
| `MODELOS_SUGERIDOS` | `tuple[str, ...]` | `('opus', 'sonnet', 'haiku')` |
| `STATUS_DO_EXECUTOR` | `tuple[str, ...]` | `('pronto', 'duvida', 'falhou')` |
| `VEREDITOS_DE_CRITERIO` | `tuple[str, ...]` | `('atende', 'parcial', 'nao_atende')` |
| `GRAVIDADES` | `tuple[str, ...]` | `('bloqueante', 'acompanhamento')` |
| `TEXTO` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': 1}` |
| `TEXTO_LIVRE` | `Mapping[str, Any]` | `{'type': 'string'}` |
| `LISTA_DE_TEXTOS` | `Mapping[str, Any]` | `{'type': 'array', 'items': {'type': 'string'}}` |
| `CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'verificacao': {'type': 'string',…` |
| `DECISAO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'motivo': TEXTO})` |
| `FATIA` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'objetivo': TEXTO, 'criterios': …` |
| `ESQUEMA_DO_PLANO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'comando_suite': TEXTO, 'criterios': _lista_d…` |
| `ESQUEMA_DA_EXECUCAO` | `dict[str, Any]` | `_objeto({'status': {'type': 'string', 'enum': list(STATUS_DO_EXECUTOR)}…` |
| `PARECER` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'veredito': {'type': 'string', 'enum': list(VERED…` |
| `ACHADO` | `dict[str, Any]` | `_objeto({'gravidade': {'type': 'string', 'enum': list(GRAVIDADES)}, 'ti…` |
| `ESQUEMA_DA_VERIFICACAO` | `dict[str, Any]` | `_objeto({'resumo': TEXTO, 'criterios': _lista_de(PARECER, 1), 'decisoes…` |
| `ESQUEMA_POR_PAPEL` | `Mapping[str, Mapping[str, Any]]` | `{PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO, PAPEL_EXECUTOR: ESQUEMA_DA_EXECUCA…` |

### Funções do módulo

- `caminho_do_prompt(papel: str) -> Path` — O prompt de sistema do papel, no pacote.

## `orquestrador/git_do_goal.py`

O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXECUTAVEL_DO_GIT` | `str` | `'git'` |
| `VARIAVEIS_DE_OUTRO_REPOSITORIO` | `frozenset[str]` | `frozenset({'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'})` |
| `NOME_DO_HOOK_DA_TRAVA` | `str` | `'reference-transaction'` |
| `HOOK_DA_TRAVA` | `str` | `'#!/bin/sh\n# Trava do graphow orquestrar: a sessao do agente nao atual…` |
| `IDENTIDADE_DE_RESERVA` | `tuple[str, ...]` | `('-c', 'user.name=graphow orquestrar', '-c', 'user.email=orquestrador@g…` |
| `LIMITE_DO_RESUMO_DO_DIFF` | `int` | `4000` |

### `AreaDoGoal`

*DTO imutável* — Onde o trabalho do Goal acontece: o repositório do humano, o worktree, a branch e a base.

**Campos:** `repositorio: Path`, `pasta: Path`, `ramo: str`, `base: str`

### `FalhaDoGitDoGoal` (GraphowError)

*serviço* — O git recusou o que o orquestrador pediu; o contexto traz o comando e a saída de erro.

### `GitDoGoal`

*DTO imutável* — Roda o git numa pasta (o repositório do humano ou a área do Goal), sem a trava do agente.

**Campos:** `pasta: Path`

- `tentar() -> SaidaDoGit` — O comando, sem recusar quando o git sai com erro.
- `rodar() -> str` — A saída padrão; recusa com a saída de erro quando o git falha.
- `head() -> str` — O commit em que a pasta está.
- `ramo_atual() -> str` — A branch do HEAD; vazio com o HEAD destacado.
- `ramo_existe(ramo: str) -> bool` — A branch local existe.
- `mudancas() -> tuple[str, ...]` — As linhas do `status --porcelain`: o que está fora de commit, ignorados de fora.
- `e_ancestral(antes: str, depois: str) -> bool` — `antes` está na história de `depois` (ou é ele).
- `arquivos_entre(antes: str, depois: str) -> tuple[str, ...]` — Os arquivos que mudaram de um commit ao outro.
- `resumo_do_diff(antes: str, depois: str) -> str` — O `diff --stat` entre os dois commits, cortado para caber no briefing.
- `commits_desde(base: str) -> tuple[str, ...]` — Hash curto e assunto de cada commit da branch desde a base, do mais antigo ao mais novo.

### `SaidaDoGit`

*DTO imutável* — O código de saída e as duas saídas de um comando do git.

**Campos:** `codigo: int`, `saida: str`, `erro: str`

### Funções do módulo

- `raiz_do_repositorio(pasta: Path) -> Path` — A raiz do repositório git que contém a pasta.
- `preparar_area(area: AreaDoGoal) -> None` — O worktree do Goal na branch dele: reaproveitado se já existe, criado da base se a branch é nova.
- `commitar(area: Path, mensagem: str) -> str` — Tudo o que mudou na área num commit do orquestrador; devolve o hash.
- `descartar_mudancas(area: Path, arquivo_patch: Path) -> bool` — Guarda o que está fora de commit num .patch e volta a área ao HEAD; diz se havia o que guardar.
- `restaurar_head(area: Path, ramo: str, esperado: str) -> str` — Desfaz o que o agente fez no git: volta à branch e, com `reset --soft`, ao commit esperado.
- `integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str` — Avança a base até a branch do Goal, só por fast-forward; devolve o commit integrado.
- `remover_area(repositorio: Path, area: Path) -> bool` — Tira o worktree do Goal depois da integração; a branch fica. Diz se conseguiu.
- `instalar_trava(pasta: Path) -> dict[str, str]` — Grava o hook da trava na pasta e devolve o ambiente que a liga numa sessão de agente.
- `regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]` — As regras `--disallowedTools` de git de escrita, para cada ferramenta de shell dada.

## `orquestrador/saidas.py`

A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VEREDITO_QUE_ATENDE` | `str` | `'atende'` |
| `GRAVIDADE_BLOQUEANTE` | `str` | `'bloqueante'` |
| `GRAVIDADE_ACOMPANHAMENTO` | `str` | `'acompanhamento'` |
| `STATUS_DUVIDA` | `str` | `'duvida'` |

### `Achado`

*DTO imutável* — Um problema que o verificador achou, com a gravidade e o que ele fere.

**Campos:** `gravidade: str`, `titulo: str`, `descricao: str`, `local: str`, `criterios: tuple[str, ...]`

- `em_json() -> dict[str, Any]` — O achado para gravar na Evidence.

### `Criterio`

*DTO imutável* — Um critério de aceite: id (C1...), texto completo e como se prova.

**Campos:** `id: str`, `texto: str`, `verificacao: str`

### `Decisao`

*DTO imutável* — Uma decisão que o trabalho segue, com o motivo.

**Campos:** `id: str`, `texto: str`, `motivo: str`

### `Fatia`

*DTO imutável* — Uma fatia vertical do plano: o que entrega, que critérios cobre, onde mexe e de que depende.

**Campos:** `id: str`, `titulo: str`, `objetivo: str`, `criterios: tuple[str, ...]`, `arquivos: tuple[str, ...]`, `depende_de: tuple[str, ...]`, `modelo: str`

- `de_json(dados: Mapping[str, Any]) -> 'Fatia'` — A fatia como o planejador a devolveu.

### `IdsFixados`

*DTO imutável* — Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id.

**Campos:** `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`

### `Parecer`

*DTO imutável* — O veredito do verificador sobre um critério ou uma decisão, com a prova.

**Campos:** `id: str`, `veredito: str`, `prova: str`

### `Plano`

*DTO imutável* — O plano do Goal: título, comando da suíte, critérios, decisões e fatias.

**Campos:** `titulo: str`, `comando_suite: str`, `criterios: tuple[Criterio, ...]`, `decisoes: tuple[Decisao, ...]`, `fatias: tuple[Fatia, ...]`, `fora_do_escopo: tuple[str, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Plano'` — O plano como o planejador o devolveu, já conferido pelo schema.

### `SaidaDoExecutor`

*DTO imutável* — O que o executor devolveu da fatia.

**Campos:** `status: str`, `resumo: str`, `arquivos: tuple[str, ...]`, `testes: tuple[str, ...]`, `duvida: str`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoExecutor'` — A saída como o executor a devolveu.
- `conferir() -> tuple[str, ...]` — A dúvida precisa da pergunta.

### `Verificacao`

*DTO imutável* — O que o verificador devolveu do Goal inteiro.

**Campos:** `resumo: str`, `criterios: tuple[Parecer, ...]`, `decisoes: tuple[Parecer, ...]`, `achados: tuple[Achado, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Verificacao'` — A verificação como o verificador a devolveu.
- `bloqueantes() -> tuple[Achado, ...]` — Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum cita, um sintético.
- `acompanhamentos() -> tuple[Achado, ...]` — Os achados que não ferem critério nem decisão.

### Funções do módulo

- `conferir_plano(plano: Plano, fixados: IdsFixados) -> tuple[str, ...]` — Os problemas de sentido do plano; vazio quando ele pode ser gravado.
- `conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]` — Um parecer por critério e por decisão do plano, e achado que cita só o que existe.

## `orquestrador/validacao_json.py`

Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DO_JSON` | `Mapping[str, tuple[type, ...]]` | `{'object': (dict,), 'array': (list,), 'string': (str,), 'integer': (int…` |

### Funções do módulo

- `validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str) -> tuple[str, ...]` — Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere.

