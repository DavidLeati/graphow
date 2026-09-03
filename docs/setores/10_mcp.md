# Setor 10 — Superfície MCP

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.mcp`

Ferramentas expostas a agentes via Model Context Protocol, com o papel fixado na abertura da sessão e recusado nos argumentos.

## Inventário

15 módulos · 1713 linhas · 25 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`mcp/construcao_operacoes.py`](#mcpconstrucaooperacoes) | 71 | Construtores de operações JSON Patch reutilizados pelas ferramentas MCP. |
| [`mcp/espera.py`](#mcpespera) | 85 | Relógio e política de espera do long-poll MCP, isolados para permitir teste. |
| [`mcp/ferramentas_escalacao.py`](#mcpferramentasescalacao) | 145 | Ferramentas MCP do caminho de volta: da resposta humana até o agente. |
| [`mcp/ferramentas_exclusao.py`](#mcpferramentasexclusao) | 97 | Ferramentas MCP de exclusão, restritas a sessões humanas pela política de identidade. |
| [`mcp/ferramentas_leitura.py`](#mcpferramentasleitura) | 101 | Ferramentas MCP de leitura e inspeção do grafo, sem efeitos colaterais. |
| [`mcp/ferramentas_navegacao.py`](#mcpferramentasnavegacao) | 132 | Ferramentas MCP da camada de navegação: Projeto, Setor e Sessão. |
| [`mcp/ferramentas_posse.py`](#mcpferramentasposse) | 93 | Ferramentas MCP de posse de tarefa: adquirir e devolver a escrita exclusiva. |
| [`mcp/ferramentas_trabalho.py`](#mcpferramentastrabalho) | 198 | Ferramentas MCP da camada de trabalho: tarefas, questões e patches livres. |
| [`mcp/identidade_sessao.py`](#mcpidentidadesessao) | 102 | Identidade imutável de uma sessão MCP e política de autorização por ferramenta. |
| [`mcp/server.py`](#mcpserver) | 112 | Servidor de Protocolo MCP (Model Context Protocol) para interação com agentes. |
| [`mcp/stdio_protocolo.py`](#mcpstdioprotocolo) | 169 | Transporte e despacho do protocolo JSON-RPC 2.0 usado pelo servidor MCP stdio. |
| [`mcp/stdio_server.py`](#mcpstdioserver) | 85 | Servidor MCP sobre transporte stdio com protocolo JSON-RPC 2.0. |
| [`mcp/submissao.py`](#mcpsubmissao) | 64 | Submissão de patches originados em ferramentas MCP sob a identidade da sessão. |
| [`mcp/tool_definitions.py`](#mcptooldefinitions) | 247 | Definições formais de schemas para ferramentas MCP expostas a agentes LLM. |

## `mcp/construcao_operacoes.py`

Construtores de operações JSON Patch reutilizados pelas ferramentas MCP.

### `EspecificacaoAresta`

*DTO imutável* — Descrição imutável de uma aresta tipada a ser criada no grafo.

**Campos:** `id: str`, `origem_id: str`, `destino_id: str`, `tipo: TipoAresta`

### `EspecificacaoNo`

*DTO imutável* — Descrição imutável de um nó a ser criado no grafo.

**Campos:** `id: str`, `tipo: TipoNo`, `rotulo: str`, `propriedades: Mapping[str, Any]`

### Funções do módulo

- `gerar_identificador(prefixo: str) -> str` — Gera um identificador curto e legível para um novo elemento do grafo.
- `montar_operacao_criar_no(especificacao: EspecificacaoNo) -> ItemPatch` — Monta a operação RFC 6902 de criação de um nó tipado.
- `montar_operacao_criar_aresta(especificacao: EspecificacaoAresta) -> ItemPatch` — Monta a operação RFC 6902 de criação de uma aresta tipada.
- `montar_operacao_remover_no(id_no: str) -> ItemPatch` — Monta a operação RFC 6902 de remoção de um nó.
- `montar_operacao_remover_aresta(id_aresta: str) -> ItemPatch` — Monta a operação RFC 6902 de remoção de uma aresta.
- `montar_operacao_definir_propriedade(id_no: str, chave: str, valor: object) -> ItemPatch` — Monta a operação RFC 6902 que define uma propriedade de um nó existente.

## `mcp/espera.py`

Relógio e política de espera do long-poll MCP, isolados para permitir teste.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TEMPO_DE_ESPERA_PADRAO_SEGUNDOS` | `float` | `30.0` |
| `INTERVALO_DE_SONDAGEM_SEGUNDOS` | `float` | `0.5` |
| `TEMPO_MAXIMO_DE_ESPERA_SEGUNDOS` | `float` | `300.0` |

