# Setor 04 — Projeção Determinística

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.projection`

Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.

## Inventário

6 módulos · 632 linhas · 9 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`projection/acumulador.py`](#projectionacumulador) | 170 | Acumulador mutável usado para dobrar muitos eventos em uma passada só. |
| [`projection/fila_trabalho.py`](#projectionfilatrabalho) | 218 | Fila de trabalho: quais tarefas de uma sessão estão de fato executáveis agora. |
| [`projection/graph_view.py`](#projectiongraphview) | 129 | Camada de consulta e visualização imutável do grafo projetado (CQRS). |
| [`projection/projecao_sincronizada.py`](#projectionprojecaosincronizada) | 75 | Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno. |
| [`projection/reducer.py`](#projectionreducer) | 34 | Redutor determinístico de eventos append-only para estado de grafo em memória. |

## `projection/acumulador.py`

Acumulador mutável usado para dobrar muitos eventos em uma passada só.

### `AcumuladorProjecao`

*serviço* — Estrutura interna e mutável que aplica eventos sem recriar o estado a cada um.

- `aplicar_todos(eventos: Sequence[EventoLog]) -> None` — Dobra a sequência inteira de eventos sobre o acumulador.
- `aplicar(evento: EventoLog) -> None` — Aplica um evento, delegando ao manipulador do seu tipo.
- `congelar() -> GrafoEstado` — Produz o estado imutável correspondente ao acumulado até aqui.

## `projection/fila_trabalho.py`

Fila de trabalho: quais tarefas de uma sessão estão de fato executáveis agora.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PROFUNDIDADE_MAXIMA_DA_SESSAO` | `int` | `32` |
| `ARESTAS_DE_ALCANCE` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ, TipoAresta.DECOMPOE})` |
| `STATUS_FORA_DA_FILA` | `frozenset[str]` | `frozenset({StatusTask.CONCLUIDO.value, StatusTask.BLOQUEADO.value})` |
| `PRIORIDADE_POR_STATUS` | `Mapping[str, int]` | `{StatusTask.PRONTO_PARA_REVISAO.value: 0, StatusTask.EM_ANDAMENTO.value…` |
| `PRIORIDADE_DE_STATUS_DESCONHECIDO` | `int` | `9` |

### `FilaDeTrabalho`

*serviço* — Consulta pura que ordena as tarefas prontas para execução em uma sessão.

- `proximas_tarefas(id_sessao: str) -> tuple[TarefaExecutavel, ...]` — Tarefas da sessão com dependências cumpridas, sem dúvida aberta e sem posse.
- `tarefas_impedidas(id_sessao: str) -> tuple[TarefaImpedida, ...]` — Tarefas da sessão que não entraram na fila, cada uma com o seu motivo.

### `MotivoDeImpedimento` (str, Enum)

*serviço* — Por que uma tarefa da sessão não está disponível agora.

### `TarefaExecutavel`

*DTO imutável* — Tarefa liberada para trabalho, com o que o agente precisa para decidir.

**Campos:** `id: str`, `rotulo: str`, `status: str`, `criterio_pronto: str`, `depende_de: tuple[str, ...]`

- `em_dicionario() -> dict[str, object]` — Forma serializável para a resposta da ferramenta MCP.

### `TarefaImpedida`

*DTO imutável* — Tarefa fora da fila, com o motivo que a mantém de fora.

**Campos:** `id: str`, `rotulo: str`, `status: str`, `motivo: MotivoDeImpedimento`

- `em_dicionario() -> dict[str, object]` — Forma serializável para a resposta da ferramenta MCP.

## `projection/graph_view.py`

Camada de consulta e visualização imutável do grafo projetado (CQRS).

### `GrafoView`

*serviço* — Consultas somente-leitura sobre o estado projetado do grafo em memória.

- `versao_log() -> int` `[property]` — Versão atual do log refletida na projeção.
- `total_nos() -> int` `[property]` — Total de nós presentes na projeção.
- `total_arestas() -> int` `[property]` — Total de arestas presentes na projeção.
- `contem_no(id_no: str) -> bool` — Verifica se um nó está presente na projeção.
- `contem_aresta(id_aresta: str) -> bool` — Verifica se uma aresta está presente na projeção.
- `obter_no(id_no: str) -> NoGrafo | None` — Retorna o nó pelo seu ID ou None caso não exista.
- `obter_aresta(id_aresta: str) -> ArestaGrafo | None` — Retorna a aresta pelo ID ou None caso não exista.
- `listar_todos_os_nos() -> tuple[NoGrafo, ...]` — Enumera todos os nós da projeção, evitando acesso ao estado interno.
- `listar_todas_as_arestas() -> tuple[ArestaGrafo, ...]` — Enumera todas as arestas da projeção, evitando acesso ao estado interno.
- `listar_nos_por_tipo(tipo: TipoNo) -> list[NoGrafo]` — Filtra todos os nós de um determinado tipo da ontologia.
- `obter_arestas_saida(origem_id: str, tipo_aresta: TipoAresta | None) -> list[ArestaGrafo]` — Lista arestas partindo do nó de origem informado.
- `obter_arestas_entrada(destino_id: str, tipo_aresta: TipoAresta | None) -> list[ArestaGrafo]` — Lista arestas incidindo no nó de destino informado.
- `obter_vizinhos_1_salto(id_no: str) -> list[NoGrafo]` — Coleta nós vizinhos conectados diretamente em 1 salto (entrada ou saída).
- `buscar_nos(termo: str, tipos: Sequence[TipoNo] | None) -> list[NoGrafo]` — Busca textual sobre rótulo e propriedades de nós filtrados por tipos.
- `obter_questoes_bloqueantes(id_task: str) -> list[NoGrafo]` — Retorna nós do tipo Question com aresta 'bloqueia' aberta para a Task.
- `esta_bloqueada(id_task: str) -> bool` — Determina se uma Task possui alguma questão aberta bloqueante.

## `projection/projecao_sincronizada.py`

Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno.

### `ProjecaoDoRamo`

*DTO imutável* — Estado projetado de um ramo junto da marca d'água já aplicada.

**Campos:** `estado: GrafoEstado`, `ultimo_seq_aplicado: int`

### `ProjecaoSincronizada`

*serviço* — Mantém projeções por ramo alinhadas ao log, aplicando apenas o delta pendente.

- `obter_estado(ramo_id: str) -> GrafoEstado` — Consulta o estado do ramo já reconciliado com tudo que há no log.
- `sincronizar(ramo_id: str) -> ProjecaoDoRamo` — Aplica os eventos surgidos desde a última leitura e devolve a projeção.
- `registrar_estado_recem_commitado(ramo_id: str, projecao: ProjecaoDoRamo) -> None` — Adota a projeção calculada pelo próprio kernel logo após o commit.
- `descartar(ramo_id: str) -> None` — Esquece a projeção do ramo, forçando reconstrução na próxima consulta.

## `projection/reducer.py`

Redutor determinístico de eventos append-only para estado de grafo em memória.

### `GrafoReducer`

*serviço* — Funções puras para projetar eventos ordenados em instâncias imutáveis de GrafoEstado.

- `reconstruir(eventos: Sequence[EventoLog]) -> GrafoEstado` — Reconstrói o estado integral do grafo a partir de uma sequência de eventos.
- `aplicar_eventos(estado_base: GrafoEstado, eventos: Sequence[EventoLog]) -> GrafoEstado` — Dobra a sequência sobre o estado base em uma passada, sem cópias intermediárias.
- `reduzir(estado: GrafoEstado, evento: EventoLog) -> GrafoEstado` — Aplica um único evento de forma pura sobre o estado atual.

