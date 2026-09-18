# Setor 04 — Projeção Determinística

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.projection`

Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.

## Inventário

11 módulos · 1672 linhas · 21 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`projection/acumulador.py`](#projectionacumulador) | 219 | Acumulador mutável usado para dobrar muitos eventos em uma passada só. |
| [`projection/caminho_critico.py`](#projectioncaminhocritico) | 178 | Caminho crítico: quem trava quem, e quanto cada gargalo destrava. |
| [`projection/fechamento.py`](#projectionfechamento) | 119 | Fechamento determinístico de uma subárvore: o que vigora, o que segue aberto, o último artefato. |
| [`projection/fila_trabalho.py`](#projectionfilatrabalho) | 218 | Fila de trabalho: quais tarefas de uma sessão estão de fato executáveis agora. |
| [`projection/graph_view.py`](#projectiongraphview) | 193 | Camada de consulta e visualização imutável do grafo projetado (CQRS). |
| [`projection/projecao_sincronizada.py`](#projectionprojecaosincronizada) | 100 | Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno. |
| [`projection/ranking_busca.py`](#projectionrankingbusca) | 186 | Ordenação e corte dos resultados de busca textual no grafo. |
| [`projection/reducer.py`](#projectionreducer) | 34 | Redutor determinístico de eventos append-only para estado de grafo em memória. |
| [`projection/rollup.py`](#projectionrollup) | 250 | Resumo agregado de cada subárvore de contenção, calculado uma vez por commit. |
| [`projection/working_set.py`](#projectionworkingset) | 169 | Escopo ativo: o que está perto do trabalho que ainda não terminou. |

## `projection/acumulador.py`

Acumulador mutável usado para dobrar muitos eventos em uma passada só.

### `AcumuladorProjecao`

*serviço* — Estrutura interna e mutável que aplica eventos sem recriar o estado a cada um.

- `aplicar_todos(eventos: Sequence[EventoLog]) -> None` — Dobra a sequência inteira de eventos sobre o acumulador.
- `aplicar(evento: EventoLog) -> None` — Aplica um evento, delegando ao manipulador do seu tipo.
- `congelar() -> GrafoEstado` — Produz o estado imutável correspondente ao acumulado até aqui.

### Funções do módulo

- `metadados_do_evento(evento: EventoLog) -> MetadadosTemporais` — Marca temporal do nó tirada do log, nunca do relógio de quem projeta.
- `ordem_do_evento(evento: EventoLog) -> OrdemNoLog` — Posição de nascimento do nó na ordem total do log.
- `marca_da_aresta(evento: EventoLog) -> MetadadosTemporais` — Marca temporal da aresta, tirada do log pelo mesmo motivo que a do nó.

## `projection/caminho_critico.py`

Caminho crítico: quem trava quem, e quanto cada gargalo destrava.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_DEPENDENCIA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DEPENDE_DE, TipoAresta.BLOQUEIA})` |
| `PROFUNDIDADE_MAXIMA` | `int` | `32` |

### `CalculadoraDeCaminhoCritico`

*serviço* — Extrai o subgrafo de dependências e mede o alcance de cada gargalo.

- `calcular() -> CaminhoCritico` — Monta o caminho com os nós participantes e os gargalos ordenados.

### `CaminhoCritico`

*DTO imutável* — Subgrafo de dependências e os gargalos que o ordenam.

**Campos:** `ids: frozenset[str]`, `gargalos: tuple[Gargalo, ...]`, `total_de_arestas_de_dependencia: int`, `tarefas_sem_dependencia_declarada: tuple[str, ...]`

- `esta_vazio() -> bool` `[property]` — Sem aresta de dependência não há caminho crítico a mostrar.
- `contem(id_no: str) -> bool` — Indica se o nó participa de alguma relação de dependência.
- `em_dicionario() -> dict[str, object]` — Resumo serializável, com o que a interface precisa para se explicar.

### `Gargalo`

