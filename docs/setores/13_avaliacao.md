# Setor 13 — Harness de Avaliação

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.avaliacao`

Corpus de tarefas gravadas e medição do tamanho da vista contra o despejo da sessão, com e sem o recorte do grafo. Existe para que essa métrica tenha número em vez de afirmação, e declara o que ela não mede: sucesso de tarefa exige um agente real.

## Inventário

19 módulos · 3197 linhas · 36 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`avaliacao/__init__.py`](#avaliacaoinit) | 47 | Harness de avaliação: mede o tamanho da vista contra o despejo da sessão sobre um corpus gravado. |
| [`avaliacao/anonimizacao_log.py`](#avaliacaoanonimizacaolog) | 260 | Anonimização do log real para o corpus de regressão do escopo governado. |
| [`avaliacao/cenario_entre_projetos.py`](#avaliacaocenarioentreprojetos) | 190 | Segundo projeto do corpus: mede se um aprendizado do primeiro chega a uma tarefa do segundo. |
| [`avaliacao/cenario_memoria.py`](#avaliacaocenariomemoria) | 126 | Extensão do cenário gravado com a camada de memória: a sessão encerrada e condensada. |
| [`avaliacao/corpus_escopo.py`](#avaliacaocorpusescopo) | 65 | Carrega o corpus anonimizado de escopo e o reconstrói por replay da projeção. |
| [`avaliacao/entre_projetos.py`](#avaliacaoentreprojetos) | 160 | Braço entre projetos: um aprendizado do primeiro projeto chega à tarefa do segundo, e a que custo. |
| [`avaliacao/escala.py`](#avaliacaoescala) | 256 | Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado. |
| [`avaliacao/forma_do_contexto.py`](#avaliacaoformadocontexto) | 235 | A forma do contexto dos Run, somada para o relatório: peso por turno, saídas grandes, pausas e leituras fora do alvo. |
| [`avaliacao/gerar_corpus_escopo.py`](#avaliacaogerarcorpusescopo) | 58 | Gera o corpus anonimizado de escopo a partir de um banco real, só em leitura. |
| [`avaliacao/medicao.py`](#avaliacaomedicao) | 135 | Medição de tokens por tarefa, com e sem o recorte do grafo. |
| [`avaliacao/orquestracao.py`](#avaliacaoorquestracao) | 346 | Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo. |
| [`avaliacao/recorte_do_log.py`](#avaliacaorecortedolog) | 187 | Recorte do log real que o corpus de escopo preserva: Goals com trabalho, suas Tasks e a vizinhança. |
| [`avaliacao/relatorio.py`](#avaliacaorelatorio) | 150 | Agregação e formatação do relatório de avaliação de tokens por tarefa. |
| [`avaliacao/relatorio_orquestracao.py`](#avaliacaorelatorioorquestracao) | 158 | O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração. |
| [`avaliacao/relatorio_rodadas.py`](#avaliacaorelatoriorodadas) | 69 | As linhas de `orquestracao-medir --por-rodada`: onde, dentro de um Goal, o tempo e a cota foram gastos. |
| [`avaliacao/retomada.py`](#avaliacaoretomada) | 113 | Braço de retomada: quanto custa recuperar decisões e achados de uma sessão encerrada. |
| [`avaliacao/rodadas.py`](#avaliacaorodadas) | 208 | As rodadas de um Goal: cada Run do condutor, com quanto durou e quanto da cota gastou. |
| [`avaliacao/tarefas_gravadas.py`](#avaliacaotarefasgravadas) | 263 | Corpus de dez tarefas gravadas, com o grafo que as cerca. |
| [`avaliacao/transcricoes.py`](#avaliacaotranscricoes) | 171 | `graphow transcricao-medir`: a forma do contexto lida direto das transcrições, sem passar pelo banco. |

## `avaliacao/__init__.py`

Harness de avaliação: mede o tamanho da vista contra o despejo da sessão sobre um corpus gravado.

### Funções do módulo

- `executar_avaliacao() -> RelatorioDeAvaliacao` — Monta os cenários gravados, mede os três braços e consolida o relatório.

## `avaliacao/anonimizacao_log.py`

Anonimização do log real para o corpus de regressão do escopo governado.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SAL` | `str` | `'graphow-corpus-escopo-v1'` |
| `PREFIXO_POR_TIPO` | `dict[str, str]` | `{'Task': 'task', 'Goal': 'goal', 'Decision': 'dec', 'Evidence': 'evid',…` |
| `CATEGORICAS` | `frozenset[str]` | `frozenset({'status', 'veredito', 'acao', 'tipo', 'modelo', 'trilha', 'e…` |
| `AUTORES` | `frozenset[str]` | `frozenset({'assumida_por', 'posse_retomada_de', 'aberta_por', 'respondi…` |
| `CONTAGENS` | `frozenset[str]` | `frozenset({'criterio_pronto', 'criterios', 'criterios_aceite', 'fora_do…` |
| `TAMANHO_INICIAL_DO_HASH` | `int` | `6` |