### `PoliticaEspera`

*DTO imutável* — Prazos aceitos pelo long-poll, com teto para não prender o transporte.

**Campos:** `prazo_padrao_segundos: float`, `intervalo_segundos: float`, `prazo_maximo_segundos: float`

- `prazo_valido(solicitado: Any) -> float` — Normaliza o prazo pedido pelo agente dentro dos limites da política.

### `Relogio` (ABC)

*contrato* — Contrato mínimo de tempo usado pelas ferramentas que esperam.

- `agora() -> float` `[abstract]` — Instante monotônico corrente, em segundos.
- `aguardar(segundos: float) -> None` `[abstract]` — Suspende a execução pelo intervalo informado.

### `RelogioMonotonico` (Relogio)

*serviço* — Relógio real de produção, imune a ajustes do relógio de parede.

- `agora() -> float` — Lê o contador monotônico do sistema.
- `aguardar(segundos: float) -> None` — Dorme pelo intervalo informado.

### `RelogioSimulado` (Relogio)

*serviço* — Relógio determinístico: cada espera apenas avança o contador interno.

- `agora() -> float` — Instante corrente do relógio simulado.
- `aguardar(segundos: float) -> None` — Avança o relógio sem suspender o processo.
- `esperas_registradas() -> tuple[float, ...]` `[property]` — Intervalos pelos quais o código pediu para esperar.

## `mcp/ferramentas_escalacao.py`

