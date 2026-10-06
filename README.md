# Graphow 🌐

> **Substrato Bilateral de Grafo Agêntico para Coordenação Humano-IA**  
> *Common Ground compartilhado, governança em 4 portões (PatchBoard), log append-only determinístico (ActiveGraph) e divulgação progressiva com orçamento de tokens.*

---

## 📌 Visão Geral

O **Graphow** é uma plataforma de estado compartilhado (*common ground*) que atua como substrato bilateral para coordenação estruturada entre pessoas e agentes autônomos de Inteligência Artificial (Planejadores, Executores, Revisores e, onde a política de governança o autoriza, o Árbitro).

O trabalho coordenado não precisa ser software. O mesmo grafo serve a uma pesquisa, a um relatório, a uma análise, a um planejamento ou a uma operação: o `Goal` é a intenção, as `Task`s entregam documentos, dados ou código, a `Evidence` diz de onde veio cada fato (um trecho de arquivo, uma URL, uma reunião) e a revisão confere a entrega contra o critério de pronto. A tarefa que é um gesto no mundo, como enviar um e-mail ou marcar uma reunião, tem entrega própria (`acao_externa`), e a política de governança diz se ela é da pessoa ou do agente. O que é próprio de código (testes, `git diff`, integração de ramos, colisões de migrations) entra como caso, quando a entrega é código.

A arquitetura do Graphow é fundamentada em quatro pilares inegociáveis:
1. **O Log é a Verdade (*ActiveGraph*):** Event store *append-only* (SQLite local-first ou memória), com o tempo do log como único eixo temporal; o grafo é uma projeção puramente determinística e reconstruível do zero absoluto via *event replay*.
2. **Caminho Único de Escrita (*PatchBoard*):** Humanos e IAs submetem mutações utilizando o mesmo protocolo JSON Patch ([RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)), avaliado rigorosamente por um **Kernel de 4 Portões**.
3. **Divulgação Progressiva (*Progressive Disclosure*):** Agentes de IA consom recortes de contexto otimizados sob orçamento estrito de tokens, expandindo nós vizinhos sob demanda.
4. **Linhagem Causal e Reversibilidade:** Rastreabilidade reversa do `Artifact` até a intenção raiz (`Goal`) pelo caminho mais curto, subindo por proveniência e decomposição e nunca por `depende_de` (pré-requisito não diz a que objetivo a tarefa pertence), com ramificações históricas (*forks*) registradas como ponteiro `(ramo_base, seq_corte)`, sem cópia de prefixo.

---

## 🏛️ Arquitetura do Sistema

```
  ┌────────────────────────────────────────────────────────┐
  │                 HUMANO (Canvas / REST / CLI)            │
  └──────────────────────────┬─────────────────────────────┘
                             │ Proposta JSON Patch (RFC 6902)
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                 AGENTE IA (MCP Server)                 │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │             KERNEL DE ESCRITA EM 4 PORTÕES             │
  │  1. SchemaGate     -> Validação Ontológica e Tipos     │
  │  2. RoleGate       -> Contratos de Permissão por Papel │
  │  3. InvariantGate  -> Ciclos DAG, Locks e Bloqueios    │
  │  4. WriteKernel    -> Transação Atômica & Commit       │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │            EVENT STORE APPEND-ONLY (SQLite)            │
  └──────────────────────────┬─────────────────────────────┘
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
   ┌───────────────────────────┐   ┌───────────────────────────┐
   │    PROJEÇÃO EM MEMÓRIA    │   │      MOTOR REATIVO        │
   │  (GrafoReducer & View)    │   │  (Revisões, Alertas, Run) │
   └───────────────────────────┘   └───────────────────────────┘
```

---

## 🧩 Ontologia Formal em Duas Camadas

O Graphow adota uma ontologia formal rígida (detalhada na [Especificação Ontológica](docs/ONTOLOGY.md)) que separa navegação espacial do trabalho executivo:

### 1. Camada de Navegação (Containers Hierárquicos)
- **`Projeto`**: Raiz macro da iniciativa.
- **`Setor`**: Domínio ou subsistema técnico/funcional.
- **`Sessao`**: Janela de contexto temporal e transacional.
- **`Governanca`**: O singleton `governanca-global`, com a política de governança global (`preset` e `personalizada`). Raiz como o `Projeto`, sem arestas, e só o humano o cria, edita ou remove. A política de cada projeto mora na propriedade `governanca` do próprio `Projeto` (veja a seção Governança Configurável, abaixo).

### 2. Camada de Trabalho (Grafo de Intenção e Execução)
- **`Goal`**: Intenção ou objetivo de alto nível.
- **`Task`**: Unidade atômica de trabalho técnico.
- **`Decision`**: Decisão arquitetural ou técnica aprovada.
- **`Question`**: Dúvida ou ambiguidade que **bloqueia** uma tarefa.
- **`Constraint`**: Restrição inviolável que escopa objetivos e tarefas.
- **`Artifact`**: Entregável concreto de código, documento ou configuração.
- **`Evidence`**: Dado empírico, benchmark ou prova que justifica decisões.
- **`Run`**: Registro de execução e telemetria de um modelo de IA.
- **`Note`**: Anotação livre, aviso reativo ou contexto efêmero. Com `acao: condensacao_de_sessao`, a condensação em prosa de uma sessão encerrada.
- **`Aprendizado`**: Memória de longo prazo, o que sobrevive ao projeto. Nasce com origem obrigatória (`deriva_de`) e só alcança outros projetos quando é promovido (`vale_para`, pelo humano ou pelo árbitro conforme a política; `alcance: global`, sempre pelo humano).

### 3. Matriz de Arestas Permitidas (13 Tipos)

Cada tipo de aresta tem **dono declarado**, e criar não é o mesmo poder que
remover: qualquer agente abre uma escalação com `bloqueia`, e só o humano a
retira. A tabela vive em `kernel/matriz_papeis.py`, o `RoleGate` a aplica no
portão, e um teste de estrutura confere que nenhum tipo ficou sem dono.

| Tipo de Aresta | Par Permitido (Origem $\rightarrow$ Destino) | Quem cria / quem remove | Semântica |
| :--- | :--- | :--- | :--- |
| **`contem`** | `Projeto` $\rightarrow$ `Setor`, `Setor` $\rightarrow$ `Sessao` | humano, sistema / humano | Hierarquia estrutural de navegação. |
| **`produz`** | `Sessao` $\rightarrow$ Nós de Trabalho | todos / humano | Criação de itens de trabalho no escopo da sessão. |
| **`ocorreu_em`** | `Run` $\rightarrow$ `Sessao` | humano, sistema / humano, sistema | Associação de execução agêntica à sessão. |
| **`decompoe`** | `Goal` $\rightarrow$ `Task`, `Task` $\rightarrow$ `Task` | humano, planejador | Decomposição hierárquica de tarefas. |
| **`depende_de`** | `Task` $\rightarrow$ `Task` | humano, planejador | Pré-requisito de execução (DAG acíclico estrito). |
| **`bloqueia`** | `Question` $\rightarrow$ `Task` | todos / **humano**, ou o árbitro com `responder_questao` | Bloqueia a conclusão da tarefa até a resolução do humano ou, conforme a política, do árbitro. |
| **`justifica`** | `Evidence` $\rightarrow$ `Decision` | humano, planejador, executor, revisor | Fundamentação empírica de decisões. |
| **`contradiz`** | `Evidence` $\rightarrow$ `Decision` / `Evidence` / `Aprendizado` | humano, executor, revisor | Registro de evidência conflitante; num `Aprendizado`, pedido de revisão. |
| **`substitui`** | `Decision` $\rightarrow$ `Decision`, `Task` $\rightarrow$ `Task`, `Aprendizado` $\rightarrow$ `Aprendizado` | humano, planejador; entre `Aprendizado`s também executor e revisor | Evolução e invalidação histórica. Entre aprendizados é consolidação: um que substitui vários. O substituído fica no grafo, marcado; a vista carrega só o vigente, e a linha do substituto diz quem ele absorveu. |
| **`escopa`** | `Constraint` $\rightarrow$ `Goal` / `Task` | **humano**, ou o árbitro com `constraint` | Restrição mandatória sobre a execução. |
| **`deriva_de`** | `Artifact` $\rightarrow$ `Task` / `Artifact`; `Evidence` $\rightarrow$ `Artifact` / `Task`; `Note` $\rightarrow$ `Task` / `Decision` / `Evidence` / `Artifact`; `Aprendizado` $\rightarrow$ `Evidence` / `Decision` / `Note` / `Artifact` / `Task` | humano, executor, revisor | Proveniência de artefatos, da evidência que avalia um trabalho, de notas reativas, da condensação de uma sessão e da origem de um aprendizado. |
| **`vale_para`** | `Aprendizado` $\rightarrow$ `Projeto` / `Setor` | **humano**, ou o árbitro com `promover_aprendizado` | Alcance de um aprendizado promovido: entra na vista de toda tarefa sob esse contêiner. Nem a estrutura ilimitada a abre a agentes comuns. |
| **`orienta`** | `Decision` $\rightarrow$ `Task` / `Goal` | humano, planejador | A decisão que vale para a tarefa ou o objetivo, herdada pela decomposição. Chega à vista de quem executa e de quem revisa mesmo tomada noutra sessão. O executor não a cria nem a remove: não mexe no que governa a própria tarefa. |

