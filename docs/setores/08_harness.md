# Setor 08 — Integração com Harness

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.harness`

Ponto de entrada para hooks de ambiente registrarem sessões e execuções, sob identidade fixada na configuração.

## Inventário

15 módulos · 1802 linhas · 20 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`harness/ambiente_padrao.py`](#harnessambientepadrao) | 205 | O ambiente padrão da memória: o Projeto do repositório e o Setor `Memoria` dentro dele. |
| [`harness/consumo_do_disparo.py`](#harnessconsumododisparo) | 83 | O que cada disparo do hook acrescenta ao Run: o consumo lido da transcrição e quem executou. |
| [`harness/convention_adapter.py`](#harnessconventionadapter) | 87 | Adaptador de fallback baseado em convenção de chamada explícita. |
| [`harness/entrada_hook.py`](#harnessentradahook) | 130 | Leitura do JSON que o ambiente entrega na entrada padrão do hook. |
| [`harness/forma_da_transcricao.py`](#harnessformadatranscricao) | 207 | A forma do contexto de uma execução: quanto cada turno carregou, o que as ferramentas devolveram, onde parou e o que leu. |
| [`harness/hook_adapter.py`](#harnesshookadapter) | 87 | Adaptador de ciclo de vida via hooks de harness (ex: Claude Code / IDE). |
| [`harness/identidade_harness.py`](#harnessidentidadeharness) | 30 | Identidade sob a qual um harness registra sessões e execuções no grafo. |
| [`harness/interfaces.py`](#harnessinterfaces) | 43 | Interface abstrata para adaptadores de ciclo de vida do harness. |
| [`harness/leitura_por_shell.py`](#harnessleituraporshell) | 110 | Os caminhos que um comando de shell lê, tirados do texto do comando por heurística conservadora. |
| [`harness/linha_de_cota.py`](#harnesslinhadecota) | 53 | A linha `Cota: 5h <n>%, semana <n>%` que a raiz escreve, lida de volta da transcrição. |
| [`harness/repositorio.py`](#harnessrepositorio) | 60 | Do diretório de trabalho ao nome do projeto: o repositório é a unidade natural da memória. |
| [`harness/retomada.py`](#harnessretomada) | 197 | A vista de retomada: o que o hook de início imprime para o agente ler antes de trabalhar. |
| [`harness/servico_harness.py`](#harnessservicoharness) | 176 | Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução. |
| [`harness/transcricao.py`](#harnesstranscricao) | 315 | O consumo de uma execução lido da transcrição que o ambiente grava: tokens, modelos e tarefas. |

## `harness/ambiente_padrao.py`

O ambiente padrão da memória: o Projeto do repositório e o Setor `Memoria` dentro dele.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ROTULO_DO_SETOR_DE_MEMORIA` | `str` | `'Memoria'` |
| `DESCRICAO_DO_SETOR_DE_MEMORIA` | `str` | `'Ambiente padrao da memoria: as sessoes do harness, seus fechamentos, c…` |
| `PREFIXO_DE_PROJETO` | `str` | `'proj'` |
| `PREFIXO_DE_SETOR` | `str` | `'setor'` |
| `SUFIXO_DO_SETOR_DE_MEMORIA` | `str` | `'memoria'` |
| `SLUG_RESERVA` | `str` | `'projeto'` |
| `RAMO_PADRAO` | `str` | `'main'` |
| `_NAO_ALFANUMERICO` | `re.Pattern[str]` | `re.compile('[^a-z0-9]+')` |

### `AmbientePadrao`

*DTO imutável* — Os identificadores e rótulos do ambiente padrão de um repositório.

**Campos:** `nome_do_projeto: str`

- `do_diretorio(diretorio: str) -> 'AmbientePadrao'` — Deriva do diretório de trabalho; vazio significa o diretório corrente do processo.
- `slug() -> str` `[property]` — A forma do nome que entra nos identificadores.
- `id_projeto() -> str` `[property]` — Id derivado do Projeto do ambiente, usado ao criá-lo quando nenhum outro nó o ocupa.
- `id_setor() -> str` `[property]` — Id derivado do Setor de memória do repositório, com a mesma regra de ocupação.
- `rotulo_do_projeto() -> str` `[property]` — O Projeto se chama como a pasta do repositório.
- `rotulo_do_setor() -> str` `[property]` — O Setor de memória tem o mesmo rótulo em todo repositório.

### `GarantidorDeAmbientePadrao`

