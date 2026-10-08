# Especificação Formal da Ontologia — Graphow

Especificação semântica do grafo agêntico bilateral para alinhamento entre humanos e agentes de inteligência artificial.

---

## 1. Princípios da Ontologia

1. **Separação em Duas Camadas**:
   - **Camada de Navegação**: Espinha dorsal visual e de agrupamento hierárquico (`Projeto` → `Setor` → `Sessao`). O humano cria e estrutura a navegação; um agente só a estrutura onde a política de governança do projeto põe o gesto `estrutura` em `ilimitado` (seção 5). O nó `Governanca`, que guarda essa política, é raiz como o `Projeto` e fica fora da hierarquia.
   - **Camada de Trabalho**: Nós semânticos de intenção, execução e evidência pendurados exclusivamente em instâncias de `Sessao`. Tanto humanos quanto agentes interagem com a camada de trabalho.
   - **Nenhum nó nasce solto**: exceto `Projeto`, todo nó criado termina o lote com uma aresta de contenção chegando nele (`contem`, `produz` ou `decompoe`). O `InvariantGate` lê o estado depois do lote e recusa com `no_fora_da_hierarquia` para qualquer papel, humano incluído; um agente também não solta da hierarquia um nó que já existia.
   - **Memória diz de onde veio**: o `Aprendizado` é o único nó de trabalho que atravessa a hierarquia, e por isso é o único que nasce apontando obrigatoriamente para a origem. Sem uma aresta `deriva_de` ao fim do lote que o cria, o `InvariantGate` recusa com `aprendizado_sem_origem`, e um agente não tira a última origem de um que já existe. O alcance dele (`vale_para` um `Projeto` ou `Setor`, ou a propriedade `alcance: global`) é escrito pelo humano; o `vale_para` também pelo árbitro, se a política do projeto lhe entrega o gesto `promover_aprendizado`. O alcance global é sempre do humano.
   - **Fato diz onde foi visto**: a `Evidence` do planejador é o que ele leu para decidir, e nasce com o ponteiro inteiro, numa de duas formas. A de arquivo é `arquivo`, `linhas` (`120` ou `120-135`) e o `trecho` literal, que cabe na faixa: o código, a ata em Markdown, o CSV. A de fonte genérica é `fonte` (uma URL, um documento, uma conversa com data e participantes), `local` livre opcional (página, seção, minuto) e o `trecho` literal: o fato que não mora num arquivo com linhas. Toda `Evidence` que cite `linhas`, `local` ou `trecho`, de qualquer papel, cita o ponteiro inteiro; `arquivo` ou `fonte` sozinhos seguem livres. O `InvariantGate` recusa na criação e na edição com `evidencia_sem_localizacao`; o portão não lê o disco, para o replay dar o mesmo veredito anos depois, e garante a forma que torna a conferência possível.
   - **A Sessão tem ciclo de vida** (`ativa`, `concluida`). Encerrada, a vista dela abre pelo fechamento determinístico (decisões vigentes, dúvidas abertas, restrições, último artefato), que é projeção do log e nunca é gravado, e o motor reativo abre nela a `Task` de condensação.

2. **Temporalidade**: o grafo tem um eixo de tempo, o do log (tempo de transação). Não é bitemporal: ninguém declara quando um fato passou a valer no mundo.
   - `criado_em` / `atualizado_em` (ISO 8601 UTC): instante do evento que criou o nó e do último que o tocou, tirados do log e nunca do relógio de quem projeta. A ordem total é o `seq`.
   - O estado em qualquer ponto passado sai do replay até um `seq` ou um instante.
   - Vigência é dita de dois jeitos: a propriedade `valido_ate` do `Aprendizado`, que a vista lê para não trazer memória vencida, e a aresta `substitui`, que marca o substituído sem apagá-lo.

3. **Imutabilidade e Evolução**:
   - Nenhum nó ou aresta é destruído fisicamente; modificações geram novos eventos de patch.
   - Informações obsoletas são conectadas via arestas `substitui` ou `contradiz`.
   - **Versão do vocabulário** (`VERSAO_ONTOLOGIA`, atualmente `1.5.0`: o escopo governado, com as arestas `motivada_por`, `acompanha`, `integra` e `desfaz` e os gestos e leituras de desvio (seção 5.7); a `1.4.0` deu à localização da `Evidence` a forma de fonte genérica; a `1.3.0` trouxe o tipo `Governanca` e o papel `arbitro`): cada evento do log declara sob qual versão desta especificação foi escrito. `core/ontologia.py` deriva uma assinatura dos termos em vigor, e um teste exige que a versão declarada acompanhe qualquer mudança de tipo, papel, origem ou status. Eventos anteriores à introdução do campo são lidos como versão `0`.

---

## 2. Tipos de Nós

### 2.1 Camada de Navegação

