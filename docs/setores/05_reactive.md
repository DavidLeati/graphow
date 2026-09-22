# Setor 05 — Motor Reativo

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.reactive`

Comportamentos desacoplados que observam commits e propõem patches derivados, com limite de cascata e guarda de reentrância.

## Inventário

10 módulos · 881 linhas · 14 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`reactive/builtins.py`](#reactivebuiltins) | 95 | Comportamentos reativos nativos desacoplados do Graphow. |
| [`reactive/condensacao.py`](#reactivecondensacao) | 169 | Condensação pedida pelo próprio grafo: a sessão encerra e o motor abre a Task. |
| [`reactive/consolidacao.py`](#reactiveconsolidacao) | 225 | Consolidação pedida pelo próprio grafo: os aprendizados de um alcance se acumulam e o motor abre a Task. |
| [`reactive/diagnostico.py`](#reactivediagnostico) | 57 | Registro das reações que o kernel recusou, para que nenhuma morra calada. |
| [`reactive/engine.py`](#reactiveengine) | 104 | Motor reativo que processa eventos e orquestra comportamentos desacoplados. |
| [`reactive/interfaces.py`](#reactiveinterfaces) | 22 | Interface abstrata para comportamentos reativos desacoplados. |
| [`reactive/montagem.py`](#reactivemontagem) | 43 | Montagem padrão do motor reativo com os comportamentos nativos do Graphow. |
| [`reactive/notas.py`](#reactivenotas) | 110 | Montagem das notas reativas: sempre ligadas à sessão e ao nó que as motivou. |
| [`reactive/observador_reativo.py`](#reactiveobservadorreativo) | 41 | Adaptador que liga o motor reativo ao gancho pós-commit do kernel. |

## `reactive/builtins.py`

Comportamentos reativos nativos desacoplados do Graphow.

### `ReavaliacaoDecisaoSubstituidaBehavior` (ComportamentoReativo)

*serviço* — Invalidação de tarefas dependentes quando uma Decisão é substituída.

- `nome() -> str` `[property]` — Nome identificador do comportamento.
- `avaliar(evento: EventoLog, view: GrafoView) -> PropostaPatch | None` — Detecta criação de aresta 'substitui' entre Decisões.

### `RevisorNotificadoBehavior` (ComportamentoReativo)

*serviço* — Acorda o revisor quando uma Task transiciona para 'pronto_para_revisao'.

- `nome() -> str` `[property]` — Nome identificador do comportamento.
- `avaliar(evento: EventoLog, view: GrafoView) -> PropostaPatch | None` — Verifica transição de status para pronto_para_revisao.

## `reactive/condensacao.py`

Condensação pedida pelo próprio grafo: a sessão encerra e o motor abre a Task.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ACAO_DE_CONDENSAR` | `str` | `'condensar_sessao'` |
| `ACAO_DE_CONSOLIDAR` | `str` | `'consolidar_aprendizados'` |
| `ACOES_ABERTAS_PELO_GRAFO` | `frozenset[str]` | `frozenset({ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR})` |
| `AUTOR_DO_CONDENSADOR` | `str` | `'comportamento-condensador'` |
| `PREFIXO_DA_TAREFA` | `str` | `'task-condensar'` |
| `CAMPO_ACAO` | `str` | `'acao'` |
| `CAMPO_ALVO` | `str` | `'id_alvo'` |
| `ROTEIRO_DA_CONDENSACAO` | `str` | `f"Leia a sessao com ler_vista e escreva uma Note produzida por ela, com…` |
| `CRITERIO_DE_PRONTO` | `str` | `'Note de condensacao produzida pela sessao, com deriva_de para cada no …` |
| `TIPOS_QUE_PEDEM_CONDENSACAO` | `frozenset[TipoNo]` | `frozenset({TipoNo.GOAL, TipoNo.TASK, TipoNo.DECISION, TipoNo.QUESTION, …` |

### `SessaoEncerradaBehavior` (ComportamentoReativo)

*serviço* — Abre a Task de condensação quando uma Sessao passa a `concluida`.

- `nome() -> str` `[property]` — Nome identificador do comportamento.
- `avaliar(evento: EventoLog, view: GrafoView) -> PropostaPatch | None` — Reage à escrita do status `concluida` numa Sessao com trabalho a condensar.

### Funções do módulo

