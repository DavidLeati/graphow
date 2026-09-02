# Setor 02 — Kernel de Escrita (PatchBoard)

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.kernel`

Os quatro portões de governança, a conversão de JSON Patch em eventos e o commit transacional. Único caminho de mutação do estado compartilhado.

## Inventário

13 módulos · 1939 linhas · 23 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`kernel/composicao.py`](#kernelcomposicao) | 48 | Raiz de composição do kernel: monta repositórios e portões numa peça só. |
| [`kernel/conversao_eventos.py`](#kernelconversaoeventos) | 129 | Conversão de operações JSON Patch RFC 6902 em eventos formais do log. |
| [`kernel/execucao.py`](#kernelexecucao) | 66 | Registro do ciclo de vida de execução de um agente no log compartilhado. |
| [`kernel/invariant_gate.py`](#kernelinvariantgate) | 210 | Portão 3: Validação de Invariantes de Integridade Relacional do Grafo (Invariant Gate). |
| [`kernel/matriz_papeis.py`](#kernelmatrizpapeis) | 114 | Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo. |
| [`kernel/observadores.py`](#kernelobservadores) | 55 | Notificação pós-commit dos eventos aceitos pelos quatro portões. |
| [`kernel/patch_models.py`](#kernelpatchmodels) | 166 | Modelos imutáveis e sanitizadores para operações JSON Patch (RFC 6902). |
| [`kernel/rastreio_projeto.py`](#kernelrastreioprojeto) | 143 | Rastreio do Projeto ancestral de um nó, resistente a ciclos na hierarquia. |
| [`kernel/role_gate.py`](#kernelrolegate) | 350 | Portão 2: Validação de Contratos de Permissão por Papel (Role Gate). |
| [`kernel/schema_gate.py`](#kernelschemagate) | 275 | Portão 1: Validação de Conformidade Estrutural com a Ontologia (Schema Gate). |
| [`kernel/telemetria.py`](#kerneltelemetria) | 102 | Descrição dos spans que o kernel emite a cada escrita aceita ou recusada. |
| [`kernel/write_kernel.py`](#kernelwritekernel) | 254 | Kernel de Escrita e Validação Transacional em 4 Portões (PatchBoard). |

## `kernel/composicao.py`

Raiz de composição do kernel: monta repositórios e portões numa peça só.

### Funções do módulo

- `montar_kernel(repositorios: ConjuntoRepositorios, tracer: Tracer | None) -> WriteKernel` — Constrói o kernel sobre um conjunto de repositórios já composto.
- `montar_kernel_em_memoria(tracer: Tracer | None) -> WriteKernel` — Kernel efêmero completo, com linhagem de ramos e locks em memória.
- `montar_kernel_sqlite(store: SQLiteEventStore, tracer: Tracer | None) -> WriteKernel` — Kernel persistente sobre um arquivo SQLite já aberto.
- `abrir_kernel_sqlite(caminho_banco: str | Path, tracer: Tracer | None) -> tuple[SQLiteEventStore, WriteKernel]` — Abre o banco e devolve o store cru junto do kernel montado sobre ele.

## `kernel/conversao_eventos.py`

Conversão de operações JSON Patch RFC 6902 em eventos formais do log.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTO_NOS` | `str` | `'nos'` |
| `SEGMENTO_ARESTAS` | `str` | `'arestas'` |
| `SEGMENTO_PROPRIEDADES` | `str` | `'propriedades'` |
| `SEGMENTOS_DE_UMA_PROPRIEDADE` | `int` | `4` |

### `ContextoConversaoEvento`

*DTO imutável* — DTO imutável para conversão de uma operação de patch em evento.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `proposta: PropostaPatch`, `seq: int`

- `origem() -> OrigemEvento` `[property]` — Origem declarada na proposta ou, na ausência dela, derivada do papel.

### `ConversorPatchParaEventos`

*serviço* — Traduz uma proposta aprovada na sequência de eventos que a representa.

- `converter(proposta: PropostaPatch, seq_base: int) -> tuple[EventoLog, ...]` — Numera e converte cada operação da proposta a partir da sequência base.

## `kernel/execucao.py`

