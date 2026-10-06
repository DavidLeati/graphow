# Setor 01 — Núcleo Ontológico

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.core`

Vocabulário da ontologia (versão 1.4.0: o tipo Governanca, o papel arbitro e a Evidence localizada por fonte genérica), modelos imutáveis do grafo, eventos do log, os modos de falha da taxonomia MAST, a hierarquia de exceções de domínio e a política de governança pura (gestos, presets, herança global para projeto e composição pela mais restritiva). Não depende de nenhum outro setor.

## Inventário

9 módulos · 1154 linhas · 37 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`core/events.py`](#coreevents) | 93 | Definições de eventos de log transacionais append-only do Graphow. |
| [`core/exceptions.py`](#coreexceptions) | 65 | Hierarquia de exceções de domínio cirúrgicas do Graphow. |
| [`core/falhas.py`](#corefalhas) | 76 | Vocabulário de modos de falha, na taxonomia MAST (Cemri et al., 2025). |
| [`core/governanca.py`](#coregovernanca) | 389 | Política de governança: quem pode fazer cada gesto que antes era só do humano. |
| [`core/models.py`](#coremodels) | 196 | Modelos imutáveis do Grafo, Nós, Arestas e Metadados Temporais. |
| [`core/ontologia.py`](#coreontologia) | 71 | Versão declarada do vocabulário da ontologia e a impressão digital que a checa. |
| [`core/orquestracao.py`](#coreorquestracao) | 88 | Propriedades que a orquestração grava na Task, no Goal, na Evidence de revisão e na Decision de aceite. |
| [`core/types.py`](#coretypes) | 120 | Definições de enumerações e tipos de valor base para a ontologia do Graphow. |

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

## `core/governanca.py`

Política de governança: quem pode fazer cada gesto que antes era só do humano.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_GOVERNANCA_GLOBAL` | `str` | `'governanca-global'` |
| `PROPRIEDADE_GOVERNANCA_DO_PROJETO` | `str` | `'governanca'` |
| `PROPRIEDADE_NIVEL_AUTONOMIA` | `str` | `'nivel_autonomia'` |
| `CHAVE_PRESET` | `str` | `'preset'` |
| `CHAVE_PERSONALIZADA` | `str` | `'personalizada'` |
| `CHAVES_DA_CONFIGURACAO` | `frozenset[str]` | `frozenset({CHAVE_PRESET, CHAVE_PERSONALIZADA})` |
| `VALOR_HUMANO` | `str` | `'humano'` |
| `VALOR_ARBITRO` | `str` | `'arbitro'` |
| `VALOR_EXECUTOR` | `str` | `'executor'` |
| `VALOR_ESTRITO` | `str` | `'estrito'` |
| `VALOR_ILIMITADO` | `str` | `'ilimitado'` |
| `MAX_CORRECOES_MINIMO` | `int` | `0` |
| `MAX_CORRECOES_MAXIMO` | `int` | `5` |
| `ORIGEM_GLOBAL` | `str` | `'global'` |
| `ORIGEM_PROJETO` | `str` | `'projeto'` |
| `ORIGEM_LEGADO` | `str` | `'legado:nivel_autonomia'` |
| `PREFIXO_ORIGEM_PRESET` | `str` | `'preset:'` |
| `PREFIXO_ORIGEM_PROJETO_RESTRITIVO` | `str` | `'projeto:'` |
| `GESTOS_COM_LEITURA_PROPRIA` | `frozenset[Gesto]` | `frozenset({Gesto.ESTRUTURA, Gesto.MAX_CORRECOES, Gesto.ACAO_EXTERNA})` |
| `GESTOS_POR_PAPEL` | `frozenset[Gesto]` | `frozenset((gesto for gesto in Gesto if gesto not in GESTOS_COM_LEITURA_…` |
| `_VALORES_DE_PAPEL` | `frozenset[str]` | `frozenset({VALOR_HUMANO, VALOR_ARBITRO})` |
| `VALORES_ACEITOS` | `Mapping[Gesto, frozenset[str]]` | `MappingProxyType({**{gesto: _VALORES_DE_PAPEL for gesto in GESTOS_POR_P…` |
| `_GOVERNANCA_MAXIMA` | `Mapping[Gesto, ValorDeGesto]` | `MappingProxyType({**{gesto: VALOR_HUMANO for gesto in GESTOS_POR_PAPEL}…` |
| `_ARBITRAGEM_MAXIMA` | `Mapping[Gesto, ValorDeGesto]` | `MappingProxyType({**{gesto: VALOR_ARBITRO for gesto in GESTOS_POR_PAPEL…` |
| `PRESETS_FIXOS` | `Mapping[PresetGovernanca, Mapping[Gesto, ValorDeGesto]]` | `MappingProxyType({PresetGovernanca.GOVERNANCA_MAXIMA: _GOVERNANCA_MAXIM…` |

