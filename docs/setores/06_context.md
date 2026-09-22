# Setor 06 — Divulgação Progressiva

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.context`

Recorta o subgrafo relevante ao alvo por papel e o renderiza sob orçamento estrito de tokens, descartando seções por prioridade.

## Inventário

17 módulos · 2100 linhas · 30 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`context/aprendizados_aplicaveis.py`](#contextaprendizadosaplicaveis) | 201 | A seção Aprendizados Aplicaveis: os aprendizados que alcançam o alvo, por herança, por léxico ou por índice. |
| [`context/corte.py`](#contextcorte) | 64 | Escada de degradação da vista sob pressão de orçamento, em uma tabela só. |
| [`context/exploracao.py`](#contextexploracao) | 111 | Exploração limitada do subgrafo a partir de um nó alvo. |
| [`context/fechamento.py`](#contextfechamento) | 130 | Seção de fechamento: como uma sessão encerrada se apresenta a quem a retoma. |
| [`context/materializer.py`](#contextmaterializer) | 146 | Motor de materialização de vistas de contexto com orçamento de tokens. |
| [`context/memoria.py`](#contextmemoria) | 157 | O Aprendizado como o grafo o lê: alcance, origem, substituição e a linha que a vista carrega. |
| [`context/orientacao.py`](#contextorientacao) | 83 | As decisões que valem para um trabalho: as que o orientam e as que orientam quem o contém. |
| [`context/panorama.py`](#contextpanorama) | 138 | Seção de panorama: os filhos de um contêiner resumidos, em vez de listados. |
| [`context/politicas.py`](#contextpoliticas) | 333 | Políticas de extração de subgrafo por papel (Behavior-Guided Progressive Disclosure). |
| [`context/protocolo.py`](#contextprotocolo) | 86 | O protocolo da memória dito ao agente: o mesmo texto no hook de início e no aperto de mão do MCP. |
| [`context/renderizacao.py`](#contextrenderizacao) | 133 | Renderização em Markdown de um recorte de contexto sob orçamento de tokens. |
| [`context/secoes.py`](#contextsecoes) | 220 | Seções que compõem uma vista de contexto e sua ordem de descarte. |
| [`context/substituicao.py`](#contextsubstituicao) | 51 | Marcação de proveniência e de decisões substituídas nas linhas da vista. |
| [`context/token_counter.py`](#contexttokencounter) | 40 | Fachada de contagem de tokens sobre o estimador calibrado corrente. |
| [`context/tokenizacao.py`](#contexttokenizacao) | 110 | Estimadores de tokens atrás de uma interface, calibrados por classe de caractere. |
| [`context/vizinhanca.py`](#contextvizinhanca) | 76 | Montagem da seção de vizinhos: ordem por relevância e corte por tipo. |

## `context/aprendizados_aplicaveis.py`

A seção Aprendizados Aplicaveis: os aprendizados que alcançam o alvo, por herança, por léxico ou por índice.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_APRENDIZADOS` | `str` | `'Aprendizados Aplicaveis'` |
| `ORDEM_DE_EXIBICAO_DOS_APRENDIZADOS` | `int` | `2` |
| `CAMPO_DESCRICAO` | `str` | `'descricao'` |
| `PROFUNDIDADE_DA_HERANCA` | `int` | `8` |
| `LIMITE_DE_CASAMENTOS_LEXICAIS` | `int` | `5` |
| `MECANISMO_HERANCA` | `str` | `'heranca'` |
| `MECANISMO_LEXICO` | `str` | `'lexico'` |
| `MECANISMO_SEMANTICO` | `str` | `'semantico'` |

### `AprendizadoAplicavel`

*DTO imutável* — Um aprendizado que alcançou o alvo, com o mecanismo pelo qual chegou.

**Campos:** `no: NoGrafo`, `mecanismo: str`, `alcance: str`

### `IndiceSemantico` (ABC)

*contrato* — Recuperação por sentido, para quando herança e léxico não atravessam projetos.

- `sugerir(texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]` `[abstract]` — Identificadores dos candidatos aplicáveis ao texto, em ordem.
- `descrever() -> str` `[abstract]` — Nome do índice em uso, para o relatório de avaliação declarar.

### `IndiceSemanticoNulo` (IndiceSemantico)

*serviço* — O padrão: não sugere nada e não custa nada.

- `sugerir(texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]` — Nenhuma sugestão.
- `descrever() -> str` — Nome do índice nulo.