Ferramentas MCP do caminho de volta: da resposta humana até o agente.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_AUTOR_DA_QUESTAO` | `str` | `'aberta_por'` |

### `DescricaoQuestao`

*DTO imutável* — Instantâneo de uma dúvida aberta pelo agente e do que houve com ela.

**Campos:** `id: str`, `pergunta: str`, `status: str`, `resposta: str`, `respondida_por: str`

- `de_no(no: NoGrafo) -> 'DescricaoQuestao'` — Projeta o nó Question na forma que a ferramenta devolve.
- `em_dicionario() -> dict[str, str]` — Forma serializável para a resposta MCP.
- `foi_encerrada() -> bool` `[property]` — Uma dúvida deixa de bloquear quando sai do status 'aberta'.

### `FerramentasEscalacao`

*serviço* — Consulta e espera pelas respostas às dúvidas abertas por esta sessão.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de escalação aos seus executores.
- `minhas_questoes(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Lista as dúvidas abertas por este autor, com resposta quando houver.
- `aguardar_resposta(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Bloqueia até a dúvida ser encerrada pelo humano ou o prazo expirar.

## `mcp/ferramentas_exclusao.py`

Ferramentas MCP de exclusão, restritas a sessões humanas pela política de identidade.

### `FerramentasExclusao`

*serviço* — Remoção individual, em lote e em cascata de elementos do grafo.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de exclusão aos seus executores.
- `excluir_em_lote(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Remove atomicamente uma coleção arbitrária de nós e arestas.
- `excluir_projeto(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Remove o projeto e, opcionalmente, todos os seus descendentes.

## `mcp/ferramentas_leitura.py`

Ferramentas MCP de leitura e inspeção do grafo, sem efeitos colaterais.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORCAMENTO_TOKENS_PADRAO` | `int` | `1500` |

### `FerramentasLeitura`

*serviço* — Consultas do agente sobre o grafo, materializadas sob orçamento de tokens.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de leitura aos seus executores.
- `proximas_tarefas(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Devolve as tarefas executáveis da sessão, em ordem estável de atendimento.
- `ler_vista(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Materializa o subgrafo focal usando a política do papel da sessão.
- `expandir_no(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Devolve a ficha completa de um nó específico e suas arestas incidentes.
- `buscar(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Pesquisa textual sobre rótulos e propriedades, filtrada por tipos da ontologia.

## `mcp/ferramentas_navegacao.py`

Ferramentas MCP da camada de navegação: Projeto, Setor e Sessão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NIVEL_AUTONOMIA_PADRAO` | `str` | `'estrito'` |

### `FerramentasNavegacao`

*serviço* — Criação dos contêineres hierárquicos que organizam o grafo de trabalho.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de navegação aos seus executores.
- `criar_projeto(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Cria o nó Projeto raiz definindo o nível de autonomia dos agentes.
- `criar_setor(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Cria o Setor e a aresta de contenção que o liga ao Projeto.
- `criar_sessao(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Cria a Sessão e a aresta de contenção que a liga ao Setor.
- `configurar_autonomia_projeto(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Ajusta o nível de autonomia de um projeto. Restrito a sessões humanas.

### `PedidoContainerFilho`

*DTO imutável* — Parâmetros de criação de um contêiner subordinado a outro na hierarquia.

**Campos:** `id_filho: str`, `tipo_filho: TipoNo`, `id_pai: str`, `rotulo: str`

## `mcp/ferramentas_posse.py`

Ferramentas MCP de posse de tarefa: adquirir e devolver a escrita exclusiva.

### `FerramentasPosse`

*serviço* — Aquisição e devolução do direito exclusivo de escrever numa Task.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de posse aos seus executores.
- `assumir_tarefa(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Adquire o lock da Task e a move para 'em_andamento' no mesmo gesto.
- `liberar_tarefa(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Devolve o lock da Task, deixando o status como está.

## `mcp/ferramentas_trabalho.py`

Ferramentas MCP da camada de trabalho: tarefas, questões e patches livres.

### `FerramentasTrabalho`

*serviço* — Operações do agente sobre o grafo de intenção e execução.

- `obter_manipuladores() -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]` — Mapeia os nomes das ferramentas de trabalho aos seus executores.
- `criar_tarefa(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Cria uma Task com aresta 'produz' e hierarquias opcionais.
- `abrir_questao(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Abre uma Question e a aresta 'bloqueia' que trava a tarefa até resposta humana.
- `responder_questao(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Registra a resposta humana e destrava a tarefa. Restrito a sessões humanas.
- `concluir_tarefa(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Transiciona a Task para concluído, se nenhuma Question aberta a bloquear.
- `propor_patch(argumentos: Mapping[str, Any]) -> dict[str, Any]` — Submete um lote livre de operações RFC 6902 aos quatro portões.

## `mcp/identidade_sessao.py`

Identidade imutável de uma sessão MCP e política de autorização por ferramenta.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEIS_VALIDOS_EM_SESSAO` | `frozenset[PapelAutor]` | `frozenset({PapelAutor.HUMANO, PapelAutor.PLANEJADOR, PapelAutor.EXECUTO…` |
| `FERRAMENTAS_EXCLUSIVAS_DO_HUMANO` | `frozenset[str]` | `frozenset({'responder_questao', 'configurar_autonomia_projeto', 'exclui…` |

### `IdentidadeSessaoMCP`

*DTO imutável* — Autor e papel fixados para toda a duração de uma sessão MCP.

**Campos:** `autor: str`, `papel: PapelAutor`

- `criar(autor: str, papel_declarado: str) -> 'IdentidadeSessaoMCP'` — Valida e congela a identidade da sessão a partir da configuração do servidor.
- `eh_humano() -> bool` `[property]` — Indica se a sessão foi aberta sob a identidade humana.

### `PoliticaIdentidadeMCP`

*serviço* — Decide, sem efeitos colaterais, se a identidade da sessão pode usar a ferramenta.

- `autorizar(nome_ferramenta: str, identidade: IdentidadeSessaoMCP) -> ResultadoAutorizacao` — Consulta pura de autorização da ferramenta para a identidade corrente.

### `ResultadoAutorizacao`

*DTO imutável* — Veredito imutável sobre a permissão de uso de uma ferramenta MCP.

**Campos:** `autorizado: bool`, `motivo: str`

- `permitido() -> 'ResultadoAutorizacao'` — Constrói o veredito positivo padrão.
- `negado(motivo: str) -> 'ResultadoAutorizacao'` — Constrói o veredito negativo com a justificativa exibida ao agente.

## `mcp/server.py`

Servidor de Protocolo MCP (Model Context Protocol) para interação com agentes.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_PAPEL_RECUSADO` | `str` | `'papel'` |

### `GraphowMCPServer`

*serviço* — Servidor MCP que disponibiliza ferramentas para agentes IA lerem e mutarem o grafo.

- `identidade() -> IdentidadeSessaoMCP` `[property]` — Identidade imutável sob a qual esta sessão opera.
- `listar_ferramentas() -> list[dict[str, Any]]` — Retorna os metadados de todas as ferramentas MCP disponíveis.
- `executar_ferramenta(nome_ferramenta: str, argumentos: Mapping[str, Any]) -> dict[str, Any]` — Executa a ferramenta MCP sob a identidade da sessão e retorna resposta estruturada.

## `mcp/stdio_protocolo.py`

Transporte e despacho do protocolo JSON-RPC 2.0 usado pelo servidor MCP stdio.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VERSAO_PROTOCOLO_MCP` | `str` | `'2024-11-05'` |
| `CODIGO_METODO_NAO_ENCONTRADO` | `int` | `-32601` |
| `METODOS_DE_NOTIFICACAO` | `frozenset[str]` | `frozenset({'notifications/initialized', 'notifications/cancelled'})` |

### `CanalJsonRpc` (ABC)

*contrato* — Contrato de entrada e saída de mensagens do protocolo JSON-RPC.

- `ler_linhas() -> Iterator[str]` `[abstract]` — Itera as linhas recebidas do cliente MCP.
- `escrever_mensagem(mensagem: Mapping[str, Any]) -> None` `[abstract]` — Emite uma mensagem JSON-RPC serializada para o cliente.
- `registrar_falha(mensagem: str) -> None` `[abstract]` — Registra uma falha de transporte fora do canal de respostas.

### `CanalJsonRpcEmMemoria` (CanalJsonRpc)

*serviço* — Transporte determinístico para testes, com linhas de entrada pré-definidas.

- `ler_linhas() -> Iterator[str]` — Itera as linhas fornecidas na construção.
- `escrever_mensagem(mensagem: Mapping[str, Any]) -> None` — Acumula a mensagem emitida para inspeção posterior.
- `registrar_falha(mensagem: str) -> None` — Acumula a falha registrada para inspeção posterior.
- `mensagens() -> tuple[dict[str, Any], ...]` `[property]` — Cópia imutável das mensagens emitidas.
- `falhas() -> tuple[str, ...]` `[property]` — Cópia imutável das falhas registradas.

### `CanalJsonRpcStdio` (CanalJsonRpc)

*serviço* — Transporte concreto sobre a entrada e a saída padrão do processo.

- `preparar_codificacao() -> None` — Força UTF-8 nos fluxos, pois o protocolo MCP não admite outra codificação.
- `ler_linhas() -> Iterator[str]` — Itera as linhas da entrada padrão até o fechamento do canal.
- `escrever_mensagem(mensagem: Mapping[str, Any]) -> None` — Serializa e emite a mensagem em uma única linha na saída padrão.
- `registrar_falha(mensagem: str) -> None` — Escreve a falha na saída de erro, sem poluir o canal do protocolo.

### `DespachanteJsonRpc`

*serviço* — Roteia requisições JSON-RPC para as capacidades do servidor MCP.

- `despachar(requisicao: Mapping[str, Any]) -> None` — Encaminha a requisição ao método correspondente do protocolo.

## `mcp/stdio_server.py`

Servidor MCP sobre transporte stdio com protocolo JSON-RPC 2.0.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_SUCESSO` | `int` | `0` |
| `CODIGO_FALHA_DOMINIO` | `int` | `1` |

### Funções do módulo

- `executar_loop_stdio(despachante: DespachanteJsonRpc, canal: CanalJsonRpc) -> None` — Loop principal de leitura de linhas JSON-RPC vindas do transporte.
- `iniciar_stdio_server(kernel: WriteKernel, identidade: IdentidadeSessaoMCP) -> None` — Executa o loop stdio do MCP sobre um kernel e uma identidade já resolvidos.
- `main(argumentos: Sequence[str] | None) -> int` — Ponto de entrada do módulo stdio MCP.

## `mcp/submissao.py`

Submissão de patches originados em ferramentas MCP sob a identidade da sessão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAMO_PADRAO` | `str` | `'main'` |

### `ContextoFerramentaMCP`

*DTO imutável* — Dependências compartilhadas por todas as ferramentas de uma sessão MCP.

**Campos:** `kernel: WriteKernel`, `identidade: IdentidadeSessaoMCP`

### `PedidoSubmissaoMCP`

*DTO imutável* — Descrição imutável de um lote de operações a submeter ao kernel.

**Campos:** `operacoes: tuple[ItemPatch, ...]`, `justificativa: str`, `ramo_id: str`, `identificadores_criados: dict[str, str]`

### `SubmissorPatchMCP`

*serviço* — Encaminha operações ao kernel usando sempre o papel fixado na sessão.

- `submeter(pedido: PedidoSubmissaoMCP) -> ResultadoSubmissao` — Constrói a proposta com a identidade da sessão e a envia aos portões.
- `submeter_e_relatar(pedido: PedidoSubmissaoMCP) -> dict[str, Any]` — Submete o lote e devolve a resposta padronizada da ferramenta MCP.

### Funções do módulo

- `extrair_ramo(argumentos: dict[str, Any]) -> str` — Lê o ramo alvo dos argumentos, com o ramo principal como padrão.

## `mcp/tool_definitions.py`

Definições formais de schemas para ferramentas MCP expostas a agentes LLM.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DEFINICOES_FERRAMENTAS_MCP` | `list[dict[str, Any]]` | `[{'name': 'ler_vista', 'description': 'Materializa uma vista de context…` |