| Tipo de Nó | Descrição | Autor Permitido |
|---|---|---|
| `Projeto` | Agrupador raiz de alto nível de uma iniciativa: um produto, uma pesquisa, uma operação, um repositório. | `humano`; `harness`, só o Projeto do repositório no ambiente padrão da memória |
| `Setor` | Domínio de negócio ou especialidade dentro de um projeto. | `humano`; `harness`, só o Setor `Memoria` do ambiente padrão |
| `Sessao` | Contexto de interação onde execuções e diálogos ocorrem. Tem ciclo de vida: `ativa` e `concluida`. | `humano`, `harness` |
| `Governanca` | Singleton `governanca-global`: a política de governança global, com as propriedades `preset` e `personalizada`. Raiz como o `Projeto`, isenta da regra de hierarquia, e nenhuma aresta a toca (a política do projeto mora na propriedade `governanca` do próprio `Projeto`). | `humano`, sempre, em qualquer política |

### 2.2 Camada de Trabalho

| Tipo de Nó | Descrição | Autor Permitido |
|---|---|---|
| `Goal` | Intenção ou objetivo de alto nível estabelecido pelo humano. | `humano` |
| `Task` | Unidade de trabalho executável com critério de pronto e status. | `humano`, `planejador` |
| `Decision` | Escolha tomada com alternativas consideradas e justificativa. Com `acao: aceite_apos_reprovacao`, é o aceite de uma entrega no teto de reprovações em cadeia (`max_correcoes`). | `humano`, `planejador`, `executor`, `arbitro` |
| `Question` | Ponto de dúvida ou ambiguidade que requer resposta do humano ou, conforme a política, do árbitro. Guarda `aberta_por`; respondida, guarda `respondida_por` e `respondida_por_papel`. | `planejador`, `executor`, `revisor` |
| `Constraint` | Restrição ou regra mandatória do trabalho: de negócio, legal, de prazo, de código. | `humano`; `arbitro`, se a política lhe entrega o gesto `constraint` |
| `Artifact` | Entregável produzido: documento, dado, código, patch ou outro arquivo; na `Task` de ação externa, o registro do gesto feito, sem `arquivos`. | `executor` |
| `Evidence` | Fato observado no mundo (trecho lido num arquivo ou numa fonte, retorno de busca, saída de verificação, prova de um envio). Pode apontar por `deriva_de` o `Artifact` ou a `Task` que avalia. | `planejador` (só leitura localizada), `executor`, `revisor`, `arbitro` |
| `Run` | Registro de uma execução de agente (modelo, tokens, latência). | `sistema` |
| `Note` | Anotação textual livre sem contrato semântico estrito. Com `acao: condensacao_de_sessao`, é a condensação em prosa de uma sessão encerrada. | `humano`, `planejador`, `executor`, `revisor`, `arbitro` |
| `Aprendizado` | Memória de longo prazo: o que sobrevive ao projeto. O rótulo é a afirmação em uma linha; `como_aplicar` diz o que fazer com ela; `alcance: global` só pelo humano; `valido_ate` é lido pela vista; promovido, guarda `promovido_por` e `promovido_por_papel`. Registra quem detém `deriva_de`. | `humano`, `executor`, `revisor` |

### 2.3 Propriedades da Orquestração

Não são termos da ontologia. O `SchemaGate` confere `id` e `tipo` de um nó novo e não valida propriedades, e a assinatura da versão cobre tipos, arestas, papéis, origens e status, não propriedades: nenhuma delas exigiu subir a versão. São a convenção que o orquestrador grava por `criar_tarefa`, que `proximas_tarefas` devolve e que a medição lê, declarada em `core/orquestracao.py`.

