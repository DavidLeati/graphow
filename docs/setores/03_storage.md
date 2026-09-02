# Setor 03 — Persistência Append-Only

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.storage`

Repositórios de eventos, locks e linhagem de ramos. Resolve onde o banco vive, migra bancos antigos e repara sequências duplicadas.

## Inventário

11 módulos · 1326 linhas · 31 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`storage/composicao.py`](#storagecomposicao) | 51 | Fábricas que montam o conjunto de repositórios usado pelo kernel. |
| [`storage/in_memory_store.py`](#storageinmemorystore) | 80 | Implementação em memória do repositório de eventos append-only. |
| [`storage/interfaces.py`](#storageinterfaces) | 83 | Interfaces abstratas de contrato para persistência de eventos e locks. |
| [`storage/linhagem_ramo.py`](#storagelinhagemramo) | 157 | Definição e persistência da linhagem entre ramos do log de eventos. |
| [`storage/localizador_banco.py`](#storagelocalizadorbanco) | 158 | Resolução do caminho do banco de eventos fora de pastas sincronizadas por nuvem. |
| [`storage/lock_store.py`](#storagelockstore) | 112 | Repositórios de locks exclusivos de escrita sobre tarefas. |
| [`storage/migrador_banco.py`](#storagemigradorbanco) | 134 | Migração segura do banco de eventos entre localizações, preservando o WAL. |
| [`storage/reparo_sequencia.py`](#storagereparosequencia) | 209 | Diagnóstico e reparo de sequências duplicadas no log de eventos. |
| [`storage/repositorio_com_linhagem.py`](#storagerepositoriocomlinhagem) | 74 | Repositório de eventos que compõe a leitura de um ramo com a herança do pai. |
| [`storage/sqlite_store.py`](#storagesqlitestore) | 261 | Implementação SQLite append-only do repositório de eventos. |

## `storage/composicao.py`

Fábricas que montam o conjunto de repositórios usado pelo kernel.

### `ConjuntoRepositorios`

*DTO imutável* — Repositórios já compostos e prontos para injeção no kernel.

**Campos:** `eventos: RepositorioEventos`, `ramos: RepositorioRamos`, `locks: RepositorioLocks`

### Funções do módulo

- `montar_repositorios_em_memoria() -> ConjuntoRepositorios` — Monta o conjunto efêmero, com linhagem de ramos resolvida na leitura.
- `montar_repositorios_sqlite(store: SQLiteEventStore) -> ConjuntoRepositorios` — Monta o conjunto persistente sobre um arquivo SQLite já aberto.
- `abrir_repositorios_sqlite(caminho_banco: str | Path) -> tuple[SQLiteEventStore, ConjuntoRepositorios]` — Abre o arquivo e devolve o store cru junto do conjunto composto.

## `storage/in_memory_store.py`

Implementação em memória do repositório de eventos append-only.

### `InMemoryEventStore` (RepositorioEventos)

*serviço* — Armazenamento em memória thread-safe para testes e prototipação ultrarrápida.

- `append_evento(evento: EventoLog) -> None` — Adiciona um novo evento no log em memória com garantia de ordem.
- `append_eventos(eventos: Sequence[EventoLog]) -> None` — Adiciona o lote inteiro ou nenhum, espelhando a atomicidade do SQLite.
- `ler_eventos(ramo_id: str) -> list[EventoLog]` — Retorna cópia da lista de eventos de um ramo ordenada por sequência.
- `ler_eventos_ate_seq(ramo_id: str, seq_limite: int) -> list[EventoLog]` — Lê eventos de um ramo filtrados até a sequência limite.
- `ler_eventos_desde_seq(ramo_id: str, seq_exclusivo: int) -> list[EventoLog]` — Lê apenas os eventos posteriores à sequência informada.
- `obter_ultimo_seq(ramo_id: str) -> int` — Retorna a sequência do último evento persistido no ramo.
- `listar_ramos() -> list[str]` — Lista identificadores de todos os ramos criados.
- `obter_evento_por_id(id_evento: str) -> EventoLog | None` — Localiza um evento pelo identificador único.

## `storage/interfaces.py`

Interfaces abstratas de contrato para persistência de eventos e locks.

### `RepositorioEventos` (ABC)

*contrato* — Contrato abstrato de armazenamento para eventos transacionais append-only.

- `append_evento(evento: EventoLog) -> None` `[abstract]` — Persiste um único evento no log.
- `append_eventos(eventos: Sequence[EventoLog]) -> None` `[abstract]` — Persiste um lote de eventos de forma atômica: ou todos, ou nenhum.
- `ler_eventos(ramo_id: str) -> list[EventoLog]` `[abstract]` — Lê todos os eventos ordenados por número de sequência para um ramo.
- `ler_eventos_ate_seq(ramo_id: str, seq_limite: int) -> list[EventoLog]` `[abstract]` — Lê eventos de um ramo até um número limite de sequência inclusive.
- `ler_eventos_desde_seq(ramo_id: str, seq_exclusivo: int) -> list[EventoLog]` `[abstract]` — Lê os eventos de um ramo posteriores à sequência informada, exclusive.
- `obter_ultimo_seq(ramo_id: str) -> int` `[abstract]` — Retorna o número da última sequência registrada no ramo.
- `listar_ramos() -> list[str]` `[abstract]` — Lista todos os identificadores de ramos existentes no store.
- `obter_evento_por_id(id_evento: str) -> EventoLog | None` `[abstract]` — Busca um evento específico pelo seu identificador único.

### `RepositorioLocks` (ABC)

*contrato* — Contrato de coordenação de escrita exclusiva sobre tarefas.

- `tentar_adquirir(id_task: str, autor: str) -> bool` `[abstract]` — Adquire o lock para o autor, ou confirma que ele já é o dono.
- `liberar(id_task: str, autor: str) -> bool` `[abstract]` — Libera o lock, se pertencer ao autor solicitante.
- `obter_dono(id_task: str) -> str | None` `[abstract]` — Consulta quem detém o lock da tarefa, se houver alguém.
- `listar_locks() -> dict[str, str]` `[abstract]` — Devolve um instantâneo do mapa de tarefa para autor detentor.

## `storage/linhagem_ramo.py`

Definição e persistência da linhagem entre ramos do log de eventos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DDL_TABELA_RAMOS` | `str` | `"\n CREATE TABLE IF NOT EXISTS ramos (\n ramo_id TEXT PRIMARY KEY,\n ra…` |
| `PROFUNDIDADE_MAXIMA_DE_LINHAGEM` | `int` | `32` |