### `Anonimizador`

*serviço* — Converte evento a evento, mantendo os mesmos pseudônimos de ponta a ponta.

- `converter(linha: Mapping[str, Any], bruto: EventoBruto) -> dict[str, Any] | None` — Evento anonimizado, ou None quando ele fica fora do recorte ou nada guarda.
- `propriedades(propriedades: Mapping[str, Any]) -> dict[str, Any]` — Aplica a lista branca às propriedades de um nó.
- `nomes_removidos(chaves: Sequence[str]) -> list[str]` — Nomes de propriedade removida que o corpus conhece, já na forma em que foram gravados.

### `Pseudonimos`

*serviço* — Troca ids por prefixo e hash estável, alongando o hash se dois ids colidirem.

- `atribuir(original: str, prefixo: str) -> str` — Pseudônimo do id, o mesmo em toda chamada com o mesmo original.

### `RotulosDeAutor`

*serviço* — `humano-N`, `agente-N` ou `sistema`, na ordem em que cada autor aparece.

- `de(autor: str) -> str` — Rótulo anônimo do autor, sem nada do nome original.

### Funções do módulo

- `papeis_por_autor(linhas: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]` — Papéis com que cada autor escreveu no log inteiro.
- `anonimizar_eventos(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]` — Recorta e anonimiza as linhas da tabela `eventos`, na ordem de `seq`.

## `avaliacao/cenario_entre_projetos.py`