| Onde | Propriedade | O que diz |
|---|---|---|
| `Task` | `criterio_pronto` | O critério de aceite, contra o qual o revisor julga. Já existia; a orquestração não criou outro nome para ele. |
| `Task` | `modelo`, `motivo_modelo` | O modelo que deve executar a tarefa e por quê. `criar_tarefa` recusa o modelo sem o motivo, para a escolha ficar auditável no log. |
| `Task` | `trilha` | `leve` ou `completa`; ausente vale `completa`. A leve é a da tarefa trivial de texto (redação, comentário ou documentação), sem mudança com efeito em código, dado ou configuração: pula o teste do executor frio, roda em Sonnet e vai ao revisor Sonnet. `criar_tarefa` recusa outro valor e a leve com `modelo: opus`. |
| `Task` | `entrega` | `artefato` (o padrão: arquivo, documento, dado) ou `acao_externa` (um gesto no mundo que não deixa arquivo, como enviar um e-mail ou marcar uma reunião). Quem executa a ação externa é o gesto `acao_externa` da política (seção 5.1). `criar_tarefa` recusa outro valor, e o executor não a troca. |
| `Task` | `arquivos_alvo` | Os arquivos que a tarefa toca, relativos à raiz do trabalho (código, documentos, planilhas). Só rodam em paralelo tarefas com arquivos-alvo disjuntos; a de ação externa não leva. |
| `Task` | `corrige` | Na tarefa de correção, a `Evidence` de revisão rejeitada que a motivou. |
| `Goal` | `configuracao` | O rótulo do arranjo de modelos com que o Goal foi orquestrado, para comparar configurações. |
| `Goal`, `Setor`, `Projeto` | `ramo_base`, `caminhos_de_colisao` | Só quando o trabalho mora num repositório git. Gravadas pelo humano: o ramo em que o trabalho do Goal vai ser integrado (`origin/stage` ou `stage`) e a lista de globs dos caminhos em que dois ramos colidem sem tocar o mesmo arquivo (`**/migrations/*.py`). O Goal herda cada uma do Setor que contém a sessão que o produziu e depois do Projeto. `graphow base-colisoes` as lê. |
| `Evidence` | `veredito` | O que o revisor concluiu contra os critérios da tarefa: `aprovado` ou `rejeitado`. Só conta o veredito de uma `Evidence` de papel que julga (`revisor`, `humano` ou `arbitro`, pela proveniência do nó); é ele que libera o fechamento da `Task` (seção 5.4). |
| `Projeto` | `governanca` | A política do projeto: `{preset, personalizada}`, com `preset` em `herdar` (o padrão), `governanca_maxima`, `arbitragem_maxima` ou `personalizada`, e uma `personalizada` parcial. Só o humano a escreve (seção 5). |
| `Projeto` | `nivel_autonomia` | Legado: `estrito` ou `ilimitado`, que a política lê como o gesto `estrutura`. Só o humano o escreve. |
| `Goal`, `Setor`, `Projeto` | `cadencia`, `teto_rodadas` | Gravadas pelo humano (a aba Configurações as grava no `Projeto`): quando a orquestração para e devolve a palavra (`tarefa`, `goal`, `setor` ou `desvio`, que devolve a palavra quando um gatilho de desvio do escopo governado dispara, com o placar) e quantas rodadas roda. Lidas pela skill, não pelo kernel. |
| `Goal` | `planos` | O plano aprovado, em versões que só crescem: lista de `{versao, seq, aprovado_por, papel}`, com `papel` `humano` ou `arbitro` e `seq` a `versao_log` do estado no momento da aprovação. A versão `v` é o conjunto das `Task`s alcançáveis do Goal por `decompoe` com `seq_criacao <= seq`. A referência é a última versão aprovada por `humano`; sem ela, toda `Task` é emergente (seção 5.7). |
| `Goal` | `respostas_de_desvio` | As respostas ao placar de desvio, só crescem: lista de `{seq, respondido_por, papel, raiz, resposta}`, com `raiz` o id da raiz de cadeia respondida ou nulo (o Goal inteiro). Zeram o contador do Goal só as entradas de `papel: humano`, como os planos de `papel: humano`. |
| `Task` | `atende_criterio` | Na `Task` emergente, o id da `Constraint` de critério de aceite que ela atende. |
| `Task` | `fase` | Rótulo opcional de agrupamento do plano (`F1`, `F2`…); serve só à apresentação. |
| `Constraint` | `tipo` | `criterio_aceite` (o critério que abre a porta da `Task` emergente) ou `fronteira` (o que o Goal não toca). Ausente, a restrição é uma restrição comum. |
| `Note` | `acao` | Com `proposta_fora_do_goal`, a descoberta fora dos critérios do Goal registrada como proposta para o humano decidir, e não como `Task`. |
| `Evidence` | `acao` | Com `veredito_de_escopo`, o julgamento de uma raiz de decisão e das `Task`s que ela gerou contra os critérios e a fronteira do Goal; não bloqueia. |
| `Evidence` | `triagem` | `fora_da_trilha` quando o revisor Sonnet acha, numa Task da trilha leve, mudança com efeito (no diff, quando a entrega é código). Não é veredito: não vigora sobre a tarefa nem entra na contagem da medição, e a Task vai ao revisor Opus. |

---

## 3. Tipos de Arestas

