# Setor 13 — Harness de Avaliação

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.avaliacao`

Corpus de tarefas gravadas e medição de tokens por tarefa bem-sucedida, com e sem o recorte do grafo. Existe para que essa métrica tenha número em vez de afirmação.

## Inventário

11 módulos · 1694 linhas · 20 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`avaliacao/__init__.py`](#avaliacaoinit) | 47 | Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado. |
| [`avaliacao/cenario_entre_projetos.py`](#avaliacaocenarioentreprojetos) | 195 | Segundo projeto do corpus: mede se um aprendizado do primeiro chega a uma tarefa do segundo. |
| [`avaliacao/cenario_memoria.py`](#avaliacaocenariomemoria) | 126 | Extensão do cenário gravado com a camada de memória: a sessão encerrada e condensada. |
| [`avaliacao/entre_projetos.py`](#avaliacaoentreprojetos) | 160 | Braço entre projetos: um aprendizado do primeiro projeto chega à tarefa do segundo, e a que custo. |
| [`avaliacao/escala.py`](#avaliacaoescala) | 243 | Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado. |
| [`avaliacao/medicao.py`](#avaliacaomedicao) | 135 | Medição de tokens por tarefa, com e sem o recorte do grafo. |
| [`avaliacao/orquestracao.py`](#avaliacaoorquestracao) | 208 | Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo. |
| [`avaliacao/relatorio.py`](#avaliacaorelatorio) | 139 | Agregação e formatação do relatório de avaliação de tokens por tarefa. |
| [`avaliacao/relatorio_orquestracao.py`](#avaliacaorelatorioorquestracao) | 65 | O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração. |
| [`avaliacao/retomada.py`](#avaliacaoretomada) | 113 | Braço de retomada: quanto custa recuperar decisões e achados de uma sessão encerrada. |
| [`avaliacao/tarefas_gravadas.py`](#avaliacaotarefasgravadas) | 263 | Corpus de dez tarefas gravadas, com o grafo que as cerca. |

## `avaliacao/__init__.py`

Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado.

### Funções do módulo

- `executar_avaliacao() -> RelatorioDeAvaliacao` — Monta os cenários gravados, mede os três braços e consolida o relatório.

## `avaliacao/cenario_entre_projetos.py`

Segundo projeto do corpus: mede se um aprendizado do primeiro chega a uma tarefa do segundo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_PROJETO_SEGUNDO` | `str` | `'proj-segundo'` |
| `ID_SETOR_SEGUNDO` | `str` | `'setor-segundo'` |
| `ID_SESSAO_SEGUNDA` | `str` | `'sess-segunda'` |
| `ID_APRENDIZADO_GLOBAL` | `str` | `'apr-corte-por-secao'` |
| `ID_APRENDIZADO_LEXICO` | `str` | `'apr-eviccao-por-lru'` |
| `ID_APRENDIZADO_ISOLADO` | `str` | `'apr-posse-no-portao'` |
| `MECANISMO_NENHUM` | `str` | `'nenhum'` |
| `TAREFAS_ENTRE_PROJETOS` | `tuple[TarefaEntreProjetos, ...]` | `(TarefaEntreProjetos(id='t2-spans', titulo='Exportar os spans do kernel…` |
| `APRENDIZADOS_GRAVADOS` | `tuple[AprendizadoGravado, ...]` | `(AprendizadoGravado(id=ID_APRENDIZADO_GLOBAL, afirmacao='Nao corte a vi…` |

### `AprendizadoGravado`

*DTO imutável* — Um aprendizado do corpus: a afirmação, como aplicar, de onde saiu e onde vale.

**Campos:** `id: str`, `afirmacao: str`, `como_aplicar: str`, `id_origem: str`, `vale_para: str`, `global_: bool`

### `TarefaEntreProjetos`

*DTO imutável* — Uma tarefa do segundo projeto e o aprendizado do primeiro de que ela depende.

**Campos:** `id: str`, `titulo: str`, `descricao: str`, `id_aprendizado_esperado: str`, `mecanismo_esperado: str`

### Funções do módulo

- `montar_cenario_entre_projetos() -> WriteKernel` — O cenário com memória, mais os aprendizados promovidos e o segundo projeto.