---

## 🛡️ Os 4 Portões de Governança (PatchBoard)

Toda mutação no grafo (seja humana ou de IA) é submetida via JSON Patch RFC 6902 e processada sequencialmente:

1. **Portão 1 — `SchemaGate`:** Sanitização estrita contra *prototype pollution* (`__proto__`, `constructor`, `__class__`), checagem de tipos e validação da tabela ontológica de pares válidos de arestas. Só aceita as formas que o conversor grava como elas são (`add`/`remove` em `/nos/<id>` e `/arestas/<id>`, `add`/`replace` em `/nos/<id>/rotulo`, `add`/`replace`/`remove` em `/nos/<id>/propriedades/<chave>`), sem segmento vazio (`//` ou `/` no final), e todo `add` cria um id novo, o mesmo do campo `id` do valor. Também confere a política de governança declarada (`preset` e `personalizada` do nó `Governanca` e da propriedade `governanca` do `Projeto`): preset ou gesto desconhecido, valor fora do domínio do gesto e um segundo nó `Governanca` com id diferente de `governanca-global` caem com `estrutura_incompleta`, e nenhuma aresta toca o `Governanca`. Antes disso, uma barra no final de `.../propriedades/status/` escapava da regra do RoleGate e encerrava a `Question`, um `test` no status concluía uma `Task` com dúvida bloqueante aberta, um `add` sobre id existente transformava uma `Constraint` em `Note`, e um `add` em `/arestas/<id>/...` gravava um evento que quebrava toda leitura do ramo.
2. **Portão 2 — `RoleGate`:** Matriz de permissões por papel, aplicada sobre a identidade da *conexão*, nunca sobre um campo do payload:
   - **`humano`**: Acesso irrestrito. Só ele faz, em qualquer preset, a promoção global, a configuração da governança e o push; os demais gestos (encerrar uma `Question`, criar/editar `Constraint`, excluir, fechar `Goal`, encerrar `Sessao`, liberar posse alheia, estruturar a camada de navegação) são dele a menos que a política os entregue ao árbitro, e a `Task` de ação externa é dele a menos que a política a entregue ao executor.
   - **`planejador`**: Cria `Task`, `Decision`, `Question`, `Note` e a `Evidence` do que leu, sempre localizada (no arquivo ou na fonte); decompõe, ordena e diz com `orienta` onde cada decisão vale; proibido de fechar tarefas.
   - **`executor`**: Cria `Artifact`, `Evidence`, `Question`, `Note`, `Aprendizado`; assume tarefas e trabalha nelas; proibido de criar tarefas, alterar constraints, trocar a `entrega` de uma `Task` e, salvo quando a política lhe entrega o gesto `acao_externa`, assumir ou entregar a `Task` de ação externa.
   - **`revisor`**: Cria `Evidence`, `Question`, `Note`, `Aprendizado`; valida artefatos. Registra `Aprendizado` quem detém `deriva_de`: executor e revisor.
   - **`arbitro`**: O agente a quem a política de governança do projeto entrega os gestos que tira do humano. Por si só cria só `Evidence`, `Decision` e `Note`; o resto vem da política do projeto do alvo e é recusado onde ela o deixa com o humano. Nunca promove a global, nunca altera a governança, não encerra a `Question` que abriu nem promove o `Aprendizado` que registrou, e não fecha `Task`. Servidor: `graphow mcp --papel arbitro`.
   - **`sistema`**: Telemetria (`Run`), a `Sessao` em que o harness roda e, quando o humano não configurou um Setor, o **ambiente padrão da memória**: o `Projeto` com o nome do repositório e o `Setor` `Memoria` dentro dele. Nada do grafo de trabalho, e nenhum papel de agente alcança `sistema`.

   Estas regras valem para **todo** papel não humano, e valem no kernel, não no
   nome da ferramenta: escrever na `Question` um status que não seja `aberta`
   (ou remover o status), remover uma `Question`, remover a aresta `bloqueia`,
   escrever `alcance` num `Aprendizado` ou criar `vale_para`, remover um
   `Aprendizado` exigem o humano, ou o árbitro quando a política do projeto
   lhe entrega o gesto (`responder_questao`, `promover_aprendizado`, `excluir`);
   escrever `nivel_autonomia` ou `governanca` num `Projeto`, mexer no nó
   `Governanca` e promover à global exigem o humano, sempre. Sem as três
   primeiras, um agente encerrava a própria escalação com um `propor_patch` e
   concluía a tarefa em seguida; sem as duas seguintes, promoveria a própria
   memória a memória de todos; sem a última, se daria autonomia ilimitada ou
   desligaria todos os portões pela política.

   A remoção é julgada pelo que está no grafo, nunca pelo valor enviado: o tipo
   e as pontas de uma aresta removida vêm do estado, e um agente remove só o
   tipo de nó que pode criar, desde que cada aresta que sai com ele na cascata
   seja uma que ele também poderia remover. Antes, `remove` com
   `"tipo": "justifica"` tirava a `bloqueia`, e remover a `Task` levava junto a
   `bloqueia` e a `escopa` dela.
3. **Portão 3 — `InvariantGate`:**
   - **Hierarquia Obrigatória:** Todo nó novo, exceto `Projeto`, termina o lote que o cria com uma aresta de contenção chegando nele (`contem`, `produz` ou `decompoe`). Vale para todo papel, humano incluído: o nó solto só aparecia na pasta "Fora da hierarquia" e sumia de qualquer visão colapsada. A regra lê o estado depois do lote, com remoções e cascata aplicadas (`kernel/estrutura_apos_lote.py`): criar a contenção e removê-la no mesmo lote não pendura nada, e um agente não solta da hierarquia um nó que já existia.
   - **Memória com Origem:** Todo `Aprendizado` novo termina o lote com ao menos uma aresta `deriva_de` partindo dele; sem ela o lote cai com `aprendizado_sem_origem`. Um agente também não tira a última origem de um `Aprendizado` existente. Memória sem origem é opinião com autoridade de memória.
   - **Leitura Localizada:** A `Evidence` do planejador, e qualquer `Evidence` que cite `linhas`, `local` ou `trecho`, carrega o ponteiro inteiro, numa de duas formas: `arquivo`, `linhas` (`120` ou `120-135`) e o `trecho` literal, que cabe na faixa; ou, quando o fato não mora num arquivo com linhas, `fonte` (URL, documento, conversa com data e participantes), `local` livre opcional (página, seção, minuto) e o `trecho` literal. Vale na criação e na edição; sem isso o lote cai com `evidencia_sem_localizacao`. Uma interpretação sem o trecho que a sustenta não ganha autoridade de fato registrado.
   - **Detecção de Ciclos:** DFS iterativa impedindo ciclos em `depende_de`.
   - **Bloqueio por Dúvidas:** Impede que uma `Task` passe para `concluido` enquanto houver `Question` aberta com aresta `bloqueia`, inclusive a que o próprio lote cria. Responder e concluir seguem sendo dois lotes.
   - **Veredito para Concluir:** Um papel não humano só escreve `concluido` numa `Task` cujo veredito de revisão efetivo é `aprovado`, em todo preset; sem isso o lote cai com `fechamento_sem_veredito_aprovado`. Só conta o veredito de uma `Evidence` de `revisor`, `humano` ou `arbitro` (o executor não aprova a própria entrega); uma correção aprovada supera a rejeição que a motivou; e o aceite pelo teto de correções, uma `Decision` de `acao: aceite_apos_reprovacao` do planejador, do humano ou do árbitro, justificada pela `Evidence` do veredito vigente, é a outra porta. Ficam isentos o humano e as `Task`s de condensar a sessão e consolidar aprendizados, que o próprio grafo abre sem revisor (`kernel/veredito_de_fechamento.py`).
   - **Posse de Tarefa:** Nenhum agente move o status de uma `Task` sem deter o lock dela. Sem isso, dois executores na mesma tarefa não colidiam e o segundo sobrescrevia o primeiro em silêncio.
   - **Locks Exclusivos:** Impede mutações em tarefas travadas por outro escritor, e isso inclui criar ou remover as arestas que redefinem a tarefa (`depende_de`, `decompoe`, `orienta`, `escopa`, `substitui`). `bloqueia` e `deriva_de` seguem livres: a escalação e a proveniência continuam chegando à tarefa travada.
4. **Portão 4 — `WriteKernel`:** Geração dos `EventoLog` e projeção do lote **antes** de gravá-lo (o lote que o acumulador não consegue aplicar volta recusado, e o log fica intacto), persistência do lote inteiro em uma única transação (`BEGIN IMMEDIATE`/`ROLLBACK`, com `UNIQUE(ramo_id, seq)`) e notificação dos observadores — canal SSE e motor reativo.

   Quando outro processo ocupa a posição entre a validação e o commit, o kernel revalida contra o log atualizado, dobrando só o que o outro gravou, e tenta de novo depois de uma espera sorteada que dobra a cada perda, até dez vezes. Com quatro tentativas coladas, três processos gravando juntos perdiam de 2% a 7% dos lotes; no mesmo cenário, agora, nenhum de 900. Ler o que outro processo gravou custa a janela nova, lida pelo SQL (0,6 ms num log de 14 mil eventos), e não o ramo inteiro (117 ms).

   Abrir o banco parte do último **instantâneo** da projeção (`projection/instantaneo.py`), guardado no mesmo arquivo, e dobra só o que veio depois dele: 55 a 80 ms num log de 14 mil eventos, contra 200 ms do replay completo. O instantâneo é cache, não verdade. Ele só vale se o evento na posição do corte for o mesmo de quando foi gravado e se a impressão digital do código de projeção for a de agora; qualquer divergência cai no replay, e `reparar-sequencias` apaga todos.