### `Gesto` (str, Enum)

*serviço* — Gestos governáveis: cada um mapeia um portão que a política pode abrir ao árbitro.

### `PoliticaGovernanca`

*DTO imutável* — Política efetiva: o valor de cada gesto e de onde esse valor veio.

**Campos:** `valores: Mapping[Gesto, ValorDeGesto]`, `origens: Mapping[Gesto, str]`

- `valor(gesto: Gesto) -> ValorDeGesto` — Valor efetivo do gesto: 'humano', 'arbitro', 'estrito', 'ilimitado' ou o inteiro.
- `origem(gesto: Gesto) -> str` — De onde o valor veio: global, projeto, preset:<nome> ou legado:nivel_autonomia.
- `permite(gesto: Gesto, papel: PapelAutor) -> bool` — Diz se o papel pode fazer o gesto: o humano sempre, o árbitro quando a política o entrega.
- `estrutura_ilimitada() -> bool` `[property]` — Verdadeiro quando todos os agentes ganham os tipos de nó e a camada `contem`.
- `acao_externa_com_executor() -> bool` `[property]` — Verdadeiro quando o executor assume e entrega a Task de ação externa; senão ela é do humano.
- `max_correcoes() -> int` `[property]` — Reprovações em cadeia antes do teto: a de ordem `max_correcoes` já escala (profundidade_correcao + 1 >= max_correcoes).

### `PresetDoProjeto` (str, Enum)

*serviço* — Presets do nível do Projeto: os do global mais `herdar`, que é o padrão.

### `PresetGovernanca` (str, Enum)

*serviço* — Presets do nível global: dois fixos e a personalizada, a única editável.

### Funções do módulo

- `politica_do_preset(preset: PresetGovernanca) -> PoliticaGovernanca` — Política cujos gestos todos vêm de um preset fixo.
- `politica_padrao() -> PoliticaGovernanca` — O que vale sem nó global: governança máxima.
- `compor_politica_global(propriedades: Mapping[str, Any] | None) -> PoliticaGovernanca` — Política efetiva global a partir das propriedades do nó `governanca-global`.
- `compor_politica_do_projeto(governanca: Any, nivel_autonomia: Any, politica_global: PoliticaGovernanca) -> PoliticaGovernanca` — Política efetiva do Projeto a partir da propriedade `governanca` e da global.
- `compor_mais_restritiva(politicas_por_projeto: Mapping[str, PoliticaGovernanca]) -> PoliticaGovernanca` — Política que vale para um nó contido por mais de um Projeto: em cada gesto, a mais restritiva.
- `validar_personalizada(personalizada: Any) -> list[str]` — Problemas de uma `personalizada`: gesto desconhecido ou valor fora do domínio.
- `validar_configuracao_global(configuracao: Any) -> list[str]` — Problemas das propriedades do nó Governanca (`preset` e `personalizada`).
- `validar_configuracao_do_projeto(configuracao: Any) -> list[str]` — Problemas da propriedade `governanca` de um Projeto.

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

*DTO imutável* — Tempo de transação do nó: quando o log o registrou e quando o tocou por último.

**Campos:** `criado_em: str`, `atualizado_em: str | None`