### `DefinicaoRamo`

*DTO imutável* — Ponteiro imutável de um ramo para o ponto de corte no ramo de origem.

**Campos:** `ramo_id: str`, `ramo_base: str`, `seq_corte: int`, `evento_corte_id: str | None`

### `RepositorioRamos` (ABC)

*contrato* — Contrato de persistência das definições de ramificação.

- `registrar(definicao: DefinicaoRamo) -> None` `[abstract]` — Grava a definição de um novo ramo derivado.
- `obter_definicao(ramo_id: str) -> DefinicaoRamo | None` `[abstract]` — Recupera a definição do ramo, ou None se ele for raiz.
- `listar_ramos_derivados() -> tuple[str, ...]` `[abstract]` — Enumera os ramos que possuem definição de linhagem registrada.

### `RepositorioRamosEmMemoria` (RepositorioRamos)

*serviço* — Linhagem mantida apenas em memória, para testes e execução efêmera.

- `registrar(definicao: DefinicaoRamo) -> None` — Grava a definição, recusando a redefinição de um ramo existente.
- `obter_definicao(ramo_id: str) -> DefinicaoRamo | None` — Consulta a definição do ramo informado.
- `listar_ramos_derivados() -> tuple[str, ...]` — Enumera os ramos derivados em ordem estável.

### `RepositorioRamosSQLite` (RepositorioRamos)

*serviço* — Linhagem persistida no mesmo arquivo do log de eventos.

- `registrar(definicao: DefinicaoRamo) -> None` — Grava a definição, recusando a redefinição de um ramo existente.
- `obter_definicao(ramo_id: str) -> DefinicaoRamo | None` — Consulta a definição do ramo informado.
- `listar_ramos_derivados() -> tuple[str, ...]` — Enumera os ramos derivados em ordem estável.

### `ResolvedorLinhagem`

*serviço* — Consulta pura que descreve de onde cada ramo herda os próprios eventos.

- `resolver_cadeia(ramo_id: str) -> tuple[DefinicaoRamo, ...]` — Devolve a cadeia de heranças, do ramo consultado até a raiz.
- `obter_seq_corte(ramo_id: str) -> int` — Sequência a partir da qual o ramo passa a ter eventos próprios.

## `storage/localizador_banco.py`