| Tipo de Aresta | Origem Permitida | Destino Permitido | Semântica |
|---|---|---|---|
| `contem` | `Projeto` → `Setor`, `Setor` → `Sessao` | Hierarquia estrita de navegação. |
| `produz` | `Sessao` → Nó de Trabalho | Vincula o item à sessão onde foi gerado. |
| `ocorreu_em` | `Run` → `Sessao` | Associa a execução à sessão ativa. |
| `decompoe` | `Goal` → `Task`, `Task` → `Task` | Decomposição hierárquica de tarefas. |
| `depende_de` | `Task` → `Task` | Pré-requisito de execução (acíclico obrigatório). |
| `bloqueia` | `Question` → `Task` | Trava o avanço da tarefa até resolução. |
| `justifica` | `Evidence` → `Decision` | Base empírica que sustenta uma decisão. |
| `orienta` | `Decision` → `Task` / `Goal` | A decisão que vale para a tarefa ou o objetivo. Como as restrições, desce pela decomposição em qualquer profundidade: a do `Goal` vale para toda tarefa dele, e a tarefa de correção herda as da tarefa que corrige. Chega à vista de quem executa e de quem revisa, mesmo tomada noutra sessão. |
| `contradiz` | `Evidence` → `Decision` / `Evidence` / `Aprendizado` | Aponta divergência ou refutação empírica; num `Aprendizado`, sinaliza que ele precisa de revisão. |
| `substitui` | `Decision` → `Decision`, `Task` → `Task`, `Aprendizado` → `Aprendizado` | Substituição evolutiva de definição anterior. O substituído segue visível, marcado. |
| `escopa` | `Constraint` → `Goal` / `Task` | Aplicação de restrição obrigatória. |
| `deriva_de` | `Artifact` → `Task` / `Artifact`; `Evidence` → `Artifact` / `Task`; `Note` → `Task` / `Decision` / `Evidence` / `Artifact`; `Aprendizado` → `Evidence` / `Decision` / `Note` / `Artifact` / `Task` | Proveniência de artefatos, da evidência que avalia um trabalho, de notas reativas, da condensação de uma sessão e da origem de um aprendizado. |
| `vale_para` | `Aprendizado` → `Projeto` / `Setor` | Alcance de um aprendizado promovido: entra na vista de toda tarefa sob esse contêiner. |
| `motivada_por` | `Task` → `Decision` / `Evidence` / `Task` / `Question`; `Decision` → `Decision` / `Evidence` / `Task` / `Question` | De que decisão, achado, trabalho ou dúvida a `Task` nasceu; a `Decision` que nasce de outra decisão ou de um achado liga a cadeia pelo mesmo vínculo. Subir `motivada_por` até um nó sem `motivada_por` saindo dele dá a raiz da cadeia (seção 5.7). |
| `acompanha` | `Task` → `Evidence` | A `Task` de acompanhamento de uma reprovação cujo aceite o árbitro registrou. |
| `integra` | `Task` → `Task` | A `Task` que integra a entrega de outra no ramo base. |
| `desfaz` | `Task` → `Decision` | A `Task` que desfaz uma decisão já substituída ou revogada. |

### 3.1 Dono de Cada Aresta

Criar e remover são poderes distintos, e ambos são impostos pelo `RoleGate`
(`kernel/matriz_papeis.py` e `kernel/permissao_de_aresta.py`). Qualquer agente
abre uma escalação com `bloqueia`; só o humano a retira, ou o árbitro quando a
política lhe entrega `responder_questao`. A coluna "Conforme a política" diz o
que a política de governança acrescenta à tabela: ela só acrescenta quem pode,
nunca tira (seção 5).

| Tipo de Aresta | Pode criar | Pode remover | Conforme a política |
|---|---|---|---|
| `contem` | `humano`, `sistema` | `humano` | Criar: todo agente, sob `estrutura: ilimitado` |
| `produz` | todos os papéis | `humano` | - |
| `ocorreu_em` | `humano`, `sistema` | `humano`, `sistema` | Criar: todo agente, sob `estrutura: ilimitado` |
| `decompoe` | `humano`, `planejador` | `humano`, `planejador` | Criar: todo agente, sob `estrutura: ilimitado` |
| `depende_de` | `humano`, `planejador` | `humano`, `planejador` | Criar: todo agente, sob `estrutura: ilimitado` |
| `bloqueia` | `humano`, `planejador`, `executor`, `revisor`, `arbitro` | `humano` | Remover: `arbitro`, com `responder_questao` (e nunca a da Question que ele abriu) |
| `justifica` | `humano`, `planejador`, `executor`, `revisor`, `arbitro` | `humano`, `planejador`, `executor`, `revisor`, `arbitro` | - |
| `contradiz` | `humano`, `executor`, `revisor` | `humano`, `executor`, `revisor` | Criar: todo agente, sob `estrutura: ilimitado` |
| `substitui` | `humano`, `planejador`; entre `Aprendizado`s também `executor`, `revisor`, `arbitro` | `humano`, `planejador` | Criar: todo agente, sob `estrutura: ilimitado` |
| `escopa` | `humano` | `humano` | Criar e remover: `arbitro`, com `constraint` |
| `deriva_de` | `humano`, `executor`, `revisor` | `humano`, `executor`, `revisor` | Criar: todo agente, sob `estrutura: ilimitado` |
| `vale_para` | `humano` | `humano` | Criar e remover, de um `Aprendizado` a um `Projeto` ou `Setor`: `arbitro`, com `promover_aprendizado` (e nunca o `Aprendizado` que ele registrou) |
| `orienta` | `humano`, `planejador` | `humano`, `planejador` | Criar: todo agente, sob `estrutura: ilimitado` |
| `motivada_por`, `acompanha`, `integra`, `desfaz` | `humano`, `planejador` | `humano` | Criar: todo agente, sob `estrutura: ilimitado` |

As quatro arestas do escopo governado se criam como `decompoe` e `orienta`, mas
só o humano as retira: retirar o vínculo apagaria a prova de que o trabalho
nasceu de algo. Estão entre as arestas que redefinem uma `Task` travada, então
numa `Task` com posse só o dono do lock as cria ou remove.

Nem o `estrutura: ilimitado` abre `escopa` ou `vale_para` a um agente: a
primeira amarra a restrição ao trabalho, a segunda promove memória de agente a
memória de todos. Essas duas só se abrem ao árbitro, pelo gesto próprio. E
nenhuma aresta toca o nó `Governanca`: o `SchemaGate` recusa com
`par_de_aresta_invalido`.

---

## 4. Matriz de Contratos por Papel