- `produzidos_pela_sessao(id_sessao: str, view: GrafoView) -> tuple[NoGrafo, ...]` — Nós que a sessão produziu, na ordem estável dos identificadores.
- `tem_trabalho_a_condensar(id_sessao: str, view: GrafoView) -> bool` — Há conhecimento na sessão além da telemetria e das Tasks que o grafo abriu nela sozinho.
- `tem_condensacao_pendente(id_sessao: str, view: GrafoView) -> bool` — Uma Task de condensar ainda aberta: pedir outra seria pedir duas vezes.
- `eh_tarefa_de_condensacao(no: NoGrafo) -> bool` — Reconhece a Task que este comportamento abre.
- `eh_tarefa_aberta_pelo_grafo(no: NoGrafo) -> bool` — Condensar a sessão ou consolidar aprendizados: pedido do grafo, não trabalho da sessão.
- `montar_proposta_de_condensacao(sessao: NoGrafo) -> PropostaPatch` — A Task pendurada na sessão que a motivou, assinada pelo papel que cria Task.

## `reactive/consolidacao.py`

Consolidação pedida pelo próprio grafo: os aprendizados de um alcance se acumulam e o motor abre a Task.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AUTOR_DO_CONSOLIDADOR` | `str` | `'comportamento-consolidador'` |
| `PREFIXO_DA_TAREFA` | `str` | `'task-consolidar'` |
| `LIMITE_DE_VIGENTES_POR_ALCANCE` | `int` | `12` |
| `ROTEIRO_DA_CONSOLIDACAO` | `str` | `'Leia os aprendizados vigentes deste alcance (expandir_no em cada id ab…` |
| `CRITERIO_DE_PRONTO` | `str` | `f'Aprendizados consolidados registrados, cada um com substitui para os …` |
| `GLOBAL` | `Alcance` | `Alcance(id=ALCANCE_GLOBAL, rotulo=ALCANCE_GLOBAL)` |

### `Alcance`

*DTO imutável* — Um lugar onde aprendizados valem: o id do contêiner ou a marca global, com o rótulo para a Task.

**Campos:** `id: str`, `rotulo: str`

### `AprendizadosAcumuladosBehavior` (ComportamentoReativo)

*serviço* — Abre a Task de consolidar quando uma Sessao abre num alcance com vigentes demais.

- `nome() -> str` `[property]` — Nome identificador do comportamento.
- `avaliar(evento: EventoLog, view: GrafoView) -> PropostaPatch | None` — Reage à Sessao criada ou reaberta; propõe uma Task por alcance lotado e sem pedido pendente.

### `PedidoDeConsolidacao`

*DTO imutável* — Um alcance que passou do limite e os vigentes que a Task vai listar.

**Campos:** `alcance: Alcance`, `vigentes: tuple[str, ...]`

### Funções do módulo

- `sessao_que_abre(evento: EventoLog, view: GrafoView) -> NoGrafo | None` — A Sessao que o evento cria ou devolve a `ativa`; None para qualquer outro evento.
- `pedidos_de_consolidacao(id_sessao: str, view: GrafoView) -> tuple[PedidoDeConsolidacao, ...]` — Os alcances da sessão que passaram do limite e ainda não têm Task de consolidar aberta.
- `alcances_da_sessao(id_sessao: str, view: GrafoView) -> tuple[Alcance, ...]` — O Setor da sessão, o Projeto dele e o global, nesta ordem; sem Setor, só o global.
- `alcances_do_setor(id_setor: str, view: GrafoView) -> tuple[Alcance, ...]` — O Setor, o Projeto que o contém e o global, nesta ordem.
- `vigentes_no_alcance(alcance: str, view: GrafoView) -> tuple[str, ...]` — Ids dos aprendizados vigentes que valem para o alcance, na ordem do log.
- `tarefas_de_consolidacao_pendentes(alcance: str, view: GrafoView) -> tuple[NoGrafo, ...]` — As Tasks de consolidar este alcance ainda abertas, em ordem estável.
- `tem_consolidacao_pendente(alcance: str, view: GrafoView) -> bool` — Uma Task de consolidar ainda aberta: pedir outra seria pedir duas vezes.
- `eh_tarefa_de_consolidacao(no: NoGrafo) -> bool` — Reconhece a Task que este comportamento abre.
- `montar_proposta_de_consolidacao(sessao: NoGrafo, pedidos: Sequence[PedidoDeConsolidacao]) -> PropostaPatch` — Uma Task por alcance lotado, pendurada na sessão que abre e assinada pelo papel que cria Task.

## `reactive/diagnostico.py`