- `com_atualizacao(momento: str) -> 'MetadadosTemporais'` — Registra quando o nó foi alterado, sem mexer em quando ele nasceu.
- `agora() -> 'MetadadosTemporais'` — Cria metadados temporais com timestamp UTC atual.

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
| `VERSAO_ONTOLOGIA` | `str` | `'1.4.0'` |
| `ARESTAS_DE_CONTENCAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.CONTEM, TipoAresta.PRODUZ, TipoAresta.DECOMPOE})` |
| `VERSAO_ONTOLOGIA_DESCONHECIDA` | `str` | `'0'` |
| `TAMANHO_DA_ASSINATURA` | `int` | `12` |
| `ASSINATURA_DECLARADA` | `str` | `'0d0a5e75ff80'` |

### Funções do módulo

- `calcular_assinatura_da_ontologia() -> str` — Impressão digital do vocabulário: muda quando um termo entra, sai ou muda.

## `core/orquestracao.py`

Propriedades que a orquestração grava na Task, no Goal, na Evidence de revisão e na Decision de aceite.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_MODELO` | `str` | `'modelo'` |
| `CAMPO_MOTIVO_DO_MODELO` | `str` | `'motivo_modelo'` |
| `CAMPO_ARQUIVOS_ALVO` | `str` | `'arquivos_alvo'` |
| `CAMPO_CORRIGE` | `str` | `'corrige'` |
| `CAMPO_CRITERIO_PRONTO` | `str` | `'criterio_pronto'` |
| `CAMPO_TRILHA` | `str` | `'trilha'` |
| `TRILHA_LEVE` | `str` | `'leve'` |
| `TRILHA_COMPLETA` | `str` | `'completa'` |
| `TRILHAS` | `frozenset[str]` | `frozenset({TRILHA_LEVE, TRILHA_COMPLETA})` |
| `CAMPO_ENTREGA` | `str` | `'entrega'` |
| `ENTREGA_ARTEFATO` | `str` | `'artefato'` |
| `ENTREGA_ACAO_EXTERNA` | `str` | `'acao_externa'` |
| `ENTREGAS` | `frozenset[str]` | `frozenset({ENTREGA_ARTEFATO, ENTREGA_ACAO_EXTERNA})` |
| `CAMPO_CONFIGURACAO` | `str` | `'configuracao'` |
| `CAMPO_RAMO_BASE` | `str` | `'ramo_base'` |
| `CAMPO_CAMINHOS_DE_COLISAO` | `str` | `'caminhos_de_colisao'` |
| `CAMPO_ARQUIVOS` | `str` | `'arquivos'` |
| `CAMPO_VEREDITO` | `str` | `'veredito'` |
| `VEREDITO_APROVADO` | `str` | `'aprovado'` |
| `VEREDITO_REJEITADO` | `str` | `'rejeitado'` |
| `CAMPO_TRIAGEM` | `str` | `'triagem'` |
| `TRIAGEM_FORA_DA_TRILHA` | `str` | `'fora_da_trilha'` |
| `CAMPO_ACAO` | `str` | `'acao'` |
| `ACAO_ACEITE_APOS_REPROVACAO` | `str` | `'aceite_apos_reprovacao'` |
| `ACAO_DE_CONDENSAR` | `str` | `'condensar_sessao'` |
| `ACAO_DE_CONSOLIDAR` | `str` | `'consolidar_aprendizados'` |
| `ACOES_ABERTAS_PELO_GRAFO` | `frozenset[str]` | `frozenset({ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR})` |

### Funções do módulo

- `ler_textos(valor: object) -> tuple[str, ...]` — Lista de textos não vazios, sem repetição e na ordem dada; um texto solto vira lista de um.
- `ler_texto(propriedades: Mapping[str, Any], chave: str) -> str` — O valor textual da propriedade, sem espaços nas pontas; vazio quando ausente.

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

### `StatusSessao` (str, Enum)

*serviço* — Estados de uma Sessao: aberta ao trabalho ou encerrada.

### `StatusTask` (str, Enum)

*serviço* — Estados do ciclo de vida de um nó Task.

### `TipoAresta` (str, Enum)

*serviço* — Tipos de arestas tipadas da ontologia.

### `TipoNo` (str, Enum)

*serviço* — Tipos de nós suportados pela ontologia de duas camadas.