### `PedidoDeMemoria`

*DTO imutável* — O que a seção precisa: o alvo, a projeção, o índice e o instante de referência.

**Campos:** `alvo: NoGrafo`, `view: GrafoView`, `indice: IndiceSemantico`, `agora: str`

- `instante() -> str` `[property]` — Instante ISO contra o qual `valido_ate` é comparado; o relógio, se não vier.
- `texto_do_alvo() -> str` `[property]` — Título e descrição do alvo, que é o que o léxico e o índice comparam.

### Funções do módulo

- `montar_secao_de_aprendizados(pedido: PedidoDeMemoria) -> SecaoContexto` — Monta a seção nos três passos, agrupada por mecanismo para encolher sob orçamento.

## `context/corte.py`

Escada de degradação da vista sob pressão de orçamento, em uma tabela só.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITES_DE_VIZINHOS_POR_TIPO` | `tuple[int, ...]` | `(8, 4, 2, 1)` |
| `_CONTEXTO` | `frozenset[PrioridadeRetencao]` | `frozenset({PrioridadeRetencao.CONTEXTO})` |
| `_APOIO` | `frozenset[PrioridadeRetencao]` | `_CONTEXTO | {PrioridadeRetencao.APOIO}` |
| `_MAIS_DECISOES` | `frozenset[PrioridadeRetencao]` | `_APOIO | {PrioridadeRetencao.DECISOES}` |
| `_MAIS_BLOQUEIOS` | `frozenset[PrioridadeRetencao]` | `_MAIS_DECISOES | {PrioridadeRetencao.BLOQUEIOS}` |
| `_MAIS_NAVEGACAO` | `frozenset[PrioridadeRetencao]` | `_MAIS_BLOQUEIOS | {PrioridadeRetencao.NAVEGACAO, PrioridadeRetencao.MEM…` |
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

## `context/fechamento.py`

Seção de fechamento: como uma sessão encerrada se apresenta a quem a retoma.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_FECHAMENTO` | `str` | `'Fechamento da Sessao (encerrada: leia isto antes de descer)'` |
| `ORDEM_DE_EXIBICAO_DO_FECHAMENTO` | `int` | `0` |
| `ACAO_DE_CONDENSACAO` | `str` | `'condensacao_de_sessao'` |
| `CAMPO_ACAO` | `str` | `'acao'` |
| `CAMPO_ALVO` | `str` | `'id_alvo'` |
| `CAMPO_CORPO` | `str` | `'corpo'` |
| `CAMPO_RESUMO` | `str` | `'resumo'` |

### Funções do módulo

- `esta_encerrada(no: NoGrafo) -> bool` — Uma Sessão encerrada foi fechada pelo humano, pelo harness ou pela interface.
- `localizar_condensacao(id_sessao: str, view: GrafoView) -> NoGrafo | None` — A Note de condensação mais recente produzida pela sessão, se um agente a escreveu.
- `montar_secao_de_fechamento(sessao: NoGrafo, view: GrafoView) -> SecaoContexto` — Abre a vista da sessão encerrada com o que ela deixou em vigor.

## `context/materializer.py`

Motor de materialização de vistas de contexto com orçamento de tokens.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_TOKENS_PADRAO` | `int` | `1500` |
| `TITULO_SECAO_VIZINHOS` | `str` | `'Vizinhos a 1 Salto'` |

### `MaterializadorContexto`

*serviço* — Responsável por sintetizar subgrafos em formato ótimo de tokens para agentes.

**Campos:** `POLITICAS_POR_PAPEL: dict[PapelAutor, PoliticaContexto]`

- `indice_semantico() -> IndiceSemantico` `[property]` — O índice em uso, para o relatório de avaliação declarar com o que mediu.
- `materializar(requisicao: RequisicaoVista, view: GrafoView) -> VistaMaterializada` — Gera a vista mais completa que couber no orçamento de tokens do pedido.
- `expandir_no(id_no: str, view: GrafoView) -> dict[str, Any]` — Expansão detalhada sob demanda de um nó específico.

### `RequisicaoVista`

*DTO imutável* — DTO imutável para solicitação de materialização de contexto.

**Campos:** `id_alvo: str`, `papel: PapelAutor`, `orcamento_tokens: int`, `escopo_ativo: bool`, `raio_do_escopo: int`

### `VistaMaterializada`

*DTO imutável* — Recorte de contexto imutável materializado com orçamento estrito de tokens.

**Campos:** `id_alvo: str`, `papel: PapelAutor`, `conteudo_formatado: str`, `tokens_estimados: int`, `orcamento_tokens: int`, `nos_incluidos: tuple[str, ...]`, `vizinhos_expansiveis: tuple[str, ...]`

## `context/memoria.py`

O Aprendizado como o grafo o lê: alcance, origem, substituição e a linha que a vista carrega.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_ALCANCE` | `str` | `'alcance'` |
| `ALCANCE_GLOBAL` | `str` | `'global'` |
| `CAMPO_COMO_APLICAR` | `str` | `'como_aplicar'` |
| `CAMPO_VALIDO_ATE` | `str` | `'valido_ate'` |
| `MARCA_DE_SUBSTITUIDO` | `str` | `'SUBSTITUIDO'` |
| `MARCA_DE_CONTRADITO` | `str` | `'CONTRADITO'` |
| `MARCA_DE_SUBSTITUTO_PENDENTE` | `str` | `'SUBSTITUTO PENDENTE'` |

### Funções do módulo

- `aprendizados_promovidos(view: GrafoView, instante: str) -> tuple[NoGrafo, ...]` — Aprendizados com alcance declarado e ainda válidos, em ordem estável.
- `aprendizados_vigentes(view: GrafoView, instante: str) -> tuple[NoGrafo, ...]` — Os promovidos que nenhum promovido substituiu: o que a vista carrega.
- `alcances_de(no: NoGrafo, view: GrafoView) -> tuple[str, ...]` — Onde o aprendizado vale: a marca global e os destinos de `vale_para`.
- `ja_vale_para(id_aprendizado: str, id_alvo: str, view: GrafoView) -> bool` — Diz se o aprendizado já tem `vale_para` chegando no alvo.
- `origens_de(no: NoGrafo, view: GrafoView) -> tuple[str, ...]` — De onde o aprendizado saiu: os destinos das arestas `deriva_de`.
- `identificar_substituto(id_aprendizado: str, view: GrafoView) -> str | None` — O primeiro Aprendizado que substituiu o informado, promovido ou não, se houver.
- `substitutos_de(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]` — Os Aprendizados de onde parte `substitui` chegando neste, em ordem estável.
- `substituidos_por(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]` — Os Aprendizados que este substitui: a linha do consolidado diz quem ele absorveu.
- `substituto_promovido(id_aprendizado: str, view: GrafoView) -> str | None` — O substituto que já tem alcance, se houver: só ele tira o antigo da vista.
- `identificar_contradicoes(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]` — Evidences que contradizem o aprendizado: sinal de que ele precisa de revisão.
- `formatar_aprendizado(no: NoGrafo, view: GrafoView) -> str` — Uma linha: afirmação, proveniência, como aplicar, alcance, quem substitui, origem e marcas.

## `context/orientacao.py`

As decisões que valem para um trabalho: as que o orientam e as que orientam quem o contém.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_HERANCA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DECOMPOE})` |
| `TITULO_DO_CONTEXTO` | `str` | `'Perto Desta Tarefa, Sem Governa-la (mesma sessao ou so relacionado)'` |

### Funções do módulo

- `montar_secoes_de_decisoes(alvo: NoGrafo, proximos: Iterable[NoGrafo], view: GrafoView) -> tuple[SecaoContexto, SecaoContexto]` — As decisões que governam o alvo e, noutra seção, o que só está perto dele.
- `coletar_decisoes_que_orientam(alvo: NoGrafo, view: GrafoView) -> tuple[NoGrafo, ...]` — As Decision ligadas por `orienta` ao trabalho do alvo ou a um ancestral dele, sem repetição.

## `context/panorama.py`

Seção de panorama: os filhos de um contêiner resumidos, em vez de listados.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_PANORAMA` | `str` | `'Panorama dos Filhos (use ler_vista no que tiver trabalho aberto)'` |
| `ORDEM_DE_EXIBICAO_DO_PANORAMA` | `int` | `8` |
| `LIMITE_DE_FILHOS_NOMEADOS_POR_TIPO` | `int` | `5` |

