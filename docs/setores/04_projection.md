# Setor 04 — Projeção Determinística

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.projection`

Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.

## Inventário

23 módulos · 3742 linhas · 40 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`projection/acumulador.py`](#projectionacumulador) | 215 | Acumulador mutável usado para dobrar muitos eventos em uma passada só. |
| [`projection/ambito.py`](#projectionambito) | 71 | O âmbito de cada nó: os projetos de trabalho ou as sessões que o hook abre. |
| [`projection/apresentacao_do_placar.py`](#projectionapresentacaodoplacar) | 229 | O placar de escopo em texto e em dicionário: as cinco linhas da seção 4.7 e o recorte para a web e o MCP. |
| [`projection/caminho_critico.py`](#projectioncaminhocritico) | 178 | Caminho crítico: quem trava quem, e quanto cada gargalo destrava. |
| [`projection/classificacao_escopo.py`](#projectionclassificacaoescopo) | 281 | A classe de escopo de cada Task: de onde ela veio em relação ao plano aprovado do Goal. |
| [`projection/custo_de_escopo.py`](#projectioncustodeescopo) | 287 | O custo por decisão: de que raiz de `motivada_por` nasceu cada Task depois da referência e quanto ela custou. |
| [`projection/decomposicao.py`](#projectiondecomposicao) | 27 | As tarefas de um Goal: todas as Tasks abaixo dele pela decomposição, em qualquer profundidade. |
| [`projection/escopo_plano.py`](#projectionescopoplano) | 179 | O plano aprovado de um Goal lido do grafo: versões, referência, conjunto de Tasks e Goal de uma Task. |
| [`projection/faixas_da_fila.py`](#projectionfaixasdafila) | 96 | As faixas de escopo da fila: o plano primeiro, o emergente que o plano pede depois, o resto no fim. |
| [`projection/fechamento.py`](#projectionfechamento) | 119 | Fechamento determinístico de uma subárvore: o que vigora, o que segue aberto, o último artefato. |
| [`projection/fila_trabalho.py`](#projectionfilatrabalho) | 274 | Fila de trabalho: quais tarefas de uma sessão estão de fato executáveis agora. |
| [`projection/graph_view.py`](#projectiongraphview) | 198 | Camada de consulta e visualização imutável do grafo projetado (CQRS). |
| [`projection/instantaneo.py`](#projectioninstantaneo) | 156 | Reconstrução de um ramo a partir do último instantâneo guardado, conferido contra o log. |
| [`projection/integracao_base.py`](#projectionintegracaobase) | 112 | O ramo base de um Goal e os caminhos em que ele colide, lidos do grafo por herança. |
| [`projection/placar_escopo.py`](#projectionplacarescopo) | 318 | O placar de escopo de um Goal: o plano, o desvio desde a referência e os gatilhos K e M. |
| [`projection/projecao_sincronizada.py`](#projectionprojecaosincronizada) | 108 | Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno. |
| [`projection/propostas.py`](#projectionpropostas) | 127 | As propostas fora do Goal que o agente deixou para o humano decidir. |
| [`projection/ranking_busca.py`](#projectionrankingbusca) | 186 | Ordenação e corte dos resultados de busca textual no grafo. |
| [`projection/reducer.py`](#projectionreducer) | 34 | Redutor determinístico de eventos append-only para estado de grafo em memória. |
| [`projection/revisao.py`](#projectionrevisao) | 146 | A revisão de uma tarefa lida do grafo: os vereditos que ela recebeu e o que vigora entre eles. |
| [`projection/rollup.py`](#projectionrollup) | 221 | Resumo agregado de cada subárvore de contenção, calculado uma vez por commit. |
| [`projection/working_set.py`](#projectionworkingset) | 174 | Escopo ativo: o que está perto do trabalho que ainda não terminou. |

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

## `projection/ambito.py`

O âmbito de cada nó: os projetos de trabalho ou as sessões que o hook abre.

### `Ambito` (str, Enum)

*serviço* — Onde um nó mora: entre os projetos de trabalho ou nas sessões do hook.

### Funções do módulo

- `ler_ambito(texto: str | None) -> Ambito | None` — O âmbito pedido, ou None quando o pedido não nomeia um: nesse caso nada é filtrado.
- `nasceu_do_hook(no: NoGrafo) -> bool` — O papel `sistema` só é assumido pelo harness: o que ele criou nasceu do hook.
- `eh_ambiente_do_hook(no: NoGrafo) -> bool` — Um Projeto que o hook criou guarda as sessões de um repositório, e não é projeto de trabalho.
- `ambientes_do_hook(view: GrafoView) -> frozenset[str]` — Os ids dos Projetos que o hook criou, um por repositório.
- `ambito_do_no(id_no: str, mapa_projetos: Mapping[str, str], ambientes: frozenset[str]) -> Ambito` — O âmbito do Projeto que contém o nó.
- `contar_por_ambito(view: GrafoView, mapa_projetos: Mapping[str, str]) -> dict[str, int]` — Quantos nós do grafo moram em cada âmbito, para cada raiz da árvore mostrar o seu total.

## `projection/apresentacao_do_placar.py`

O placar de escopo em texto e em dicionário: as cinco linhas da seção 4.7 e o recorte para a web e o MCP.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ROTULO_DAS_CLASSES` | `dict[str, str]` | `{ClasseDeEscopo.B1.value: 'B1', ClasseDeEscopo.B3.value: 'B3', ClasseDe…` |
| `SEPARADOR` | `str` | `' · '` |
| `CLASSES_DE_SEMPRE` | `frozenset[str]` | `frozenset({ClasseDeEscopo.B1.value, ClasseDeEscopo.B3.value, ClasseDeEs…` |
| `CLASSES_EMERGENTES` | `tuple[ClasseDeEscopo, ...]` | `(ClasseDeEscopo.B3, ClasseDeEscopo.SEM_LIGACAO)` |

