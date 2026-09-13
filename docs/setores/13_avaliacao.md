# Setor 13 — Harness de Avaliação

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.avaliacao`

Corpus de tarefas gravadas e medição de tokens por tarefa bem-sucedida, com e sem o recorte do grafo. Existe para que essa métrica tenha número em vez de afirmação.

## Inventário

5 módulos · 745 linhas · 10 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`avaliacao/__init__.py`](#avaliacaoinit) | 30 | Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado. |
| [`avaliacao/escala.py`](#avaliacaoescala) | 225 | Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado. |
| [`avaliacao/medicao.py`](#avaliacaomedicao) | 135 | Medição de tokens por tarefa, com e sem o recorte do grafo. |
| [`avaliacao/relatorio.py`](#avaliacaorelatorio) | 94 | Agregação e formatação do relatório de avaliação de tokens por tarefa. |
| [`avaliacao/tarefas_gravadas.py`](#avaliacaotarefasgravadas) | 261 | Corpus de dez tarefas gravadas, com o grafo que as cerca. |

## `avaliacao/__init__.py`

Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado.

### Funções do módulo

- `executar_avaliacao() -> RelatorioDeAvaliacao` — Monta o cenário gravado, mede as dez tarefas e consolida o relatório.

## `avaliacao/escala.py`

Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_DA_MEDICAO` | `int` | `1500` |
| `PROFUNDIDADE_MAXIMA_DA_DESCIDA` | `int` | `8` |
| `TERMOS_DE_SONDAGEM` | `tuple[str, ...]` | `('dados', 'modelo', 'a')` |
| `TIPOS_DE_CONTAINER` | `tuple[TipoNo, ...]` | `(TipoNo.PROJETO, TipoNo.SETOR, TipoNo.SESSAO)` |

### `MedidaDeBusca`

*DTO imutável* — Custo de uma busca, com e sem o limite de resultados.

**Campos:** `termo: str`, `total_encontrado: int`, `tokens_sem_limite: int`, `tokens_com_limite: int`

### `MedidaDeCanvas`

*DTO imutável* — Peso do payload do canvas sob um recorte.

**Campos:** `rotulo: str`, `nos: int`, `kilobytes: float`

### `MedidorDeEscala`

*serviço* — Roda as três medidas sobre a projeção do ramo informado.

- `medir(ramo_id: str) -> RelatorioDeEscala` — Consolida o relatório de escala do ramo.

### `RelatorioDeEscala`

*DTO imutável* — Consolidação das três medidas que decidem se o grafo ainda cabe.

**Campos:** `total_nos: int`, `total_arestas: int`, `canvas: tuple[MedidaDeCanvas, ...]`, `tokens_da_varredura: int`, `tokens_do_caminho_guiado: int`, `passos_do_caminho_guiado: tuple[str, ...]`, `buscas: tuple[MedidaDeBusca, ...]`, `nos_orfaos: tuple[str, ...]`

- `fator_de_reducao_da_navegacao() -> float` `[property]` — Quantas vezes o caminho guiado é mais barato que a varredura cega.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do relatório, prontas para o console.

### Funções do módulo

- `medir_escala(kernel: WriteKernel, ramo_id: str) -> RelatorioDeEscala` — Ponto de entrada da medição de escala sobre um kernel já montado.

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

*DTO imutável* — Consolidação das medições, com as médias de tokens por tarefa bem-sucedida.

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