Registro das reações que o kernel recusou, para que nenhuma morra calada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_RECUSAS_RETIDAS` | `int` | `64` |

### `ReacaoRecusada`

*DTO imutável* — O que o kernel recusou, e por quê, ao avaliar um comportamento reativo.

**Campos:** `comportamento: str`, `id_evento_gatilho: str`, `mensagem: str`, `modo_de_falha: str | None`

- `descrever() -> str` — Linha legível para diagnóstico, com o modo MAST quando houver.

### `RegistroDeReacoes` (ABC)

*contrato* — Destino das recusas observadas pelo motor reativo.

- `registrar(recusa: ReacaoRecusada) -> None` `[abstract]` — Guarda a recusa para inspeção posterior.
- `listar() -> tuple[ReacaoRecusada, ...]` `[abstract]` — Recusas retidas, da mais antiga para a mais recente.

### `RegistroEmMemoria` (RegistroDeReacoes)

*serviço* — Retém as últimas recusas em memória, com teto para não crescer sem fim.

- `registrar(recusa: ReacaoRecusada) -> None` — Acrescenta a recusa, descartando a mais antiga ao estourar o teto.
- `listar() -> tuple[ReacaoRecusada, ...]` — Instantâneo imutável das recusas retidas, em ordem de chegada.

## `reactive/engine.py`

Motor reativo que processa eventos e orquestra comportamentos desacoplados.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_CASCATA_PADRAO` | `int` | `3` |

### `ContextoReacao`

*DTO imutável* — Estado imutável de uma rodada de avaliação de comportamentos reativos.

**Campos:** `evento: EventoLog`, `view: GrafoView`, `profundidade: int`

### `MotorReativo`

*serviço* — Despachante reativo que escuta mutações de log e invoca comportamentos.

- `registrar_comportamento(comportamento: ComportamentoReativo) -> None` — Registra um novo comportamento reativo no motor.
- `comportamentos_registrados() -> tuple[str, ...]` `[property]` — Nomes dos comportamentos ativos, em ordem estável de registro.
- `recusas_registradas() -> tuple[ReacaoRecusada, ...]` `[property]` — Reações que o kernel recusou desde a construção do motor.
- `processar_evento(evento: EventoLog, profundidade: int) -> list[str]` — Dispara avaliação para todos os comportamentos registrados sobre o evento.

## `reactive/interfaces.py`

Interface abstrata para comportamentos reativos desacoplados.

### `ComportamentoReativo` (ABC)

*contrato* — Contrato formal: escuta evento, consulta GrafoView e emite no máximo uma PropostaPatch.

- `nome() -> str` `[property]` `[abstract]` — Nome identificador único do comportamento.
- `avaliar(evento: EventoLog, view: GrafoView) -> PropostaPatch | None` `[abstract]` — Processa a mutação e decide se deve propor um patch reativo.

## `reactive/montagem.py`

Montagem padrão do motor reativo com os comportamentos nativos do Graphow.

### Funções do módulo

- `montar_comportamentos_padrao() -> tuple[ComportamentoReativo, ...]` — Lista os comportamentos reativos que o produto ativa por padrão.
- `montar_motor_reativo_padrao(kernel: WriteKernel) -> MotorReativo` — Constrói o motor reativo com os comportamentos nativos já registrados.
- `ligar_motor_reativo_padrao(kernel: WriteKernel) -> MotorReativo` — Monta o motor padrão e o inscreve no gancho pós-commit do kernel.

## `reactive/notas.py`

Montagem das notas reativas: sempre ligadas à sessão e ao nó que as motivou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_ORIGEM_DE_SESSAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ, TipoAresta.CONTEM})` |

### `PedidoDeNota`

*DTO imutável* — Tudo o que uma nota reativa precisa para nascer conectada.

**Campos:** `prefixo: str`, `rotulo: str`, `id_alvo: str`, `id_sessao: str`, `autor: str`, `papel: PapelAutor`, `propriedades: Mapping[str, Any]`

- `identificador() -> str` `[property]` — Identificador único e legível da nota a ser criada.

### Funções do módulo

- `localizar_sessao_de(id_no: str, view: GrafoView) -> str | None` — Encontra a Sessao que produziu o nó, subindo uma aresta de origem.
- `montar_proposta_de_nota(pedido: PedidoDeNota) -> PropostaPatch` — Cria a nota, o vínculo com a sessão e a aresta que aponta para o alvo.

## `reactive/observador_reativo.py`

Adaptador que liga o motor reativo ao gancho pós-commit do kernel.

### `ObservadorReativo` (ObservadorCommit)

*serviço* — Encaminha os eventos commitados ao motor reativo, sem recursão dupla.

- `nome() -> str` `[property]` — Nome identificador do observador.
- `notificar(eventos: Sequence[EventoLog]) -> None` — Processa cada evento do lote, ignorando chamadas reentrantes.