Resolução do caminho do banco de eventos fora de pastas sincronizadas por nuvem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOME_ARQUIVO_BANCO_PADRAO` | `str` | `'graphow.db'` |
| `NOME_PASTA_APLICACAO` | `str` | `'graphow'` |
| `VARIAVEL_CAMINHO_BANCO` | `str` | `'GRAPHOW_DB'` |
| `PASTAS_SINCRONIZADAS_CONHECIDAS` | `tuple[str, ...]` | `('onedrive', 'dropbox', 'google drive', 'googledrive', 'icloud', 'iclou…` |

### `AmbienteEmMemoria` (ProvedorAmbiente)

*serviço* — Adaptador de ambiente controlado, para testes e simulações determinísticas.

- `obter_variavel(nome: str) -> str | None` — Lê a variável do dicionário fornecido na construção.
- `obter_diretorio_home() -> Path` — Retorna o diretório pessoal fornecido na construção.

### `AmbienteSistemaOperacional` (ProvedorAmbiente)

*serviço* — Adaptador concreto de leitura do ambiente real do processo.

- `obter_variavel(nome: str) -> str | None` — Lê a variável diretamente de os.environ.
- `obter_diretorio_home() -> Path` — Resolve o diretório pessoal via pathlib.

### `LocalizacaoBanco`

*DTO imutável* — Resultado imutável da resolução do caminho do banco de eventos.

**Campos:** `caminho: Path`, `origem: OrigemCaminhoBanco`, `esta_em_pasta_sincronizada: bool`

- `caminho_absoluto_texto() -> str` `[property]` — Caminho em forma textual absoluta, pronto para o driver do SQLite.
- `diretorio_pai() -> Path` `[property]` — Diretório que precisa existir antes de o banco ser aberto.

### `LocalizadorBancoEventos`

*serviço* — Resolve, sem efeitos colaterais, onde o banco de eventos deve residir.

- `resolver(caminho_explicito: str | None) -> LocalizacaoBanco` — Consulta pura: precedência argumento > variável de ambiente > diretório de dados.

### `OrigemCaminhoBanco` (str, Enum)

*serviço* — De onde veio o caminho resolvido para o banco de eventos.

### `PreparadorDiretorioBanco`

*serviço* — Comando de infraestrutura que garante a existência do diretório do banco.

- `garantir_diretorio(localizacao: LocalizacaoBanco) -> None` — Cria o diretório pai do banco, se ainda não existir.

### `ProvedorAmbiente` (ABC)

*contrato* — Contrato de leitura do ambiente do sistema operacional.

- `obter_variavel(nome: str) -> str | None` `[abstract]` — Lê uma variável de ambiente, ou None se não estiver definida.
- `obter_diretorio_home() -> Path` `[abstract]` — Retorna o diretório pessoal do usuário corrente.

### Funções do módulo

- `caminho_esta_em_pasta_sincronizada(caminho: Path) -> bool` — Detecta se algum segmento do caminho pertence a um sincronizador de nuvem.

## `storage/lock_store.py`

Repositórios de locks exclusivos de escrita sobre tarefas.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DDL_TABELA_LOCKS` | `str` | `"\n CREATE TABLE IF NOT EXISTS locks_de_tarefa (\n id_task TEXT PRIMARY…` |

### `LockStoreEmMemoria` (RepositorioLocks)

*serviço* — Coordenação de locks dentro de um único processo, para testes e uso efêmero.

- `tentar_adquirir(id_task: str, autor: str) -> bool` — Adquire o lock se estiver livre ou já pertencer ao mesmo autor.
- `liberar(id_task: str, autor: str) -> bool` — Libera o lock apenas se o solicitante for o detentor.
- `obter_dono(id_task: str) -> str | None` — Consulta o detentor atual do lock da tarefa.
- `listar_locks() -> dict[str, str]` — Devolve uma cópia do mapa de locks ativos.

### `LockStoreSQLite` (RepositorioLocks)

*serviço* — Coordenação de locks compartilhada entre processos pelo mesmo arquivo SQLite.

- `tentar_adquirir(id_task: str, autor: str) -> bool` — Insere o lock de forma atômica, respeitando um detentor preexistente.
- `liberar(id_task: str, autor: str) -> bool` — Remove o lock apenas quando o autor informado é o detentor registrado.
- `obter_dono(id_task: str) -> str | None` — Consulta o detentor do lock diretamente no banco compartilhado.
- `listar_locks() -> dict[str, str]` — Devolve um instantâneo de todos os locks ativos no banco.

## `storage/migrador_banco.py`

Migração segura do banco de eventos entre localizações, preservando o WAL.

### `AcessoBancoSQLite` (ABC)

*contrato* — Contrato de operações de infraestrutura sobre arquivos SQLite.

- `arquivo_existe(caminho: Path) -> bool` `[abstract]` — Informa se o arquivo de banco está presente no sistema de arquivos.
- `contar_eventos(caminho: Path) -> int` `[abstract]` — Conta os eventos persistidos, incluindo os que ainda vivem apenas no WAL.
- `copiar_com_checkpoint(caminho_origem: Path, caminho_destino: Path) -> None` `[abstract]` — Consolida o WAL e replica o banco íntegro no destino.

### `AcessoBancoSQLitePadrao` (AcessoBancoSQLite)

*serviço* — Adaptador concreto sobre o driver sqlite3 da biblioteca padrão.

- `arquivo_existe(caminho: Path) -> bool` — Verifica presença do arquivo principal do banco.
- `contar_eventos(caminho: Path) -> int` — Abre o banco em modo leitura e conta a tabela de eventos.
- `copiar_com_checkpoint(caminho_origem: Path, caminho_destino: Path) -> None` — Consolida o WAL na origem e usa a API de backup do SQLite para replicar.

### `AnalisadorMigracaoBanco`

*serviço* — Consulta pura que decide se e por que uma migração deve ocorrer.

- `planejar(caminho_origem: Path, caminho_destino: Path) -> PlanoMigracao` — Monta o plano de migração sem alterar nada em disco.

### `MigradorBancoEventos`

*serviço* — Comando que executa um plano de migração previamente calculado.

- `executar(plano: PlanoMigracao) -> None` — Replica o banco no destino. A origem permanece intacta como backup.

### `PlanoMigracao`

*DTO imutável* — Diagnóstico imutável do que uma migração faria, sem executá-la.

**Campos:** `caminho_origem: Path`, `caminho_destino: Path`, `eventos_na_origem: int`, `destino_ja_existe: bool`, `deve_migrar: bool`, `motivo: str`

## `storage/reparo_sequencia.py`

Diagnóstico e reparo de sequências duplicadas no log de eventos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DESLOCAMENTO_TEMPORARIO` | `int` | `1000000000` |

### `AcessoSequencias` (ABC)

*contrato* — Contrato de acesso de baixo nível à tabela de eventos, para reparo.

- `listar_ramos() -> tuple[str, ...]` `[abstract]` — Enumera os ramos presentes no log.
- `listar_registros(ramo_id: str) -> tuple[RegistroEvento, ...]` `[abstract]` — Lê os registros do ramo em ordem determinística de sequência e tempo.
- `aplicar_reparo(diagnostico: DiagnosticoRamo) -> None` `[abstract]` — Remove duplicatas e renumera o ramo em uma única transação.

### `AcessoSequenciasSQLite` (AcessoSequencias)

*serviço* — Adaptador que opera diretamente no arquivo, mesmo quando ele está inconsistente.

- `listar_ramos() -> tuple[str, ...]` — Enumera os ramos distintos registrados na tabela de eventos.
- `listar_registros(ramo_id: str) -> tuple[RegistroEvento, ...]` — Lê o ramo ordenado por sequência, tempo e identificador, nesta ordem.
- `aplicar_reparo(diagnostico: DiagnosticoRamo) -> None` — Aplica remoção e renumeração dentro de uma transação única e reversível.

### `AnalisadorSequencias`

*serviço* — Consulta pura que descreve o reparo necessário sem tocar no banco.

- `diagnosticar_todos_os_ramos() -> tuple[DiagnosticoRamo, ...]` — Diagnostica cada ramo existente no log.
- `diagnosticar(ramo_id: str) -> DiagnosticoRamo` — Monta o plano de deduplicação e renumeração contígua do ramo.

### `DiagnosticoRamo`

*DTO imutável* — Resultado imutável da inspeção de um ramo do log.

**Campos:** `ramo_id: str`, `total_eventos: int`, `posicoes_duplicadas: int`, `ids_a_remover: tuple[str, ...]`, `renumeracao: Mapping[str, int]`, `posicoes_alteradas: int`

- `precisa_reparo() -> bool` `[property]` — Indica se há duplicatas ou lacunas de numeração a corrigir.

### `RegistroEvento`

*DTO imutável* — Projeção mínima de um evento, suficiente para ordenar e deduplicar.

**Campos:** `id: str`, `seq: int`, `timestamp_utc: str`, `parent_evento_id: str | None`, `tipo_evento: str`, `payload_json: str`

- `assinatura_de_conteudo() -> tuple[str, str, str]` `[property]` — Identidade do conteúdo, para reconhecer cópias geradas por fork repetido.

### `ReparadorSequencias`

*serviço* — Comando que executa o plano de reparo previamente diagnosticado.

- `reparar(diagnostico: DiagnosticoRamo) -> None` — Aplica o reparo do ramo, se ele for necessário.

## `storage/repositorio_com_linhagem.py`

Repositório de eventos que compõe a leitura de um ramo com a herança do pai.

### `RepositorioEventosComLinhagem` (RepositorioEventos)

*serviço* — Decorador que resolve a herança entre ramos em toda leitura do log.

- `append_evento(evento: EventoLog) -> None` — Grava o evento como próprio do ramo informado.
- `append_eventos(eventos: Sequence[EventoLog]) -> None` — Grava o lote como eventos próprios do ramo informado.
- `ler_eventos(ramo_id: str) -> list[EventoLog]` — Lê o prefixo herdado seguido dos eventos próprios, em ordem de sequência.
- `ler_eventos_ate_seq(ramo_id: str, seq_limite: int) -> list[EventoLog]` — Lê a composição do ramo até a sequência limite inclusive.
- `ler_eventos_desde_seq(ramo_id: str, seq_exclusivo: int) -> list[EventoLog]` — Lê a composição do ramo a partir da sequência informada, exclusive.
- `obter_ultimo_seq(ramo_id: str) -> int` — Maior sequência visível no ramo, contando o que ele herdou.
- `listar_ramos() -> list[str]` — Lista os ramos com eventos próprios somados aos ramos apenas declarados.
- `obter_evento_por_id(id_evento: str) -> EventoLog | None` — Busca um evento pelo identificador no repositório subjacente.

## `storage/sqlite_store.py`

Implementação SQLite append-only do repositório de eventos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAGINAS_ATE_CHECKPOINT_AUTOMATICO` | `int` | `256` |
| `COLUNAS_EVENTO` | `str` | `'id, seq, timestamp_utc, autor, papel, origem, tipo_evento, payload_jso…` |
| `COLUNA_VERSAO_ONTOLOGIA` | `str` | `'versao_ontologia'` |
| `DDL_COLUNA_VERSAO_ONTOLOGIA` | `str` | `f'ALTER TABLE eventos ADD COLUMN {COLUNA_VERSAO_ONTOLOGIA} TEXT;'` |
| `DDL_TABELA_EVENTOS` | `str` | `'\n CREATE TABLE IF NOT EXISTS eventos (\n id TEXT PRIMARY KEY,\n seq I…` |
| `DDL_INDICE_SEQ_UNICO` | `str` | `'CREATE UNIQUE INDEX IF NOT EXISTS idx_eventos_ramo_seq_unico ON evento…` |

### `SQLiteEventStore` (RepositorioEventos)

*serviço* — Armazenamento persistente local-first em SQLite para eventos append-only.

- `conexao() -> sqlite3.Connection` `[property]` — Conexão compartilhada, para adaptadores que residem no mesmo arquivo.
- `caminho_banco() -> str` `[property]` — Caminho do arquivo SQLite em uso por este repositório.
- `append_evento(evento: EventoLog) -> None` — Insere o evento de forma append-only no banco SQLite.
- `append_eventos(eventos: Sequence[EventoLog]) -> None` — Insere o lote inteiro em uma única transação: ou todos, ou nenhum.
- `ler_eventos(ramo_id: str) -> list[EventoLog]` — Lê todos os eventos de um ramo em ordem crescente de sequência.
- `ler_eventos_ate_seq(ramo_id: str, seq_limite: int) -> list[EventoLog]` — Lê eventos de um ramo até o limite superior de sequência inclusive.
- `ler_eventos_desde_seq(ramo_id: str, seq_exclusivo: int) -> list[EventoLog]` — Lê apenas os eventos posteriores à sequência informada, para atualização incremental.
- `obter_ultimo_seq(ramo_id: str) -> int` — Consulta o maior número de sequência no ramo especificado.
- `listar_ramos() -> list[str]` — Retorna a lista distinta de todos os ramos existentes.
- `obter_evento_por_id(id_evento: str) -> EventoLog | None` — Localiza e reconstrói um evento pelo ID.
- `consolidar_wal() -> None` — Move todo o conteúdo do WAL para o arquivo principal do banco.
- `fechar() -> None` — Consolida o WAL e fecha a conexão, para não deixar eventos fora do .db.