*DTO imutável* — Um nó que trava outros, com o tamanho do que ele segura.

**Campos:** `id: str`, `rotulo: str`, `tipo: str`, `status: str`, `desbloqueia_diretamente: int`, `desbloqueia_no_total: int`

- `em_dicionario() -> dict[str, object]` — Forma serializável para a resposta REST e para a ferramenta MCP.

## `projection/fechamento.py`

Fechamento determinístico de uma subárvore: o que vigora, o que segue aberto, o último artefato.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_IDS_POR_LINHA` | `int` | `5` |

### `FechamentoDeSubarvore`

*DTO imutável* — Esqueleto determinístico do que uma subárvore deixou em vigor.

**Campos:** `decisoes_vigentes: tuple[str, ...]`, `decisoes_substituidas: int`, `questoes_abertas: tuple[str, ...]`, `restricoes: tuple[str, ...]`, `ultimo_artefato: str`, `seq_ultimo_artefato: int`

- `esta_vazio() -> bool` `[property]` — Sem decisão, dúvida, restrição ou artefato não há fechamento a mostrar.
- `descrever(limite: int) -> tuple[str, ...]` — Linhas compactas do fechamento, na casa de vinte tokens cada.
- `em_dicionario() -> dict[str, object]` — Forma serializável para o canvas e para as respostas REST.

### Funções do módulo

- `decisoes_substituidas(estado: GrafoEstado) -> frozenset[str]` — Decisões que receberam uma aresta `substitui`: já não vigoram.
- `calcular_fechamento(nos: Sequence[NoGrafo], substituidas: frozenset[str]) -> FechamentoDeSubarvore` — Dobra os nós alcançados no esqueleto do fechamento, em ordem estável.

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

- `indice_de_rollup() -> IndiceDeRollup` `[property]` — Índice dos resumos de subárvore, calculado sob demanda se não vier pronto.
- `obter_resumo(id_no: str) -> ResumoDeSubarvore | None` — Resumo agregado da subárvore do nó, ou None se ele nada contiver.
- `calcular_escopo_ativo(raio: int) -> EscopoAtivo` — Recorte do grafo em torno do trabalho que ainda não terminou.
- `calcular_caminho_critico() -> CaminhoCritico` — Subgrafo de dependências, com os gargalos ordenados por alcance.
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
- `obter_filhos_por_contencao(id_no: str) -> list[NoGrafo]` — Filhos diretos do nó pelas arestas de contenção da ontologia.
- `obter_vizinhos_1_salto(id_no: str) -> list[NoGrafo]` — Coleta nós vizinhos conectados diretamente em 1 salto (entrada ou saída).
- `buscar_nos(termo: str, tipos: Sequence[TipoNo] | None) -> list[NoGrafo]` — Busca textual sobre rótulo e propriedades de nós filtrados por tipos.
- `buscar_ranqueado(criterio: CriterioBusca, escopo: EscopoAtivo | None) -> ResultadoDaBusca` — Busca ordenada por relevância e cortada no limite pedido.
- `obter_questoes_bloqueantes(id_task: str) -> list[NoGrafo]` — Retorna nós do tipo Question com aresta 'bloqueia' aberta para a Task.
- `esta_bloqueada(id_task: str) -> bool` — Determina se uma Task possui alguma questão aberta bloqueante.

## `projection/projecao_sincronizada.py`

Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno.

### `ProjecaoDoRamo`

*DTO imutável* — Estado projetado de um ramo junto da marca d'água já aplicada.

**Campos:** `estado: GrafoEstado`, `ultimo_seq_aplicado: int`, `indice: IndiceDeRollup | None`

### `ProjecaoSincronizada`

*serviço* — Mantém projeções por ramo alinhadas ao log, aplicando apenas o delta pendente.

- `obter_estado(ramo_id: str) -> GrafoEstado` — Consulta o estado do ramo já reconciliado com tudo que há no log.
- `sincronizar(ramo_id: str) -> ProjecaoDoRamo` — Aplica os eventos surgidos desde a última leitura e devolve a projeção.
- `registrar_estado_recem_commitado(ramo_id: str, projecao: ProjecaoDoRamo) -> None` — Adota a projeção calculada pelo próprio kernel logo após o commit.
- `obter_indice(ramo_id: str) -> IndiceDeRollup` — Índice de rollup do ramo, reconciliado com tudo que há no log.
- `descartar(ramo_id: str) -> None` — Esquece a projeção do ramo, forçando reconstrução na próxima consulta.

## `projection/ranking_busca.py`

Ordenação e corte dos resultados de busca textual no grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_PADRAO_DE_RESULTADOS` | `int` | `5` |
| `LIMITE_MAXIMO_DE_RESULTADOS` | `int` | `50` |
| `STATUS_ENCERRADOS` | `frozenset[str]` | `frozenset({StatusTask.CONCLUIDO.value, StatusQuestion.RESPONDIDA.value,…` |
| `CASOU_NO_ROTULO` | `str` | `'rotulo'` |
| `CASOU_NAS_PROPRIEDADES` | `str` | `'propriedades'` |
| `PALAVRAS_VAZIAS` | `frozenset[str]` | `frozenset({'para', 'pelo', 'pela', 'pelos', 'pelas', 'como', 'mais', 'm…` |
| `TAMANHO_MINIMO_DE_PALAVRA` | `int` | `4` |
| `_FORMA_PALAVRA_INTEIRA` | `int` | `0` |
| `_FORMA_PREFIXO` | `int` | `1` |
| `_FORMA_SUBSTRING` | `int` | `2` |
| `_FORMA_SEM_CASAMENTO` | `int` | `3` |