## `avaliacao/cenario_memoria.py`

Extensão do cenário gravado com a camada de memória: a sessão encerrada e condensada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_NOTA_DE_CONDENSACAO` | `str` | `'nota-condensacao-sess-avaliacao'` |
| `AUTOR_HUMANO` | `str` | `'david'` |
| `AUTOR_REVISOR` | `str` | `'agente-revisor'` |
| `RESUMO_DECLARADO` | `str` | `'Nove das dez tarefas do kernel fechadas; o ciclo de vida pelos hooks f…` |
| `CORPO_DA_CONDENSACAO` | `str` | `'Decisoes vigentes: o item de patch e um dataclass frozen, porque o lot…` |

### Funções do módulo

- `montar_cenario_com_memoria() -> WriteKernel` — O cenário gravado, mais a sessão encerrada e a condensação escrita pelo revisor.
- `estender_com_memoria(kernel: WriteKernel) -> WriteKernel` — Encerra a sessão do corpus e grava a condensação que um revisor escreveria.
- `ids_de_conhecimento_do_corpus() -> tuple[str, ...]` — As decisões e evidências que o corpus gravou, na ordem das tarefas.

## `avaliacao/entre_projetos.py`

Braço entre projetos: um aprendizado do primeiro projeto chega à tarefa do segundo, e a que custo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_ENTRE_PROJETOS` | `int` | `1500` |
| `PROFUNDIDADE_MAXIMA` | `int` | `8` |

### `MedicaoEntreProjetos`

*DTO imutável* — Uma tarefa do segundo projeto: o aprendizado chegou, e a que custo em cada braço.

**Campos:** `id_tarefa: str`, `id_aprendizado_esperado: str`, `mecanismo_esperado: str`, `chegou: bool`, `tokens_pela_vista: int`, `tokens_despejo_do_primeiro_projeto: int`, `tokens_busca_cega: int`

### `MedidorEntreProjetos`

*serviço* — Mede, por tarefa do segundo projeto, a vista contra o despejo e a busca cega.

- `medir_todas(tarefas: Sequence[TarefaEntreProjetos]) -> RelatorioEntreProjetos` — Mede cada tarefa gravada do segundo projeto sobre a mesma projeção.

### `RelatorioEntreProjetos`

*DTO imutável* — As medições do braço e o índice semântico com que foram feitas.

**Campos:** `medicoes: tuple[MedicaoEntreProjetos, ...]`, `indice_semantico: str`

- `acertos() -> int` `[property]` — Quantas tarefas receberam o aprendizado de que dependiam.
- `taxa_de_acerto() -> float` `[property]` — Fração de tarefas atendidas, entre 0 e 1.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do braço, prontas para o console.

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

**Campos:** `total_nos: int`, `total_arestas: int`, `canvas: tuple[MedidaDeCanvas, ...]`, `tokens_da_varredura: int`, `tokens_do_caminho_guiado: int`, `passos_do_caminho_guiado: tuple[str, ...]`, `buscas: tuple[MedidaDeBusca, ...]`, `nos_orfaos: tuple[str, ...]`, `milissegundos_do_rollup: float`, `tokens_do_panorama_da_raiz: int`

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

## `avaliacao/orquestracao.py`

Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_CONFIGURACAO` | `str` | `'sem configuracao'` |
| `SEM_MODELO` | `str` | `'sem modelo'` |
| `AGENTE_ORQUESTRADOR` | `str` | `'orquestrador'` |
| `CAMPOS_DE_TOKENS` | `tuple[str, ...]` | `tuple(CHAVES_DE_USO.values())` |

### `MedicaoDeGoal`

*DTO imutável* — O que um Goal custou e rendeu sob a configuração com que foi orquestrado.

**Campos:** `id_goal: str`, `rotulo: str`, `configuracao: str`, `tarefas: int`, `concluidas: int`, `concluidas_sem_retrabalho: int`, `com_retrabalho: int`, `correcoes: int`, `rejeicoes: int`, `aprovacoes: int`, `modelos_por_tarefa: Mapping[str, int]`, `tokens_por_agente: Mapping[str, int]`, `runs_sem_tokens: int`

- `tokens() -> int` `[property]` — Todos os tokens atribuídos ao Goal, de todos os agentes.

