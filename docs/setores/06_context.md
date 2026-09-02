# Setor 06 — Divulgação Progressiva

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.context`

Recorta o subgrafo relevante ao alvo por papel e o renderiza sob orçamento estrito de tokens, descartando seções por prioridade.

## Inventário

11 módulos · 1124 linhas · 24 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`context/corte.py`](#contextcorte) | 57 | Escada de degradação da vista sob pressão de orçamento, em uma tabela só. |
| [`context/exploracao.py`](#contextexploracao) | 111 | Exploração limitada do subgrafo a partir de um nó alvo. |
| [`context/materializer.py`](#contextmaterializer) | 110 | Motor de materialização de vistas de contexto com orçamento de tokens. |
| [`context/politicas.py`](#contextpoliticas) | 229 | Políticas de extração de subgrafo por papel (Behavior-Guided Progressive Disclosure). |
| [`context/renderizacao.py`](#contextrenderizacao) | 127 | Renderização em Markdown de um recorte de contexto sob orçamento de tokens. |
| [`context/secoes.py`](#contextsecoes) | 191 | Seções que compõem uma vista de contexto e sua ordem de descarte. |
| [`context/substituicao.py`](#contextsubstituicao) | 52 | Marcação de proveniência e de decisões substituídas nas linhas da vista. |
| [`context/token_counter.py`](#contexttokencounter) | 40 | Fachada de contagem de tokens sobre o estimador calibrado corrente. |
| [`context/tokenizacao.py`](#contexttokenizacao) | 110 | Estimadores de tokens atrás de uma interface, calibrados por classe de caractere. |
| [`context/vizinhanca.py`](#contextvizinhanca) | 76 | Montagem da seção de vizinhos: ordem por relevância e corte por tipo. |

## `context/corte.py`

Escada de degradação da vista sob pressão de orçamento, em uma tabela só.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITES_DE_VIZINHOS_POR_TIPO` | `tuple[int, ...]` | `(8, 4, 2, 1)` |
| `_APOIO` | `frozenset[PrioridadeRetencao]` | `frozenset({PrioridadeRetencao.APOIO})` |
| `_MAIS_DECISOES` | `frozenset[PrioridadeRetencao]` | `_APOIO | {PrioridadeRetencao.DECISOES}` |
| `_MAIS_BLOQUEIOS` | `frozenset[PrioridadeRetencao]` | `_MAIS_DECISOES | {PrioridadeRetencao.BLOQUEIOS}` |
| `_MAIS_NAVEGACAO` | `frozenset[PrioridadeRetencao]` | `_MAIS_BLOQUEIOS | {PrioridadeRetencao.NAVEGACAO}` |
| `_TUDO_MENOS_O_ALVO` | `frozenset[PrioridadeRetencao]` | `_MAIS_NAVEGACAO | {PrioridadeRetencao.RESTRICOES}` |

### `PlanoDeCorte`

*DTO imutável* — Um degrau da escada: o que se abre mão e quanto a vizinhança encolhe.

**Campos:** `prioridades_descartadas: frozenset[PrioridadeRetencao]`, `limite_de_vizinhos: int | None`

- `houve_corte() -> bool` `[property]` — Indica se algo foi omitido, para o aviso de truncagem no texto.

### Funções do módulo

- `montar_escada_de_corte() -> tuple[PlanoDeCorte, ...]` — Consulta pura: os degraus, do texto mais completo ao mais enxuto.

## `context/exploracao.py`

Exploração limitada do subgrafo a partir de um nó alvo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SALTOS_MAXIMOS_PADRAO` | `int` | `3` |

### `DirecaoTravessia` (str, Enum)

*serviço* — Sentido em que uma aresta é percorrida durante a exploração.

### `ExploradorSubgrafo`

*serviço* — Percorre o grafo em largura, restrito a tipos de aresta e a um raio de saltos.

- `coletar_alcancaveis(pedido: PedidoExploracao) -> tuple[NoGrafo, ...]` — Consulta pura: nós alcançáveis a partir do alvo, sem incluir o próprio alvo.
- `coletar_origens_diretas(id_alvo: str, tipo_aresta: TipoAresta) -> tuple[NoGrafo, ...]` — Nós que apontam diretamente para o alvo por um tipo específico de aresta.

### `PedidoExploracao`

*DTO imutável* — Parâmetros imutáveis de uma travessia a partir do nó alvo.

**Campos:** `id_alvo: str`, `tipos_de_aresta: frozenset[TipoAresta]`, `direcao: DirecaoTravessia`, `saltos_maximos: int`

## `context/materializer.py`

Motor de materialização de vistas de contexto com orçamento de tokens.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_TOKENS_PADRAO` | `int` | `1500` |
| `TITULO_SECAO_VIZINHOS` | `str` | `'Vizinhos a 1 Salto'` |

