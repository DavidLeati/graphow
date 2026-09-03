# Setor 01 — Núcleo Ontológico

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.core`

Vocabulário da ontologia, modelos imutáveis do grafo, eventos do log, os modos de falha da taxonomia MAST e a hierarquia de exceções de domínio. Não depende de nenhum outro setor.

## Inventário

7 módulos · 619 linhas · 32 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`core/events.py`](#coreevents) | 93 | Definições de eventos de log transacionais append-only do Graphow. |
| [`core/exceptions.py`](#coreexceptions) | 65 | Hierarquia de exceções de domínio cirúrgicas do Graphow. |
| [`core/falhas.py`](#corefalhas) | 62 | Vocabulário de modos de falha, na taxonomia MAST (Cemri et al., 2025). |
| [`core/models.py`](#coremodels) | 204 | Modelos imutáveis do Grafo, Nós, Arestas e Metadados Temporais. |
| [`core/ontologia.py`](#coreontologia) | 47 | Versão declarada do vocabulário da ontologia e a impressão digital que a checa. |
| [`core/types.py`](#coretypes) | 92 | Definições de enumerações e tipos de valor base para a ontologia do Graphow. |

## `core/events.py`

Definições de eventos de log transacionais append-only do Graphow.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_ROTULO` | `str` | `'rotulo'` |
| `CAMPO_PROPRIEDADES` | `str` | `'propriedades'` |
| `CAMPO_PROPRIEDADES_REMOVIDAS` | `str` | `'propriedades_removidas'` |

### `DadosCriacaoEvento`

*DTO imutável* — DTO imutável para criação de novos eventos no log.

**Campos:** `seq: int`, `autor: str`, `papel: PapelAutor`, `tipo_evento: TipoEvento`, `payload: Mapping[str, Any]`, `origem: OrigemEvento`, `ramo_id: str`, `parent_evento_id: str | None`, `trace_id: str | None`, `versao_ontologia: str`

### `EventoLog`

*DTO imutável* — Evento imutável de log append-only para fonte de verdade determinística.

**Campos:** `id: str`, `seq: int`, `timestamp_utc: str`, `autor: str`, `papel: PapelAutor`, `origem: OrigemEvento`, `tipo_evento: TipoEvento`, `payload: Mapping[str, Any]`, `ramo_id: str`, `parent_evento_id: str | None`, `trace_id: str | None`, `versao_ontologia: str`

- `criar(dados: DadosCriacaoEvento) -> 'EventoLog'` — Fábrica com geração automática de UUID e timestamp ISO 8601 UTC via DTO.
- `serializar_payload_json() -> str` — Serializa o payload do evento em JSON ordenado determinístico.

### `TipoEvento` (str, Enum)

*serviço* — Tipos de eventos registráveis no log append-only.

## `core/exceptions.py`

Hierarquia de exceções de domínio cirúrgicas do Graphow.

### `ErroCicloDetectado` (ErroInvarianteGrafo)

*serviço* — Lançado quando uma aresta de dependência cria um ciclo proibido.

### `ErroConcorrenciaPersistente` (GraphowError)

*serviço* — Lançado quando as tentativas de resolver conflitos de escrita se esgotam.

### `ErroConflitoDeSequencia` (GraphowError)

*serviço* — Lançado quando dois escritores tentam ocupar a mesma posição do log.

### `ErroEntidadeNaoEncontrada` (GraphowError)

*serviço* — Lançado quando um nó, aresta ou evento solicitado não existe.

### `ErroInvarianteGrafo` (GraphowError)

*serviço* — Lançado quando uma mutação quebra uma regra de integridade relacional do grafo.

### `ErroLockConcorrencia` (GraphowError)

*serviço* — Lançado quando múltiplos escritores tentam adquirir lock sobre a mesma Task.

### `ErroNaoDeterminismo` (GraphowError)

*serviço* — Lançado quando uma projeção diverge em relação ao replay do log.

### `ErroOrcamentoExcedido` (GraphowError)

*serviço* — Lançado quando a materialização de contexto excede o orçamento estrito de tokens.

### `ErroPatchInvalido` (GraphowError)

*serviço* — Lançado quando a estrutura do JSON Patch é sintaticamente inválida.

### `ErroPermissaoPapel` (GraphowError)

*serviço* — Lançado quando um autor tenta executar uma ação não permitida para seu papel.

### `ErroSegurancaPatch` (GraphowError)

*serviço* — Lançado quando um patch tenta acessar campos protegidos (ex: prototype pollution).

### `ErroValidacaoOntologia` (GraphowError)

*serviço* — Lançado quando uma estrutura viola as regras da ontologia formal.

### `GraphowError` (Exception)

*serviço* — Exceção raiz para todas as falhas de domínio do Graphow.

- `formatar_para_llm() -> str` — Formata o erro de forma estruturada para autocorreção por agentes.

## `core/falhas.py`