### `CriterioBusca`

*DTO imutável* — Parâmetros imutáveis de uma consulta textual ao grafo.

**Campos:** `termo: str`, `tipos: tuple[TipoNo, ...]`, `limite: int`

- `termo_normalizado() -> str` `[property]` — Termo em caixa baixa e sem espaços nas pontas, como o índice compara.
- `limite_efetivo() -> int` `[property]` — Limite saneado: ao menos um resultado, no máximo o teto da ferramenta.

### `ResultadoDaBusca`

*DTO imutável* — Página de resultados já ordenada, com o total do qual ela foi tirada.

**Campos:** `itens: tuple[ResultadoRanqueado, ...]`, `total_encontrado: int`

- `truncado() -> bool` `[property]` — Indica que há mais resultados além dos exibidos.
- `em_dicionario() -> dict[str, object]` — Resposta completa: o que veio, quanto existe e se foi cortado.

### `ResultadoRanqueado`

*DTO imutável* — Um nó encontrado, com onde o termo casou nele.

**Campos:** `no: NoGrafo`, `onde_casou: str`

- `em_dicionario() -> dict[str, object]` — Linha esquelética de resultado, sem descrição nem metadados.

### Funções do módulo

- `ranquear(nos: Sequence[NoGrafo], criterio: CriterioBusca) -> ResultadoDaBusca` — Ordena os nós por relevância ao termo e corta no limite pedido.
- `palavras_significativas(texto: str) -> frozenset[str]` — Palavras do texto que dizem de que ele trata: sem as curtas, as vazias e os números.
- `contar_palavras_casadas(no: NoGrafo, palavras: frozenset[str]) -> int` — Quantas das palavras aparecem inteiras no rótulo ou nas propriedades do nó.

## `projection/reducer.py`

Redutor determinístico de eventos append-only para estado de grafo em memória.

### `GrafoReducer`

*serviço* — Funções puras para projetar eventos ordenados em instâncias imutáveis de GrafoEstado.

- `reconstruir(eventos: Sequence[EventoLog]) -> GrafoEstado` — Reconstrói o estado integral do grafo a partir de uma sequência de eventos.
- `aplicar_eventos(estado_base: GrafoEstado, eventos: Sequence[EventoLog]) -> GrafoEstado` — Dobra a sequência sobre o estado base em uma passada, sem cópias intermediárias.
- `reduzir(estado: GrafoEstado, evento: EventoLog) -> GrafoEstado` — Aplica um único evento de forma pura sobre o estado atual.

