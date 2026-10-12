# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

21 módulos · 3000 linhas · 40 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/briefing.py`](#orquestradorbriefing) | 147 | O briefing de cada sessão, montado por código a partir do livro-razão e do git. |
| [`orquestrador/contexto_do_laco.py`](#orquestradorcontextodolaco) | 147 | O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar. |
| [`orquestrador/documento_do_goal.py`](#orquestradordocumentodogoal) | 75 | O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências. |
| [`orquestrador/entrada_do_goal.py`](#orquestradorentradadogoal) | 114 | De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração. |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 115 | Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem. |
| [`orquestrador/execucao_da_fatia.py`](#orquestradorexecucaodafatia) | 143 | O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro. |
| [`orquestrador/git_do_goal.py`](#orquestradorgitdogoal) | 234 | O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração. |
| [`orquestrador/gravacao_do_plano.py`](#orquestradorgravacaodoplano) | 115 | O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só. |
| [`orquestrador/laco.py`](#orquestradorlaco) | 172 | O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão. |
| [`orquestrador/leitura_do_goal.py`](#orquestradorleituradogoal) | 247 | O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações. |
| [`orquestrador/livro_razao.py`](#orquestradorlivrorazao) | 256 | O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`. |
| [`orquestrador/modelo_do_goal.py`](#orquestradormodelodogoal) | 139 | Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço. |
| [`orquestrador/planejamento.py`](#orquestradorplanejamento) | 126 | O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão. |
| [`orquestrador/saidas.py`](#orquestradorsaidas) | 256 | A saída de cada papel como objeto tipado, com a conferência que o schema não faz. |
| [`orquestrador/sessoes_de_papel.py`](#orquestradorsessoesdepapel) | 232 | A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria. |
| [`orquestrador/spec_do_goal.py`](#orquestradorspecdogoal) | 93 | A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro. |
| [`orquestrador/status.py`](#orquestradorstatus) | 73 | O `--status` do orquestrador: onde o Goal está, o que cada fatia fez e quanto as sessões custaram. |
| [`orquestrador/suite.py`](#orquestradorsuite) | 64 | A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit. |
| [`orquestrador/validacao_json.py`](#orquestradorvalidacaojson) | 81 | Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam. |
| [`orquestrador/verificacao_do_goal.py`](#orquestradorverificacaodogoal) | 159 | Os passos do fim: a verificação adversarial do Goal, as fatias de correção e o fechamento. |

## `orquestrador/briefing.py`

O briefing de cada sessão, montado por código a partir do livro-razão e do git.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DO_ERRO` | `int` | `6000` |

### `ContextoDaFatia`

*DTO imutável* — O que o git e o livro-razão dizem em volta da fatia que vai rodar.

**Campos:** `tentativa: int`, `entregues: tuple[str, ...]`, `diff_da_anterior: str`

### Funções do módulo

- `briefing_do_planejador(estado: EstadoDoGoal, spec: str, tem_fixados: bool) -> str` — O pedido ao planejador: a spec inteira e onde está o repositório.
- `briefing_do_executor(estado: EstadoDoGoal, fatia: FatiaRegistrada, contexto: ContextoDaFatia) -> str` — O pedido ao executor da fatia, com tudo o que a governa por extenso.
- `briefing_do_verificador(estado: EstadoDoGoal, commit: str, entregues: Sequence[str]) -> str` — O pedido ao verificador: spec, critérios, decisões, suíte e o commit, sem nada de quem implementou.
- `pedido_de_correcao_da_saida(problemas: Sequence[str]) -> str` — O que vai à mesma sessão quando a saída dela não conferiu.

## `orquestrador/contexto_do_laco.py`

O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MAXIMO_DE_FALHAS` | `int` | `2` |
| `MAXIMO_DE_CICLOS_DE_CORRECAO` | `int` | `2` |
| `ORCAMENTO_PADRAO_USD` | `float` | `30.0` |

### `ContextoDoGoal`

*DTO imutável* — Um Goal sendo conduzido: o livro-razão, a configuração gravada e as sessões dele.

**Campos:** `livro: LivroRazaoDoGoal`, `configuracao: m.ConfiguracaoDoGoal`, `sessoes: SessoesDePapel`, `telemetria: RepositorioTelemetria`, `pasta: Path`, `opcoes: OpcoesDoLaco`

- `id_goal() -> str` `[property]` — O Goal.
- `area() -> Path` `[property]` — O worktree do Goal.
- `git() -> GitDoGoal` `[property]` — O git da área.
- `banco_descartavel() -> Path` `[property]` — O banco que a suíte e os hooks das sessões recebem, para não escreverem no do usuário.
- `estado() -> EstadoDoGoal` — O estado do Goal relido do livro-razão.
- `patch(nome: str) -> Path` — Onde guardar o que uma tentativa deixou fora de commit.
- `gasto() -> float` — O custo conhecido das sessões do Goal até agora.
- `restante() -> float` — O que sobra do orçamento.
- `sem_orcamento() -> Parada | None` — A parada por orçamento, quando ele acabou; None quando ainda dá para abrir sessão.

### `DependenciasDoLaco`

*DTO imutável* — O que o laço usa e não decide: o grafo, as sessões, a telemetria e onde guardar o estado de cada Goal.

**Campos:** `kernel: WriteKernel`, `executor: ExecutorDeSessao`, `telemetria: RepositorioTelemetria`, `pasta_de_estado: Path`, `modelos: Mapping[str, str]`, `modo_de_permissao: str`, `tempo_limite_da_sessao_s: float`

### `GoalInexistente` (GraphowError)

*serviço* — O Goal pedido não está no livro-razão.

### `MotivoDaParada` (str, Enum)

*serviço* — Por que o laço devolveu a palavra.

### `OpcoesDoLaco`

*DTO imutável* — O que a chamada pede; None quer dizer "o que já está gravado no Goal, ou o padrão".

**Campos:** `modo: str | None`, `ramo: str`, `base: str`, `orcamento_usd: float | None`, `area: Path | None`, `tempo_limite_da_suite_s: float`

### `Parada`

*DTO imutável* — O laço parou: em que Goal, por quê e o que fazer para seguir.

**Campos:** `id_goal: str`, `motivo: MotivoDaParada`, `mensagem: str`

- `fechou() -> bool` `[property]` — O Goal fechou.

## `orquestrador/documento_do_goal.py`

O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DOS_DOCUMENTOS` | `str` | `'docs/goals'` |
| `TITULO_DAS_PENDENCIAS` | `str` | `'## Pendencias'` |

### Funções do módulo

- `caminho_do_documento(slug: str) -> str` — O caminho do documento do Goal, relativo à raiz do repositório.
- `renderizar_documento(id_goal: str, configuracao: m.ConfiguracaoDoGoal, plano: Plano) -> str` — O documento do Goal recém-planejado, sem pendências ainda.
- `com_pendencias(documento: str, pendencias: Sequence[Mapping[str, Any]]) -> str` — O documento com a seção de pendências reescrita.
- `escrever_documento(area: Path, slug: str, conteudo: str) -> Path` — Grava o documento na área do Goal e devolve o caminho.

## `orquestrador/entrada_do_goal.py`

De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PREFIXO_GENERICO_DA_SPEC` | `str` | `'spec-'` |
| `SUFIXOS_POSSIVEIS` | `int` | `100` |

### `GoalDaSpec`

*DTO imutável* — O Goal que a spec retoma ou cria: o id, o slug (com o sufixo) e se ele já existe.

**Campos:** `id_goal: str`, `slug: str`, `existe: bool`

### `PedidoDeConfiguracao`

*DTO imutável* — O que a configuração de um Goal novo precisa: o Goal, o repositório, a chamada e onde fica o estado.

**Campos:** `id_goal: str`, `slug: str`, `raiz: Path`, `opcoes: OpcoesDoLaco`, `pasta_de_estado: Path`

### `PedidoInvalido` (GraphowError)

*serviço* — O que a chamada pediu não dá para conduzir.

### Funções do módulo

- `goal_da_spec(view: GrafoView, spec: Path, texto: str) -> GoalDaSpec` — O Goal aberto que a mesma spec criou no mesmo repositório, ou o primeiro id livre para um novo.
- `slug_da_spec(spec: Path, raiz: Path) -> str` — O nome da spec sem o prefixo `spec-`; a spec de nome genérico leva o nome do repositório.
- `configuracao_nova(pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal` — A configuração do Goal novo, com os padrões do que a chamada não disse, conferida.
- `adotar_goal(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal` — O Goal do gerente passa a ser conduzido: a spec montada dos nós e a configuração da chamada.
- `pedido_de_adocao(estado: EstadoDoGoal, opcoes: OpcoesDoLaco) -> PedidoDeConfiguracao` — O pedido de configuração do Goal do gerente, que pede o repositório na primeira vez.
- `atualizar_configuracao(livro: LivroRazaoDoGoal, configuracao: m.ConfiguracaoDoGoal, opcoes: OpcoesDoLaco) -> m.ConfiguracaoDoGoal` — O modo e o orçamento que a chamada pede de novo valem daqui em diante, e ficam gravados.

## `orquestrador/esquemas.py`

Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEL_PLANEJADOR` | `str` | `'planejador'` |
| `PAPEL_EXECUTOR` | `str` | `'executor'` |
| `PAPEL_VERIFICADOR` | `str` | `'verificador'` |
| `PAPEIS` | `tuple[str, ...]` | `(PAPEL_PLANEJADOR, PAPEL_EXECUTOR, PAPEL_VERIFICADOR)` |
| `PASTA_DOS_PROMPTS` | `Path` | `Path(__file__).parent / 'prompts'` |
| `LIMITE_DO_PROMPT_BYTES` | `int` | `5 * 1024` |
| `VERIFICACOES_DE_CRITERIO` | `tuple[str, ...]` | `('teste', 'checagem')` |
| `MODELOS_SUGERIDOS` | `tuple[str, ...]` | `('opus', 'sonnet', 'haiku')` |
| `STATUS_DO_EXECUTOR` | `tuple[str, ...]` | `('pronto', 'duvida', 'falhou')` |
| `VEREDITOS_DE_CRITERIO` | `tuple[str, ...]` | `('atende', 'parcial', 'nao_atende')` |
| `GRAVIDADES` | `tuple[str, ...]` | `('bloqueante', 'acompanhamento')` |
| `TEXTO` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': 1}` |
| `TEXTO_LIVRE` | `Mapping[str, Any]` | `{'type': 'string'}` |
| `LISTA_DE_TEXTOS` | `Mapping[str, Any]` | `{'type': 'array', 'items': {'type': 'string'}}` |
| `CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'verificacao': {'type': 'string',…` |
| `DECISAO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'motivo': TEXTO})` |
| `FATIA` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'objetivo': TEXTO, 'criterios': …` |
| `ESQUEMA_DO_PLANO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'comando_suite': TEXTO, 'criterios': _lista_d…` |
| `ESQUEMA_DA_EXECUCAO` | `dict[str, Any]` | `_objeto({'status': {'type': 'string', 'enum': list(STATUS_DO_EXECUTOR)}…` |
| `PARECER` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'veredito': {'type': 'string', 'enum': list(VERED…` |
| `ACHADO` | `dict[str, Any]` | `_objeto({'gravidade': {'type': 'string', 'enum': list(GRAVIDADES)}, 'ti…` |
| `ESQUEMA_DA_VERIFICACAO` | `dict[str, Any]` | `_objeto({'resumo': TEXTO, 'criterios': _lista_de(PARECER, 1), 'decisoes…` |
| `ESQUEMA_POR_PAPEL` | `Mapping[str, Mapping[str, Any]]` | `{PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO, PAPEL_EXECUTOR: ESQUEMA_DA_EXECUCA…` |

### Funções do módulo

- `caminho_do_prompt(papel: str) -> Path` — O prompt de sistema do papel, no pacote.

## `orquestrador/execucao_da_fatia.py`

O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_PRONTO` | `str` | `'pronto'` |
| `STATUS_DUVIDA` | `str` | `'duvida'` |

### `Tentativa`

*DTO imutável* — Uma tentativa em curso: a fatia, o número e o commit de onde ela partiu.

**Campos:** `fatia: FatiaRegistrada`, `numero: int`, `head: str`

### Funções do módulo

- `executar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> Parada | None` — Roda uma tentativa da fatia; a parada diz por que o laço não segue.

## `orquestrador/git_do_goal.py`

O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXECUTAVEL_DO_GIT` | `str` | `'git'` |
| `VARIAVEIS_DE_OUTRO_REPOSITORIO` | `frozenset[str]` | `frozenset({'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'})` |
| `NOME_DO_HOOK_DA_TRAVA` | `str` | `'reference-transaction'` |
| `HOOK_DA_TRAVA` | `str` | `'#!/bin/sh\n# Trava do graphow orquestrar: a sessao do agente nao atual…` |
| `IDENTIDADE_DE_RESERVA` | `tuple[str, ...]` | `('-c', 'user.name=graphow orquestrar', '-c', 'user.email=orquestrador@g…` |
| `LIMITE_DO_RESUMO_DO_DIFF` | `int` | `4000` |

### `AreaDoGoal`

*DTO imutável* — Onde o trabalho do Goal acontece: o repositório do humano, o worktree, a branch e a base.

**Campos:** `repositorio: Path`, `pasta: Path`, `ramo: str`, `base: str`

### `FalhaDoGitDoGoal` (GraphowError)

*serviço* — O git recusou o que o orquestrador pediu; o contexto traz o comando e a saída de erro.

### `GitDoGoal`

*DTO imutável* — Roda o git numa pasta (o repositório do humano ou a área do Goal), sem a trava do agente.

**Campos:** `pasta: Path`

- `tentar() -> SaidaDoGit` — O comando, sem recusar quando o git sai com erro.
- `rodar() -> str` — A saída padrão; recusa com a saída de erro quando o git falha.
- `head() -> str` — O commit em que a pasta está.
- `ramo_atual() -> str` — A branch do HEAD; vazio com o HEAD destacado.
- `ramo_existe(ramo: str) -> bool` — A branch local existe.
- `mudancas() -> tuple[str, ...]` — As linhas do `status --porcelain`: o que está fora de commit, ignorados de fora.
- `e_ancestral(antes: str, depois: str) -> bool` — `antes` está na história de `depois` (ou é ele).
- `arquivos_entre(antes: str, depois: str) -> tuple[str, ...]` — Os arquivos que mudaram de um commit ao outro.
- `resumo_do_diff(antes: str, depois: str) -> str` — O `diff --stat` entre os dois commits, cortado para caber no briefing.
- `commits_desde(base: str) -> tuple[str, ...]` — Hash curto e assunto de cada commit da branch desde a base, do mais antigo ao mais novo.

### `SaidaDoGit`

*DTO imutável* — O código de saída e as duas saídas de um comando do git.

**Campos:** `codigo: int`, `saida: str`, `erro: str`

### Funções do módulo

- `raiz_do_repositorio(pasta: Path) -> Path` — A raiz do repositório git que contém a pasta.
- `preparar_area(area: AreaDoGoal) -> None` — O worktree do Goal na branch dele: reaproveitado se já existe, criado da base se a branch é nova.
- `commitar(area: Path, mensagem: str) -> str` — Tudo o que mudou na área num commit do orquestrador; devolve o hash.
- `ultimo_commit_do_arquivo(area: Path, caminho: str) -> str` — O commit mais novo que tocou o arquivo; o HEAD quando nenhum tocou.
- `descartar_mudancas(area: Path, arquivo_patch: Path) -> bool` — Guarda o que está fora de commit num .patch e volta a área ao HEAD; diz se havia o que guardar.
- `restaurar_head(area: Path, ramo: str, esperado: str) -> str` — Desfaz o que o agente fez no git: volta à branch e, com `reset --soft`, ao commit esperado.
- `integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str` — Avança a base até a branch do Goal, só por fast-forward; devolve o commit integrado.
- `remover_area(repositorio: Path, area: Path) -> bool` — Tira o worktree do Goal depois da integração; a branch fica. Diz se conseguiu.
- `instalar_trava(pasta: Path) -> dict[str, str]` — Grava o hook da trava na pasta e devolve o ambiente que a liga numa sessão de agente.
- `regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]` — As regras `--disallowedTools` de git de escrita, para cada ferramenta de shell dada.

## `orquestrador/gravacao_do_plano.py`

O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só.

### `PlanoParaGravar`

*DTO imutável* — O plano conferido e o que o cerca: o slug, os nós já fixados e o commit do documento.

**Campos:** `plano: Plano`, `slug: str`, `commit_do_documento: str`, `caminho_do_documento: str`, `nos_fixados: Mapping[str, str]`, `renomear_goal: bool`

### Funções do módulo

- `gravar_plano(livro: LivroRazaoDoGoal, pedido: PlanoParaGravar) -> None` — Grava o plano inteiro num lote.

## `orquestrador/laco.py`

O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_PASSOS` | `int` | `200` |

### `Orquestrador`

*serviço* — Conduz Goals com as dependências dadas; cada chamada roda até o Goal fechar ou o laço parar.

- `iniciar_da_spec(spec: Path, repositorio: Path, opcoes: OpcoesDoLaco) -> Parada` — Cria o Goal da spec (ou retoma o que a mesma spec já criou) e roda; a falha de domínio vira parada.
- `rodar(id_goal: str, opcoes: OpcoesDoLaco, repositorio: Path | None) -> Parada` — Roda ou retoma o Goal até ele fechar ou o laço parar; a falha de domínio vira parada.
- `aprovar_plano(id_goal: str, autor: str) -> str` — O portão do plano do orquestrador: o humano grava a aprovação no Goal, com o commit do documento.

## `orquestrador/leitura_do_goal.py`

O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_NA_FILA` | `frozenset[str]` | `frozenset({m.STATUS_PENDENTE, m.STATUS_EM_ANDAMENTO})` |

### `DuvidaRegistrada`

*DTO imutável* — Uma Question que o orquestrador abriu para uma fatia, e o que o humano respondeu.

**Campos:** `id: str`, `pergunta: str`, `status: str`, `resposta: str`

- `aberta() -> bool` `[property]` — Ainda espera o humano.

### `EstadoDoGoal`

*DTO imutável* — Tudo o que o laço lê do Goal para decidir o passo seguinte.

**Campos:** `id_goal: str`, `rotulo: str`, `status: str`, `propriedades: Mapping[str, Any]`, `fatias: tuple[FatiaRegistrada, ...]`, `verificacoes: tuple[VerificacaoRegistrada, ...]`, `plano_aprovado: bool`

- `configuracao() -> m.ConfiguracaoDoGoal | None` `[property]` — A configuração do laço, quando o orquestrador já conduz o Goal.
- `plano() -> Mapping[str, Any] | None` `[property]` — O plano gravado, quando já há.
- `fechado() -> bool` `[property]` — O Goal já fechou.
- `ciclos_de_correcao() -> int` `[property]` — Quantos ciclos de correção a verificação já abriu.
- `pendencias() -> list[dict[str, Any]]` `[property]` — As pendências gravadas no Goal.
- `ultima_verificacao() -> VerificacaoRegistrada | None` `[property]` — A verificação mais recente.
- `prontas() -> tuple[FatiaRegistrada, ...]` — As fatias que podem rodar agora, na ordem do plano.
- `pausadas() -> tuple[FatiaRegistrada, ...]` — As fatias paradas numa dúvida aberta.
- `bloqueadas() -> tuple[FatiaRegistrada, ...]` — As fatias que viraram pendência depois da segunda falha.
- `todas_concluidas() -> bool` — Há fatias e todas fecharam.

### `FatiaRegistrada`

*DTO imutável* — Uma fatia do Goal como o livro-razão a guarda.

**Campos:** `id: str`, `codigo: str`, `titulo: str`, `status: str`, `ordem: int`, `propriedades: Mapping[str, Any]`, `depende_de: tuple[str, ...]`, `duvidas: tuple[DuvidaRegistrada, ...]`

- `texto(chave: str) -> str` — Uma propriedade de texto da fatia.
- `lista(chave: str) -> tuple[str, ...]` — Uma propriedade de lista de textos da fatia.
- `tentativas() -> int` `[property]` — Quantas sessões de executor a fatia já abriu, dúvidas inclusive.
- `falhas() -> int` `[property]` — Quantas tentativas falharam (a saída inválida, a suíte vermelha, a sessão interrompida); a dúvida não conta.
- `duvida_aberta() -> DuvidaRegistrada | None` `[property]` — A dúvida que pausa a fatia, quando há.

### `VerificacaoRegistrada`

*DTO imutável* — Uma verificação do Goal: em que commit, com que veredito e o que achou.

**Campos:** `id: str`, `commit: str`, `veredito: str`, `ciclo: int`, `propriedades: Mapping[str, Any]`

- `limpa() -> bool` `[property]` — Sem bloqueante.
- `lista(chave: str) -> list[dict[str, Any]]` — Os bloqueantes ou os acompanhamentos gravados.

### Funções do módulo

- `ler_estado(view: GrafoView, id_goal: str) -> EstadoDoGoal | None` — O estado do Goal no grafo; None quando o Goal não existe.
- `setor_do_goal(view: GrafoView, id_goal: str) -> str` — O Setor que contém a Sessao que produziu o Goal; vazio quando não há.

## `orquestrador/livro_razao.py`

O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAMO_PADRAO` | `str` | `'main'` |
| `ROTULO_DO_SETOR` | `str` | `'Goals orquestrados'` |
| `LIMITE_DO_ROTULO` | `int` | `120` |

### `GoalNovo`

*DTO imutável* — O Goal que nasce de uma spec: onde ele mora no grafo e o que ele guarda.

**Campos:** `id_goal: str`, `rotulo: str`, `spec: str`, `configuracao: m.ConfiguracaoDoGoal`, `nome_do_repositorio: str`

### `LivroRazaoDoGoal`

*serviço* — As escritas do laço sobre um Goal, cada uma num lote do papel `orquestrador`.

- `id_sessao() -> str` `[property]` — A Sessao do orquestrador que produz o que ele grava do Goal.
- `view() -> GrafoView` — O grafo agora.
- `gravar(operacoes: Sequence[ItemPatch], justificativa: str) -> None` — Submete o lote; a recusa vira `LoteRecusado` com o motivo do kernel.
- `produzido(id_no: str, tipo: TipoNo, rotulo: str) -> list[ItemPatch]` — O nó de trabalho pendurado na Sessao do orquestrador.
- `criar_goal(novo: GoalNovo) -> None` — Projeto e Setor do repositório (se faltam), a Sessao do Goal e o Goal com a spec e a configuração.
- `adotar_goal(id_setor: str, spec: str, configuracao: m.ConfiguracaoDoGoal) -> None` — O Goal que o gerente criou passa a ser conduzido: a Sessao do orquestrador, a spec montada e a configuração.
- `gravar_plano_proposto(dados: Mapping[str, Any]) -> None` — A saída conferida do planejador no Goal, antes de qualquer passo que possa cair no meio.
- `iniciar_tentativa(id_task: str, tentativa: int) -> None` — A fatia entra em andamento, com a tentativa contada antes de a sessão abrir.
- `concluir_fatia(id_task: str, tentativa: int) -> None` — O commit vira Artifact da fatia, e a fatia fecha; a observação diz o que o orquestrador desfez no git.
- `registrar_falha(id_task: str, tentativa: int) -> None` — A tentativa que falhou vira Note da fatia, e a fatia volta a pendente com o erro e a conta das falhas.
- `marcar_pendencia(id_task: str, motivo: str, pendencias: Sequence[Mapping[str, Any]]) -> None` — A fatia que falhou duas vezes sai da fila e vira pendência do Goal.
- `abrir_duvida(id_task: str, tentativa: int) -> str` — A dúvida do executor vira Question que bloqueia a fatia; devolve o id dela.
- `gravar_verificacao(numero: int, verificacao: Verificacao) -> str` — A verificação vira Evidence ligada ao Goal, com o commit verificado; devolve o id dela.
- `criar_correcoes(id_evidencia: str, achados: Sequence[Achado]) -> None` — Cada bloqueante vira uma fatia de correção, que diz por `corrige` de que verificação nasceu.
- `registrar_pendencias(pendencias: Sequence[Mapping[str, Any]]) -> None` — A lista de pendências do Goal (acompanhamentos e bloqueantes sem ciclo), inteira.
- `fechar(commit_integrado: str) -> None` — O Goal fecha com o commit integrado, e a Sessao do orquestrador se encerra.

### `LoteRecusado` (GraphowError)

*serviço* — O kernel recusou um lote do orquestrador: defeito do laço, e não do agente.

### Funções do módulo

- `no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch` — A criação de um nó.
- `aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch` — A criação de uma aresta, com id derivado das pontas.
- `propriedade(id_no: str, chave: str, valor: object) -> ItemPatch` — A escrita de uma propriedade de um nó que já existe.

## `orquestrador/modelo_do_goal.py`

Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AUTOR_DO_ORQUESTRADOR` | `str` | `'graphow-orquestrar'` |
| `MODO_SUPERVISIONADO` | `str` | `'supervisionado'` |
| `MODO_AUTONOMO` | `str` | `'autonomo'` |
| `MODOS` | `tuple[str, ...]` | `(MODO_SUPERVISIONADO, MODO_AUTONOMO)` |
| `CAMPO_SPEC` | `str` | `'spec'` |
| `CAMPO_ORQUESTRACAO` | `str` | `'orquestracao'` |
| `CAMPO_PLANO` | `str` | `'plano'` |
| `CAMPO_PLANO_PROPOSTO` | `str` | `'plano_proposto'` |
| `CAMPO_CICLOS` | `str` | `'ciclos_de_correcao'` |
| `CAMPO_PENDENCIAS` | `str` | `'pendencias'` |
| `CAMPO_INTEGRADO_EM` | `str` | `'integrado_em'` |
| `CAMPO_APROVACAO_DO_PLANO` | `str` | `CAMPO_DA_APROVACAO` |
| `CAMPO_STATUS` | `str` | `'status'` |
| `CAMPO_FATIA` | `str` | `'fatia'` |
| `CAMPO_OBJETIVO` | `str` | `'objetivo'` |
| `CAMPO_CRITERIOS` | `str` | `'criterios'` |
| `CAMPO_ARQUIVOS_ALVO` | `str` | `'arquivos_alvo'` |
| `CAMPO_MODELO` | `str` | `'modelo'` |
| `CAMPO_ORDEM` | `str` | `'ordem'` |
| `CAMPO_TENTATIVAS` | `str` | `'tentativas'` |
| `CAMPO_FALHAS` | `str` | `'falhas'` |
| `CAMPO_ULTIMO_ERRO` | `str` | `'ultimo_erro'` |
| `CAMPO_PATCH` | `str` | `'patch_da_tentativa'` |
| `CAMPO_PENDENCIA` | `str` | `'pendencia'` |
| `CAMPO_COMMIT` | `str` | `'commit'` |
| `CAMPO_CORRIGE` | `str` | `'corrige_verificacao'` |
| `CAMPO_CRITERIO_PRONTO` | `str` | `'criterio_pronto'` |
| `CAMPO_PERGUNTA` | `str` | `'pergunta'` |
| `CAMPO_RESPOSTA` | `str` | `'resposta'` |
| `CAMPO_ABERTA_POR` | `str` | `'aberta_por'` |
| `CAMPO_VEREDITO` | `str` | `'veredito'` |
| `CAMPO_CICLO` | `str` | `'ciclo'` |
| `ACAO_DA_VERIFICACAO` | `str` | `'verificacao_do_goal'` |
| `ACAO_DA_TENTATIVA` | `str` | `'tentativa_que_falhou'` |
| `VEREDITO_LIMPO` | `str` | `'aprovado'` |
| `VEREDITO_COM_BLOQUEANTE` | `str` | `'rejeitado'` |
| `STATUS_PENDENTE` | `str` | `'pendente'` |
| `STATUS_EM_ANDAMENTO` | `str` | `'em_andamento'` |
| `STATUS_CONCLUIDO` | `str` | `'concluido'` |
| `STATUS_BLOQUEADO` | `str` | `'bloqueado'` |

### `ConfiguracaoDoGoal`

*DTO imutável* — O que o laço precisa saber de onde e como trabalhar, gravado no Goal na primeira chamada.

**Campos:** `modo: str`, `repositorio: str`, `area: str`, `ramo: str`, `base: str`, `slug: str`, `orcamento_usd: float`

- `em_json() -> dict[str, Any]` — A configuração como propriedade do Goal.
- `de_json(dados: Mapping[str, Any]) -> 'ConfiguracaoDoGoal'` — A configuração lida do Goal.

### Funções do módulo

- `slug_de(texto: str) -> str` — Identificador estável, minúsculo, sem acento nem espaço.
- `id_do_goal(slug: str) -> str` — O Goal que o orquestrador cria a partir de uma spec.
- `id_do_projeto(slug_do_repositorio: str) -> str` — O Projeto dos Goals orquestrados de um repositório.
- `id_do_setor(slug_do_repositorio: str) -> str` — O Setor dos Goals orquestrados de um repositório.
- `id_da_sessao(id_goal: str) -> str` — A Sessao do orquestrador que produz o que ele grava do Goal.
- `id_do_criterio(slug: str, codigo: str) -> str` — A Constraint de um critério de aceite criado pelo plano.
- `id_da_decisao(slug: str, codigo: str) -> str` — A Decision de uma decisão registrada pelo plano.
- `id_da_fatia(slug: str, codigo: str) -> str` — A Task de uma fatia do plano ou de uma correção.

## `orquestrador/planejamento.py`

O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão.

### Funções do módulo

- `planejar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — O plano já pago, ou uma sessão do planejador; grava o plano, ou diz por que não deu.

## `orquestrador/saidas.py`

A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VEREDITO_QUE_ATENDE` | `str` | `'atende'` |
| `GRAVIDADE_BLOQUEANTE` | `str` | `'bloqueante'` |
| `GRAVIDADE_ACOMPANHAMENTO` | `str` | `'acompanhamento'` |
| `STATUS_DUVIDA` | `str` | `'duvida'` |

### `Achado`

*DTO imutável* — Um problema que o verificador achou, com a gravidade e o que ele fere.

**Campos:** `gravidade: str`, `titulo: str`, `descricao: str`, `local: str`, `criterios: tuple[str, ...]`

- `em_json() -> dict[str, Any]` — O achado para gravar na Evidence.

### `Criterio`

*DTO imutável* — Um critério de aceite: id (C1...), texto completo e como se prova.

**Campos:** `id: str`, `texto: str`, `verificacao: str`

### `Decisao`

*DTO imutável* — Uma decisão que o trabalho segue, com o motivo.

**Campos:** `id: str`, `texto: str`, `motivo: str`

### `Fatia`

*DTO imutável* — Uma fatia vertical do plano: o que entrega, que critérios cobre, onde mexe e de que depende.

**Campos:** `id: str`, `titulo: str`, `objetivo: str`, `criterios: tuple[str, ...]`, `arquivos: tuple[str, ...]`, `depende_de: tuple[str, ...]`, `modelo: str`

- `de_json(dados: Mapping[str, Any]) -> 'Fatia'` — A fatia como o planejador a devolveu.

### `IdsFixados`

*DTO imutável* — Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id.

**Campos:** `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`

### `Parecer`

*DTO imutável* — O veredito do verificador sobre um critério ou uma decisão, com a prova.

**Campos:** `id: str`, `veredito: str`, `prova: str`

### `Plano`

*DTO imutável* — O plano do Goal: título, comando da suíte, critérios, decisões e fatias.

**Campos:** `titulo: str`, `comando_suite: str`, `criterios: tuple[Criterio, ...]`, `decisoes: tuple[Decisao, ...]`, `fatias: tuple[Fatia, ...]`, `fora_do_escopo: tuple[str, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Plano'` — O plano como o planejador o devolveu, já conferido pelo schema.

### `SaidaDoExecutor`

*DTO imutável* — O que o executor devolveu da fatia.

**Campos:** `status: str`, `resumo: str`, `arquivos: tuple[str, ...]`, `testes: tuple[str, ...]`, `duvida: str`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoExecutor'` — A saída como o executor a devolveu.
- `conferir() -> tuple[str, ...]` — A dúvida precisa da pergunta.

### `Verificacao`

*DTO imutável* — O que o verificador devolveu do Goal inteiro.

**Campos:** `resumo: str`, `criterios: tuple[Parecer, ...]`, `decisoes: tuple[Parecer, ...]`, `achados: tuple[Achado, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Verificacao'` — A verificação como o verificador a devolveu.
- `bloqueantes() -> tuple[Achado, ...]` — Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum cita, um sintético.
- `acompanhamentos() -> tuple[Achado, ...]` — Os achados que não ferem critério nem decisão.

### Funções do módulo

- `conferir_plano(plano: Plano, fixados: IdsFixados) -> tuple[str, ...]` — Os problemas de sentido do plano; vazio quando ele pode ser gravado.
- `conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]` — Um parecer por critério e por decisão do plano, e achado que cita só o que existe.

## `orquestrador/sessoes_de_papel.py`

A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FERRAMENTAS_POR_PAPEL` | `Mapping[str, tuple[str, ...]]` | `{PAPEL_PLANEJADOR: ('Bash', 'Read', 'Glob', 'Grep'), PAPEL_EXECUTOR: ('…` |
| `MODO_DE_PERMISSAO_PADRAO` | `str` | `'bypassPermissions'` |
| `MODELO_PADRAO` | `str` | `'opus'` |
| `FONTES_DE_CONFIGURACAO` | `str` | `'project'` |
| `ORCAMENTO_MINIMO_DA_SESSAO_USD` | `float` | `0.05` |

### `ConfiguracaoDasSessoes`

*DTO imutável* — O que vale para toda sessão de agente do Goal.

**Campos:** `pasta_das_sessoes: Path`, `ambiente_da_trava: Mapping[str, str]`, `modelos: Mapping[str, str]`, `modo_de_permissao: str`, `tempo_limite_s: float`, `banco_dos_hooks: Path | None`

### `PedidoDePapel`

*DTO imutável* — Uma sessão a rodar: o papel, onde, com que briefing e como conferir a saída.

**Campos:** `papel: str`, `id_goal: str`, `pasta: Path`, `briefing: str`, `conferir: Conferencia`, `fatia: str`, `tentativa: int`, `modelo: str`, `orcamento_restante_usd: float`

### `RespostaDePapel`

*DTO imutável* — A saída conferida, ou os problemas que sobraram, e as invocações que rodaram.

**Campos:** `dados: Mapping[str, Any] | None`, `problemas: tuple[str, ...]`, `resultados: tuple[ResultadoDeSessao, ...]`

- `valida() -> bool` `[property]` — A saída conferiu e pode ser gravada.

### `SessoesDePapel`

*serviço* — Roda as sessões dos papéis e registra cada invocação na telemetria.

- `modelo_do_papel(papel: str) -> str` — O modelo configurado para o papel; Opus quando a configuração não diz.
- `rodar(pedido: PedidoDePapel) -> RespostaDePapel` — A sessão, e a retomada com os problemas quando a saída não confere.

### Funções do módulo

- `argumentos_do_papel(papel: str, orcamento_restante_usd: float) -> tuple[str, ...]` — O que o comando da sessão leva além do que o pedido de sessão já nomeia; a lista variádica vai por último.
- `ler_saida(resultado: ResultadoDeSessao, pedido: PedidoDePapel) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]` — O JSON da sessão conferido, ou os problemas: o `structured_output`, senão o texto final como JSON.
- `saida_conferida_da_telemetria(registros: Sequence[SessaoRegistrada], papel: str, problemas: Conferencia) -> Mapping[str, Any] | None` — A saída mais nova do papel, relida do stream gravado, que passa na conferência; None sem nenhuma.
- `registro_da_invocacao(pedido: PedidoDePapel, resultado: ResultadoDeSessao) -> SessaoRegistrada` — A invocação como linha de telemetria.
- `resultados_da_telemetria(registros: Sequence[SessaoRegistrada]) -> tuple[ResultadoDeSessao, ...]` — As invocações relidas dos streams gravados, como a bancada as mede.

## `orquestrador/spec_do_goal.py`

A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro.

### `SpecDoGoal`

*DTO imutável* — O texto da spec, os ids que o plano tem de manter e o nó de cada um.

**Campos:** `texto: str`, `fixados: IdsFixados`, `nos_fixados: dict[str, str]`

### Funções do módulo

- `montar_spec_do_goal(view: GrafoView, id_goal: str) -> SpecDoGoal` — A spec do Goal a partir do grafo, com os critérios e as decisões numerados.

## `orquestrador/status.py`

O `--status` do orquestrador: onde o Goal está, o que cada fatia fez e quanto as sessões custaram.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |

### Funções do módulo

- `formatar_status(estado: EstadoDoGoal, registros: Sequence[SessaoRegistrada]) -> list[str]` — As linhas do status do Goal.

## `orquestrador/suite.py`

A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TEMPO_LIMITE_DA_SUITE_S` | `float` | `1800.0` |
| `LIMITE_DA_SAIDA` | `int` | `20000` |

### `ResultadoDaSuite`

*DTO imutável* — Como a suíte terminou e o fim do que ela imprimiu.

**Campos:** `comando: str`, `codigo: int | None`, `saida: str`, `tempo_esgotado: bool`

- `passou() -> bool` `[property]` — Saiu com zero dentro do tempo.
- `descrever() -> str` — O resultado para o briefing da nova tentativa.

### Funções do módulo

- `rodar_suite(area: Path, comando: str, banco_descartavel: Path) -> ResultadoDaSuite` — Roda o comando na área e devolve o resultado.

## `orquestrador/validacao_json.py`

Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DO_JSON` | `Mapping[str, tuple[type, ...]]` | `{'object': (dict,), 'array': (list,), 'string': (str,), 'integer': (int…` |

### Funções do módulo

- `validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str) -> tuple[str, ...]` — Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere.

## `orquestrador/verificacao_do_goal.py`

Os passos do fim: a verificação adversarial do Goal, as fatias de correção e o fechamento.

### Funções do módulo

- `verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — Com as fatias concluídas: verifica o commit atual, abre correções ou fecha.

