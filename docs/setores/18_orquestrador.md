# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

9 módulos · 1421 linhas · 22 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 115 | Os schemas da saída de cada papel: o que o planejador, o executor e o verificador devolvem. |
| [`orquestrador/git_do_goal.py`](#orquestradorgitdogoal) | 228 | O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração. |
| [`orquestrador/gravacao_do_plano.py`](#orquestradorgravacaodoplano) | 115 | O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só. |
| [`orquestrador/leitura_do_goal.py`](#orquestradorleituradogoal) | 236 | O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações. |
| [`orquestrador/livro_razao.py`](#orquestradorlivrorazao) | 250 | O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`. |
| [`orquestrador/modelo_do_goal.py`](#orquestradormodelodogoal) | 128 | Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço. |
| [`orquestrador/saidas.py`](#orquestradorsaidas) | 256 | A saída de cada papel como objeto tipado, com a conferência que o schema não faz. |
| [`orquestrador/validacao_json.py`](#orquestradorvalidacaojson) | 81 | Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam. |

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
- `tentativas() -> int` `[property]` — Quantas sessões de executor a fatia já abriu.
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
- `iniciar_tentativa(id_task: str, tentativa: int) -> None` — A fatia entra em andamento, com a tentativa contada antes de a sessão abrir.
- `concluir_fatia(id_task: str, tentativa: int) -> None` — O commit vira Artifact da fatia, e a fatia fecha.
- `registrar_falha(id_task: str, tentativa: int) -> None` — A tentativa que falhou vira Note da fatia, e a fatia volta a pendente com o erro para a próxima.
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
| `CAMPO_CICLOS` | `str` | `'ciclos_de_correcao'` |
| `CAMPO_PENDENCIAS` | `str` | `'pendencias'` |
| `CAMPO_INTEGRADO_EM` | `str` | `'integrado_em'` |
| `CAMPO_STATUS` | `str` | `'status'` |
| `CAMPO_FATIA` | `str` | `'fatia'` |
| `CAMPO_OBJETIVO` | `str` | `'objetivo'` |
| `CAMPO_CRITERIOS` | `str` | `'criterios'` |
| `CAMPO_ARQUIVOS_ALVO` | `str` | `'arquivos_alvo'` |
| `CAMPO_MODELO` | `str` | `'modelo'` |
| `CAMPO_ORDEM` | `str` | `'ordem'` |
| `CAMPO_TENTATIVAS` | `str` | `'tentativas'` |
| `CAMPO_ULTIMO_ERRO` | `str` | `'ultimo_erro'` |
| `CAMPO_PATCH` | `str` | `'patch_da_tentativa'` |
| `CAMPO_PENDENCIA` | `str` | `'pendencia'` |
| `CAMPO_COMMIT` | `str` | `'commit'` |
| `CAMPO_CORRIGE` | `str` | `'corrige'` |
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

## `orquestrador/validacao_json.py`

Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DO_JSON` | `Mapping[str, tuple[type, ...]]` | `{'object': (dict,), 'array': (list,), 'string': (str,), 'integer': (int…` |

### Funções do módulo

- `validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str) -> tuple[str, ...]` — Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere.

