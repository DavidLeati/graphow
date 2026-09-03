# Setor 12 — Canvas e API REST

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.web`

Servidor HTTP, controladores REST por área e o canal de tempo real que leva cada commit ao canvas.

## Inventário

17 módulos · 1754 linhas · 31 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`web/composicao.py`](#webcomposicao) | 42 | Raiz de composição do servidor web: quem escuta os commits do kernel. |
| [`web/conversao_requisicoes.py`](#webconversaorequisicoes) | 117 | Conversão pura de payloads JSON da interface nos DTOs de requisição. |
| [`web/desconexao_cliente.py`](#webdesconexaocliente) | 12 | Distinção entre o cliente HTTP ter ido embora e o servidor ter falhado. |
| [`web/dto.py`](#webdto) | 150 | Objetos de Transferência de Dados (DTOs) imutáveis para a interface Web do Graphow. |
| [`web/identidade_web.py`](#webidentidadeweb) | 71 | Identidade da sessão web, fixada no servidor e nunca lida do corpo da requisição. |
| [`web/mapeamento_escopo.py`](#webmapeamentoescopo) | 76 | Mapeamento de cada nó do grafo à Sessão e ao Projeto que o contêm. |
| [`web/observador_sse.py`](#webobservadorsse) | 24 | Adaptador que publica no canal SSE os eventos aceitos pelo kernel. |
| [`web/rest_canvas_controller.py`](#webrestcanvascontroller) | 276 | Controlador REST especializado para operações de leitura e mutação visual do Canvas. |
| [`web/rest_fork_controller.py`](#webrestforkcontroller) | 80 | Controlador REST especializado na gestão de ramos, criação de Forks e Diff estrutural. |
| [`web/rest_lineage_controller.py`](#webrestlineagecontroller) | 37 | Controlador REST especializado no rastreamento de linhagem causal e proveniência. |
| [`web/rest_simulation_controller.py`](#webrestsimulationcontroller) | 57 | Controlador REST especializado na simulação de orçamentos de tokens e visualização de contexto. |
| [`web/rest_timeline_controller.py`](#webresttimelinecontroller) | 74 | Controlador REST especializado na Timeline de eventos bitemporais e Replay Temporal. |
| [`web/server.py`](#webserver) | 398 | Servidor HTTP integrado e despachante de rotas REST, SSE e Assets da interface do Graphow. |
| [`web/sse_controller.py`](#webssecontroller) | 123 | Controlador de Server-Sent Events para transmissão de eventos em tempo real para a UI. |
| [`web/static_assets_provider.py`](#webstaticassetsprovider) | 61 | Provedor seguro de arquivos estáticos para a Single-Page Application do Graphow. |
| [`web/vigia_do_log.py`](#webvigiadolog) | 129 | Vigia que leva ao canal SSE os eventos escritos por outros processos. |

## `web/composicao.py`

Raiz de composição do servidor web: quem escuta os commits do kernel.

### Funções do módulo

- `registrar_observadores_do_servidor(kernel: WriteKernel, controlador_sse: SSEWebController, motor: MotorReativo) -> None` — Liga o canal de tempo real e o motor reativo ao gancho pós-commit do kernel.
- `montar_tempo_real(kernel: WriteKernel, controlador_sse: SSEWebController) -> MotorReativo` — Monta o motor reativo padrão e o registra junto do canal SSE.
- `montar_vigia_do_log(kernel: WriteKernel, controlador_sse: SSEWebController) -> VigiaDoLogExterno` — Cria o vigia que publica no canvas o que outros processos escreveram no log.

## `web/conversao_requisicoes.py`

Conversão pura de payloads JSON da interface nos DTOs de requisição.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAMO_PADRAO` | `str` | `'main'` |
| `CAMPOS_DE_POSICAO` | `frozenset[str]` | `frozenset({'id_no', 'x', 'y'})` |

### Funções do módulo