## `projection/rollup.py`

Resumo agregado de cada subárvore de contenção, calculado uma vez por commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_TERMINAIS_DE_TAREFA` | `frozenset[str]` | `frozenset({StatusTask.CONCLUIDO.value})` |

### `IndiceDeRollup`

*serviço* — Resumo de cada subárvore de contenção do grafo, pronto para consulta.

- `calcular(estado: GrafoEstado) -> 'IndiceDeRollup'` — Dobra o estado inteiro em um resumo por contêiner, em uma passada.
- `obter(id_no: str) -> ResumoDeSubarvore | None` — Resumo da subárvore do nó, ou None quando ele não contém nada.
- `eh_container(id_no: str) -> bool` — Indica se o nó tem ao menos um filho por contenção.
- `nos_orfaos() -> tuple[str, ...]` `[property]` — Nós fora de qualquer hierarquia, que sumiriam calados na tela colapsada.
- `total_de_containers() -> int` `[property]` — Quantos nós do grafo têm subárvore resumida.

### `ResumoDeSubarvore`

*DTO imutável* — O que existe sob um contêiner, sem precisar abri-lo.

**Campos:** `id: str`, `total_nos: int`, `tarefas_por_status: Mapping[str, int]`, `questoes_abertas: int`, `seq_ultimo_toque: int`, `fechamento: FechamentoDeSubarvore`

- `tarefas_totais() -> int` `[property]` — Quantas Tasks a subárvore contém, em qualquer estado.
- `tarefas_concluidas() -> int` `[property]` — Quantas dessas Tasks já chegaram a um estado terminal.
- `tarefas_abertas() -> int` `[property]` — Quantas Tasks ainda pedem trabalho de alguém.
- `tem_trabalho_aberto() -> bool` `[property]` — Indica se vale a pena descer neste contêiner.
- `descrever() -> str` — Linha compacta de panorama, na casa de dez tokens.
- `em_dicionario() -> dict[str, object]` — Forma serializável para o canvas e para as respostas REST.

### `_MotorDeAlcance`

*serviço* — Resolve, para cada nó, o conjunto de identificadores da sua subárvore.

- `resolver_todos() -> Mapping[str, frozenset[str]]` — Alcance de cada nó do grafo, incluindo ele mesmo.

## `projection/working_set.py`

Escopo ativo: o que está perto do trabalho que ainda não terminou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAIO_PADRAO` | `int` | `1` |
| `RAIO_MAXIMO` | `int` | `6` |
| `ARESTAS_DE_TRABALHO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ, TipoAresta.DECOMPOE, TipoAresta.DEPENDE_D…` |

### `CalculadoraDeEscopoAtivo`

*serviço* — Percorre o grafo a partir do trabalho aberto até o raio pedido.

- `calcular(raio: int) -> EscopoAtivo` — Monta o escopo: sementes, alcance no raio e os contêineres de tudo isso.

### `EscopoAtivo`

*DTO imutável* — Conjunto de nós próximos ao trabalho aberto, com a semente que os trouxe.

**Campos:** `ids: frozenset[str]`, `sementes: frozenset[str]`, `raio: int`

- `contem(id_no: str) -> bool` — Indica se o nó pertence ao escopo ativo.
- `esta_vazio() -> bool` `[property]` — Sem trabalho aberto não há escopo ativo: a tela deve mostrar tudo.
- `em_dicionario() -> dict[str, object]` — Resumo serializável do recorte, para o canvas explicar o que escondeu.

### Funções do módulo

- `filtrar_por_escopo(ids: Sequence[str], escopo: EscopoAtivo) -> tuple[str, ...]` — Mantém apenas o que está no escopo; um escopo vazio não filtra nada.

