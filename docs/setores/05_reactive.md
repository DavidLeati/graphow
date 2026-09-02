# Setor 05 — Motor Reativo

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.reactive`

Comportamentos desacoplados que observam commits e propõem patches derivados, com limite de cascata e guarda de reentrância.

## Inventário

8 módulos · 471 linhas · 10 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`reactive/builtins.py`](#reactivebuiltins) | 95 | Comportamentos reativos nativos desacoplados do Graphow. |
| [`reactive/diagnostico.py`](#reactivediagnostico) | 58 | Registro das reações que o kernel recusou, para que nenhuma morra calada. |
| [`reactive/engine.py`](#reactiveengine) | 104 | Motor reativo que processa eventos e orquestra comportamentos desacoplados. |
| [`reactive/interfaces.py`](#reactiveinterfaces) | 22 | Interface abstrata para comportamentos reativos desacoplados. |
| [`reactive/montagem.py`](#reactivemontagem) | 25 | Montagem padrão do motor reativo com os comportamentos nativos do Graphow. |
| [`reactive/notas.py`](#reactivenotas) | 111 | Montagem das notas reativas: sempre ligadas à sessão e ao nó que as motivou. |
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