"A própria `Task` atribuída" deixou de ser uma frase e virou regra do kernel: a
atribuição é o **lock** da tarefa, adquirido por `assumir_tarefa` e verificado
pelo `InvariantGate` a cada mudança de status. Um agente sem posse recebe
recusa com o modo de falha `posse_de_tarefa_ausente` e o nome de quem detém a
tarefa.

A coluna "Conforme a política" é o que o papel ganha quando a política de
governança do projeto do alvo lhe entrega o gesto (seção 5). Sem ela, valem só as
outras colunas, e a `governanca_maxima` é exatamente isso.

| Papel | Nós que pode criar | Campos que pode editar | Ações proibidas | Conforme a política |
|---|---|---|---|---|
| `humano` | Todos | Todos | Nenhuma | - |
| `planejador` | `Task`, `Decision`, `Question`, `Note`, `Evidence` localizada | `titulo`, `descricao`, `criterio_pronto` de `Task` | Fechar `Task`, editar `Constraint`, encerrar `Question`, registrar ou promover `Aprendizado` | Só `estrutura: ilimitado` (como todo agente). Nenhum gesto de papel: o condutor nunca ganha o que a política tira do humano |
| `executor` | `Artifact`, `Evidence`, `Decision`, `Question`, `Note`, `Aprendizado` | `status` da `Task` cuja posse detém | Criar `Task`, editar `Constraint`, encerrar `Question`, mexer em `Task` de outro, promover `Aprendizado` | Só `estrutura: ilimitado` |
| `revisor` | `Evidence`, `Question`, `Note`, `Aprendizado` | Status de revisão da `Task` cuja posse detém | Fechar `Task` diretamente, encerrar `Question`, promover `Aprendizado` | Só `estrutura: ilimitado` |
| `arbitro` | `Evidence`, `Decision`, `Note` | O `status` da `Question` (`respondida` ou `descartada`), do `Goal` (`concluido`) e da `Sessao`, e a posse alheia, cada um com o gesto da política | Fechar `Task`, criar `Task`, `Governanca` ou `Projeto`, promover global, alterar a governança, encerrar a `Question` que abriu, promover o `Aprendizado` que registrou | `responder_questao`, `promover_aprendizado` (Setor e Projeto), `constraint`, `excluir`, `fechar_goal`, `encerrar_sessao`, `liberar_posse_alheia`, `aprovar_plano`, e todos os tipos de nó menos `Constraint`, `Governanca` e `Projeto` sob `estrutura: ilimitado` |
| `sistema` | `Run`, `Sessao`, e `Projeto` e `Setor` do ambiente padrão da memória | Métricas de execução e a própria `Sessao` | Criar ou alterar nós semânticos de trabalho | Encerrar a `Sessao` que abriu vale sempre, sem política |

### 4.1 O Que Nenhum Agente Faz, Por Nenhum Caminho

Estas operações são do humano em **qualquer** preset, no **portão**, não no nome
da ferramenta — um `propor_patch` cru recebe a mesma recusa, e nem o árbitro as
exerce:

1. **Promover a global**: escrever `alcance: global` num `Aprendizado` (o `global` de `promover_aprendizado`).
2. **Alterar a governança** (o meta-portão): criar, editar ou remover o nó `Governanca`, e escrever a propriedade `governanca` ou `nivel_autonomia` de um `Projeto`. Quem escrevesse a política se daria todos os gestos que ela governa. Um agente que cria um `Projeto` só o declara `estrito` e sem `governanca`.
3. O **push** do git, quando o trabalho mora num repositório: fora do grafo, é sempre do humano; o gesto `integracao` cobre só o commit e o merge local na base.

Fora da política, e não do humano por exceção, vale também a regra do veredito: um
agente só conclui uma `Task` com revisão aprovada (seção 5.4).

### 4.2 O Que Só o Humano Faz Por Padrão, e a Política Pode Entregar ao Árbitro

Com a `governanca_maxima` (o padrão, e o que vale sem nó `Governanca`) todos
estes gestos são do humano e nenhum agente os exerce, por nenhum caminho. A
política os entrega ao `arbitro`, nunca ao planejador, executor ou revisor:

1. `responder_questao`: escrever na `Question` um status que não seja `aberta` (o árbitro escreve só `respondida` ou `descartada`), remover o status dela, remover uma aresta `bloqueia`, inclusive pela cascata de remover a `Task` ou a `Sessao`. O árbitro não encerra a `Question` que ele abriu, nem por remoção.
2. `promover_aprendizado`: escrever `alcance` num `Aprendizado` de Setor ou Projeto, ou criar e remover `vale_para`. O árbitro não promove o `Aprendizado` que registrou.
3. `constraint`: criar, editar e remover `Constraint`, e criar e remover a aresta `escopa`.
4. `excluir`: as ferramentas `excluir_projeto` e `excluir_em_lote`, e remover nós `Question` e `Aprendizado`: memória é substituída ou contradita, nunca apagada por agente sem o gesto.
5. `fechar_goal`: escrever `concluido` num `Goal`.
6. `encerrar_sessao`: escrever o status de uma `Sessao`.
7. `liberar_posse_alheia`: `liberar_tarefa` sobre a posse de outro autor.
8. `aprovar_plano`: aprovar uma versão do plano de um `Goal`. A versão aprovada pelo árbitro vale como plano vigente, mas nunca como referência do escopo (seção 5.7).
9. `responder_desvio`: responder ao alerta de desvio do plano. É a exceção desta lista: o humano o detém também na `arbitragem_maxima`, e só a `personalizada` o entrega ao árbitro. A resposta do árbitro dispensa o alerta, mas não zera o contador do Goal.

