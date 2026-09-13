# Setor 07 — Linhagem e Ramificação

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.lineage`

Rastreio causal reverso até o Goal raiz, replay pontual com instantâneos e forks registrados como ponteiro para o ponto de corte.

## Inventário

4 módulos · 292 linhas · 7 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`lineage/fork_manager.py`](#lineageforkmanager) | 80 | Gerenciador de ramificações (Forks) sem cópia de prefixo de eventos. |
| [`lineage/lineage_tracer.py`](#lineagelineagetracer) | 101 | Rastreamento de linhagem reversa de artefatos até objetivos raiz (Goals). |
| [`lineage/replay_engine.py`](#lineagereplayengine) | 104 | Motor de Replay determinístico e cálculo de Diff entre ramificações. |

## `lineage/fork_manager.py`

Gerenciador de ramificações (Forks) sem cópia de prefixo de eventos.

### `ForkManager`

*serviço* — Permite bifurcar o estado do grafo em qualquer ponto histórico de evento.

- `criar_fork(pedido: PedidoFork) -> str` — Registra o ponteiro do novo ramo e marca a bifurcação no próprio log dele.
- `obter_estado_fork(ramo_id: str) -> GrafoEstado` — Reconstrói a projeção do ramo bifurcado, herança inclusa.

### `PedidoFork`

*DTO imutável* — Parâmetros imutáveis de criação de uma ramificação.

**Campos:** `ramo_origem: str`, `id_evento_corte: str`, `novo_ramo_id: str`, `autor: str`

## `lineage/lineage_tracer.py`

Rastreamento de linhagem reversa de artefatos até objetivos raiz (Goals).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DE_ARESTA_ASCENDENTE_POR_SAIDA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DERIVA_DE, TipoAresta.SUBSTITUI, TipoAresta.JUSTI…` |

### `CaminhoLinhagem`

*DTO imutável* — Representação imutável da cadeia de proveniência de um artefato.

**Campos:** `id_alvo: str`, `passos: tuple[str, ...]`, `nos_cadeia: tuple[NoGrafo, ...]`, `goal_raiz: NoGrafo | None`

### `LineageTracer`

*serviço* — Localiza a trilha causal completa de um nó folha até o Goal raiz.

- `rastrear_linhagem(id_no_alvo: str, view: GrafoView) -> CaminhoLinhagem` — Sobe a hierarquia de arestas partindo do nó alvo até encontrar o Goal correspondente.

## `lineage/replay_engine.py`

Motor de Replay determinístico e cálculo de Diff entre ramificações.

### `DiferencaEstrutural`

*DTO imutável* — Comparação imutável entre dois estados projetados.

**Campos:** `nos_adicionados: tuple[str, ...]`, `nos_removidos: tuple[str, ...]`, `nos_comuns: tuple[str, ...]`, `arestas_adicionadas: tuple[str, ...]`, `arestas_removidas: tuple[str, ...]`

- `como_dicionario() -> dict[str, list[str]]` — Representação serializável para as camadas REST e de linha de comando.

### `InstantaneoRamo`

*DTO imutável* — Estado já reconstruído de um ramo até determinada sequência.

**Campos:** `ramo_id: str`, `seq: int`, `estado: GrafoEstado`

### `ReplayEngine`

*serviço* — Motor para reconstrução pontual e comparação de linhagem de grafos.

- `reproduzir_ate_seq(ramo_id: str, seq_limite: int) -> GrafoEstado` — Recria o estado exato do grafo na sequência especificada.
- `reproduzir_ate_timestamp(ramo_id: str, timestamp_utc: str) -> GrafoEstado` — Recria o estado exato do grafo até o momento temporal informado.
- `calcular_diff(estado_a: GrafoEstado, estado_b: GrafoEstado) -> dict[str, list[str]]` — Calcula diferenças estruturais entre dois estados (ex: comparação de forks).
- `comparar(estado_a: GrafoEstado, estado_b: GrafoEstado) -> DiferencaEstrutural` — Compara dois estados projetados devolvendo o resultado tipado.

