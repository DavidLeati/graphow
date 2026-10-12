# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

36 módulos · 6012 linhas · 58 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/aceite_intocado.py`](#orquestradoraceiteintocado) | 167 | Os testes de aceite rodam sempre da cópia intocada, e a configuração de teste não muda sem o plano dizer. |
| [`orquestrador/atendimento_dos_pedidos.py`](#orquestradoratendimentodospedidos) | 63 | A conferência dos pedidos do humano contra o Goal como ele está, antes de gravá-los. |
| [`orquestrador/autor_de_aceite.py`](#orquestradorautordeaceite) | 135 | O passo do aceite: uma sessão do autor de aceite, os testes conferidos vermelhos, o commit e o registro. |
| [`orquestrador/briefing.py`](#orquestradorbriefing) | 252 | O briefing de cada sessão, montado por código a partir do livro-razão e do git. |
| [`orquestrador/comandos_do_stream.py`](#orquestradorcomandosdostream) | 63 | Os comandos que uma sessão rodou de fato, lidos do stream, contra os que ela declarou na saída. |
| [`orquestrador/contexto_do_laco.py`](#orquestradorcontextodolaco) | 177 | O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar. |
| [`orquestrador/correcoes.py`](#orquestradorcorrecoes) | 59 | As fatias de correção de um ciclo: os bloqueantes do mesmo arquivo, ou do mesmo critério, juntos numa fatia só. |
| [`orquestrador/documento_do_goal.py`](#orquestradordocumentodogoal) | 97 | O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências. |
| [`orquestrador/entrada_do_goal.py`](#orquestradorentradadogoal) | 142 | De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração. |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 154 | Os schemas da saída de cada papel: o que o planejador, o autor de aceite, o executor e o verificador devolvem. |
| [`orquestrador/execucao_da_fatia.py`](#orquestradorexecucaodafatia) | 226 | O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro. |
| [`orquestrador/git_do_goal.py`](#orquestradorgitdogoal) | 367 | O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração. |
| [`orquestrador/gravacao_da_verificacao.py`](#orquestradorgravacaodaverificacao) | 117 | A verificação gravada no livro-razão: a Evidence, um nó Achado por problema, o estado dos critérios e as pendências, num lote só. |
| [`orquestrador/gravacao_do_aceite.py`](#orquestradorgravacaodoaceite) | 79 | Os testes de aceite gravados no livro-razão: o commit como Artifact, a ligação de cada critério aos seus testes e o Goal. |
| [`orquestrador/gravacao_do_plano.py`](#orquestradorgravacaodoplano) | 123 | O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só. |
| [`orquestrador/laco.py`](#orquestradorlaco) | 213 | O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão. |
| [`orquestrador/leitura_das_verificacoes.py`](#orquestradorleituradasverificacoes) | 113 | As verificações do Goal e os nós Achado delas e das revisões de risco, como o laço os lê do livro-razão. |
| [`orquestrador/leitura_do_goal.py`](#orquestradorleituradogoal) | 329 | O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações. |
| [`orquestrador/livro_razao.py`](#orquestradorlivrorazao) | 277 | O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`. |
| [`orquestrador/modelo_do_goal.py`](#orquestradormodelodogoal) | 196 | Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço. |
| [`orquestrador/pedidos_do_humano.py`](#orquestradorpedidosdohumano) | 137 | Os pedidos do humano ao laço: cada saída que ele tem de um Goal parado, gravada como Decision dele. |
| [`orquestrador/planejamento.py`](#orquestradorplanejamento) | 131 | O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão. |
| [`orquestrador/resultado_de_teste.py`](#orquestradorresultadodeteste) | 259 | O que a saída de um teste de aceite diz: passou de verdade, ou falhou pelo motivo certo. |
| [`orquestrador/revisao_da_fatia.py`](#orquestradorrevisaodafatia) | 164 | A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit. |
| [`orquestrador/saida_do_aceite.py`](#orquestradorsaidadoaceite) | 252 | A saída do autor de aceite e a conferência dela: a forma, o lugar dos testes e o vermelho de antes da implementação. |
| [`orquestrador/saida_do_verificador.py`](#orquestradorsaidadoverificador) | 187 | A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código. |
| [`orquestrador/saidas.py`](#orquestradorsaidas) | 245 | A saída de cada papel como objeto tipado, com a conferência que o schema não faz. |
| [`orquestrador/sessoes_de_papel.py`](#orquestradorsessoesdepapel) | 305 | A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria. |
| [`orquestrador/spec_do_goal.py`](#orquestradorspecdogoal) | 129 | A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro. |
| [`orquestrador/status.py`](#orquestradorstatus) | 105 | O `--status` do orquestrador: onde o Goal está, o que prova que ele está pronto, o que cada fatia fez e quanto custou. |
| [`orquestrador/suite.py`](#orquestradorsuite) | 152 | A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit. |
| [`orquestrador/trava_do_git.py`](#orquestradortravadogit) | 152 | A trava do git nas sessões de agente: as regras, o ambiente e a restauração do clone depois de cada sessão. |
| [`orquestrador/validacao_json.py`](#orquestradorvalidacaojson) | 83 | Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam. |
| [`orquestrador/verificacao_do_goal.py`](#orquestradorverificacaodogoal) | 142 | O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal. |
| [`orquestrador/verificacao_do_marco.py`](#orquestradorverificacaodomarco) | 208 | A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão. |

## `orquestrador/aceite_intocado.py`

Os testes de aceite rodam sempre da cópia intocada, e a configuração de teste não muda sem o plano dizer.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOMES_DE_CONFIGURACAO` | `frozenset[str]` | `frozenset({'conftest.py', 'pytest.ini', '.pytest.ini', 'pytest.toml', '…` |
| `PREFIXOS_DE_CONFIGURACAO` | `tuple[str, ...]` | `('jest.config.', 'vitest.config.', 'vitest.workspace.', 'babel.config.'…` |
| `SUFIXOS_DE_CONFIGURACAO` | `tuple[str, ...]` | `('.pth',)` |
| `SOMBRAS_DO_RUNNER` | `frozenset[str]` | `frozenset({'pytest.py', 'pytest', '_pytest', 'unittest.py', 'unittest',…` |
| `SECOES_DE_TESTE` | `Mapping[str, tuple[str, ...]]` | `{'pyproject.toml': ('tool', 'pytest'), 'setup.cfg': ('tool:pytest',), '…` |
| `PASTAS_DO_AMBIENTE` | `frozenset[str]` | `frozenset({'node_modules', '.venv', 'venv', '.tox', '.nox', '.git', 'si…` |

### Funções do módulo

- `e_configuracao_de_teste(caminho: str) -> bool` — O caminho, relativo à raiz, é de um arquivo que muda como os testes rodam (pelo nome).
- `configuracoes_mudadas(area: Path, caminhos: Iterable[str]) -> tuple[str, ...]` — Dos caminhos mudados desde o commit `antes`, os de configuração de teste (no pyproject e afins, só a parte de teste).
- `soltos_que_mudam_os_testes(area: Path) -> tuple[str, ...]` — Os arquivos fora do git (não versionados ou ignorados) que estão em aceite/ ou que configuram os testes.
- `preparar_o_aceite(area: Path, commit_do_aceite: str) -> tuple[str, ...]` — Antes de rodar os testes de aceite: aceite/ como no commit do aceite e a configuração solta fora; diz o que tirou.
- `flags_do_indice(area: Path) -> tuple[str, ...]` — Os arquivos com `skip-worktree` (S) ou `assume-unchanged` (letra minúscula) no índice: mudança que o status esconde.
- `limpar_flags(area: Path, arquivos: Sequence[str]) -> None` — Tira as flags do índice dos arquivos, para o git voltar a ver o que mudou neles.

## `orquestrador/atendimento_dos_pedidos.py`

A conferência dos pedidos do humano contra o Goal como ele está, antes de gravá-los.

### Funções do módulo

- `conferir_pedido(view: GrafoView, estado: EstadoDoGoal, pedido: NovoPedido) -> tuple[NovoPedido, Sequence[ItemPatch]]` — O pedido completo (o marco do `mais_ciclos`) e o que ele muda no mesmo lote; recusa o que não vale.

## `orquestrador/autor_de_aceite.py`

O passo do aceite: uma sessão do autor de aceite, os testes conferidos vermelhos, o commit e o registro.

### Funções do módulo

- `escrever_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — Os testes de aceite já pagos, ou uma sessão do autor; commita e grava, ou diz por que não deu.
- `linhas_do_aceite(saida: SaidaDoAceite) -> list[str]` — A seção dos testes de aceite no documento do Goal: o comando e o que prova cada critério.

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
- `briefing_do_revisor(estado: EstadoDoGoal, fatia: FatiaRegistrada, mudados: Sequence[str]) -> str` — O pedido ao revisor da fatia de risco: a fatia, os critérios dela com os testes de aceite, as decisões e o que mudou.
- `briefing_do_autor_de_aceite(estado: EstadoDoGoal) -> str` — O pedido ao autor de aceite: a spec, os critérios com o tipo de verificação, as decisões e a suíte.
- `briefing_do_verificador(estado: EstadoDoGoal, commit: str, entregues: Sequence[str]) -> str` — O pedido ao verificador do marco: spec, critérios que ele julga, decisões, suíte e o commit, sem nada de quem implementou.
- `pedido_de_correcao_da_saida(problemas: Sequence[str]) -> str` — O que vai à mesma sessão quando a saída dela não conferiu.

## `orquestrador/comandos_do_stream.py`

Os comandos que uma sessão rodou de fato, lidos do stream, contra os que ela declarou na saída.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FERRAMENTA_DO_SHELL` | `str` | `'Bash'` |
| `PROMPT_DO_SHELL` | `re.Pattern[str]` | `re.compile('^\\$\\s+')` |

### Funções do módulo

- `comandos_bash(caminho: Path) -> tuple[str, ...]` — Os comandos de cada chamada da ferramenta Bash no stream, na ordem; vazio sem stream.
- `comandos_nao_rodados(declarados: Iterable[str], resultados: Sequence[ResultadoDeSessao]) -> tuple[str, ...]` — Os comandos declarados que não aparecem em chamada Bash nenhuma das invocações dadas.
- `problema_dos_comandos(faltando: Sequence[str]) -> tuple[str, ...]` — O que volta à sessão quando ela declarou comando que não rodou.

## `orquestrador/contexto_do_laco.py`

O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MAXIMO_DE_FALHAS` | `int` | `2` |
| `MAXIMO_DE_CICLOS_DE_CORRECAO` | `int` | `m.MAXIMO_DE_CICLOS_DE_CORRECAO` |
| `ORCAMENTO_PADRAO_USD` | `float` | `30.0` |

### `ContextoDoGoal`

*DTO imutável* — Um Goal sendo conduzido: o livro-razão, a configuração gravada e as sessões dele.

**Campos:** `livro: LivroRazaoDoGoal`, `configuracao: m.ConfiguracaoDoGoal`, `sessoes: SessoesDePapel`, `telemetria: RepositorioTelemetria`, `pasta: Path`, `opcoes: OpcoesDoLaco`

- `id_goal() -> str` `[property]` — O Goal.
- `area() -> Path` `[property]` — O clone do Goal, onde as sessões trabalham.
- `area_do_goal() -> AreaDoGoal` `[property]` — O clone, o repositório do humano, a branch e a base, juntos.
- `commitar(mensagem: str) -> str` — O commit do orquestrador no clone, já levado à branch do Goal no repositório do humano.
- `commit_do_codigo() -> str` — O commit do código da área: o último que mudou algo além do documento do Goal.
- `registrar_ponta() -> None` — A ponta da branch do Goal no livro-razão, quando o git andou desde a última gravada.
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

**Campos:** `modo: str | None`, `ramo: str`, `base: str`, `orcamento_usd: float | None`, `area: Path | None`, `tempo_limite_da_suite_s: float`, `adotar_ramo: bool`

### `Parada`

*DTO imutável* — O laço parou: em que Goal, por quê e o que fazer para seguir.

**Campos:** `id_goal: str`, `motivo: MotivoDaParada`, `mensagem: str`

- `fechou() -> bool` `[property]` — O Goal fechou.

## `orquestrador/correcoes.py`

As fatias de correção de um ciclo: os bloqueantes do mesmo arquivo, ou do mesmo critério, juntos numa fatia só.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MAXIMO_POR_FATIA` | `int` | `6` |

### Funções do módulo

- `area_do_achado(achado: AchadoRegistrado) -> str` — A área em que o achado mora: o arquivo do local, o primeiro critério ou decisão que ele fere, ou ele mesmo.
- `agrupar_por_area(achados: Iterable[AchadoRegistrado]) -> list[tuple[AchadoRegistrado, ...]]` — Os achados em grupos da mesma área, na ordem em que cada área apareceu, sem repetir achado.
- `titulo_da_correcao(grupo: Sequence[AchadoRegistrado]) -> str` — O título da fatia: o primeiro achado, e quantos outros ela corrige junto.
- `propriedades_da_correcao(grupo: Sequence[AchadoRegistrado]) -> dict[str, Any]` — O objetivo, os critérios, os arquivos e os achados da fatia que corrige o grupo.

## `orquestrador/documento_do_goal.py`

O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DOS_DOCUMENTOS` | `str` | `'docs/goals'` |
| `TITULO_DAS_PENDENCIAS` | `str` | `'## Pendencias'` |
| `TITULO_DO_ACEITE` | `str` | `'## Testes de aceite'` |

### Funções do módulo

- `caminho_do_documento(slug: str) -> str` — O caminho do documento do Goal, relativo à raiz do repositório.
- `renderizar_documento(id_goal: str, configuracao: m.ConfiguracaoDoGoal, plano: Plano) -> str` — O documento do Goal recém-planejado, sem pendências ainda.
- `com_aceite(documento: str, linhas: Sequence[str]) -> str` — O documento com a seção dos testes de aceite logo antes das pendências (reescrita, se já havia).
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

Os schemas da saída de cada papel: o que o planejador, o autor de aceite, o executor e o verificador devolvem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEL_PLANEJADOR` | `str` | `'planejador'` |
| `PAPEL_AUTOR_DE_ACEITE` | `str` | `'aceite'` |
| `PAPEL_EXECUTOR` | `str` | `'executor'` |
| `PAPEL_REVISOR` | `str` | `'revisor'` |
| `PAPEL_VERIFICADOR` | `str` | `'verificador'` |
| `PAPEIS` | `tuple[str, ...]` | `(PAPEL_PLANEJADOR, PAPEL_AUTOR_DE_ACEITE, PAPEL_EXECUTOR, PAPEL_REVISOR…` |
| `PASTA_DOS_PROMPTS` | `Path` | `Path(__file__).parent / 'prompts'` |
| `LIMITE_DO_PROMPT_BYTES` | `int` | `5 * 1024` |
| `VERIFICACOES_DE_CRITERIO` | `tuple[str, ...]` | `a.VERIFICACOES_DE_CRITERIO` |
| `MODELOS_SUGERIDOS` | `tuple[str, ...]` | `('opus', 'sonnet', 'haiku')` |
| `STATUS_DO_EXECUTOR` | `tuple[str, ...]` | `('pronto', 'duvida', 'falhou')` |
| `VEREDITOS_DE_CRITERIO` | `tuple[str, ...]` | `a.VEREDITOS_DE_CRITERIO` |
| `SEVERIDADES` | `tuple[str, ...]` | `('alta', 'media', 'baixa')` |
| `TAMANHO_MINIMO_DA_PROVA` | `int` | `10` |
| `TEXTO` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': 1}` |
| `PROVA` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': TAMANHO_MINIMO_DA_PROVA}` |
| `TEXTO_LIVRE` | `Mapping[str, Any]` | `{'type': 'string'}` |
| `LISTA_DE_TEXTOS` | `Mapping[str, Any]` | `{'type': 'array', 'items': {'type': 'string'}}` |
| `CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'verificacao': {'type': 'string',…` |
| `DECISAO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'motivo': TEXTO})` |
| `FATIA` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'objetivo': TEXTO, 'criterios': …` |
| `MARCO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'fatias': LISTA_DE_TEXTOS})` |
| `ESQUEMA_DO_PLANO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'comando_suite': TEXTO, 'criterios': _lista_d…` |
| `TESTE_DE_ACEITE` | `dict[str, Any]` | `_objeto({'arquivo': TEXTO, 'nome': TEXTO, 'comando': TEXTO})` |
| `ACEITE_DO_CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'testes': _lista_de(TESTE_DE_ACEITE), 'checagem':…` |
| `ESQUEMA_DO_ACEITE` | `dict[str, Any]` | `_objeto({'resumo': TEXTO, 'comando_aceite': TEXTO, 'criterios': _lista_…` |
| `PROBLEMA_DA_REVISAO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'descricao': TEXTO, 'prova': PROVA, 'local': …` |
| `ESQUEMA_DA_REVISAO` | `dict[str, Any]` | `_objeto({'veredito': {'type': 'string', 'enum': ['aprovado', 'rejeitado…` |
| `ESQUEMA_DA_EXECUCAO` | `dict[str, Any]` | `_objeto({'status': {'type': 'string', 'enum': list(STATUS_DO_EXECUTOR)}…` |
| `PARECER` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'veredito': {'type': 'string', 'enum': list(VERED…` |
| `COMANDO_RODADO` | `dict[str, Any]` | `_objeto({'comando': TEXTO, 'codigo': {'type': 'integer'}, 'saida': TEXT…` |
| `ACHADO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'descricao': TEXTO, 'prova': PROVA, 'local': …` |
| `ESQUEMA_DA_VERIFICACAO` | `dict[str, Any]` | `_objeto({'resumo': TEXTO, 'comandos': _lista_de(COMANDO_RODADO, 1), 'cr…` |
| `ESQUEMA_POR_PAPEL` | `Mapping[str, Mapping[str, Any]]` | `{PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO, PAPEL_AUTOR_DE_ACEITE: ESQUEMA_DO_…` |

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
| `TRAILER_DO_GOAL` | `str` | `'Graphow-Goal'` |
| `TRAILER_DA_TASK` | `str` | `'Graphow-Task'` |
| `SEPARADOR_DE_COMMITS` | `str` | `'\x1e'` |
| `SEPARADOR_DO_HASH` | `str` | `'\x1f'` |
| `CHAVES_COPIADAS_PARA_O_CLONE` | `tuple[str, ...]` | `('user.name', 'user.email', 'core.autocrlf', 'core.eol', 'core.safecrlf…` |
| `REMOTO_DO_CLONE` | `str` | `'origin'` |
| `IDENTIDADE_DE_RESERVA` | `tuple[str, ...]` | `('-c', 'user.name=graphow orquestrar', '-c', 'user.email=orquestrador@g…` |
| `LIMITE_DO_RESUMO_DO_DIFF` | `int` | `4000` |

### `AreaDoGoal`

*DTO imutável* — Onde o trabalho do Goal acontece: o repositório do humano, o clone do Goal, a branch e a base.

**Campos:** `repositorio: Path`, `pasta: Path`, `ramo: str`, `base: str`

### `CommitDoGit`

*DTO imutável* — Um commit da branch: o hash e a mensagem inteira.

**Campos:** `hash: str`, `mensagem: str`

- `tem_trailer(chave: str, valor: str) -> bool` — A mensagem traz a linha `chave: valor`.

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
- `caminhos_mudados() -> tuple[str, ...]` — Cada arquivo criado, mudado, apagado ou renomeado fora de commit (as duas pontas do renomeado), um por um.
- `e_ancestral(antes: str, depois: str) -> bool` — `antes` está na história de `depois` (ou é ele).
- `arquivos_entre(antes: str, depois: str) -> tuple[str, ...]` — Os arquivos que mudaram de um commit ao outro.
- `resumo_do_diff(antes: str, depois: str) -> str` — O `diff --stat` entre os dois commits, cortado para caber no briefing.
- `commit_do_codigo(documento: str) -> str` — O último commit, a partir do HEAD, que mudou algo além do documento dado; o HEAD quando não há.
- `commits_desde(base: str) -> tuple[str, ...]` — Hash curto e assunto de cada commit da branch desde a base, do mais antigo ao mais novo.

### `SaidaDoGit`

*DTO imutável* — O código de saída e as duas saídas de um comando do git.

**Campos:** `codigo: int`, `saida: str`, `erro: str`

### Funções do módulo

- `raiz_do_repositorio(pasta: Path) -> Path` — A raiz do repositório git que contém a pasta.
- `preparar_area(area: AreaDoGoal) -> None` — O clone do Goal na branch dele, e a branch do Goal no repositório do humano no commit do clone.
- `limpar_rastros_do_clone(pasta: Path) -> None` — Tira do clone o reflog (que diz de onde ele veio) e os hooks: nada ali roda nos commits do orquestrador.
- `sincronizar_ramo(area: AreaDoGoal) -> None` — A branch do Goal no repositório do humano vai ao commit do clone, puxada dele, só por fast-forward.
- `mensagem_do_orquestrador(assunto: str, corpo: str) -> str` — A mensagem do commit com os trailers do Goal e, na fatia, da Task.
- `commitar(area: Path, mensagem: str) -> str` — Tudo o que mudou na área num commit do orquestrador; devolve o hash.
- `commits_entre(area: Path, antes: str, depois: str) -> tuple[CommitDoGit, ...]` — Os commits de `antes..depois`, do mais novo ao mais antigo, com a mensagem inteira.
- `commit_da_fatia(area: Path, id_task: str, base: str) -> CommitDoGit | None` — O commit mais novo da branch, desde a base, que o orquestrador fez para a fatia; None sem nenhum.
- `arquivos_do_commit(area: Path, hash_do_commit: str) -> tuple[str, ...]` — Os arquivos que o commit mudou.
- `ultimo_commit_do_arquivo(area: Path, caminho: str) -> str` — O commit mais novo que tocou o arquivo; o HEAD quando nenhum tocou.
- `descartar_mudancas(area: Path, arquivo_patch: Path) -> bool` — Guarda o que está fora de commit num .patch e volta a área ao HEAD; diz se havia o que guardar.
- `restaurar_head(area: Path, ramo: str, esperado: str) -> str` — Desfaz o que o agente fez no git: volta à branch e, com `reset --soft`, ao commit esperado.
- `integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str` — Avança a base até a branch do Goal, só por fast-forward; devolve o commit integrado.
- `remover_area(area: Path) -> bool` — Apaga o clone do Goal depois da integração; a branch fica no repositório do humano. Diz se conseguiu.

## `orquestrador/gravacao_da_verificacao.py`

A verificação gravada no livro-razão: a Evidence, um nó Achado por problema, o estado dos critérios e as pendências, num lote só.

### `RegistroDaVerificacao`

*DTO imutável* — O que a verificação deixa no livro-razão: o número, o commit verificado, o parecer e o que o orquestrador rodou.

**Campos:** `numero: int`, `verificacao: Verificacao`, `commit: str`, `commit_do_codigo: str`, `suite: ResultadoDaSuite`, `nos: Mapping[str, str]`, `pendencias: Sequence[Mapping[str, Any]]`, `ciclo: int`, `final: bool`, `marco: str`, `aceite: Sequence[Mapping[str, Any]]`, `resolver: Sequence[str]`, `tirado_antes_do_aceite: Sequence[str]`

- `limpa() -> bool` `[property]` — Sem bloqueante.
- `propriedades(id_goal: str) -> dict[str, Any]` — As propriedades da Evidence; cada parecer leva o nó do critério ou da decisão que julga.
- `achados(id_goal: str) -> list[tuple[str, Achado]]` — Os achados que viram nós, com o id de cada um: os bloqueantes e depois os acompanhamentos.

### Funções do módulo

- `gravar_verificacao(livro: LivroRazaoDoGoal, registro: RegistroDaVerificacao) -> str` — Grava a verificação inteira num lote; devolve o id da Evidence.

## `orquestrador/gravacao_do_aceite.py`

Os testes de aceite gravados no livro-razão: o commit como Artifact, a ligação de cada critério aos seus testes e o Goal.

### `AceiteParaGravar`

*DTO imutável* — O aceite conferido e commitado: a saída do autor, o commit, os arquivos, as execuções e o nó de cada critério.

**Campos:** `saida: SaidaDoAceite`, `commit: str`, `arquivos: tuple[str, ...]`, `execucoes: Sequence[Mapping[str, Any]]`, `nos: Mapping[str, str]`

- `em_json() -> dict[str, Any]` — O aceite como propriedade do Goal.

### Funções do módulo

- `gravar_aceite_proposto(livro: LivroRazaoDoGoal, proposto: Mapping[str, Any] | None) -> None` — A saída conferida do autor e as execuções vermelhas, no Goal, antes do commit: a retomada a reaproveita.
- `gravar_aceite(livro: LivroRazaoDoGoal, pedido: AceiteParaGravar) -> None` — O Artifact do commit dos testes, a ligação de cada critério aos seus testes e o aceite no Goal, num lote.

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
- `aprovar_plano(id_goal: str, autor: str) -> str` — O portão do plano do orquestrador: o humano aprova junto o plano e os testes de aceite, no commit deles.
- `pedir(id_goal: str, pedido: NovoPedido) -> str` — Grava o pedido do humano (orquestrador/pedidos_do_humano.py), conferido contra o Goal como ele está.

## `orquestrador/leitura_das_verificacoes.py`

As verificações do Goal e os nós Achado delas e das revisões de risco, como o laço os lê do livro-razão.

### `AchadoRegistrado`

*DTO imutável* — Um nó Achado de uma verificação do Goal: a gravidade que o código decidiu, o estado e o que ele é.

**Campos:** `id: str`, `verificacao: str`, `gravidade: str`, `estado: str`, `propriedades: Mapping[str, Any]`

- `texto(chave: str) -> str` — Uma propriedade de texto do achado.
- `lista(chave: str) -> tuple[str, ...]` — Uma propriedade de lista de textos do achado.
- `bloqueante() -> bool` `[property]` — O código o decidiu bloqueante.

### `VerificacaoRegistrada`

*DTO imutável* — Uma verificação do Goal: em que commit, com que veredito e o que achou.

**Campos:** `id: str`, `commit: str`, `veredito: str`, `ciclo: int`, `propriedades: Mapping[str, Any]`, `commit_do_codigo: str`, `achados: tuple[AchadoRegistrado, ...]`, `marco: str`

- `bloqueantes() -> tuple[AchadoRegistrado, ...]` — Os nós Achado bloqueantes desta verificação.
- `bloqueantes_abertos() -> tuple[AchadoRegistrado, ...]` — Os bloqueantes ainda não encerrados: o resolvido e o que o humano descartou não contam.
- `limpa() -> bool` `[property]` — Sem bloqueante, ou com todo bloqueante dela encerrado: resolvido, ou descartado pelo humano.

### Funções do módulo

- `verificacoes_do_goal(view: GrafoView, id_goal: str) -> tuple[VerificacaoRegistrada, ...]` — As Evidence de verificação ligadas ao Goal, da mais antiga à mais nova.
- `achados_da_evidencia(view: GrafoView, id_evidencia: str) -> tuple[AchadoRegistrado, ...]` — Os nós Achado que derivam da verificação, na ordem dos ids.
- `achados_das_revisoes(view: GrafoView, id_task: str) -> tuple[AchadoRegistrado, ...]` — Os nós Achado das revisões de risco da fatia, da revisão mais antiga à mais nova.

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

**Campos:** `id_goal: str`, `rotulo: str`, `status: str`, `propriedades: Mapping[str, Any]`, `fatias: tuple[FatiaRegistrada, ...]`, `verificacoes: tuple[VerificacaoRegistrada, ...]`, `plano_aprovado: bool`, `pedidos: tuple[PedidoDoHumano, ...]`

- `configuracao() -> m.ConfiguracaoDoGoal | None` `[property]` — A configuração do laço, quando o orquestrador já conduz o Goal.
- `plano() -> Mapping[str, Any] | None` `[property]` — O plano gravado, quando já há.
- `aceite() -> Mapping[str, Any] | None` `[property]` — Os testes de aceite gravados (commit, comando, arquivos e o aceite de cada critério), quando já há.
- `arquivos_protegidos() -> tuple[str, ...]` — Os arquivos dos testes de aceite: o executor não os toca, e a suíte do plano roda sem eles.
- `fechado() -> bool` `[property]` — O Goal já fechou.
- `cancelado() -> bool` `[property]` — O humano cancelou o Goal.
- `ciclos_de_correcao() -> int` `[property]` — Quantos ciclos de correção a verificação já abriu.
- `pendencias() -> list[dict[str, Any]]` `[property]` — As pendências gravadas no Goal.
- `achado(id_achado: str) -> AchadoRegistrado | None` — O nó Achado de qualquer verificação do Goal, pelo id.
- `ultima_verificacao() -> VerificacaoRegistrada | None` `[property]` — A verificação mais recente.
- `marcos() -> tuple[MarcoRegistrado, ...]` — Os marcos do plano, em ordem; o plano sem marcos (o de antes da fase 2) é um marco só, o final.
- `fatias_do_marco(marco: MarcoRegistrado) -> tuple[FatiaRegistrada, ...]` — As fatias do marco, as de correção inclusive.
- `verificacoes_do_marco(marco: MarcoRegistrado) -> tuple[VerificacaoRegistrada, ...]` — As verificações do marco, da mais antiga à mais nova.
- `marco_atual() -> MarcoRegistrado` — O primeiro marco sem verificação limpa que ainda tem o que fazer; com todos encerrados, o final.
- `limite_de_ciclos(marco: MarcoRegistrado) -> int` — Quantos ciclos de correção o marco tem: os dois de todo marco, mais os que o humano deu a ele.
- `pedidos_pendentes(acao: str) -> tuple[PedidoDoHumano, ...]` — Os pedidos do humano com a ação dada que o laço ainda não atendeu.
- `marco_esgotado(marco: MarcoRegistrado) -> bool` — O marco intermediário gastou os ciclos, e a verificação depois do último ainda tem bloqueante: ele não tem o que fazer.
- `bloqueantes_de_outros_marcos(marco: MarcoRegistrado) -> tuple[AchadoRegistrado, ...]` — Os bloqueantes ainda abertos que as verificações dos outros marcos deixaram: a final os cobra de novo.
- `corrigidos(marco: MarcoRegistrado) -> tuple[str, ...]` — Os Achados que uma correção entregou e que a verificação limpa do marco resolve; na final, os do Goal inteiro.
- `ciclos_do_marco(marco: MarcoRegistrado) -> int` — Quantos ciclos de correção o marco já abriu: as verificações dele de onde nasceram fatias de correção.
- `prontas(marco: MarcoRegistrado | None) -> tuple[FatiaRegistrada, ...]` — As fatias que podem rodar agora, na ordem do plano; com o marco dado, só as dele.
- `pausadas() -> tuple[FatiaRegistrada, ...]` — As fatias paradas numa dúvida aberta.
- `bloqueadas() -> tuple[FatiaRegistrada, ...]` — As fatias que viraram pendência depois da segunda falha.

### `FatiaRegistrada`

*DTO imutável* — Uma fatia do Goal como o livro-razão a guarda.

**Campos:** `id: str`, `codigo: str`, `titulo: str`, `status: str`, `ordem: int`, `propriedades: Mapping[str, Any]`, `depende_de: tuple[str, ...]`, `duvidas: tuple[DuvidaRegistrada, ...]`, `achados_de_revisao: tuple[AchadoRegistrado, ...]`

- `texto(chave: str) -> str` — Uma propriedade de texto da fatia.
- `lista(chave: str) -> tuple[str, ...]` — Uma propriedade de lista de textos da fatia.
- `tentativas() -> int` `[property]` — Quantas sessões de executor a fatia já abriu, dúvidas inclusive.
- `falhas() -> int` `[property]` — Quantas tentativas falharam (a saída inválida, a suíte vermelha, a sessão interrompida); a dúvida não conta.
- `duvida_aberta() -> DuvidaRegistrada | None` `[property]` — A dúvida que pausa a fatia, quando há.

### `MarcoRegistrado`

*DTO imutável* — Um marco do plano gravado: as fatias dele, os critérios que a verificação dele julga e se é o final.

**Campos:** `id: str`, `titulo: str`, `fatias: tuple[str, ...]`, `criterios: tuple[str, ...]`, `final: bool`

- `contem(fatia: FatiaRegistrada, primeiro: bool) -> bool` — A fatia é deste marco; a fatia de antes dos marcos é do primeiro.

### Funções do módulo

- `ler_estado(view: GrafoView, id_goal: str) -> EstadoDoGoal | None` — O estado do Goal no grafo; None quando o Goal não existe.
- `setor_do_goal(view: GrafoView, id_goal: str) -> str` — O Setor que contém a Sessao que produziu o Goal; vazio quando não há.

## `orquestrador/livro_razao.py`

O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAMO_PADRAO` | `str` | `'main'` |
| `ACAO_DA_REVISAO_DE_RISCO` | `str` | `'revisao_de_risco'` |
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
- `registrar_revisao(id_task: str, tentativa: int) -> None` — O veredito da revisão da fatia de risco vira Evidence que deriva da fatia, com os Achados dela no mesmo lote.
- `marcar_pendencia(id_task: str, motivo: str, pendencias: Sequence[Mapping[str, Any]]) -> None` — A fatia que falhou duas vezes sai da fila e vira pendência do Goal.
- `abrir_duvida(id_task: str, tentativa: int) -> str` — A dúvida do executor vira Question que bloqueia a fatia; devolve o id dela.
- `gravar_ponta(ponta: Mapping[str, str]) -> None` — A ponta da branch do Goal como o git a tem agora: o commit e o commit do código.
- `criar_correcoes(id_evidencia: str, achados: Sequence[AchadoRegistrado]) -> None` — Os Achados bloqueantes viram fatias de correção do marco, os do mesmo arquivo juntos, cada uma derivando dos dela.
- `resolver(achados: Sequence[str], justificativa: str) -> None` — Os Achados corrigidos passam a resolvidos: a verificação final limpa os confirmou.
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
| `CAMPO_ORQUESTRACAO` | `str` | `a.CAMPO_CONDUCAO` |
| `CAMPO_PLANO` | `str` | `a.CAMPO_PLANO` |
| `CAMPO_PLANO_PROPOSTO` | `str` | `'plano_proposto'` |
| `CAMPO_CICLOS` | `str` | `'ciclos_de_correcao'` |
| `CAMPO_ACEITE` | `str` | `'aceite'` |
| `CAMPO_ACEITE_PROPOSTO` | `str` | `'aceite_proposto'` |
| `CAMPO_PENDENCIAS` | `str` | `'pendencias'` |
| `CAMPO_INTEGRADO_EM` | `str` | `'integrado_em'` |
| `CAMPO_PONTA_DO_RAMO` | `str` | `a.CAMPO_PONTA_DO_RAMO` |
| `CAMPO_COMMIT_DO_CODIGO` | `str` | `a.CAMPO_COMMIT_DO_CODIGO` |
| `CAMPO_APROVACAO_DO_PLANO` | `str` | `CAMPO_DA_APROVACAO` |
| `CAMPO_STATUS` | `str` | `'status'` |
| `CAMPO_FATIA` | `str` | `'fatia'` |
| `CAMPO_OBJETIVO` | `str` | `'objetivo'` |
| `CAMPO_CRITERIOS` | `str` | `'criterios'` |
| `CAMPO_ARQUIVOS_ALVO` | `str` | `'arquivos_alvo'` |
| `CAMPO_MARCO` | `str` | `a.CAMPO_MARCO` |
| `CAMPO_MODELO` | `str` | `'modelo'` |
| `CAMPO_RISCO` | `str` | `'risco'` |
| `CAMPO_MOTIVO_DO_RISCO` | `str` | `'motivo_do_risco'` |
| `CAMPO_ORDEM` | `str` | `'ordem'` |
| `CAMPO_TENTATIVAS` | `str` | `'tentativas'` |
| `CAMPO_FALHAS` | `str` | `'falhas'` |
| `CAMPO_ULTIMO_ERRO` | `str` | `'ultimo_erro'` |
| `CAMPO_PATCH` | `str` | `'patch_da_tentativa'` |
| `CAMPO_PENDENCIA` | `str` | `'pendencia'` |
| `CAMPO_COMMIT` | `str` | `a.CAMPO_COMMIT` |
| `CAMPO_CORRIGE` | `str` | `'corrige_verificacao'` |
| `CAMPO_ACHADO` | `str` | `'achado'` |
| `CAMPO_ACHADOS` | `str` | `'achados'` |
| `MAXIMO_DE_CICLOS_DE_CORRECAO` | `int` | `2` |
| `CAMPO_CRITERIO_PRONTO` | `str` | `'criterio_pronto'` |
| `CAMPO_PERGUNTA` | `str` | `'pergunta'` |
| `CAMPO_RESPOSTA` | `str` | `'resposta'` |
| `CAMPO_ABERTA_POR` | `str` | `'aberta_por'` |
| `CAMPO_VEREDITO` | `str` | `a.CAMPO_VEREDITO` |
| `CAMPO_CICLO` | `str` | `'ciclo'` |
| `CAMPO_NUMERO` | `str` | `a.CAMPO_NUMERO` |
| `CAMPO_FINAL` | `str` | `a.CAMPO_FINAL` |
| `CAMPO_PARECERES` | `str` | `a.CAMPO_PARECERES` |
| `ACAO_DA_VERIFICACAO` | `str` | `a.ACAO_DA_VERIFICACAO` |
| `ACAO_DA_TENTATIVA` | `str` | `'tentativa_que_falhou'` |
| `VEREDITO_LIMPO` | `str` | `a.VEREDITO_LIMPO` |
| `VEREDITO_COM_BLOQUEANTE` | `str` | `a.VEREDITO_COM_BLOQUEANTE` |
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

- `achados_da_correcao(propriedades: Mapping[str, Any]) -> tuple[str, ...]` — Os Achados que a fatia de correção corrige: a lista, ou o único da fatia de antes do agrupamento.
- `id_da_revisao(id_task: str, tentativa: int) -> str` — O id da Evidence da revisão de risco de uma tentativa da fatia.
- `slug_de(texto: str) -> str` — Identificador estável, minúsculo, sem acento nem espaço.
- `id_do_goal(slug: str) -> str` — O Goal que o orquestrador cria a partir de uma spec.
- `id_do_projeto(slug_do_repositorio: str) -> str` — O Projeto dos Goals orquestrados de um repositório.
- `id_do_setor(slug_do_repositorio: str) -> str` — O Setor dos Goals orquestrados de um repositório.
- `id_da_sessao(id_goal: str) -> str` — A Sessao do orquestrador que produz o que ele grava do Goal (o contrato do papel a reconhece por este nome).
- `id_do_criterio(slug: str, codigo: str) -> str` — O Criterio de um critério de aceite criado pelo plano (na fase 1, uma Constraint com o mesmo id).
- `id_da_decisao(slug: str, codigo: str) -> str` — A Decision de uma decisão registrada pelo plano.
- `id_do_aceite(id_goal: str) -> str` — O que o trailer `Graphow-Task` do commit dos testes de aceite diz, e o sufixo do Artifact dele.
- `id_da_verificacao(id_goal: str, numero: int) -> str` — A Evidence da verificação de número dado do Goal.
- `id_do_achado(id_goal: str, numero: int, indice: int) -> str` — O Achado de índice dado da verificação de número dado.
- `id_da_fatia(slug: str, codigo: str) -> str` — A Task de uma fatia do plano ou de uma correção.

## `orquestrador/pedidos_do_humano.py`

Os pedidos do humano ao laço: cada saída que ele tem de um Goal parado, gravada como Decision dele.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PEDIDO_DESCARTAR_ACHADO` | `str` | `'descartar_achado'` |
| `PEDIDO_MAIS_CICLOS` | `str` | `'mais_ciclos'` |
| `PEDIDO_CANCELAR` | `str` | `'cancelar'` |
| `PEDIDO_RECUSAR_PLANO` | `str` | `'recusar_plano'` |
| `PEDIDO_REFAZER_ACEITE` | `str` | `'refazer_aceite'` |
| `PEDIDOS` | `frozenset[str]` | `frozenset({PEDIDO_DESCARTAR_ACHADO, PEDIDO_MAIS_CICLOS, PEDIDO_CANCELAR…` |
| `ESTADOS_QUE_SE_DESCARTAM` | `frozenset[str]` | `frozenset({a.ESTADO_ABERTO, a.ESTADO_CORRIGIDO, a.ESTADO_DO_ACOMPANHAME…` |

### `NovoPedido`

*DTO imutável* — O que o humano pede pela CLI.

**Campos:** `acao: str`, `motivo: str`, `por: str`, `alvo: str`, `ciclos: int`

### `PedidoDoHumano`

*DTO imutável* — Um pedido gravado: o que o humano pediu, por quê, sobre o quê e quem pediu.

**Campos:** `id: str`, `acao: str`, `motivo: str`, `alvo: str`, `ciclos: int`, `por: str`

### `PedidoRecusado` (GraphowError)

*serviço* — O pedido do humano não vale para o Goal como ele está, ou o kernel o recusou.

### Funções do módulo

- `ler_pedidos(view: GrafoView, id_goal: str) -> tuple[PedidoDoHumano, ...]` — Os pedidos do humano sobre o Goal, na ordem do log.
- `gravar_pedido(kernel: WriteKernel, id_goal: str, pedido: NovoPedido) -> str` — Grava a Decision do pedido, com o que ele muda no mesmo lote, como o humano; devolve o id dela.
- `escrita(id_no: str, chave: str, valor: object) -> ItemPatch` — A escrita de uma propriedade de um nó, no lote do pedido.
- `descarte(view: GrafoView, id_achado: str, motivo: str) -> list[ItemPatch]` — O que o descarte muda no Achado; recusa o que não é Achado, ou o que já está encerrado.
- `cancelamento(id_goal: str, motivo: str) -> list[ItemPatch]` — O que o cancelamento muda no Goal.

## `orquestrador/planejamento.py`

O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão.

### Funções do módulo

- `planejar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — O plano já pago, ou uma sessão do planejador; grava o plano, ou diz por que não deu.

## `orquestrador/resultado_de_teste.py`

O que a saída de um teste de aceite diz: passou de verdade, ou falhou pelo motivo certo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RUNNER_DESCONHECIDO` | `str` | `'desconhecido'` |
| `CODIGOS_DE_COMANDO_AUSENTE` | `frozenset[int]` | `frozenset({126, 127})` |
| `CODIGO_DO_PYTEST_COM_FALHA` | `int` | `1` |
| `EXCECOES_DE_ASSERCAO` | `frozenset[str]` | `frozenset({'AssertionError', 'Failed', 'pytest.fail.Exception', '_pytes…` |
| `PALAVRAS_DE_PULO` | `re.Pattern[str]` | `re.compile('\\b(skip|skipped|skipping|xfail|xfailed|xpass|xpassed|todo|…` |
| `ERRO_FORA_DA_ASSERCAO` | `re.Pattern[str]` | `re.compile('\\b(ModuleNotFoundError|ImportError|SyntaxError|Indentation…` |
| `MARCAS_DE_FALHA` | `re.Pattern[str]` | `re.compile('^(FAILED|FAIL:|FAIL |not ok|\\s*[✖✕×●]|_{3,} |\\s*\\d+\\) )…` |
| `RUNNERS_NO_COMANDO` | `tuple[tuple[str, re.Pattern[str]], ...]` | `(('pytest', re.compile('\\b(pytest|py\\.test)\\b')), ('unittest', re.co…` |
| `LEITORES` | `tuple[Callable[[str], Contagem | None], ...]` | `(_pytest, _unittest, _node, _jest, _vitest, _mocha)` |

### `Contagem`

*DTO imutável* — Quantos testes passaram, falharam, deram erro e foram pulados, como o runner disse.

**Campos:** `runner: str`, `passados: int`, `falhos: int`, `erros: int`, `pulados: int`

### Funções do módulo

- `runner_do_comando(comando: str) -> str` — O runner que o comando chama, quando é um que o orquestrador conhece; senão, desconhecido.
- `ler_saida(saida: str) -> Contagem | None` — A contagem do primeiro runner conhecido cujo resumo está na saída; None quando nenhum está.
- `por_que_nao_passou(comando: str, codigo: int | None, saida: str) -> str` — Por que o teste não conta como verde; vazio quando conta.
- `por_que_o_vermelho_nao_vale(comando: str, codigo: int | None, saida: str) -> str` — Por que a falha não é a asserção do teste declarado; vazio quando é.

## `orquestrador/revisao_da_fatia.py`

A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VEREDITO_APROVADO` | `str` | `'aprovado'` |

### `PedidoDeRevisao`

*DTO imutável* — A fatia a revisar, a tentativa em curso e por que ela é de risco.

**Campos:** `fatia: FatiaRegistrada`, `tentativa: int`, `motivo: str`

### `RejeicaoDaRevisao`

*DTO imutável* — A revisão rejeitou a entrega: os problemas, para a tentativa seguinte; eles já estão nos Achados da revisão.

**Campos:** `texto: str`

### Funções do módulo

- `de_risco(fatia: FatiaRegistrada) -> str` — Por que a fatia é de risco; vazio quando não é e não tem revisão.
- `revisar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> 'str | Parada | RejeicaoDaRevisao'` — A revisão da mudança fora de commit: vazio quando aprovada, os problemas quando rejeitada, ou a parada.
- `operacoes_dos_achados(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> list[ItemPatch]` — Na rejeição, cada problema vira nó Achado da revisão, com a gravidade do código; na aprovação, os de antes se resolvem.

## `orquestrador/saida_do_aceite.py`

A saída do autor de aceite e a conferência dela: a forma, o lugar dos testes e o vermelho de antes da implementação.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DO_ACEITE` | `str` | `'aceite'` |
| `PASTAS_DE_CACHE` | `frozenset[str]` | `frozenset({'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'…` |
| `SUFIXOS_DE_CACHE` | `tuple[str, ...]` | `('.pyc', '.pyo')` |
| `LIMITE_DA_SAIDA_REGISTRADA` | `int` | `600` |
| `TESTE_DO_COMANDO_DE_ACEITE` | `str` | `'comando_aceite'` |
| `TESTE_DA_SUITE_COM_O_ACEITE` | `str` | `'suite_e_aceite'` |

### `AceiteDoCriterio`

*DTO imutável* — O que prova um critério: os testes, a checagem e, quando o código já o atendia, por quê.

**Campos:** `id: str`, `testes: tuple[TesteDeAceite, ...]`, `checagem: tuple[str, ...]`, `ja_atendido: str`

- `em_json() -> dict[str, Any]` — O aceite do critério para o livro-razão.

### `ExecucaoDeAceite`

*DTO imutável* — Um teste de aceite rodado pelo orquestrador: o critério, o teste, o comando e como saiu.

**Campos:** `criterio: str`, `teste: str`, `comando: str`, `codigo: int | None`, `saida: str`, `so_o_codigo: bool`

- `motivo() -> str` `[property]` — Por que o teste não conta como verde (saiu com erro, foi pulado, o runner não disse); vazio quando conta.
- `passou() -> bool` `[property]` — Saiu com zero e a saída do runner diz que passou, sem pular nada.
- `vermelho_invalido() -> str` — Por que a falha não é a asserção do teste declarado; vazio quando é.
- `em_json() -> dict[str, Any]` — A execução para o livro-razão.

### `SaidaDoAceite`

*DTO imutável* — O que o autor de aceite devolveu.

**Campos:** `resumo: str`, `comando_aceite: str`, `criterios: tuple[AceiteDoCriterio, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoAceite'` — A saída como o autor a devolveu, já conferida pelo schema.
- `do_livro(aceite: Mapping[str, Any] | None) -> 'SaidaDoAceite'` — Os testes de aceite como o Goal os guarda; vazio quando ainda não há.
- `do_criterio(id_criterio: str) -> AceiteDoCriterio | None` — O aceite de um critério, pelo código.
- `testes() -> Iterable[tuple[AceiteDoCriterio, TesteDeAceite]]` — Cada teste com o critério que ele prova.

### `TesteDeAceite`

*DTO imutável* — Um teste de aceite: o arquivo, o nome e o comando que roda só ele.

**Campos:** `arquivo: str`, `nome: str`, `comando: str`

- `em_json() -> dict[str, str]` — O teste para o livro-razão.

### Funções do módulo

- `conferir_forma(saida: SaidaDoAceite, criterios: Mapping[str, str], area: Path) -> tuple[str, ...]` — Uma entrada por critério do plano, o teste certo para o critério `teste`, a checagem para o `checagem` e tudo em aceite/.
- `e_cache(caminho: str) -> bool` — O caminho é de cache que a execução dos testes deixa (bytecode, cache do pytest, dependências instaladas).
- `dentro_do_aceite(caminho: str) -> bool` — O caminho, relativo à raiz, está na pasta dos testes de aceite.
- `rodar_testes(saida: SaidaDoAceite, rodar: Rodar, criterios: Iterable[str] | None) -> tuple[ExecucaoDeAceite, ...]` — Cada teste de aceite dos critérios dados (todos, sem eles), rodado pelo comando dele.
- `rodar_o_comando_de_aceite(saida: SaidaDoAceite, rodar: Rodar) -> ExecucaoDeAceite` — O comando que roda todos os testes de aceite, de uma vez.
- `rodar_a_suite_com_o_aceite(saida: SaidaDoAceite, comando_suite: str, rodar: Rodar) -> ExecucaoDeAceite` — A suíte do projeto e todos os testes de aceite num comando só, com os arquivos de aceite na área.
- `conferir_vermelho(saida: SaidaDoAceite, rodar: Rodar) -> tuple[tuple[str, ...], tuple[ExecucaoDeAceite, ...]]` — Os testes falham antes da implementação, salvo o do critério que já era atendido; devolve os problemas e as execuções.

## `orquestrador/saida_do_verificador.py`

A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORIGEM_DO_VERIFICADOR` | `str` | `'verificador'` |
| `ORIGEM_DO_ORQUESTRADOR` | `str` | `'orquestrador'` |
| `ORIGEM_DA_REVISAO` | `str` | `'revisao_de_risco'` |
| `TITULO_DA_SUITE_VERMELHA` | `str` | `'A suite do plano falhou no commit verificado'` |
| `LIMITE_DA_PROVA` | `int` | `2000` |

### `Achado`

*DTO imutável* — Um problema achado na verificação: o que é, a prova, onde, o que ele toca e de quem veio.

**Campos:** `titulo: str`, `descricao: str`, `prova: str`, `local: str`, `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`, `severidade: str`, `origem: str`

- `toca() -> tuple[str, ...]` `[property]` — Os critérios e as decisões que o achado toca, sem repetir.
- `gravidade() -> str` `[property]` — Bloqueante quando toca critério ou decisão, ou quando foi o orquestrador quem viu falhar; senão acompanhamento.
- `em_json() -> dict[str, Any]` — O achado para a lista de pendências e para o nó Achado.
- `de_json(dados: Mapping[str, Any]) -> 'Achado'` — O achado como o verificador o devolveu.

### `ComandoRodado`

*DTO imutável* — Um comando que o verificador rodou: o que, com que código saiu e um trecho do que imprimiu.

**Campos:** `comando: str`, `codigo: int`, `saida: str`

- `em_json() -> dict[str, Any]` — O comando para gravar na Evidence.

### `Parecer`

*DTO imutável* — O veredito do verificador sobre um critério ou uma decisão, com a prova.

**Campos:** `id: str`, `veredito: str`, `prova: str`

### `Verificacao`

*DTO imutável* — O que o verificador devolveu de um marco, ou do Goal inteiro na verificação final.

**Campos:** `resumo: str`, `criterios: tuple[Parecer, ...]`, `decisoes: tuple[Parecer, ...]`, `achados: tuple[Achado, ...]`, `comandos: tuple[ComandoRodado, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Verificacao'` — A verificação como o verificador a devolveu.
- `com_achado_do_orquestrador(titulo: str, descricao: str, criterios: tuple[str, ...]) -> 'Verificacao'` — A verificação com o que o orquestrador viu falhar no commit verificado (a suíte, um teste de aceite).
- `com_parecer(id_criterio: str, veredito: str, prova: str) -> 'Verificacao'` — A verificação com o parecer do critério trocado pelo que o orquestrador viu.
- `bloqueantes() -> tuple[Achado, ...]` — Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum achado toca, um sintético.
- `acompanhamentos() -> tuple[Achado, ...]` — Os achados que não tocam critério nem decisão.
- `achados_finais() -> tuple[Achado, ...]` — Os bloqueantes e depois os acompanhamentos, na ordem em que viram nós Achado.

### Funções do módulo

- `conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]` — Um parecer por critério e por decisão pedidos, achado que toca só o que pode tocar e ao menos um comando rodado.

## `orquestrador/saidas.py`

A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_DUVIDA` | `str` | `'duvida'` |
| `MARCO_UNICO` | `str` | `'M1'` |

### `Criterio`

*DTO imutável* — Um critério de aceite: id (C1...), texto completo e como se prova.

**Campos:** `id: str`, `texto: str`, `verificacao: str`

### `Decisao`

*DTO imutável* — Uma decisão que o trabalho segue, com o motivo.

**Campos:** `id: str`, `texto: str`, `motivo: str`

### `Fatia`

*DTO imutável* — Uma fatia vertical do plano: o que entrega, que critérios cobre, onde mexe e de que depende.

**Campos:** `id: str`, `titulo: str`, `objetivo: str`, `criterios: tuple[str, ...]`, `arquivos: tuple[str, ...]`, `depende_de: tuple[str, ...]`, `modelo: str`, `risco: bool`, `motivo_do_risco: str`

- `de_json(dados: Mapping[str, Any]) -> 'Fatia'` — A fatia como o planejador a devolveu.

### `IdsFixados`

*DTO imutável* — Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id.

**Campos:** `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`

### `Marco`

*DTO imutável* — Um marco do plano: as fatias que, juntas, entregam critérios verificáveis.

**Campos:** `id: str`, `titulo: str`, `fatias: tuple[str, ...]`

### `Plano`

*DTO imutável* — O plano do Goal: título, comando da suíte, critérios, decisões, fatias e os marcos que as repartem.

**Campos:** `titulo: str`, `comando_suite: str`, `criterios: tuple[Criterio, ...]`, `decisoes: tuple[Decisao, ...]`, `fatias: tuple[Fatia, ...]`, `fora_do_escopo: tuple[str, ...]`, `marcos: tuple[Marco, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Plano'` — O plano como o planejador o devolveu, já conferido pelo schema.
- `marco_da_fatia(id_fatia: str) -> str` — O marco em que a fatia está; vazio quando nenhum a traz.
- `criterios_do_marco(id_marco: str) -> tuple[str, ...]` — Os critérios que o marco completa (a última fatia que os cobre está nele); no último, todos.
- `com_criterios_do_humano(criterios: Sequence[Criterio]) -> 'Plano'` — O plano com o texto e o tipo de verificação dos critérios que o humano fixou, como ele os escreveu.

### `SaidaDoExecutor`

*DTO imutável* — O que o executor devolveu da fatia.

**Campos:** `status: str`, `resumo: str`, `arquivos: tuple[str, ...]`, `testes: tuple[str, ...]`, `duvida: str`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoExecutor'` — A saída como o executor a devolveu.
- `conferir() -> tuple[str, ...]` — A dúvida precisa da pergunta.

### Funções do módulo

- `conferir_plano(plano: Plano, fixados: IdsFixados) -> tuple[str, ...]` — Os problemas de sentido do plano; vazio quando ele pode ser gravado.

## `orquestrador/sessoes_de_papel.py`

A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FERRAMENTAS_POR_PAPEL` | `Mapping[str, tuple[str, ...]]` | `{PAPEL_PLANEJADOR: ('Bash', 'Read', 'Glob', 'Grep'), PAPEL_AUTOR_DE_ACE…` |
| `MODO_DE_PERMISSAO_PADRAO` | `str` | `'bypassPermissions'` |
| `MODELO_PADRAO` | `str` | `'opus'` |
| `FONTES_DE_CONFIGURACAO` | `str` | `'project'` |
| `ORCAMENTO_MINIMO_DA_SESSAO_USD` | `float` | `0.05` |

### `ConfiguracaoDasSessoes`

*DTO imutável* — O que vale para toda sessão de agente do Goal.

**Campos:** `pasta_das_sessoes: Path`, `ambiente_da_trava: Mapping[str, str]`, `modelos: Mapping[str, str]`, `modo_de_permissao: str`, `tempo_limite_s: float`, `banco_dos_hooks: Path | None`

### `PedidoDePapel`

*DTO imutável* — Uma sessão a rodar: o papel, onde, com que briefing e como conferir a saída.

**Campos:** `papel: str`, `id_goal: str`, `pasta: Path`, `briefing: str`, `conferir: Conferencia`, `fatia: str`, `tentativa: int`, `modelo: str`, `orcamento_restante_usd: float`, `comandos_declarados: Callable[[Mapping[str, Any]], Sequence[str]] | None`

### `RespostaDePapel`

*DTO imutável* — A saída conferida, ou os problemas que sobraram, e as invocações que rodaram.

**Campos:** `dados: Mapping[str, Any] | None`, `problemas: tuple[str, ...]`, `resultados: tuple[ResultadoDeSessao, ...]`, `desfeito: str`

### `SessoesDePapel`

*serviço* — Roda as sessões dos papéis e registra cada invocação na telemetria.

- `modelo_do_papel(papel: str) -> str` — O modelo configurado para o papel; Opus quando a configuração não diz.
- `rodar(pedido: PedidoDePapel) -> RespostaDePapel` — A sessão conferida, e o clone deixado como estava antes dela; o que foi desfeito vai na resposta.

### Funções do módulo

- `argumentos_do_papel(papel: str, orcamento_restante_usd: float) -> tuple[str, ...]` — O que o comando da sessão leva além do que o pedido de sessão já nomeia; a lista variádica vai por último.
- `ler_saida(resultado: ResultadoDeSessao, pedido: PedidoDePapel) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]` — O JSON da sessão conferido, ou os problemas: o `structured_output`, senão o texto final como JSON.
- `saida_conferida_da_telemetria(registros: Sequence[SessaoRegistrada], papel: str, problemas: Conferencia) -> Mapping[str, Any] | None` — A saída mais nova do papel, relida do stream gravado, que passa na conferência; None sem nenhuma.
- `registro_em_andamento(pedido: PedidoDePapel, arquivo: Path) -> SessaoRegistrada` — A linha da invocação antes de a sessão abrir: quem, onde e desde quando.
- `com_o_resultado(aberta: SessaoRegistrada, resultado: ResultadoDeSessao) -> SessaoRegistrada` — A linha da invocação com o fim dela; a sessão retomada que morreu sem dizer o id fica com o id retomado.
- `recuperar_sessoes_em_andamento(telemetria: RepositorioTelemetria, id_goal: str) -> int` — As linhas que ficaram em andamento porque o orquestrador caiu; devolve quantas recuperou.
- `resultados_da_telemetria(registros: Sequence[SessaoRegistrada]) -> tuple[ResultadoDeSessao, ...]` — As invocações relidas dos streams gravados, como a bancada as mede.

## `orquestrador/spec_do_goal.py`

A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro.

### `SpecDoGoal`

*DTO imutável* — O texto da spec, os ids que o plano tem de manter e o nó de cada um.

**Campos:** `texto: str`, `fixados: IdsFixados`, `nos_fixados: dict[str, str]`, `criterios_do_humano: tuple[Criterio, ...]`

### Funções do módulo

- `montar_spec_do_goal(view: GrafoView, id_goal: str) -> SpecDoGoal` — A spec do Goal a partir do grafo, com os critérios e as decisões numerados.

## `orquestrador/status.py`

O `--status` do orquestrador: onde o Goal está, o que prova que ele está pronto, o que cada fatia fez e quanto custou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |

### Funções do módulo

- `formatar_status(estado: EstadoDoGoal, registros: Sequence[SessaoRegistrada]) -> list[str]` — As linhas do status do Goal.

## `orquestrador/suite.py`

A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VARIAVEL_DO_SHELL` | `str` | `'GRAPHOW_SHELL'` |
| `VARIAVEL_DO_GIT_BASH` | `str` | `'CLAUDE_CODE_GIT_BASH_PATH'` |
| `SHELL_DA_MAQUINA` | `str` | `'o shell da maquina (cmd no Windows, /bin/sh fora dele)'` |
| `TEMPO_LIMITE_DA_SUITE_S` | `float` | `1800.0` |
| `LIMITE_DA_SAIDA` | `int` | `20000` |
| `BYTES_DE_CONTINUACAO` | `bytes` | `bytes(range(128, 192))` |
| `LIMITE_DO_TRECHO` | `int` | `2000` |
| `AMBIENTE_SEM_CACHE` | `dict[str, str]` | `{'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_ADDOPTS': '-p no:cacheprovider…` |

### `ResultadoDaSuite`

*DTO imutável* — Como a suíte terminou e o fim do que ela imprimiu.

**Campos:** `comando: str`, `codigo: int | None`, `saida: str`, `tempo_esgotado: bool`, `shell: str`

- `passou() -> bool` `[property]` — Saiu com zero dentro do tempo.
- `descrever() -> str` — O resultado para o briefing da nova tentativa.

### Funções do módulo

- `shell_dos_agentes() -> Path | None` — O bash em que a ferramenta Bash das sessões roda; None quando a máquina não tem um.
- `descrever_shell(shell: Path | None) -> str` — O shell da suíte em palavras, para o briefing e para o resultado.
- `rodar_suite(area: Path, comando: str, banco_descartavel: Path) -> ResultadoDaSuite` — Roda o comando na área, no shell dos agentes, e devolve o resultado.
- `arquivos_ocultos(area: Path, arquivos: Sequence[str], guarda: Path) -> Iterator[None]` — Tira da área os arquivos dados enquanto o bloco roda e os devolve depois, mesmo se o bloco falhar.

## `orquestrador/trava_do_git.py`

A trava do git nas sessões de agente: as regras, o ambiente e a restauração do clone depois de cada sessão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `HOOKS_DA_TRAVA` | `Mapping[str, str]` | `{'reference-transaction': '#!/bin/sh\n# Trava do graphow orquestrar: a …` |
| `SUBCOMANDOS_DE_ESCRITA` | `tuple[str, ...]` | `('commit', 'push', 'pull', 'fetch', 'reset', 'checkout', 'switch', 'res…` |
| `OPCOES_GLOBAIS_NEGADAS` | `tuple[str, ...]` | `('-c', '-C', '--git-dir', '--work-tree', '--exec-path')` |

### `FotoDoClone`

*DTO imutável* — O clone antes de uma sessão de agente: a branch do HEAD, as refs e a configuração.

**Campos:** `area: Path`, `ramo: str`, `refs: Mapping[str, str]`, `configuracao: bytes`

- `ref_do_ramo() -> str` `[property]` — A ref da branch do Goal.

### Funções do módulo

- `instalar_trava(pasta: Path) -> dict[str, str]` — Grava os hooks da trava na pasta e devolve o ambiente que a liga numa sessão de agente.
- `regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]` — As regras `--disallowedTools` do git de escrita e das opções que trocam de repositório ou de configuração.
- `fotografar_clone(area: Path) -> FotoDoClone` — A foto do clone, tirada logo antes da sessão.
- `restaurar_o_clone(foto: FotoDoClone) -> str` — Deixa o clone como a foto: a branch do Goal, as outras refs, a configuração e os hooks; diz o que desfez.

## `orquestrador/validacao_json.py`

Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DO_JSON` | `Mapping[str, tuple[type, ...]]` | `{'object': (dict,), 'array': (list,), 'string': (str,), 'integer': (int…` |

### Funções do módulo

- `validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str) -> tuple[str, ...]` — Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere.

## `orquestrador/verificacao_do_goal.py`

O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal.

### Funções do módulo

- `verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None` — Com as fatias do marco concluídas: verifica o commit atual, abre correções, segue ao próximo marco ou fecha.

## `orquestrador/verificacao_do_marco.py`

A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão.

### Funções do módulo

- `verificar_marco(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None` — Uma sessão nova do verificador no commit atual e a suíte do plano, gravadas como Evidence do Goal.
- `criterios_ate_o_marco(estado: EstadoDoGoal, marco: MarcoRegistrado) -> tuple[str, ...]` — Os critérios que os marcos até este, inclusive, completaram: os que já podem ser julgados ou feridos.
- `decisoes_do_plano(estado: EstadoDoGoal) -> tuple[str, ...]` — Os ids das decisões do plano.
- `nos_do_plano(plano: Mapping[str, Any]) -> dict[str, str]` — O nó do livro-razão de cada critério e decisão do plano, pelo código.
- `sincronizar_documento(contexto: ContextoDoGoal, pendencias: Sequence[Mapping[str, Any]]) -> None` — Reescreve a seção de pendências do documento como o livro-razão a tem e commita, se ele mudou.