---

## ⚖️ Governança Configurável

Quem faz cada gesto que antes era sempre do humano deixou de ser fixo: é uma
**política**, em dois níveis (global e por projeto), guardada no próprio grafo
para o replay dar o mesmo veredito. São onze gestos: `responder_questao`,
`promover_aprendizado`, `constraint`, `estrutura`, `excluir`, `fechar_goal`,
`encerrar_sessao`, `liberar_posse_alheia`, `integracao`, `max_correcoes` e
`acao_externa`. Cada um vale `humano` (só o humano faz) ou `arbitro` (o humano e o papel
`arbitro` fazem); `estrutura` vale `estrito` ou `ilimitado`, `max_correcoes` é
um inteiro de 0 a 5, as reprovações em cadeia antes do teto (a de ordem N escala; 2 = a original e a primeira correção), e
`acao_externa` vale `humano` ou `executor`: quem assume e entrega a `Task` cuja
entrega é um gesto no mundo, sem arquivo (enviar um e-mail, marcar uma reunião).
Os dois presets fixos a deixam com o humano; só a `personalizada` a entrega ao executor. A tabela completa está na
[Especificação Ontológica](docs/ONTOLOGY.md#5-governança-configurável).

**Três presets.** `governanca_maxima` (todos os gestos com o humano, estrutura
estrita, `max_correcoes` 2) é o padrão, e vale sem nó `Governanca`. `arbitragem_maxima`
entrega ao árbitro todos os gestos que a política pode delegar (estrutura
ilimitada, `max_correcoes` 2). Os dois são fixos. `personalizada` é a única editável,
gesto a gesto, e fica sempre guardada à parte: trocar para um preset fixo não a
apaga, e voltar a ela a recupera intacta.

**Herança global para projeto.** O nó `governanca-global` guarda a política
global. Cada `Projeto` herda dela (`herdar`, o padrão), escolhe um preset próprio
ou usa uma `personalizada` parcial, em que cada gesto pode ser sobrescrito ou
`herdar` da global por gesto. Um `Projeto` com o `nivel_autonomia: ilimitado`
legado, sem política própria, segue valendo `estrutura: ilimitado`. A política de
um nó é a do projeto que o contém pelas arestas de contenção (`contem`, `produz`,
`decompoe`); se são vários projetos, vale a mais restritiva, gesto a gesto.

**O que é sempre humano**, em qualquer preset: a **promoção global** de um
`Aprendizado`, **configurar a governança** (o nó `Governanca` e as propriedades
`governanca` e `nivel_autonomia` do projeto) e o **push** do git. É o meta-portão:
um agente que escrevesse a política se daria todos os gestos. O árbitro também não
responde a `Question` que abriu nem promove o `Aprendizado` que registrou.

**O veredito é regra do kernel, não gesto.** Em todo preset, um agente só conclui
uma `Task` com veredito de revisão `aprovado` (de revisor, humano ou árbitro);
uma correção aprovada supera a rejeição que a motivou, e o aceite no teto de
reprovações em cadeia, por uma `Decision`, é a outra porta.

**Como configurar.**

- **Aba Configurações.** Na interface web (`graphow web`), a engrenagem da faixa de ícones à esquerda (ou o comando "Configurações: governança e operação" da paleta, `Ctrl+P`) abre a aba. Escolha o escopo (Global ou um projeto), um preset nos cartões e, na `personalizada`, o valor de cada gesto; no projeto cada gesto pode `herdar`. A tabela mostra a origem de cada valor, as linhas sempre humanas e a auditoria do que o árbitro fez. Escolher um preset já grava.
- **`configurar_governanca`.** O equivalente pelo MCP, numa sessão humana: `escopo` (`global` ou o id de um `Projeto`), `preset` e `personalizada` opcional. Devolve a política efetiva e a origem de cada gesto. `configurar_autonomia_projeto` segue como o caminho legado.
- **Subagente `graphow-arbitro`.** Despachado pela raiz da orquestração quando a política lhe concede o gesto, decide num contexto novo o que a política entrega ao árbitro (responder ou descartar `Question`, promover `Aprendizado` ao Setor ou Projeto, criar `Constraint`, fechar `Goal`, liberar posse órfã, encerrar sessão esquecida) e escala ao humano o resto.

---

## 🔌 Superfície de Ferramentas MCP (Model Context Protocol)

O `GraphowMCPServer` expõe 23 ferramentas para consumo por agentes de IA. O **papel do agente não é um argumento**: ele é fixado na abertura da sessão (`graphow mcp --papel <papel>`) e qualquer chamada que traga `papel` é recusada.

A falha de uma ferramenta volta no resultado com `isError: true`, inclusive argumento de tipo errado e banco travado por outro escritor: antes, um `TypeError` ou um `sqlite3.OperationalError` derrubavam o processo MCP. Linha que não é JSON recebe `-32700`, e lote ou requisição sem `method` recebem `-32600`.

| Ferramenta | Descrição |
| :--- | :--- |
| **`ler_vista`** | Materializa o subgrafo do nó alvo formatado em Markdown, respeitando orçamentos estritos de tokens (ex: 1500, 500, 200). Num contêiner, traz o **panorama agregado** dos filhos em vez de listar a subárvore. Aceita `escopo="ativo"` para podar a navegação até o trabalho não concluído, e `perspectiva` para ler o alvo como outro papel o lê: é o teste do executor frio, feito pelo planejador antes de despachar. |
| **`expandir_no`** | Fornece visão detalhada sob demanda de propriedades e arestas incidentes de um nó específico. |
| **`propor_patch`** | Submete propostas de alteração via operações JSON Patch com validação atômica. |
| **`abrir_questao`** | Cria um nó `Question` e uma aresta `bloqueia` sobre uma `Task`, sinalizando dúvida ao humano. Aceita `titulo` curto — é o que o card mostra no canvas — e guarda o corpo da dúvida na propriedade `pergunta`; sem `titulo`, ele sai do começo da pergunta. |
| **`buscar`** | Busca textual *case-insensitive* ranqueada por relevância, cortada em `limite` (padrão 5, teto 50) e sempre acompanhada de `total` e `truncado`. Filtra por `TipoNo` e por `escopo`. |
| **`proximas_tarefas`** | Fila de trabalho da sessão ou do `Goal`: tarefas com dependências concluídas, sem dúvida aberta e sem posse de outro agente, em ordem de atendimento. Cada tarefa traz `modelo`, `trilha`, `entrega` e `arquivos_alvo`, com que o orquestrador escolhe o executor (ou devolve a ação externa à pessoa), o revisor e o que roda em paralelo. |
| **`assumir_tarefa`** | Adquire a posse exclusiva de uma `Task` e a move para `em_andamento`. Exigido antes de qualquer mudança de status. |
| **`liberar_tarefa`** | Devolve a posse de uma `Task`, sem alterar o status registrado. O humano devolve a posse de qualquer autor (a de um subagente que terminou sem liberar), e o árbitro também quando o gesto `liberar_posse_alheia` está com ele na política. |
| **`minhas_questoes`** | Lista as dúvidas abertas por esta sessão, com a resposta (do humano ou do árbitro) quando já houver. |
| **`aguardar_resposta`** | Long-poll até a dúvida ser encerrada (pelo humano ou pelo árbitro), ou até o prazo expirar. Substitui o polling manual com `expandir_no`. |
| **`criar_projeto`** | Cria o nó `Projeto` raiz e define o nível de autonomia dos agentes nele. |
| **`criar_setor`** | Cria o `Setor` e a aresta `contem` que o liga ao `Projeto`. |
| **`criar_sessao`** | Cria a `Sessao` e a aresta `contem` que a liga ao `Setor`. |
| **`criar_tarefa`** | Cria uma `Task` com aresta `produz` e hierarquias opcionais. Para a orquestração, grava `modelo` (recusado sem `motivo_modelo`), `trilha` (`leve` ou `completa`, a leve recusada em Opus), `entrega` (`artefato` ou `acao_externa`), `arquivos_alvo` e `corrige`, e liga à tarefa por `orienta` cada `Decision` listada em `decisoes`. |
| **`concluir_tarefa`** | Transiciona a `Task` para `concluido`, se nenhuma `Question` aberta a bloquear. |
| **`responder_questao`** | Registra a resposta e destrava a `Task`; grava `respondida_por` e `respondida_por_papel`. Gesto `responder_questao` da política: do humano, ou do árbitro quando a política de governança do projeto lhe entrega o gesto. O árbitro não responde a `Question` que ele mesmo abriu. |
| **`configurar_autonomia_projeto`** | Legado: ajusta o `nivel_autonomia` do projeto, que a política lê como o gesto `estrutura`. Prefira `configurar_governanca`. **Sempre sessão humana.** |
| **`configurar_governanca`** | Grava a política de governança: `escopo` (`global` ou o id de um `Projeto`), `preset` (`governanca_maxima`, `arbitragem_maxima`, `personalizada`, e `herdar` no projeto) e `personalizada` opcional (gesto para valor). Os presets fixos não mudam; a `personalizada` é mesclada na salva e nunca apagada ao trocar de preset, e no projeto `herdar` apaga a sobrescrita do gesto. Cria o nó `governanca-global` se faltar e devolve a política efetiva e a origem de cada gesto. **Sempre sessão humana**, árbitro inclusive. |
| **`encerrar_sessao`** | Encerra a `Sessao`: status `concluida` e resumo opcional. A vista da sessão passa a abrir pelo **fechamento determinístico** (decisões vigentes, dúvidas abertas, restrições, último artefato). Gesto `encerrar_sessao` da política: do humano, ou do árbitro quando a política de governança do projeto lhe entrega o gesto; o harness encerra pelo hook de fim. |
| **`registrar_aprendizado`** | Cria um `Aprendizado` pendurado na `Sessao` e ligado por `deriva_de` a cada nó de origem. Sem origem no mesmo lote, o `InvariantGate` recusa com `aprendizado_sem_origem`. Com `substitui`, consolida: a aresta para cada `Aprendizado` absorvido nasce no mesmo lote. |
| **`promover_aprendizado`** | Dá alcance ao `Aprendizado`: aresta `vale_para` um `Projeto` ou `Setor`, ou a marca `alcance: global`. A partir daí ele entra na seção **Aprendizados Aplicáveis** da vista de toda tarefa sob esse alcance. Gesto `promover_aprendizado` da política: do humano, ou do árbitro quando a política de governança do projeto lhe entrega o gesto; grava `promovido_por` e `promovido_por_papel`, e a promoção global é sempre do humano. O árbitro não promove o `Aprendizado` que ele mesmo registrou. Sem alvo, promove ao `Setor` da sessão de origem, o alcance padrão; o `Projeto` fica para o que vale em toda tarefa dele, e o global para o que vale em qualquer projeto. |
| **`excluir_em_lote`** | Remove atomicamente uma coleção de nós e arestas. Gesto `excluir` da política: do humano, ou do árbitro quando a política de governança do projeto lhe entrega o gesto em todos os alvos do lote. |
| **`excluir_projeto`** | Remove o projeto e, opcionalmente, seus descendentes. Gesto `excluir` da política: do humano, ou do árbitro quando a política de governança do projeto lhe entrega o gesto. |

Duas ferramentas são sempre do humano: `configurar_governanca` e
`configurar_autonomia_projeto` escrevem a política que decide o que cada papel
pode fazer, e um agente que as executasse desligaria todos os portões. As demais
restritas (`responder_questao`, `promover_aprendizado`, `encerrar_sessao`,
`excluir_projeto`, `excluir_em_lote`) dependem da política efetiva do projeto do
alvo: com a `governanca_maxima` são do humano, com a `arbitragem_maxima` também do
papel `arbitro` (`graphow mcp --papel arbitro`), e planejador, executor e revisor
são recusados em qualquer política. A recusa por nome de ferramenta é a primeira
camada, não a única: o `RoleGate` impõe as mesmas garantias contra qualquer caminho,
inclusive um `propor_patch` cru.

**O servidor se apresenta.** A resposta de `initialize` traz `instructions` com
o protocolo de memória (`graphow.context.protocolo`): comece por `ler_vista`,
registre `Evidence` e `Decision` enquanto trabalha, destile `Aprendizado` antes
de terminar, condense a sessão anterior se a `Task` ficou pendente, e o que o
papel da conexão pode criar, lido do `RoleGate`. As descrições das ferramentas
dizem quando usá-las, não só o quê: é o que um agente que nunca leu a skill
recebe junto das ferramentas.

### O ciclo de um agente autônomo

As ferramentas acima fecham as três decisões que um agente sem supervisão
precisa tomar sozinho:

1. **O que fazer** — `proximas_tarefas(id_sessao)` devolve a fila já filtrada.
2. **Trabalhar sem colidir** — `assumir_tarefa` toma a posse; o kernel recusa
   qualquer mudança de status vinda de quem não a detém.
3. **Quando parar e retomar** — `abrir_questao` escala, `aguardar_resposta`
   espera em long-poll, e `minhas_questoes` recupera o que ficou pendente na
   sessão anterior.

---

## 📚 Documentação Gerada a Partir do Código

O catálogo técnico em [`docs/`](docs/) **não é mantido à mão**: ele é derivado da
árvore sintática do próprio código por `graphow docs-gerar`. Documentação escrita à
mão diverge do código em silêncio — foi assim que este projeto chegou a ter três
contagens diferentes das ferramentas MCP e duas promessas que a implementação
contradizia.

```bash
# Regenerar o índice e os dossiês
graphow docs-gerar

# Só conferir se estão em dia (sai com código 1 se não estiverem)
graphow docs-gerar --conferir
```

A estrutura tem duas camadas:

- **[`docs/INDEX.md`](docs/INDEX.md)** — o mapa: pilares com o mecanismo que os
  sustenta, roteamento por intenção, regras de engenharia e o inventário das alas.
  Compacto de propósito; o detalhe mora nos dossiês.
- **[`docs/setores/`](docs/setores/)** — um dossiê por pacote, com o catálogo de
  módulos, classes, campos, assinaturas tipadas e constantes.

A única parte escrita à mão é o texto de missão de cada ala, em
`DEFINICOES_DE_SETOR` ([`src/graphow/documentacao/setores.py`](src/graphow/documentacao/setores.py)).
Um pacote novo sem ala declarada — ou uma ala sem pacote — faz a geração falhar.

`tests/qualidade/test_documentacao_alinhada.py` compara o que está em `docs/` com o
que o código produziria agora: alterar o código sem regenerar quebra a suíte.

**Documento canônico escrito à mão** (conceitual, não catalográfico):
- **[🧩 Especificação Formal da Ontologia (`docs/ONTOLOGY.md`)](docs/ONTOLOGY.md)**: Vocabulário semântico, temporalidade do log, separação Navegação vs Trabalho, matriz das 13 arestas permitidas, matriz de papéis (com a coluna "conforme a política") e a Governança Configurável: os onze gestos, os presets, a herança e a regra do veredito.

---

## 🚀 Instalação e Execução

### Pré-requisitos
- Python $\ge$ 3.11
- [Claude Code](https://claude.com/claude-code) (CLI ou app desktop), para a memória e a orquestração

### 1. Instalar o pacote

A instalação tem de ser editável e a partir de um checkout: o `graphow setup`
copia as skills e os subagentes de `.agents/`, que não vão dentro do pacote.

```bash
git clone https://github.com/DavidLeati/graphow.git
cd graphow
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"         # [dev] traz o pytest; sem testes, basta "pip install -e ."
```

### 2. Ligar o graphow ao Claude Code

```bash
graphow setup --escrever-settings
```

O comando faz, de uma vez, o que antes eram cinco passos à mão:

| O quê | Para onde |
| :--- | :--- |
| Skills `graphow-mcp` e `graphow-orquestracao` | `~/.claude/skills/` |
| Os sete subagentes da orquestração, com o servidor MCP de cada um apontando para o caminho absoluto do `graphow` | `~/.claude/agents/` |
| Hooks `SessionStart`, `SessionEnd` e `SubagentStop`, também com o caminho absoluto | `~/.claude/settings.json` |
| Permissões: leitura do servidor da sessão, os quatro servidores de subagente e os comandos de medição | `~/.claude/settings.json` |

O caminho absoluto é o que torna o setup confiável: com o pacote num venv, o
`graphow` só está no PATH de quem ativou o venv, e o processo do app desktop não
o acha. O hook falhava calado e a memória não chegava.

A mescla no `settings.json` preserva o que já estiver lá, troca o hook do
harness em vez de duplicá-lo e guarda o arquivo anterior em
`settings.json.graphow.bak`. Sem `--escrever-settings`, o setup não toca no
arquivo e imprime o bloco para você colar.

### 3. O que segue manual

O setup termina imprimindo os três passos que ficam com você:

1. **Registrar o servidor MCP da sessão principal**, uma vez por usuário. O
   setup imprime o comando pronto, com o caminho do executável:
   `claude mcp add --scope user graphow -- "<executável>" mcp --papel humano --autor <você>`.
   O papel é `humano`, e as permissões liberam só as ferramentas de leitura.
   Responder Question, promover Aprendizado e o resto continuam pedindo sua
   confirmação. Outros ambientes (Cursor, Claude Desktop, Antigravity) estão no
   [guia do MCP](.agents/skills/graphow-mcp/references/mcp_setup_guide.md).
2. **Gravar a política de governança** de cada projeto, na aba Configurações do
   `graphow web`. Sem política vale a `governanca_maxima`: o árbitro recusa todo
   gesto, e todo portão para em você.
3. **Reiniciar o Claude Code e conferir** a linha `Banco:` que o hook de início
   imprime: raiz, subagentes e hooks precisam usar o mesmo banco
   (`graphow banco-info`).

Nada precisa existir no grafo antes: a primeira sessão cria o Projeto do
repositório e o Setor `Memoria` (ver [Harness](#-harness-o-grafo-sabe-que-a-sessão-existe)).

### 4. Atualizar

As cópias em `~/.claude` não se atualizam sozinhas. Depois de cada `git pull`,
rode o setup de novo; para só saber se envelheceram (sai com 1 se sim):

```bash
graphow setup --conferir
```

Opções para casos fora do padrão: `--claude-dir` (outro diretório do Claude
Code), `--executavel` (outro `graphow`), `--autor` (padrão: o usuário do
sistema) e `--origem` (outro checkout).

---

## 💻 Guia de Uso

### 1. Interface de Linha de Comando (CLI)

```bash
# Descobrir onde o banco vive (padrão: diretório de dados do usuário, fora de nuvem)
graphow banco-info

# Inicializar o banco de eventos
graphow init

# Trazer um banco antigo, preservando a origem intacta
graphow migrar-banco --origem "C:/caminho/antigo/graphow.db"

# Criar uma tarefa vinculada a uma Sessão
graphow task-create --titulo "Implementar Parser XML" --sessao "sess-01"

# Listar tarefas registradas
graphow task-list

# Imprimir resumo estrutural do Grafo
graphow print

# Abrir o servidor MCP com o papel fixado para a sessão
graphow mcp --papel executor --autor agente-cursor

# No servidor de um subagente: posse própria para cada processo, para executores em paralelo não dividirem a tarefa
graphow mcp --papel executor --autor executor-sonnet --autor-por-conexao

# Regenerar o catálogo de documentação a partir do código
graphow docs-gerar

# Instalar (ou atualizar) skills, subagentes, hooks e permissões no Claude Code
graphow setup --escrever-settings

# Só conferir se as cópias em ~/.claude estão em dia (sai com código 1 se não estiverem)
graphow setup --conferir

# Instalar só a skill graphow-mcp, para ambientes sem a orquestração
graphow skill-instalar

# Registrar o ciclo de vida de uma execução (chamado pelos hooks do ambiente).
# Sem --setor, a sessão nasce no ambiente padrão do repositório em que o comando roda
graphow harness --fase inicio --sessao sess-01 --modelo opus-5
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"

# O fim de um subagente (hook SubagentStop): um Run com os tokens, o modelo e as tarefas que ele assumiu
graphow harness --fase subagente --entrada-hook

# Comparar Goals orquestrados sob configurações de modelo: retrabalho, rejeições na revisão e tokens
graphow orquestracao-medir --goal goal-padrao --goal goal-tudo-opus

# O mesmo, com uma linha por rodada do condutor: minutos, o que fechou e foi revisado na janela, tokens e cota
graphow orquestracao-medir --goal goal-padrao --por-rodada

# Quando o trabalho mora num repositório git: conferir o Goal contra o ramo_base dele, o que o ramo base ganhou desde o merge-base,
# nos caminhos_de_colisao, e que colide com o que o Goal toca (sai com 1 se colidir, 2 se não der para conferir)
graphow base-colisoes --goal goal-migrations --repo . --sem-fetch

# Medir o tamanho da vista contra o despejo da sessão sobre o corpus gravado
graphow avaliar

# Medir a escala do grafo que está no banco: peso do canvas por recorte,
# custo de navegar, custo de buscar e o custo do rollup com o fechamento
graphow medir-escala

# Projetar os aprendizados promovidos num diretório de notas em Markdown
graphow notas-gerar --destino notas

# Só conferir se o acervo está em dia com o grafo (sai com código 1 se não estiver)
graphow notas-gerar --destino notas --conferir
```

### 2. Uso Programático em Python

```python
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer

# 1. Inicializar Repositório e Kernel pela raiz de composição
store, kernel = abrir_kernel_sqlite("graphow.db")
mcp_server = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("agente-planejador", "planejador"))

# 2. Humano cria Sessão e Goal
proposta_inicial = PropostaPatch.criar(DadosPropostaPatch(
    autor="david",
    papel=PapelAutor.HUMANO,
    operacoes=[
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-01", value={"id": "sess-01", "tipo": TipoNo.SESSAO.value, "rotulo": "Sprint 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/goal-1", value={"id": "goal-1", "tipo": TipoNo.GOAL.value, "rotulo": "Substrato Bilateral"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e-prod", value={"id": "e-prod", "origem_id": "sess-01", "destino_id": "goal-1", "tipo": TipoAresta.PRODUZ.value}),
    ],
    justificativa="Inicialização do projeto",
))
recibo = kernel.submeter_patch(proposta_inicial)
assert recibo.sucesso is True

# 3. Agente Planejador consome vista sob orçamento de tokens
# O papel vem da identidade da sessão, não dos argumentos da chamada
vista = mcp_server.executar_ferramenta("ler_vista", {
    "id_alvo": "goal-1",
    "orcamento_tokens": 1000,
})
print(vista["conteudo"])
```

### 3. Interface Web (`graphow web`)

O canvas fica no centro, com a moldura em volta dele. A faixa de ícones à esquerda guarda as ações globais. A lateral
esquerda tem o **explorador** (a árvore Projeto → Setor → Sessão → trabalho,
com o trabalho aberto de cada subárvore ao lado do nome), a **busca**, os
**marcadores** e a **memória**. No centro, cada **aba** abre o grafo num escopo — tudo, um
projeto, um setor ou uma sessão — com trilha, voltar e avançar no cabeçalho. A
lateral direita mostra o nó selecionado em cima (**propriedades**,
**conexões**, **linhagem** e **vista do agente**) e o **histórico** do log
embaixo, com o calendário de atividade e a viagem no tempo. A barra de status
fica no canto: ramo, versão do log, tamanho da tela, zoom, tempo real e
identidade.

| Onde | O que faz |
| :--- | :--- |
| Explorador | Clique abre o contêiner no canvas; Ctrl+clique abre em aba nova; o botão direito cria setor, sessão ou nó já pendurado no pai |
| Busca (`Ctrl+K`, `Ctrl+Shift+F`) | Procura no ramo inteiro, não só no que está na tela, na mesma ordem de relevância do `buscar` do MCP |
| Paleta (`Ctrl+P`) | Lista todo comando da interface, com o atalho de cada um (`?` mostra todos) |
| Canvas | Clique direito em nó, aresta ou fundo abre o menu daquilo; duplo clique num contêiner o abre; duplo clique no fundo cria um nó naquele ponto |
| Histórico | O dia no calendário filtra os eventos; cada evento volta o grafo até ele, em modo somente leitura |
| Memória | Os aprendizados do ramo com origem, alcance e as marcas de substituído e contradito, promovidos ou não, e as sessões com o fechamento e o estado da condensação. Promover fica a um clique, e o menu de qualquer Decision, Evidence, Note, Artifact ou Task registra um aprendizado a partir dele |
| Configurações (engrenagem da faixa de ícones, ou `Ctrl+P`) | A aba da governança: escopo Global ou projeto, os três presets em cartões, a tabela dos onze gestos com o valor e a origem de cada um, as linhas sempre humanas, a operação do projeto (cadência, teto de rodadas e, quando o trabalho mora num repositório git, ramo base e caminhos de colisão) e a auditoria do que o árbitro fez. O que o árbitro respondeu ou promoveu leva o selo "pelo árbitro", e o menu da `Task` libera a posse de outro autor |

**Auto-layout.** O arranjo automático não põe o grafo inteiro num Sugiyama só:
ele monta o desenho em blocos. Cada componente de trabalho vira um bloco em
camadas no sentido do fluxo causal — com as folhas de um mesmo vizinho
(as dezessete evidências de uma decisão) recolhidas numa grade, em vez de numa
coluna de quatro metros. Cada bloco vai para o menor contêiner que abriga todos
os seus nós, e por isso nenhuma aresta de trabalho atravessa uma sessão alheia.
O conteúdo de uma sessão se empacota embaixo do cartão dela, os filhos de
árvore descem numa coluna ao lado do pai, e a coluna só se reparte quando
passa da altura de uma página — que é calculada e recalculada até o desenho
inteiro ter a proporção da tela. Duzentos e vinte nós saem em 8000 × 7000 px,
sem um cartão sobre o outro; dois mil e quinhentos nós levam 100 ms. O corredor
de uma aresta longa tem teto de altura: sem ele, a altura se realimentava a cada
relaxação, e uma sessão de mil nós saía com y na casa de 7e12. O arranjo tem
testes próprios em `tests/web/js`, rodados por `node --test` e chamados pela
suíte do pytest quando há Node no PATH.

Quatro leituras sustentam a moldura, todas resolvidas no servidor:

| Rota | Para quê |
| :--- | :--- |
| `GET /api/canvas?setor=<id>` | Escopo por Setor, ao lado de `projeto` e `sessao`. Aberta uma Sessão, só ela e o que produziu vão para a tela |
| `GET /api/busca?termo=&tipos=&limite=` | Busca ranqueada sobre o ramo, com a sessão de cada nó e o trecho onde o termo casou |
| `GET /api/ontologia` | Tipos de nó, pares de aresta aceitos e vocabulário de status, lidos da tabela do `SchemaGate` — a tela não mantém cópia |
| `POST /api/nodes` com `contido_em` | Cria o contêiner e a aresta `contem` até o pai no mesmo lote: se o portão recusar a aresta, o nó também não entra |
| `GET /api/memoria` | Os aprendizados e as sessões do ramo para o painel de memória, na mesma leitura do acervo de notas. `POST /api/memoria/aprendizados` e `POST /api/memoria/promocoes` recebem do humano o registro e a promoção, sob a identidade do servidor |
| `GET /api/governanca`, `PUT /api/governanca/global`, `GET`/`PUT /api/projetos/<id>/governanca`, `GET /api/governanca/auditoria?limite=` | A política global e a do projeto (a configuração guardada, a política efetiva e a origem de cada gesto, mais o catálogo de gestos e presets lido da própria política), a escrita pelo humano e os eventos do árbitro. `POST /api/tarefas/<id>/liberar-posse` devolve a posse de uma tarefa |

---

## 🔬 Observabilidade: Spans do Kernel e Taxonomia MAST

**O que existe, dito com precisão:** o Graphow **não embarca o SDK do
OpenTelemetry** e não fala OTLP. O que ele faz é emitir spans que seguem a
convenção de atributos **GenAI** e escrevê-los em NDJSON, um span por linha,
com os nomes de campo do modelo OTLP (`traceId`, `spanId`, `name`,
`attributes`). A ponte para um coletor é sua, e é curta.

**Quem emite:** o `WriteKernel`, em toda submissão ao PatchBoard e em todo fato
de ciclo de vida do harness — aceito ou recusado. O destino é injetado e, por
padrão, é `TracerNulo`: sem `--spans`, a telemetria não custa nada.

```bash
graphow --spans spans/graphow.ndjson web
```

**Atributos:** `gen_ai.system`, `gen_ai.model` (nos spans de execução),
`agent.role`, `graphow.autor`, `graphow.patch.id`, `graphow.no.id` (o nó focal
do lote), `graphow.ramo.id` e, na recusa, `graphow.portao` e
`graphow.modo_de_falha`.

**Diagnóstico MAST** (*Why Do Multi-Agent LLM Systems Fail?* Cemri et al.,
2025): o portão que recusa **declara** o modo de falha (`core/falhas.py`); o
avaliador só traduz modo em macro-categoria. Antes ele decidia por substring da
mensagem em português — funcionava, e quebraria na primeira reescrita de texto:

  - `DESALINHAMENTO_DE_AGENTE` (`VIOLACAO_PERMISSAO_PAPEL`, `PROTOTYPE_POLLUTION`)
  - `DESIGN_DO_SISTEMA` (`CICLO_DEPENDENCIA`, `ESTOURO_ORCAMENTO_TOKENS`, `TIPO_DESCONHECIDO`, `CONFLITO_CONCORRENCIA_LOCK`, `CAMINHO_INVALIDO`, `ESTRUTURA_INCOMPLETA`, `REFERENCIA_INEXISTENTE`, `PAR_DE_ARESTA_INVALIDO`, `NO_FORA_DA_HIERARQUIA`, `ELEMENTO_JA_EXISTENTE`)
  - `VERIFICACAO_DE_TAREFA` (`FECHAMENTO_COM_BLOQUEIO_PENDENTE`, `POSSE_DE_TAREFA_AUSENTE`, `APRENDIZADO_SEM_ORIGEM`)

Um teste de AST confere que toda recusa dos três portões declara o seu modo, e
a escada textual sobrevive apenas como rede para vereditos montados fora deles.

---

## 🪪 Identidade da Escrita nas Duas Superfícies

Quem escreveu o quê é a coisa que o produto promete mostrar, então a identidade
é propriedade da **conexão** nos dois lados da ponte, nunca do payload:

| Superfície | Onde a identidade é fixada | O que acontece se o corpo a declarar |
| :--- | :--- | :--- |
| **MCP (agentes)** | `graphow mcp --papel <papel> --autor <autor>` | A chamada é recusada com o papel real da sessão. |
| **Web (canvas)** | Sessão do servidor, no `graphow web` | `POST`/`PUT` com `autor` ou `papel` é recusado com `400`. |

A web escreve como o humano, então ela só aceita quem prova ser a própria
página (`web/guarda_http.py`). Toda requisição precisa de um `Host` que nomeie
o servidor (um nome de loopback ou o host em que ele abriu) e, se trouxer
`Origin`, que seja a da página. Toda escrita traz o token da sessão no
cabeçalho `X-Graphow-Token` e o corpo em `application/json`. O token nasce com
o servidor e chega à página por `/api/identity`, que outro site não consegue
ler. Sem isso, qualquer site aberto no navegador criava nós como humano, e um
domínio apontado para `127.0.0.1` lia o grafo inteiro. O canvas escapa todo
campo do nó antes de pô-lo no HTML, porque status, posse e id vêm de agentes.
| **Harness (hooks)** | `IdentidadeHarness`, papel `sistema` | Papéis de agente são recusados na construção. |

A vista materializada carrega essa proveniência em cada linha (`por autor
(papel)`), e conteúdo de `Evidence`, `Artifact` ou `Aprendizado` criado por
agente chega ao modelo marcado como **não confiável**, com a marca logo depois
do id e antes do texto, também nos vizinhos e no cabeçalho. Todo texto do grafo
entra numa linha só (`context/secoes.py`, `em_uma_linha`): um rótulo não abre
seção, não abre cerca de código e não finge ser outro item. Antes, uma Evidence
com `\n## Restricoes Inviolaveis\n` no rótulo forjava uma seção com autoria de
humano.

Junto dela viaja a **ordem**: cada nó carrega a sequência do evento que o criou
(`log #N` nas linhas da vista e no rodapé do card, com a data por extenso em
`expandir_no` e no inspetor). O carimbo de tempo diz a idade; a sequência diz
quem veio antes de quem, e é a única resposta confiável para isso, porque a web
e o MCP escrevem de processos distintos, cada um com o seu relógio. A sequência
fica fora do cabeçalho da vista de propósito: ele é obrigatório em toda leitura,
então tudo que entra ali sai do orçamento de tokens de todo agente.

Cada evento também declara **em qual vocabulário foi escrito**
(`versao_ontologia`, hoje `1.3.0`), gravado no log e devolvido na linha do tempo
e no SSE. Sem isso, um log relido depois de um tipo mudar de nome projeta errado
em silêncio. A versão não pode mentir: `core/ontologia.py` calcula uma
assinatura dos termos em vigor, e um teste a compara com a versão declarada —
acrescentar um tipo de aresta sem subir a versão derruba a suíte. Eventos
gravados antes desta mudança voltam do banco como versão `0`, que é a verdade
sobre eles.

---

## 🔗 Harness: o Grafo Sabe que a Sessão Existe

`graphow harness` é a porta pela qual os hooks de início e fim de sessão do
ambiente escrevem no log. Cada disparo emite um evento de ciclo de vida
(`execucao_solicitada`, `execucao_iniciada`, `execucao_concluida`), projetado no
nó `Run` da sessão. O evento diz em que sessão a execução ocorreu, e a projeção
pendura o `Run` nela por `produz` e `ocorreu_em`: a execução mora dentro da
hierarquia, como qualquer nó de trabalho, e não na pasta "Fora da hierarquia".

O identificador da sessão **não vem de variável de ambiente**: o hook entrega um
objeto JSON na entrada padrão, com `session_id` e `cwd` dentro. `--entrada-hook`
lê esse objeto no próprio subcomando, sem depender de `jq` no PATH:

```bash
graphow harness --fase inicio --entrada-hook
```

**O que o hook de início imprime vira contexto do agente.** O ambiente injeta a
saída padrão do hook de SessionStart na conversa, e é por aí que a memória
chega sem depender de skill instalada nem de CLAUDE.md: junto do recibo sai a
**vista de retomada** (`harness/retomada.py`): onde a sessão mora (Projeto,
Setor e o id da sessão, que as ferramentas pedem), os aprendizados que valem
ali (promovidos ao Projeto ou ao Setor, globais, e os nascidos no Setor ainda
sem promoção), o que a sessão anterior deixou (balanço, fechamento
determinístico, a condensação em prosa se um agente a escreveu, ou a `Task` de
condensar que ficou pendente, com o id para assumir) e o protocolo de memória,
o mesmo que o servidor MCP declara em `instructions`. Uma sessão retomada
também se apresenta a si mesma. A entrada e a saída do hook são postas em
UTF-8, porque o Windows abre os canos em cp1252 e um aprendizado com acento
chegaria trocado.

**A memória tem ambiente padrão.** Nada precisa existir no grafo antes do
primeiro hook: sem `--setor`, a sessão nasce no repositório em que o hook rodou,
lido do `cwd` do payload. O harness garante o `Projeto` com o nome da pasta do
repositório (um worktree do git conta como o repositório principal, para a
memória não se partir por worktree) e o `Setor` `Memoria` dentro dele, criados na
primeira sessão e reaproveitados nas seguintes. Esse `Projeto` é das sessões do
hook, e não de trabalho. Um `Projeto` que o humano ou o planejador criou com o
nome do repositório não é reaproveitado: o ambiente nasce ao lado dele, com
sufixo no id se o id derivado já estiver ocupado. Um `Setor` chamado `Memoria`
dentro do ambiente é reaproveitado. É por isso que o papel `sistema` cria
`Projeto` e `Setor`: só o ambiente padrão, e nunca o grafo de trabalho.
`--setor <id>` continua valendo para quem quer a sessão em outro lugar.

**Projetos e sessões do hook ficam em raízes separadas.** O ambiente padrão
guarda uma sessão por vez que o agente roda, com os `Run` de telemetria, e no
meio dos projetos ele enchia a árvore e o canvas. A separação é lida da
proveniência, sem propriedade nova: o que nasceu do papel `sistema`, que só o
harness assume, mora no âmbito `hook`; o resto mora no âmbito `projetos`. A
árvore mostra **Todos os projetos** e, à parte, **Sessões do hook**, um ambiente
por repositório. O canvas aberto em cada raiz traz só o que é dela
(`/api/canvas?ambito=projetos|hook`). A sessão do hook continua sendo onde o
agente registra a pergunta ou a nota avulsa que não deve poluir projeto nenhum.
Uma sessão do hook que alguém move para um Setor de trabalho passa a morar nele,
com o que produziu.

Uma sessão que o hook de fim já encerrou e o ambiente retoma volta a `ativa`,
para o painel não a mostrar fechada enquanto o agente trabalha nela. O `source`
do início e o `reason` do fim vão para o `Run` como `motivo`; o `resumo` da
sessão só muda quando alguém o declara, por `--resumo`, por `encerrar_sessao`
ou pelo painel, e o hook de fim nunca o apaga.

Fora de um hook, a sessão é declarada à mão. `--sessao` e `--entrada-hook` são
mutuamente exclusivos e um deles é obrigatório, e um identificador em branco é
recusado pelo analisador — antes era escrito como caminho vazio no patch:

```bash
graphow harness --fase fim --sessao sess-1 --resumo "sprint encerrada"
```

`graphow setup --escrever-settings` grava os três hooks no
`~/.claude/settings.json` com o caminho absoluto do executável. A mesma fiação,
com `graphow` sem caminho, está em `.agents/hooks/graphow_harness_hooks.json`,
e `graphow docs-gerar --conferir` passa cada comando desse arquivo pelo analisador
real e recusa qualquer exemplo que dependa de variável de ambiente.

O motor reativo escreve com origem `comportamento`, distinta de `harness` e de
`humano`, e cada nota reativa nasce ligada à sessão e ao nó que a motivou — nota
órfã não aparece na vista de ninguém.

Quando uma `Sessao` passa a `concluida` — pelo hook de fim, por `encerrar_sessao`
ou pela interface — o comportamento `SessaoEncerrada` abre nela uma `Task` de
condensação (`acao: condensar_sessao`), assinada como planejador. O grafo pede a
própria memória como trabalho: o agente que pega a tarefa lê a sessão, escreve a
`Note` de condensação (`acao: condensacao_de_sessao`) com `deriva_de` para cada
nó condensado, e a vista da sessão passa a abrir por ela. O motor está ligado
nos três processos que escrevem no log: web, MCP e harness.

---

## 🧠 Memória em Camadas

O grafo já era memória de curto prazo: a vista sob orçamento, o rollup, o escopo
ativo e a escada de corte entregam o que está perto do alvo. O que não existia
era consolidação: nada era condensado, e conhecimento antigo só voltava por
descida na hierarquia ou por busca textual. A consolidação tem três degraus,
montados com as peças que já existiam, e cada degrau tem número em
`graphow avaliar`:

| Camada | O que é | Como nasce | Como chega ao agente |
| :--- | :--- | :--- | :--- |
| **Curto prazo** | A sessão viva: alvo, restrições, bloqueios, decisões, vizinhança | O trabalho de sempre | `ler_vista` sob orçamento |
| **Médio prazo** | O fechamento da sessão encerrada: decisões vigentes, dúvidas abertas, restrições, último artefato, e a condensação em prosa | O fechamento é projeção do log, calculada no rollup na primeira consulta depois de cada commit. A prosa é uma `Note` escrita por um agente a partir da `Task` de condensação que o próprio grafo abre quando a sessão encerra | `ler_vista` numa sessão encerrada abre pelo fechamento; o panorama do Setor mostra o fechamento de cada sessão |
| **Longo prazo** | O `Aprendizado`: o que sobrevive ao projeto, com origem obrigatória | `registrar_aprendizado` por qualquer papel; promoção com `promover_aprendizado`, pelo humano ou pelo árbitro conforme a política (a global, sempre pelo humano) | Seção **Aprendizados Aplicáveis** na vista de qualquer alvo: por herança pela hierarquia, por casamento lexical e, se injetado, por índice semântico. Vai inteira (como aplicar, alcance, origem) a linha do que casa com o texto do alvo, até cinco por herança; as demais levam só a afirmação, e `expandir_no` traz o resto |

Três princípios seguram o desenho. Nada derivado é gravado quando pode ser
projetado: o fechamento é uma dobra do estado, e uma sessão reaberta atualiza
sozinha. Memória diz de onde veio: um `Aprendizado` sem `deriva_de` no mesmo
lote é recusado no portão, como um nó sem aresta de contenção. E memória que
cai primeiro sob pressão de orçamento não é memória: a seção de aprendizados e
o fechamento retêm como `MEMORIA`, e só saem da vista no degrau em que a
navegação também sai. Antes de sair ela encolhe: logo depois do contexto, e
antes do apoio e das decisões que governam a tarefa, os aprendizados vão só
com a afirmação, a proveniência e as marcas, e `expandir_no` traz o resto.
As restrições invioláveis ficam para depois de tudo isso, e também encolhem
antes de sair: primeiro cada `Constraint` vai numa linha sem propriedades, sob
um título que pede `expandir_no` antes de agir, depois a lista corta com as
demais anunciadas. Uma tarefa com sessenta restrições saía antes só com o
cabeçalho em qualquer orçamento abaixo de 3200 tokens.

Esquecer é marcar, nunca apagar: `substitui` entre aprendizados deixa o antigo
no grafo, no painel e no acervo com `SUBSTITUIDO`, e a vista carrega só o
vigente, cuja linha diz quem ele substitui. Enquanto o substituto não é
promovido, o antigo segue valendo, avisado de que há um substituto à espera:
substituir é propor, promover é aceitar, e quem aceita é o humano ou, conforme a política, o árbitro. `contradiz` de uma
`Evidence` nova marca o aprendizado com `CONTRADITO` sem tirá-lo da vista,
`valido_ate` tira o vencido, e remover é do humano (ou do árbitro, com o gesto `excluir`). O
índice semântico é opcional e injetável no `MaterializadorContexto`, com padrão
nulo: sem configurar, não custa nada e não traz dependência.

**A memória se consolida.** Quando uma sessão abre num Setor cujo alcance (o
Setor, o Projeto ou o global) passa de doze aprendizados vigentes, o
comportamento `AprendizadosAcumulados` abre nela uma `Task` de consolidar
(`acao: consolidar_aprendizados`), com os ids vigentes na descrição. Quem a
pega agrupa por tema e registra, por `registrar_aprendizado`, um aprendizado
por grupo, com `substitui` para os absorvidos e `deriva_de` para as origens
deles. Nada é apagado: os absorvidos saem da vista quando o consolidado é promovido, pelo humano ou pelo árbitro conforme a política do projeto. É a mesma compactação que a condensação faz com a sessão, um
nível acima, e a vista de retomada aponta a `Task` enquanto ela estiver aberta.

**A memória tem ambiente padrão e tem lugar na tela.** O hook de início não
precisa de um Setor criado à parte: a sessão nasce no `Projeto` com o nome do
repositório, dentro do `Setor` `Memoria`, que o harness cria na primeira vez e
reaproveita depois. E o canvas tem um painel de **Memória** na lateral esquerda:
os aprendizados do ramo com origem, alcance e marcas, promovidos ou não, e as
sessões com o fechamento e o estado da condensação. Registrar e promover ficam
ali, no inspetor e no menu de qualquer nó de trabalho; a tela escreve como humano,
e a promoção global é sempre dele.

**Os agentes ficam sabendo.** Três canais dizem ao agente o que o grafo
espera dele, sem depender de ninguém lembrar: a vista de retomada que o hook de
início imprime no contexto, as `instructions` do servidor MCP e a skill
`graphow-mcp`, que `graphow setup` copia para o diretório de skills do
ambiente (`~/.claude/skills` por padrão) e atualiza a cada execução, no lugar
das cópias por projeto que envelhecem; `graphow setup --conferir` diz se a
cópia envelheceu.

**O acervo de notas é projeção.** `graphow notas-gerar` renderiza um diretório
de notas em Markdown a partir dos aprendizados promovidos, uma nota por
aprendizado, no formato *afirmação, como se sabe, como aplicar*: a origem é
derivada das arestas `deriva_de`, com o identificador e a posição no log de
cada nó citado, e os links entre notas saem de `substitui` e `contradiz`. O
grafo é a fonte; o acervo é leitura, regenerável do zero, e `--conferir` acusa
qualquer nota escrita à mão. O hook de fim de sessão do ambiente escreve no
grafo pelo harness, e é dali que o motor reativo pede a condensação.

---

## 🎼 Orquestração: um Goal, vários agentes, o estado no grafo

O Graphow sustenta uma orquestração em que o estado mora no grafo, e não na
conversa. Um orquestrador no papel `planejador` decompõe o `Goal` em `Task`,
registra as decisões e despacha agentes, cada um com o próprio servidor MCP,
porque o papel é fixado na abertura da conexão: executores no papel `executor`,
revisores no papel `revisor`. Nenhum deles precisa de especificação em prosa: o
despacho pode ser só o id da tarefa, e a vista dela traz o resto. É o que deixa
cada rodada do trabalho rodar num subagente novo, o condutor, que começa sem
histórico e o descarta ao devolver. A sessão principal só despacha as rodadas e
para nos portões humanos, sem `/clear` entre uma tarefa e outra.

O kernel sustenta cinco peças desse arranjo:

| Peça | Onde |
| :--- | :--- |
| O planejador registra a `Evidence` do que leu, sempre com o ponteiro: `arquivo`, `linhas` e `trecho`, ou `fonte`, `local` e `trecho`; sem ele inteiro, `evidencia_sem_localizacao` | `kernel/localizacao.py`, `InvariantGate` |
| A `Decision` diz onde vale por `orienta`, e chega à vista de quem executa e de quem revisa mesmo tomada noutra sessão | ontologia 1.2.0 |
| `ler_vista(..., perspectiva="executor")` é o teste do executor frio, feito antes de todo despacho | `mcp/ferramentas_leitura.py` |
| `criar_tarefa` grava `modelo` (com motivo), `trilha`, `entrega`, `arquivos_alvo`, `corrige` e as decisões; `proximas_tarefas` os devolve para o despacho e o paralelismo | `core/orquestracao.py` |
| Cada subagente tem posse própria (`--autor-por-conexao`), e o harness grava um `Run` por subagente, com tokens, modelo e as tarefas que ele assumiu | `harness/transcricao.py` |

Para decidir a divisão de modelos por número, e não por palpite, o mesmo
conjunto de tarefas roda sob configurações diferentes (a propriedade
`configuracao` do Goal), e a medição compara:

```bash
graphow orquestracao-medir --goal goal-tudo-opus --goal goal-padrao
```

O relatório dá, por configuração, as tarefas concluídas sem retrabalho, as
rejeições na revisão e os tokens por tarefa concluída. As tarefas da trilha
leve, que rodam em Sonnet sob qualquer configuração, aparecem à parte na linha
de modelos de cada Goal. Quando os `Run` trazem, o custo por tarefa concluída
ganha os minutos de condutor, os pontos da cota semanal e os tokens sem a
leitura de cache, e a linha de tokens do Goal mostra o total sem ela e os `Run`
sem tokens pelo motivo (`transcricao_ausente`, `sem_agent_id`...). Com
`--por-rodada`, com ou sem `--goal`, cada Goal ganha uma linha por rodada do
condutor. A duração vem das transcrições, e a cota da linha
`Cota: 5h <n>%, semana <n>%` que a raiz escreve no despacho e na parada. Os `Run` dos agentes
despachados vêm do hook `SubagentStop`, que está na fiação de
[`graphow_harness_hooks.json`](.agents/hooks/graphow_harness_hooks.json).

Quando a política de governança do projeto entrega gestos ao árbitro, a raiz
despacha também o subagente `graphow-arbitro`, que decide em contexto novo o que
a política lhe dá (e devolve `Escaladas` para o que segue humano). A orquestração
lê a política na vista, e a `integracao` (commit e merge local, quando a entrega é
código), o `max_correcoes` e a `acao_externa` seguem o que ela diz; o push é
sempre do humano. A `Task` de ação externa que segue com a pessoa volta à raiz
como portão humano: a pessoa faz o gesto, a raiz registra a prova em nome dela
(uma `Evidence` com `fonte` e `resultado`), e a revisão e o fechamento seguem o
ciclo de sempre.

A skill que conduz esse arranjo, `graphow-orquestracao`, está em
[`.agents/skills/graphow-orquestracao`](.agents/skills/graphow-orquestracao/SKILL.md),
e os subagentes que ela despacha em `.agents/agents`. `graphow setup` copia os
dois para `~/.claude`, com o servidor MCP de cada subagente apontando para o
caminho do executável; o resto da configuração está na
[configuração](.agents/skills/graphow-orquestracao/references/configuracao.md).

---

## 📊 Avaliação: Tamanho da Vista contra o Despejo

A métrica que o projeto persegue é tokens por tarefa bem-sucedida, e ela ainda
não tem número: medir sucesso exige um agente real executando as tarefas. O que
`graphow avaliar` mede hoje é a parte determinística dela, o tamanho da vista
que o agente recebe contra o despejo dos nós da sessão, sobre um corpus de
**dez tarefas gravadas** (`src/graphow/avaliacao/`) em que "concluída" é um
rótulo escrito à mão. Ele acrescenta os
dois braços da memória: **retomar uma sessão encerrada** (a abertura da vista
pelo fechamento e pela condensação contra expandir cada `Decision` e `Evidence`
uma a uma) e **entre projetos** (um aprendizado do primeiro projeto chega à
tarefa do segundo, e a que custo, contra despejar o primeiro projeto ou buscar
às cegas):

```bash
graphow avaliar
```

O relatório publica tokens por tarefa nos dois braços, a redução média, as
intervenções humanas por tarefa e a calibração do contador em uso. Ele também
declara os próprios limites: sucesso de tarefa e taxa de patch rejeitado exigem
um agente real; o despejo vai sem as arestas, com menos informação relacional
que a vista; e o contador é uma heurística que, contra tokenizadores BPE de
referência, contou menos tokens do que eles.

### Escala: o grafo real ainda cabe?

`graphow avaliar` corre sobre um cenário gravado, hermético de propósito.
`graphow medir-escala` responde a outra pergunta — *o meu grafo, do tamanho que
está hoje, cabe na tela e no orçamento?* — e por isso corre contra o banco
aberto:

```bash
graphow medir-escala
```

Ela publica três eixos: o peso do payload do canvas sob cada recorte, o custo de
descobrir onde há trabalho aberto (varrer todos os contêineres contra descer
guiado pelo rollup) e o custo de uma busca com e sem limite.

---

## 🔭 Recorte: Rollup, Escopo Ativo e Caminho Crítico

Um grafo de duzentos nós não cabe na tela nem no orçamento. Três recortes
independentes e combináveis resolvem isso, **todos resolvidos no servidor** — um
agrupamento feito só no cliente ainda faria o payload inteiro atravessar a rede.

| Recorte | Canvas | Agente |
| :--- | :--- | :--- |
| **Rollup de subárvore** | `?colapsar=setor\|sessao` mostra só a camada de navegação, cada contêiner com o progresso agregado da sua subárvore | `ler_vista` num contêiner traz a seção *Panorama dos Filhos* |
| **Escopo ativo** | `?escopo=ativo&raio=1` mantém o que está perto de tarefa não concluída ou dúvida aberta | `escopo="ativo"` em `ler_vista` e `buscar` |
| **Caminho crítico** | `?vista=caminho_critico` mantém quem participa de dependência declarada | `proximas_tarefas` já traz `depende_de` e as impedidas com motivo |

O índice de rollup nasce a cada commit, dentro de
`ProjecaoSincronizada._registrar` — ponto único, porque o kernel adota, logo
após o commit, a projeção que ele mesmo dobrou antes de gravar. O commit só
mapeia filhos e órfãos, em tempo linear; o resumo de cada contêiner sai na
primeira consulta e fica guardado até o próximo commit. Resolver de saída a
subárvore de todo nó custava a soma dos tamanhos de subárvore: 10,9 s por
commit numa cadeia de `decompoe` com 5.000 Tasks, contra 3,5 ms agora. Não há
manutenção incremental: a agregação é uma dobra pura do estado, com a mesma
garantia de determinismo do resto da projeção.

A resposta do canvas carrega sempre um bloco `recorte` dizendo quantos nós
ficaram de fora, por qual filtro, e quais nós estão fora de qualquer hierarquia.
Uma tela que mostra 6 de 191 nós sem explicar por quê é indistinguível de uma
tela quebrada.

O escopo ativo tem padrões assimétricos de propósito: ligado no canvas, desligado
no MCP. O humano fecha uma gaveta porque sabe que pode reabri-la; o agente não
sabe que ela existe, e `Decision` e `Evidence` são exatamente a memória que
impede re-decidir.

---

## 📐 Regras de Qualidade e Engenharia de Código

O código do Graphow segue padrões rigorosos de engenharia de software validados de forma automatizada via AST em `tests/qualidade/`:

- **Limite de Linhas por Arquivo:** Máximo de 400 linhas por arquivo.
- **Limite de Linhas por Função:** Máximo de 30 linhas por método/função.
- **Aninhamento:** Máximo de 2 níveis de indentação interna (uso extensivo de *guard clauses*).
- **Parâmetros Posicionais:** Máximo de 3 parâmetros posicionais por assinatura (agrupamento via DTOs/dataclasses imutáveis).
- **Tipagem Estática:** 100% de anotações estáticas explícitas (sem `Any` desnecessário).
- **Imutabilidade como Padrão:** `@dataclass(frozen=True)` em todas as entidades e DTOs.
- **CQRS:** Zero efeitos colaterais em consultas (`GrafoView`).

---

## 🧪 Execução dos Testes

```bash
# Executar a suíte completa de testes
pytest tests/ -v

# Executar a verificação estrita de regras de qualidade de código
pytest tests/qualidade/test_estrutura_codigo.py tests/qualidade/test_aninhamento_e_excecoes.py -v

# Executar as invariantes do substrato sobre sequências arbitrárias de patches
pytest tests/qualidade/test_invariantes_do_substrato.py -v

# Executar a invariante da escalação: nenhum agente encerra a própria dúvida
pytest tests/qualidade/test_invariantes_de_escalacao.py -v

# Conferir catálogo gerado e exemplos de linha de comando dos guias
graphow docs-gerar --conferir

# Executar simulação ponta a ponta
pytest tests/test_end_to_end_simulation.py -v
```

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais detalhes.