*serviço* — Garante que o Projeto e o Setor de memória existem, criando só o que falta.

- `garantir(ambiente: AmbientePadrao, ramo_id: str) -> str` — Devolve o id do Setor de memória; vazio quando o grafo recusou criá-lo.

### `IdsDoAmbiente`

*DTO imutável* — Os ids com que o ambiente nasce: os derivados do nome ou, ocupados, os primeiros livres depois deles.

**Campos:** `id_projeto: str`, `id_setor: str`

- `reservar(ambiente: AmbientePadrao, projeto: NoGrafo | None, view: GrafoView) -> 'IdsDoAmbiente'` — Mantém o Projeto já achado e procura id livre para o que ainda vai nascer.

### Funções do módulo

- `gerar_slug(texto: str) -> str` — Identificador estável a partir de um nome: minúsculas e hífens, sem acento nem espaço.
- `primeiro_id_livre(base: str, view: GrafoView) -> str` — O id derivado, se nenhum nó o usa; senão o primeiro `<id>-2`, `<id>-3`... livre.
- `localizar_projeto(ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None` — O ambiente do repositório entre os que o hook criou: pelo id derivado ou pelo nome da pasta.
- `localizar_setor_de_memoria(projeto: NoGrafo, ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None` — O Setor de memória do Projeto: pelo id derivado ou pelo rótulo `Memoria`.
- `montar_operacoes_do_ambiente(ambiente: AmbientePadrao, ids: IdsDoAmbiente) -> tuple[ItemPatch, ...]` — O Projeto, se ainda não existe, e o Setor de memória pendurado nele no mesmo lote.

## `harness/consumo_do_disparo.py`

O que cada disparo do hook acrescenta ao Run: o consumo lido da transcrição e quem executou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPO_DE_AGENTE_DESCONHECIDO` | `str` | `'subagente'` |
| `MOTIVO_SEM_AGENT_ID` | `str` | `'sem_agent_id'` |
| `MOTIVO_SEM_TRANSCRIPT_PATH` | `str` | `'sem_transcript_path'` |

### Funções do módulo

- `ler_disparo(fase: FaseDoHarness, entrada: EntradaDeHook) -> LeituraDaTranscricao` — No fim da sessão, a transcrição dela; no fim de um subagente, a dele; nas outras fases, nada.
- `ler_consumo_do_disparo(fase: FaseDoHarness, entrada: EntradaDeHook) -> ConsumoDaTranscricao | None` — Só o consumo do disparo, para quem não precisa do motivo.
- `descrever_disparo(fase: FaseDoHarness, entrada: EntradaDeHook, consumo: ConsumoDaTranscricao | None) -> dict[str, Any]` — As propriedades extras do Run; sem transcrição legível, o Run fica sem tokens, não com zero, e diz por quê.

## `harness/convention_adapter.py`

Adaptador de fallback baseado em convenção de chamada explícita.

### `ConventionHarnessAdapter` (AdaptadorDeHarness)

*serviço* — Adaptador agnóstico para ambientes sem suporte a hooks de ciclo de vida nativos.

- `registrar_inicio_sessao(id_sessao: str, id_setor: str, metadados: Mapping[str, Any] | None) -> bool` — Cria o nó de Sessao no grafo, pendurado no Setor por 'contem'.
- `registrar_fim_sessao(id_sessao: str, resumo: str) -> bool` — Atualiza a sessão como concluída.
- `registrar_reabertura_sessao(id_sessao: str) -> bool` — Devolve a sessão a `ativa` quando o ambiente a retoma depois de concluída.
- `registrar_execucao_run(id_sessao: str, modelo: str, dados_execucao: Mapping[str, Any]) -> str` — Registra nó Run simplificado, pendurado na Sessao por 'produz'.

## `harness/entrada_hook.py`

Leitura do JSON que o ambiente entrega na entrada padrão do hook.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVE_SESSAO` | `str` | `'session_id'` |
| `CHAVE_MODELO` | `str` | `'model'` |
| `CHAVE_DIRETORIO` | `str` | `'cwd'` |
| `CHAVES_DE_IDENTIFICACAO_DO_MODELO` | `tuple[str, ...]` | `('id', 'display_name')` |
| `CHAVES_DE_MOTIVO` | `tuple[str, ...]` | `('reason', 'source', 'hook_event_name')` |
| `CHAVE_TRANSCRICAO` | `str` | `'transcript_path'` |
| `CHAVE_TRANSCRICAO_DO_AGENTE` | `str` | `'agent_transcript_path'` |
| `CHAVE_ID_AGENTE` | `str` | `'agent_id'` |
| `CHAVE_TIPO_AGENTE` | `str` | `'agent_type'` |
| `MODELO_DESCONHECIDO` | `str` | `'desconhecido'` |

