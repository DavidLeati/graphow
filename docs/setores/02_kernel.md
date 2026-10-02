# Setor 02 — Kernel de Escrita (PatchBoard)

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.kernel`

Os quatro portões de governança, a conversão de JSON Patch em eventos e o commit transacional. Único caminho de mutação do estado compartilhado.

## Inventário

22 módulos · 3644 linhas · 29 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`kernel/aceite_pelo_teto.py`](#kernelaceitepeloteto) | 40 | O aceite pelo teto de correções, que libera o fechamento sem veredito aprovado. |
| [`kernel/composicao.py`](#kernelcomposicao) | 49 | Raiz de composição do kernel: monta repositórios e portões numa peça só. |
| [`kernel/conversao_eventos.py`](#kernelconversaoeventos) | 151 | Conversão de operações JSON Patch RFC 6902 em eventos formais do log. |
| [`kernel/estrutura_apos_lote.py`](#kernelestruturaaposlote) | 118 | Hierarquia e origem conferidas no estado depois do lote, e não na lista de criações. |
| [`kernel/execucao.py`](#kernelexecucao) | 70 | Registro do ciclo de vida de execução de um agente no log compartilhado. |
| [`kernel/forma_e_identidade.py`](#kernelformaeidentidade) | 158 | Forma e identidade de cada operação do lote, conferidas pelo SchemaGate antes dos outros portões. |
| [`kernel/gestos_de_no.py`](#kernelgestosdeno) | 191 | Gestos de governança que o RoleGate aplica aos nós: quem os faz é decidido pela política do projeto. |
| [`kernel/invariant_gate.py`](#kernelinvariantgate) | 356 | Portão 3: Validação de Invariantes de Integridade Relacional do Grafo (Invariant Gate). |
| [`kernel/localizacao.py`](#kernellocalizacao) | 157 | Localização de uma Evidence de leitura de código: arquivo, faixa de linhas e trecho literal. |
| [`kernel/matriz_papeis.py`](#kernelmatrizpapeis) | 251 | Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo. |
| [`kernel/observadores.py`](#kernelobservadores) | 54 | Notificação pós-commit dos eventos aceitos pelos quatro portões. |
| [`kernel/patch_models.py`](#kernelpatchmodels) | 178 | Modelos imutáveis e sanitizadores para operações JSON Patch (RFC 6902). |
| [`kernel/permissao_de_aresta.py`](#kernelpermissaodearesta) | 292 | Permissão por papel na camada de arestas: quem cria e remove cada aresta, conforme o que ela liga. |
| [`kernel/politica_governanca.py`](#kernelpoliticagovernanca) | 56 | Resolve a política de governança efetiva lendo o estado do grafo. |
| [`kernel/rastreio_projeto.py`](#kernelrastreioprojeto) | 143 | Rastreio do Projeto ancestral de um nó, resistente a ciclos na hierarquia. |
| [`kernel/role_gate.py`](#kernelrolegate) | 384 | Portão 2: Validação de Contratos de Permissão por Papel (Role Gate). |
| [`kernel/schema_gate.py`](#kernelschemagate) | 382 | Portão 1: Validação de Conformidade Estrutural com a Ontologia (Schema Gate). |
| [`kernel/telemetria.py`](#kerneltelemetria) | 102 | Descrição dos spans que o kernel emite a cada escrita aceita ou recusada. |
| [`kernel/veredito_de_fechamento.py`](#kernelvereditodefechamento) | 120 | Quem fecha uma Task precisa de revisão aprovada: a regra do kernel, fora da política. |
| [`kernel/veredito_reservado.py`](#kernelvereditoreservado) | 56 | A propriedade `veredito` de uma Evidence é de quem julga: revisor, humano ou árbitro. |
| [`kernel/write_kernel.py`](#kernelwritekernel) | 309 | Kernel de Escrita e Validação Transacional em 4 Portões (PatchBoard). |

## `kernel/aceite_pelo_teto.py`

O aceite pelo teto de correções, que libera o fechamento sem veredito aprovado.

### Funções do módulo

- `aceite_libera_o_fechamento(view: GrafoView, id_task: str) -> bool` — Alguma Decision de aceite legítima orienta a Task e justifica-se pelo veredito vigente dela.

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
| `SEGMENTOS_DO_ELEMENTO_INTEIRO` | `int` | `2` |
| `SEGMENTOS_DE_UMA_PROPRIEDADE` | `int` | `4` |
| `MARCADOR_DE_ID` | `str` | `'<id>'` |
| `MARCADOR_DE_CHAVE` | `str` | `'<chave>'` |
| `OPERACOES_POR_FORMA` | `Mapping[tuple[str, ...], frozenset[OperacaoPatch]]` | `{(SEGMENTO_NOS, MARCADOR_DE_ID): frozenset({OperacaoPatch.ADD, Operacao…` |

### `ContextoConversaoEvento`

*DTO imutável* — DTO imutável para conversão de uma operação de patch em evento.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `proposta: PropostaPatch`, `seq: int`

- `origem() -> OrigemEvento` `[property]` — Origem declarada na proposta ou, na ausência dela, derivada do papel.

### `ConversorPatchParaEventos`

*serviço* — Traduz uma proposta aprovada na sequência de eventos que a representa.

- `converter(proposta: PropostaPatch, seq_base: int) -> tuple[EventoLog, ...]` — Numera e converte cada operação da proposta a partir da sequência base.

### Funções do módulo

- `forma_do_caminho(segmentos: Sequence[str]) -> tuple[str, ...]` — O caminho com o id do elemento e a chave da propriedade trocados por marcadores.
- `grava_como_diz(segmentos: Sequence[str], op: OperacaoPatch) -> bool` — Diz se o conversor grava a operação neste caminho como ela é, sem reinterpretá-la.

## `kernel/estrutura_apos_lote.py`

Hierarquia e origem conferidas no estado depois do lote, e não na lista de criações.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |
| `TIPOS_RAIZ` | `frozenset[TipoNo]` | `frozenset({TipoNo.PROJETO, TipoNo.GOVERNANCA})` |

### `EstruturaAposLote`

*DTO imutável* — O grafo antes e depois do lote, com o que o lote criou.

**Campos:** `antes: GrafoEstado`, `depois: GrafoEstado`, `criados: frozenset[str]`, `desliga_existentes: bool`

- `antever(proposta: PropostaPatch, estado: GrafoEstado) -> 'EstruturaAposLote'` — Aplica o lote inteiro sobre o estado, só para consulta.
- `nos_fora_da_hierarquia() -> tuple[str, ...]` — Nós que o lote cria, ou de que o agente tira a contenção, e ficam sem pai.
- `aprendizados_sem_origem() -> tuple[str, ...]` — Aprendizados que o lote cria, ou de que o agente tira a origem, e ficam sem `deriva_de`.

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

## `kernel/forma_e_identidade.py`

Forma e identidade de cada operação do lote, conferidas pelo SchemaGate antes dos outros portões.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PORTAO` | `str` | `'SchemaGate'` |
| `SEGMENTOS_ATE_O_IDENTIFICADOR` | `int` | `2` |
| `COLECAO_DE_NOS` | `str` | `'nos'` |
| `COLECOES` | `frozenset[str]` | `frozenset({COLECAO_DE_NOS, 'arestas'})` |
| `FORMAS_ACEITAS` | `str` | `'; '.join((f"{', '.join(sorted((op.value for op in operacoes)))} em /{'…` |

### `ContextoValidacaoNo`

*DTO imutável* — DTO imutável para encapsular os parâmetros de validação do nó.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `estado: GrafoEstado`

### `CriadosNoLote`

*serviço* — O que as operações anteriores do mesmo lote já criaram, na ordem do lote.

**Campos:** `nos: dict[str, TipoNo]`, `arestas: set[str]`

- `contem(colecao: str, id_elemento: str, estado: GrafoEstado) -> bool` — Diz se o id já está no grafo ou foi criado antes neste lote.

### Funções do módulo

- `validar_caminho(item: ItemPatch, segmentos: tuple[str, ...]) -> ResultadoValidacao` — O caminho nomeia um nó ou uma aresta, numa forma que o log grava como ela é.
- `validar_identidade(ctx: ContextoValidacaoNo, criados: CriadosNoLote) -> ResultadoValidacao` — O valor cria o elemento que o caminho nomeia, e esse id ainda não existe.

## `kernel/gestos_de_no.py`

Gestos de governança que o RoleGate aplica aos nós: quem os faz é decidido pela política do projeto.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMINHO_DO_STATUS` | `str` | `'/propriedades/status'` |

### `ContextoPermissaoEdicao`

*DTO imutável* — DTO imutável para parâmetros de validação de permissão de edição.

**Campos:** `segmentos: Sequence[str]`, `item: ItemPatch`, `contexto: ContextoPapel`

### `GestosDeNo`

*serviço* — Aplica os gestos da política de governança às operações sobre nós.

- `politica_do_no(id_no: str, contexto: ContextoPapel) -> PoliticaGovernanca` — Política efetiva do projeto do nó, lida só do estado do grafo.
- `exigir(gesto: Gesto, id_no: str, contexto: ContextoPapel) -> ResultadoValidacao` — Aprova se a política do projeto do nó entrega o gesto ao papel; senão diz qual falta.
- `validar_status_na_criacao(tipo_no: TipoNo, item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao` — Goal nascido concluído e Sessão nascida encerrada passam pelo gesto que os fecharia.
- `validar_tipo_exclusivo(no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao` — Constraint e Governanca são do humano; o gesto `constraint` abre o primeiro ao árbitro.
- `validar_exclusao(no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao` — A exclusão que o gesto `excluir` entrega ao árbitro, menos a da Question que ele abriu.
- `recusar_remocao(no: NoGrafo, ctx: ContextoPermissaoEdicao, motivo: str) -> ResultadoValidacao` — Diz que o papel não remove aquele tipo de nó, e por quê.
- `validar_encerramento_de_questao(no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao` — Encerrar a Question é o gesto `responder_questao`: do humano, ou do árbitro se a política o entrega.
- `recusar_encerramento_de_questao(id_questao: str, papel: PapelAutor, politica: PoliticaGovernanca | None) -> ResultadoValidacao` — Explica que só a resposta do humano, ou do árbitro que a política autoriza, encerra a dúvida.
- `validar_status_que_exige_gesto(no: NoGrafo, ctx: ContextoPermissaoEdicao) -> ResultadoValidacao` — Fechar um Goal e encerrar uma Sessão, por escrita de status, são gestos da política.

## `kernel/invariant_gate.py`

Portão 3: Validação de Invariantes de Integridade Relacional do Grafo (Invariant Gate).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |
| `ARESTAS_QUE_REDEFINEM_A_TAREFA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DEPENDE_DE, TipoAresta.DECOMPOE, TipoAresta.ORIEN…` |
| `VINCULO_DE_TRABALHO` | `str` | `"'produz' vinda de uma Sessao"` |
| `VINCULO_ESPERADO` | `Mapping[TipoNo, str]` | `{TipoNo.SETOR: "'contem' vinda de um Projeto", TipoNo.SESSAO: "'contem'…` |

### `InvariantGate`

*serviço* — Portão de validação de invariantes relacionais do grafo.

- `validar(proposta: PropostaPatch, estado: GrafoEstado, locks_ativos: Mapping[str, str] | None) -> ResultadoValidacao` — Executa validação de invariantes de ciclo, questões bloqueantes e locks.

## `kernel/localizacao.py`

Localização de uma Evidence de leitura de código: arquivo, faixa de linhas e trecho literal.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_ARQUIVO` | `str` | `'arquivo'` |
| `CAMPO_LINHAS` | `str` | `'linhas'` |
| `CAMPO_TRECHO` | `str` | `'trecho'` |
| `CAMPOS_QUE_DECLARAM_PONTEIRO` | `tuple[str, ...]` | `(CAMPO_LINHAS, CAMPO_TRECHO)` |
| `PADRAO_DE_FAIXA` | `re.Pattern[str]` | `re.compile('^\\s*(\\d+)\\s*(?:[-–]\\s*(\\d+)\\s*)?$')` |

### `EvidenciaNoLote`

*DTO imutável* — Uma Evidence que o lote cria ou edita, como ela ficará gravada depois dele.

**Campos:** `id: str`, `papel_de_quem_criou: str`, `propriedades: Mapping[str, Any]`

- `exige_localizacao() -> bool` `[property]` — Do planejador, sempre; de qualquer papel, quando cita linhas ou trecho.

### `FaixaDeLinhas`

*DTO imutável* — Linhas de início e fim, as duas inclusivas e contadas a partir de 1.

**Campos:** `inicio: int`, `fim: int`

- `total() -> int` `[property]` — Quantas linhas a faixa cobre.

### Funções do módulo

- `interpretar_faixa(valor: object) -> FaixaDeLinhas | None` — Lê `linhas` como faixa; None quando a forma não descreve linhas de arquivo.
- `contar_linhas(trecho: str) -> int` — Linhas como o editor as conta: só quebra de linha separa, e a quebra final não abre linha nova.
- `diagnosticar_localizacao(propriedades: Mapping[str, Any]) -> str | None` — O que falta ou está errado no ponteiro; None quando ele está inteiro.
- `projetar_evidencias_do_lote(proposta: PropostaPatch, estado: GrafoEstado) -> tuple[EvidenciaNoLote, ...]` — As Evidence que o lote toca, depois de convertidas e aplicadas como o kernel as gravaria.

## `kernel/matriz_papeis.py`

Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_EXCLUSIVOS_DO_HUMANO` | `frozenset[TipoNo]` | `frozenset({TipoNo.CONSTRAINT, TipoNo.GOVERNANCA})` |
| `TIPOS_EDITAVEIS_PELO_SISTEMA` | `frozenset[TipoNo]` | `frozenset({TipoNo.RUN, TipoNo.SESSAO})` |
| `TIPOS_CUJA_REMOCAO_EXIGE_HUMANO` | `frozenset[TipoNo]` | `frozenset({TipoNo.CONSTRAINT, TipoNo.QUESTION, TipoNo.APRENDIZADO})` |
| `PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO` | `frozenset[str]` | `frozenset({'alcance'})` |
| `STATUS_DE_QUESTION_ESCRITOS_POR_AGENTES` | `frozenset[str]` | `frozenset({StatusQuestion.ABERTA.value})` |
| `PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO` | `frozenset[str]` | `frozenset({'nivel_autonomia', PROPRIEDADE_GOVERNANCA_DO_PROJETO})` |
| `STATUS_DE_QUESTION_ESCRITOS_PELO_ARBITRO` | `frozenset[str]` | `frozenset({StatusQuestion.RESPONDIDA.value, StatusQuestion.DESCARTADA.v…` |
| `STATUS_QUE_FECHA_GOAL` | `str` | `StatusTask.CONCLUIDO.value` |
| `STATUS_QUE_ENCERRA_SESSAO` | `str` | `StatusSessao.CONCLUIDA.value` |
| `TIPOS_LIBERADOS_POR_GESTO` | `Mapping[TipoNo, Gesto]` | `{TipoNo.CONSTRAINT: Gesto.CONSTRAINT}` |
| `PAPEIS_QUE_JULGAM` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.REVISOR, PapelAutor.HUMANO, PapelAutor.ARBITRO})` |
| `PAPEIS_QUE_ACEITAM_A_ENTREGA` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.PLANEJADOR, PapelAutor.HUMANO, PapelAutor.ARBITRO…` |
| `SEPARADOR_DO_SUFIXO_DE_CONEXAO` | `str` | `'#'` |
| `SO_HUMANO` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.HUMANO})` |
| `HUMANO_E_PLANEJADOR` | `frozenset[PapelAutor]` | `SO_HUMANO | {PapelAutor.PLANEJADOR}` |
| `HUMANO_E_TRABALHO` | `frozenset[PapelAutor]` | `SO_HUMANO | {PapelAutor.EXECUTOR, PapelAutor.REVISOR}` |
| `QUEM_JUSTIFICA` | `frozenset[PapelAutor]` | `HUMANO_E_TRABALHO | {PapelAutor.PLANEJADOR}` |
| `TODOS_OS_PAPEIS_DE_AGENTE` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVIS…` |
| `HUMANO_E_AGENTES` | `frozenset[PapelAutor]` | `SO_HUMANO | TODOS_OS_PAPEIS_DE_AGENTE` |
| `DONOS_POR_TIPO_DE_ARESTA` | `Mapping[TipoAresta, DonosDeAresta]` | `{TipoAresta.CONTEM: DonosDeAresta(adicao=SO_HUMANO | {PapelAutor.SISTEM…` |
| `PARES_DO_GESTO_PROMOVER_APRENDIZADO` | `frozenset[tuple[TipoNo, TipoNo]]` | `frozenset({(TipoNo.APRENDIZADO, TipoNo.SETOR), (TipoNo.APRENDIZADO, Tip…` |
| `DONOS_POR_PAR_DE_ARESTA` | `Mapping[tuple[TipoAresta, TipoNo, TipoNo], DonosDeAresta]` | `{(TipoAresta.SUBSTITUI, TipoNo.APRENDIZADO, TipoNo.APRENDIZADO): DonosD…` |
| `ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.ESCOPA, TipoAresta.VALE_PARA})` |

### `DonosDeAresta`

*DTO imutável* — Papéis autorizados a criar e a remover um tipo de aresta.

**Campos:** `adicao: frozenset[PapelAutor]`, `remocao: frozenset[PapelAutor]`

- `autoriza(papel: PapelAutor, eh_remocao: bool) -> bool` — Consulta pura: informa se o papel pode executar a operação pedida.

### Funções do módulo

- `papel_julga(papel: str) -> bool` — O papel gravado na proveniência de um nó é de quem julga, e seu veredito conta.
- `papel_aceita_a_entrega(papel: str) -> bool` — O papel gravado na proveniência de um nó é de quem pode aceitar a entrega pelo teto.
- `autor_sem_sufixo_de_conexao(autor: str) -> str` — O autor sem o sufixo `#xxxx` que a conexão acrescenta para ter posse própria.
- `eh_autoria_propria(autor_da_proposta: str, aberta_por: object) -> bool` — Diz se quem propõe é quem abriu a dúvida, comparando sem o sufixo da conexão.
- `gesto_da_aresta(tipo: TipoAresta, par: tuple[TipoNo, TipoNo] | None, eh_remocao: bool) -> Gesto | None` — O gesto de governança que decide a operação sobre a aresta, ou None se a tabela decide sozinha.
- `obter_donos_sob_autonomia_ilimitada(tipo: TipoAresta, par: tuple[TipoNo, TipoNo] | None) -> DonosDeAresta` — Donos ampliados de um tipo de aresta dentro de um projeto autônomo.
- `obter_donos_de_aresta(tipo: TipoAresta, par: tuple[TipoNo, TipoNo] | None) -> DonosDeAresta` — Consulta os donos de um tipo de aresta, negando o que não foi declarado.
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

## `kernel/permissao_de_aresta.py`

Permissão por papel na camada de arestas: quem cria e remove cada aresta, conforme o que ela liga.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |

### `ContextoPapel`

*DTO imutável* — Estado compartilhado por todas as verificações de uma mesma proposta.

**Campos:** `proposta: PropostaPatch`, `estado: GrafoEstado`, `estado_com_lote: GrafoEstado`

### `PermissaoDeAresta`

*serviço* — Aplica a matriz de donos de aresta à operação de um lote, sob o papel do autor.

- `validar(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao` — Consulta a matriz de donos de aresta para a operação e o papel correntes.
- `validar_remocao(aresta: ArestaGrafo, contexto: ContextoPapel) -> ResultadoValidacao` — Julga a remoção pela aresta como ela está no grafo, nunca pelo valor enviado.
- `validar_remocao_em_cascata(id_no: str, contexto: ContextoPapel) -> ResultadoValidacao` — Remover um nó leva junto as arestas dele, e cada uma exige o poder de removê-la.

### Funções do módulo

- `descrever_reserva_do_gesto(gesto: Gesto, politica: PoliticaGovernanca) -> str` — Diz de quem é o gesto na política do projeto, para a recusa nomear o que falta.

## `kernel/politica_governanca.py`

Resolve a política de governança efetiva lendo o estado do grafo.

### Funções do módulo

- `resolver_politica_global(estado: GrafoEstado) -> PoliticaGovernanca` — Política global: a do nó `governanca-global`, ou governança máxima se ele não existe.
- `resolver_politica_do_projeto(id_projeto: str, estado: GrafoEstado) -> PoliticaGovernanca` — Política efetiva do Projeto, com a herança da global e o legado `nivel_autonomia`.
- `resolver_politica_do_no(id_no: str, estado: GrafoEstado, rastreador: RastreadorProjetoAncestral) -> PoliticaGovernanca` — Política efetiva do Projeto que contém o nó; sem Projeto ancestral, a global.

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
| `SEGMENTOS_DE_UMA_PROPRIEDADE` | `int` | `4` |

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
| `SEGMENTOS_ATE_A_CHAVE` | `int` | `4` |

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

## `kernel/veredito_de_fechamento.py`

Quem fecha uma Task precisa de revisão aprovada: a regra do kernel, fora da política.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DE_ELEMENTO_INTEIRO` | `int` | `2` |
| `SEGMENTOS_DA_PROPRIEDADE` | `int` | `4` |
| `CAMPO_STATUS` | `str` | `'status'` |

### Funções do módulo

- `tarefas_sem_veredito_aprovado(proposta: PropostaPatch, estrutura: EstruturaAposLote) -> tuple[str, ...]` — As Tasks que o lote conclui sem veredito efetivo `aprovado` nem aceite pelo teto.

## `kernel/veredito_reservado.py`

A propriedade `veredito` de uma Evidence é de quem julga: revisor, humano ou árbitro.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGMENTOS_DA_PROPRIEDADE` | `int` | `4` |

### Funções do módulo

- `validar_escrita_de_veredito(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao` — Recusa o papel que não julga quando a operação escreve ou remove o veredito de uma Evidence.

## `kernel/write_kernel.py`

Kernel de Escrita e Validação Transacional em 4 Portões (PatchBoard).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TENTATIVAS_MAXIMAS_DE_COMMIT` | `int` | `10` |
| `ESPERA_BASE_ENTRE_TENTATIVAS_S` | `float` | `0.005` |
| `ESPERA_MAXIMA_ENTRE_TENTATIVAS_S` | `float` | `0.5` |

### `DependenciasKernel`

*DTO imutável* — Colaboradores injetáveis do kernel de escrita.

**Campos:** `schema_gate: SchemaGate | None`, `role_gate: RoleGate | None`, `invariant_gate: InvariantGate | None`, `repositorio_locks: RepositorioLocks | None`, `repositorio_ramos: RepositorioRamos | None`, `tracer: Tracer | None`, `repositorio_instantaneos: RepositorioInstantaneos | None`

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
- `obter_view(ramo_id: str) -> GrafoView` — Fornece visão imutável CQRS do grafo, com o índice de rollup do ramo.
- `repositorio() -> RepositorioEventos` `[property]` — Repositório de eventos injetado, para colaboradores que leem o log cru.
- `repositorio_ramos() -> RepositorioRamos` `[property]` — Repositório de linhagem de ramos injetado no kernel.
- `obter_evento(id_evento: str) -> EventoLog | None` — Consulta um evento persistido pelo identificador, sem expor o repositório.
- `listar_ramos() -> tuple[str, ...]` — Enumera os ramos existentes no repositório de eventos.
- `obter_dono_do_lock(id_task: str) -> str | None` — Consulta quem detém a escrita exclusiva sobre a tarefa.
- `listar_locks_ativos() -> dict[str, str]` — Instantâneo dos locks vigentes, para consultas que filtram por posse.
- `adquirir_lock_task(id_task: str, autor: str) -> bool` — Adquire lock exclusivo de escrita sobre uma Task para o autor.
- `liberar_lock_task(id_task: str, autor: str) -> bool` — Libera o lock exclusivo caso pertença ao autor solicitante.
- `transferir_lock_task(id_task: str, de: str, para: str) -> bool` — Passa o lock da Task de um autor a outro, se o primeiro ainda o detiver.

### Funções do módulo

- `esperar_antes_de_repetir(tentativa: int) -> None` — Recuo exponencial com sorteio completo: entre zero e o teto da tentativa.