### `MaterializadorContexto`

*serviço* — Responsável por sintetizar subgrafos em formato ótimo de tokens para agentes.

**Campos:** `POLITICAS_POR_PAPEL: dict[PapelAutor, PoliticaContexto]`

- `materializar(requisicao: RequisicaoVista, view: GrafoView) -> VistaMaterializada` — Gera a vista mais completa que couber no orçamento de tokens do pedido.
- `expandir_no(id_no: str, view: GrafoView) -> dict[str, Any]` — Expansão detalhada sob demanda de um nó específico.

### `RequisicaoVista`

*DTO imutável* — DTO imutável para solicitação de materialização de contexto.

**Campos:** `id_alvo: str`, `papel: PapelAutor`, `orcamento_tokens: int`

### `VistaMaterializada`

*DTO imutável* — Recorte de contexto imutável materializado com orçamento estrito de tokens.

**Campos:** `id_alvo: str`, `papel: PapelAutor`, `conteudo_formatado: str`, `tokens_estimados: int`, `orcamento_tokens: int`, `nos_incluidos: tuple[str, ...]`, `vizinhos_expansiveis: tuple[str, ...]`

## `context/politicas.py`

Políticas de extração de subgrafo por papel (Behavior-Guided Progressive Disclosure).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_HIERARQUIA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DECOMPOE, TipoAresta.PRODUZ})` |
| `ARESTAS_DE_PROVENIENCIA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DERIVA_DE, TipoAresta.SUBSTITUI, TipoAresta.JUSTI…` |

### `PoliticaBase` (PoliticaContexto)

*contrato* — Peças comuns a todas as políticas: restrições, bloqueios e vizinhança.

- `extrair_recorte(id_alvo: str, view: GrafoView) -> RecorteContexto` — Monta o recorte combinando as seções universais com as do papel.

### `PoliticaContexto` (ABC)

*contrato* — Contrato abstrato para políticas de seleção de contexto.

- `extrair_recorte(id_alvo: str, view: GrafoView) -> RecorteContexto` `[abstract]` — Monta o recorte de contexto centrado no nó alvo.

### `PoliticaExecutor` (PoliticaBase)

*serviço* — Executor: a tarefa em mãos, as decisões que a governam e as evidências delas.

### `PoliticaPlanejador` (PoliticaBase)

*serviço* — Planejador: a decomposição do alvo e as dúvidas abertas dentro dela.

### `PoliticaRevisor` (PoliticaBase)

*serviço* — Revisor: os artefatos derivados do alvo e as evidências que os sustentam.

## `context/renderizacao.py`

Renderização em Markdown de um recorte de contexto sob orçamento de tokens.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AVISO_DE_TRUNCAGEM` | `str` | `'[AVISO: secoes secundarias omitidas por limite de tokens]'` |

### `CandidatoRenderizado`

*DTO imutável* — Texto já montado e medido, aguardando aprovação pelo orçamento.

**Campos:** `conteudo: str`, `tokens_estimados: int`, `secoes: tuple[SecaoContexto, ...]`

### `RenderizadorContexto`

*serviço* — Converte um recorte em Markdown, descendo a escada de corte até caber.

- `renderizar(recorte: RecorteContexto, orcamento_tokens: int) -> TextoRenderizado` — Monta o texto mais completo que couber no orçamento informado.

### `TextoRenderizado`

*DTO imutável* — Resultado imutável da renderização, já enquadrado no orçamento.

**Campos:** `conteudo: str`, `tokens_estimados: int`, `secoes_incluidas: tuple[str, ...]`, `ids_incluidos: tuple[str, ...]`, `ids_por_secao: Mapping[str, tuple[str, ...]]`

