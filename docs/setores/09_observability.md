# Setor 09 — Observabilidade e Taxonomia MAST

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.observability`

Traduz o modo de falha que o portão declarou em categoria MAST e recebe os spans GenAI do kernel, em memória ou em arquivo NDJSON.

## Inventário

4 módulos · 262 linhas · 8 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`observability/exportador_spans.py`](#observabilityexportadorspans) | 40 | Exportador de spans para arquivo NDJSON, uma linha por span. |
| [`observability/mast_evaluator.py`](#observabilitymastevaluator) | 74 | Avaliador de falhas na taxonomia MAST (Cemri et al., 2025). |
| [`observability/tracer.py`](#observabilitytracer) | 117 | Spans GenAI do Graphow: coleta em memória e forma serializável. |

## `observability/exportador_spans.py`

Exportador de spans para arquivo NDJSON, uma linha por span.

### `TracerArquivoNDJSON` (Tracer)

*serviço* — Escreve cada span como uma linha JSON no arquivo indicado.

- `caminho() -> Path` `[property]` — Arquivo em que os spans estão sendo acumulados.
- `registrar_span(dados: DadosSpanDTO) -> SpanGenAI` — Materializa o span e o acrescenta ao arquivo, sem reter nada em memória.

## `observability/mast_evaluator.py`

Avaliador de falhas na taxonomia MAST (Cemri et al., 2025).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PISTAS_TEXTUAIS` | `tuple[tuple[str, ModoFalhaMAST], ...]` | `(('papel', ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL), ('permissão', ModoF…` |
| `PORTAO_DESCONHECIDO` | `str` | `'Desconhecido'` |

### `DiagnosticoFalha`

*DTO imutável* — Diagnóstico estruturado para análise de qualidade e auto-recuperação.

**Campos:** `categoria: CategoriaFalhaMAST`, `modo: ModoFalhaMAST`, `mensagem: str`, `portao: str`, `detalhes: Mapping[str, str]`

### `MASTEvaluator`

*serviço* — Traduz a recusa de um portão em diagnóstico da taxonomia MAST.

- `classificar_resultado(resultado: ResultadoValidacao) -> DiagnosticoFalha | None` — Mapeia o resultado de validação de um patch para a taxonomia MAST.

## `observability/tracer.py`

Spans GenAI do Graphow: coleta em memória e forma serializável.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_SPANS_RETIDOS` | `int` | `512` |

### `DadosSpanDTO`

*DTO imutável* — DTO imutável para criação de novos spans de telemetria OTel.

**Campos:** `nome_operacao: str`, `atributos: Mapping[str, Any]`, `sucesso: bool`, `parent_span_id: str | None`, `trace_id: str | None`

### `SpanGenAI`

*DTO imutável* — Span imutável de telemetria aderente às convenções GenAI OpenTelemetry.

**Campos:** `trace_id: str`, `span_id: str`, `nome_operacao: str`, `parent_span_id: str | None`, `inicio_utc: str`, `fim_utc: str`, `atributos: Mapping[str, Any]`, `sucesso: bool`, `mensagem_erro: str | None`

### `Tracer` (ABC)

*contrato* — Destino dos spans emitidos pelo kernel.

- `registrar_span(dados: DadosSpanDTO) -> SpanGenAI | None` `[abstract]` — Recebe o span descrito e o encaminha ao destino concreto.

### `TracerNulo` (Tracer)

*serviço* — Destino padrão: não materializa span algum, para não custar nada.

- `registrar_span(dados: DadosSpanDTO) -> SpanGenAI | None` — Descarta a descrição sem alocar o span.

### `TracerOTel` (Tracer)

*serviço* — Coletor em memória dos spans de execução de agentes e ferramentas.

- `registrar_span(dados: DadosSpanDTO) -> SpanGenAI` — Cria e armazena um novo span OTel a partir do DTO.
- `obter_spans_por_trace(trace_id: str) -> list[SpanGenAI]` — Recupera todos os spans associados a um determinado trace_id.
- `listar_todos_spans() -> list[SpanGenAI]` — Retorna cópia de todos os spans retidos, do mais antigo ao mais novo.

### Funções do módulo

- `criar_span(dados: DadosSpanDTO) -> SpanGenAI` — Materializa o span com identificadores e marca temporal próprios.
- `serializar_span(span: SpanGenAI) -> dict[str, Any]` — Forma serializável do span, com os nomes de campo do modelo OTLP.