- `extrair_ramo(payload: Mapping[str, Any]) -> str` — Lê o ramo alvo do corpo, com o ramo principal como padrão.
- `converter_novo_no(payload: Mapping[str, Any]) -> RequisicaoNovoNo` — Monta o pedido de criação de nó a partir do corpo recebido.
- `converter_nova_aresta(payload: Mapping[str, Any]) -> RequisicaoNovaAresta` — Monta o pedido de criação de aresta tipada.
- `converter_edicao_no(payload: Mapping[str, Any]) -> RequisicaoEdicaoNo` — Monta o pedido de edição de rótulo e propriedades de um nó.
- `converter_criar_fork(payload: Mapping[str, Any]) -> RequisicaoCriarFork` — Monta o pedido de bifurcação a partir de um ponto de corte.
- `converter_simular_vista(payload: Mapping[str, Any]) -> RequisicaoSimularVista` — Monta o pedido do simulador de orçamento, onde o papel é uma pergunta.
- `converter_exclusao_lote(payload: Mapping[str, Any]) -> RequisicaoExclusaoLote` — Monta o pedido de exclusão atômica de vários elementos.
- `converter_exclusao_projeto(payload: Mapping[str, Any]) -> RequisicaoExclusaoProjeto` — Monta o pedido de exclusão em cascata de um projeto.
- `converter_salvar_layout(payload: Mapping[str, Any]) -> RequisicaoSalvarLayout` — Monta o pedido de persistência do arranjo visual do canvas.
- `converter_posicoes(posicoes_brutas: Any) -> tuple[PosicaoNoCanvas, ...]` — Converte a lista recebida do canvas em coordenadas tipadas.

## `web/desconexao_cliente.py`

Distinção entre o cliente HTTP ter ido embora e o servidor ter falhado.

### Funções do módulo

- `eh_desconexao_do_cliente(erro: BaseException | None) -> bool` — Indica se a exceção é o cliente tendo ido embora, e não uma falha do servidor.

## `web/dto.py`

Objetos de Transferência de Dados (DTOs) imutáveis para a interface Web do Graphow.

### `DadosArestaVisual`

*DTO imutável* — DTO imutável para representação de uma aresta no Canvas.

**Campos:** `id: str`, `origem_id: str`, `destino_id: str`, `tipo: str`, `propriedades: Mapping[str, Any]`

### `DadosCanvasVisual`

*DTO imutável* — DTO imutável contendo o estado integral do Canvas para renderização.

**Campos:** `ramo_id: str`, `versao_log: int`, `total_nos: int`, `total_arestas: int`, `nos: Sequence[DadosNoVisual]`, `arestas: Sequence[DadosArestaVisual]`

### `DadosNoVisual`

*DTO imutável* — DTO imutável para representação de um nó no Canvas.

**Campos:** `id: str`, `tipo: str`, `rotulo: str`, `propriedades: Mapping[str, Any]`, `esta_bloqueado: bool`, `lock_ativo: str | None`, `sessao_id: str | None`

### `PosicaoNoCanvas`

*DTO imutável* — Coordenada imutável de um nó na superfície do canvas.

**Campos:** `id_no: str`, `x: int`, `y: int`

### `RequisicaoCriarFork`

*DTO imutável* — DTO imutável de entrada para criação de novo ramo a partir do log.

**Campos:** `novo_ramo: str`, `ramo_origem: str`, `evento_id_ponto_corte: str | None`

### `RequisicaoEdicaoNo`

*DTO imutável* — DTO imutável de entrada para modificação de atributos de um nó.

**Campos:** `id_no: str`, `novas_propriedades: Mapping[str, Any]`, `novo_rotulo: str | None`, `ramo_id: str`

### `RequisicaoExclusaoLote`

*DTO imutável* — DTO imutável de entrada para exclusão em lote de nós e arestas.

**Campos:** `ids_nos: Sequence[str]`, `ids_arestas: Sequence[str]`, `ramo_id: str`

### `RequisicaoExclusaoProjeto`

*DTO imutável* — DTO imutável de entrada para exclusão em cascata de um projeto inteiro.

**Campos:** `id_projeto: str`, `ramo_id: str`

### `RequisicaoNovaAresta`

*DTO imutável* — DTO imutável de entrada para criação de nova aresta via interface.

**Campos:** `origem_id: str`, `destino_id: str`, `tipo: str`, `id_aresta: str | None`, `propriedades: Mapping[str, Any]`, `ramo_id: str`

### `RequisicaoNovoNo`

*DTO imutável* — DTO imutável de entrada para criação de novo nó via interface.

**Campos:** `tipo: str`, `rotulo: str`, `id_no: str | None`, `sessao_id: str | None`, `propriedades: Mapping[str, Any]`, `ramo_id: str`

### `RequisicaoSalvarLayout`

