# Setor 13 — Harness de Avaliação

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.avaliacao`

Corpus de tarefas gravadas e medição de tokens por tarefa bem-sucedida, com e sem o recorte do grafo. Existe para que a métrica principal do plano tenha número em vez de afirmação.

## Inventário

4 módulos · 517 linhas · 6 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`avaliacao/__init__.py`](#avaliacaoinit) | 26 | Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado. |
| [`avaliacao/medicao.py`](#avaliacaomedicao) | 135 | Medição de tokens por tarefa, com e sem o recorte do grafo. |
| [`avaliacao/relatorio.py`](#avaliacaorelatorio) | 95 | Agregação e formatação do relatório de avaliação de tokens por tarefa. |
| [`avaliacao/tarefas_gravadas.py`](#avaliacaotarefasgravadas) | 261 | Corpus de dez tarefas gravadas, com o grafo que as cerca. |

## `avaliacao/__init__.py`

Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado.

### Funções do módulo

- `executar_avaliacao() -> RelatorioDeAvaliacao` — Monta o cenário gravado, mede as dez tarefas e consolida o relatório.

## `avaliacao/medicao.py`

Medição de tokens por tarefa, com e sem o recorte do grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_ALCANCE_DA_SESSAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ, TipoAresta.DECOMPOE, TipoAresta.CONTEM})` |
| `PROFUNDIDADE_MAXIMA` | `int` | `8` |

### `MedicaoDaTarefa`

*DTO imutável* — Custo de contexto e esforço humano de uma tarefa gravada.

**Campos:** `id_tarefa: str`, `tokens_com_grafo: int`, `tokens_sem_grafo: int`, `intervencoes_humanas: int`, `concluida: bool`

- `reducao() -> float` `[property]` — Fração do contexto poupada pelo recorte, entre 0 e 1.

### `MedidorDeTarefas`

*serviço* — Executa a medição das dez tarefas gravadas sobre um cenário montado.

- `medir_todas() -> tuple[MedicaoDaTarefa, ...]` — Mede cada tarefa do corpus contra o mesmo cenário gravado.

## `avaliacao/relatorio.py`

Agregação e formatação do relatório de avaliação de tokens por tarefa.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITES_DECLARADOS` | `tuple[str, ...]` | `("O braco 'sem grafo' e o despejo do subgrafo da sessao, nao a saida de…` |

### `RelatorioDeAvaliacao`

*DTO imutável* — Consolidação das medições, com as médias que o plano pede na Fase 3.

**Campos:** `medicoes: tuple[MedicaoDaTarefa, ...]`, `calibracao: str`, `limites: tuple[str, ...]`

- `a_partir_de(medicoes: Sequence[MedicaoDaTarefa]) -> 'RelatorioDeAvaliacao'` — Monta o relatório registrando com que régua os tokens foram medidos.
- `bem_sucedidas() -> tuple[MedicaoDaTarefa, ...]` `[property]` — Somente as tarefas concluídas entram na métrica número um.
- `tokens_por_tarefa_bem_sucedida() -> float` `[property]` — Média de tokens de contexto por tarefa concluída, com o grafo.
- `tokens_por_tarefa_sem_grafo() -> float` `[property]` — Mesma média no braço sem divulgação progressiva.
- `intervencoes_por_tarefa() -> float` `[property]` — Média de respostas humanas exigidas por tarefa concluída.
- `reducao_media() -> float` `[property]` — Fração média de contexto poupada nas tarefas concluídas.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do relatório, prontas para o console.

## `avaliacao/tarefas_gravadas.py`

Corpus de dez tarefas gravadas, com o grafo que as cerca.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_PROJETO` | `str` | `'proj-avaliacao'` |
| `ID_SETOR` | `str` | `'setor-engenharia'` |
| `ID_SESSAO` | `str` | `'sess-avaliacao'` |
| `ID_GOAL` | `str` | `'goal-substrato'` |
| `ORCAMENTO_PADRAO_DA_MEDICAO` | `int` | `1500` |
| `TAREFAS_GRAVADAS` | `tuple[TarefaGravada, ...]` | `(TarefaGravada(id='t01-parser', titulo='Escrever o parser de JSON Patch…` |

### `DescricaoDeNo`

*DTO imutável* — Rótulo e propriedades de um nó a criar, agrupados para caber na assinatura.

**Campos:** `rotulo: str`, `propriedades: Mapping[str, str]`

### `Ligacao`

*DTO imutável* — As duas pontas e o tipo de uma aresta a criar.

**Campos:** `origem: str`, `destino: str`, `tipo: TipoAresta`

### `TarefaGravada`

*DTO imutável* — Uma tarefa do corpus, com o que basta para medi-la de forma repetível.

**Campos:** `id: str`, `titulo: str`, `criterio_pronto: str`, `papel: PapelAutor`, `concluida: bool`, `depende_de: str`, `pergunta_escalada: str`, `orcamento_tokens: int`, `decisoes: tuple[str, ...]`, `evidencias: tuple[str, ...]`

- `id_questao() -> str` `[property]` — Identificador da Question de escalação desta tarefa, se houver.

### Funções do módulo

- `montar_cenario_gravado() -> WriteKernel` — Reconstrói o grafo das dez tarefas sempre da mesma forma, do zero.