### `MedidorDeOrquestracao`

*serviço* — Consulta pura sobre a projeção: nada é escrito, e o mesmo grafo dá sempre o mesmo número.

- `medir(ids_goals: Iterable[str]) -> tuple[MedicaoDeGoal, ...]` — Uma medição por Goal pedido; sem pedido, todo Goal que tem tarefas decompostas.

### `TrabalhoDoGoal`

*DTO imutável* — Os nós que pertencem ao Goal: tarefas, artefatos, vereditos e as sessões que os produziram.

**Campos:** `tarefas: tuple[NoGrafo, ...]`, `artefatos: frozenset[str]`, `vereditos: tuple[NoGrafo, ...]`, `sessoes: frozenset[str]`

- `ids_tarefas() -> frozenset[str]` `[property]` — Os ids das tarefas do Goal, correções incluídas.

## `avaliacao/relatorio.py`

Agregação e formatação do relatório de avaliação de tokens por tarefa.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITES_DECLARADOS` | `tuple[str, ...]` | `("O braco 'sem grafo' e o despejo do subgrafo da sessao, nao a saida de…` |

### `RelatorioDeAvaliacao`

*DTO imutável* — Consolidação das medições, com as médias de tokens por tarefa bem-sucedida.

**Campos:** `medicoes: tuple[MedicaoDaTarefa, ...]`, `calibracao: str`, `limites: tuple[str, ...]`, `retomada: MedicaoDeRetomada | None`, `entre_projetos: RelatorioEntreProjetos | None`

- `a_partir_de(medicoes: Sequence[MedicaoDaTarefa]) -> 'RelatorioDeAvaliacao'` — Monta o relatório registrando com que régua os tokens foram medidos.
- `bem_sucedidas() -> tuple[MedicaoDaTarefa, ...]` `[property]` — Somente as tarefas concluídas entram na métrica número um.
- `tokens_por_tarefa_bem_sucedida() -> float` `[property]` — Média de tokens de contexto por tarefa concluída, com o grafo.
- `tokens_por_tarefa_sem_grafo() -> float` `[property]` — Mesma média no braço sem divulgação progressiva.
- `intervencoes_por_tarefa() -> float` `[property]` — Média de respostas humanas exigidas por tarefa concluída.
- `reducao_media() -> float` `[property]` — Fração média de contexto poupada nas tarefas concluídas.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do relatório, prontas para o console.

## `avaliacao/relatorio_orquestracao.py`

O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_GOALS` | `str` | `'Nenhum Goal com tarefas decompostas: nada a medir.'` |

### Funções do módulo

- `formatar_relatorio(medicoes: Sequence[MedicaoDeGoal]) -> tuple[str, ...]` — As linhas do relatório: cada Goal medido e, no fim, a soma por configuração.

## `avaliacao/retomada.py`

Braço de retomada: quanto custa recuperar decisões e achados de uma sessão encerrada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_DA_RETOMADA` | `int` | `1500` |
| `PAPEL_DA_MEDICAO` | `PapelAutor` | `PapelAutor.PLANEJADOR` |
| `TIPOS_DE_CONHECIMENTO` | `frozenset[TipoNo]` | `frozenset({TipoNo.DECISION, TipoNo.EVIDENCE})` |

### `MedicaoDeRetomada`

*DTO imutável* — Custo de retomar uma sessão encerrada, pela abertura da vista e nó a nó.

**Campos:** `id_sessao: str`, `tokens_pela_vista: int`, `tokens_no_a_no: int`, `nos_lidos_um_a_um: int`, `decisoes_vigentes: int`, `decisoes_entregues: int`, `condensacao_entregue: bool`

- `reducao() -> float` `[property]` — Fração do contexto poupada pela abertura da vista, entre 0 e 1.
- `cobertura_completa() -> bool` `[property]` — A abertura só vale o que economiza se entregar toda decisão vigente e a condensação.

### `MedidorDeRetomada`

*serviço* — Compara a abertura da vista da sessão encerrada com a leitura nó a nó.

- `medir(id_sessao: str, orcamento: int) -> MedicaoDeRetomada` — Mede os dois braços sobre a mesma projeção.

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