Segundo projeto do corpus: mede se um aprendizado do primeiro chega a uma tarefa do segundo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_PROJETO_SEGUNDO` | `str` | `'proj-segundo'` |
| `ID_SETOR_SEGUNDO` | `str` | `'setor-segundo'` |
| `ID_SESSAO_SEGUNDA` | `str` | `'sess-segunda'` |
| `ID_APRENDIZADO_GLOBAL` | `str` | `'apr-corte-por-secao'` |
| `ID_APRENDIZADO_LEXICO` | `str` | `'apr-eviccao-por-lru'` |
| `ID_APRENDIZADO_ISOLADO` | `str` | `'apr-posse-no-portao'` |
| `MECANISMO_NENHUM` | `str` | `'nenhum'` |
| `TAREFAS_ENTRE_PROJETOS` | `tuple[TarefaEntreProjetos, ...]` | `(TarefaEntreProjetos(id='t2-spans', titulo='Exportar os spans do kernel…` |
| `APRENDIZADOS_GRAVADOS` | `tuple[AprendizadoGravado, ...]` | `(AprendizadoGravado(id=ID_APRENDIZADO_GLOBAL, afirmacao='Nao corte a vi…` |

### `AprendizadoGravado`

*DTO imutável* — Um aprendizado do corpus: a afirmação, como aplicar, de onde saiu e onde vale.

**Campos:** `id: str`, `afirmacao: str`, `como_aplicar: str`, `id_origem: str`, `vale_para: str`, `global_: bool`

### `TarefaEntreProjetos`

*DTO imutável* — Uma tarefa do segundo projeto e o aprendizado do primeiro de que ela depende.

**Campos:** `id: str`, `titulo: str`, `descricao: str`, `id_aprendizado_esperado: str`, `mecanismo_esperado: str`

### Funções do módulo

- `montar_cenario_entre_projetos() -> WriteKernel` — O cenário com memória, mais os aprendizados promovidos e o segundo projeto.

## `avaliacao/cenario_memoria.py`

Extensão do cenário gravado com a camada de memória: a sessão encerrada e condensada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_NOTA_DE_CONDENSACAO` | `str` | `'nota-condensacao-sess-avaliacao'` |
| `AUTOR_HUMANO` | `str` | `'david'` |
| `AUTOR_REVISOR` | `str` | `'agente-revisor'` |
| `RESUMO_DECLARADO` | `str` | `'Nove das dez tarefas do kernel fechadas; o ciclo de vida pelos hooks f…` |
| `CORPO_DA_CONDENSACAO` | `str` | `'Decisoes vigentes: o item de patch e um dataclass frozen, porque o lot…` |

### Funções do módulo

- `montar_cenario_com_memoria() -> WriteKernel` — O cenário gravado, mais a sessão encerrada e a condensação escrita pelo revisor.
- `estender_com_memoria(kernel: WriteKernel) -> WriteKernel` — Encerra a sessão do corpus e grava a condensação que um revisor escreveria.
- `ids_de_conhecimento_do_corpus() -> tuple[str, ...]` — As decisões e evidências que o corpus gravou, na ordem das tarefas.

## `avaliacao/corpus_escopo.py`

Carrega o corpus anonimizado de escopo e o reconstrói por replay da projeção.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMINHO_DO_CORPUS` | `Path` | `Path(__file__).resolve().parents[3] / 'tests' / 'avaliacao' / 'dados' /…` |

### `CorpusEscopo`

*DTO imutável* — Eventos do corpus em ordem de `seq` e o estado final que o replay produz.

**Campos:** `eventos: tuple[EventoLog, ...]`, `estado: GrafoEstado`

- `estado_ate(seq: int) -> GrafoEstado` — Estado do grafo logo depois do evento `seq`, para as análises temporais.

### Funções do módulo

- `evento_do_corpus(registro: dict[str, Any]) -> EventoLog` — Reconstrói o evento a partir da linha do corpus; o id do evento é derivado do `seq`.
- `ler_registros(caminho: Path) -> Iterable[dict[str, Any]]` — Linhas do corpus, uma por evento, na ordem gravada.
- `carregar_corpus(caminho: Path | None) -> CorpusEscopo` — Lê o corpus e projeta o grafo pelo redutor de produção.

## `avaliacao/entre_projetos.py`

Braço entre projetos: um aprendizado do primeiro projeto chega à tarefa do segundo, e a que custo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_ENTRE_PROJETOS` | `int` | `1500` |
| `PROFUNDIDADE_MAXIMA` | `int` | `8` |

### `MedicaoEntreProjetos`

*DTO imutável* — Uma tarefa do segundo projeto: o aprendizado chegou, e a que custo em cada braço.

**Campos:** `id_tarefa: str`, `id_aprendizado_esperado: str`, `mecanismo_esperado: str`, `chegou: bool`, `tokens_pela_vista: int`, `tokens_despejo_do_primeiro_projeto: int`, `tokens_busca_cega: int`

### `MedidorEntreProjetos`

*serviço* — Mede, por tarefa do segundo projeto, a vista contra o despejo e a busca cega.

- `medir_todas(tarefas: Sequence[TarefaEntreProjetos]) -> RelatorioEntreProjetos` — Mede cada tarefa gravada do segundo projeto sobre a mesma projeção.

### `RelatorioEntreProjetos`

*DTO imutável* — As medições do braço e o índice semântico com que foram feitas.

**Campos:** `medicoes: tuple[MedicaoEntreProjetos, ...]`, `indice_semantico: str`

- `acertos() -> int` `[property]` — Quantas tarefas receberam o aprendizado de que dependiam.
- `taxa_de_acerto() -> float` `[property]` — Fração de tarefas atendidas, entre 0 e 1.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do braço, prontas para o console.

## `avaliacao/escala.py`

Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_DA_MEDICAO` | `int` | `1500` |
| `PROFUNDIDADE_MAXIMA_DA_DESCIDA` | `int` | `8` |
| `TERMOS_DE_SONDAGEM` | `tuple[str, ...]` | `('dados', 'modelo', 'a')` |
| `TIPOS_DE_CONTAINER` | `tuple[TipoNo, ...]` | `(TipoNo.PROJETO, TipoNo.SETOR, TipoNo.SESSAO)` |

### `MedidaDeBusca`

*DTO imutável* — Custo de uma busca, com e sem o limite de resultados.

**Campos:** `termo: str`, `total_encontrado: int`, `tokens_sem_limite: int`, `tokens_com_limite: int`

### `MedidaDeCanvas`

*DTO imutável* — Peso do payload do canvas sob um recorte.

**Campos:** `rotulo: str`, `nos: int`, `kilobytes: float`

### `MedidorDeEscala`

*serviço* — Roda as três medidas sobre a projeção do ramo informado.

- `medir(ramo_id: str) -> RelatorioDeEscala` — Consolida o relatório de escala do ramo.

### `RelatorioDeEscala`

*DTO imutável* — Consolidação das três medidas que decidem se o grafo ainda cabe.

**Campos:** `total_nos: int`, `total_arestas: int`, `canvas: tuple[MedidaDeCanvas, ...]`, `tokens_da_varredura: int`, `tokens_do_caminho_guiado: int`, `passos_do_caminho_guiado: tuple[str, ...]`, `buscas: tuple[MedidaDeBusca, ...]`, `nos_orfaos: tuple[str, ...]`, `milissegundos_do_rollup: float`, `tokens_do_panorama_da_raiz: int`

- `fator_de_reducao_da_navegacao() -> float` `[property]` — Quantas vezes o caminho guiado é mais barato que a varredura cega.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do relatório, prontas para o console.

### Funções do módulo

- `medir_escala(kernel: WriteKernel, ramo_id: str) -> RelatorioDeEscala` — Ponto de entrada da medição de escala sobre um kernel já montado.

## `avaliacao/forma_do_contexto.py`

A forma do contexto dos Run, somada para o relatório: peso por turno, saídas grandes, pausas e leituras fora do alvo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_ARQUIVO_DA_EVIDENCIA` | `str` | `'arquivo'` |
| `CAMPO_TURNOS` | `str` | `'mensagens_de_modelo'` |
| `CAMPOS_DA_FORMA` | `tuple[str, ...]` | `(CAMPO_CONTEXTO_MEDIO, CAMPO_MAIOR_SAIDA, CAMPO_MAIOR_PAUSA, CAMPO_CAMI…` |
| `RUNS_MAIS_CAROS` | `int` | `3` |
| `FERRAMENTAS_MOSTRADAS` | `int` | `3` |
| `SEGUNDOS_POR_MINUTO` | `int` | `60` |

### `FormaAgregada`

*DTO imutável* — A forma do contexto de vários Run: médias ponderadas pelos turnos, picos e somas.

**Campos:** `contexto_medio: int | None`, `contexto_maximo: int | None`, `turnos_maximo: int | None`, `maior_saida: int | None`, `saidas_grandes: int`, `pausas_longas: int`, `maior_pausa_s: int | None`, `leituras_fora_do_alvo: int | None`, `saidas_grandes_por_ferramenta: Mapping[str, int]`

### `RunCaro`

*DTO imutável* — Um Run pelo que custou: quem, quanto, quanto tempo, quantos turnos e o contexto médio.

**Campos:** `agente: str`, `tokens: int`, `duracao_s: int | None`, `turnos: int`, `contexto_medio: int | None`

### Funções do módulo

- `agregar_forma(runs: Iterable[tuple[Mapping[str, Any], int | None]]) -> FormaAgregada | None` — A forma somada dos Run, cada um com as suas leituras fora do alvo; None quando nenhum traz forma.
- `formatar_forma(forma: FormaAgregada) -> str` — A linha da forma do contexto, cada trecho só quando o dado existe.
- `runs_mais_caros(runs: Iterable[Mapping[str, Any]], quantos: int) -> tuple[RunCaro, ...]` — Os Run de maior custo em tokens, do mais caro ao mais barato; os sem token ficam de fora.
- `formatar_run_caro(run: RunCaro) -> str` — O Run caro numa frase: agente, tokens, duração, turnos e contexto médio.
- `leituras_fora_do_run(propriedades: Mapping[str, Any], view: GrafoView) -> int | None` — Quantos caminhos lidos pelo Run caem fora do alvo das Tasks que ele assumiu; None sem Task ou sem alvo.
- `caminhos_lidos(propriedades: Mapping[str, Any]) -> tuple[str, ...]` — Os caminhos lidos pelas ferramentas de leitura e pelo shell, sem repetição.
- `alvos_das_tarefas(view: GrafoView, ids_tarefas: Iterable[str]) -> tuple[str, ...]` — Os `arquivos_alvo` das Tasks e o `arquivo` das Evidence derivadas delas; vazio quando nenhuma existe.
- `contar_fora_do_alvo(caminhos: Iterable[str], alvos: Iterable[str]) -> int | None` — Quantos caminhos não casam com alvo nenhum; None quando não há alvo contra o qual medir.
- `casa_com_alvo(caminho: str, alvo: str) -> bool` — O caminho lido é o alvo, termina nele, é o sufixo dele ou está dentro da pasta que ele nomeia.
- `normalizar_caminho_lido(caminho: str) -> str` — Barra normal, sem `./` na frente nem barra no fim, em minúsculas: a forma em que dois caminhos se comparam.
- `tokens_do_run(propriedades: Mapping[str, Any]) -> int` — A soma das quatro categorias de token; zero quando o Run não traz nenhuma.

## `avaliacao/gerar_corpus_escopo.py`

Gera o corpus anonimizado de escopo a partir de um banco real, só em leitura.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `COLUNAS` | `str` | `'id, seq, timestamp_utc, autor, papel, origem, tipo_evento, payload_jso…` |

### Funções do módulo

- `ler_linhas(caminho_banco: Path) -> list[dict[str, Any]]` — Todas as linhas do ramo principal, lidas com a conexão em modo somente leitura.
- `gravar_corpus(eventos: Sequence[dict[str, Any]], destino: Path) -> int` — Grava um evento por linha, comprimido, de forma determinística; devolve os bytes.
- `main(argv: Sequence[str] | None) -> int` — Lê o banco, anonimiza o recorte e grava o corpus.

## `avaliacao/medicao.py`

Medição de tokens por tarefa, com e sem o recorte do grafo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARESTAS_DE_ALCANCE_DA_SESSAO` | `frozenset[TipoAresta]` | `frozenset({TipoAresta.PRODUZ, TipoAresta.DECOMPOE, TipoAresta.CONTEM})` |
| `PROFUNDIDADE_MAXIMA` | `int` | `8` |

### `MedicaoDaTarefa`

*DTO imutável* — Custo de contexto e esforço humano de uma tarefa gravada.

**Campos:** `id_tarefa: str`, `tokens_com_grafo: int`, `tokens_sem_grafo: int`, `intervencoes_humanas: int`, `concluida: bool`

- `reducao() -> float` `[property]` — Fração do contexto poupada pelo recorte, entre 0 e 1.

### `MedidorDeTarefas`

*serviço* — Executa a medição das dez tarefas gravadas sobre um cenário montado.

- `medir_todas() -> tuple[MedicaoDaTarefa, ...]` — Mede cada tarefa do corpus contra o mesmo cenário gravado.

## `avaliacao/orquestracao.py`

Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_CONFIGURACAO` | `str` | `'sem configuracao'` |
| `SEM_MODELO` | `str` | `'sem modelo'` |
| `AGENTE_ORQUESTRADOR` | `str` | `'orquestrador'` |
| `CAMPOS_DE_TOKENS` | `tuple[str, ...]` | `tuple(CHAVES_DE_USO.values())` |
| `CAMPO_CACHE_LEITURA` | `str` | `CHAVES_DE_USO['cache_read_input_tokens']` |
| `SEM_MOTIVO` | `str` | `'sem motivo'` |

### `MedicaoDeGoal`

*DTO imutável* — O que um Goal custou e rendeu sob a configuração com que foi orquestrado.

**Campos:** `id_goal: str`, `rotulo: str`, `configuracao: str`, `tarefas: int`, `concluidas: int`, `concluidas_sem_retrabalho: int`, `com_retrabalho: int`, `correcoes: int`, `rejeicoes: int`, `aprovacoes: int`, `aceites_pelo_teto: int`, `modelos_por_tarefa: Mapping[str, int]`, `tarefas_leves: int`, `tokens_por_agente: Mapping[str, int]`, `tokens_cache_leitura: int`, `runs_sem_tokens_por_motivo: Mapping[str, int]`, `rodadas: tuple[Rodada, ...]`, `forma: FormaAgregada | None`, `runs_mais_caros: tuple[RunCaro, ...]`

- `tokens() -> int` `[property]` — Todos os tokens atribuídos ao Goal, de todos os agentes.
- `tokens_sem_cache_leitura() -> int` `[property]` — Os tokens sem a leitura de cache, que domina o total e custa bem menos que os outros.
- `runs_sem_tokens() -> int` `[property]` — Quantos Run atribuídos ao Goal não trouxeram token nenhum, por qualquer motivo.
- `segundos_de_rodada() -> float` `[property]` — A soma das durações conhecidas dos condutores, na parte que cabe ao Goal.
- `pontos_de_cota_semanal() -> float | None` `[property]` — A soma das variações conhecidas da cota semanal, na parte do Goal; None sem nenhuma conhecida.

### `MedidorDeOrquestracao`

*serviço* — Consulta pura sobre a projeção: nada é escrito, e o mesmo grafo dá sempre o mesmo número.

- `medir(ids_goals: Iterable[str]) -> tuple[MedicaoDeGoal, ...]` — Uma medição por Goal pedido; sem pedido, todo Goal que tem tarefas decompostas.

### `TrabalhoDoGoal`

*DTO imutável* — Os nós que pertencem ao Goal: tarefas, artefatos, vereditos e as sessões que os produziram.

**Campos:** `tarefas: tuple[NoGrafo, ...]`, `artefatos: frozenset[str]`, `vereditos: tuple[NoGrafo, ...]`, `sessoes: frozenset[str]`

- `ids_tarefas() -> frozenset[str]` `[property]` — Os ids das tarefas do Goal, correções incluídas.

## `avaliacao/recorte_do_log.py`

Recorte do log real que o corpus de escopo preserva: Goals com trabalho, suas Tasks e a vizinhança.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MINIMO_DE_TASKS_POR_GOAL` | `int` | `3` |
| `CAMPOS_DE_REFERENCIA` | `frozenset[str]` | `frozenset({'corrige', 'id_alvo', 'substitui'})` |
| `TIPO_GOAL` | `str` | `'Goal'` |
| `TIPO_TASK` | `str` | `'Task'` |
| `TIPO_SESSAO` | `str` | `'Sessao'` |
| `TIPO_RUN` | `str` | `'Run'` |
| `ARESTA_DECOMPOE` | `str` | `'decompoe'` |
| `ARESTA_CONTEM` | `str` | `'contem'` |
| `ARESTA_PRODUZ` | `str` | `'produz'` |

### `EventoBruto`

*DTO imutável* — Evento do banco com o payload já decodificado, a única forma que o recorte lê.

**Campos:** `id: str`, `seq: int`, `tipo_evento: str`, `payload: dict[str, Any]`

### `Historia`

*DTO imutável* — Tudo que o log chegou a criar: tipo de cada nó, arestas e a sessão de cada Run.

**Campos:** `tipos: dict[str, str]`, `arestas: dict[str, tuple[str, str, str]]`, `sessao_do_run: dict[str, str]`, `referencias: dict[str, set[str]]`

### `Recorte`

*DTO imutável* — Nós e arestas que entram no corpus, e os Goals que o motivaram.

**Campos:** `goals: frozenset[str]`, `nos: dict[str, str]`, `arestas: frozenset[str]`

### `_Levantamento`

*serviço* — Acumula, evento a evento, o que o log criou.

- `registrar(evento: EventoBruto) -> None` — Anota o nó, a aresta ou o Run que o evento cria.
- `historia() -> Historia` — Fecha o levantamento; Run ligado só por `produz` ganha a sessão que o produziu.

### Funções do módulo

- `id_do_run(evento: EventoBruto) -> str` — Identificador do Run de um evento de execução, igual ao que a projeção usa.
- `levantar_historia(eventos: Iterable[EventoBruto]) -> Historia` — Varre o log uma vez e junta o que o recorte precisa saber.
- `tasks_por_goal(historia: Historia) -> dict[str, set[str]]` — Tasks alcançáveis de cada Goal por `decompoe`, em qualquer momento da história.
- `calcular_recorte(historia: Historia) -> Recorte` — Goals relevantes, Tasks, vizinhos, referências citadas, ancestrais e Runs das sessões.
- `eventos_brutos(linhas: Sequence[Any]) -> list[EventoBruto]` — Converte as linhas do banco em eventos com payload decodificado.

## `avaliacao/relatorio.py`

Agregação e formatação do relatório de avaliação de tokens por tarefa.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITES_DECLARADOS` | `tuple[str, ...]` | `("Sucesso de tarefa nao e medido: nenhum agente executa as tarefas, 'co…` |

### `RelatorioDeAvaliacao`

*DTO imutável* — Consolidação das medições: tamanho da vista contra o despejo, por tarefa marcada concluída.

**Campos:** `medicoes: tuple[MedicaoDaTarefa, ...]`, `calibracao: str`, `limites: tuple[str, ...]`, `retomada: MedicaoDeRetomada | None`, `entre_projetos: RelatorioEntreProjetos | None`

- `a_partir_de(medicoes: Sequence[MedicaoDaTarefa]) -> 'RelatorioDeAvaliacao'` — Monta o relatório registrando com que régua os tokens foram medidos.
- `bem_sucedidas() -> tuple[MedicaoDaTarefa, ...]` `[property]` — Somente as tarefas concluídas entram na métrica número um.
- `tokens_por_tarefa_bem_sucedida() -> float` `[property]` — Média de tokens de contexto por tarefa concluída, com o grafo.
- `tokens_por_tarefa_sem_grafo() -> float` `[property]` — Mesma média no braço sem divulgação progressiva.
- `intervencoes_por_tarefa() -> float` `[property]` — Média de respostas humanas exigidas por tarefa concluída.
- `reducao_media() -> float` `[property]` — Fração média de contexto poupada nas tarefas concluídas.
- `formatar() -> tuple[str, ...]` — Linhas legíveis do relatório, prontas para o console.

## `avaliacao/relatorio_orquestracao.py`

O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_GOALS` | `str` | `'Nenhum Goal com tarefas decompostas: nada a medir.'` |

### Funções do módulo

- `formatar_relatorio(medicoes: Sequence[MedicaoDeGoal]) -> tuple[str, ...]` — As linhas do relatório: cada Goal medido e, no fim, a soma por configuração.

## `avaliacao/relatorio_rodadas.py`

As linhas de `orquestracao-medir --por-rodada`: onde, dentro de um Goal, o tempo e a cota foram gastos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_RODADAS` | `str` | `' rodadas: nenhum Run do condutor atribuido'` |
| `DESCONHECIDO` | `str` | `'?'` |
| `NOTA_DAS_RODADAS` | `tuple[str, ...]` | `('Rodadas: a janela vai do inicio ao fim do Run do condutor, e tokens s…` |

### Funções do módulo

- `linhas_das_rodadas(medicao: MedicaoDeGoal) -> tuple[str, ...]` — Uma linha por rodada do Goal, R1 a Rn, depois do bloco dele.
- `nota_das_rodadas(medicoes: Sequence[MedicaoDeGoal]) -> tuple[str, ...]` — A explicação das colunas, uma vez no fim; some quando nenhum Goal teve rodada.

## `avaliacao/retomada.py`

Braço de retomada: quanto custa recuperar decisões e achados de uma sessão encerrada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_DA_RETOMADA` | `int` | `1500` |
| `PAPEL_DA_MEDICAO` | `PapelAutor` | `PapelAutor.PLANEJADOR` |
| `TIPOS_DE_CONHECIMENTO` | `frozenset[TipoNo]` | `frozenset({TipoNo.DECISION, TipoNo.EVIDENCE})` |

### `MedicaoDeRetomada`

*DTO imutável* — Custo de retomar uma sessão encerrada, pela abertura da vista e nó a nó.

**Campos:** `id_sessao: str`, `tokens_pela_vista: int`, `tokens_no_a_no: int`, `nos_lidos_um_a_um: int`, `decisoes_vigentes: int`, `decisoes_entregues: int`, `condensacao_entregue: bool`

- `reducao() -> float` `[property]` — Fração do contexto poupada pela abertura da vista, entre 0 e 1.
- `cobertura_completa() -> bool` `[property]` — A abertura só vale o que economiza se entregar toda decisão vigente e a condensação.

### `MedidorDeRetomada`

*serviço* — Compara a abertura da vista da sessão encerrada com a leitura nó a nó.

- `medir(id_sessao: str, orcamento: int) -> MedicaoDeRetomada` — Mede os dois braços sobre a mesma projeção.

## `avaliacao/rodadas.py`

As rodadas de um Goal: cada Run do condutor, com quanto durou e quanto da cota gastou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AGENTE_CONDUTOR` | `str` | `'graphow-condutor'` |

### `MarcasNoTempo`

*DTO imutável* — Quando cada coisa do Goal aconteceu, para contar o que cai na janela de cada rodada.

**Campos:** `conclusoes: tuple[datetime, ...]`, `aprovacoes: tuple[datetime, ...]`, `rejeicoes: tuple[datetime, ...]`, `runs: tuple[RunNoTempo, ...]`

### `NaJanela`

*DTO imutável* — O que aconteceu no Goal entre o início e o fim da rodada.

**Campos:** `concluidas: int`, `aprovados: int`, `rejeitados: int`, `tokens: int`, `tokens_sem_cache_leitura: int`

### `Rodada`

*DTO imutável* — Um Run do condutor situado no tempo, com a parte dele que cabe ao Goal.

**Campos:** `id_run: str`, `id_sessao: str`, `inicio: datetime | None`, `fim: datetime | None`, `duracao_s: int | None`, `divisor: int`, `cota: VariacaoDeCota`, `na_janela: NaJanela | None`

### `RunNoTempo`

*DTO imutável* — Um Run do Goal pelo instante em que começou, com os tokens da parte do Goal.

**Campos:** `inicio: datetime`, `tokens: int`, `tokens_sem_cache_leitura: int`

### `VariacaoDeCota`

*DTO imutável* — Os pontos percentuais que a rodada gastou de cada janela; None quando não se sabe.

**Campos:** `cinco_horas: float | None`, `semanal: float | None`

### Funções do módulo

- `situar(rodadas: Iterable[Rodada], marcas: MarcasNoTempo) -> tuple[Rodada, ...]` — Cada rodada com o que caiu na janela dela; a que não tem início e fim fica sem janela.
- `ultimo_toque(no: NoGrafo) -> datetime | None` — O último toque do nó no log, ou o nascimento se ninguém o tocou depois.
- `nascimento(no: NoGrafo) -> datetime | None` — Quando o log registrou o nó.
- `eh_condutor(run: NoGrafo) -> bool` — O Run é de uma rodada: o subagente que terminou era o condutor.
- `eh_run_da_sessao(run: NoGrafo) -> bool` — O Run é da sessão, não de um subagente: é nele que a cota da parada fica.
- `montar_rodadas(condutores: Sequence[tuple[NoGrafo, int]], raizes: Mapping[str, NoGrafo]) -> tuple[Rodada, ...]` — As rodadas em ordem de início, as sem início no fim, cada uma com a variação de cota.

## `avaliacao/tarefas_gravadas.py`

Corpus de dez tarefas gravadas, com o grafo que as cerca.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ID_PROJETO` | `str` | `'proj-avaliacao'` |
| `ID_SETOR` | `str` | `'setor-engenharia'` |
| `ID_SESSAO` | `str` | `'sess-avaliacao'` |
| `ID_GOAL` | `str` | `'goal-substrato'` |
| `ORCAMENTO_PADRAO_DA_MEDICAO` | `int` | `1500` |
| `TAREFAS_GRAVADAS` | `tuple[TarefaGravada, ...]` | `(TarefaGravada(id='t01-parser', titulo='Escrever o parser de JSON Patch…` |

### `DescricaoDeNo`

*DTO imutável* — Rótulo e propriedades de um nó a criar, agrupados para caber na assinatura.

**Campos:** `rotulo: str`, `propriedades: Mapping[str, str]`

### `Ligacao`

*DTO imutável* — As duas pontas e o tipo de uma aresta a criar.

**Campos:** `origem: str`, `destino: str`, `tipo: TipoAresta`

### `TarefaGravada`

*DTO imutável* — Uma tarefa do corpus, com o que basta para medi-la de forma repetível.

**Campos:** `id: str`, `titulo: str`, `criterio_pronto: str`, `papel: PapelAutor`, `concluida: bool`, `depende_de: str`, `pergunta_escalada: str`, `orcamento_tokens: int`, `decisoes: tuple[str, ...]`, `evidencias: tuple[str, ...]`

- `id_questao() -> str` `[property]` — Identificador da Question de escalação desta tarefa, se houver.

### Funções do módulo

- `montar_cenario_gravado() -> WriteKernel` — Reconstrói o grafo das dez tarefas sempre da mesma forma, do zero.

## `avaliacao/transcricoes.py`

`graphow transcricao-medir`: a forma do contexto lida direto das transcrições, sem passar pelo banco.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXTENSAO_DE_TRANSCRICAO` | `str` | `'.jsonl'` |
| `SUFIXO_DOS_METADADOS` | `str` | `'.meta.json'` |
| `CAMPO_TIPO_DO_AGENTE` | `str` | `'agentType'` |
| `PASTA_DE_SUBAGENTES` | `str` | `'subagents'` |
| `CARACTERES_DA_SESSAO` | `int` | `8` |
| `TOP_PADRAO` | `int` | `20` |
| `SEM_TRANSCRICOES` | `str` | `'Nenhuma transcricao legivel: nada a medir.'` |
| `CAMPO_CACHE_LEITURA` | `str` | `CHAVES_DE_USO['cache_read_input_tokens']` |

### `MedicaoDeTranscricao`

*DTO imutável* — Uma transcrição medida: de onde veio, quem a escreveu, as propriedades que viraria no Run e as leituras fora do alvo.

**Campos:** `rotulo: str`, `agente: str`, `propriedades: Mapping[str, Any]`, `leituras_fora_do_alvo: int | None`

- `tokens() -> int` `[property]` — O custo em tokens, as quatro categorias somadas.

### Funções do módulo

- `coletar_transcricoes(entradas: Iterable[Path]) -> tuple[tuple[Path, str], ...]` — Cada transcrição com o rótulo que o relatório mostra; a pasta é varrida por inteiro.
- `medir_transcricoes(transcricoes: Iterable[tuple[Path, str]], view: GrafoView | None) -> tuple[MedicaoDeTranscricao, ...]` — A medição de cada transcrição legível, da mais cara à mais barata.
- `formatar_transcricoes(medicoes: tuple[MedicaoDeTranscricao, ...], top: int) -> tuple[str, ...]` — As `top` transcrições mais caras, uma por linha, e o agregado de todas.
- `vista_somente_leitura(caminho: Path | None) -> Iterator[GrafoView | None]` — A vista do ramo principal sobre uma cópia em memória do banco; None quando o banco não existe.