Vale ainda, para todo papel: remover um nó de tipo que o papel não cria, ou um
cuja cascata leve uma aresta que o papel não remove. O tipo e as pontas da aresta
removida vêm do grafo, nunca do valor enviado.

---

## 5. Governança Configurável

A pergunta "quem faz este gesto" deixou de ter resposta fixa. Cada gesto que era
só do humano é decidido por uma política, em dois níveis (global e por projeto),
e a política mora no grafo, para o replay do log dar o mesmo veredito: o kernel
decide só pelo estado.

### 5.1 Os Dezesseis Gestos

Valores aceitos e o que cada preset fixo vale (`governanca_maxima` /
`arbitragem_maxima`). `humano` significa que só o humano faz o gesto; `arbitro`,
que o humano e o árbitro o fazem. O catálogo vive em `core/governanca.py`.

| Gesto | Valores | O que governa | Presets |
|---|---|---|---|
| `responder_questao` | `humano`, `arbitro` | Encerrar uma `Question` (`respondida` ou `descartada`) e retirar a aresta `bloqueia` | humano / arbitro |
| `promover_aprendizado` | `humano`, `arbitro` | Escrever `vale_para` para `Setor` ou `Projeto`; o global nunca | humano / arbitro |
| `constraint` | `humano`, `arbitro` | Criar, editar e remover `Constraint`, e criar e remover a aresta `escopa` | humano / arbitro |
| `estrutura` | `estrito`, `ilimitado` | O que era o `nivel_autonomia`: `ilimitado` dá a todos os agentes os tipos de nó (menos `Constraint`, `Governanca` e `Projeto`) e a criação das arestas, `contem` inclusive, menos `escopa` e `vale_para` | estrito / ilimitado |
| `excluir` | `humano`, `arbitro` | `excluir_projeto`, `excluir_em_lote` e remover `Question` e `Aprendizado` | humano / arbitro |
| `fechar_goal` | `humano`, `arbitro` | Escrever `concluido` num `Goal` | humano / arbitro |
| `encerrar_sessao` | `humano`, `arbitro` | Escrever o status de uma `Sessao` e a ferramenta `encerrar_sessao`; o papel `sistema` do harness segue sempre autorizado | humano / arbitro |
| `liberar_posse_alheia` | `humano`, `arbitro` | `liberar_tarefa` sobre o lock de outro autor | humano / arbitro |
| `integracao` | `humano`, `arbitro` | Lido só pela skill: commit e merge local na base. O push é sempre humano | humano / arbitro |
| `max_correcoes` | inteiro de 0 a 5 | Lido pela skill: reprovações em cadeia antes do teto (a de ordem N já escala; 2 = a original e a primeira correção) | 2 / 2 |
| `aprovar_plano` | `humano`, `arbitro` | Aprovar uma versão do plano de um `Goal` (a propriedade `planos`). Só a aprovação de `humano` define a referência do escopo e zera o contador de desvio | humano / arbitro |
| `responder_desvio` | `humano`, `arbitro` | Responder ao placar quando o trabalho emergente passa dos limiares (a propriedade `respostas_de_desvio`). Só a resposta de `humano` zera o contador | humano / humano |
| `limiar_desvio_por_raiz` | inteiro de 1 a 50 | Lido pelo kernel e pelas projeções: K, as `Task`s emergentes de uma mesma raiz de cadeia a partir das quais o desvio dispara | 3 / 3 |
| `limiar_desvio_por_goal` | inteiro de 1 a 200 | Lido pelo kernel e pelas projeções: M, as `Task`s emergentes do `Goal` desde a última vez que o contador zerou, a partir das quais o desvio dispara | 5 / 5 |
| `teto_expansao` | inteiro de 0 a 500 | Teto de `Task`s emergentes de um `Goal` até um `responder_desvio`; acima dele o `InvariantGate` recusa a nova com `orcamento_de_escopo_esgotado`. 0 desliga a recusa | 0 / 0 |
| `acao_externa` | `humano`, `executor` | Assumir e entregar a `Task` de `entrega: acao_externa` (enviar e-mail, marcar reunião). Sob `humano`, o `RoleGate` recusa o executor que a assume ou a põe em revisão, e o que troca a `entrega`; a posse para fechar a Task já aprovada segue livre. A `arbitragem_maxima` o entrega ao executor, e a `personalizada` escolhe | humano / executor |

