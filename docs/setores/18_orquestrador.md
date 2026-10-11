# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

4 módulos · 464 linhas · 9 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 115 | Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem. |
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