## `context/secoes.py`

Seções que compõem uma vista de contexto e sua ordem de descarte.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PROPRIEDADES_APENAS_VISUAIS` | `frozenset[str]` | `frozenset({'pos_x', 'pos_y', 'x', 'y'})` |
| `MARCA_DE_CONTEUDO_NAO_CONFIAVEL` | `str` | `'[nao confiavel: conteudo trazido por agente]'` |
| `TIPOS_DE_CONTEUDO_EXTERNO` | `frozenset[TipoNo]` | `frozenset({TipoNo.EVIDENCE, TipoNo.ARTIFACT})` |

### `GrupoDeLinhas`

*DTO imutável* — Subconjunto homogêneo de uma seção, cortável de forma independente.

**Campos:** `rotulo: str`, `linhas: tuple[str, ...]`, `ids: tuple[str, ...]`

- `primeiras(limite: int) -> tuple[tuple[str, ...], tuple[str, ...]]` — Devolve as linhas mantidas e os identificadores correspondentes.
- `linha_de_excedente(limite: int) -> tuple[str, ...]` — Anuncia quantos itens do grupo ficaram de fora, se algum ficou.

### `PrioridadeRetencao` (IntEnum)

*serviço* — Quanto menor o valor, mais tarde a seção é descartada sob pressão de orçamento.

### `RecorteContexto`

*DTO imutável* — Resultado imutável de uma política: o alvo e as seções que o cercam.

**Campos:** `alvo: NoGrafo`, `secoes: tuple[SecaoContexto, ...]`

- `secoes_por_exibicao() -> tuple[SecaoContexto, ...]` — Seções não vazias na ordem em que devem aparecer no texto.
- `ids_incluidos() -> tuple[str, ...]` — Identificadores citados no recorte, sem repetição e com o alvo à frente.

### `SecaoContexto`

*DTO imutável* — Bloco nomeado da vista materializada, com suas duas ordens.

**Campos:** `titulo: str`, `linhas: tuple[str, ...]`, `ordem_exibicao: int`, `prioridade_retencao: PrioridadeRetencao`, `ids_incluidos: tuple[str, ...]`, `grupos: tuple[GrupoDeLinhas, ...]`

- `esta_vazia() -> bool` `[property]` — Uma seção sem linhas não deve ser renderizada.
- `pode_encolher() -> bool` `[property]` — Só encolhe por dentro a seção que declara grupos cortáveis.
- `reduzida(limite_por_grupo: int) -> 'SecaoContexto'` — Nova seção com no máximo N itens por grupo e o resto anunciado.
- `renderizar() -> tuple[str, ...]` — Emite o cabeçalho uma única vez, seguido das linhas do bloco.

### Funções do módulo

- `filtrar_propriedades_de_dominio(propriedades: Mapping[str, Any]) -> dict[str, Any]` — Descarta as propriedades que só interessam ao layout do canvas.
- `formatar_propriedades(propriedades: Mapping[str, Any]) -> str` — Serializa as propriedades de domínio em JSON determinístico.
- `anotar_proveniencia(no: NoGrafo) -> str` — Sufixo com autor e papel, mais o aviso de conteúdo não confiável se couber.
- `formatar_no_em_linha(no: NoGrafo) -> str` — Descreve um nó em uma linha compacta de lista, com a sua autoria.
- `formatar_no_com_propriedades(no: NoGrafo) -> str` — Descreve um nó incluindo as propriedades de domínio e a sua autoria.
- `montar_secao_de_nos(titulo: str, nos: Sequence[NoGrafo], ordens: tuple[int, PrioridadeRetencao]) -> SecaoContexto` — Constrói uma seção de lista simples a partir de um conjunto de nós.

## `context/substituicao.py`

Marcação de proveniência e de decisões substituídas nas linhas da vista.

### Funções do módulo

- `identificar_substituta(id_decisao: str, view: GrafoView) -> str | None` — Devolve a Decision vigente que substituiu a informada, se houver alguma.
- `formatar_decisao(no: NoGrafo, view: GrafoView) -> str` — Descreve a decisão marcando explicitamente quando ela já não vale.
- `montar_secao_de_decisoes(decisoes: Sequence[NoGrafo], view: GrafoView, ordens: tuple[int, PrioridadeRetencao]) -> SecaoContexto` — Seção de decisões com as vigentes à frente e as substituídas sinalizadas.

## `context/token_counter.py`

Fachada de contagem de tokens sobre o estimador calibrado corrente.

### `ContadorTokens`

*serviço* — Contador determinístico de tokens delegado ao estimador configurado.

**Campos:** `ESTIMADOR: EstimadorTokens`

- `estimar_texto(texto: str) -> int` — Estima o número de tokens de uma string.
- `estimar_objeto(obj: Any) -> int` — Serializa o objeto em JSON determinístico e calcula a contagem estimada.
- `cabe_no_orcamento(texto: str, orcamento: int) -> bool` — Verifica se o texto cabe dentro do limite de tokens especificado.
- `calibracao_em_uso() -> str` — Nome da calibração corrente, para constar de recibos e medições.

## `context/tokenizacao.py`

Estimadores de tokens atrás de uma interface, calibrados por classe de caractere.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PRIMEIRO_PONTO_ASTRAL` | `int` | `65536` |
| `ULTIMO_PONTO_ASCII` | `int` | `127` |
| `ULTIMO_PONTO_LATINO_ESTENDIDO` | `int` | `591` |
| `CUSTO_POR_CLASSE` | `dict[ClasseDeCaractere, float]` | `{ClasseDeCaractere.ASCII: 0.25, ClasseDeCaractere.LATINO_ACENTUADO: 0.5…` |
| `ESTIMADOR_PADRAO` | `EstimadorTokens` | `EstimadorPorClasseDeCaractere()` |