`estrutura`, `acao_externa` e as quatro leituras inteiras (`max_correcoes`,
`limiar_desvio_por_raiz`, `limiar_desvio_por_goal` e `teto_expansao`) não são
permissões por papel do árbitro: a política tem leitura própria deles
(`estrutura_ilimitada`, `acao_externa_com_executor`, `max_correcoes`,
`limiar_desvio_por_raiz`, `limiar_desvio_por_goal` e `teto_expansao`), e
perguntar a eles `permite(...)` é erro de quem chama. Na composição entre
projetos o humano vence o executor. O domínio e o padrão de cada leitura inteira
moram em `core/leituras_inteiras.py`; o inteiro fora do domínio, o texto e o
booleano são recusados na configuração.

### 5.2 Presets, Herança e Legado

- **Presets.** `governanca_maxima` e `arbitragem_maxima` são fixos e imutáveis. `personalizada` é a única editável, e fica **guardada à parte**: trocar para um preset fixo não a apaga, e voltar a ela a recupera intacta.
- **Global.** O singleton `governanca-global` (tipo `Governanca`) guarda `preset` e a `personalizada` completa. Sem o nó, vale a `governanca_maxima`. Na `personalizada` global, o gesto ausente completa com a `governanca_maxima`.
- **Projeto.** A propriedade `governanca` do `Projeto` é `{preset, personalizada}`, com `preset` em `herdar` (o padrão e o que vale se a propriedade falta), `governanca_maxima`, `arbitragem_maxima` ou `personalizada`. A `personalizada` do projeto é **parcial**: cada gesto ausente herda da política efetiva global. Na interface e em `configurar_governanca`, o valor `herdar` de um gesto apaga a sobrescrita dele.
- **Origem.** Cada gesto da política efetiva traz de onde veio o valor: `global`, `projeto`, `preset:<nome>`, `legado:nivel_autonomia` ou, na composição de vários projetos, `projeto:<id>`. A interface mostra esse selo.
- **Legado `nivel_autonomia`.** Um `Projeto` com `nivel_autonomia: ilimitado` e `governanca` ausente ou `herdar` sobrepõe `estrutura: ilimitado` à política herdada, e o comportamento de antes é preservado. Um projeto com preset próprio não o conserva. `configurar_autonomia_projeto` continua funcionando, sempre do humano; o caminho novo é `configurar_governanca`.
- **Validação.** O `SchemaGate` recusa, com `estrutura_incompleta`, um preset desconhecido, um gesto desconhecido, um valor fora do domínio do gesto, uma chave estranha na configuração e um segundo nó `Governanca` com id diferente de `governanca-global`.

### 5.3 Qual Política Vale para um Nó

A política de um nó é a do `Projeto` que o contém, subindo **só pelas arestas de
contenção** (`contem`, `produz`, `decompoe`). `orienta`, `deriva_de`, `justifica`,
`bloqueia` e as demais ligam por significado, não por pertencimento, e não
decidem política: senão uma aresta a um projeto alheio puxaria a política mais
permissiva para um alvo que não é dele. A subida para no `Projeto`, que não é
atravessado. Sem `Projeto` ancestral, vale a global.

Um nó pode ter **mais de um** `Projeto` pela contenção (o planejador cria
`decompoe` de um `Goal` de outro projeto). Então vale, gesto a gesto, a política
**mais restritiva**: `humano` vence `arbitro`, `estrito` vence `ilimitado`, e
nas leituras inteiras vale o menor número, e no `teto_expansao` o menor positivo (0 desliga a
recusa, então perde para qualquer teto ligado). A origem do gesto aponta o projeto que restringiu
(`projeto:<id>`) e, no empate, o de menor id. A resposta não depende da ordem
das arestas, e com um projeto só é a política dele.

### 5.4 A Regra do Veredito, Fora da Política

Vale em **todos** os presets: uma proposta de papel não humano que escreve `status`
`concluido` numa `Task` é recusada com `fechamento_sem_veredito_aprovado` se a
Task não tem o veredito efetivo `aprovado`:

- O **veredito** é o da `Evidence` com `veredito` mais recente sobre a `Task` ou os `Artifact`s dela, e só conta se a `Evidence` é de papel que julga: `revisor`, `humano` ou `arbitro`, pela proveniência do nó. O executor não cria a própria aprovação.
- A **correção aprovada supera a rejeição**: a `Task` de correção aponta por `corrige` a `Evidence` da rejeição, e se ela vale como aprovada (ou a correção da correção, em cadeia), o veredito efetivo da original é `aprovado`.
- O **aceite pelo teto** é a outra porta: uma `Decision` com `acao: aceite_apos_reprovacao` que orienta a `Task`, justificada pela `Evidence` do veredito vigente, criada por `planejador`, `humano` ou `arbitro`. O executor não se declara aceito.
- O lote é lido pelo estado depois dele: a `Evidence` aprovada criada no mesmo lote conta, a que o lote remove não.
- **Isentos**: o humano e as `Task`s de manutenção de memória que o próprio grafo abre sem revisor (`acao` `condensar_sessao` e `consolidar_aprendizados`).

### 5.5 Anti-Autoconflito

Quem pergunta e quem decide nunca são o mesmo: o árbitro não responde, descarta
nem remove a `Question` que ele abriu (propriedade `aberta_por`), e não promove o
`Aprendizado` que registrou. Compara-se o autor sem o sufixo `#xxxx` que a
conexão acrescenta; um `Aprendizado` criado no mesmo lote conta como registrado
por quem propõe.