Registro do ciclo de vida de execução de um agente no log compartilhado.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EVENTOS_DE_CICLO_DE_EXECUCAO` | `frozenset[TipoEvento]` | `frozenset({TipoEvento.EXECUCAO_SOLICITADA, TipoEvento.EXECUCAO_INICIADA…` |

### `PedidoDeExecucao`

*DTO imutável* — Fato de ciclo de vida a registrar, com a identidade de quem o observou.

**Campos:** `id_run: str`, `id_sessao: str`, `tipo_evento: TipoEvento`, `autor: str`, `papel: PapelAutor`, `origem: OrigemEvento`, `ramo_id: str`, `dados: Mapping[str, Any]`

- `eh_de_ciclo_de_execucao() -> bool` `[property]` — Recusa qualquer tipo de evento que não pertença a este canal.
- `montar_payload() -> dict[str, Any]` — Payload do evento, com o vínculo à sessão sempre presente.
- `montar_evento(seq: int) -> EventoLog` — Constrói o evento numerado na posição informada do log.

## `kernel/invariant_gate.py`

Portão 3: Validação de Invariantes de Integridade Relacional do Grafo (Invariant Gate).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |

### `InvariantGate`

*serviço* — Portão de validação de invariantes relacionais do grafo.

- `validar(proposta: PropostaPatch, estado: GrafoEstado, locks_ativos: Mapping[str, str] | None) -> ResultadoValidacao` — Executa validação de invariantes de ciclo, questões bloqueantes e locks.

## `kernel/matriz_papeis.py`

Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_EXCLUSIVOS_DO_HUMANO` | `frozenset[TipoNo]` | `frozenset({TipoNo.CONSTRAINT})` |
| `TIPOS_EDITAVEIS_PELO_SISTEMA` | `frozenset[TipoNo]` | `frozenset({TipoNo.RUN, TipoNo.SESSAO})` |
| `TIPOS_CUJA_REMOCAO_EXIGE_HUMANO` | `frozenset[TipoNo]` | `frozenset({TipoNo.CONSTRAINT, TipoNo.QUESTION})` |
| `STATUS_DE_QUESTION_RESERVADOS_AO_HUMANO` | `frozenset[str]` | `frozenset({StatusQuestion.RESPONDIDA.value, StatusQuestion.DESCARTADA.v…` |
| `SO_HUMANO` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.HUMANO})` |
| `HUMANO_E_PLANEJADOR` | `frozenset[PapelAutor]` | `SO_HUMANO | {PapelAutor.PLANEJADOR}` |
| `HUMANO_E_TRABALHO` | `frozenset[PapelAutor]` | `SO_HUMANO | {PapelAutor.EXECUTOR, PapelAutor.REVISOR}` |
| `TODOS_OS_PAPEIS_DE_AGENTE` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVIS…` |
| `HUMANO_E_AGENTES` | `frozenset[PapelAutor]` | `SO_HUMANO | TODOS_OS_PAPEIS_DE_AGENTE` |
| `DONOS_POR_TIPO_DE_ARESTA` | `Mapping[TipoAresta, DonosDeAresta]` | `{TipoAresta.CONTEM: DonosDeAresta(adicao=SO_HUMANO | {PapelAutor.SISTEM…` |
| `ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.ESCOPA})` |

### `DonosDeAresta`

*DTO imutável* — Papéis autorizados a criar e a remover um tipo de aresta.

**Campos:** `adicao: frozenset[PapelAutor]`, `remocao: frozenset[PapelAutor]`

- `autoriza(papel: PapelAutor, eh_remocao: bool) -> bool` — Consulta pura: informa se o papel pode executar a operação pedida.

### Funções do módulo

- `obter_donos_sob_autonomia_ilimitada(tipo: TipoAresta) -> DonosDeAresta` — Donos ampliados de um tipo de aresta dentro de um projeto autônomo.
- `obter_donos_de_aresta(tipo: TipoAresta) -> DonosDeAresta` — Consulta o par de donos de um tipo de aresta, negando o que não foi declarado.
- `descrever_donos_de_aresta(tipo: TipoAresta) -> tuple[str, ...]` — Lista, em ordem estável, os papéis que podem criar o tipo de aresta.

## `kernel/observadores.py`

Notificação pós-commit dos eventos aceitos pelos quatro portões.

### `DespachanteObservadores`

*serviço* — Mantém os observadores registrados e os notifica em ordem de registro.

- `registrar(observador: ObservadorCommit) -> None` — Adiciona um observador ao fim da cadeia de notificação.
- `nomes_registrados() -> tuple[str, ...]` `[property]` — Nomes dos observadores ativos, em ordem de registro.
- `notificar(eventos: Sequence[EventoLog]) -> None` — Entrega o lote a cada observador, isolando a falha de um dos demais.

### `ObservadorCommit` (ABC)

*contrato* — Contrato de quem quer saber dos eventos assim que eles viram história.

- `nome() -> str` `[property]` `[abstract]` — Nome identificador do observador, usado em diagnóstico.
- `notificar(eventos: Sequence[EventoLog]) -> None` `[abstract]` — Recebe o lote de eventos recém-persistido, já validado e ordenado.

## `kernel/patch_models.py`

Modelos imutáveis e sanitizadores para operações JSON Patch (RFC 6902).

### `DadosPropostaPatch`

*DTO imutável* — DTO imutável para dados de criação de PropostaPatch.

