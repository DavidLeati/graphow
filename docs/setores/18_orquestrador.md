# Setor 18 — Orquestrador em Código

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.orquestrador`

O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

## Inventário

72 módulos · 13822 linhas · 105 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`orquestrador/aceite_intocado.py`](#orquestradoraceiteintocado) | 278 | Os testes de aceite rodam sempre da cópia intocada, sem arquivo solto do executor em `aceite/` nem configuração solta. |
| [`orquestrador/aceite_no_commit.py`](#orquestradoraceitenocommit) | 202 | O aceite que o orquestrador roda no commit verificado: com a configuração entregue e, se ela mudou, também com a do commit do aceite. |
| [`orquestrador/arquivos_do_git.py`](#orquestradorarquivosdogit) | 134 | Os arquivos que mudam o que o git do humano roda, lidos em bytes, sem processo nenhum. |
| [`orquestrador/atendimento_dos_pedidos.py`](#orquestradoratendimentodospedidos) | 67 | A conferência dos pedidos do humano contra o Goal como ele está, antes de gravá-los. |
| [`orquestrador/autor_de_aceite.py`](#orquestradorautordeaceite) | 189 | O passo do aceite: uma sessão do autor de aceite, os testes conferidos vermelhos, o commit e o registro. |
| [`orquestrador/base_que_andou.py`](#orquestradorbasequeandou) | 101 | A base que andou: antes de integrar, o orquestrador refaz a branch do Goal sobre a base nova e roda a suíte e o aceite. |
| [`orquestrador/briefing.py`](#orquestradorbriefing) | 392 | O briefing de cada sessão, montado por código a partir do livro-razão e do git. |
| [`orquestrador/cancelamento_tardio.py`](#orquestradorcancelamentotardio) | 76 | O cancelamento tardio: o humano cancela o Goal quando a base já tem o trabalho dele, e o livro-razão guarda isso. |
| [`orquestrador/comandos_do_stream.py`](#orquestradorcomandosdostream) | 115 | Os comandos que uma sessão rodou de fato, lidos do stream: o comando, o código de saída e um trecho do que imprimiu. |
| [`orquestrador/commit_do_pedido.py`](#orquestradorcommitdopedido) | 41 | O commit do pedido do humano: só os caminhos que o pedido escreveu, e nunca a área inteira. |
| [`orquestrador/conferencia_da_evidencia.py`](#orquestradorconferenciadaevidencia) | 114 | A conferência da Evidence sobre código na leitura: os arquivos que ela afirma mudaram desde o commit dela? |
| [`orquestrador/conferencia_do_humano.py`](#orquestradorconferenciadohumano) | 320 | A conferência do repositório do humano depois de cada sessão de papel: a perda para o laço, o avanço segue. |
| [`orquestrador/conferencia_na_leitura.py`](#orquestradorconferencianaleitura) | 221 | A conferência da Evidence na hora da leitura: o briefing, a vista, o canvas e o `--status` perguntam aqui. |
| [`orquestrador/configuracao_do_aceite.py`](#orquestradorconfiguracaodoaceite) | 204 | A segunda rodada do aceite: com a configuração de teste do commit do aceite, quando o executor a mudou. |
| [`orquestrador/contexto_do_laco.py`](#orquestradorcontextodolaco) | 197 | O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar. |
| [`orquestrador/correcoes.py`](#orquestradorcorrecoes) | 106 | As fatias de correção de um ciclo: os bloqueantes dele todos numa fatia só. |
| [`orquestrador/decisoes_do_agente.py`](#orquestradordecisoesdoagente) | 75 | O modo autônomo não tem humano no meio: o executor decide, e o teste de aceite errado se refaz sozinho, uma vez. |
| [`orquestrador/diff_das_correcoes.py`](#orquestradordiffdascorrecoes) | 85 | O diff das correções que vai à conferência: o resumo de todos os arquivos, o corpo do código primeiro e o aviso do corte. |
| [`orquestrador/documento_do_goal.py`](#orquestradordocumentodogoal) | 136 | O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências. |
| [`orquestrador/entrada_do_goal.py`](#orquestradorentradadogoal) | 144 | De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração. |
| [`orquestrador/esquemas.py`](#orquestradoresquemas) | 216 | Os schemas da saída de cada papel: o que o planejador, o autor de aceite, o executor e o verificador devolvem. |
| [`orquestrador/execucao_da_fatia.py`](#orquestradorexecucaodafatia) | 399 | O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro. |
| [`orquestrador/falhas_da_api.py`](#orquestradorfalhasdaapi) | 81 | O limite de uso da conta e o erro passageiro da API: não são falha do papel, nem da fatia. |
| [`orquestrador/fatia_de_conflito.py`](#orquestradorfatiadeconflito) | 316 | A fatia de conflito: no modo autônomo, o rebase que deu conflito, ou deixou vermelho a suíte ou o aceite, vira trabalho do executor. |
| [`orquestrador/foto_do_humano.py`](#orquestradorfotodohumano) | 215 | A foto do repositório do humano em volta de cada sessão de papel: a camada da trava que não lê o comando. |
| [`orquestrador/git_da_foto.py`](#orquestradorgitdafoto) | 42 | O git que a foto e a salvaguarda rodam no repositório do humano: sem fsmonitor, sem hooks e sem trava opcional. |
| [`orquestrador/git_do_goal.py`](#orquestradorgitdogoal) | 385 | O git do Goal: a área de trabalho numa branch própria e o commit de cada fatia. |
| [`orquestrador/git_no_comando.py`](#orquestradorgitnocomando) | 399 | A decisão da trava do git sobre um comando Bash do agente: só as leituras do git passam. |
| [`orquestrador/gravacao_da_verificacao.py`](#orquestradorgravacaodaverificacao) | 132 | A verificação gravada no livro-razão: a Evidence, um nó Achado por problema, o estado dos critérios e as pendências, num lote só. |
| [`orquestrador/gravacao_do_aceite.py`](#orquestradorgravacaodoaceite) | 104 | Os testes de aceite gravados no livro-razão: o commit como Artifact, a ligação de cada critério aos seus testes e o Goal. |
| [`orquestrador/gravacao_do_plano.py`](#orquestradorgravacaodoplano) | 134 | O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só. |
| [`orquestrador/historico_da_correcao.py`](#orquestradorhistoricodacorrecao) | 121 | O que a fatia de correção recebe além do achado: o comando que o reproduz e, quando a falha volta, a tentativa anterior. |
| [`orquestrador/hook_do_git.py`](#orquestradorhookdogit) | 61 | O hook PreToolUse da trava do git: o Claude Code o chama antes de cada comando Bash da sessão de agente. |
| [`orquestrador/laco.py`](#orquestradorlaco) | 338 | O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão. |
| [`orquestrador/leitura_das_verificacoes.py`](#orquestradorleituradasverificacoes) | 190 | As verificações do Goal e os nós Achado delas e das revisões de risco, como o laço os lê do livro-razão. |
| [`orquestrador/leitura_do_goal.py`](#orquestradorleituradogoal) | 399 | O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações. |
| [`orquestrador/leitura_do_shell.py`](#orquestradorleituradoshell) | 399 | A leitura de um comando Bash em comandos simples, para a trava do git decidir sobre cada um. |
| [`orquestrador/leituras_do_git.py`](#orquestradorleiturasdogit) | 184 | Quais invocações do git a trava deixa o agente rodar: só as leituras, com as opções que não gravam nem rodam nada. |
| [`orquestrador/livro_razao.py`](#orquestradorlivrorazao) | 367 | O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`. |
| [`orquestrador/modelo_do_goal.py`](#orquestradormodelodogoal) | 229 | Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço. |
| [`orquestrador/pedidos_do_humano.py`](#orquestradorpedidosdohumano) | 167 | Os pedidos do humano ao laço: cada saída que ele tem de um Goal parado, gravada como Decision dele. |
| [`orquestrador/planejamento.py`](#orquestradorplanejamento) | 155 | O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão. |
| [`orquestrador/rastro.py`](#orquestradorrastro) | 234 | O rastro de cada critério do Goal: o que o prova, o que o cobre, quem o atestou e o que o fere. |
| [`orquestrador/rebase_no_clone.py`](#orquestradorrebasenoclone) | 234 | O rebase da branch do Goal sobre a base que andou, feito pelo orquestrador no clone do Goal. |
| [`orquestrador/refazer_aceite.py`](#orquestradorrefazeraceite) | 262 | Refazer o aceite de um critério: o autor de aceite reescreve os testes dele, com o motivo do humano no briefing. |
| [`orquestrador/refs_do_humano.py`](#orquestradorrefsdohumano) | 73 | As refs do repositório do humano que o orquestrador move: a base, na integração, e a branch do Goal, depois do rebase. |
| [`orquestrador/registro_do_rebase.py`](#orquestradorregistrodorebase) | 168 | O rebase no livro-razão: a Evidence dele, a ponta nova, os commits novos das fatias e dos Artifact, e a retomada depois da queda. |
| [`orquestrador/regra_da_conferencia.py`](#orquestradorregradaconferencia) | 192 | A regra da conferência num ponto só: o que ela reprova e o código dá por `atende`, e a regressão que o código confirma. |
| [`orquestrador/replanejamento.py`](#orquestradorreplanejamento) | 91 | Recusar o plano: o humano recusa, com o motivo, e o planejador o refaz com o recusado e o motivo no briefing. |
| [`orquestrador/resultado_de_teste.py`](#orquestradorresultadodeteste) | 266 | O que a saída de um teste de aceite diz: passou de verdade, ou falhou pelo motivo certo. |
| [`orquestrador/retirada_de_criterio.py`](#orquestradorretiradadecriterio) | 107 | Retirar um critério: a única saída do humano para fechar o Goal com um critério que a verificação reprova. |
| [`orquestrador/revisao_da_fatia.py`](#orquestradorrevisaodafatia) | 192 | A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit. |
| [`orquestrador/saida_do_aceite.py`](#orquestradorsaidadoaceite) | 297 | A saída do autor de aceite e a conferência dela: a forma, o lugar dos testes e o vermelho de antes da implementação. |
| [`orquestrador/saida_do_verificador.py`](#orquestradorsaidadoverificador) | 391 | A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código. |
| [`orquestrador/saidas.py`](#orquestradorsaidas) | 254 | A saída de cada papel como objeto tipado, com a conferência que o schema não faz. |
| [`orquestrador/salvaguarda_do_humano.py`](#orquestradorsalvaguardadohumano) | 140 | A salvaguarda do repositório do humano, guardada fora dele: a recuperação sobrevive a um `git gc --prune=now`. |
| [`orquestrador/sed_e_awk.py`](#orquestradorsedeawk) | 45 | Quando o `sed` e o `awk` rodam comando: a trava os trata como texto que ela não lê (orquestrador/git_no_comando.py). |
| [`orquestrador/segunda_opiniao.py`](#orquestradorsegundaopiniao) | 86 | A segunda opinião sobre o achado que uma opinião só rebaixaria: rebaixá-lo a acompanhamento exige que dois concordem. |
| [`orquestrador/sessoes_de_papel.py`](#orquestradorsessoesdepapel) | 397 | A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria. |
| [`orquestrador/spec_do_goal.py`](#orquestradorspecdogoal) | 129 | A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro. |
| [`orquestrador/status.py`](#orquestradorstatus) | 136 | O `--status` do orquestrador: onde o Goal está, o que prova que ele está pronto, o que cada fatia fez e quanto custou. |
| [`orquestrador/suite.py`](#orquestradorsuite) | 169 | A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit. |
| [`orquestrador/suite_sem_rastro.py`](#orquestradorsuitesemrastro) | 65 | A suíte que o orquestrador roda não deixa rastro na área: o que ela escreve nunca entra num commit do laço. |
| [`orquestrador/tipo_da_verificacao.py`](#orquestradortipodaverificacao) | 271 | O tipo de cada verificação: a caçada uma vez, na primeira final; a do marco intermediário; a conferência depois de cada correção. |
| [`orquestrador/trava_do_git.py`](#orquestradortravadogit) | 307 | A trava do git nas sessões de agente: as regras, o ambiente e a restauração do clone depois de cada sessão. |
| [`orquestrador/trava_do_goal.py`](#orquestradortravadogoal) | 309 | Um orquestrador por Goal: a trava que impede duas execuções de `graphow orquestrar` no mesmo Goal. |
| [`orquestrador/validacao_json.py`](#orquestradorvalidacaojson) | 83 | Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam. |
| [`orquestrador/verificacao_do_goal.py`](#orquestradorverificacaodogoal) | 240 | O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal. |
| [`orquestrador/verificacao_do_marco.py`](#orquestradorverificacaodomarco) | 277 | A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão. |
| [`orquestrador/vermelho_do_rebase.py`](#orquestradorvermelhodorebase) | 71 | O que fica vermelho depois do rebase: a suíte do plano e os testes de aceite, na configuração entregue. |
| [`orquestrador/vermelho_do_refeito.py`](#orquestradorvermelhodorefeito) | 94 | O teste de aceite refeito só vale se falhar contra o código de antes da implementação. |

## `orquestrador/aceite_intocado.py`

Os testes de aceite rodam sempre da cópia intocada, sem arquivo solto do executor em `aceite/` nem configuração solta.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOMES_DE_CONFIGURACAO` | `frozenset[str]` | `frozenset({'conftest.py', 'pytest.ini', '.pytest.ini', 'pytest.toml', '…` |
| `PREFIXOS_DE_CONFIGURACAO` | `tuple[str, ...]` | `('jest.config.', 'vitest.config.', 'vitest.workspace.', 'babel.config.'…` |
| `SUFIXOS_DE_CONFIGURACAO` | `tuple[str, ...]` | `('.pth',)` |
| `SOMBRAS_DO_RUNNER` | `frozenset[str]` | `frozenset({'pytest.py', 'pytest', '_pytest.py', '_pytest', 'pluggy.py',…` |
| `SECOES_DE_TESTE` | `Mapping[str, tuple[str, ...]]` | `{'pyproject.toml': ('tool', 'pytest'), 'setup.cfg': ('tool:pytest',), '…` |
| `HOOKS_QUE_DECIDEM_O_RESULTADO` | `frozenset[str]` | `frozenset({'pytest_pyfunc_call', 'pytest_runtest_call', 'pytest_runtest…` |
| `PASTAS_DO_AMBIENTE` | `frozenset[str]` | `frozenset({'node_modules', '.venv', 'venv', '.tox', '.nox', '.git', 'si…` |

### Funções do módulo

- `e_configuracao_de_teste(caminho: str) -> bool` — O caminho, relativo à raiz, é de um arquivo que muda como os testes rodam (pelo nome).
- `configuracoes_mudadas(area: Path, caminhos: Iterable[str]) -> tuple[str, ...]` — Dos caminhos mudados desde o commit `antes`, os de configuração de teste (no pyproject e afins, só a parte de teste).
- `sombra_do_runner(caminho: str) -> str` — O trecho do caminho até o primeiro nome que sombreia o runner (`src/pytest.py`, `tests/unittest`); vazio sem ele.
- `tirar_sombras_do_runner(area: Path, caminhos: Iterable[str]) -> tuple[str, ...]` — As sombras do runner que não existiam no commit `antes`, entre os caminhos e os arquivos fora do git: saem do disco.
- `hooks_que_decidem_o_resultado(codigo: str) -> tuple[str, ...]` — Os hooks que decidem o resultado que o código define ou cita (def, atribuição, import, argumento, texto); nenhum se não compila.
- `conftests_que_decidem_o_resultado(area: Path, caminhos: Iterable[str]) -> dict[str, tuple[str, ...]]` — Os conftest.py novos ou mudados desde `antes` (o ignorado inclusive) que citam hook que decide o resultado, com os hooks.
- `soltos_que_mudam_os_testes(area: Path) -> tuple[str, ...]` — Os arquivos fora do git (não versionados ou ignorados) que estão em aceite/, que configuram os testes ou sombreiam o runner.
- `preparar_o_aceite(area: Path, commit_do_aceite: str) -> tuple[str, ...]` — Antes de rodar os testes de aceite: aceite/ como no commit do aceite e a configuração solta fora; diz o que tirou.
- `forcar_o_aceite_no_indice(area: Path) -> tuple[str, ...]` — Os arquivos de aceite/ que o .gitignore do projeto ignora entram no índice à força (`git add -f`); devolve quais.
- `flags_do_indice(area: Path) -> tuple[str, ...]` — Os arquivos com `skip-worktree` (S) ou `assume-unchanged` (letra minúscula) no índice: mudança que o status esconde.
- `limpar_flags(area: Path, arquivos: Sequence[str]) -> None` — Tira as flags do índice dos arquivos, para o git voltar a ver o que mudou neles.

## `orquestrador/aceite_no_commit.py`

O aceite que o orquestrador roda no commit verificado: com a configuração entregue e, se ela mudou, também com a do commit do aceite.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DO_MOTIVO` | `int` | `300` |
| `LIMITE_DE_CADA_SAIDA` | `int` | `900` |
| `DESTINO_DO_CODIGO` | `str` | `'achado_automatico'` |
| `DESTINO_DO_VERIFICADOR` | `str` | `'verificador'` |

### `AceiteNoCommit`

*DTO imutável* — As execuções do aceite com a configuração entregue e, quando ela mudou, com a do commit do aceite e o diff dela.

**Campos:** `execucoes: tuple[ExecucaoDeAceite, ...]`, `com_a_do_aceite: tuple[ExecucaoDeAceite, ...]`, `trocados: tuple[str, ...]`, `commit: str`, `diff: str`

- `diferencas() -> tuple[Par, ...]` — Cada teste que passou numa configuração e não na outra: (com a entregue, com a do aceite).
- `escondidas() -> tuple[Par, ...]` — Os que, com a configuração do aceite, falham numa asserção: a entregue esconde uma falha real.
- `a_julgar() -> tuple[Par, ...]` — Os que, com a configuração do aceite, falham por import, coleta ou ambiente: vão ao verificador.
- `chaves_a_julgar() -> tuple[tuple[str, str], ...]` — O critério e o teste de cada diferença que pede o parecer do verificador.
- `diferencas_em_json(pareceres: Sequence[ParecerDaDiferenca]) -> list[dict[str, Any]]` — As diferenças como a verificação as grava, com quem as julgou e o parecer do verificador, quando houve.
- `para_o_verificador() -> list[str]` — As diferenças que o verificador julga, com o fim das duas saídas, o commit do aceite e o diff do que mudou.
- `julgar(verificacao: Verificacao) -> Verificacao` — A verificação com o que as diferenças decidem: a falha escondida reprova o critério, e o `ilegitima` vira bloqueante.

### Funções do módulo

- `rodar_o_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, criterios: Sequence[str]) -> AceiteNoCommit` — O aceite dos critérios dados com a configuração entregue (na final, o de todos e a suíte junto) e, se ela mudou, com a do aceite.

## `orquestrador/arquivos_do_git.py`

Os arquivos que mudam o que o git do humano roda, lidos em bytes, sem processo nenhum.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AUSENTE` | `str` | `'ausente'` |
| `PASTA` | `str` | `'pasta'` |
| `LINK` | `str` | `'link '` |
| `ORIGEM_DE_ARQUIVO` | `str` | `'file'` |
| `CHAVE_DO_INCLUDE` | `str` | `'include.path'` |
| `PREFIXO_DO_INCLUDE_CONDICIONAL` | `str` | `'includeif.'` |
| `SUFIXO_DO_INCLUDE_CONDICIONAL` | `str` | `'.path'` |

### `ArquivosDoGit`

*DTO imutável* — O que a foto vigia no repositório do humano: os arquivos (existam ou não) e as pastas de hooks, lidas inteiras.

**Campos:** `repositorio: Path`, `pasta_do_git: Path`, `comum: Path`, `arquivos: tuple[Path, ...]`, `pastas: tuple[Path, ...]`

### Funções do módulo

- `arquivos_do_git(repositorio: Path, pasta_do_git: Path, comum: Path) -> ArquivosDoGit` — A lista da foto de antes: os arquivos fixos, os da configuração (origens e includes) e as pastas dos hooks.
- `ler_os_arquivos_do_git(vigia: ArquivosDoGit) -> dict[str, str]` — O sha256 de cada arquivo vigiado (`ausente` quando não existe) e de cada arquivo das pastas, pelo nome que a parada
- `conteudo_do_arquivo(caminho: Path) -> str` — O sha256 do conteúdo (do alvo, no link); `ausente` quando o arquivo não existe, `pasta` no submódulo.

## `orquestrador/atendimento_dos_pedidos.py`

A conferência dos pedidos do humano contra o Goal como ele está, antes de gravá-los.

### Funções do módulo

- `conferir_pedido(view: GrafoView, estado: EstadoDoGoal, pedido: NovoPedido) -> tuple[NovoPedido, Sequence[ItemPatch]]` — O pedido completo (o marco do `mais_ciclos`) e o que ele muda no mesmo lote; recusa o que não vale.

## `orquestrador/autor_de_aceite.py`

O passo do aceite: uma sessão do autor de aceite, os testes conferidos vermelhos, o commit e o registro.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RETOMADAS_DO_AUTOR` | `int` | `2` |

### Funções do módulo

- `escrever_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — Os testes de aceite já pagos, ou uma sessão do autor; commita e grava, ou diz por que não deu.
- `linhas_do_aceite(saida: SaidaDoAceite) -> list[str]` — A seção dos testes de aceite no documento do Goal: o comando e o que prova cada critério.

## `orquestrador/base_que_andou.py`

A base que andou: antes de integrar, o orquestrador refaz a branch do Goal sobre a base nova e roda a suíte e o aceite.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARQUIVOS_NA_MENSAGEM` | `int` | `20` |

### Funções do módulo

- `base_andou(contexto: ContextoDoGoal) -> bool` — A base do repositório do humano não está na história da branch do Goal: não há fast-forward.
- `rebasear_o_goal(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — O rebase da branch do Goal sobre a base nova, com a suíte; None quando o laço segue (registrado, ou com a fatia de conflito).
- `parada_do_conflito(contexto: ContextoDoGoal, conflito: ConflitoNoRebase, vermelho: Vermelho | None) -> Parada` — O rebase que não deu, no supervisionado: a branch do Goal ficou como estava, e a parada diz por quê e os arquivos.

## `orquestrador/briefing.py`

O briefing de cada sessão, montado por código a partir do livro-razão e do git.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DO_ERRO` | `int` | `6000` |

### `ContextoDaFatia`

*DTO imutável* — O que o git e o livro-razão dizem em volta da fatia que vai rodar.

**Campos:** `tentativa: int`, `entregues: tuple[str, ...]`, `diff_da_anterior: str`, `correcoes_anteriores: tuple[str, ...]`

### `PedidoDaConferencia`

*DTO imutável* — O que a conferência confere: os achados que as correções trataram, o commit de onde elas partiram e o diff delas.

**Campos:** `conferidos: Sequence[AchadoRegistrado]`, `antes: str`, `diff: str`, `diferencas: Sequence[str]`, `excedentes: Sequence[AchadoRegistrado]`, `conferencia_da_anterior: ConferenciaDaEvidencia | None`

### Funções do módulo

- `briefing_do_planejador(estado: EstadoDoGoal, spec: str, tem_fixados: bool) -> str` — O pedido ao planejador: a spec inteira e onde está o repositório.
- `briefing_do_executor(estado: EstadoDoGoal, fatia: FatiaRegistrada, contexto: ContextoDaFatia) -> str` — O pedido ao executor da fatia, com tudo o que a governa por extenso.
- `briefing_do_revisor(estado: EstadoDoGoal, fatia: FatiaRegistrada, mudados: Sequence[str]) -> str` — O pedido ao revisor da fatia de risco: a fatia, os critérios dela com os testes de aceite, as decisões, o que mudou e,
- `briefing_do_autor_de_aceite(estado: EstadoDoGoal) -> str` — O pedido ao autor de aceite: a spec, os critérios com o tipo de verificação, as decisões e a suíte.
- `briefing_do_verificador(estado: EstadoDoGoal, commit: str, entregues: Sequence[str]) -> str` — O pedido ao verificador do marco: spec, critérios que ele julga, decisões, suíte e o commit, sem nada de quem implementou.
- `briefing_da_conferencia(estado: EstadoDoGoal, commit: str) -> str` — O pedido curto da conferência: os critérios, os achados a reproduzir, os pareceres de antes e o diff das correções.
- `pedido_de_correcao_da_saida(problemas: Sequence[str]) -> str` — O que vai à mesma sessão quando a saída dela não conferiu.

## `orquestrador/cancelamento_tardio.py`

O cancelamento tardio: o humano cancela o Goal quando a base já tem o trabalho dele, e o livro-razão guarda isso.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ACAO_DO_CANCELAMENTO_TARDIO` | `str` | `'cancelamento_tardio'` |

### Funções do módulo

- `anotar_o_cancelamento_tardio(livro: LivroRazaoDoGoal, estado: EstadoDoGoal) -> Parada` — A Evidence e a nota no Goal de que a base já tinha o trabalho dele, até `integrado`, quando o cancelamento foi lido.
- `cancelamento_ja_integrado(livro: LivroRazaoDoGoal, estado: EstadoDoGoal) -> Parada | None` — No Goal cancelado, a nota que a queda logo depois do fast-forward não deixou gravar; None quando não há o que anotar.

## `orquestrador/comandos_do_stream.py`

Os comandos que uma sessão rodou de fato, lidos do stream: o comando, o código de saída e um trecho do que imprimiu.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FERRAMENTA_DO_SHELL` | `str` | `'Bash'` |
| `PROMPT_DO_SHELL` | `re.Pattern[str]` | `re.compile('^\\$\\s+')` |
| `CODIGO_DE_SAIDA` | `re.Pattern[str]` | `re.compile('^Exit code (-?\\d+)\\s*')` |
| `LIMITE_DO_TRECHO_DA_CHAMADA` | `int` | `600` |

### `ChamadaBash`

*DTO imutável* — Uma chamada da ferramenta Bash, como o stream a mostra: o comando, o código de saída e o fim do que ela imprimiu.

**Campos:** `comando: str`, `codigo: int`, `saida: str`

### Funções do módulo

- `comandos_bash(caminho: Path) -> tuple[str, ...]` — Os comandos de cada chamada da ferramenta Bash no stream, na ordem; vazio sem stream.
- `chamadas_bash(caminhos: Iterable[Path]) -> tuple[ChamadaBash, ...]` — Cada chamada Bash dos streams dados, na ordem, com o resultado que veio para ela.
- `comandos_nao_rodados(declarados: Iterable[str], resultados: Sequence[ResultadoDeSessao]) -> tuple[str, ...]` — Os comandos declarados que não aparecem em chamada Bash nenhuma das invocações dadas.
- `problema_dos_comandos(faltando: Sequence[str]) -> tuple[str, ...]` — O que volta à sessão quando ela declarou comando que não rodou.

## `orquestrador/commit_do_pedido.py`

O commit do pedido do humano: só os caminhos que o pedido escreveu, e nunca a área inteira.

### Funções do módulo

- `commitar_so(area: Path, mensagem: str, caminhos: Sequence[str]) -> str` — Só o que mudou nos caminhos dados, num commit do orquestrador; o resto da área fica fora dele. Devolve o hash.

## `orquestrador/conferencia_da_evidencia.py`

A conferência da Evidence sobre código na leitura: os arquivos que ela afirma mudaram desde o commit dela?

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VIGENTE` | `str` | `'vigente'` |
| `DESATUALIZADA` | `str` | `'desatualizada'` |
| `SEM_ANCORA` | `str` | `'sem_ancora'` |
| `CAMPO_ARVORE` | `str` | `'arvore'` |

### `ConferenciaDaEvidencia`

*DTO imutável* — O estado da Evidence na ponta, os arquivos dela que mudaram (na desatualizada) e o motivo, quando há.

**Campos:** `estado: str`, `arquivos: tuple[str, ...]`, `motivo: str`

- `vigente() -> bool` `[property]` — A Evidence vale como fato na ponta.

### Funções do módulo

- `conferir_evidencia(propriedades: Mapping[str, Any], git: GitDoGoal, ponta: str) -> ConferenciaDaEvidencia` — A Evidence conferida contra a ponta dada, no git dado (a área do Goal ou o repositório do humano).
- `sem_ancora(propriedades: Mapping[str, Any]) -> ConferenciaDaEvidencia` — A Evidence sem âncora válida, com o motivo: não precisa de git.
- `arquivos_mudados(git: GitDoGoal, antes: str, depois: str) -> tuple[str, ...]` — Os caminhos que mudaram entre as duas árvores, como o git os escreve, o renomeado pelas duas pontas.

## `orquestrador/conferencia_do_humano.py`

A conferência do repositório do humano depois de cada sessão de papel: a perda para o laço, o avanço segue.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MOTIVO_DA_PARADA` | `str` | `'repositorio_do_humano_mexido'` |
| `LIMITE_DE_MUDANCAS_NA_PARADA` | `int` | `20` |
| `NO_HEAD` | `str` | `'voltou ao conteudo do HEAD ou do indice de antes da sessao'` |
| `SUMIU` | `str` | `'sumiu da arvore sem ir a um commit'` |
| `SOBRESCRITO` | `str` | `'foi sobrescrito por um conteudo que o git ja tinha, e o de antes nao f…` |
| `NOVO` | `str` | `'mudou para um conteudo novo'` |
| `TROCADA` | `str` | `'foi trocada por um conteudo que o git ja tinha'` |

### `HumanoMexido`

*DTO imutável* — O que mudou no repositório do humano durante a sessão, separado em perda e avanço, e a salvaguarda de antes dela.

**Campos:** `repositorio: Path`, `perdas: tuple[str, ...]`, `avancos: tuple[str, ...]`, `salvaguarda: Salvaguarda`, `soltos_perdidos: tuple[str, ...]`, `git_mexido: bool`, `arvore_conferida: bool`, `cabeca_de_antes: str`

- `recuperar() -> tuple[str, ...]` `[property]` — Os comandos que devolvem o de antes da sessão: o `fetch` da pasta da salvaguarda, o `stash apply` do rastreado e o

### `RepositorioDoHumanoMexido` (GraphowError)

*serviço* — O repositório do humano perdeu trabalho durante a sessão de papel: o laço para em FALHA.

### `_Conferencia`

*DTO imutável* — As duas fotos e o que a conferência consulta no git do humano: a história e o objeto de cada caminho nos commits de

**Campos:** `antes: FotoDoHumano`, `depois: FotoDoHumano`, `e_ancestral: Callable[[str, str], bool]`, `objetos: Mapping[tuple[str, str], str]`

### Funções do módulo

- `resumo(mudancas: tuple[str, ...]) -> tuple[str, ...]` — As primeiras mudanças e quantas sobram.
- `conferir_o_humano(antes: FotoDoHumano | None, papel: str, fatia: str) -> None` — Depois da sessão, a foto refeita; o que mudou vai ao livro-razão, e a perda para o laço (`RepositorioDoHumanoMexido`).
- `conferir_os_arquivos_do_git(antes: FotoDoHumano) -> HumanoMexido | None` — Os arquivos que mudam o git, relidos em bytes, sem processo; None quando nenhum mudou. Mudou algum, a perda são eles,
- `conferir_as_fotos(antes: FotoDoHumano, depois: FotoDoHumano) -> HumanoMexido` — O que mudou de uma foto para a outra, separado em perda e avanço.
- `mensagem_da_parada(mexido: HumanoMexido, papel: str) -> str` — O motivo, a perda, a salvaguarda e os comandos que a recuperam.

## `orquestrador/conferencia_na_leitura.py`

A conferência da Evidence na hora da leitura: o briefing, a vista, o canvas e o `--status` perguntam aqui.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NAO_CONFERIDA` | `str` | `'nao_conferida'` |
| `PAPEL_DO_ORQUESTRADOR` | `str` | `PapelAutor.ORQUESTRADOR.value` |
| `MAXIMO_DE_ARQUIVOS_NO_ROTULO` | `int` | `8` |
| `ROTULOS` | `dict[str, str]` | `{VIGENTE: 'vigente', SEM_ANCORA: 'sem ancora', NAO_CONFERIDA: 'nao conf…` |

### `GitDaLeitura` (GitDoGoal)

*DTO imutável* — O git de uma leitura: cada consulta roda uma vez e fica guardada até a leitura acabar.

**Campos:** `memoria: dict[tuple[str, ...], SaidaDoGit]`

- `tentar() -> SaidaDoGit` — A consulta, do cache quando a leitura já a fez.

### `LeituraDaConferencia`

*serviço* — Uma leitura: o git em que a Evidence ancorada confere (ou nenhum) e a ponta.

- `com_git() -> bool` `[property]` — A leitura tem um repositório à mão para conferir a ancorada.
- `conferir(papel: str, propriedades: Mapping[str, Any]) -> ConferenciaDaEvidencia | None` — A conferência da Evidence gravada pelo papel; None quando ela não é sobre código nem tem âncora.

### `LeituraPorGoal`

*serviço* — A leitura da vista e do canvas: a Evidence do orquestrador confere na branch do Goal dela; as outras, sem git.

- `conferir(no: NoGrafo) -> ConferenciaDaEvidencia | None` — A conferência do nó Evidence; None para os outros tipos e para a Evidence livre.

### `MemoriaDasPontas`

*serviço* — O que o canvas guarda entre pedidos: por repositório e branch, a ponta conferida e as consultas ao git feitas nela.

- `da_ponta(pasta: str, ramo: str, ponta: str) -> dict[tuple[str, ...], SaidaDoGit]` — As consultas guardadas na ponta dada; vazias, e as da ponta anterior esquecidas, quando ela andou.

### Funções do módulo

- `leitura_do_repositorio(repositorio: object, ramo: object) -> LeituraDaConferencia` — A leitura no repositório, na ponta da branch (o hash); sem git quando a pasta não é repositório ou a branch não existe.
- `rotulo_da_conferencia(conferencia: ConferenciaDaEvidencia) -> str` — O rótulo curto: `vigente`, `desatualizada (mudaram: ...)`, `sem ancora` ou `nao conferida`.
- `marca_da_conferencia(conferencia: ConferenciaDaEvidencia) -> str` — O rótulo com o motivo, na sem âncora e na não conferida: a vista diz por quê, e não só o estado.
- `conferencia_em_json(conferencia: ConferenciaDaEvidencia | None) -> dict[str, Any] | None` — A conferência como o canvas a manda ao inspetor, com o rótulo; None quando não há o que mostrar.
- `aviso_de_historico(conferencia: ConferenciaDaEvidencia) -> str` — O aviso do briefing para a Evidence que não vale na ponta: o estado em maiúsculas e os arquivos, ou o motivo.

## `orquestrador/configuracao_do_aceite.py`

A segunda rodada do aceite: com a configuração de teste do commit do aceite, quando o executor a mudou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVES_DE_TESTE_DO_PACOTE` | `tuple[str, ...]` | `('jest', 'mocha', 'vitest', 'ava')` |
| `LIMITE_DO_DIFF_DA_CONFIGURACAO` | `int` | `4000` |
| `MARCA_DA_TROCA` | `str` | `'graphow-configuracao-do-aceite.json'` |
| `MISTOS` | `Mapping[str, Callable[[str, str], str]]` | `{'pyproject.toml': _com_as_tabelas_do_aceite(lambda nome: nome.startswi…` |

### Funções do módulo

- `configuracao_do_aceite(area: Path, commit_do_aceite: str) -> Iterator[tuple[str, ...]]` — Enquanto o bloco roda, a configuração de teste é a do commit do aceite; devolve o que trocou e, no fim, volta à ponta.
- `restaurar_a_configuracao_entregue(area: Path) -> tuple[str, ...]` — O que a rodada do aceite trocou e não desfez (o processo caiu no meio dela) volta à ponta; devolve o que voltou.
- `trocas_da_configuracao(area: Path, commit_do_aceite: str) -> dict[str, str | None]` — O conteúdo que cada arquivo de configuração de teste tem de ter durante o aceite (None: o arquivo sai).
- `diff_da_configuracao(area: Path, commit_do_aceite: str) -> str` — O diff, do commit do aceite à ponta, de cada arquivo que configura o teste (conftest, pyproject, pytest.ini, setup.cfg...).

## `orquestrador/contexto_do_laco.py`

O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MAXIMO_DE_FALHAS` | `int` | `2` |
| `MAXIMO_DE_CICLOS_DE_CORRECAO` | `int` | `m.MAXIMO_DE_CICLOS_DE_CORRECAO` |
| `ORCAMENTO_PADRAO_USD` | `float` | `30.0` |

### `ContextoDoGoal`

*DTO imutável* — Um Goal sendo conduzido: o livro-razão, a configuração gravada e as sessões dele.

**Campos:** `livro: LivroRazaoDoGoal`, `configuracao: m.ConfiguracaoDoGoal`, `sessoes: SessoesDePapel`, `telemetria: RepositorioTelemetria`, `pasta: Path`, `opcoes: OpcoesDoLaco`

- `id_goal() -> str` `[property]` — O Goal.
- `area() -> Path` `[property]` — O clone do Goal, onde as sessões trabalham.
- `area_do_goal() -> AreaDoGoal` `[property]` — O clone, o repositório do humano, a branch e a base, juntos.
- `commitar(mensagem: str) -> str` — O commit do orquestrador no clone (com `caminhos`, só deles), já levado à branch do Goal no repositório do humano.
- `commit_do_codigo() -> str` — O commit do código da área: o último que mudou algo além do documento do Goal.
- `registrar_ponta() -> None` — A ponta da branch do Goal no livro-razão, quando o git andou desde a última gravada.
- `git() -> GitDoGoal` `[property]` — O git da área.
- `banco_descartavel() -> Path` `[property]` — O banco que a suíte e os hooks das sessões recebem, para não escreverem no do usuário.
- `estado() -> EstadoDoGoal` — O estado do Goal relido do livro-razão.
- `patch(nome: str) -> Path` — Onde guardar o que uma tentativa deixou fora de commit.
- `gasto() -> float` — O custo conhecido das sessões do Goal até agora.
- `restante() -> float` — O que sobra do orçamento.
- `sem_orcamento() -> Parada | None` — A parada por orçamento, quando ele acabou; None quando ainda dá para abrir sessão.

### `DependenciasDoLaco`

*DTO imutável* — O que o laço usa e não decide: o grafo, as sessões, a telemetria e onde guardar o estado de cada Goal.

**Campos:** `kernel: WriteKernel`, `executor: ExecutorDeSessao`, `telemetria: RepositorioTelemetria`, `pasta_de_estado: Path`, `modelos: Mapping[str, str]`, `modo_de_permissao: str`, `tempo_limite_da_sessao_s: float`, `esperar: Callable[[float], None]`

### `GoalInexistente` (GraphowError)

*serviço* — O Goal pedido não está no livro-razão.

### `MotivoDaParada` (str, Enum)

*serviço* — Por que o laço devolveu a palavra.

### `OpcoesDoLaco`

*DTO imutável* — O que a chamada pede; None quer dizer "o que já está gravado no Goal, ou o padrão".

**Campos:** `modo: str | None`, `ramo: str`, `base: str`, `orcamento_usd: float | None`, `area: Path | None`, `tempo_limite_da_suite_s: float`, `adotar_ramo: bool`, `ciclos_de_correcao: int | None`

### `Parada`

*DTO imutável* — O laço parou: em que Goal, por quê e o que fazer para seguir.

**Campos:** `id_goal: str`, `motivo: MotivoDaParada`, `mensagem: str`

- `fechou() -> bool` `[property]` — O Goal fechou.

## `orquestrador/correcoes.py`

As fatias de correção de um ciclo: os bloqueantes dele todos numa fatia só.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MAXIMO_POR_FATIA` | `int` | `TETO_DE_BLOQUEANTES` |
| `CAMINHO_NO_LOCAL` | `re.Pattern[str]` | `re.compile('(?:[A-Za-z]:)?[\\w./\\\\-]*\\w\\.[A-Za-z][A-Za-z0-9]{0,7}\\…` |

### Funções do módulo

- `normalizar_caminho(caminho: str) -> str` — O caminho como o agrupamento o compara: barras para a frente, sem `./` no começo e, no Windows, sem caixa.
- `area_do_achado(achado: AchadoRegistrado) -> str` — A área em que o achado mora: o arquivo do local, o primeiro critério ou decisão que ele fere, ou ele mesmo.
- `agrupar_o_ciclo(achados: Iterable[AchadoRegistrado]) -> list[tuple[AchadoRegistrado, ...]]` — Os bloqueantes do ciclo numa fatia só, na ordem e sem repetir achado; acima de `MAXIMO_POR_FATIA`, em pedaços dele.
- `arquivos_do_local(local: str) -> list[str]` — Todos os arquivos que o local cita, na ordem, com a barra para a frente e sem `./`.
- `titulo_da_correcao(grupo: Sequence[AchadoRegistrado]) -> str` — O título da fatia: o primeiro achado, e quantos outros ela corrige junto.
- `propriedades_da_correcao(grupo: Sequence[AchadoRegistrado]) -> dict[str, Any]` — O objetivo, os critérios, os arquivos e os achados da fatia que corrige o grupo.

## `orquestrador/decisoes_do_agente.py`

O modo autônomo não tem humano no meio: o executor decide, e o teste de aceite errado se refaz sozinho, uma vez.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_TESTE_ERRADO` | `str` | `'teste_errado'` |
| `CAMPO_RESPOSTA_DO_AUTOR` | `str` | `'resposta_do_autor_de_aceite'` |
| `CAMPO_DESACORDO` | `str` | `'desacordo_sobre_o_teste'` |
| `CAMPO_CRITERIOS_REFEITOS` | `str` | `'criterios_refeitos_pelo_agente'` |
| `CAMPO_REFEITO_SEM_VERMELHO` | `str` | `'refeito_sem_vermelho'` |
| `PREFIXO_DO_PEDIDO_AUTOMATICO` | `str` | `'auto-'` |

### Funções do módulo

- `operacoes_das_decisoes(livro: LivroRazaoDoGoal, id_task: str, tentativa: int) -> list[ItemPatch]` — Cada decisão do executor como Decision marcada como do agente, que orienta a fatia.
- `linhas_das_decisoes(decisoes: Sequence[DecisaoDoAgente], novas: Sequence[Mapping[str, Any]]) -> list[str]` — As decisões do agente para o documento: a fatia pelo código dela (F1), a questão, a decisão e o motivo.
- `documentar_decisoes(contexto: ContextoDoGoal, fatia: FatiaRegistrada, novas: Sequence[Mapping[str, Any]]) -> None` — A seção das decisões do agente no documento do Goal, com as novas, para entrar no commit da fatia.

## `orquestrador/diff_das_correcoes.py`

O diff das correções que vai à conferência: o resumo de todos os arquivos, o corpo do código primeiro e o aviso do corte.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DO_CORPO` | `int` | `8000` |
| `RESUMO_SEM_ABREVIAR` | `tuple[str, ...]` | `('--stat=1000,900', '--stat-graph-width=20')` |
| `PASTAS_DE_TESTE` | `frozenset[str]` | `frozenset({'tests', 'test', '__tests__', 'spec'})` |
| `NOME_DE_TESTE` | `re.Pattern[str]` | `re.compile('^test_|[._-](test|spec)\\.[^.]+$')` |

### `CorpoDoDiff`

*DTO imutável* — O corpo que coube no limite, o arquivo cortado no meio e os que ficaram de fora.

**Campos:** `texto: str`, `cortado: str`, `fora: tuple[str, ...]`

### Funções do módulo

- `diff_das_correcoes(git: GitDoGoal, antes: str, slug: str) -> str` — O resumo e o corpo do diff do commit da verificação anterior até o atual, sem o documento do Goal; vazio sem o commit de antes.
- `prioridade_no_diff(caminho: str) -> int` — A ordem do arquivo no corpo: `src/`, os testes (os de `aceite/` inclusive), o resto e, por último, `docs/` e o README.

## `orquestrador/documento_do_goal.py`

O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DOS_DOCUMENTOS` | `str` | `'docs/goals'` |
| `TITULO_DAS_PENDENCIAS` | `str` | `'## Pendencias'` |
| `TITULO_DO_ACEITE` | `str` | `'## Testes de aceite'` |
| `TITULO_DOS_RETIRADOS` | `str` | `'## Criterios retirados pelo humano'` |
| `TITULO_DAS_DECISOES_DO_AGENTE` | `str` | `'## Decisoes do agente (para o humano revisar)'` |

### Funções do módulo

- `caminho_do_documento(slug: str) -> str` — O caminho do documento do Goal, relativo à raiz do repositório.
- `renderizar_documento(id_goal: str, configuracao: m.ConfiguracaoDoGoal, plano: Plano) -> str` — O documento do Goal recém-planejado, sem pendências ainda.
- `com_aceite(documento: str, linhas: Sequence[str]) -> str` — O documento com a seção dos testes de aceite logo antes das pendências (reescrita, se já havia).
- `com_retirados(documento: str, linhas: Sequence[str]) -> str` — O documento com a seção dos critérios retirados pelo humano logo antes das pendências (reescrita, se já havia).
- `com_secao(documento: str, titulo: str, linhas: Sequence[str]) -> str` — O documento com a seção dada (reescrita, se já havia) logo antes das pendências, e as outras seções como estavam.
- `com_pendencias(documento: str, pendencias: Sequence[Mapping[str, Any]]) -> str` — O documento com a seção de pendências reescrita.
- `normalizar_quebras(texto: str) -> str` — O texto com toda quebra de linha (CRLF, CR) como LF.
- `gravar_se_mudou(caminho: Path, conteudo: str) -> bool` — Grava o texto com as quebras normalizadas, só quando ele difere do que está no arquivo; diz se gravou.
- `escrever_documento(area: Path, slug: str, conteudo: str) -> Path` — Grava o documento na área do Goal, se ele mudou, e devolve o caminho.

## `orquestrador/entrada_do_goal.py`

De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PREFIXO_GENERICO_DA_SPEC` | `str` | `'spec-'` |
| `SUFIXOS_POSSIVEIS` | `int` | `100` |

### `GoalDaSpec`

*DTO imutável* — O Goal que a spec retoma ou cria: o id, o slug (com o sufixo) e se ele já existe.

**Campos:** `id_goal: str`, `slug: str`, `existe: bool`

### `PedidoDeConfiguracao`

*DTO imutável* — O que a configuração de um Goal novo precisa: o Goal, o repositório, a chamada e onde fica o estado.

**Campos:** `id_goal: str`, `slug: str`, `raiz: Path`, `opcoes: OpcoesDoLaco`, `pasta_de_estado: Path`

### `PedidoInvalido` (GraphowError)

*serviço* — O que a chamada pediu não dá para conduzir.

### Funções do módulo

- `goal_da_spec(view: GrafoView, spec: Path, texto: str) -> GoalDaSpec` — O Goal aberto que a mesma spec criou no mesmo repositório, ou o primeiro id livre para um novo.
- `slug_da_spec(spec: Path, raiz: Path) -> str` — O nome da spec sem o prefixo `spec-`; a spec de nome genérico leva o nome do repositório.
- `configuracao_nova(pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal` — A configuração do Goal novo, com os padrões do que a chamada não disse, conferida.
- `adotar_goal(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal` — O Goal do gerente passa a ser conduzido: a spec montada dos nós e a configuração da chamada.
- `pedido_de_adocao(estado: EstadoDoGoal, opcoes: OpcoesDoLaco) -> PedidoDeConfiguracao` — O pedido de configuração do Goal do gerente, que pede o repositório na primeira vez.
- `atualizar_configuracao(livro: LivroRazaoDoGoal, configuracao: m.ConfiguracaoDoGoal, opcoes: OpcoesDoLaco) -> m.ConfiguracaoDoGoal` — O modo, o orçamento e os ciclos de correção que a chamada pede de novo valem daqui em diante, e ficam gravados.

## `orquestrador/esquemas.py`

Os schemas da saída de cada papel: o que o planejador, o autor de aceite, o executor e o verificador devolvem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PAPEL_PLANEJADOR` | `str` | `'planejador'` |
| `PAPEL_AUTOR_DE_ACEITE` | `str` | `'aceite'` |
| `PAPEL_EXECUTOR` | `str` | `'executor'` |
| `PAPEL_REVISOR` | `str` | `'revisor'` |
| `PAPEL_VERIFICADOR` | `str` | `'verificador'` |
| `PAPEL_VERIFICADOR_DO_MARCO` | `str` | `'marco'` |
| `PAPEL_CONFERENCIA` | `str` | `'conferencia'` |
| `PAPEL_SEGUNDA_OPINIAO` | `str` | `'segunda_opiniao'` |
| `PAPEIS` | `tuple[str, ...]` | `(PAPEL_PLANEJADOR, PAPEL_AUTOR_DE_ACEITE, PAPEL_EXECUTOR, PAPEL_REVISOR…` |
| `PASTA_DOS_PROMPTS` | `Path` | `Path(__file__).parent / 'prompts'` |
| `LIMITE_DO_PROMPT_BYTES` | `int` | `5 * 1024` |
| `VERIFICACOES_DE_CRITERIO` | `tuple[str, ...]` | `a.VERIFICACOES_DE_CRITERIO` |
| `MODELOS_SUGERIDOS` | `tuple[str, ...]` | `('opus', 'sonnet', 'haiku')` |
| `STATUS_DO_EXECUTOR` | `tuple[str, ...]` | `('pronto', 'duvida', 'falhou')` |
| `STATUS_DO_EXECUTOR_AUTONOMO` | `tuple[str, ...]` | `('pronto', 'teste_errado', 'falhou')` |
| `VEREDITOS_DE_CRITERIO` | `tuple[str, ...]` | `a.VEREDITOS_DE_CRITERIO` |
| `SEVERIDADES` | `tuple[str, ...]` | `('alta', 'media', 'baixa')` |
| `TAMANHO_MINIMO_DA_PROVA` | `int` | `10` |
| `TEXTO` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': 1}` |
| `PROVA` | `Mapping[str, Any]` | `{'type': 'string', 'minLength': TAMANHO_MINIMO_DA_PROVA}` |
| `TEXTO_LIVRE` | `Mapping[str, Any]` | `{'type': 'string'}` |
| `LISTA_DE_TEXTOS` | `Mapping[str, Any]` | `{'type': 'array', 'items': {'type': 'string'}}` |
| `CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'verificacao': {'type': 'string',…` |
| `DECISAO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'texto': TEXTO, 'motivo': TEXTO})` |
| `FATIA` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'objetivo': TEXTO, 'criterios': …` |
| `MARCO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'titulo': TEXTO, 'fatias': LISTA_DE_TEXTOS})` |
| `ESQUEMA_DO_PLANO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'comando_suite': TEXTO, 'criterios': _lista_d…` |
| `TESTE_DE_ACEITE` | `dict[str, Any]` | `_objeto({'arquivo': TEXTO, 'nome': TEXTO, 'comando': TEXTO}, opcionais=…` |
| `ACEITE_DO_CRITERIO` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'testes': _lista_de(TESTE_DE_ACEITE), 'checagem':…` |
| `ESQUEMA_DO_ACEITE` | `dict[str, Any]` | `_objeto({'resumo': TEXTO, 'comando_aceite': TEXTO, 'comando_do_teste': …` |
| `PROBLEMA_DA_REVISAO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'descricao': TEXTO, 'prova': PROVA, 'local': …` |
| `ESQUEMA_DA_REVISAO` | `dict[str, Any]` | `_objeto({'veredito': {'type': 'string', 'enum': ['aprovado', 'rejeitado…` |
| `DECISAO_DO_AGENTE` | `dict[str, Any]` | `_objeto({'questao': TEXTO, 'decisao': TEXTO, 'motivo': TEXTO})` |
| `ESQUEMA_DA_EXECUCAO` | `dict[str, Any]` | `_objeto({'status': {'type': 'string', 'enum': list(STATUS_DO_EXECUTOR)}…` |
| `ESQUEMA_DA_EXECUCAO_AUTONOMA` | `dict[str, Any]` | `{**ESQUEMA_DA_EXECUCAO, 'properties': {**ESQUEMA_DA_EXECUCAO['propertie…` |
| `PARECER` | `dict[str, Any]` | `_objeto({'id': TEXTO, 'veredito': {'type': 'string', 'enum': list(VERED…` |
| `ALCANCE` | `Mapping[str, Any]` | `{'type': 'string', 'enum': list(ALCANCES)}` |
| `ACHADO` | `dict[str, Any]` | `_objeto({'titulo': TEXTO, 'descricao': TEXTO, 'prova': PROVA, 'local': …` |
| `PARECER_DA_DIFERENCA` | `dict[str, Any]` | `_objeto({'criterio': TEXTO_LIVRE, 'teste': TEXTO, 'parecer': {'type': '…` |
| `ACHADO_DA_CONFERENCIA` | `dict[str, Any]` | `_objeto({**ACHADO['properties'], 'persiste': TEXTO_LIVRE, 'regressao': …` |
| `PARECER_DO_CONFERIDO` | `dict[str, Any]` | `_objeto({'achado': TEXTO, 'parecer': {'type': 'string', 'enum': list(PA…` |
| `ESQUEMA_DA_VERIFICACAO` | `dict[str, Any]` | `_esquema_da_verificacao(ACHADO)` |
| `ESQUEMA_DA_CONFERENCIA` | `dict[str, Any]` | `_esquema_da_verificacao(ACHADO_DA_CONFERENCIA, {'conferidos': _lista_de…` |
| `ESQUEMA_DA_SEGUNDA_OPINIAO` | `dict[str, Any]` | `_objeto({'criterios': LISTA_DE_TEXTOS, 'decisoes': LISTA_DE_TEXTOS, 'al…` |
| `ESQUEMA_POR_PAPEL` | `Mapping[str, Mapping[str, Any]]` | `{PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO, PAPEL_AUTOR_DE_ACEITE: ESQUEMA_DO_…` |

### Funções do módulo

- `caminho_do_prompt(papel: str) -> Path` — O prompt de sistema do papel, no pacote.

## `orquestrador/execucao_da_fatia.py`

O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_PRONTO` | `str` | `'pronto'` |
| `STATUS_DUVIDA` | `str` | `'duvida'` |
| `STATUS_TESTE_ERRADO` | `str` | `'teste_errado'` |
| `MODELO_DA_CORRECAO` | `str` | `'opus'` |

### `Tentativa`

*DTO imutável* — Uma tentativa em curso: a fatia, o número e a referência (o commit de onde partiu; na de conflito, a árvore mesclada).

**Campos:** `fatia: FatiaRegistrada`, `numero: int`, `referencia: str`

### Funções do módulo

- `executar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> Parada | None` — Roda uma tentativa da fatia; a parada diz por que o laço não segue.
- `guardar_a_fatia_interrompida(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> EstadoDoGoal` — Antes do pedido do humano, a fatia que caiu no meio da sessão é tratada como na retomada; devolve o estado relido.

## `orquestrador/falhas_da_api.py`

O limite de uso da conta e o erro passageiro da API: não são falha do papel, nem da fatia.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ERRO_DO_LIMITE_DE_USO` | `str` | `'usage_limit_reached'` |
| `RAZAO_DO_ERRO_DA_API` | `str` | `'api_error'` |
| `STATUS_DO_LIMITE_DE_TAXA` | `int` | `429` |
| `STATUS_DO_ERRO_DO_SERVIDOR` | `int` | `500` |
| `STATUS_DA_SOBRECARGA` | `int` | `529` |
| `ERRO_DA_SOBRECARGA` | `str` | `'overloaded_error'` |

### `FalhaDaApi`

*DTO imutável* — O que a API disse: se é o limite de uso da conta, o que foi e quando a janela volta.

**Campos:** `limite_de_uso: bool`, `descricao: str`, `volta_em: str`

### `LimiteDaApi` (GraphowError)

*serviço* — A API recusou a sessão (o limite de uso, ou o erro que não passou com as esperas): o laço para, retomável.

### Funções do módulo

- `falha_da_api(resultado: ResultadoDeSessao) -> FalhaDaApi | None` — A falha da API que o stream da invocação mostra; None quando a sessão não esbarrou nela, ou esbarrou e terminou bem.
- `recusa(falha: FalhaDaApi, papel: str) -> LimiteDaApi` — A exceção que para o laço, com o que a API disse e quando retomar.

## `orquestrador/fatia_de_conflito.py`

A fatia de conflito: no modo autônomo, o rebase que deu conflito, ou deixou vermelho a suíte ou o aceite, vira trabalho do executor.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_CONFLITO` | `str` | `'conflito_com_a_base'` |
| `LIMITE_DO_DIFF` | `int` | `6000` |
| `MODELO_DO_CONFLITO` | `str` | `'opus'` |
| `COMO_RESOLVER` | `str` | `'Nesta fatia, a area traz o trabalho do Goal com a base nova mesclada, …` |
| `COMO_MANTER_A_BASE` | `str` | `'O orquestrador recusa a tentativa: mantenha cada linha que a base pos …` |
| `PERGUNTA_DA_BASE` | `str` | `'Pergunta desta revisao: o resultado anula o que a base trouxe? O orque…` |

### Funções do módulo

- `abrir_fatia_de_conflito(contexto: ContextoDoGoal, estado: EstadoDoGoal, conflito: ConflitoNoRebase) -> str` — A fatia do marco final que resolve o conflito com a base nova; devolve o id da Task.
- `referencia_da_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str` — Contra o que a tentativa se compara: o HEAD; na fatia de conflito, a árvore da ponta do Goal com a base nova mesclada.
- `preparar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str` — A referência da tentativa; na fatia de conflito, a área e o índice a recebem, fora de commit, com o HEAD onde estava.
- `desfaz_a_base(contexto: ContextoDoGoal, fatia: FatiaRegistrada, mudados: Sequence[str]) -> str` — Na fatia de conflito, o erro da área que desfaz o que a base nova trouxe; vazio quando a mudança da base continua nela.
- `base_para_o_revisor(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str` — Na fatia aberta pelo rebase, a seção do briefing do revisor com o diff da base nova e a pergunta se o resultado o
- `aceite_da_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> str` — Na fatia de conflito, os testes de aceite na área resolvida: o erro do vermelho, ou vazio; nas outras fatias, vazio.
- `commitar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada, mensagem: str) -> str` — O commit da fatia; o da de conflito, da árvore que a conferência julgou sobre a referência, vai sobre a base nova e é

## `orquestrador/foto_do_humano.py`

A foto do repositório do humano em volta de cada sessão de papel: a camada da trava que não lê o comando.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPOS_ANTES_DO_CAMINHO` | `Mapping[str, int]` | `{'1': 8, '2': 9, 'u': 10, '?': 1}` |
| `CABECALHO_DO_STATUS` | `str` | `'# branch.'` |
| `NAO_RASTREADO` | `str` | `'?'` |
| `OBJETO_DO_GIT` | `re.Pattern[str]` | `re.compile('[0-9a-f]{40}|[0-9a-f]{64}')` |

### `ArquivoListado`

*DTO imutável* — Um arquivo que o status lista: o tipo do registro (1, 2, u ou ?), o XY e, no rastreado, o modo e o objeto no HEAD

**Campos:** `tipo: str`, `xy: str`, `modo_no_head: str`, `no_head: str`, `no_indice: str`

- `entrada_do_head() -> str` `[property]` — A entrada do índice igual à do HEAD (`modo objeto 0`), a que o `reset` ou o `checkout HEAD` devolvem.

### `FotoDoHumano`

*DTO imutável* — O repositório do humano num instante.

**Campos:** `repositorio: Path`, `cabeca: str`, `refs: Mapping[str, str]`, `indice: Mapping[str, tuple[str, ...]]`, `listados: Mapping[str, ArquivoListado]`, `conteudos: Mapping[str, str]`, `do_git: Mapping[str, str]`, `vigia: ArquivosDoGit`, `objetos: Mapping[str, str]`, `salvaguarda: Salvaguarda`

### Funções do módulo

- `foto_antes_da_sessao(repositorio: Path | None) -> FotoDoHumano | None` — A foto de antes da sessão e, com a pasta dada, a salvaguarda nela; None sem repositório do humano a guardar.
- `fotografar_o_humano(repositorio: Path, tambem: Iterable[str]) -> FotoDoHumano` — Os arquivos do git (da lista dada, ou da tirada agora da configuração), o HEAD, o status, as refs e o índice, com o
- `soltos_da_salvaguarda(foto: FotoDoHumano) -> tuple[str, ...]` — Os não rastreados que a árvore da salvaguarda guarda: o arquivo comum (o link e a pasta ficam de fora).
- `objetos_nos_commits(repositorio: Path, pedidos: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]` — O objeto de cada caminho em cada commit pedido (`<commit>:<caminho>`, num `cat-file --batch-check`); o caminho que

## `orquestrador/git_da_foto.py`

O git que a foto e a salvaguarda rodam no repositório do humano: sem fsmonitor, sem hooks e sem trava opcional.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_TRAVA_OPCIONAL` | `str` | `'--no-optional-locks'` |
| `SEM_FSMONITOR` | `tuple[str, ...]` | `('-c', 'core.fsmonitor=false')` |
| `CHAVE_DOS_HOOKS` | `str` | `'core.hooksPath'` |
| `VARIAVEIS_DA_FOTO` | `frozenset[str]` | `VARIAVEIS_DE_OUTRO_REPOSITORIO | {'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNAT…` |

### Funções do módulo

- `git_da_foto(pasta: Path, argumentos: Sequence[str]) -> str | None` — O git na pasta, sem fsmonitor nem hooks e sem trava opcional; a saída padrão, ou None quando ele falha.
- `e_ancestral_no_humano(repositorio: Path, antes: str, depois: str) -> bool` — `antes` está na história de `depois` (ou é ele), pelo git da foto.

## `orquestrador/git_do_goal.py`

O git do Goal: a área de trabalho numa branch própria e o commit de cada fatia.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXECUTAVEL_DO_GIT` | `str` | `'git'` |
| `VARIAVEIS_DE_OUTRO_REPOSITORIO` | `frozenset[str]` | `frozenset({'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'})` |
| `TRAILER_DO_GOAL` | `str` | `'Graphow-Goal'` |
| `TRAILER_DA_TASK` | `str` | `'Graphow-Task'` |
| `TRAILER_DO_ACEITE` | `str` | `'Graphow-Aceite'` |
| `ACEITE_VERMELHO` | `str` | `'vermelho'` |
| `CHAVES_COPIADAS_PARA_O_CLONE` | `tuple[str, ...]` | `('user.name', 'user.email', 'core.autocrlf', 'core.eol', 'core.safecrlf…` |
| `REMOTO_DO_CLONE` | `str` | `'origin'` |
| `IDENTIDADE_DE_RESERVA` | `tuple[str, ...]` | `('-c', 'user.name=graphow orquestrar', '-c', 'user.email=orquestrador@g…` |
| `LIMITE_DO_RESUMO_DO_DIFF` | `int` | `4000` |
| `SEM_ASPAS` | `tuple[str, ...]` | `('-c', 'core.quotepath=false')` |

### `AreaDoGoal`

*DTO imutável* — Onde o trabalho do Goal acontece: o repositório do humano, o clone do Goal, a branch e a base.

**Campos:** `repositorio: Path`, `pasta: Path`, `ramo: str`, `base: str`

### `CommitDoGit`

*DTO imutável* — Um commit da branch: o hash, a mensagem inteira e as linhas que o git leu como trailers dela.

**Campos:** `hash: str`, `mensagem: str`, `trailers: tuple[str, ...]`

- `tem_trailer(chave: str, valor: str) -> bool` — O git leu o trailer `chave: valor` no fim da mensagem (a chave sem caixa, como no git); a linha do corpo não conta.
- `valor_do_trailer(chave: str) -> str` — O valor do último trailer `chave` (a chave sem caixa); vazio sem ele.

### `FalhaDoGitDoGoal` (GraphowError)

*serviço* — O git recusou o que o orquestrador pediu; o contexto traz o comando e a saída de erro.

### `GitDoGoal`

*DTO imutável* — Roda o git numa pasta (o repositório do humano ou a área do Goal), sem a trava do agente.

**Campos:** `pasta: Path`

- `tentar() -> SaidaDoGit` — O comando, sem recusar quando o git sai com erro.
- `bytes_de() -> bytes` — A saída padrão em bytes, sem decodificar; recusa quando o git falha.
- `rodar() -> str` — A saída padrão; recusa com a saída de erro quando o git falha.
- `head() -> str` — O commit em que a pasta está.
- `ramo_atual() -> str` — A branch do HEAD; vazio com o HEAD destacado.
- `ramo_existe(ramo: str) -> bool` — A branch local existe.
- `mudancas() -> tuple[str, ...]` — As linhas do `status --porcelain` (só dos caminhos, quando dados): o que está fora de commit, ignorados de fora.
- `caminhos_mudados() -> tuple[str, ...]` — Cada arquivo criado, mudado, apagado ou renomeado fora de commit (as duas pontas do renomeado), um por um.
- `e_ancestral(antes: str, depois: str) -> bool` — `antes` está na história de `depois` (ou é ele).
- `resumo_do_diff(antes: str, depois: str) -> str` — O `diff --stat` entre os dois commits, cortado para caber no briefing.
- `commit_do_codigo(documento: str) -> str` — O último commit, a partir do HEAD, que mudou algo além do documento dado; o HEAD quando não há.
- `commits_desde(base: str) -> tuple[str, ...]` — Hash curto e assunto de cada commit da branch desde a base, do mais antigo ao mais novo.

### `SaidaDoGit`

*DTO imutável* — O código de saída e as duas saídas de um comando do git.

**Campos:** `codigo: int`, `saida: str`, `erro: str`

### Funções do módulo

- `raiz_do_repositorio(pasta: Path) -> Path` — A raiz do repositório git que contém a pasta.
- `preparar_area(area: AreaDoGoal) -> None` — O clone do Goal na branch dele, e a branch do Goal no repositório do humano no commit do clone.
- `limpar_rastros_do_clone(pasta: Path) -> None` — Tira do clone o reflog (que diz de onde ele veio) e os hooks: nada ali roda nos commits do orquestrador.
- `sincronizar_ramo(area: AreaDoGoal) -> None` — A branch do Goal no repositório do humano vai ao commit do clone, puxada dele, só por fast-forward.
- `mensagem_do_orquestrador(assunto: str, corpo: str) -> str` — A mensagem do commit com os trailers do Goal, da Task (na fatia e no aceite) e do aceite vermelho, quando pedido.
- `commitar(area: Path, mensagem: str) -> str` — Tudo o que mudou na área num commit do orquestrador; devolve o hash.
- `commits_entre(area: Path, antes: str, depois: str) -> tuple[CommitDoGit, ...]` — Os commits de `antes..depois`, do mais novo ao mais antigo, com a mensagem e os trailers que o git leu nela.
- `commit_da_fatia(area: Path, id_task: str, base: str) -> CommitDoGit | None` — O commit mais novo da branch, desde a base, que o orquestrador fez para a fatia; None sem nenhum.
- `arquivos_do_commit(area: Path, hash_do_commit: str) -> tuple[str, ...]` — Os arquivos que o commit mudou, sem as aspas e os octais com que o git cita o nome com acento.
- `ultimo_commit_do_arquivo(area: Path, caminho: str) -> str` — O commit mais novo que tocou o arquivo; o HEAD quando nenhum tocou.
- `guardar_patch(area: Path, arquivo_patch: Path) -> None` — O que está fora de commit, os arquivos novos inclusive, num .patch binário, byte a byte; a área fica como está, no índice.
- `descartar_mudancas(area: Path, arquivo_patch: Path) -> bool` — Guarda o que está fora de commit num .patch e volta a área ao HEAD; diz se havia o que guardar.
- `restaurar_head(area: Path, ramo: str, esperado: str) -> str` — Desfaz o que o agente fez no git: volta à branch e, com `reset --soft`, ao commit esperado.
- `remover_area(area: Path) -> bool` — Apaga o clone do Goal depois da integração; a branch fica no repositório do humano. Diz se conseguiu.

## `orquestrador/git_no_comando.py`

A decisão da trava do git sobre um comando Bash do agente: só as leituras do git passam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PROGRAMAS_DO_GIT` | `frozenset[str]` | `frozenset({'git'})` |
| `SHELLS` | `frozenset[str]` | `frozenset({'bash', 'sh', 'zsh', 'dash', 'ksh', 'ash', 'mksh', 'fish'})` |
| `EXECUTORES` | `frozenset[str]` | `frozenset({'env', 'exec', 'nohup', 'time', 'nice', 'timeout', 'sudo', '…` |
| `EXECUTORES_PELO_SHELL` | `frozenset[str]` | `frozenset({'watch', 'flock', 'parallel'})` |
| `PROGRAMAS_COMUNS` | `frozenset[str]` | `frozenset({'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack', 'cat', 'head', …` |
| `SUFIXOS_DE_EXECUTAVEL` | `tuple[str, ...]` | `('.exe', '.cmd', '.bat', '.com')` |
| `OPCOES_DO_SHELL_COM_VALOR` | `frozenset[str]` | `frozenset({'-o', '+o', '-O', '+O', '--rcfile', '--init-file'})` |
| `FIM_DO_EXEC_DO_FIND` | `frozenset[str]` | `frozenset({';', '+'})` |
| `DA_ENTRADA` | `re.Pattern[str]` | `re.compile('-|/dev/stdin|/dev/fd/\\d+|/proc/[^/]+/fd/\\d+')` |
| `LIMITE_DE_ANINHAMENTO` | `int` | `8` |
| `PALAVRA_GIT` | `re.Pattern[str]` | `re.compile('(?<!\\w)git(?!\\w|\\.(?!(?:' + '|'.join((sufixo[1:] for suf…` |
| `LIBERADO` | `Decisao` | `Decisao(True)` |
| `TRATADORES` | `Mapping[str, Callable[[_Chamada], Decisao]]` | `{**{programa: _git for programa in PROGRAMAS_DO_GIT}, **{programa: _she…` |

### `Decisao`

*DTO imutável* — Se o comando passa e, quando não passa, o motivo que vai ao agente.

**Campos:** `permitido: bool`, `motivo: str`, `opaco: str`

### `_Chamada`

*DTO imutável* — Um programa a decidir: as palavras a partir do nome dele e o que veio na frente e na entrada.

**Campos:** `palavras: tuple[Palavra, ...]`, `atribuicoes: tuple[Palavra, ...]`, `entrada: str | None`, `entrada_dinamica: bool`, `profundidade: int`

- `argumentos() -> tuple[Palavra, ...]` `[property]` — As palavras depois do nome do programa.
- `programa() -> str` `[property]` — O nome do programa chamado.

### Funções do módulo

- `decidir(comando: str) -> Decisao` — Se o comando Bash passa pela trava do git: só as leituras do git passam, e o que não se lê é recusado.
- `cita_git(texto: str) -> bool` — O texto tem a palavra `git` que pode ser o comando, sem contar aspas (`g"i"t` cita).
- `nome_do_programa(texto: str) -> str` — O nome do programa sem a pasta, em minúsculas e sem `.exe` (o Windows não distingue caixa).

## `orquestrador/gravacao_da_verificacao.py`

A verificação gravada no livro-razão: a Evidence, um nó Achado por problema, o estado dos critérios e as pendências, num lote só.

### `RegistroDaVerificacao`

*DTO imutável* — O que a verificação deixa no livro-razão: o número, o commit verificado, o parecer e o que o orquestrador rodou.

**Campos:** `numero: int`, `verificacao: Verificacao`, `commit: str`, `commit_do_codigo: str`, `suite: ResultadoDaSuite`, `nos: Mapping[str, str]`, `pendencias: Sequence[Mapping[str, Any]]`, `ciclo: int`, `final: bool`, `marco: str`, `aceite: Sequence[Mapping[str, Any]]`, `resolver: Sequence[str]`, `tirado_antes_do_aceite: Sequence[str]`, `configuracao_do_aceite: Sequence[str]`, `aceite_com_a_configuracao_do_aceite: Sequence[Mapping[str, Any]]`, `diferencas_de_configuracao: Sequence[Mapping[str, Any]]`, `tipo: str`, `arquivos: Sequence[str]`

- `limpa() -> bool` `[property]` — Sem bloqueante.
- `propriedades(id_goal: str) -> dict[str, Any]` — As propriedades da Evidence; cada parecer leva o nó do critério ou da decisão que julga.
- `achados(id_goal: str) -> list[tuple[str, Achado]]` — Os achados que viram nós, com o id de cada um: os bloqueantes e depois os acompanhamentos.

### Funções do módulo

- `gravar_verificacao(livro: LivroRazaoDoGoal, registro: RegistroDaVerificacao) -> str` — Grava a verificação inteira num lote; devolve o id da Evidence.

## `orquestrador/gravacao_do_aceite.py`

Os testes de aceite gravados no livro-razão: o commit como Artifact, a ligação de cada critério aos seus testes e o Goal.

### `AceiteParaGravar`

*DTO imutável* — O aceite conferido e commitado: a saída do autor, o commit, os arquivos, as execuções e o nó de cada critério.

**Campos:** `saida: SaidaDoAceite`, `commit: str`, `arquivos: tuple[str, ...]`, `execucoes: Sequence[Mapping[str, Any]]`, `nos: Mapping[str, str]`, `id_do_aceite: str`, `revisoes: int`, `atendidos: tuple[str, ...]`, `so: tuple[str, ...]`, `commit_da_configuracao: str`, `do_commit: tuple[str, ...]`, `declarados: tuple[str, ...]`

- `em_json() -> dict[str, Any]` — O aceite como propriedade do Goal.

### Funções do módulo

- `commit_da_configuracao(aceite: Mapping[str, Any] | None) -> str` — O commit cuja configuração de teste vale para o aceite: o do primeiro aceite do plano, que os refeitos guardam.
- `gravar_aceite_proposto(livro: LivroRazaoDoGoal, proposto: Mapping[str, Any] | None) -> None` — A saída conferida do autor e as execuções vermelhas, no Goal, antes do commit: a retomada a reaproveita.
- `gravar_aceite(livro: LivroRazaoDoGoal, pedido: AceiteParaGravar) -> None` — O Artifact do commit dos testes, a ligação de cada critério aos seus testes e o aceite no Goal, num lote.

## `orquestrador/gravacao_do_plano.py`

O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só.

### `PlanoParaGravar`

*DTO imutável* — O plano conferido e o que o cerca: o slug, os nós já fixados e o commit do documento, com os arquivos dele.

**Campos:** `plano: Plano`, `slug: str`, `commit_do_documento: str`, `caminho_do_documento: str`, `arquivos_do_commit: tuple[str, ...]`, `nos_fixados: Mapping[str, str]`, `renomear_goal: bool`, `versao: int`, `retirar: Mapping[str, Mapping[str, str]]`

- `slug_das_tasks() -> str` `[property]` — O slug das Tasks do plano: com a versão, a partir do plano que veio depois de uma recusa.

### Funções do módulo

- `gravar_plano(livro: LivroRazaoDoGoal, pedido: PlanoParaGravar) -> None` — Grava o plano inteiro num lote.

## `orquestrador/historico_da_correcao.py`

O que a fatia de correção recebe além do achado: o comando que o reproduz e, quando a falha volta, a tentativa anterior.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DO_DIFF` | `int` | `4000` |
| `MAXIMO_DE_CHAMADAS` | `int` | `8` |
| `MAXIMO_DE_TENTATIVAS_ANTERIORES` | `int` | `2` |
| `CITACAO_DE_COMANDO` | `re.Pattern[str]` | `re.compile('`([^`\\n]*\\S\\s+\\S[^`\\n]*)`')` |
| `CAMPO_REPRODUCAO` | `str` | `'reproducao'` |

### Funções do módulo

- `chamadas_que_reproduzem(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> list[str]` — As chamadas que reproduzem cada achado da correção, da verificação em que ele nasceu: ao menos uma por achado, até 8.
- `tentativas_anteriores(area: GitDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> tuple[str, ...]` — O diff das correções de ciclos anteriores do marco na mesma área, e o que a verificação seguinte disse delas.

## `orquestrador/hook_do_git.py`

O hook PreToolUse da trava do git: o Claude Code o chama antes de cada comando Bash da sessão de agente.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CODIGO_DE_RECUSA` | `int` | `2` |
| `FERRAMENTA_DO_SHELL` | `str` | `'Bash'` |

### Funções do módulo

- `decisao_da_entrada(texto: str) -> Decisao` — A decisão sobre o evento do PreToolUse; a entrada que não se lê é recusada.
- `responder(entrada: BinaryIO | None, erro: BinaryIO | None) -> int` — Lê o evento da entrada padrão e devolve o código de saída: 0 passa, 2 recusa com o motivo no stderr.

## `orquestrador/laco.py`

O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LIMITE_DE_PASSOS` | `int` | `200` |
| `PEDIDOS_COM_A_TRAVA` | `frozenset[str]` | `frozenset({PEDIDO_RETIRAR_CRITERIO, PEDIDO_RECUSAR_PLANO, PEDIDO_REFAZE…` |

### `Orquestrador`

*serviço* — Conduz Goals com as dependências dadas; cada chamada roda até o Goal fechar ou o laço parar.

- `iniciar_da_spec(spec: Path, repositorio: Path, opcoes: OpcoesDoLaco) -> Parada` — Cria o Goal da spec (ou retoma o que a mesma spec já criou) e roda; a falha de domínio vira parada.
- `rodar(id_goal: str, opcoes: OpcoesDoLaco, repositorio: Path | None) -> Parada` — Roda ou retoma o Goal até ele fechar ou o laço parar, com a trava do Goal; a falha de domínio vira parada.
- `aprovar_plano(id_goal: str, autor: str) -> str` — O portão do plano do orquestrador: o humano aprova junto o plano e os testes de aceite, no commit deles.
- `pedir(id_goal: str, pedido: NovoPedido) -> str` — Grava o pedido do humano (orquestrador/pedidos_do_humano.py), conferido contra o Goal como ele está.

## `orquestrador/leitura_das_verificacoes.py`

As verificações do Goal e os nós Achado delas e das revisões de risco, como o laço os lê do livro-razão.

### `AchadoRegistrado`

*DTO imutável* — Um nó Achado de uma verificação do Goal: a gravidade que o código decidiu, o estado e o que ele é.

**Campos:** `id: str`, `verificacao: str`, `gravidade: str`, `estado: str`, `propriedades: Mapping[str, Any]`

- `texto(chave: str) -> str` — Uma propriedade de texto do achado.
- `lista(chave: str) -> tuple[str, ...]` — Uma propriedade de lista de textos do achado.
- `bloqueante() -> bool` `[property]` — O código o decidiu bloqueante.
- `encerrado() -> bool` `[property]` — Resolvido, ou descartado pelo humano.

### `VerificacaoRegistrada`

*DTO imutável* — Uma verificação do Goal: em que commit, com que veredito e o que achou.

**Campos:** `id: str`, `commit: str`, `veredito: str`, `ciclo: int`, `propriedades: Mapping[str, Any]`, `commit_do_codigo: str`, `achados: tuple[AchadoRegistrado, ...]`, `marco: str`, `reprovados: tuple[str, ...]`

- `tipo() -> str` `[property]` — A caçada, a do marco ou a conferência; vazio na verificação de antes dos tipos.
- `confirmados() -> tuple[str, ...]` `[property]` — Os achados conferidos que esta conferência deu por corrigidos.
- `bloqueantes() -> tuple[AchadoRegistrado, ...]` — Os nós Achado bloqueantes desta verificação.
- `bloqueantes_abertos() -> tuple[AchadoRegistrado, ...]` — Os bloqueantes ainda não encerrados: o resolvido e o que o humano descartou não contam.
- `limpa() -> bool` `[property]` — Sem bloqueante, ou com todo bloqueante dela encerrado (resolvido, ou descartado pelo humano), e sem critério reprovado.

### Funções do módulo

- `do_orquestrador(no: NoGrafo | None) -> bool` — O nó nasceu de um lote do orquestrador: o laço só lê a verificação, o Achado e a revisão que ele mesmo gravou.
- `a_resolver(verificacoes: Sequence[VerificacaoRegistrada], escopo: Sequence[VerificacaoRegistrada], agora: Sequence[str]) -> tuple[str, ...]` — Os bloqueantes ainda não encerrados que uma conferência do escopo (ou a de agora) deu por corrigidos, e os que eles repetiam.
- `verificacoes_do_goal(view: GrafoView, id_goal: str) -> tuple[VerificacaoRegistrada, ...]` — As Evidence de verificação ligadas ao Goal, da mais antiga à mais nova.
- `criterios_ativos(view: GrafoView, id_goal: str) -> frozenset[str]` — Os nós Criterio que escopam o Goal e que o humano não retirou (por uma Decision dele).
- `retirado_pelo_humano(view: GrafoView, criterio: NoGrafo, id_goal: str) -> bool` — O Criterio traz a retirada pelo pedido do humano que o retira, deste Goal, como o kernel a conta.
- `achados_da_evidencia(view: GrafoView, id_evidencia: str) -> tuple[AchadoRegistrado, ...]` — Os nós Achado que derivam da verificação, na ordem dos ids.
- `achados_das_revisoes(view: GrafoView, id_task: str) -> tuple[AchadoRegistrado, ...]` — Os nós Achado das revisões de risco da fatia, da revisão mais antiga à mais nova.

## `orquestrador/leitura_do_goal.py`

O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CAMPO_TESTE_ERRADO` | `str` | `'teste_errado'` |
| `STATUS_NA_FILA` | `frozenset[str]` | `frozenset({m.STATUS_PENDENTE, m.STATUS_EM_ANDAMENTO})` |

### `DuvidaRegistrada`

*DTO imutável* — Uma Question que o orquestrador abriu para uma fatia, e o que o humano respondeu.

**Campos:** `id: str`, `pergunta: str`, `status: str`, `resposta: str`, `criterio_do_teste: str`, `decisao_do_teste: str`

- `aberta() -> bool` `[property]` — Ainda espera o humano.

### `EstadoDoGoal`

*DTO imutável* — Tudo o que o laço lê do Goal para decidir o passo seguinte.

**Campos:** `id_goal: str`, `rotulo: str`, `status: str`, `propriedades: Mapping[str, Any]`, `fatias: tuple[FatiaRegistrada, ...]`, `verificacoes: tuple[VerificacaoRegistrada, ...]`, `plano_aprovado: bool`, `pedidos: tuple[PedidoDoHumano, ...]`, `decisoes_do_agente: tuple[DecisaoDoAgente, ...]`, `commits_do_aceite: Mapping[str, str]`

- `configuracao() -> m.ConfiguracaoDoGoal | None` `[property]` — A configuração do laço, quando o orquestrador já conduz o Goal.
- `plano() -> Mapping[str, Any] | None` `[property]` — O plano gravado, quando já há.
- `aceite() -> Mapping[str, Any] | None` `[property]` — Os testes de aceite gravados (commit, comando, arquivos e o aceite de cada critério), quando já há.
- `arquivos_protegidos() -> tuple[str, ...]` — Os arquivos dos testes de aceite: o executor não os toca, e a suíte do plano roda sem eles.
- `fechado() -> bool` `[property]` — O Goal já fechou.
- `cancelado() -> bool` `[property]` — O humano cancelou o Goal.
- `ciclos_de_correcao() -> int` `[property]` — Quantos ciclos de correção a verificação já abriu.
- `pendencias() -> list[dict[str, Any]]` `[property]` — As pendências gravadas no Goal.
- `desacordo_vigente(item: Mapping[str, Any]) -> bool` — O desacordo sobre o teste de aceite do critério ainda vale: o teste não foi refeito depois dele (o commit do aceite é o mesmo).
- `achado(id_achado: str) -> AchadoRegistrado | None` — O nó Achado de qualquer verificação do Goal, pelo id.
- `ultima_verificacao() -> VerificacaoRegistrada | None` `[property]` — A verificação mais recente.
- `marcos() -> tuple[MarcoRegistrado, ...]` — Os marcos do plano, em ordem; o plano sem marcos (o de antes da fase 2) é um marco só, o final.
- `fatias_do_marco(marco: MarcoRegistrado) -> tuple[FatiaRegistrada, ...]` — As fatias do marco, as de correção inclusive.
- `verificacoes_do_marco(marco: MarcoRegistrado) -> tuple[VerificacaoRegistrada, ...]` — As verificações do marco, da mais antiga à mais nova.
- `marco_atual() -> MarcoRegistrado` — O primeiro marco sem verificação limpa que ainda tem o que fazer; com todos encerrados, o final.
- `limite_de_ciclos(marco: MarcoRegistrado) -> int` — Quantos ciclos de correção o marco tem: os do Goal (dois, ou o que a chamada disse), mais os que o humano deu a ele.
- `pedidos_pendentes(acao: str) -> tuple[PedidoDoHumano, ...]` — Os pedidos com a ação dada que o laço ainda não atendeu: os do humano e os de refazer um teste de aceite.
- `marco_esgotado(marco: MarcoRegistrado) -> bool` — O marco intermediário gastou os ciclos, e a verificação depois do último ainda tem bloqueante: ele não tem o que fazer.
- `bloqueantes_de_antes(ultima: VerificacaoRegistrada) -> tuple[AchadoRegistrado, ...]` — Os bloqueantes ainda abertos das outras verificações (dos outros marcos e as anteriores do marco): a final os cobra de novo.
- `corrigidos(marco: MarcoRegistrado, agora: Sequence[str]) -> tuple[str, ...]` — Os Achados que a verificação limpa do marco resolve: os que uma conferência dele (na final, do Goal) ou a de agora deu por corrigidos.
- `ciclos_do_marco(marco: MarcoRegistrado) -> int` — Quantos ciclos de correção o marco já abriu: as verificações dele de onde nasceram fatias de correção.
- `prontas(marco: MarcoRegistrado | None) -> tuple[FatiaRegistrada, ...]` — As fatias que podem rodar agora, na ordem do plano; com o marco dado, só as dele.
- `pausadas() -> tuple[FatiaRegistrada, ...]` — As fatias paradas numa dúvida aberta.
- `bloqueadas() -> tuple[FatiaRegistrada, ...]` — As fatias que viraram pendência depois da segunda falha.

### `FatiaRegistrada`

*DTO imutável* — Uma fatia do Goal como o livro-razão a guarda.

**Campos:** `id: str`, `codigo: str`, `titulo: str`, `status: str`, `ordem: int`, `propriedades: Mapping[str, Any]`, `depende_de: tuple[str, ...]`, `duvidas: tuple[DuvidaRegistrada, ...]`, `achados_de_revisao: tuple[AchadoRegistrado, ...]`

- `texto(chave: str) -> str` — Uma propriedade de texto da fatia.
- `lista(chave: str) -> tuple[str, ...]` — Uma propriedade de lista de textos da fatia.
- `tentativas() -> int` `[property]` — Quantas sessões de executor a fatia já abriu, dúvidas inclusive.
- `falhas() -> int` `[property]` — Quantas tentativas falharam (a saída inválida, a suíte vermelha, a sessão interrompida); a dúvida não conta.
- `duvida_aberta() -> DuvidaRegistrada | None` `[property]` — A dúvida que pausa a fatia, quando há.

### `MarcoRegistrado`

*DTO imutável* — Um marco do plano gravado: as fatias dele, os critérios que a verificação dele julga e se é o final.

**Campos:** `id: str`, `titulo: str`, `fatias: tuple[str, ...]`, `criterios: tuple[str, ...]`, `final: bool`

- `contem(fatia: FatiaRegistrada, primeiro: bool) -> bool` — A fatia é deste marco; a fatia de antes dos marcos é do primeiro.

### Funções do módulo

- `ler_estado(view: GrafoView, id_goal: str) -> EstadoDoGoal | None` — O estado do Goal no grafo; None quando o Goal não existe.
- `setor_do_goal(view: GrafoView, id_goal: str) -> str` — O Setor que contém a Sessao que produziu o Goal; vazio quando não há.

## `orquestrador/leitura_do_shell.py`

A leitura de um comando Bash em comandos simples, para a trava do git decidir sobre cada um.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEPARADORES` | `tuple[str, ...]` | `('&&', '||', ';;&', ';;', ';&', '|&', ';', '|', '&', '(', ')')` |
| `FIM_DO_ITEM_DO_CASE` | `frozenset[str]` | `frozenset({';;', ';;&', ';&'})` |
| `PALAVRAS_RESERVADAS` | `frozenset[str]` | `frozenset({'!', '{', '}', 'if', 'then', 'else', 'elif', 'fi', 'do', 'do…` |
| `REDIRECIONAMENTOS` | `tuple[str, ...]` | `('<<<', '<<-', '&>>', '<<', '>>', '<&', '>&', '<>', '>|', '&>', '<', '>…` |
| `INICIO_DE_OPERADOR` | `str` | `';&|()<>'` |
| `ESCAPAVEIS_NAS_ASPAS` | `str` | `'$`"\\\n'` |
| `NOME_DE_VARIAVEL` | `re.Pattern[str]` | `re.compile('[A-Za-z_][A-Za-z0-9_]*')` |
| `VARIAVEL_PURA` | `re.Pattern[str]` | `re.compile('\\$(?:[A-Za-z_][A-Za-z0-9_]*|\\{[A-Za-z_][A-Za-z0-9_]*\\})')` |
| `PARES` | `dict[str, str]` | `{'(': ')', '{': '}'}` |

### `ComandoIlegivel` (ValueError)

*serviço* — O texto não fecha como shell: aspas, parêntese, substituição ou heredoc sem fim.

### `ComandoSimples`

*DTO imutável* — Um comando simples: as palavras e o texto que entra por heredoc ou here-string.

**Campos:** `palavras: tuple[Palavra, ...]`, `entrada: str | None`, `entrada_dinamica: bool`

### `LeituraDoShell`

*DTO imutável* — Os comandos simples do texto e o texto de cada substituição que ele faz.

**Campos:** `comandos: tuple[ComandoSimples, ...]`, `substituicoes: tuple[str, ...]`

### `Palavra`

*DTO imutável* — Uma palavra sem aspas; dinâmica quando o valor só se sabe ao rodar; composta com expansão além de `$NOME`.

**Campos:** `texto: str`, `dinamica: bool`, `atribuicao: bool`, `composta: bool`

- `nome_atribuido() -> str` `[property]` — O nome da variável de `NOME=valor`; vazio quando a palavra não é atribuição.

### `_Leitor`

*serviço* — O cursor da leitura: a palavra em obra, os comandos fechados e o que espera um heredoc.

- `ler() -> LeituraDoShell` — Lê o texto inteiro e confere que nada ficou aberto.

### Funções do módulo

- `ler_shell(texto: str) -> LeituraDoShell` — Os comandos simples e as substituições do texto; `ComandoIlegivel` quando ele não fecha.
- `substituicoes_em(texto: str) -> list[str]` — O texto de cada `$(...)` e crase de um trecho que o shell expande sem separar em palavras.
- `fechamento(texto: str, abre: int) -> int` — O índice do parêntese ou da chave que fecha o de `abre`, pulando aspas e escapes.
- `fim_das_aspas(texto: str, abre: int) -> int` — O índice da aspa que fecha a de `abre`; nas duplas, pula escapes e substituições.

## `orquestrador/leituras_do_git.py`

Quais invocações do git a trava deixa o agente rodar: só as leituras, com as opções que não gravam nem rodam nada.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `LEITURAS_DO_GIT` | `tuple[str, ...]` | `('status', 'diff', 'log', 'show', 'blame', 'ls-files', 'rev-parse', 'gr…` |
| `LEITURAS_EM_TEXTO` | `str` | `', '.join(LEITURAS_DO_GIT) + ', branch e tag que listam, stash list/sho…` |
| `OPCOES_GLOBAIS_COM_VALOR` | `frozenset[str]` | `frozenset({'-C', '--git-dir', '--work-tree', '--namespace', '--super-pr…` |
| `OPCOES_GLOBAIS_SEM_VALOR` | `frozenset[str]` | `frozenset({'--no-pager', '-p', '--paginate', '-P', '--bare', '--no-repl…` |
| `OPCOES_DE_LISTAR_BRANCH` | `frozenset[str]` | `frozenset({'--show-current', '-a', '--all', '-r', '--remotes', '-v', '-…` |
| `OPCOES_DE_LISTAR_TAG` | `frozenset[str]` | `frozenset({'-l', '--list', '-n', '--contains', '--no-contains', '--merg…` |
| `OPCOES_QUE_LISTAM_TAG` | `frozenset[str]` | `frozenset({'-l', '--list', '-n', '--contains', '--no-contains', '--merg…` |
| `ACOES_QUE_LEEM_CONFIG` | `frozenset[str]` | `frozenset({'--get', '--get-all', '--get-regexp', '--get-urlmatch', '--l…` |
| `OPCOES_DE_LER_CONFIG` | `frozenset[str]` | `ACOES_QUE_LEEM_CONFIG | frozenset({'--global', '--system', '--local', '…` |
| `OPCOES_QUE_GRAVAM` | `tuple[tuple[str, int], ...]` | `(('--output', 4), ('--open-files-in-pager', 4))` |
| `LEITURAS_EM_PARTE` | `Mapping[str, Callable[[tuple[Palavra, ...]], bool]]` | `{'branch': _branch_que_lista, 'tag': _tag_que_lista, 'stash': _stash_qu…` |

### `_Subcomando`

*DTO imutável* — O subcomando achado depois das opções globais e o que vem depois dele.

**Campos:** `nome: str`, `argumentos: tuple[Palavra, ...]`

### Funções do módulo

- `motivo_do_git(argumentos: tuple[Palavra, ...]) -> str` — Por que a trava recusa o git com estes argumentos; vazio quando é leitura que passa.
- `chave_inofensiva(atribuicao: str) -> bool` — A chave do `git -c chave=valor` só muda a saída: `core.quotepath` ou `color.*` (nenhum `*.command`).

## `orquestrador/livro_razao.py`

O livro-razão do Goal, gravado pelo orquestrador com o papel `orquestrador`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RAMO_PADRAO` | `str` | `'main'` |
| `ACAO_DA_REVISAO_DE_RISCO` | `str` | `'revisao_de_risco'` |
| `CAMPOS_DA_ANCORA_DA_REVISAO` | `tuple[str, ...]` | `(m.CAMPO_COMMIT, CAMPO_ARVORE, CAMPO_ARQUIVOS)` |
| `ROTULO_DO_SETOR` | `str` | `'Goals orquestrados'` |
| `LIMITE_DO_ROTULO` | `int` | `120` |

### `GoalNovo`

*DTO imutável* — O Goal que nasce de uma spec: onde ele mora no grafo e o que ele guarda.

**Campos:** `id_goal: str`, `rotulo: str`, `spec: str`, `configuracao: m.ConfiguracaoDoGoal`, `nome_do_repositorio: str`

### `LivroRazaoDoGoal`

*serviço* — As escritas do laço sobre um Goal, cada uma num lote do papel `orquestrador`.

- `id_sessao() -> str` `[property]` — A Sessao do orquestrador que produz o que ele grava do Goal.
- `view() -> GrafoView` — O grafo agora.
- `gravar(operacoes: Sequence[ItemPatch], justificativa: str) -> None` — Submete o lote; a recusa vira `LoteRecusado` com o motivo do kernel.
- `produzido(id_no: str, tipo: TipoNo, rotulo: str) -> list[ItemPatch]` — O nó de trabalho pendurado na Sessao do orquestrador.
- `criar_goal(novo: GoalNovo) -> None` — Projeto e Setor do repositório (se faltam), a Sessao do Goal e o Goal com a spec e a configuração.
- `adotar_goal(id_setor: str, spec: str, configuracao: m.ConfiguracaoDoGoal) -> None` — O Goal que o gerente criou passa a ser conduzido: a Sessao do orquestrador, a spec montada e a configuração.
- `gravar_plano_proposto(dados: Mapping[str, Any]) -> None` — A saída conferida do planejador no Goal, antes de qualquer passo que possa cair no meio.
- `iniciar_tentativa(id_task: str, tentativa: int) -> None` — A fatia entra em andamento, com a tentativa contada antes de a sessão abrir.
- `guardar_entrega(id_task: str, entrega: Mapping[str, Any]) -> None` — A entrega pronta do executor fica na fatia (o .patch e a saída): a retomada refaz só a revisão.
- `devolver_tentativa(id_task: str, tentativas: int) -> None` — A tentativa que a API recusou não conta: a fatia volta a pendente, com as tentativas de antes dela.
- `concluir_fatia(id_task: str, tentativa: int) -> None` — O commit vira Artifact da fatia, com os `arquivos` lidos dele, e a fatia fecha.
- `registrar_falha(id_task: str, tentativa: int) -> None` — A tentativa que falhou vira Note da fatia, e a fatia volta a pendente com o erro e a conta das falhas.
- `registrar_trava_mexida(papel: str, fatia: str, motivo: str) -> None` — A sessão de papel que mexeu na trava do git vira Note da Sessao do Goal (e da fatia, quando há), com o papel e o motivo.
- `registrar_humano_mexido(papel: str, fatia: str, mexido: HumanoMexido) -> None` — A sessão em que o repositório do humano mudou vira Note da Sessao do Goal (e da fatia): a que perdeu trabalho, com a
- `registrar_revisao(id_task: str, tentativa: int) -> None` — O veredito da revisão da fatia de risco vira Evidence que deriva da fatia, com os Achados dela no mesmo lote.
- `marcar_pendencia(id_task: str, motivo: str, pendencias: Sequence[Mapping[str, Any]]) -> None` — A fatia que falhou duas vezes sai da fila e vira pendência do Goal.
- `abrir_duvida(id_task: str, tentativa: int) -> str` — A dúvida do executor vira Question que bloqueia a fatia; devolve o id dela.
- `gravar_ponta(ponta: Mapping[str, object]) -> None` — A ponta da branch do Goal como o git a tem agora: o commit, o commit do código e os equivalentes dele.
- `criar_correcoes(id_evidencia: str, achados: Sequence[AchadoRegistrado]) -> None` — Os Achados bloqueantes do ciclo viram uma fatia de correção do marco, que deriva de todos eles.
- `dividir_correcao(fatia: FatiaRegistrada, achados: Sequence[AchadoRegistrado]) -> None` — A correção agrupada que esgotou as tentativas sai do plano e vira uma fatia por achado, no mesmo ciclo.
- `resolver(achados: Sequence[str], justificativa: str) -> None` — Os Achados corrigidos passam a resolvidos: a conferência os confirmou, e a verificação limpa do marco fecha o ciclo.
- `fechar(commit_integrado: str) -> None` — O Goal fecha com o commit integrado, e a Sessao do orquestrador se encerra.

### `LoteRecusado` (GraphowError)

*serviço* — O kernel recusou um lote do orquestrador: defeito do laço, e não do agente.

### Funções do módulo

- `no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch` — A criação de um nó.
- `aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch` — A criação de uma aresta, com id derivado das pontas.
- `propriedade(id_no: str, chave: str, valor: object) -> ItemPatch` — A escrita de uma propriedade de um nó que já existe.
- `fora_do_commit(declarados: Iterable[str], do_commit: Sequence[str]) -> str` — O que foi declarado e o commit não traz, como trecho da observação do Artifact; vazio quando ele traz tudo.
- `juntar_observacoes() -> str` — As observações que não estão vazias, numa frase só.

## `orquestrador/modelo_do_goal.py`

Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AUTOR_DO_ORQUESTRADOR` | `str` | `'graphow-orquestrar'` |
| `MODO_SUPERVISIONADO` | `str` | `'supervisionado'` |
| `MODO_AUTONOMO` | `str` | `'autonomo'` |
| `MODOS` | `tuple[str, ...]` | `(MODO_SUPERVISIONADO, MODO_AUTONOMO)` |
| `CAMPO_SPEC` | `str` | `'spec'` |
| `CAMPO_ORQUESTRACAO` | `str` | `a.CAMPO_CONDUCAO` |
| `CAMPO_PLANO` | `str` | `a.CAMPO_PLANO` |
| `CAMPO_PLANO_PROPOSTO` | `str` | `'plano_proposto'` |
| `CAMPO_CICLOS` | `str` | `'ciclos_de_correcao'` |
| `CAMPO_ACEITE` | `str` | `'aceite'` |
| `CAMPO_ACEITE_PROPOSTO` | `str` | `'aceite_proposto'` |
| `CAMPO_PENDENCIAS` | `str` | `'pendencias'` |
| `CAMPO_INTEGRADO_EM` | `str` | `'integrado_em'` |
| `CAMPO_PONTA_DO_RAMO` | `str` | `a.CAMPO_PONTA_DO_RAMO` |
| `CAMPO_COMMIT_DO_CODIGO` | `str` | `a.CAMPO_COMMIT_DO_CODIGO` |
| `CAMPO_APROVACAO_DO_PLANO` | `str` | `CAMPO_DA_APROVACAO` |
| `CAMPO_STATUS` | `str` | `'status'` |
| `CAMPO_FATIA` | `str` | `'fatia'` |
| `CAMPO_OBJETIVO` | `str` | `'objetivo'` |
| `CAMPO_CRITERIOS` | `str` | `'criterios'` |
| `CAMPO_ARQUIVOS_ALVO` | `str` | `'arquivos_alvo'` |
| `CAMPO_MARCO` | `str` | `a.CAMPO_MARCO` |
| `CAMPO_MODELO` | `str` | `'modelo'` |
| `CAMPO_RISCO` | `str` | `'risco'` |
| `CAMPO_MOTIVO_DO_RISCO` | `str` | `'motivo_do_risco'` |
| `CAMPO_ORDEM` | `str` | `'ordem'` |
| `CAMPO_TENTATIVAS` | `str` | `'tentativas'` |
| `CAMPO_FALHAS` | `str` | `'falhas'` |
| `CAMPO_ULTIMO_ERRO` | `str` | `'ultimo_erro'` |
| `CAMPO_PATCH` | `str` | `'patch_da_tentativa'` |
| `CAMPO_PENDENCIA` | `str` | `'pendencia'` |
| `CAMPO_COMMIT` | `str` | `a.CAMPO_COMMIT` |
| `CAMPO_CORRIGE` | `str` | `'corrige_verificacao'` |
| `CAMPO_ACHADO` | `str` | `'achado'` |
| `CAMPO_SUBSTITUIDA` | `str` | `'substituida_por'` |
| `CAMPO_ENTREGA_PENDENTE` | `str` | `'entrega_pendente'` |
| `CAMPO_CRITERIO_DO_TESTE` | `str` | `'criterio_do_teste'` |
| `CAMPO_ACHADOS` | `str` | `'achados'` |
| `MAXIMO_DE_CICLOS_DE_CORRECAO` | `int` | `2` |
| `CAMPO_CRITERIO_PRONTO` | `str` | `'criterio_pronto'` |
| `CAMPO_PERGUNTA` | `str` | `'pergunta'` |
| `CAMPO_RESPOSTA` | `str` | `'resposta'` |
| `CAMPO_ABERTA_POR` | `str` | `'aberta_por'` |
| `CAMPO_VEREDITO` | `str` | `a.CAMPO_VEREDITO` |
| `CAMPO_CICLO` | `str` | `'ciclo'` |
| `CAMPO_NUMERO` | `str` | `a.CAMPO_NUMERO` |
| `CAMPO_TIPO_DA_VERIFICACAO` | `str` | `'tipo_da_verificacao'` |
| `CAMPO_CONFERIDOS` | `str` | `'conferidos'` |
| `CAMPO_FINAL` | `str` | `a.CAMPO_FINAL` |
| `CAMPO_PARECERES` | `str` | `a.CAMPO_PARECERES` |
| `ACAO_DA_VERIFICACAO` | `str` | `a.ACAO_DA_VERIFICACAO` |
| `ACAO_DA_TENTATIVA` | `str` | `'tentativa_que_falhou'` |
| `ACAO_DA_TRAVA_MEXIDA` | `str` | `'trava_mexida'` |
| `ACAO_DO_HUMANO_MEXIDO` | `str` | `'repositorio_do_humano_mexido'` |
| `ACAO_DO_HUMANO_QUE_AVANCOU` | `str` | `'repositorio_do_humano_avancou'` |
| `VEREDITO_LIMPO` | `str` | `a.VEREDITO_LIMPO` |
| `VEREDITO_COM_BLOQUEANTE` | `str` | `a.VEREDITO_COM_BLOQUEANTE` |
| `STATUS_PENDENTE` | `str` | `'pendente'` |
| `STATUS_EM_ANDAMENTO` | `str` | `'em_andamento'` |
| `STATUS_CONCLUIDO` | `str` | `'concluido'` |
| `STATUS_BLOQUEADO` | `str` | `'bloqueado'` |

### `ConfiguracaoDoGoal`

*DTO imutável* — O que o laço precisa saber de onde e como trabalhar, gravado no Goal na primeira chamada.

**Campos:** `modo: str`, `repositorio: str`, `area: str`, `ramo: str`, `base: str`, `slug: str`, `orcamento_usd: float`, `ciclos_de_correcao: int`

- `em_json() -> dict[str, Any]` — A configuração como propriedade do Goal.
- `de_json(dados: Mapping[str, Any]) -> 'ConfiguracaoDoGoal'` — A configuração lida do Goal.

### Funções do módulo

- `achados_da_correcao(propriedades: Mapping[str, Any]) -> tuple[str, ...]` — Os Achados que a fatia de correção corrige: a lista, ou o único da fatia de antes do agrupamento.
- `id_da_revisao(id_task: str, tentativa: int) -> str` — O id da Evidence da revisão de risco de uma tentativa da fatia.
- `slug_de(texto: str) -> str` — Identificador estável, minúsculo, sem acento nem espaço.
- `id_do_goal(slug: str) -> str` — O Goal que o orquestrador cria a partir de uma spec.
- `id_do_projeto(slug_do_repositorio: str) -> str` — O Projeto dos Goals orquestrados de um repositório.
- `id_do_setor(slug_do_repositorio: str) -> str` — O Setor dos Goals orquestrados de um repositório.
- `id_da_sessao(id_goal: str) -> str` — A Sessao do orquestrador que produz o que ele grava do Goal (o contrato do papel a reconhece por este nome).
- `id_do_criterio(slug: str, codigo: str) -> str` — O Criterio de um critério de aceite criado pelo plano (na fase 1, uma Constraint com o mesmo id).
- `id_da_decisao(slug: str, codigo: str) -> str` — A Decision de uma decisão registrada pelo plano.
- `id_do_aceite(id_goal: str, versao: int) -> str` — O que o trailer `Graphow-Task` do commit dos testes de aceite diz, e o sufixo do Artifact dele.
- `versao_do_plano(propriedades: Mapping[str, Any]) -> int` — A versão do plano do Goal: um, mais um por plano que o humano recusou.
- `slug_da_versao(slug: str, versao: int) -> str` — O slug com que as Tasks do plano nascem: o do Goal, e a versão a partir da segunda.
- `id_da_verificacao(id_goal: str, numero: int) -> str` — A Evidence da verificação de número dado do Goal.
- `id_do_achado(id_goal: str, numero: int, indice: int) -> str` — O Achado de índice dado da verificação de número dado.
- `id_da_fatia(slug: str, codigo: str) -> str` — A Task de uma fatia do plano ou de uma correção.

## `orquestrador/pedidos_do_humano.py`

Os pedidos do humano ao laço: cada saída que ele tem de um Goal parado, gravada como Decision dele.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PEDIDO_DESCARTAR_ACHADO` | `str` | `'descartar_achado'` |
| `PEDIDO_MAIS_CICLOS` | `str` | `'mais_ciclos'` |
| `PEDIDO_CANCELAR` | `str` | `'cancelar'` |
| `PEDIDO_RECUSAR_PLANO` | `str` | `a.ACAO_RECUSAR_PLANO` |
| `PEDIDO_REFAZER_ACEITE` | `str` | `'refazer_aceite'` |
| `PEDIDO_RETIRAR_CRITERIO` | `str` | `a.ACAO_RETIRAR_CRITERIO` |
| `PEDIDOS` | `frozenset[str]` | `frozenset({PEDIDO_DESCARTAR_ACHADO, PEDIDO_MAIS_CICLOS, PEDIDO_CANCELAR…` |
| `CAMPO_DECIDIDA_PELO_AGENTE` | `str` | `'decidida_pelo_agente'` |
| `ESTADOS_QUE_SE_DESCARTAM` | `frozenset[str]` | `frozenset({a.ESTADO_ABERTO, a.ESTADO_CORRIGIDO, a.ESTADO_DO_ACOMPANHAME…` |

### `DecisaoDoAgente`

*DTO imutável* — Uma decisão que o executor tomou por conta própria, no modo autônomo, para o humano revisar.

**Campos:** `id: str`, `fatia: str`, `questao: str`, `decisao: str`, `motivo: str`

### `NovoPedido`

*DTO imutável* — O que o humano pede pela CLI.

**Campos:** `acao: str`, `motivo: str`, `por: str`, `alvo: str`, `ciclos: int`

### `PedidoDoHumano`

*DTO imutável* — Um pedido gravado: o que o humano pediu, por quê, sobre o quê e quem pediu.

**Campos:** `id: str`, `acao: str`, `motivo: str`, `alvo: str`, `ciclos: int`, `por: str`, `fatia: str`

### `PedidoRecusado` (GraphowError)

*serviço* — O pedido do humano não vale para o Goal como ele está, ou o kernel o recusou.

### Funções do módulo

- `ler_pedidos(view: GrafoView, id_goal: str) -> tuple[PedidoDoHumano, ...]` — Os pedidos do humano sobre o Goal, na ordem do log.
- `ler_decisoes_do_agente(view: GrafoView, id_goal: str) -> tuple[DecisaoDoAgente, ...]` — As decisões do agente que o orquestrador gravou no Goal, na ordem do log.
- `gravar_pedido(kernel: WriteKernel, id_goal: str, pedido: NovoPedido) -> str` — Grava a Decision do pedido, com o que ele muda no mesmo lote, como o humano; devolve o id dela.
- `escrita(id_no: str, chave: str, valor: object) -> ItemPatch` — A escrita de uma propriedade de um nó, no lote do pedido.
- `descarte(view: GrafoView, id_achado: str, motivo: str) -> list[ItemPatch]` — O que o descarte muda no Achado; recusa o que não é Achado, ou o que já está encerrado.
- `cancelamento(id_goal: str, motivo: str) -> list[ItemPatch]` — O que o cancelamento muda no Goal.

## `orquestrador/planejamento.py`

O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão.

### Funções do módulo

- `planejar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None` — O plano já pago, ou uma sessão do planejador; grava o plano, ou diz por que não deu.

## `orquestrador/rastro.py`

O rastro de cada critério do Goal: o que o prova, o que o cobre, quem o atestou e o que o fere.

### `AchadoDoCriterio`

*DTO imutável* — Um Achado que fere o critério: o título, a gravidade, o estado e a verificação (ou revisão) de onde veio.

**Campos:** `id: str`, `titulo: str`, `gravidade: str`, `estado: str`, `origem: str`

### `AtestadoDoCriterio`

*DTO imutável* — A verificação mais recente que julgou o critério: o veredito, o commit e se ela vale na ponta.

**Campos:** `verificacao: str`, `tipo: str`, `marco: str`, `veredito: str`, `commit: str`, `conferencia: ConferenciaDaEvidencia | None`

- `em_json() -> dict[str, Any]` — O atestado com a conferência como o canvas a manda (com o rótulo).

### `FatiaDoCriterio`

*DTO imutável* — Uma fatia que cobre o critério: o código, o título, a situação, o commit e a verificação que ela corrige.

**Campos:** `codigo: str`, `titulo: str`, `status: str`, `commit: str`, `corrige: str`

### `RastroDoCriterio`

*DTO imutável* — O rastro de um critério: os quatro blocos e, quando o humano o retirou, a retirada.

**Campos:** `codigo: str`, `no: str`, `texto: str`, `testes: tuple[Mapping[str, Any], ...]`, `checagem: tuple[str, ...]`, `ja_atendido: str`, `commit_do_aceite: str`, `fatias: tuple[FatiaDoCriterio, ...]`, `atestado: AtestadoDoCriterio | None`, `achados: tuple[AchadoDoCriterio, ...]`, `retirada: Mapping[str, Any] | None`

- `em_json() -> dict[str, Any]` — O critério como a rota da API o devolve.

### `RastroDoGoal`

*DTO imutável* — O rastro de todos os critérios do plano do Goal, na ordem do plano.

**Campos:** `id_goal: str`, `rotulo: str`, `fechado: bool`, `criterios: tuple[RastroDoCriterio, ...]`

- `em_json() -> dict[str, Any]` — O rastro como a rota da API o devolve.

### `_LeitorDoRastro`

*serviço* — O que a leitura de cada critério consulta: o grafo, o estado do Goal e a conferência.

- `criterio(item: Mapping[str, Any]) -> RastroDoCriterio` — O rastro do critério do plano, lido do Criterio dele, das fatias, das verificações e dos Achados.

### Funções do módulo

- `ler_rastro(view: GrafoView, estado: EstadoDoGoal, leitura: LeituraPorGoal) -> RastroDoGoal` — O rastro do Goal lido (`ler_estado`), um critério do plano por vez; sem plano, sem critério.
- `formatar_rastro(rastro: RastroDoGoal) -> list[str]` — As linhas do `--rastro`: por critério, os testes, as fatias, a verificação e os achados.

## `orquestrador/rebase_no_clone.py`

O rebase da branch do Goal sobre a base que andou, feito pelo orquestrador no clone do Goal.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `OPCOES_DO_REBASE` | `tuple[str, ...]` | `('--no-autosquash', '--keep-empty', '--empty=keep', '--reapply-cherry-p…` |
| `SEM_ASPAS` | `tuple[str, ...]` | `('-c', 'core.quotepath=false')` |
| `PASTAS_DO_REBASE` | `tuple[str, ...]` | `('rebase-merge', 'rebase-apply')` |
| `LIMITE_DO_ERRO` | `int` | `2000` |

### `ConflitoNoRebase`

*DTO imutável* — O rebase que parou em conflito, já abortado: as bases, a ponta que ficou, os arquivos em conflito e o que o git disse.

**Campos:** `base_antes: str`, `base_depois: str`, `antes: str`, `arquivos: tuple[str, ...]`, `erro: str`

### `RebaseNoClone`

*DTO imutável* — O rebase que deu certo: as duas bases, as duas pontas, o par de cada commit e os arquivos que ele mudou na ponta.

**Campos:** `base_antes: str`, `base_depois: str`, `antes: str`, `depois: str`, `pares: tuple[tuple[str, str], ...]`, `arquivos: tuple[str, ...]`

### Funções do módulo

- `trazer_a_base(area: AreaDoGoal) -> str` — A base do repositório do humano, como ela está agora, no clone; devolve o commit dela.
- `rebasear(area: Path, ramo: str, base: str) -> RebaseNoClone | ConflitoNoRebase` — A branch do Goal refeita sobre a base, com o HEAD destacado; no conflito, o rebase sai e o clone volta à branch.
- `arquivos_entre(git: GitDoGoal, antes: str, depois: str) -> tuple[str, ...]` — Os arquivos que mudaram de um commit (ou árvore) ao outro, as duas pontas do renomeado, sem aspas nem escape no nome.
- `mudados_desde(area: Path, referencia: str) -> tuple[str, ...]` — Os arquivos em que a área (os novos inclusive, sem os ignorados) difere da referência; o índice fica nela.
- `arvore_da_area(area: Path, referencia: str) -> str` — A árvore da área sobre o índice da referência, que fica nela: o que a referência rastreia segue rastreado.
- `fora_da_referencia(area: Path, referencia: str, caminhos: Iterable[str]) -> tuple[str, ...]` — Dos caminhos, os que a referência (um commit ou uma árvore) não tem.
- `desfazer_o_rebase(area: Path, ramo: str) -> None` — O clone de volta à branch do Goal, que o rebase não moveu, sem o que a suíte deixou.
- `recuperar_o_clone(area: Path, ramo: str) -> str` — O rebase que o processo deixou pela metade sai, e o clone com o HEAD destacado volta à branch; diz o que fez.
- `mover_as_refs(area: AreaDoGoal, antes: str, depois: str) -> None` — A branch do Goal vai de `antes` a `depois` no clone e no repositório do humano, cada uma só se ainda está em `antes`.
- `arvore_mesclada(area: Path, ponta: str, base: str) -> tuple[str, tuple[str, ...]]` — A árvore da ponta do Goal com a base mesclada (`merge-tree`, os marcadores no conflito) e os arquivos em conflito.
- `commit_sobre(area: Path, mensagem: str) -> str` — O commit da área inteira sobre o índice da referência (`arvore_da_area`) com o pai dado, sem mover ref; devolve o hash.
- `antes_das_fatias_sobre(area: Path, base: str, commits: Sequence[CommitDoGit]) -> tuple[str, dict[str, str]]` — Os commits de antes da primeira fatia (o plano, os testes de aceite), na ordem, refeitos sobre a base; o último e o par de cada.

## `orquestrador/refazer_aceite.py`

Refazer o aceite de um critério: o autor de aceite reescreve os testes dele, com o motivo do humano no briefing.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `CHAVE_DO_REFEITO` | `str` | `'refeito'` |
| `CHAVE_SEM_VERMELHO` | `str` | `'sem_vermelho'` |

### `Refeito`

*DTO imutável* — O que a sessão do autor deu: o aceite novo, ou os problemas; `sem_vermelho` diz por que ficou o teste antigo.

**Campos:** `aceite: SaidaDoAceite | None`, `problemas: tuple[str, ...]`, `sem_vermelho: str`

### Funções do módulo

- `refazer_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None` — Uma sessão do autor de aceite refaz os testes do critério do pedido; commita e grava, ou diz por que não deu.
- `briefing_do_refazer(estado: EstadoDoGoal, pedido: PedidoDoHumano, atual: SaidaDoAceite) -> str` — O pedido ao autor: o de sempre, mais o critério a refazer, os testes atuais dele e o motivo do humano.

## `orquestrador/refs_do_humano.py`

As refs do repositório do humano que o orquestrador move: a base, na integração, e a branch do Goal, depois do rebase.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PREFIXO_DO_WORKTREE` | `str` | `'worktree '` |
| `PREFIXO_DA_BRANCH` | `str` | `'branch '` |

### Funções do módulo

- `worktree_do_ramo(repositorio: Path, ramo: str) -> str` — A pasta do worktree do repositório (o principal inclusive) em que a branch está aberta; vazio quando em nenhum.
- `integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str` — Avança a base até o commit verificado, só por fast-forward e só se a base e a branch do Goal estão onde a conferência
- `recusar_se_aberta(repositorio: Path, ramo: str) -> None` — Recusa mover a branch do Goal quando ela está aberta num worktree do repositório do humano, o checkout dele inclusive.

## `orquestrador/registro_do_rebase.py`

O rebase no livro-razão: a Evidence dele, a ponta nova, os commits novos das fatias e dos Artifact, e a retomada depois da queda.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ACAO_DO_REBASE` | `str` | `'rebase_do_goal'` |
| `CAMPO_COMMIT_ANTES_DO_REBASE` | `str` | `'commit_antes_do_rebase'` |
| `CAMPO_REBASE` | `str` | `'rebase'` |
| `CAMPO_COMMIT_ANTES` | `str` | `'commit_antes'` |
| `PREFIXO_DO_ACEITE` | `str` | `'aceite-'` |
| `CAMPOS_DO_COMMIT_DO_ACEITE` | `tuple[str, ...]` | `('commit', 'commit_da_configuracao')` |

### Funções do módulo

- `registrar_o_rebase(contexto: ContextoDoGoal, estado: EstadoDoGoal, feito: RebaseNoClone) -> str` — A Evidence do rebase, a ponta nova e os commits novos das fatias e dos Artifact, num lote; devolve o id da Evidence.
- `aceites_refeitos(contexto: ContextoDoGoal, feito: RebaseNoClone) -> dict[str, str]` — O commit novo de cada commit dos testes de aceite do Goal, pelo trailer `Graphow-Task: aceite-…` de antes e de depois.
- `cobertos_pelo_rebase(estado: EstadoDoGoal, git: GitDoGoal, arquivos: Sequence[str]) -> tuple[str, ...]` — Dos arquivos que o rebase mudou na ponta, os que algum critério cobre.
- `equivalentes_da_ponta(propriedades: Mapping[str, Any], codigo: str) -> tuple[str, ...]` — Os commits do código que a ponta gravada dá por equivalentes ao dado; vazio quando ela é de outro commit.
- `rebases_do_goal(view: GrafoView, id_goal: str) -> tuple[NoGrafo, ...]` — As Evidence de rebase que o orquestrador gravou derivando do Goal, pela ordem do log.
- `retomar_o_rebase(contexto: ContextoDoGoal) -> None` — Antes de preparar a área: o rebase pela metade sai, e o último registrado leva as refs que ficaram para trás.

## `orquestrador/regra_da_conferencia.py`

A regra da conferência num ponto só: o que ela reprova e o código dá por `atende`, e a regressão que o código confirma.

### `RegraDaConferencia`

*DTO imutável* — O que a conferência não decide sozinha, com os fatos de antes dela: os conferidos, os excedentes, os pareceres e os arquivos.

**Campos:** `conferidos: tuple[AchadoRegistrado, ...]`, `excedentes: tuple[AchadoRegistrado, ...]`, `repeticoes: Mapping[str, frozenset[str]]`, `anteriores: tuple[Parecer, ...]`, `diff: frozenset[str] | None`, `arquivos: Mapping[str, frozenset[str]]`, `em_desacordo: frozenset[str]`

- `confirmada(regressao: Achado, verificacao: Verificacao) -> bool` — A regressão cita um X que atendia ou viraria `atende`, e o diff das correções toca o local, o plano de X ou arquivo sem critério.
- `com_os_pareceres(verificacao: Verificacao) -> Verificacao` — O que ela reprova sem bloqueante que o toque, e que a regra dá por `atende`, sai `atende`; o `atende` com excedente pendente, não.

### Funções do módulo

- `copia_que_persiste(original: AchadoRegistrado, prova: str) -> Achado` — O achado conhecido que persiste (o conferido, ou o excedente do teto), como ele era, com a prova dada: bloqueante.
- `repeticoes_de(achados: Sequence[AchadoRegistrado], id_achado: str) -> frozenset[str]` — Os achados que repetem o dado pela cadeia de `persiste` (a cópia da cópia inclusive), sem ele.

## `orquestrador/replanejamento.py`

Recusar o plano: o humano recusa, com o motivo, e o planejador o refaz com o recusado e o motivo no briefing.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PROPRIEDADES_DO_PLANO_VELHO` | `tuple[str, ...]` | `(m.CAMPO_PLANO, m.CAMPO_PLANO_PROPOSTO, m.CAMPO_ACEITE, m.CAMPO_ACEITE_…` |

### Funções do módulo

- `replanejar(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None` — Retira o plano recusado (e os testes de aceite dele) e deixa o Goal pronto para o planejador de novo.
- `atendidos_com(estado: EstadoDoGoal, id_pedido: str) -> list[str]` — Os pedidos atendidos do Goal, mais o dado.
- `bloco_da_recusa(estado: EstadoDoGoal) -> str` — No briefing do planejador, o último plano recusado e o motivo do humano; vazio sem recusa.
- `retirados_pela_recusa(estado: EstadoDoGoal, codigos_novos: Sequence[str]) -> dict[str, dict[str, str]]` — O Criterio dos planos recusados que o plano novo não traz mais, com a Decision do humano que o retirou.

## `orquestrador/resultado_de_teste.py`

O que a saída de um teste de aceite diz: passou de verdade, ou falhou pelo motivo certo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `RUNNER_DESCONHECIDO` | `str` | `'desconhecido'` |
| `CODIGOS_DE_COMANDO_AUSENTE` | `frozenset[int]` | `frozenset({126, 127})` |
| `CODIGO_DO_PYTEST_COM_FALHA` | `int` | `1` |
| `EXCECOES_DE_ASSERCAO` | `frozenset[str]` | `frozenset({'AssertionError', 'Failed', 'pytest.fail.Exception', '_pytes…` |
| `PALAVRAS_DE_PULO` | `re.Pattern[str]` | `re.compile('\\b(skip|skipped|skipping|xfail|xfailed|xpass|xpassed|todo|…` |
| `ERRO_FORA_DA_ASSERCAO` | `re.Pattern[str]` | `re.compile('\\b(ModuleNotFoundError|ImportError|SyntaxError|Indentation…` |
| `MARCAS_DE_FALHA` | `re.Pattern[str]` | `re.compile('^(FAILED|FAIL:|FAIL |not ok|\\s*[✖✕×●]|_{3,} |\\s*\\d+\\) )…` |
| `RUNNERS_NO_COMANDO` | `tuple[tuple[str, re.Pattern[str]], ...]` | `(('pytest', re.compile('\\b(pytest|py\\.test)\\b')), ('unittest', re.co…` |
| `LEITORES` | `tuple[Callable[[str], Contagem | None], ...]` | `(_pytest, _unittest, _node, _jest, _vitest, _mocha)` |
| `CORTE_DO_PYTEST` | `str` | `'...'` |

### `Contagem`

*DTO imutável* — Quantos testes passaram, falharam, deram erro e foram pulados, como o runner disse.

**Campos:** `runner: str`, `passados: int`, `falhos: int`, `erros: int`, `pulados: int`

### Funções do módulo

- `runner_do_comando(comando: str) -> str` — O runner que o comando chama, quando é um que o orquestrador conhece; senão, desconhecido.
- `ler_saida(saida: str) -> Contagem | None` — A contagem do primeiro runner conhecido cujo resumo está na saída; None quando nenhum está.
- `por_que_nao_passou(comando: str, codigo: int | None, saida: str) -> str` — Por que o teste não conta como verde; vazio quando conta.
- `por_que_o_vermelho_nao_vale(comando: str, codigo: int | None, saida: str) -> str` — Por que a falha não é a asserção do teste declarado; vazio quando é.

## `orquestrador/retirada_de_criterio.py`

Retirar um critério: a única saída do humano para fechar o Goal com um critério que a verificação reprova.

### Funções do módulo

- `no_do_criterio(estado: EstadoDoGoal, codigo: str) -> str` — O nó do critério do plano, pelo código; recusa o código que não é do plano.
- `descartes_da_retirada(view: GrafoView, id_criterio: str, motivo: str) -> list[ItemPatch]` — Os Achados abertos do orquestrador que ferem só o critério retirado, descartados com o motivo da retirada.
- `retirar_criterio(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None` — Grava no Criterio a retirada pela Decision do humano e a mostra no documento do Goal.
- `retirados(estado: EstadoDoGoal) -> list[Mapping[str, Any]]` — As retiradas que o laço já gravou, pela ordem dos pedidos atendidos.

## `orquestrador/revisao_da_fatia.py`

A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VEREDITO_APROVADO` | `str` | `'aprovado'` |

### `PedidoDeRevisao`

*DTO imutável* — A fatia a revisar, a tentativa em curso e por que ela é de risco.

**Campos:** `fatia: FatiaRegistrada`, `tentativa: int`, `motivo: str`, `referencia: str`

### `RejeicaoDaRevisao`

*DTO imutável* — A revisão rejeitou a entrega: os problemas, para a tentativa seguinte; eles já estão nos Achados da revisão.

**Campos:** `texto: str`

### Funções do módulo

- `de_risco(fatia: FatiaRegistrada) -> str` — Por que a fatia é de risco; vazio quando não é e não tem revisão.
- `revisar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> 'str | Parada | RejeicaoDaRevisao'` — A revisão da mudança fora de commit: vazio quando aprovada, os problemas quando rejeitada, ou a parada.
- `operacoes_dos_achados(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> list[ItemPatch]` — Na rejeição, cada problema vira nó Achado da revisão, com a gravidade do código; na aprovação, os de antes se resolvem.

## `orquestrador/saida_do_aceite.py`

A saída do autor de aceite e a conferência dela: a forma, o lugar dos testes e o vermelho de antes da implementação.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DO_ACEITE` | `str` | `'aceite'` |
| `PASTAS_DE_CACHE` | `frozenset[str]` | `frozenset({'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'…` |
| `SUFIXOS_DE_CACHE` | `tuple[str, ...]` | `('.pyc', '.pyo')` |
| `LIMITE_DA_SAIDA_REGISTRADA` | `int` | `600` |
| `TESTE_DO_COMANDO_DE_ACEITE` | `str` | `'comando_aceite'` |
| `TESTE_DA_SUITE_COM_O_ACEITE` | `str` | `'suite_e_aceite'` |
| `_PYTHON_NO_COMANDO` | `re.Pattern[str]` | `re.compile('(?P<antes>(?:^|&&|\\|\\||[;|(])\\s*(?:[A-Za-z_]\\w*=\\S*\\s…` |

### `AceiteDoCriterio`

*DTO imutável* — O que prova um critério: os testes, a checagem e, quando o código já o atendia, por quê.

**Campos:** `id: str`, `testes: tuple[TesteDeAceite, ...]`, `checagem: tuple[str, ...]`, `ja_atendido: str`

- `em_json() -> dict[str, Any]` — O aceite do critério para o livro-razão.

### `ExecucaoDeAceite`

*DTO imutável* — Um teste de aceite rodado pelo orquestrador: o critério, o teste, o comando e como saiu.

**Campos:** `criterio: str`, `teste: str`, `comando: str`, `codigo: int | None`, `saida: str`, `so_o_codigo: bool`

- `motivo() -> str` `[property]` — Por que o teste não conta como verde (saiu com erro, foi pulado, o runner não disse); vazio quando conta.
- `passou() -> bool` `[property]` — Saiu com zero e a saída do runner diz que passou, sem pular nada.
- `vermelho_invalido() -> str` — Por que a falha não é a asserção do teste declarado; vazio quando é.
- `em_json() -> dict[str, Any]` — A execução para o livro-razão.

### `SaidaDoAceite`

*DTO imutável* — O que o autor de aceite devolveu.

**Campos:** `resumo: str`, `comando_aceite: str`, `criterios: tuple[AceiteDoCriterio, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoAceite'` — A saída como o autor a devolveu, já conferida pelo schema; o teste sem comando ganha o do modelo.
- `do_livro(aceite: Mapping[str, Any] | None) -> 'SaidaDoAceite'` — Os testes de aceite como o Goal os guarda; vazio quando ainda não há.
- `do_criterio(id_criterio: str) -> AceiteDoCriterio | None` — O aceite de um critério, pelo código.
- `testes() -> Iterable[tuple[AceiteDoCriterio, TesteDeAceite]]` — Cada teste com o critério que ele prova.

### `TesteDeAceite`

*DTO imutável* — Um teste de aceite: o arquivo, o nome e o comando que roda só ele.

**Campos:** `arquivo: str`, `nome: str`, `comando: str`

- `em_json() -> dict[str, str]` — O teste para o livro-razão.

### Funções do módulo

- `conferir_forma(saida: SaidaDoAceite, criterios: Mapping[str, str], area: Path) -> tuple[str, ...]` — Uma entrada por critério do plano, o teste certo para o critério `teste`, a checagem para o `checagem` e tudo em aceite/.
- `e_cache(caminho: str) -> bool` — O caminho é de cache que a execução dos testes deixa (bytecode, cache do pytest, dependências instaladas).
- `dentro_do_aceite(caminho: str) -> bool` — O caminho, relativo à raiz, está na pasta dos testes de aceite.
- `sem_a_pasta_atual(comando: str) -> str` — O comando com `-P` em cada interpretador Python que ele chama: nem a pasta atual nem a do script entram no `sys.path`.
- `rodar_testes(saida: SaidaDoAceite, rodar: Rodar, criterios: Iterable[str] | None) -> tuple[ExecucaoDeAceite, ...]` — Cada teste de aceite dos critérios dados (todos, sem eles), rodado pelo comando dele, sem a pasta atual no caminho.
- `rodar_o_comando_de_aceite(saida: SaidaDoAceite, rodar: Rodar) -> ExecucaoDeAceite` — O comando que roda todos os testes de aceite, de uma vez, sem a pasta atual no caminho.
- `rodar_a_suite_com_o_aceite(saida: SaidaDoAceite, comando_suite: str, rodar: Rodar) -> ExecucaoDeAceite` — A suíte do projeto e todos os testes de aceite num comando só, com os arquivos de aceite na área.
- `conferir_vermelho(saida: SaidaDoAceite, rodar: Rodar) -> tuple[tuple[str, ...], tuple[ExecucaoDeAceite, ...]]` — Cada teste falha numa asserção dele antes da implementação, ou já passa com o porquê; devolve os problemas e as execuções.

## `orquestrador/saida_do_verificador.py`

A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ORIGEM_DO_VERIFICADOR` | `str` | `'verificador'` |
| `ORIGEM_DO_ORQUESTRADOR` | `str` | `'orquestrador'` |
| `ORIGEM_DA_REVISAO` | `str` | `'revisao_de_risco'` |
| `TITULO_DA_SUITE_VERMELHA` | `str` | `'A suite do plano falhou no commit verificado'` |
| `LIMITE_DA_PROVA` | `int` | `2000` |
| `PARECER_LEGITIMA` | `str` | `'legitima'` |
| `PARECER_ILEGITIMA` | `str` | `'ilegitima'` |
| `PARECERES_DA_DIFERENCA` | `tuple[str, ...]` | `(PARECER_LEGITIMA, PARECER_ILEGITIMA)` |
| `ALCANCE_USO_PREVISTO` | `str` | `'uso_previsto'` |
| `ALCANCE_EXTREMO` | `str` | `'extremo'` |
| `ALCANCES` | `tuple[str, ...]` | `(ALCANCE_USO_PREVISTO, ALCANCE_EXTREMO)` |
| `TETO_DE_BLOQUEANTES` | `int` | `5` |
| `MARCA_DO_TETO` | `str` | `'excedeu o teto do ciclo'` |
| `MARCA_DA_CONFERENCIA` | `str` | `'achado novo da conferencia, sem regressao'` |
| `MARCA_DA_REGRESSAO` | `str` | `'regressao nao confirmada'` |
| `MARCA_DO_PARECER` | `str` | `'reprovado na conferencia sem achado que bloqueie; vale o parecer anter…` |
| `MARCA_DO_CORRIGIDO` | `str` | `'reprovado na conferencia sem achado que bloqueie; o que o reprovava fo…` |
| `PARECER_CORRIGIDO` | `str` | `'corrigido'` |
| `PARECER_PERSISTE` | `str` | `'persiste'` |
| `PARECERES_DO_CONFERIDO` | `tuple[str, ...]` | `(PARECER_CORRIGIDO, PARECER_PERSISTE)` |

### `Achado`

*DTO imutável* — Um problema achado na verificação: o que é, a prova, onde, o que ele toca, o alcance e de quem veio.

**Campos:** `titulo: str`, `descricao: str`, `prova: str`, `local: str`, `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`, `severidade: str`, `origem: str`, `segunda_opiniao: str`, `sem_acordo: bool`, `reproducao: tuple[str, ...]`, `alcance: str`, `decisao_do_limite: str`, `alcance_da_segunda_opiniao: str`, `excedeu_o_teto: bool`, `persiste: str`, `regressao: bool`, `rebaixado_na_conferencia: str`

- `toca() -> tuple[str, ...]` `[property]` — Os critérios e as decisões que o achado toca, sem repetir; a decisão que fala do limite inclusive.
- `extremo() -> bool` `[property]` — Entrada extrema de cujo limite nenhuma decisão fala, sem a segunda opinião dizer que é de uso previsto.
- `gravidade() -> str` `[property]` — Bloqueante quando o orquestrador viu falhar, quando a segunda opinião não concordou ou quando toca algo e não é extremo.
- `em_json() -> dict[str, Any]` — O achado para a lista de pendências e para o nó Achado.
- `marca() -> str` `[property]` — Por que o código rebaixou o achado que tocava algo; vazio quando não rebaixou.
- `de_json(dados: Mapping[str, Any]) -> 'Achado'` — O achado como o verificador o devolveu; sem alcance, de uso previsto.

### `ComandoRodado`

*DTO imutável* — Um comando que o verificador rodou: o que, com que código saiu e um trecho do que imprimiu.

**Campos:** `comando: str`, `codigo: int`, `saida: str`

- `em_json() -> dict[str, Any]` — O comando para gravar na Evidence.

### `Parecer`

*DTO imutável* — O veredito do verificador sobre um critério ou uma decisão, com a prova.

**Campos:** `id: str`, `veredito: str`, `prova: str`

### `ParecerDaDiferenca`

*DTO imutável* — O que o verificador julgou de um teste de aceite que só passa com a configuração entregue.

**Campos:** `criterio: str`, `teste: str`, `parecer: str`, `motivo: str`

- `chave() -> tuple[str, str]` `[property]` — O critério e o teste, como a diferença os tem.
- `em_json() -> dict[str, str]` — O parecer para gravar com a diferença.
- `de_json(dados: Mapping[str, Any]) -> 'ParecerDaDiferenca'` — O parecer como o verificador o devolveu.

### `ParecerDoConferido`

*DTO imutável* — O que a conferência diz de um achado conferido: corrigido ou persiste, com a prova.

**Campos:** `achado: str`, `parecer: str`, `prova: str`

- `persiste() -> bool` `[property]` — A conferência reproduziu o achado.
- `em_json() -> dict[str, str]` — O parecer para gravar na verificação.
- `de_json(dados: Mapping[str, Any]) -> 'ParecerDoConferido'` — O parecer como a conferência o devolveu.

### `Verificacao`

*DTO imutável* — O que o verificador devolveu de um marco, ou do Goal inteiro na verificação final.

**Campos:** `resumo: str`, `criterios: tuple[Parecer, ...]`, `decisoes: tuple[Parecer, ...]`, `achados: tuple[Achado, ...]`, `comandos: tuple[ComandoRodado, ...]`, `diferencas: tuple[ParecerDaDiferenca, ...]`, `conferidos: tuple[ParecerDoConferido, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Verificacao'` — A verificação como o verificador a devolveu.
- `confirmados() -> tuple[str, ...]` `[property]` — Os achados conferidos que a conferência deu por corrigidos.
- `com_achado_do_orquestrador(titulo: str, descricao: str, criterios: tuple[str, ...]) -> 'Verificacao'` — A verificação com o que o orquestrador viu falhar no commit verificado (a suíte, um teste de aceite).
- `com_parecer(id_criterio: str, veredito: str, prova: str) -> 'Verificacao'` — A verificação com o parecer do critério trocado pelo que o orquestrador viu.
- `bloqueantes() -> tuple[Achado, ...]` — Os bloqueantes dentro do teto, na ordem de sempre.
- `acompanhamentos() -> tuple[Achado, ...]` — Os achados que não tocam critério nem decisão, os de entrada extrema e, marcados, os bloqueantes que passaram do teto.
- `achados_finais() -> tuple[Achado, ...]` — Os bloqueantes e depois os acompanhamentos, na ordem em que viram nós Achado.

### Funções do módulo

- `alcance_de(valor: object) -> str` — O alcance dito; o que falta ou não é um dos dois é uso previsto, o que não rebaixa nada.
- `conferir_verificacao(verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str]) -> tuple[str, ...]` — Um parecer por critério, por decisão e por diferença de configuração pedidos, e achado que toca só o que pode tocar.

## `orquestrador/saidas.py`

A saída de cada papel como objeto tipado, com a conferência que o schema não faz.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `STATUS_DUVIDA` | `str` | `'duvida'` |
| `STATUS_TESTE_ERRADO` | `str` | `'teste_errado'` |
| `MARCO_UNICO` | `str` | `'M1'` |

### `Criterio`

*DTO imutável* — Um critério de aceite: id (C1...), texto completo e como se prova.

**Campos:** `id: str`, `texto: str`, `verificacao: str`

### `Decisao`

*DTO imutável* — Uma decisão que o trabalho segue, com o motivo.

**Campos:** `id: str`, `texto: str`, `motivo: str`

### `Fatia`

*DTO imutável* — Uma fatia vertical do plano: o que entrega, que critérios cobre, onde mexe e de que depende.

**Campos:** `id: str`, `titulo: str`, `objetivo: str`, `criterios: tuple[str, ...]`, `arquivos: tuple[str, ...]`, `depende_de: tuple[str, ...]`, `modelo: str`, `risco: bool`, `motivo_do_risco: str`

- `de_json(dados: Mapping[str, Any]) -> 'Fatia'` — A fatia como o planejador a devolveu.

### `IdsFixados`

*DTO imutável* — Os critérios e as decisões que o Goal já trazia (do gerente): o plano os mantém com o mesmo id.

**Campos:** `criterios: tuple[str, ...]`, `decisoes: tuple[str, ...]`

### `Marco`

*DTO imutável* — Um marco do plano: as fatias que, juntas, entregam critérios verificáveis.

**Campos:** `id: str`, `titulo: str`, `fatias: tuple[str, ...]`

### `Plano`

*DTO imutável* — O plano do Goal: título, comando da suíte, critérios, decisões, fatias e os marcos que as repartem.

**Campos:** `titulo: str`, `comando_suite: str`, `criterios: tuple[Criterio, ...]`, `decisoes: tuple[Decisao, ...]`, `fatias: tuple[Fatia, ...]`, `fora_do_escopo: tuple[str, ...]`, `marcos: tuple[Marco, ...]`

- `de_json(dados: Mapping[str, Any]) -> 'Plano'` — O plano como o planejador o devolveu, já conferido pelo schema.
- `marco_da_fatia(id_fatia: str) -> str` — O marco em que a fatia está; vazio quando nenhum a traz.
- `criterios_do_marco(id_marco: str) -> tuple[str, ...]` — Os critérios que o marco completa (a última fatia que os cobre está nele); no último, todos.
- `com_criterios_do_humano(criterios: Sequence[Criterio]) -> 'Plano'` — O plano com o texto e o tipo de verificação dos critérios que o humano fixou, como ele os escreveu.

### `SaidaDoExecutor`

*DTO imutável* — O que o executor devolveu da fatia.

**Campos:** `status: str`, `resumo: str`, `arquivos: tuple[str, ...]`, `testes: tuple[str, ...]`, `duvida: str`, `teste_errado: str`, `decisoes: tuple[Mapping[str, Any], ...]`

- `de_json(dados: Mapping[str, Any]) -> 'SaidaDoExecutor'` — A saída como o executor a devolveu.
- `conferir() -> tuple[str, ...]` — A dúvida precisa da pergunta; o teste errado, do critério e do porquê.

### Funções do módulo

- `conferir_plano(plano: Plano, fixados: IdsFixados) -> tuple[str, ...]` — Os problemas de sentido do plano; vazio quando ele pode ser gravado.

## `orquestrador/salvaguarda_do_humano.py`

A salvaguarda do repositório do humano, guardada fora dele: a recuperação sobrevive a um `git gc --prune=now`.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DA_SALVAGUARDA` | `str` | `'salvaguarda-do-humano'` |
| `PASTA_DOS_SOLTOS` | `str` | `'soltos'` |
| `MENSAGEM_DA_SALVAGUARDA` | `str` | `'graphow: salvaguarda do repositorio do humano antes da sessao'` |
| `MODO_DO_SOLTO` | `str` | `'100644'` |
| `CONFIGURACAO_DA_PASTA` | `str` | `'[uploadpack]\n\tallowAnySHA1InWant = true\n'` |

### `PedidoDeSalvaguarda`

*DTO imutável* — O que guardar do repositório do humano: o arquivo do índice e a pasta de objetos dele, o commit do HEAD, se há

**Campos:** `repositorio: Path`, `indice: Path`, `objetos: Path`, `head: str`, `rastreado: bool`, `soltos: tuple[str, ...]`

### `Salvaguarda`

*DTO imutável* — O commit de `git stash create` com as mudanças rastreadas, a árvore com os blobs dos não rastreados e a pasta que os

**Campos:** `stash: str`, `soltos: str`, `pasta: str`

### Funções do módulo

- `salvaguardar(pedido: PedidoDeSalvaguarda, pasta: Path) -> Salvaguarda` — A salvaguarda na pasta, fora do repositório do humano; vazia, sem processo, quando não há o que guardar.
- `comandos_de_recuperacao(repositorio: Path, salvaguarda: Salvaguarda, soltos: Sequence[str]) -> tuple[str, ...]` — O `fetch` que traz da pasta os objetos, o `stash apply` do rastreado e o `restore` dos não rastreados que sumiram.

## `orquestrador/sed_e_awk.py`

Quando o `sed` e o `awk` rodam comando: a trava os trata como texto que ela não lê (orquestrador/git_no_comando.py).

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SED_QUE_RODA` | `re.Pattern[str]` | `re.compile('(?:^|[^A-Za-z0-9_\\\\])[gpiImM0-9]*e(?:$|[\\s;}])')` |
| `AWK_QUE_RODA` | `re.Pattern[str]` | `re.compile('system|\\|')` |
| `OPCOES_COM_PROGRAMA_DO_SED` | `frozenset[str]` | `frozenset({'-e', '--expression'})` |
| `OPCOES_COM_VALOR_DO_SED` | `frozenset[str]` | `frozenset({'-f', '--file', '-l', '--line-length'})` |
| `OPCOES_COM_VALOR_DO_AWK` | `frozenset[str]` | `frozenset({'-F', '-v', '-f'})` |

### Funções do módulo

- `sed_roda_comando(argumentos: tuple[Palavra, ...]) -> bool` — O sed tem `e` no programa, ou um programa que só se sabe ao rodar.
- `awk_roda_comando(argumentos: tuple[Palavra, ...]) -> bool` — O awk tem `system` ou `|` no programa, ou um programa que só se sabe ao rodar.

## `orquestrador/segunda_opiniao.py`

A segunda opinião sobre o achado que uma opinião só rebaixaria: rebaixá-lo a acompanhamento exige que dois concordem.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MOTIVO_SEM_RESPOSTA` | `str` | `'a segunda opiniao nao respondeu: sem acordo, o achado nao se rebaixa'` |

### Funções do módulo

- `com_a_segunda_opiniao(contexto: ContextoDoGoal, verificacao: Verificacao) -> Verificacao` — A verificação com cada achado que uma opinião só rebaixaria julgado de novo, numa sessão própria, contra os critérios e decisões dados.
- `briefing_da_segunda_opiniao(achado: Achado, textos: Mapping[str, str]) -> str` — O pedido: os critérios e as decisões com o texto, e o achado inteiro, com o que o verificador citou e sem o alcance dele.

## `orquestrador/sessoes_de_papel.py`

A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `FERRAMENTAS_POR_PAPEL` | `Mapping[str, tuple[str, ...]]` | `{PAPEL_PLANEJADOR: ('Bash', 'Read', 'Glob', 'Grep'), PAPEL_AUTOR_DE_ACE…` |
| `MODO_DE_PERMISSAO_PADRAO` | `str` | `'bypassPermissions'` |
| `MODELO_PADRAO` | `str` | `'opus'` |
| `RECUOS_DO_ERRO_DA_API_S` | `tuple[float, ...]` | `(30.0, 120.0, 300.0)` |
| `MODELOS_PADRAO_POR_PAPEL` | `Mapping[str, str]` | `{PAPEL_AUTOR_DE_ACEITE: 'sonnet', PAPEL_SEGUNDA_OPINIAO: 'sonnet', PAPE…` |
| `FONTES_DE_CONFIGURACAO` | `str` | `'project'` |
| `ORCAMENTO_MINIMO_DA_SESSAO_USD` | `float` | `0.05` |

### `ConfiguracaoDasSessoes`

*DTO imutável* — O que vale para toda sessão de agente do Goal.

**Campos:** `pasta_das_sessoes: Path`, `ambiente_da_trava: Mapping[str, str]`, `hook_da_trava: Path`, `modelos: Mapping[str, str]`, `modo_de_permissao: str`, `tempo_limite_s: float`, `banco_dos_hooks: Path | None`, `esperar: Callable[[float], None]`, `recuos_s: tuple[float, ...]`, `registrar_trava_mexida: RegistroDaTravaMexida | None`, `repositorio_do_humano: Path | None`, `registrar_humano_mexido: RegistroDoHumanoMexido | None`, `salvaguarda_do_humano: Path | None`

### `PedidoDePapel`

*DTO imutável* — Uma sessão a rodar: o papel, onde, com que briefing e como conferir a saída.

**Campos:** `papel: str`, `id_goal: str`, `pasta: Path`, `briefing: str`, `conferir: Conferencia`, `fatia: str`, `tentativa: int`, `modelo: str`, `orcamento_restante_usd: float`, `comandos_declarados: Callable[[Mapping[str, Any]], Sequence[str]] | None`, `retomadas: int`, `esquema: Mapping[str, Any] | None`, `exige_bash: bool`, `referencia_do_selo: str`

- `schema() -> Mapping[str, Any]` `[property]` — O schema da saída: o do pedido (o executor do modo autônomo tem o dele) ou o do papel.

### `RespostaDePapel`

*DTO imutável* — A saída conferida, ou os problemas que sobraram, e as invocações que rodaram.

**Campos:** `dados: Mapping[str, Any] | None`, `problemas: tuple[str, ...]`, `resultados: tuple[ResultadoDeSessao, ...]`, `desfeito: str`, `trava_mexida: str`

### `SessoesDePapel`

*serviço* — Roda as sessões dos papéis e registra cada invocação na telemetria.

- `modelo_do_papel(papel: str) -> str` — O modelo configurado para o papel; Opus quando a configuração não diz.
- `rodar(pedido: PedidoDePapel) -> RespostaDePapel` — A sessão conferida, e o clone deixado como estava antes dela, mesmo quando a API a recusa; o humano conferido.

### `_TravaMexida` (RuntimeError)

*serviço* — A invocação mexeu no settings do hook ou no `.claude/` do clone: a sessão para ali.

### Funções do módulo

- `modelo_padrao(papel: str) -> str` — O modelo do papel quando a chamada não diz outro.
- `argumentos_do_papel(papel: str, orcamento_restante_usd: float) -> tuple[str, ...]` — O que o comando da sessão leva além do que o pedido de sessão já nomeia; a lista variádica vai por último.
- `ler_saida(resultado: ResultadoDeSessao, pedido: PedidoDePapel) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]` — O JSON da sessão conferido, ou os problemas: o `structured_output`, senão o texto final como JSON.
- `saida_conferida_da_telemetria(registros: Sequence[SessaoRegistrada], papel: str, problemas: Conferencia) -> Mapping[str, Any] | None` — A saída mais nova do papel, relida do stream gravado, que passa na conferência; None sem nenhuma.
- `registro_em_andamento(pedido: PedidoDePapel, arquivo: Path) -> SessaoRegistrada` — A linha da invocação antes de a sessão abrir: quem, onde e desde quando.
- `com_o_resultado(aberta: SessaoRegistrada, resultado: ResultadoDeSessao) -> SessaoRegistrada` — A linha da invocação com o fim dela; a sessão retomada que morreu sem dizer o id fica com o id retomado.
- `recuperar_sessoes_em_andamento(telemetria: RepositorioTelemetria, id_goal: str) -> int` — As linhas que ficaram em andamento porque o orquestrador caiu; devolve quantas recuperou.
- `resultados_da_telemetria(registros: Sequence[SessaoRegistrada]) -> tuple[ResultadoDeSessao, ...]` — As invocações relidas dos streams gravados, como a bancada as mede.

## `orquestrador/spec_do_goal.py`

A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro.

### `SpecDoGoal`

*DTO imutável* — O texto da spec, os ids que o plano tem de manter e o nó de cada um.

**Campos:** `texto: str`, `fixados: IdsFixados`, `nos_fixados: dict[str, str]`, `criterios_do_humano: tuple[Criterio, ...]`

### Funções do módulo

- `montar_spec_do_goal(view: GrafoView, id_goal: str) -> SpecDoGoal` — A spec do Goal a partir do grafo, com os critérios e as decisões numerados.

## `orquestrador/status.py`

O `--status` do orquestrador: onde o Goal está, o que prova que ele está pronto, o que cada fatia fez e quanto custou.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEGUNDOS_POR_MINUTO` | `float` | `60.0` |

### Funções do módulo

- `formatar_status(estado: EstadoDoGoal, registros: Sequence[SessaoRegistrada]) -> list[str]` — As linhas do status do Goal.

## `orquestrador/suite.py`

A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `VARIAVEL_DO_SHELL` | `str` | `'GRAPHOW_SHELL'` |
| `VARIAVEL_DO_GIT_BASH` | `str` | `'CLAUDE_CODE_GIT_BASH_PATH'` |
| `SHELL_DA_MAQUINA` | `str` | `'o shell da maquina (cmd no Windows, /bin/sh fora dele)'` |
| `TEMPO_LIMITE_DA_SUITE_S` | `float` | `1800.0` |
| `LIMITE_DA_SAIDA` | `int` | `20000` |
| `BYTES_DE_CONTINUACAO` | `bytes` | `bytes(range(128, 192))` |
| `LIMITE_DO_TRECHO` | `int` | `2000` |
| `AMBIENTE_SEM_CACHE` | `dict[str, str]` | `{'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_ADDOPTS': '-p no:cacheprovider…` |
| `FORA_DO_AMBIENTE_DO_ACEITE` | `frozenset[str]` | `frozenset({'PYTHONPATH'})` |

### `ResultadoDaSuite`

*DTO imutável* — Como a suíte terminou e o fim do que ela imprimiu.

**Campos:** `comando: str`, `codigo: int | None`, `saida: str`, `tempo_esgotado: bool`, `shell: str`

- `passou() -> bool` `[property]` — Saiu com zero dentro do tempo.
- `descrever() -> str` — O resultado para o briefing da nova tentativa.

### Funções do módulo

- `shell_dos_agentes() -> Path | None` — O bash em que a ferramenta Bash das sessões roda; None quando a máquina não tem um.
- `descrever_shell(shell: Path | None) -> str` — O shell da suíte em palavras, para o briefing e para o resultado.
- `rodar_suite(area: Path, comando: str, banco_descartavel: Path) -> ResultadoDaSuite` — Roda o comando na área, no shell dos agentes, e devolve o resultado; o do aceite, sem o `PYTHONPATH` herdado.
- `arquivos_ocultos(area: Path, arquivos: Sequence[str], guarda: Path) -> Iterator[None]` — Tira da área os arquivos dados enquanto o bloco roda e os devolve depois, mesmo se o bloco falhar.

## `orquestrador/suite_sem_rastro.py`

A suíte que o orquestrador roda não deixa rastro na área: o que ela escreve nunca entra num commit do laço.

### Funções do módulo

- `sem_o_que_a_suite_escreve(area: Path, arquivo_patch: Path) -> Iterator[None]` — Guarda a árvore da área antes do bloco e a devolve depois dele, com o que o bloco escreveu no .patch dado.
- `guardar_a_arvore(area: Path) -> str` — O hash da árvore da área como está, os arquivos novos inclusive; o índice fica como estava.
- `voltar_a_arvore(area: Path, arvore: str, arquivo_patch: Path) -> bool` — A área de volta à árvore dada, sem tocar nos ignorados, e o índice ao dado; o que mudou vai ao .patch. Diz se havia o que desfazer.

## `orquestrador/tipo_da_verificacao.py`

O tipo de cada verificação: a caçada uma vez, na primeira final; a do marco intermediário; a conferência depois de cada correção.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPO_CACA` | `str` | `'caca'` |
| `TIPO_MARCO` | `str` | `'marco'` |
| `TIPO_CONFERENCIA` | `str` | `'conferencia'` |
| `TIPOS_DE_VERIFICACAO` | `tuple[str, ...]` | `(TIPO_CACA, TIPO_MARCO, TIPO_CONFERENCIA)` |
| `PAPEL_DO_TIPO` | `Mapping[str, str]` | `{TIPO_CACA: PAPEL_VERIFICADOR, TIPO_MARCO: PAPEL_VERIFICADOR_DO_MARCO, …` |

### `TipoDaVerificacao`

*DTO imutável* — O tipo da verificação que o laço vai rodar e, na conferência, de onde ela partiu e a regra com os fatos dela.

**Campos:** `tipo: str`, `antes: str`, `regra: RegraDaConferencia`

- `papel() -> str` `[property]` — O papel da sessão: o prompt, o schema e o modelo do tipo.
- `conferidos() -> tuple[AchadoRegistrado, ...]` `[property]` — Os achados que as correções trataram: cada um pede um parecer.
- `excedentes() -> tuple[AchadoRegistrado, ...]` `[property]` — Os excedentes do teto ainda pendentes, que a conferência pode citar em `persiste`.
- `ids_dos_conferidos() -> tuple[str, ...]` `[property]` — Os ids dos achados que a conferência confere: cada um pede um parecer.
- `ids_dos_excedentes() -> tuple[str, ...]` `[property]` — Os ids dos excedentes do teto que a conferência pode citar em `persiste`.
- `conferencia() -> bool` `[property]` — É a conferência de depois de uma correção.
- `ajustar(verificacao: Verificacao) -> Verificacao` — Na conferência, cada achado do verificador com o destino dela; nos outros tipos, como veio.
- `sustentar(verificacao: Verificacao) -> Verificacao` — Na conferência, o reprovado que a regra dá por `atende` sai `atende` (`RegraDaConferencia.com_os_pareceres`); nos outros, como veio.

### Funções do módulo

- `escolher_o_tipo(estado: EstadoDoGoal, marco: MarcoRegistrado, git: GitDoGoal | None) -> TipoDaVerificacao` — A conferência quando o marco já tem verificação gravada; senão a do marco intermediário, ou a caçada na final.
- `pareceres_gravados(itens: object) -> tuple[Parecer, ...]` — Os pareceres de critério e de decisão como a verificação os gravou.
- `criterios_em_desacordo(estado: EstadoDoGoal) -> frozenset[str]` — Os critérios cujo teste de aceite está em desacordo: o autor manteve o que o executor disse errado, ou o refazer ficou com o antigo.
- `arquivos_por_criterio(estado: EstadoDoGoal, git: GitDoGoal) -> dict[str, frozenset[str]]` — Os arquivos de cada critério do plano: os das fatias do plano dele, os previstos e os que os commits delas mudaram.
- `arquivos_dos_criterios(estado: EstadoDoGoal, git: GitDoGoal) -> frozenset[str]` — Os arquivos que algum critério cobre: os das fatias do plano dele (previstos e commitados) e os testes de aceite.
- `na_conferencia(verificacao: Verificacao, regra: RegraDaConferencia) -> Verificacao` — A conferência com o destino de cada achado do verificador e um bloqueante por conferido que persiste.

## `orquestrador/trava_do_git.py`

A trava do git nas sessões de agente: as regras, o ambiente e a restauração do clone depois de cada sessão.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `HOOKS_DA_TRAVA` | `Mapping[str, str]` | `{'reference-transaction': '#!/bin/sh\n# Trava do graphow orquestrar: a …` |
| `SUBCOMANDOS_DE_ESCRITA` | `tuple[str, ...]` | `('commit', 'push', 'pull', 'fetch', 'reset', 'checkout', 'switch', 'res…` |
| `OPCOES_GLOBAIS_NAS_REGRAS` | `tuple[str, ...]` | `('--exec-path',)` |
| `MODULO_DO_HOOK` | `str` | `'graphow.orquestrador.hook_do_git'` |
| `ARQUIVO_DO_HOOK` | `str` | `'settings-da-trava.json'` |
| `TEMPO_LIMITE_DO_HOOK_S` | `int` | `30` |
| `PASTA_DO_CLAUDE` | `str` | `':(icase).claude'` |
| `INSTRUCOES_DO_CLAUDE` | `tuple[str, ...]` | `('CLAUDE.md', 'CLAUDE.local.md')` |
| `CAMINHOS_DO_CLAUDE` | `tuple[str, ...]` | `(PASTA_DO_CLAUDE, *(f':(icase,glob)**/{nome}' for nome in INSTRUCOES_DO…` |
| `RAIZ_DO_PACOTE` | `Path` | `Path(__file__).resolve().parents[2]` |

### `FotoDoClone`

*DTO imutável* — O clone antes de uma sessão de agente: a branch do HEAD, as refs e a configuração.

**Campos:** `area: Path`, `ramo: str`, `refs: Mapping[str, str]`, `configuracao: bytes`

- `ref_do_ramo() -> str` `[property]` — A ref da branch do Goal.

### `SeloDaSessao`

*DTO imutável* — O settings do hook como foi gravado antes da invocação, o clone onde ela roda e a referência do `.claude/`.

**Campos:** `hook: Path`, `sha256: str`, `area: Path`, `referencia: str`

### Funções do módulo

- `instalar_trava(pasta: Path) -> dict[str, str]` — Grava os hooks da trava na pasta e devolve o ambiente que a liga numa sessão de agente.
- `configuracao_do_hook(python: str, raiz: Path) -> dict[str, Any]` — O settings do Claude Code que liga o hook PreToolUse da trava a cada comando Bash.
- `gravar_hook_da_trava(pasta: Path) -> Path` — Grava o settings do hook na pasta de estado do Goal e devolve o caminho, que vai no `--settings` da sessão.
- `selar_a_sessao(hook: Path, area: Path, referencia: str) -> SeloDaSessao` — Antes de cada invocação: o settings do hook regravado, o `.claude/` e os CLAUDE.md do clone como na referência.
- `trava_mexida(selo: SeloDaSessao) -> str` — Depois da invocação: o que ela mexeu no settings do hook, no `.claude/` ou nos CLAUDE.md; vazio quando nada.
- `claude_mexido(area: Path, referencia: str) -> tuple[str, ...]` — Os arquivos do `.claude/` e os CLAUDE.md do clone fora da referência: mudados, apagados, novos e ignorados.
- `instrucoes_do_estado(hook: Path) -> tuple[Path, ...]` — Os CLAUDE.md e CLAUDE.local.md, em qualquer caixa, da pasta de estado do Goal (a do settings do hook) e da de cima.
- `regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]` — As regras `--disallowedTools` do git de escrita e do `--exec-path`.
- `fotografar_clone(area: Path) -> FotoDoClone` — A foto do clone, tirada logo antes da sessão.
- `restaurar_o_clone(foto: FotoDoClone) -> str` — Deixa o clone como a foto: a branch do Goal, as outras refs, a configuração e os hooks; diz o que desfez.

## `orquestrador/trava_do_goal.py`

Um orquestrador por Goal: a trava que impede duas execuções de `graphow orquestrar` no mesmo Goal.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOME_DA_TRAVA` | `str` | `'orquestrar.trava'` |
| `TENTATIVAS` | `int` | `3` |
| `PAUSA_ENTRE_TENTATIVAS_S` | `float` | `0.05` |
| `CONSULTA_LIMITADA` | `int` | `4096` |
| `AINDA_ATIVO` | `int` | `259` |
| `ACESSO_NEGADO` | `int` | `5` |
| `FILETIME_POR_SEGUNDO` | `int` | `10000000` |
| `FILETIME_DA_EPOCA_UNIX` | `int` | `116444736000000000` |
| `FOLGA_DA_CRIACAO_S` | `float` | `2.0` |

### `DonoDaTrava`

*DTO imutável* — Quem tomou a trava: o processo, a máquina, desde quando, com que comando e a ficha que a distingue.

**Campos:** `pid: int`, `maquina: str`, `inicio: str`, `comando: str`, `ficha: str`, `criacao: float | None`

- `descrever() -> str` — O dono como a mensagem o mostra.

### `GoalOcupado` (GraphowError)

*serviço* — Outra execução de `graphow orquestrar` conduz o Goal, ou a trava dele não dá para ler ou tomar.

### `TravaDoGoal`

*DTO imutável* — A trava tomada: onde ela está, de quem é e o aviso da trava velha que foi liberada para tomá-la.

**Campos:** `caminho: Path`, `dono: DonoDaTrava`, `aviso: str`

### Funções do módulo

- `conduzindo(pasta: Path, id_goal: str) -> Iterator[TravaDoGoal]` — A trava do Goal durante o bloco; ela é solta no fim, inclusive por exceção ou parada.
- `tomar_trava(pasta: Path, id_goal: str) -> TravaDoGoal` — Toma a trava do Goal na pasta de estado dele, liberando a velha desta máquina; `GoalOcupado` quando outra vale.
- `soltar_trava(trava: TravaDoGoal) -> None` — Solta a trava se ela ainda é desta execução (a ficha confere); no Windows, espera quem a lê fechar o arquivo.
- `ler_dono(caminho: Path) -> DonoDaTrava | None` — Quem tem a trava; None sem trava, ou com uma que não dá para ler (vazia, corrompida ou de outro formato).
- `processo_vivo(pid: int) -> bool` — O processo de PID dado existe nesta máquina (no POSIX, o sinal 0; no Windows, OpenProcess, que não mata nada).
- `hora_de_criacao(pid: int) -> float | None` — Quando o processo do PID foi criado, em segundos da época do Unix; None quando não dá para ler.

## `orquestrador/validacao_json.py`

Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `TIPOS_DO_JSON` | `Mapping[str, tuple[type, ...]]` | `{'object': (dict,), 'array': (list,), 'string': (str,), 'integer': (int…` |

### Funções do módulo

- `validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str) -> tuple[str, ...]` — Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere.

## `orquestrador/verificacao_do_goal.py`

O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal.

### Funções do módulo

- `verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None` — Com as fatias do marco concluídas: verifica o commit atual, abre correções, segue ao próximo marco ou fecha.

## `orquestrador/verificacao_do_marco.py`

A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão.

### Funções do módulo

- `verificar_marco(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None` — Uma sessão nova do verificador no commit atual e a suíte do plano, gravadas como Evidence do Goal.
- `arquivos_da_entrega(contexto: ContextoDoGoal, commit: str) -> tuple[str, ...]` — Os arquivos que a entrega do Goal mudou da base ao commit verificado: o que a Evidence da verificação afirma.
- `criterios_ate_o_marco(estado: EstadoDoGoal, marco: MarcoRegistrado) -> tuple[str, ...]` — Os critérios que os marcos até este, inclusive, completaram: os que já podem ser julgados ou feridos.
- `decisoes_do_plano(estado: EstadoDoGoal) -> tuple[str, ...]` — Os ids das decisões do plano.
- `nos_do_plano(plano: Mapping[str, Any]) -> dict[str, str]` — O nó do livro-razão de cada critério e decisão do plano, pelo código.
- `sincronizar_documento(contexto: ContextoDoGoal, pendencias: Sequence[Mapping[str, Any]]) -> None` — Reescreve a seção de pendências do documento como o livro-razão a tem e commita só ele, pelo caminho, se ele mudou.

## `orquestrador/vermelho_do_rebase.py`

O que fica vermelho depois do rebase: a suíte do plano e os testes de aceite, na configuração entregue.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `MOTIVO_DA_SUITE` | `str` | `'suite_vermelha'` |
| `MOTIVO_DO_ACEITE` | `str` | `'aceite_vermelho'` |
| `LIMITE_DA_SAIDA` | `int` | `1500` |

### `Vermelho`

*DTO imutável* — O que ficou vermelho depois do rebase: o motivo que a fatia de conflito grava, a frase, o fim da saída e os critérios.

**Campos:** `motivo: str`, `resumo: str`, `detalhe: str`, `criterios: tuple[str, ...]`

### Funções do módulo

- `da_suite(suite: ResultadoDaSuite) -> Vermelho` — A suíte do plano que ficou vermelha.
- `aceite_vermelho(contexto: ContextoDoGoal, estado: EstadoDoGoal, rastro: Path) -> Vermelho | None` — Os testes de aceite de todos os critérios na área como ela está, sem rastro; None quando todos passam.

## `orquestrador/vermelho_do_refeito.py`

O teste de aceite refeito só vale se falhar contra o código de antes da implementação.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PASTA_DO_CHECKOUT` | `str` | `'antes-do-refeito'` |

### Funções do módulo

- `commit_de_antes(contexto: ContextoDoGoal, estado: EstadoDoGoal, criterio: str) -> str` — O commit anterior à primeira fatia que cobre o critério, achada pelo trailer; a ponta, quando nenhuma delas commitou.
- `checkout_de_antes(area: Path, destino: Path, commit: str) -> Iterator[Path]` — Um clone local da área no commit dado, com o `aceite/` da área por cima; sai no fim, mesmo quando o bloco falha.
- `conferir_o_vermelho_de_antes(contexto: ContextoDoGoal, estado: EstadoDoGoal, refeito: SaidaDoAceite) -> tuple[str, ...]` — Os testes refeitos do critério que não falham numa asserção contra o código de antes; vazio quando todos falham.