### 5.6 Onde a Política Aparece

- **Vistas e protocolo.** A seção `Governanca` da vista de `Sessao`, `Task` e `Goal` (e o protocolo que o hook imprime) diz o preset efetivo, os gestos `com o arbitro`, a estrutura ilimitada, o `max_correcoes` fora do padrão, os limiares de desvio e o teto de expansão fora do padrão e a `acao_externa` com o executor, e que a promoção global e a configuração da governança seguem sempre do humano. A vista do árbitro traz o que ele precisa para decidir.
- **MCP.** `graphow mcp --papel arbitro` abre o servidor do papel `arbitro`. A ferramenta `configurar_governanca` grava a política (`escopo` `global` ou o id de um `Projeto`, `preset`, `personalizada`) e devolve a política efetiva com a origem de cada gesto; é sempre do humano, árbitro inclusive.
- **Interface web.** A aba **Configurações** (engrenagem na faixa de ícones, ou a paleta `Ctrl+P`, comando "Configurações: governança e operação") escolhe o escopo (Global ou um projeto), mostra os presets em cartões, a tabela dos gestos com o valor e a origem (editável só na `personalizada`; no projeto cada gesto pode herdar), as duas linhas sempre humanas (promoção global e alterar a governança), a operação do projeto (cadência, teto de rodadas e, quando o trabalho mora num repositório git, ramo base e caminhos de colisão) e a auditoria do que o árbitro fez. O que o árbitro respondeu ou promoveu leva o selo "pelo árbitro". A tela escreve como o humano, pelas rotas `/api/governanca` e `/api/projetos/<id>/governanca`, e libera posse por `/api/tarefas/<id>/liberar-posse`.
- **Orquestração.** O subagente `graphow-arbitro` (`.agents/agents/graphow-arbitro.md`) é despachado pela raiz da skill `graphow-orquestracao` quando a política lhe concede o gesto: lê a política na vista, exerce só os gestos que ela entrega e devolve `Escaladas` para o resto. A matriz de nós, arestas e papéis que os agentes consultam está em `.agents/skills/graphow-mcp/references/ontology_matrix.md`.

### 5.7 Escopo Governado: O Vocabulário

O escopo governado fecha o trabalho de um `Goal` ao que o humano aprovou. Esta
seção declara o vocabulário que a ontologia `1.5.0` acrescentou; as regras que o
usam (os portões de ligação e de plano aprovado, a fila, o placar) entram em
etapas seguintes e valem só para eventos de versão `1.5.0` em diante, de modo que
o replay de um log antigo não passa por elas. As convenções de propriedade estão
em `core/escopo.py`.

- **Plano e referência.** `Goal.planos` guarda as versões aprovadas. O plano da versão `v` são as `Task`s alcançáveis do `Goal` por `decompoe` com `seq_criacao <= seq`. O plano vigente é a última versão; a referência do escopo é a última versão aprovada por `humano`. Sem referência, toda `Task` é emergente.
- **Classes de `Task`.** Sob um `Goal`, uma `Task` é do `plano`; subdivisão (`B1`, `decompoe` vindo de `Task` do plano vigente ou de descendente); `correcao` (`corrige` uma `Evidence` rejeitada); `acompanhamento` (`acompanha` uma `Evidence` rejeitada que tem `Decision` `aceite_apos_reprovacao`); `integracao` (`integra` uma `Task` do mesmo `Goal` com `Artifact`); `reversao` (`desfaz` uma `Decision` substituída ou revogada); `emergente` (`B3`: `motivada_por` mais `atende_criterio` apontando uma `Constraint` `tipo: criterio_aceite` que `escopa` o `Goal`); ou sem ligação, nenhuma das anteriores. Num histórico anterior à `1.5.0` a avaliação usa `orienta` (`Decision` → `Task`) como aproximação de `motivada_por`.
- **Raiz de cadeia.** Subir `motivada_por` até um nó sem `motivada_por` saindo dele. K e M contam `Task`s emergentes por raiz e por `Goal`.
- **Gestos.** `aprovar_plano` (`humano` na `governanca_maxima`, `arbitro` na `arbitragem_maxima`) e `responder_desvio` (`humano` nos dois presets fixos; só a `personalizada` o põe com o `arbitro`).
- **Leituras.** `limiar_desvio_por_raiz` (K, padrão 3), `limiar_desvio_por_goal` (M, padrão 5) e `teto_expansao` (padrão 0, desligado), inteiros com a composição mais restritiva da seção 5.3.
- **Falhas.** `ligacao_de_escopo_ausente` (a `Task` nova não diz de que nasceu) e `plano_nao_aprovado` (o `Goal` não tem plano aprovado), da categoria `verificacao_de_tarefa`; `orcamento_de_escopo_esgotado` (o `teto_expansao` foi atingido), da categoria `design_do_sistema`.
- **Cadência.** O valor `desvio` de `cadencia`, em que a orquestração devolve a palavra quando um gatilho de desvio dispara.