**Campos:** `autor: str`, `papel: PapelAutor`, `operacoes: Sequence[ItemPatch]`, `justificativa: str`, `ramo_id: str`, `trace_id: str | None`, `origem: OrigemEvento | None`

### `ItemPatch`

*DTO imutável* — Item individual de operação JSON Patch RFC 6902.

**Campos:** `op: OperacaoPatch`, `path: str`, `value: Any`, `from_path: str | None`

### `OperacaoPatch` (str, Enum)

*serviço* — Operações padrão do RFC 6902.

### `PropostaPatch`

*DTO imutável* — Conjunto de operações de patch submetidas atomicamente por um autor.

**Campos:** `id: str`, `autor: str`, `papel: PapelAutor`, `operacoes: tuple[ItemPatch, ...]`, `justificativa: str`, `ramo_id: str`, `trace_id: str | None`, `origem: OrigemEvento | None`

- `criar(dados: DadosPropostaPatch) -> 'PropostaPatch'` — Fábrica para instanciação com geração de ID único a partir do DTO.

### `ResultadoValidacao`

*DTO imutável* — Resultado detalhado da avaliação de um patch pelos portões do kernel.

**Campos:** `aprovado: bool`, `mensagem_erro: str | None`, `portao_falha: str | None`, `contexto_detalhado: Mapping[str, str]`, `modo: ModoFalhaMAST | None`

- `sucesso() -> 'ResultadoValidacao'` — Cria resultado de aprovação.
- `falha(mensagem: str, portao: str, contexto: Mapping[str, str] | None) -> 'ResultadoValidacao'` — Cria resultado de rejeição com motivo, modo declarado e contexto para LLMs.

### `SanitizadorPatch`

*serviço* — Sanitizador estrito contra injeção de atributos e prototype pollution.

**Campos:** `CHAVES_PROIBIDAS: frozenset[str]`

- `sanitizar_item(item: ItemPatch) -> None` — Verifica se o caminho ou valores contêm propriedades proibidas.

## `kernel/rastreio_projeto.py`