### `FilhoResumido`

*serviço* — Par de nó e resumo, na ordem em que o panorama deve exibi-los.

- `tem_trabalho_aberto() -> bool` `[property]` — Trabalho aberto na subárvore ou, sendo folha, no próprio nó.
- `formatar() -> str` — Uma linha: identidade do filho e o agregado da subárvore dele.

### Funções do módulo

- `ordenar_por_urgencia(filhos: Sequence[FilhoResumido]) -> tuple[FilhoResumido, ...]` — Quem tem trabalho aberto vem primeiro; o resto segue por identificador.
- `montar_secao_de_panorama(filhos: Sequence[FilhoResumido]) -> SecaoContexto` — Monta o panorama agrupado por tipo, pronto para encolher sob orçamento.

## `context/politicas.py`

Políticas de extração de subgrafo por papel (Behavior-Guided Progressive Disclosure).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_HIERARQUIA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DECOMPOE, TipoAresta.PRODUZ})` |
| `ARESTAS_DE_PROVENIENCIA` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.DERIVA_DE, TipoAresta.SUBSTITUI, TipoAresta.JUSTI…` |
| `ARESTAS_DE_ORIENTACAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.ORIENTA})` |
| `ARESTAS_DO_TRABALHO` | `frozenset[TipoAresta]` | `ARESTAS_DE_PROVENIENCIA | ARESTAS_DE_ORIENTACAO | frozenset({TipoAresta…` |
| `ARESTAS_DA_SESSAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ})` |