### `ClasseDeCaractere` (str, Enum)

*serviço* — Faixas de custo distinto nos tokenizadores BPE de vocabulário grande.

### `EstimadorPorClasseDeCaractere` (EstimadorTokens)

*DTO imutável* — Estimador padrão: soma o custo de cada caractere segundo a sua faixa.

**Campos:** `nome: str`

- `estimar_texto(texto: str) -> int` — Arredonda para cima a soma dos custos, nunca reportando menos que um.
- `descrever() -> str` — Nome da calibração corrente.

### `EstimadorPorNormalizacao` (EstimadorTokens)

*DTO imutável* — Variante que decompõe acentos antes de medir, para textos já normalizados.

**Campos:** `nome: str`

- `estimar_texto(texto: str) -> int` — Mede o texto após decomposição canônica.
- `descrever() -> str` — Nome da calibração corrente.

### `EstimadorTokens` (ABC)

*contrato* — Contrato de estimativa de tokens usado por todo o materializador.

- `estimar_texto(texto: str) -> int` `[abstract]` — Devolve o número estimado de tokens do texto informado.
- `descrever() -> str` `[abstract]` — Identifica a calibração em uso, para registro em métricas e recibos.

### Funções do módulo

- `classificar(caractere: str) -> ClasseDeCaractere` — Consulta pura que enquadra o caractere na faixa de custo correspondente.

## `context/vizinhanca.py`

Montagem da seção de vizinhos: ordem por relevância e corte por tipo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_VIZINHOS` | `str` | `'Vizinhos a 1 Salto (use expandir_no para aprofundar)'` |
| `ORDEM_DE_EXIBICAO_DOS_VIZINHOS` | `int` | `9` |
| `RELEVANCIA_POR_STATUS` | `Mapping[str, int]` | `{StatusTask.BLOQUEADO.value: 0, StatusQuestion.ABERTA.value: 0, StatusT…` |
| `RELEVANCIA_DE_NO_SEM_STATUS` | `int` | `4` |

### Funções do módulo

- `ordenar_por_relevancia(nos: Sequence[NoGrafo]) -> tuple[NoGrafo, ...]` — Ordena vizinhos por urgência do status e, em empate, por identificador.
- `formatar_vizinho(no: NoGrafo) -> str` — Descreve o vizinho em uma linha, com o status quando ele existir.
- `montar_secao_de_vizinhos(nos: Sequence[NoGrafo]) -> SecaoContexto` — Monta a seção agrupada por tipo, pronta para encolher sob orçamento.