### `EntradaDeHook`

*DTO imutável* — Os campos do payload do hook que o Graphow aproveita.

**Campos:** `id_sessao: str`, `modelo: str`, `motivo: str`, `diretorio: str`, `transcricao: str`, `transcricao_do_agente: str`, `id_agente: str`, `tipo_agente: str`

- `tem_sessao() -> bool` `[property]` — Informa se a entrada trouxe um identificador de sessão utilizável.
- `caminhos_de_transcricao() -> dict[str, str]` — Os caminhos como o ambiente os nomeia, para quem procura a transcrição de um subagente.

### Funções do módulo

- `interpretar_entrada_de_hook(texto: str) -> EntradaDeHook` — Converte o corpo do hook em DTO, tolerando entrada ausente ou malformada.
- `ler_entrada_de_hook(fonte: IO[str]) -> EntradaDeHook` — Lê e interpreta o payload do hook a partir de um fluxo de texto.
- `preparar_fluxos_do_hook(entrada: IO[str] | None, saida: IO[str] | None) -> None` — Põe a entrada e a saída padrão em UTF-8: o ambiente fala UTF-8, e o Windows abre os canos em cp1252.

## `harness/forma_da_transcricao.py`

A forma do contexto de uma execução: quanto cada turno carregou, o que as ferramentas devolveram, onde parou e o que leu.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVES_DE_CONTEXTO` | `tuple[str, ...]` | `('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_token…` |
| `LIMITE_DE_SAIDA_GRANDE` | `int` | `2000` |
| `PAUSA_LONGA_S` | `int` | `300` |
| `LIMITE_DE_CAMINHOS_LIDOS` | `int` | `200` |
| `CAMPO_DE_CAMINHO_POR_FERRAMENTA` | `Mapping[str, str]` | `{'Read': 'file_path', 'Grep': 'path', 'Glob': 'path'}` |
| `FERRAMENTAS_DE_SHELL` | `frozenset[str]` | `frozenset({'Bash', 'PowerShell'})` |
| `CAMPO_DO_COMANDO` | `str` | `'command'` |
| `SEPARADOR_DO_NOME_MCP` | `str` | `'__'` |
| `FERRAMENTA_DESCONHECIDA` | `str` | `'?'` |
| `CAMPO_CONTEXTO_MEDIO` | `str` | `'contexto_medio_turno'` |
| `CAMPO_CONTEXTO_MAXIMO` | `str` | `'contexto_maximo_turno'` |
| `CAMPO_MAIOR_SAIDA` | `str` | `'maior_saida_ferramenta'` |
| `CAMPO_SAIDAS_GRANDES` | `str` | `'saidas_acima_2000'` |
| `CAMPO_PAUSAS_LONGAS` | `str` | `'pausas_acima_5min'` |
| `CAMPO_MAIOR_PAUSA` | `str` | `'maior_pausa_s'` |
| `CAMPO_CAMINHOS_LIDOS` | `str` | `'caminhos_lidos'` |
| `CAMPO_CAMINHOS_LIDOS_SHELL` | `str` | `'caminhos_lidos_shell'` |
| `CAMPO_SAIDAS_GRANDES_POR_FERRAMENTA` | `str` | `'saidas_grandes_por_ferramenta'` |

### `AcumuladorDeForma`

*serviço* — Junta, entrada por entrada, o que dá a forma do contexto; o contexto por turno vem dos usos já deduplicados.

- `registrar_resposta(identificador: str, instante: datetime | None, conteudo: object) -> None` — O instante de um bloco da resposta do modelo e os caminhos que as chamadas dele leem.
- `registrar_resultados(conteudo: object) -> None` — O tamanho do texto de cada resposta de ferramenta, uma vez por chamada respondida.
- `consolidar(usos: Iterable[Mapping[str, Any]]) -> FormaDoContexto` — A forma do que foi registrado, com o contexto de cada mensagem do modelo.

### `FormaDoContexto`

*DTO imutável* — O contexto de cada turno, o tamanho de cada saída de ferramenta, as pausas e os caminhos lidos.

**Campos:** `contextos: tuple[int, ...]`, `saidas_de_ferramenta: tuple[int, ...]`, `pausas_s: tuple[int, ...]`, `caminhos_lidos: tuple[str, ...]`, `caminhos_lidos_shell: tuple[str, ...]`, `ferramentas_das_saidas: tuple[str, ...]`

- `em_propriedades() -> dict[str, Any]` — As propriedades do Run, cada grupo só quando a transcrição trouxe o dado.

### `_JanelaDaMensagem`

*serviço* — O primeiro e o último instante em que os blocos de uma mesma mensagem foram gravados.

**Campos:** `inicio: datetime`, `fim: datetime`

## `harness/hook_adapter.py`

Adaptador de ciclo de vida via hooks de harness (ex: Claude Code / IDE).

### `HookHarnessAdapter` (AdaptadorDeHarness)

*serviço* — Captura eventos de lifecycle automáticos via hooks e traduz para patches no kernel.

- `registrar_inicio_sessao(id_sessao: str, id_setor: str, metadados: Mapping[str, Any] | None) -> bool` — Emite patch de criação de Sessao e aresta 'contem' a partir do Setor.
- `registrar_fim_sessao(id_sessao: str, resumo: str) -> bool` — Conclui a sessão e, só quando alguém o declarou, grava o resumo.
- `registrar_reabertura_sessao(id_sessao: str) -> bool` — Devolve a sessão a `ativa`: o ambiente retoma sessões que o fim já encerrou.
- `registrar_execucao_run(id_sessao: str, modelo: str, dados_execucao: Mapping[str, Any]) -> str` — Cria nó do tipo Run, pendurado na Sessao por 'produz' e ligado a ela por 'ocorreu_em'.

## `harness/identidade_harness.py`

Identidade sob a qual um harness registra sessões e execuções no grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEIS_VALIDOS_EM_HARNESS` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.SISTEMA, PapelAutor.HUMANO})` |

### `IdentidadeHarness`

*DTO imutável* — Autor e papel fixados na configuração do harness, não na chamada.

**Campos:** `autor: str`, `papel: PapelAutor`

## `harness/interfaces.py`

Interface abstrata para adaptadores de ciclo de vida do harness.

### `AdaptadorDeHarness` (ABC)

*contrato* — Contrato para captura e injeção desacoplada do ciclo de vida de sessões.

- `registrar_inicio_sessao(id_sessao: str, id_setor: str, metadados: Mapping[str, Any] | None) -> bool` `[abstract]` — Registra a criação de uma nova sessão e vincula ao Setor correspondente.
- `registrar_fim_sessao(id_sessao: str, resumo: str) -> bool` `[abstract]` — Marca a conclusão de uma sessão no grafo compartilhado.
- `registrar_reabertura_sessao(id_sessao: str) -> bool` `[abstract]` — Devolve a `ativa` uma sessão que o fim já encerrou e o ambiente retomou.
- `registrar_execucao_run(id_sessao: str, modelo: str, dados_execucao: Mapping[str, Any]) -> str` `[abstract]` — Registra um nó Run associado à sessão e retorna o ID gerado.

## `harness/leitura_por_shell.py`

Os caminhos que um comando de shell lê, tirados do texto do comando por heurística conservadora.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LEITORES_SIMPLES` | `frozenset[str]` | `frozenset({'cat', 'head', 'tail', 'less', 'wc', 'get-content', 'gc', 't…` |
| `LEITORES_COM_PADRAO` | `frozenset[str]` | `frozenset({'grep', 'rg', 'sed'})` |
| `LEITOR_POR_PARAMETRO` | `str` | `'select-string'` |
| `PARAMETROS_DE_CAMINHO` | `frozenset[str]` | `frozenset({'-path', '-literalpath'})` |
| `FLAGS_DE_PADRAO` | `frozenset[str]` | `frozenset({'-e', '-f', '--regexp', '--file', '--expression'})` |
| `FLAGS_DE_EDICAO` | `frozenset[str]` | `frozenset({'-i', '--in-place'})` |
| `SEPARADORES` | `frozenset[str]` | `frozenset({';', '|', '||', '&&', '&', '(', ')'})` |
| `ASPAS` | `str` | `'"\''` |
| `CARACTERES_DE_REDIRECIONAMENTO` | `str` | `'<>&'` |
| `MARCA_DE_HEREDOC` | `str` | `'<<'` |

### Funções do módulo

- `caminhos_lidos_no_comando(comando: str) -> tuple[str, ...]` — Os caminhos que os leitores reconhecidos do comando leem, na ordem; vazio na dúvida.

## `harness/linha_de_cota.py`

A linha `Cota: 5h <n>%, semana <n>%` que a raiz escreve, lida de volta da transcrição.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PADRAO_DA_COTA` | `re.Pattern[str]` | `re.compile('cota\\s*:\\s*\\**\\s*5\\s*h\\s*(?P<cinco_horas>\\d+(?:[.,]\…` |
| `MARCAS_DA_COTA` | `tuple[str, ...]` | `('Cota', 'cota', 'COTA')` |
| `PREFIXO_COTA_5H` | `str` | `'cota_5h_'` |
| `PREFIXO_COTA_SEMANAL` | `str` | `'cota_semanal_'` |
| `MOMENTO_DO_DESPACHO` | `str` | `'inicio'` |
| `MOMENTO_DA_PARADA` | `str` | `'fim'` |

### `CotaDeclarada`

*DTO imutável* — Os percentuais da janela de 5 horas e da semanal, como a raiz os leu.

**Campos:** `cinco_horas: float`, `semanal: float`

- `em_propriedades(momento: str) -> dict[str, float]` — As propriedades do Run para o momento dado: `inicio` no despacho, `fim` na parada.

### Funções do módulo

- `ultima_cota(texto: str) -> CotaDeclarada | None` — A última linha de cota do texto; None quando ele não traz nenhuma.

## `harness/repositorio.py`

Do diretório de trabalho ao nome do projeto: o repositório é a unidade natural da memória.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MARCADOR_DO_GIT` | `str` | `'.git'` |
| `PREFIXO_DO_GITDIR` | `str` | `'gitdir:'` |
| `PASTA_DE_WORKTREES` | `str` | `'worktrees'` |
| `NOME_DE_PROJETO_RESERVA` | `str` | `'projeto'` |

### Funções do módulo

- `localizar_raiz_do_repositorio(caminho: Path) -> Path` — A raiz do repositório que contém o caminho; sem git, o próprio caminho.
- `nome_do_projeto(caminho: Path) -> str` — O nome da pasta do repositório, que é o nome natural do projeto.

## `harness/retomada.py`

A vista de retomada: o que o hook de início imprime para o agente ler antes de trabalhar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_DA_VISTA` | `str` | `'Memoria do graphow para esta sessao'` |
| `TITULO_DOS_APRENDIZADOS` | `str` | `'### Aprendizados aplicaveis'` |
| `TITULO_DA_SESSAO_ANTERIOR` | `str` | `'### Sessao anterior'` |
| `TITULO_DA_SESSAO_RETOMADA` | `str` | `'### Esta sessao (retomada)'` |
| `LIMITE_DE_APRENDIZADOS` | `int` | `12` |
| `LIMITE_DE_CARACTERES_DA_CONDENSACAO` | `int` | `600` |
| `SEM_APRENDIZADOS` | `str` | `'- nenhum aprendizado registrado para este projeto ainda: o que aprende…` |
| `SEM_SESSAO_ANTERIOR` | `str` | `'- nenhuma sessao anterior neste Setor: esta e a primeira.'` |
| `SEM_REGISTROS` | `str` | `' sem registros alem da telemetria: a sessao nao deixou Evidence, Decis…` |

### `PedidoDeRetomada`

*DTO imutável* — O que a vista precisa: a projeção, a sessão que abre e o Setor em que ela mora.

**Campos:** `view: GrafoView`, `id_sessao: str`, `id_setor: str`

### Funções do módulo

- `montar_vista_de_retomada(pedido: PedidoDeRetomada) -> tuple[str, ...]` — As linhas da vista, prontas para a saída padrão do hook; vazia se o Setor não existe.

## `harness/servico_harness.py`

Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EVENTO_POR_FASE` | `Mapping[FaseDoHarness, TipoEvento]` | `{FaseDoHarness.INICIO: TipoEvento.EXECUCAO_SOLICITADA, FaseDoHarness.PR…` |

### `FaseDoHarness` (str, Enum)

*serviço* — Momentos do ciclo de vida que o ambiente comunica ao grafo.

### `PedidoDeCicloDeVida`

*DTO imutável* — O que o hook informa ao grafo em cada disparo.

**Campos:** `fase: FaseDoHarness`, `id_sessao: str`, `id_setor: str`, `modelo: str`, `resumo: str`, `ramo_id: str`, `metadados: Mapping[str, Any]`, `diretorio_de_trabalho: str`, `motivo: str`, `id_agente: str`

- `id_run() -> str` `[property]` — Identificador estável do Run: um por sessão, para as fases dela; um por subagente despachado.

### `ResultadoCicloDeVida`

*DTO imutável* — Recibo do que o serviço conseguiu registrar no grafo.

**Campos:** `sucesso: bool`, `id_run: str`, `mensagem: str`, `versao_log: int`, `id_setor: str`

### `ServicoHarness`

*serviço* — Traduz cada disparo do hook em escrita no grafo, sob identidade fixada.

- `registrar(pedido: PedidoDeCicloDeVida) -> ResultadoCicloDeVida` — Executa o efeito da fase sobre a sessão e emite o evento de execução.

## `harness/transcricao.py`

O consumo de uma execução lido da transcrição que o ambiente grava: tokens, modelos e tarefas.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVES_DE_USO` | `Mapping[str, str]` | `{'input_tokens': 'tokens_entrada', 'output_tokens': 'tokens_saida', 'ca…` |
| `MODELO_SINTETICO` | `str` | `'<synthetic>'` |
| `SUFIXO_DE_ASSUMIR_TAREFA` | `str` | `'__assumir_tarefa'` |
| `CAMPO_AUTOR_DO_RECIBO` | `str` | `'autor'` |
| `MARCAS_DE_LINHA_UTIL` | `tuple[str, ...]` | `('"usage"', SUFIXO_DE_ASSUMIR_TAREFA, '"tool_result"', *MARCAS_DA_COTA)` |
| `MARCA_DE_INSTANTE` | `str` | `'"timestamp"'` |
| `MARCA_DE_USUARIO` | `str` | `'"user"'` |
| `CAMPO_MOTIVO_SEM_CONSUMO` | `str` | `'motivo_sem_consumo'` |
| `MOTIVO_TRANSCRICAO_AUSENTE` | `str` | `'transcricao_ausente'` |
| `MOTIVO_ERRO_DE_LEITURA` | `str` | `'erro_de_leitura'` |

### `AcumuladorDeConsumo`

*serviço* — Soma a transcrição entrada por entrada, contando cada mensagem do modelo uma vez só.

- `abrir_com(despacho: Mapping[str, Any]) -> None` — Lê a cota do prompt de despacho, a primeira entrada do usuário na transcrição do subagente.
- `marcar_instante(entrada: Mapping[str, Any]) -> bool` — Estende a janela da execução até o instante da entrada; False quando ela não traz um válido.
- `acrescentar(entrada: Mapping[str, Any]) -> None` — Registra o uso, o modelo e as tarefas de uma resposta do modelo, e o autor que a ferramenta devolveu.
- `consolidar() -> ConsumoDaTranscricao` — Os totais do que foi acrescentado.

### `ConsumoDaTranscricao`

*DTO imutável* — O que uma execução gastou e em que trabalhou, pronto para virar propriedades do Run.

**Campos:** `tokens: Mapping[str, int]`, `mensagens_de_modelo: int`, `modelos: tuple[str, ...]`, `tarefas: tuple[str, ...]`, `autores_mcp: tuple[str, ...]`, `inicio: datetime | None`, `fim: datetime | None`, `cota_do_despacho: CotaDeclarada | None`, `ultima_cota_escrita: CotaDeclarada | None`, `forma: FormaDoContexto`

- `modelo_principal() -> str` `[property]` — O modelo que mais respondeu; vazio quando nenhum respondeu.
- `em_propriedades() -> dict[str, Any]` — As propriedades do Run: tokens por categoria, modelos, tarefas assumidas, com que autores, quando e a forma do contexto.

### `LeituraDaTranscricao`

*DTO imutável* — O consumo lido ou, sem ele, o motivo: quem mede separa o arquivo ausente do ilegível.

**Campos:** `consumo: ConsumoDaTranscricao | None`, `motivo_sem_consumo: str`

### Funções do módulo

- `ler_consumo(caminho: Path) -> ConsumoDaTranscricao | None` — O consumo da transcrição no caminho; None quando o arquivo não existe ou não se lê.
- `ler_transcricao(caminho: Path) -> LeituraDaTranscricao` — O consumo da transcrição no caminho, ou o motivo de não haver um.
- `localizar_transcricao_do_subagente(caminhos: Mapping[str, str], id_agente: str) -> Path | None` — A transcrição do subagente: a que o hook indicar, ou a pasta `subagents` da sessão.
- `ler_instante(valor: object) -> datetime | None` — O instante ISO 8601 de uma entrada, em UTC; o que não se lê como instante vira None.