*DTO imutável* — DTO imutável de entrada para persistir o arranjo visual do grafo.

**Campos:** `posicoes: tuple[PosicaoNoCanvas, ...]`, `ramo_id: str`

### `RequisicaoSimularVista`

*DTO imutável* — DTO imutável de entrada para simulação de orçamentos de tokens.

**Campos:** `id_alvo: str`, `papel: str`, `orcamento_tokens: int`, `ramo_id: str`

### `RespostaReciboWeb`

*DTO imutável* — DTO imutável de saída contendo recibo padronizado de mutação.

**Campos:** `sucesso: bool`, `mensagem: str`, `versao_log: int`, `eventos_gerados: Sequence[str]`, `diagnostico_mast: str | None`, `modo_de_falha: str | None`

## `web/identidade_web.py`

Identidade da sessão web, fixada no servidor e nunca lida do corpo da requisição.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AUTOR_PADRAO_DA_INTERFACE` | `str` | `'humano-ui'` |
| `CAMPOS_DE_IDENTIDADE_RECUSADOS` | `frozenset[str]` | `frozenset({'papel', 'autor'})` |

### `IdentidadeSessaoWeb`

*DTO imutável* — Autor e papel de toda escrita vinda do canvas nesta execução do servidor.

**Campos:** `autor: str`, `papel: PapelAutor`

- `do_usuario_local() -> 'IdentidadeSessaoWeb'` — Identifica quem abriu o servidor, caindo no autor genérico se não der.
- `papel_textual() -> str` `[property]` — Papel em texto, como os controladores REST o consomem.

### Funções do módulo

- `detectar_identidade_declarada(payload: Mapping[str, Any]) -> tuple[str, ...]` — Lista os campos de identidade que a requisição tentou declarar.
- `montar_recusa_de_identidade(campos: tuple[str, ...], identidade: IdentidadeSessaoWeb) -> dict[str, Any]` — Recusa explícita, no mesmo espírito da mensagem do servidor MCP.

## `web/mapeamento_escopo.py`

Mapeamento de cada nó do grafo à Sessão e ao Projeto que o contêm.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_QUE_PROPAGAM_PROJETO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.CONTEM, TipoAresta.PRODUZ})` |

### `MapeadorEscopo`

*serviço* — Consultas puras que associam nós aos contêineres de navegação.

- `mapear_sessoes(view: GrafoView) -> Mapping[str, str]` — Associa cada nó de trabalho à Sessão que o produziu.
- `mapear_projetos(view: GrafoView) -> Mapping[str, str]` — Propaga a filiação a projeto por toda a cadeia, até o ponto fixo.
- `identificar_tasks_bloqueadas(view: GrafoView) -> frozenset[str]` — Coleta as Tasks travadas por alguma Question ainda aberta.
- `coletar_descendentes_do_projeto(id_projeto: str, view: GrafoView) -> tuple[str, ...]` — Lista o projeto e tudo que pende dele, em ordem estável.

## `web/observador_sse.py`

Adaptador que publica no canal SSE os eventos aceitos pelo kernel.

### `ObservadorSSE` (ObservadorCommit)

*serviço* — Entrega ao canal de tempo real cada evento que os portões aprovaram.

- `nome() -> str` `[property]` — Nome identificador do observador.
- `notificar(eventos: Sequence[EventoLog]) -> None` — Publica o lote para todos os assinantes conectados.

## `web/rest_canvas_controller.py`

