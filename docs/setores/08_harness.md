# Setor 08 — Integração com Harness

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.harness`

Ponto de entrada para hooks de ambiente registrarem sessões e execuções, sob identidade fixada na configuração.

## Inventário

9 módulos · 662 linhas · 11 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`harness/ambiente_padrao.py`](#harnessambientepadrao) | 162 | O ambiente padrão da memória: o Projeto do repositório e o Setor `Memoria` dentro dele. |
| [`harness/convention_adapter.py`](#harnessconventionadapter) | 78 | Adaptador de fallback baseado em convenção de chamada explícita. |
| [`harness/entrada_hook.py`](#harnessentradahook) | 86 | Leitura do JSON que o ambiente entrega na entrada padrão do hook. |
| [`harness/hook_adapter.py`](#harnesshookadapter) | 72 | Adaptador de ciclo de vida via hooks de harness (ex: Claude Code / IDE). |
| [`harness/identidade_harness.py`](#harnessidentidadeharness) | 30 | Identidade sob a qual um harness registra sessões e execuções no grafo. |
| [`harness/interfaces.py`](#harnessinterfaces) | 38 | Interface abstrata para adaptadores de ciclo de vida do harness. |
| [`harness/repositorio.py`](#harnessrepositorio) | 60 | Do diretório de trabalho ao nome do projeto: o repositório é a unidade natural da memória. |
| [`harness/servico_harness.py`](#harnessservicoharness) | 117 | Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução. |

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
- `id_projeto() -> str` `[property]` — Id do Projeto criado para o repositório, quando nenhum com o nome dele existe.
- `id_setor() -> str` `[property]` — Id do Setor de memória do repositório.
- `rotulo_do_projeto() -> str` `[property]` — O Projeto se chama como a pasta do repositório.
- `rotulo_do_setor() -> str` `[property]` — O Setor de memória tem o mesmo rótulo em todo repositório.

### `GarantidorDeAmbientePadrao`

*serviço* — Garante que o Projeto e o Setor de memória existem, criando só o que falta.

- `garantir(ambiente: AmbientePadrao, ramo_id: str) -> str` — Devolve o id do Setor de memória; vazio quando o grafo recusou criá-lo.

### Funções do módulo

- `gerar_slug(texto: str) -> str` — Identificador estável a partir de um nome: minúsculas e hífens, sem acento nem espaço.
- `localizar_projeto(ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None` — O Projeto do repositório: pelo id derivado ou, na falta, pelo nome que o humano deu.
- `localizar_setor_de_memoria(projeto: NoGrafo, ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None` — O Setor de memória do Projeto: pelo id derivado ou pelo rótulo `Memoria`.
- `montar_operacoes_do_ambiente(ambiente: AmbientePadrao, projeto: NoGrafo | None) -> tuple[ItemPatch, ...]` — O Projeto, se ainda não existe, e o Setor de memória pendurado nele no mesmo lote.

## `harness/convention_adapter.py`

Adaptador de fallback baseado em convenção de chamada explícita.

### `ConventionHarnessAdapter` (AdaptadorDeHarness)

*serviço* — Adaptador agnóstico para ambientes sem suporte a hooks de ciclo de vida nativos.

- `registrar_inicio_sessao(id_sessao: str, id_setor: str, metadados: Mapping[str, Any] | None) -> bool` — Cria o nó de Sessao no grafo, pendurado no Setor por 'contem'.
- `registrar_fim_sessao(id_sessao: str, resumo: str) -> bool` — Atualiza a sessão como concluída.
- `registrar_execucao_run(id_sessao: str, modelo: str, dados_execucao: Mapping[str, Any]) -> str` — Registra nó Run simplificado, pendurado na Sessao por 'produz'.

## `harness/entrada_hook.py`

Leitura do JSON que o ambiente entrega na entrada padrão do hook.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVE_SESSAO` | `str` | `'session_id'` |
| `CHAVE_MODELO` | `str` | `'model'` |
| `CHAVES_DE_IDENTIFICACAO_DO_MODELO` | `tuple[str, ...]` | `('id', 'display_name')` |
| `CHAVES_DE_RESUMO` | `tuple[str, ...]` | `('reason', 'source', 'hook_event_name')` |
| `MODELO_DESCONHECIDO` | `str` | `'desconhecido'` |

### `EntradaDeHook`

*DTO imutável* — Os campos do payload do hook que o Graphow aproveita.

**Campos:** `id_sessao: str`, `modelo: str`, `resumo: str`

- `tem_sessao() -> bool` `[property]` — Informa se a entrada trouxe um identificador de sessão utilizável.

### Funções do módulo

- `interpretar_entrada_de_hook(texto: str) -> EntradaDeHook` — Converte o corpo do hook em DTO, tolerando entrada ausente ou malformada.
- `ler_entrada_de_hook(fonte: IO[str]) -> EntradaDeHook` — Lê e interpreta o payload do hook a partir de um fluxo de texto.

## `harness/hook_adapter.py`

Adaptador de ciclo de vida via hooks de harness (ex: Claude Code / IDE).

### `HookHarnessAdapter` (AdaptadorDeHarness)

*serviço* — Captura eventos de lifecycle automáticos via hooks e traduz para patches no kernel.

- `registrar_inicio_sessao(id_sessao: str, id_setor: str, metadados: Mapping[str, Any] | None) -> bool` — Emite patch de criação de Sessao e aresta 'contem' a partir do Setor.
- `registrar_fim_sessao(id_sessao: str, resumo: str) -> bool` — Atualiza o status da sessão para concluída com anotação de resumo.
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
- `registrar_execucao_run(id_sessao: str, modelo: str, dados_execucao: Mapping[str, Any]) -> str` `[abstract]` — Registra um nó Run associado à sessão e retorna o ID gerado.

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

## `harness/servico_harness.py`

Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EVENTO_POR_FASE` | `Mapping[FaseDoHarness, TipoEvento]` | `{FaseDoHarness.INICIO: TipoEvento.EXECUCAO_SOLICITADA, FaseDoHarness.PR…` |

### `FaseDoHarness` (str, Enum)

*serviço* — Momentos do ciclo de vida que o ambiente comunica ao grafo.

### `PedidoDeCicloDeVida`

*DTO imutável* — O que o hook informa ao grafo em cada disparo.

**Campos:** `fase: FaseDoHarness`, `id_sessao: str`, `id_setor: str`, `modelo: str`, `resumo: str`, `ramo_id: str`, `metadados: Mapping[str, Any]`

- `id_run() -> str` `[property]` — Identificador estável do Run, para as três fases atualizarem o mesmo nó.

### `ResultadoCicloDeVida`

*DTO imutável* — Recibo do que o serviço conseguiu registrar no grafo.

**Campos:** `sucesso: bool`, `id_run: str`, `mensagem: str`, `versao_log: int`

### `ServicoHarness`

*serviço* — Traduz cada disparo do hook em escrita no grafo, sob identidade fixada.

- `registrar(pedido: PedidoDeCicloDeVida) -> ResultadoCicloDeVida` — Executa o efeito da fase sobre a sessão e emite o evento de execução.