Vocabulário de modos de falha, na taxonomia MAST (Cemri et al., 2025).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CATEGORIA_POR_MODO` | `Mapping[ModoFalhaMAST, CategoriaFalhaMAST]` | `{ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL: CategoriaFalhaMAST.DESALINHAME…` |

### `CategoriaFalhaMAST` (str, Enum)

*serviço* — 3 macro-categorias de falha em sistemas multi-agente conforme MAST.

### `ModoFalhaMAST` (str, Enum)

*serviço* — Modos específicos de falha que os portões do kernel sabem recusar.

### Funções do módulo

- `categoria_de(modo: ModoFalhaMAST) -> CategoriaFalhaMAST` — Macro-categoria MAST à qual o modo pertence, sem consulta a texto.

## `core/models.py`

Modelos imutáveis do Grafo, Nós, Arestas e Metadados Temporais.

### `ArestaGrafo`

*DTO imutável* — Representação imutável de uma aresta direcionada e tipada.

**Campos:** `id: str`, `origem_id: str`, `destino_id: str`, `tipo: TipoAresta`, `metadados: MetadadosTemporais`

### `GrafoEstado`

*DTO imutável* — Estado integral imutável da projeção do grafo em memória.

**Campos:** `nos: Mapping[str, NoGrafo]`, `arestas: Mapping[str, ArestaGrafo]`, `versao_log: int`

- `contem_no(id_no: str) -> bool` — Verifica existência de um nó por ID.
- `contem_aresta(id_aresta: str) -> bool` — Verifica existência de uma aresta por ID.
- `serializar_para_json() -> str` — Serialização determinística ordenada por chaves para asserção de paridade.

### `MetadadosTemporais`

*DTO imutável* — Estrutura bitemporal de rastreabilidade de validade e log.

**Campos:** `criado_em: str`, `registrado_em: str`, `valido_de: str | None`, `valido_ate: str | None`, `atualizado_em: str | None`

- `com_atualizacao(momento: str) -> 'MetadadosTemporais'` — Registra quando o nó foi alterado, sem mexer em quando ele nasceu.
- `agora(valido_de: str | None) -> 'MetadadosTemporais'` — Cria metadados temporais com timestamp UTC atual.

### `NoGrafo`

*DTO imutável* — Representação imutável de um nó do grafo de conhecimento.

**Campos:** `id: str`, `tipo: TipoNo`, `rotulo: str`, `propriedades: Mapping[str, Any]`, `metadados: MetadadosTemporais`, `proveniencia: ProvenienciaNo`, `ordem: OrdemNoLog`

- `obter_propriedade(chave: str, padrao: Any) -> Any` — Obtém o valor de uma propriedade com valor de fallback.
- `com_propriedades(novas_propriedades: Mapping[str, Any]) -> 'NoGrafo'` — Retorna uma nova instância com propriedades mescladas de forma imutável.
- `tocado_em(momento: str, seq: int) -> 'NoGrafo'` — Nova instância marcando quando e em que ponto do log o nó foi alterado.

### `OrdemNoLog`

*DTO imutável* — Onde o nó nasceu e onde foi tocado por último na ordem total do log.

**Campos:** `seq_criacao: int`, `seq_atualizacao: int`

- `foi_alterado() -> bool` `[property]` — Indica que o nó recebeu ao menos uma escrita depois da que o criou.
- `com_atualizacao(seq: int) -> 'OrdemNoLog'` — Marca a posição do último toque, preservando a de nascimento.

### `ProvenienciaNo`

*DTO imutável* — Quem escreveu o nó, sob qual papel e por qual origem.

**Campos:** `autor: str`, `papel: str`, `origem: str`, `atualizado_por: str`

- `eh_de_agente() -> bool` `[property]` — Indica conteúdo que não passou pela mão do humano ao ser criado.
- `descrever() -> str` — Assinatura curta para a linha da vista materializada.
- `com_atualizacao(autor: str) -> 'ProvenienciaNo'` — Registra quem tocou o nó por último, preservando quem o criou.

## `core/ontologia.py`

Versão declarada do vocabulário da ontologia e a impressão digital que a checa.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VERSAO_ONTOLOGIA` | `str` | `'1.0.0'` |
| `VERSAO_ONTOLOGIA_DESCONHECIDA` | `str` | `'0'` |
| `TAMANHO_DA_ASSINATURA` | `int` | `12` |
| `ASSINATURA_DECLARADA` | `str` | `'df1c29b96eae'` |

### Funções do módulo

- `calcular_assinatura_da_ontologia() -> str` — Impressão digital do vocabulário: muda quando um termo entra, sai ou muda.

## `core/types.py`

Definições de enumerações e tipos de valor base para a ontologia do Graphow.

### `NivelAutonomiaProjeto` (str, Enum)

*serviço* — Níveis de permissividade e autonomia concedidos a agentes no escopo do projeto.

### `OrigemEvento` (str, Enum)

*serviço* — Origem do disparo de mutações no log.

### `PapelAutor` (str, Enum)

*serviço* — Papéis de autoria com contratos específicos de permissão de escrita.

### `StatusExecucao` (str, Enum)

*serviço* — Estados do ciclo de vida de execução de um agente (Run).

### `StatusQuestion` (str, Enum)

*serviço* — Estados de resolução de uma dúvida/questão.

### `StatusTask` (str, Enum)

*serviço* — Estados do ciclo de vida de um nó Task.

### `TipoAresta` (str, Enum)

*serviço* — Tipos de arestas tipadas da ontologia.

### `TipoNo` (str, Enum)

*serviço* — Tipos de nós suportados pela ontologia de duas camadas.