Controlador REST especializado para operações de leitura e mutação visual do Canvas.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVE_POS_X` | `str` | `'pos_x'` |
| `CHAVE_POS_Y` | `str` | `'pos_y'` |

### `CanvasWebController`

*serviço* — Controlador responsável por gerar a projeção do Canvas e processar mutações de nós/arestas.

- `obter_canvas(ramo_id: str, sessao_id: str | None, projeto_id: str | None) -> DadosCanvasVisual` — Gera a projeção visual completa do grafo com metadados de bloqueio e locks.
- `criar_no(req: RequisicaoNovoNo) -> RespostaReciboWeb` — Processa a criação de um novo nó com vinculação opcional à Sessão.
- `criar_aresta(req: RequisicaoNovaAresta) -> RespostaReciboWeb` — Processa a criação de uma nova aresta tipada entre dois nós.
- `editar_no(req: RequisicaoEdicaoNo) -> RespostaReciboWeb` — Processa alterações de rótulo e propriedades de um nó existente.
- `remover_elemento(tipo_elemento: str, id_elemento: str, ramo_id: str) -> RespostaReciboWeb` — Remove nó ou aresta gerando o respectivo patch de remoção.
- `remover_lote(req: RequisicaoExclusaoLote) -> RespostaReciboWeb` — Processa a remoção atômica de múltiplos nós e arestas.
- `salvar_layout(req: RequisicaoSalvarLayout) -> RespostaReciboWeb` — Persiste as coordenadas do canvas como propriedades dos nós.
- `remover_projeto_completo(req: RequisicaoExclusaoProjeto) -> RespostaReciboWeb` — Processa a remoção em cascata de um projeto e todos os seus descendentes.

### `ContextoFiltroVisual`

*DTO imutável* — DTO imutável para parâmetros de filtragem e mapeamento visual.

**Campos:** `mapa_sessoes: Mapping[str, str]`, `mapa_projetos: Mapping[str, str]`, `nos_bloqueados: frozenset[str]`, `sessao_id: str | None`, `projeto_id: str | None`

### `MetadadosSubmissao`

*DTO imutável* — DTO imutável para metadados de autoria e justificativa de submissões.

**Campos:** `autor: str`, `papel: str`, `ramo_id: str`, `justificativa: str`

## `web/rest_fork_controller.py`

Controlador REST especializado na gestão de ramos, criação de Forks e Diff estrutural.

### `ForkWebController`

*serviço* — Controlador para bifurcação histórica e comparação visual de ramos.

- `criar_fork(req: RequisicaoCriarFork) -> RespostaReciboWeb` — Cria um novo ramo a partir de um evento de corte especificado.
- `calcular_diff_ramos(ramo_a: str, ramo_b: str) -> dict[str, Any]` — Calcula as discrepâncias estruturais entre dois ramos forkados.
- `listar_ramos() -> list[str]` — Lista todos os ramos existentes no repositório.

## `web/rest_lineage_controller.py`

Controlador REST especializado no rastreamento de linhagem causal e proveniência.

### `LineageWebController`

*serviço* — Controlador para expor trilhas causais do entregável até o objetivo raiz.

- `obter_linhagem(id_no: str, ramo_id: str) -> dict[str, Any]` — Rastreia passos causais e nós intermediários desde o nó alvo até o Goal raiz.

## `web/rest_simulation_controller.py`

Controlador REST especializado na simulação de orçamentos de tokens e visualização de contexto.

### `SimulationWebController`

*serviço* — Controlador para simular a visão materializada consumida por agentes de IA.

- `simular_vista(req: RequisicaoSimularVista) -> dict[str, Any]` — Gera a vista em Markdown e métricas de tokens para o papel e orçamento solicitados.
- `expandir_no(id_no: str, ramo_id: str) -> dict[str, Any]` — Executa a ferramenta expandir_no sob demanda revelando propriedades e arestas.

## `web/rest_timeline_controller.py`

Controlador REST especializado na Timeline de eventos bitemporais e Replay Temporal.

### `TimelineWebController`

*serviço* — Controlador para leitura cronológica do log e reconstrução de estado histórico.

- `obter_eventos(ramo_id: str, autor: str | None, papel: str | None) -> list[dict[str, Any]]` — Recupera lista cronológica de eventos com filtros opcionais por autor e papel.
- `obter_estado_na_versao(versao_alvo: int, ramo_id: str) -> DadosCanvasVisual` — Reconstrói o estado do grafo exatamente como existia na versão de log informada.

## `web/server.py`

Servidor HTTP integrado e despachante de rotas REST, SSE e Assets da interface do Graphow.

### `EnderecoServidor`

*DTO imutável* — Host e porta em que a interface do canvas fica disponível.

**Campos:** `host: str`, `porta: int`

### `GraphowHTTPHandler` (BaseHTTPRequestHandler)

*serviço* — Manipulador de requisições HTTP REST, SSE e arquivos estáticos.

**Campos:** `server: 'GraphowThreadingServer'`

- `do_GET() -> None` — Despacha requisições GET para os controladores específicos.
- `do_POST() -> None` — Despacha requisições POST para controladores de mutação e simulação.
- `do_PUT() -> None` — Despacha requisições PUT para edição de nós e persistência de layout.
- `do_DELETE() -> None` — Despacha requisições DELETE para remoção de nós ou arestas.
- `log_message(format: str) -> None` — Silencia logs padrões do BaseHTTPRequestHandler para não poluir terminal.

### `GraphowThreadingServer` (ThreadingHTTPServer)

*serviço* — Servidor HTTP multithread contendo instâncias injetadas dos controladores.

- `handle_error(request: Any, client_address: Any) -> None` — Descarta o ruído da desconexão e deixa passar todo o resto.
- `server_close() -> None` — Encerra a varredura do log antes de fechar os sockets.

### `GraphowWebServer`

*serviço* — Gerenciador de alto nível para inicialização e desligamento do servidor web.

- `iniciar(bloqueante: bool) -> None` — Inicializa o servidor HTTP na porta configurada.
- `parar() -> None` — Encerra o servidor e fecha os sockets.

## `web/sse_controller.py`

Controlador de Server-Sent Events para transmissão de eventos em tempo real para a UI.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_IDS_LEMBRADOS` | `int` | `2000` |
| `LIMITE_DE_EVENTOS_EM_FILA` | `int` | `500` |
| `NOME_EVENTO_ABERTURA` | `str` | `'conexao_aberta'` |
| `NOME_EVENTO_DESCARTE` | `str` | `'assinante_descartado'` |
| `MOTIVO_DO_DESCARTE` | `str` | `'fila cheia: o cliente não acompanhou o ritmo do log'` |