Rastreio do Projeto ancestral de um nó, resistente a ciclos na hierarquia.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PROFUNDIDADE_MAXIMA_DE_SUBIDA` | `int` | `64` |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |

### `RastreadorProjetoAncestral`

*serviço* — Encontra o Projeto que contém um nó, percorrendo as arestas de entrada.

- `rastrear(id_no: str, estado: GrafoEstado) -> str | None` — Consulta iterativa que devolve o identificador do Projeto ancestral, se existir.

### Funções do módulo

- `projetar_lote(operacoes: Sequence[ItemPatch], estado: GrafoEstado) -> GrafoEstado` — Antecipa o estado como se o lote já estivesse aplicado, só para consulta.

## `kernel/role_gate.py`

Portão 2: Validação de Contratos de Permissão por Papel (Role Gate).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |

### `ContextoPapel`

*DTO imutável* — Estado compartilhado por todas as verificações de uma mesma proposta.

**Campos:** `proposta: PropostaPatch`, `estado: GrafoEstado`, `estado_com_lote: GrafoEstado`

### `ContextoPermissaoEdicao`

*DTO imutável* — DTO imutável para parâmetros de validação de permissão de edição.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `contexto: ContextoPapel`

### `RoleGate`

*serviço* — Portão que impõe as regras de permissão de escrita conforme o papel do autor.

**Campos:** `NOS_CRIACAO_PERMITIDOS: dict[PapelAutor, frozenset[TipoNo]]`, `NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA: frozenset[TipoNo]`

- `validar(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao` — Avalia se todas as operações da proposta estão autorizadas para o papel.

### Funções do módulo

- `descrever_tipos_permitidos(papel: PapelAutor) -> tuple[str, ...]` — Consulta auxiliar que lista, em ordem estável, os tipos criáveis por um papel.

## `kernel/schema_gate.py`

Portão 1: Validação de Conformidade Estrutural com a Ontologia (Schema Gate).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_ATE_O_IDENTIFICADOR` | `int` | `2` |

### `ContextoValidacaoNo`

*DTO imutável* — DTO imutável para encapsular os parâmetros de validação do nó.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `estado: GrafoEstado`

### `SchemaGate`

*serviço* — Portão de validação estrutural contra as regras formais da ontologia.

**Campos:** `PARES_ARESTAS_PERMITIDOS: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]]`

- `validar(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao` — Avalia todas as operações do patch contra o schema da ontologia.

## `kernel/telemetria.py`

Descrição dos spans que o kernel emite a cada escrita aceita ou recusada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SISTEMA` | `str` | `'graphow'` |
| `ATRIBUTO_SISTEMA` | `str` | `'gen_ai.system'` |
| `ATRIBUTO_MODELO` | `str` | `'gen_ai.model'` |
| `ATRIBUTO_PAPEL` | `str` | `'agent.role'` |
| `ATRIBUTO_AUTOR` | `str` | `'graphow.autor'` |
| `ATRIBUTO_PATCH` | `str` | `'graphow.patch.id'` |
| `ATRIBUTO_NO` | `str` | `'graphow.no.id'` |
| `ATRIBUTO_RAMO` | `str` | `'graphow.ramo.id'` |
| `ATRIBUTO_PORTAO` | `str` | `'graphow.portao'` |
| `ATRIBUTO_MODO_DE_FALHA` | `str` | `'graphow.modo_de_falha'` |
| `ATRIBUTO_EVENTOS` | `str` | `'graphow.eventos.total'` |
| `ATRIBUTO_RUN` | `str` | `'graphow.run.id'` |
| `ATRIBUTO_SESSAO` | `str` | `'graphow.sessao.id'` |
| `OPERACAO_SUBMETER_PATCH` | `str` | `'graphow.patch.submeter'` |
| `OPERACAO_REGISTRAR_EXECUCAO` | `str` | `'graphow.execucao.registrar'` |

### `FatoDeEscrita`

*DTO imutável* — O desfecho de uma submissão, na forma de que a telemetria precisa.

**Campos:** `sucesso: bool`, `portao: str | None`, `modo_de_falha: str | None`, `eventos_gerados: int`

### Funções do módulo

- `montar_span_de_patch(proposta: PropostaPatch, fato: FatoDeEscrita) -> DadosSpanDTO` — Descreve o span de uma submissão ao PatchBoard, aceita ou recusada.
- `montar_span_de_execucao(pedido: PedidoDeExecucao, sucesso: bool) -> DadosSpanDTO` — Descreve o span de um fato de ciclo de vida vindo do harness.

## `kernel/write_kernel.py`

Kernel de Escrita e Validação Transacional em 4 Portões (PatchBoard).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TENTATIVAS_MAXIMAS_DE_COMMIT` | `int` | `4` |

### `DependenciasKernel`

*DTO imutável* — Colaboradores injetáveis do kernel de escrita.

**Campos:** `schema_gate: SchemaGate | None`, `role_gate: RoleGate | None`, `invariant_gate: InvariantGate | None`, `repositorio_locks: RepositorioLocks | None`, `repositorio_ramos: RepositorioRamos | None`, `tracer: Tracer | None`

### `ResultadoSubmissao`

*DTO imutável* — Recibo imutável do resultado da submissão de um patch ao kernel.

**Campos:** `sucesso: bool`, `mensagem: str`, `versao_log: int`, `eventos_gerados: tuple[str, ...]`, `diagnostico: DiagnosticoFalha | None`

- `modo_de_falha() -> str | None` `[property]` — Modo MAST da rejeicao, para o agente corrigir a proposta sem adivinhar.

### `WriteKernel`

*serviço* — Orquestrador central de mutações por JSON Patch sobre o estado compartilhado.

- `registrar_observador(observador: ObservadorCommit) -> None` — Inscreve um observador para receber os eventos aceitos pelos portões.
- `observadores_registrados() -> tuple[str, ...]` `[property]` — Nomes dos observadores ativos, em ordem de registro.
- `submeter_patch(proposta: PropostaPatch) -> ResultadoSubmissao` — Executa os 4 portões contra o log atual e persiste o lote atomicamente.
- `registrar_execucao(pedido: PedidoDeExecucao) -> ResultadoSubmissao` — Grava um fato de ciclo de vida de execução no log e notifica os observadores.
- `obter_estado(ramo_id: str) -> GrafoEstado` — Consulta a projeção do ramo já reconciliada com o log persistido.
- `obter_view(ramo_id: str) -> GrafoView` — Fornece visão imutável CQRS do grafo.
- `repositorio() -> RepositorioEventos` `[property]` — Repositório de eventos injetado, para colaboradores que leem o log cru.
- `repositorio_ramos() -> RepositorioRamos` `[property]` — Repositório de linhagem de ramos injetado no kernel.
- `obter_evento(id_evento: str) -> EventoLog | None` — Consulta um evento persistido pelo identificador, sem expor o repositório.
- `listar_ramos() -> tuple[str, ...]` — Enumera os ramos existentes no repositório de eventos.
- `obter_dono_do_lock(id_task: str) -> str | None` — Consulta quem detém a escrita exclusiva sobre a tarefa.
- `listar_locks_ativos() -> dict[str, str]` — Instantâneo dos locks vigentes, para consultas que filtram por posse.
- `adquirir_lock_task(id_task: str, autor: str) -> bool` — Adquire lock exclusivo de escrita sobre uma Task para o autor.
- `liberar_lock_task(id_task: str, autor: str) -> bool` — Libera o lock exclusivo caso pertença ao autor solicitante.