### Funções do módulo

- `linhas_do_placar(placar: 'PlacarDeEscopo') -> tuple[str, ...]` — As cinco linhas: escopo, plano, contagem desde a referência, raiz que mais gerou e cadeia mais longa.
- `linhas_de_desvio(placar: 'PlacarDeEscopo') -> tuple[str, ...]` — Os gatilhos disparados, as decisões sem veredito e as respostas de desvio, uma por linha.
- `linhas_curtas_do_placar(placar: 'PlacarDeEscopo') -> tuple[str, ...]` — O placar em até três linhas: referência com os emergentes, gatilhos disparados e decisões sem veredito.
- `placar_em_dicionario(placar: 'PlacarDeEscopo') -> dict[str, Any]` — O placar como estruturas simples, com as respostas do árbitro marcadas.

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

## `projection/classificacao_escopo.py`

A classe de escopo de cada Task: de onde ela veio em relação ao plano aprovado do Goal.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_DE_DECISAO_REVOGADA` | `str` | `'revogada'` |
| `ALVOS_DE_MOTIVACAO` | `frozenset[TipoNo]` | `frozenset({TipoNo.DECISION, TipoNo.EVIDENCE, TipoNo.TASK, TipoNo.QUESTI…` |
| `LIGACOES_ACEITAS` | `dict[ClasseDeEscopo, str]` | `{ClasseDeEscopo.B1: 'decompoe vindo de uma Task do plano vigente, ou de…` |

### `BaseDoPlano` (str, Enum)

*serviço* — Contra que versão do plano a classe é lida.

### `ClasseDeEscopo` (str, Enum)

*serviço* — De onde a Task veio, em relação ao plano aprovado do Goal.

### `ClassificadorDeEscopo`

*serviço* — Classifica Tasks de uma vista, indexando a decomposição e guardando o plano de cada Goal.

- `view() -> GrafoView` `[property]` — A vista que o classificador indexa.
- `goal_da(id_task: str) -> str | None` — O Goal da Task por `decompoe`, ou None.
- `tem_plano(id_goal: str) -> bool` — O Goal tem alguma versão de plano aprovada, de qualquer papel.
- `classe_da(id_task: str) -> ClasseDeEscopo` — A classe da Task; `fora_de_goal` quando nenhum Goal a contém.
- `ligacao_valida(id_task: str) -> bool` — A Task não precisa de ligação, ou tem uma que o kernel aceita.

### Funções do módulo

- `classificar_tarefa(view: GrafoView, id_task: str) -> ClasseDeEscopo` — A classe da Task relativa ao plano de referência: a última aprovação humana, sem ela tudo é emergente.
- `classificar_tarefa_vigente(view: GrafoView, id_task: str) -> ClasseDeEscopo` — A classe da Task relativa ao plano vigente, de qualquer papel: o que a fila e o kernel conferem.
- `ligacao_valida(view: GrafoView, id_task: str) -> bool` — A Task tem a ligação que o plano vigente exige, ou não precisa de nenhuma.
- `ligacoes_faltantes(view: GrafoView, id_task: str) -> tuple[str, ...]` — As ligações aceitas que a Task não tem; vazio quando ela já está válida.
- `raiz_da_cadeia(view: GrafoView, id_no: str) -> str` — O nó de onde a cadeia de `motivada_por` parte: o primeiro sem `motivada_por` saindo dele.

## `projection/custo_de_escopo.py`

O custo por decisão: de que raiz de `motivada_por` nasceu cada Task depois da referência e quanto ela custou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_TAREFAS_DO_RUN` | `str` | `'tarefas'` |
| `CAMPOS_DE_TOKENS` | `tuple[str, ...]` | `('tokens_entrada', 'tokens_saida', 'tokens_cache_leitura', 'tokens_cach…` |
| `CAMPO_FONTE` | `str` | `'fonte'` |
| `SEM_REFERENCIA` | `int` | `-1` |
| `PROFUNDIDADE_MAXIMA` | `int` | `64` |
| `CLASSES_EMERGENTES` | `frozenset[ClasseDeEscopo]` | `frozenset({ClasseDeEscopo.B3, ClasseDeEscopo.SEM_LIGACAO})` |
| `CLASSES_QUE_HERDAM_A_RAIZ` | `frozenset[ClasseDeEscopo]` | `frozenset({ClasseDeEscopo.CORRECAO, ClasseDeEscopo.ACOMPANHAMENTO, Clas…` |
| `PASSOS_PARA_ACHAR_A_ORIGEM` | `int` | `8` |

### `CustoDaRaiz`

*DTO imutável* — O que uma raiz de cadeia gerou: Tasks por classe, alvos, custo dos Runs, reversões e profundidade.

**Campos:** `raiz: str`, `tasks: tuple[TaskDoEscopo, ...]`, `tasks_por_classe: Mapping[str, int]`, `alvos: tuple[str, ...]`, `runs: int`, `tokens: int`, `profundidade: int`

- `reversoes() -> int` `[property]` — As reversões (`desfaz`) debitadas a esta raiz.
- `emergentes() -> tuple[TaskDoEscopo, ...]` `[property]` — As Tasks B3 e sem ligação da raiz, da mais antiga à mais nova.

### `TaskDoEscopo`

*DTO imutável* — Uma Task nascida depois da referência: a classe, quem a criou, a raiz que a debita e a profundidade.

**Campos:** `id: str`, `classe: ClasseDeEscopo`, `seq: int`, `humana: bool`, `status: str`, `raiz: str | None`, `profundidade: int`

- `eh_emergente() -> bool` `[property]` — B3 e Task sem ligação são o que o gatilho de desvio conta.

### `_Atribuidor`

*serviço* — Acha a raiz que paga por cada Task: a da cadeia de `motivada_por`, a da reversão ou a da Task corrigida.

- `raiz_de(no: NoGrafo, classe: ClasseDeEscopo) -> str | None` — A raiz da Task; None para a subdivisão sem `motivada_por`, que só conta no Goal.

### Funções do módulo

- `seq_da_referencia(view: GrafoView, id_goal: str) -> int` — O `seq` da última aprovação humana do plano; `SEM_REFERENCIA` quando não houve.
- `tasks_desde_a_referencia(view: GrafoView, id_goal: str) -> tuple[TaskDoEscopo, ...]` — As Tasks do Goal nascidas depois da referência, classificadas contra ela, em ordem de criação.
- `emergentes_do_agente_desde_o_zero(view: GrafoView, id_goal: str) -> tuple[TaskDoEscopo, ...]` — As emergentes que não são de humano nascidas depois do último zero: o que o limiar M e o teto contam.
- `custo_por_raiz(view: GrafoView, tasks: Iterable[TaskDoEscopo]) -> tuple[CustoDaRaiz, ...]` — O custo de cada raiz que gerou Task, em ordem de identificador da raiz.
- `custo_do_goal(view: GrafoView, id_goal: str) -> tuple[CustoDaRaiz, ...]` — O custo por raiz de todo o trabalho do Goal depois da referência.
- `profundidade_da_cadeia(view: GrafoView, id_no: str) -> int` — O maior número de saltos de `motivada_por` a partir do nó; um ciclo para no teto.

## `projection/decomposicao.py`

As tarefas de um Goal: todas as Tasks abaixo dele pela decomposição, em qualquer profundidade.

### Funções do módulo

- `tarefas_da_decomposicao(view: GrafoView, id_raiz: str) -> tuple[NoGrafo, ...]` — Todas as Tasks abaixo do nó por `decompoe`, correções incluídas, em ordem de identificador.

## `projection/escopo_plano.py`

O plano aprovado de um Goal lido do grafo: versões, referência, conjunto de Tasks e Goal de uma Task.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEIS_QUE_APROVAM_PLANO` | `frozenset[str]` | `frozenset({PapelAutor.HUMANO.value, PapelAutor.ARBITRO.value})` |
| `PROFUNDIDADE_MAXIMA_DA_DECOMPOSICAO` | `int` | `64` |

### `IndiceDeDecomposicao`

*serviço* — Pais e filhos por `decompoe`, indexados uma vez para as travessias não varrerem as arestas.

- `filhos(id_no: str) -> tuple[str, ...]` — Os destinos de `decompoe` que saem do nó, em ordem de identificador.
- `pais(id_no: str) -> tuple[str, ...]` — As origens de `decompoe` que chegam ao nó, em ordem de identificador.

### `VersaoDoPlano`

*DTO imutável* — Uma aprovação do plano: qual versão, em que ponto do log e por quem.

**Campos:** `versao: int`, `seq: int`, `aprovado_por: str`, `papel: str`

- `eh_humano() -> bool` `[property]` — Só a aprovação humana serve de referência do desvio.

### Funções do módulo

- `planos_do_goal(view: GrafoView, id_goal: str) -> tuple[VersaoDoPlano, ...]` — As versões bem formadas de `Goal.planos`, da mais antiga à mais nova; vazio sem plano.
- `plano_vigente(view: GrafoView, id_goal: str) -> VersaoDoPlano | None` — A última versão aprovada, de qualquer papel; None quando o Goal não tem plano.
- `plano_de_referencia(view: GrafoView, id_goal: str) -> VersaoDoPlano | None` — A última versão aprovada por humano; None faz toda Task contar como emergente.
- `tasks_do_plano(view: GrafoView, id_goal: str, versao: VersaoDoPlano) -> frozenset[str]` — As Tasks alcançáveis do Goal por `decompoe`, nascidas até o `seq` da versão.
- `goal_da_task(view: GrafoView, id_task: str) -> str | None` — O Goal mais próximo acima da Task por `decompoe`; None quando nenhum a contém.
- `seq_do_ultimo_zero(view: GrafoView, id_goal: str) -> int` — O `seq` em que o contador M zerou pela última vez; 0 quando nunca zerou.

## `projection/faixas_da_fila.py`

As faixas de escopo da fila: o plano primeiro, o emergente que o plano pede depois, o resto no fim.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FAIXA_DO_PLANO` | `int` | `1` |
| `FAIXA_DO_QUE_O_PLANO_PEDE` | `int` | `2` |
| `FAIXA_DO_RESTO` | `int` | `3` |
| `CLASSES_DA_FAIXA_DO_PLANO` | `frozenset[ClasseDeEscopo]` | `frozenset({ClasseDeEscopo.PLANO, ClasseDeEscopo.B1, ClasseDeEscopo.CORR…` |

### `FaixasDaFila`

*serviço* — Classe de escopo e faixa de cada Task de uma sessão, calculadas uma vez por consulta.

- `escopo(id_task: str) -> str` — A classe de escopo da Task; vazia quando o Goal dela não tem plano para medir.
- `faixa(id_task: str) -> int` — A faixa de atendimento da Task entre as pendentes: 1, 2 ou 3.

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
| `PRIORIDADE_DO_QUE_ESTA_EM_VOO` | `int` | `1` |

### `FilaDeTrabalho`

*serviço* — Consulta pura que ordena as tarefas prontas para execução em uma sessão.

- `proximas_tarefas(id_sessao: str) -> tuple[TarefaExecutavel, ...]` — Tarefas da sessão com dependências cumpridas, sem dúvida aberta e sem posse.
- `tarefas_impedidas(id_sessao: str) -> tuple[TarefaImpedida, ...]` — Tarefas da sessão que não entraram na fila, cada uma com o seu motivo.

### `MotivoDeImpedimento` (str, Enum)

*serviço* — Por que uma tarefa da sessão não está disponível agora.

### `TarefaExecutavel`

*DTO imutável* — Tarefa liberada para trabalho, com o que o agente precisa para decidir.

**Campos:** `id: str`, `rotulo: str`, `status: str`, `criterio_pronto: str`, `depende_de: tuple[str, ...]`, `modelo: str`, `trilha: str`, `entrega: str`, `arquivos_alvo: tuple[str, ...]`, `corrige: str`, `profundidade_correcao: int`, `escopo: str`, `faixa: int`

- `em_dicionario() -> dict[str, object]` — Forma serializável para a resposta da ferramenta MCP.

### `TarefaImpedida`

*DTO imutável* — Tarefa fora da fila, com o motivo que a mantém de fora.

**Campos:** `id: str`, `rotulo: str`, `status: str`, `motivo: MotivoDeImpedimento`

- `em_dicionario() -> dict[str, object]` — Forma serializável para a resposta da ferramenta MCP.

## `projection/graph_view.py`

Camada de consulta e visualização imutável do grafo projetado (CQRS).

### `GrafoView`

*serviço* — Consultas somente-leitura sobre o estado projetado do grafo em memória.

- `estado() -> GrafoEstado` `[property]` — O estado projetado, só para leitura: quem decide como o kernel (a política de governança) lê o mesmo estado.
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

## `projection/instantaneo.py`

Reconstrução de um ramo a partir do último instantâneo guardado, conferido contra o log.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EVENTOS_ATE_NOVO_INSTANTANEO` | `int` | `1000` |
| `MODULOS_QUE_DEFINEM_A_PROJECAO` | `tuple[str, ...]` | `('graphow.core.events', 'graphow.core.models', 'graphow.core.types', 'g…` |

### `ReconstrucaoComInstantaneo`

*serviço* — Reconstrói um ramo partindo do instantâneo válido e grava outro quando o delta cresce.

- `reconstruir(ramo_id: str) -> tuple[GrafoEstado, int]` — O estado do ramo e o último seq aplicado, pelo caminho mais curto que confere.

### Funções do módulo

- `impressao_da_projecao() -> str` — Hash do código que transforma eventos em estado, lido uma vez por processo.
- `serializar_estado(estado: GrafoEstado) -> str` — Estado completo em JSON, na ordem de inserção: a desserialização devolve um estado igual.
- `desserializar_estado(texto: str) -> GrafoEstado` — Refaz o estado gravado por `serializar_estado`.

## `projection/integracao_base.py`

O ramo base de um Goal e os caminhos em que ele colide, lidos do grafo por herança.

### `IntegracaoDoGoal`

*DTO imutável* — O ramo base e os globs de colisão que valem para o Goal, com o nó de onde cada um veio.

**Campos:** `ramo_base: str`, `origem_do_ramo: str`, `caminhos_de_colisao: tuple[str, ...]`, `origem_dos_caminhos: str`

### Funções do módulo

- `resolver_integracao(view: GrafoView, id_goal: str) -> IntegracaoDoGoal` — Cada propriedade vem do primeiro nó que a tem: o Goal, depois o Setor, depois o Projeto.
- `caminhos_do_goal(view: GrafoView, id_goal: str) -> tuple[str, ...]` — Os caminhos que o trabalho do Goal toca, sem repetição e em ordem.
- `cadeia_de_heranca(view: GrafoView, id_goal: str) -> tuple[NoGrafo, ...]` — O Goal, os Setores que contêm as sessões que o produziram e os Projetos desses Setores.

## `projection/placar_escopo.py`

O placar de escopo de um Goal: o plano, o desvio desde a referência e os gatilhos K e M.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `GATILHO_POR_RAIZ` | `str` | `'raiz'` |
| `GATILHO_POR_GOAL` | `str` | `'goal'` |
| `GATILHO_INANICAO` | `str` | `'inanicao'` |
| `CLASSES_SEMPRE_NO_PLACAR` | `tuple[ClasseDeEscopo, ...]` | `(ClasseDeEscopo.B1, ClasseDeEscopo.B3, ClasseDeEscopo.CORRECAO, ClasseD…` |

### `GatilhoDeDesvio`

*DTO imutável* — Um gatilho avaliado: qual, sobre que raiz, a contagem contra o limiar e se disparou.

**Campos:** `tipo: str`, `raiz: str | None`, `contagem: int`, `limiar: int`, `disparou: bool`

### `LimiaresDeDesvio`

*DTO imutável* — K (por raiz) e M (por Goal), como a política os resolveu para o Goal.

**Campos:** `por_raiz: int`, `por_goal: int`

### `PlacarDeEscopo`

*DTO imutável* — Tudo que o placar mostra de um Goal, calculado do grafo e dos limiares recebidos.

**Campos:** `id_goal: str`, `referencia: VersaoDoPlano | None`, `versoes_do_arbitro: tuple[VersaoDoPlano, ...]`, `plano: ResumoDoPlano`, `contagem_por_classe: Mapping[str, int]`, `raizes: tuple[RaizDoPlacar, ...]`, `cadeia_mais_longa: int`, `respostas_de_desvio: tuple[RespostaDeDesvio, ...]`, `emergentes_para_m: int`, `gatilhos: tuple[GatilhoDeDesvio, ...]`, `sem_veredito: tuple[str, ...]`, `limiares: LimiaresDeDesvio`

- `raiz_que_mais_gerou() -> RaizDoPlacar | None` `[property]` — A raiz com mais emergentes; None quando nenhuma gerou.
- `em_dicionario() -> dict[str, Any]` — O placar como dicionário simples, para a web e o MCP.
- `linhas() -> tuple[str, ...]` — As cinco linhas da seção 4.7 da proposta.
- `linhas_curtas() -> tuple[str, ...]` — O placar em até três linhas, para a vista de Task e de Sessão.
- `linhas_de_desvio() -> tuple[str, ...]` — Os gatilhos disparados e as respostas de desvio, para a cadência `desvio`.

### `RaizDoPlacar`

*DTO imutável* — Uma raiz com o custo dela e o que os gatilhos dizem: contador de K, se passou e se falta o veredito.

**Campos:** `custo: CustoDaRaiz`, `contador_k: int`, `passou_de_k: bool`, `veredito_pendente: bool`

- `raiz() -> str` `[property]` — O identificador da raiz.
- `emergentes() -> int` `[property]` — As Tasks B3 e sem ligação da raiz desde a referência.

### `RespostaDeDesvio`

*DTO imutável* — Uma resposta ao placar: quem, com que papel, a que raiz (None é o Goal) e o que disse.

**Campos:** `seq: int`, `respondido_por: str`, `papel: str`, `raiz: str | None`, `resposta: str`

- `do_arbitro() -> bool` `[property]` — O árbitro dispensou o alerta; o placar marca e a resposta não zera nada.
- `eh_humana() -> bool` `[property]` — Só a resposta humana zera o contador.

### `ResumoDoPlano`

*DTO imutável* — O plano de referência: quantas Tasks, quantas concluídas e as que nunca começaram, por fase.

**Campos:** `total: int`, `concluidas: int`, `sem_comecar: tuple[str, ...]`, `sem_comecar_por_fase: Mapping[str, int]`

### `_BaseDeK`

*DTO imutável* — O que K precisa além da raiz: o `seq` da referência, as respostas de desvio e o limiar.

**Campos:** `corte: int`, `respostas: tuple[RespostaDeDesvio, ...]`, `limiar: int`

### Funções do módulo

- `montar_placar(view: GrafoView, id_goal: str, limiares: LimiaresDeDesvio) -> PlacarDeEscopo` — O placar do Goal contra o plano de referência, com os limiares recebidos.
- `gatilhos_disparados(placar: PlacarDeEscopo) -> tuple[GatilhoDeDesvio, ...]` — Os gatilhos K, M e de inanição que dispararam; vazio quando o desvio cabe nos limiares.
- `respostas_de_desvio(view: GrafoView, id_goal: str) -> tuple[RespostaDeDesvio, ...]` — As respostas de desvio do Goal, em ordem de `seq`; entrada malformada é ignorada.

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

## `projection/propostas.py`

As propostas fora do Goal que o agente deixou para o humano decidir.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_STATUS_DA_PROPOSTA` | `str` | `'status'` |
| `CAMPO_ORIGENS_DA_PROPOSTA` | `str` | `'origens'` |
| `STATUS_PROPOSTA_ABERTA` | `str` | `'aberta'` |
| `STATUS_PROPOSTA_ACEITA` | `str` | `'aceita'` |
| `STATUS_PROPOSTA_DESCARTADA` | `str` | `'descartada'` |
| `STATUS_DE_DECISAO_DO_HUMANO` | `frozenset[str]` | `frozenset({STATUS_PROPOSTA_ACEITA, STATUS_PROPOSTA_DESCARTADA})` |
| `ARESTAS_DE_DESCIDA_DO_GOAL` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DECOMPOE, TipoAresta.PRODUZ})` |
| `SALTOS_DA_ORIGEM_ATE_A_TASK` | `int` | `3` |

### `PropostaForaDoGoal`

*DTO imutável* — Uma proposta aberta: o que se propõe, de onde veio e em que Projeto está.

**Campos:** `id: str`, `rotulo: str`, `status: str`, `projeto_id: str | None`, `origens: tuple[str, ...]`, `sessao_id: str | None`, `seq_criacao: int`, `autor: str`, `papel: str`

### Funções do módulo

- `eh_proposta_fora_do_goal(no: NoGrafo) -> bool` — A Note marcada como proposta fora do Goal, qualquer que seja o status.
- `status_da_proposta(no: NoGrafo) -> str` — O status da proposta; ausente conta como aberta.
- `listar_propostas_abertas(view: GrafoView, id_projeto: str | None) -> tuple[PropostaForaDoGoal, ...]` — As propostas abertas na ordem do log, só as do Projeto quando ele é dado.
- `propostas_do_goal(view: GrafoView, id_goal: str) -> tuple[PropostaForaDoGoal, ...]` — As abertas cuja origem é uma Task do Goal ou deriva de uma; sem origem, ficam só no Projeto.

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

## `projection/revisao.py`

A revisão de uma tarefa lida do grafo: os vereditos que ela recebeu e o que vigora entre eles.

### Funções do módulo

- `artefatos_da_tarefa(view: GrafoView, id_task: str) -> frozenset[str]` — Os Artifacts que derivam da Task: o que o executor entregou para revisão.
- `vereditos_sobre(view: GrafoView, alvos: Iterable[str]) -> tuple[NoGrafo, ...]` — As Evidence com veredito que derivam de algum dos alvos, em ordem de identificador.
- `veredito_vigente(view: GrafoView, id_task: str) -> str` — O veredito mais recente sobre a Task ou os Artifacts dela; vazio quando ninguém revisou.
- `evidencia_do_veredito_vigente(view: GrafoView, id_task: str) -> NoGrafo | None` — A Evidence do julgamento mais recente sobre a Task ou os Artifacts dela; None quando ninguém revisou.
- `veredito_efetivo(view: GrafoView, id_task: str) -> str` — O veredito vigente, a menos que uma correção aprovada o tenha superado.
- `tarefa_julgada(view: GrafoView, id_veredito: str) -> str` — A Task que o veredito julgou; vazio quando o veredito não chega a nenhuma.
- `profundidade_da_correcao(view: GrafoView, id_task: str) -> int` — Quantas correções há na cadeia até a Task original: 0 na original, 1 na primeira correção.

## `projection/rollup.py`

Resumo agregado de cada subárvore de contenção, calculado uma vez por commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_TERMINAIS_DE_TAREFA` | `frozenset[str]` | `frozenset({StatusTask.CONCLUIDO.value})` |

### `IndiceDeRollup`

*serviço* — Resumo de cada subárvore de contenção do grafo, calculado quando pedido.

- `calcular(estado: GrafoEstado) -> 'IndiceDeRollup'` — Mapeia a contenção do estado; os resumos saem sob demanda.
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