### `SSEWebController`

*serviço* — Gerencia assinantes conectados e distribui eventos formatados para o Canvas via SSE.

- `registrar_assinante() -> queue.Queue[EventoLog]` — Registra um novo ouvinte de eventos em tempo real.
- `remover_assinante(fila: queue.Queue[EventoLog]) -> None` — Remove o ouvinte após desconexão do cliente HTTP.
- `esta_registrado(fila: queue.Queue[EventoLog]) -> bool` — Informa se a fila ainda pertence a um assinante ativo.
- `despachar_evento(evento: EventoLog) -> int` — Envia o evento para todas as filas ativas, uma única vez por identificador.
- `gerar_stream_para_fila(fila: queue.Queue[EventoLog], timeout_segundos: float) -> Iterator[str]` — Gera mensagens SSE com batimento cardíaco até o assinante deixar de existir.

### Funções do módulo

- `montar_mensagem_de_abertura() -> str` — Primeiro bloco do stream, que confirma ao cliente a assinatura aberta.
- `montar_mensagem_de_descarte() -> str` — Bloco SSE final que diz ao cliente por que o stream terminou.

## `web/static_assets_provider.py`

Provedor seguro de arquivos estáticos para a Single-Page Application do Graphow.

### `RecursoEstatico`

*DTO imutável* — Representação imutável de um asset estático lido do disco.

**Campos:** `conteudo: bytes`, `tipo_conteudo: str`, `status_code: int`

### `StaticAssetsProvider`

*serviço* — Localiza, valida segurança de path traversal e serve assets estáticos da interface web.

**Campos:** `MIME_MAPA: dict[str, str]`

- `obter_recurso(caminho_relativo: str) -> RecursoEstatico` — Resolve e carrega o arquivo estático com proteção estrita contra Directory Traversal.

## `web/vigia_do_log.py`

Vigia que leva ao canal SSE os eventos escritos por outros processos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `INTERVALO_PADRAO_DE_VARREDURA` | `float` | `0.5` |
| `TEMPO_LIMITE_DE_PARADA` | `float` | `2.0` |
| `NOME_DA_THREAD` | `str` | `'graphow-vigia-do-log'` |
| `PREFIXO_DO_AVISO` | `str` | `'AVISO [vigia-do-log]:'` |

### `VigiaDoLogExterno`

*serviço* — Publica no canal de tempo real os eventos que entraram no log sem passar por aqui.

- `esta_ativo() -> bool` `[property]` — Informa se a varredura de segundo plano está em curso.
- `iniciar() -> None` — Adota o log atual como já visto e passa a varrer o delta em segundo plano.
- `parar(timeout_segundos: float) -> None` — Sinaliza a parada e espera a thread de varredura encerrar.
- `adotar_posicao_atual() -> None` — Marca tudo que já existe como visto, para não republicar o passado.
- `varrer() -> int` — Publica tudo que surgiu desde a última passada e devolve quantos eventos foram.