### `AmbienteDoRecorte`

*DTO imutável* — O que toda seção precisa para se montar, agrupado para caber na assinatura.

**Campos:** `view: GrafoView`, `explorador: ExploradorSubgrafo`, `escopo: EscopoAtivo | None`, `indice_semantico: IndiceSemantico`

- `esta_no_escopo(id_no: str) -> bool` — Sem escopo declarado nada é filtrado; com escopo, vale o recorte ativo.

### `PoliticaBase` (PoliticaContexto)

*contrato* — Peças comuns a todas as políticas: restrições, bloqueios, memória e vizinhança.

- `extrair_recorte(id_alvo: str, view: GrafoView, escopo: EscopoAtivo | None) -> RecorteContexto` — Monta o recorte combinando as seções universais com as do papel.

### `PoliticaContexto` (ABC)

*contrato* — Contrato abstrato para políticas de seleção de contexto.

- `extrair_recorte(id_alvo: str, view: GrafoView, escopo: EscopoAtivo | None) -> RecorteContexto` `[abstract]` — Monta o recorte de contexto centrado no nó alvo.

### `PoliticaExecutor` (PoliticaBase)

*serviço* — Executor: a tarefa em mãos, as decisões que a governam e as evidências do trabalho.

### `PoliticaPlanejador` (PoliticaBase)

*serviço* — Planejador: a decomposição do alvo e as dúvidas abertas dentro dela.

### `PoliticaRevisor` (PoliticaBase)

*serviço* — Revisor: os artefatos derivados do alvo, as evidências e as decisões que os escopam.

## `context/protocolo.py`

O protocolo da memória dito ao agente: o mesmo texto no hook de início e no aperto de mão do MCP.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TITULO_DO_PROTOCOLO` | `str` | `'Protocolo de memoria do graphow'` |
| `NOME_DO_SERVIDOR_MCP` | `str` | `'graphow'` |
| `TIPOS_DE_REGISTRO` | `tuple[TipoNo, ...]` | `(TipoNo.EVIDENCE, TipoNo.DECISION, TipoNo.NOTE, TipoNo.ARTIFACT, TipoNo…` |
| `EXIGENCIAS_DO_PAPEL` | `Mapping[PapelAutor, str]` | `{PapelAutor.PLANEJADOR: "Sua Evidence e leitura de codigo: nasce com `a…` |
| `PASSOS_DO_PROTOCOLO` | `tuple[str, ...]` | `('Durante o trabalho, registre no grafo o que descobriu e decidiu, prod…` |

### Funções do módulo

- `montar_protocolo() -> tuple[str, ...]` — As linhas do protocolo, numeradas, com a sessão e o papel quando são conhecidos.

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
| `TIPOS_DE_CONTEUDO_EXTERNO` | `frozenset[TipoNo]` | `frozenset({TipoNo.EVIDENCE, TipoNo.ARTIFACT, TipoNo.APRENDIZADO})` |

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
- `anotar_ordem(no: NoGrafo) -> str` — Posição do nó na ordem total do log, quando ela é conhecida.
- `formatar_no_em_linha(no: NoGrafo) -> str` — Descreve um nó em uma linha compacta de lista, com a ordem e a autoria.
- `formatar_no_com_propriedades(no: NoGrafo) -> str` — Descreve um nó incluindo propriedades de domínio, ordem e autoria.
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

