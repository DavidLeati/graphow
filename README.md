# Graphow 🌐

> **Substrato Bilateral de Grafo Agêntico para Coordenação Humano-IA**  
> *Common Ground compartilhado, governança em 4 portões (PatchBoard), log append-only determinístico (ActiveGraph) e divulgação progressiva com orçamento de tokens.*

---

## 📌 Visão Geral

O **Graphow** é uma plataforma de estado compartilhado (*common ground*) que atua como substrato bilateral para coordenação estruturada entre pessoas e agentes autônomos de Inteligência Artificial.

Desde a fase 1 da reestruturação, **quem coordena é código**: `graphow orquestrar` conduz um `Goal` num laço que planeja, escreve os testes de aceite, executa, verifica e fecha, e os LLMs entram só onde há julgamento, cada um numa sessão `claude -p` nova (o planejador, o autor de aceite, um executor por fatia, o revisor da fatia de risco e o verificador adversarial de cada marco). Desde a fase 2, **o aceite está no centro**: o que prova que o Goal está pronto é escrito antes da implementação, por quem não implementa, atacado por um verificador em contexto novo a cada marco, e o kernel recusa fechar o Goal sem essa prova no commit atual. Nenhum agente escreve no grafo: cada um devolve JSON validado por schema, e o orquestrador grava o livro-razão (com o papel `orquestrador`) e commita cada fatia numa branch do Goal. O grafo é o livro-razão da intenção do humano, das decisões e das verificações; o MCP fica para a sessão do humano, onde o gerente alinha a demanda.

O trabalho coordenado não precisa ser software. O mesmo grafo serve a uma pesquisa, a um relatório, a uma análise, a um planejamento ou a uma operação: o `Goal` é a intenção, as `Task`s entregam documentos, dados ou código, a `Evidence` diz de onde veio cada fato (um trecho de arquivo, uma URL, uma reunião) e a verificação confere a entrega contra os critérios de aceite (o critério de `checagem` é provado por uma lista que o verificador executa, e não por teste). A tarefa que é um gesto no mundo, como enviar um e-mail ou marcar uma reunião, tem entrega própria (`acao_externa`), e a política de governança diz se ela é da pessoa ou do agente. O que é próprio de código (testes, `git diff`, integração de ramos, colisões de migrations) entra como caso, quando a entrega é código.

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
  │   ORQUESTRADOR EM CÓDIGO (graphow orquestrar) e MCP    │
  │   da sessão do humano. Planejador, executor e          │
  │   verificador devolvem JSON; o orquestrador grava      │
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
- **`Criterio`**: Critério de aceite do `Goal` (ontologia 1.7.0): código (`C1`), texto completo, tipo de verificação (`teste` ou `checagem`) e o estado que as verificações lhe dão (`pendente`, `atende`, `parcial`, `nao_atende`), com os testes de aceite que o provam.
- **`Achado`**: Problema que uma verificação achou, com a prova, o local e os critérios ou decisões que ele fere (`fere`). A gravidade é decidida por código: bloqueante quando fere algo com entrada de uso previsto, acompanhamento quando não fere nada ou quando a entrada é extrema e a segunda opinião concorda. Nunca vira `Note`.
- **`Artifact`**: Entregável concreto de código, documento ou configuração.
- **`Evidence`**: Dado empírico, benchmark ou prova que justifica decisões.
- **`Run`**: Registro de execução e telemetria de um modelo de IA.
- **`Note`**: Anotação livre, aviso reativo ou contexto efêmero. Com `acao: condensacao_de_sessao`, a condensação em prosa de uma sessão encerrada.
- **`Aprendizado`**: Memória de longo prazo, o que sobrevive ao projeto. Nasce com origem obrigatória (`deriva_de`) e só alcança outros projetos quando é promovido (`vale_para`, pelo humano ou pelo árbitro conforme a política; `alcance: global`, sempre pelo humano).

### 3. Matriz de Arestas Permitidas (14 Tipos)

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
| **`escopa`** | `Constraint` $\rightarrow$ `Goal` / `Task`; `Criterio` $\rightarrow$ `Goal` | **humano**, ou o árbitro com `constraint` | Restrição mandatória sobre a execução; do `Criterio`, o critério de aceite do Goal. |
| **`fere`** | `Achado` $\rightarrow$ `Criterio` / `Decision` | **humano** (e o orquestrador, pelo contrato dele) | O critério ou a decisão que o achado toca: é por ela que o código o faz bloqueante. Nem a estrutura ilimitada a abre a agentes. |
| **`deriva_de`** | `Artifact` $\rightarrow$ `Task` / `Artifact`; `Evidence` $\rightarrow$ `Artifact` / `Task`; `Note` $\rightarrow$ `Task` / `Decision` / `Evidence` / `Artifact`; `Aprendizado` $\rightarrow$ `Evidence` / `Decision` / `Note` / `Artifact` / `Task`; `Achado` $\rightarrow$ `Evidence`; `Task` $\rightarrow$ `Achado`; `Artifact` $\rightarrow$ `Criterio` | humano, executor, revisor | Proveniência de artefatos, do achado (a verificação que o achou), da fatia de correção (o achado que ela corrige), do commit dos testes de aceite (o critério que eles provam), da evidência que avalia um trabalho, de notas reativas, da condensação de uma sessão e da origem de um aprendizado. |
| **`vale_para`** | `Aprendizado` $\rightarrow$ `Projeto` / `Setor` | **humano**, ou o árbitro com `promover_aprendizado` | Alcance de um aprendizado promovido: entra na vista de toda tarefa sob esse contêiner. Nem a estrutura ilimitada a abre a agentes comuns. |
| **`orienta`** | `Decision` $\rightarrow$ `Task` / `Goal` | humano, planejador | A decisão que vale para a tarefa ou o objetivo, herdada pela decomposição. Chega à vista de quem executa e de quem revisa mesmo tomada noutra sessão. O executor não a cria nem a remove: não mexe no que governa a própria tarefa. |

---

## 🛡️ Os 4 Portões de Governança (PatchBoard)

Toda mutação no grafo (seja humana ou de IA) é submetida via JSON Patch RFC 6902 e processada sequencialmente:

1. **Portão 1 — `SchemaGate`:** Sanitização estrita contra *prototype pollution* (`__proto__`, `constructor`, `__class__`), checagem de tipos e validação da tabela ontológica de pares válidos de arestas. Só aceita as formas que o conversor grava como elas são (`add`/`remove` em `/nos/<id>` e `/arestas/<id>`, `add`/`replace` em `/nos/<id>/rotulo`, `add`/`replace`/`remove` em `/nos/<id>/propriedades/<chave>`), sem segmento vazio (`//` ou `/` no final), e todo `add` cria um id novo, o mesmo do campo `id` do valor. Também confere a política de governança declarada (`preset` e `personalizada` do nó `Governanca` e da propriedade `governanca` do `Projeto`): preset ou gesto desconhecido, valor fora do domínio do gesto e um segundo nó `Governanca` com id diferente de `governanca-global` caem com `estrutura_incompleta`, e nenhuma aresta toca o `Governanca`. Antes disso, uma barra no final de `.../propriedades/status/` escapava da regra do RoleGate e encerrava a `Question`, um `test` no status concluía uma `Task` com dúvida bloqueante aberta, um `add` sobre id existente transformava uma `Constraint` em `Note`, e um `add` em `/arestas/<id>/...` gravava um evento que quebrava toda leitura do ramo.
2. **Portão 2 — `RoleGate`:** Matriz de permissões por papel, aplicada sobre a identidade da *conexão*, nunca sobre um campo do payload:
   - **`humano`**: Acesso irrestrito. Só ele faz, em qualquer preset, a promoção global, a configuração da governança e o push; os demais gestos (encerrar uma `Question`, criar/editar `Constraint`, excluir, fechar `Goal`, encerrar `Sessao`, liberar posse alheia, estruturar a camada de navegação) são dele a menos que a política os entregue ao árbitro, e a `Task` de ação externa é dele a menos que a política a entregue ao executor.
   - **`orquestrador`**: O laço do `graphow orquestrar`, único escritor do Goal que conduz, com contrato próprio (`kernel/papel_do_orquestrador.py`): cria a hierarquia do Goal, o Goal, os critérios (`Criterio`), os achados (`Achado`), as decisões, as fatias (`Task`), as dúvidas (`Question` aberta), os commits (`Artifact`), as verificações (`Evidence` ligada ao Goal) e as notas; conclui fatia e fecha o Goal sem posse nem veredito por `Task`. Cada lote dele diz o Goal que conduz e fica preso a ele (o Goal, a Sessao `orq-sessao-<id>`, o que ela produz e a contenção acima dela): não escreve noutro Goal, não liga nó dele a nó do humano ou de outro Goal e não edita aresta. Nunca cria `Governanca` nem `Aprendizado`, não escreve a política, o plano aprovado nem a resposta de uma `Question`, não remove nada, e nenhum servidor MCP abre com ele.
   - Os papéis de agente abaixo (planejador, executor, revisor, árbitro) seguem como contratos do kernel, para o log antigo e para quem escreve em processo; desde a fase 1 nenhum servidor abre com eles, e a fase 4 os reduz.
   - **`planejador`**: Cria `Task`, `Decision`, `Question`, `Note` e a `Evidence` do que leu, sempre localizada (no arquivo ou na fonte); decompõe, ordena e diz com `orienta` onde cada decisão vale. Concluir `Task` exige veredito aprovado, como para todo agente.
   - **`executor`**: Cria `Artifact`, `Evidence`, `Question`, `Note`, `Aprendizado`; assume tarefas e trabalha nelas; proibido de criar tarefas, alterar constraints, trocar a `entrega` de uma `Task` e, salvo quando a política lhe entrega o gesto `acao_externa`, assumir ou entregar a `Task` de ação externa.
   - **`revisor`**: Cria `Evidence`, `Question`, `Note`, `Aprendizado`; valida artefatos. Registra `Aprendizado` quem detém `deriva_de`: executor e revisor.
   - **`arbitro`**: O papel a quem a política de governança do projeto entrega os gestos que tira do humano. Por si só cria só `Evidence`, `Decision` e `Note`; o resto vem da política do projeto do alvo e é recusado onde ela o deixa com o humano. Nunca promove a global, nunca altera a governança, não encerra a `Question` que abriu nem promove o `Aprendizado` que registrou. O subagente e o servidor dele saíram na fase 1: nenhum agente roda com este papel.
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
   - **Veredito para Concluir:** Um papel não humano só escreve `concluido` numa `Task` cujo veredito de revisão efetivo é `aprovado`, em todo preset; sem isso o lote cai com `fechamento_sem_veredito_aprovado`. Só conta o veredito de uma `Evidence` de `revisor`, `humano` ou `arbitro` (o executor não aprova a própria entrega); uma correção aprovada supera a rejeição que a motivou; e o aceite pelo teto de correções, uma `Decision` de `acao: aceite_apos_reprovacao` do planejador, do humano ou do árbitro, justificada pela `Evidence` do veredito vigente, é a outra porta. Ficam isentos o humano, o orquestrador (cujo Goal só fecha com a verificação do Goal limpa no commit atual) e as `Task`s de condensar a sessão e consolidar aprendizados, que o próprio grafo abre sem revisor (`kernel/veredito_de_fechamento.py`).
   - **Fechamento com a Prova:** O `Goal` conduzido pelo orquestrador, ou com `Criterio` ligado, só vai para `concluido` quando a última verificação dele é a final (sobre o Goal inteiro), limpa, feita no commit do código que o Goal grava como ponta da branch (`ponta_do_ramo`; o commit que só muda o documento do Goal não conta), com parecer `atende` para cada critério e nenhum `Achado` bloqueante sem resolver; sem isso o lote cai com `fechamento_sem_verificacao_limpa`. Vale para todo papel, o humano inclusive (`kernel/fechamento_do_goal.py`).
   - **Posse de Tarefa:** Nenhum agente move o status de uma `Task` sem deter o lock dela. Sem isso, dois executores na mesma tarefa não colidiam e o segundo sobrescrevia o primeiro em silêncio. O humano e o orquestrador, único escritor do Goal que conduz, ficam fora da regra.
   - **Locks Exclusivos:** Impede mutações em tarefas travadas por outro escritor, e isso inclui criar ou remover as arestas que redefinem a tarefa (`depende_de`, `decompoe`, `orienta`, `escopa`, `substitui`). `bloqueia` e `deriva_de` seguem livres: a escalação e a proveniência continuam chegando à tarefa travada.
4. **Portão 4 — `WriteKernel`:** Geração dos `EventoLog` e projeção do lote **antes** de gravá-lo (o lote que o acumulador não consegue aplicar volta recusado, e o log fica intacto), persistência do lote inteiro em uma única transação (`BEGIN IMMEDIATE`/`ROLLBACK`, com `UNIQUE(ramo_id, seq)`) e notificação dos observadores — canal SSE e motor reativo.

   Quando outro processo ocupa a posição entre a validação e o commit, o kernel revalida contra o log atualizado, dobrando só o que o outro gravou, e tenta de novo depois de uma espera sorteada que dobra a cada perda, até dez vezes. Com quatro tentativas coladas, três processos gravando juntos perdiam de 2% a 7% dos lotes; no mesmo cenário, agora, nenhum de 900. Ler o que outro processo gravou custa a janela nova, lida pelo SQL (0,6 ms num log de 14 mil eventos), e não o ramo inteiro (117 ms).

   Abrir o banco parte do último **instantâneo** da projeção (`projection/instantaneo.py`), guardado no mesmo arquivo, e dobra só o que veio depois dele: 55 a 80 ms num log de 14 mil eventos, contra 200 ms do replay completo. O instantâneo é cache, não verdade. Ele só vale se o evento na posição do corte for o mesmo de quando foi gravado e se a impressão digital do código de projeção for a de agora; qualquer divergência cai no replay, e `reparar-sequencias` apaga todos.

---

## ⚖️ Governança Configurável

Quem faz cada gesto que antes era sempre do humano deixou de ser fixo: é uma
**política**, em dois níveis (global e por projeto), guardada no próprio grafo
para o replay dar o mesmo veredito. São dezesseis gestos e leituras: `responder_questao`,
`promover_aprendizado`, `constraint`, `estrutura`, `excluir`, `fechar_goal`,
`encerrar_sessao`, `liberar_posse_alheia`, `integracao`, `max_correcoes`,
`acao_externa` e, do escopo governado, `aprovar_plano`, `responder_desvio`,
`limiar_desvio_por_raiz`, `limiar_desvio_por_goal` e `teto_expansao` (o
`responder_desvio` é do humano até na `arbitragem_maxima`). Cada um vale `humano` (só o humano faz) ou `arbitro` (o humano e o papel
`arbitro` fazem); `estrutura` vale `estrito` ou `ilimitado`, `max_correcoes` é
um inteiro de 0 a 5, as reprovações em cadeia antes do teto (a de ordem N escala; 2 = a original e a primeira correção), e
`acao_externa` vale `humano` ou `executor`: quem assume e entrega a `Task` cuja
entrega é um gesto no mundo, sem arquivo (enviar um e-mail, marcar uma reunião).
A `governanca_maxima` a deixa com o humano, a `arbitragem_maxima` a entrega ao
executor, e a `personalizada` escolhe. A tabela completa está na
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
- **Sem árbitro em execução.** O subagente `graphow-arbitro`, que a raiz da orquestração antiga despachava quando a política lhe concedia o gesto, saiu na fase 1, com o servidor dele. A política segue no kernel (a fase 4 a reduz a dois modos), e o `graphow orquestrar` não a consulta: ele para nos portões fixos do laço.

---

## 🔌 Superfície de Ferramentas MCP (Model Context Protocol)

O `GraphowMCPServer` expõe 25 ferramentas. Desde a fase 1 ele serve à sessão do humano (o gerente e o que o humano conduz): os agentes do `graphow orquestrar` rodam sem MCP do graphow, e o servidor só abre com `graphow mcp --papel humano`. O **papel não é um argumento**: ele é fixado na abertura da sessão e qualquer chamada que traga `papel` é recusada. A redução das ferramentas ao que a sessão do humano precisa é da fase 4.

A falha de uma ferramenta volta no resultado com `isError: true`, inclusive argumento de tipo errado e banco travado por outro escritor: antes, um `TypeError` ou um `sqlite3.OperationalError` derrubavam o processo MCP. Linha que não é JSON recebe `-32700`, e lote ou requisição sem `method` recebem `-32600`.

| Ferramenta | Descrição |
| :--- | :--- |
| **`ler_vista`** | Materializa o subgrafo do nó alvo formatado em Markdown, respeitando orçamentos estritos de tokens (ex: 1500, 500, 200). Num contêiner, traz o **panorama agregado** dos filhos em vez de listar a subárvore. Aceita `escopo="ativo"` para podar a navegação até o trabalho não concluído, e `perspectiva` para ler o alvo como outro papel o lê: lida como o executor a leria, a `Task` mostra se se sustenta sozinha. |
| **`expandir_no`** | Fornece visão detalhada sob demanda de propriedades e arestas incidentes de um nó específico. |
| **`propor_patch`** | Submete propostas de alteração via operações JSON Patch com validação atômica. |
| **`abrir_questao`** | Cria um nó `Question` e uma aresta `bloqueia` sobre uma `Task`, sinalizando dúvida ao humano. Aceita `titulo` curto — é o que o card mostra no canvas — e guarda o corpo da dúvida na propriedade `pergunta`; sem `titulo`, ele sai do começo da pergunta. |
| **`buscar`** | Busca textual *case-insensitive* ranqueada por relevância, cortada em `limite` (padrão 5, teto 50) e sempre acompanhada de `total` e `truncado`. Filtra por `TipoNo` e por `escopo`. |
| **`proximas_tarefas`** | Fila de trabalho da sessão ou do `Goal`: tarefas com dependências concluídas, sem dúvida aberta e sem posse de outro agente, em ordem de atendimento. Cada tarefa traz `modelo`, `trilha`, `entrega` e `arquivos_alvo`, com que o orquestrador escolhe o executor (ou devolve a ação externa à pessoa), o revisor e o que roda em paralelo. |
| **`assumir_tarefa`** | Adquire a posse exclusiva de uma `Task` e a move para `em_andamento`. Exigido antes de qualquer mudança de status. |
| **`liberar_tarefa`** | Devolve a posse de uma `Task`, sem alterar o status registrado. O humano devolve a posse de qualquer autor (a de uma sessão que terminou sem liberar), e o árbitro também quando o gesto `liberar_posse_alheia` está com ele na política. |
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
| **`aprovar_plano`** | Aprova o plano de um `Goal`: acrescenta a próxima versão a `Goal.planos`, com o `seq` do log de agora. Gesto `aprovar_plano` da política: do humano, ou do árbitro quando a política do projeto lhe entrega o gesto (`arbitragem_maxima`). Sem plano aprovado o executor não assume `Task` do Goal (`plano_nao_aprovado`); só a versão do humano é a referência do desvio. Não é o portão do `graphow orquestrar`: o laço tem o dele, que o humano abre com `--aprovar-plano`. |
| **`responder_desvio`** | Responde ao alerta de desvio do `Goal`: acrescenta a resposta a `Goal.respostas_de_desvio`, com `raiz` opcional (a decisão respondida). Gesto `responder_desvio` da política: do humano em qualquer preset fixo, do árbitro só na `personalizada`. Só a resposta do humano zera o contador. |

Duas ferramentas são sempre do humano: `configurar_governanca` e
`configurar_autonomia_projeto` escrevem a política que decide o que cada papel
pode fazer, e um agente que as executasse desligaria todos os portões. As demais
restritas (`responder_questao`, `promover_aprendizado`, `encerrar_sessao`,
`excluir_projeto`, `excluir_em_lote`, `aprovar_plano`, `responder_desvio`) dependem da política efetiva do projeto do
alvo: com a `governanca_maxima` são do humano, com a `arbitragem_maxima` também do
papel `arbitro` (que desde a fase 1 não abre servidor), e planejador, executor e
revisor são recusados em qualquer política. A recusa por nome de ferramenta é a primeira
camada, não a única: o `RoleGate` impõe as mesmas garantias contra qualquer caminho,
inclusive um `propor_patch` cru.

**O servidor se apresenta.** A resposta de `initialize` traz `instructions` com
o protocolo de memória (`graphow.context.protocolo`): comece por `ler_vista`,
registre `Evidence` e `Decision` enquanto trabalha, destile `Aprendizado` antes
de terminar, condense a sessão anterior se a `Task` ficou pendente, e o que o
papel da conexão pode criar, lido do `RoleGate`. As descrições das ferramentas
dizem quando usá-las, não só o quê: é o que um agente que nunca leu a skill
recebe junto das ferramentas.

### O ciclo de uma sessão sobre o MCP

As ferramentas acima fecham as três decisões que uma sessão sobre o grafo
precisa tomar (é o ciclo que os subagentes da orquestração antiga seguiam, e o
que uma sessão do humano segue hoje):

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
- **[🧩 Especificação Formal da Ontologia (`docs/ONTOLOGY.md`)](docs/ONTOLOGY.md)**: Vocabulário semântico, temporalidade do log, separação Navegação vs Trabalho, matriz das 18 arestas permitidas, matriz de papéis (com a coluna "conforme a política") e a Governança Configurável: os dezesseis gestos, os presets, a herança e a regra do veredito.

---

## 🚀 Instalação e Execução

### Pré-requisitos
- Python $\ge$ 3.11
- [Claude Code](https://claude.com/claude-code) (CLI ou app desktop), para a memória, o gerente e as sessões `claude -p` do `graphow orquestrar` (o executável vem de `GRAPHOW_CLAUDE`, depois do PATH)

### 1. Instalar o pacote

A instalação tem de ser editável e a partir de um checkout: o `graphow setup`
copia as skills de `.agents/`, que não vão dentro do pacote. Os prompts do
`graphow orquestrar` vão dentro do pacote e não precisam de instalação.

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
| Skills `graphow-mcp` e `graphow-gerente` | `~/.claude/skills/` |
| Remove as cópias obsoletas da orquestração por subagentes: a skill `graphow-orquestracao` e os sete subagentes `graphow-*.md` | `~/.claude/skills/`, `~/.claude/agents/` |
| Hooks `SessionStart` e `SessionEnd`, com o caminho absoluto; tira o `SubagentStop` antigo do harness | `~/.claude/settings.json` |
| Permissões: leitura do servidor da sessão e os comandos de medição; tira as dos servidores de subagente | `~/.claude/settings.json` |

O caminho absoluto é o que torna o setup confiável: com o pacote num venv, o
`graphow` só está no PATH de quem ativou o venv, e o processo do app desktop não
o acha. O hook falhava calado e a memória não chegava.

A mescla no `settings.json` preserva o que já estiver lá, troca o hook do
harness em vez de duplicá-lo e guarda o arquivo anterior em
`settings.json.graphow.bak`. Sem `--escrever-settings`, o setup não toca no
arquivo e imprime o bloco para você colar.

### 3. O que segue manual

O setup termina imprimindo os dois passos que ficam com você:

1. **Registrar o servidor MCP da sessão principal**, uma vez por usuário. O
   setup imprime o comando pronto, com o caminho do executável:
   `claude mcp add --scope user graphow -- "<executável>" mcp --papel humano --autor <você>`.
   O papel é `humano`, e as permissões liberam só as ferramentas de leitura.
   Responder Question, promover Aprendizado e o resto continuam pedindo sua
   confirmação. Outros ambientes (Cursor, Claude Desktop, Antigravity) estão no
   [guia do MCP](.agents/skills/graphow-mcp/references/mcp_setup_guide.md).
2. **Reiniciar o Claude Code e conferir** a linha `Banco:` que o hook de início
   imprime: a sessão, os hooks e o `graphow orquestrar` precisam usar o mesmo
   banco (`graphow banco-info`).

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

# Abrir o servidor MCP da sessão do humano (o único papel que abre servidor)
graphow mcp --papel humano --autor david

# Regenerar o catálogo de documentação a partir do código
graphow docs-gerar

# Instalar (ou atualizar) skills, hooks e permissões no Claude Code, removendo as cópias obsoletas
graphow setup --escrever-settings

# Só conferir se as cópias em ~/.claude estão em dia (sai com código 1 se não estiverem)
graphow setup --conferir

# Instalar só a skill graphow-mcp
graphow skill-instalar

# Conduzir um Goal de uma spec num repositório: plano, fatias, verificação e fechamento
# (supervisionado por padrão: para no plano e no "pronto para integrar")
graphow orquestrar --spec docs/pedido.md --repo .
graphow orquestrar --spec docs/pedido.md --repo . --modo autonomo --orcamento-usd 10

# A branch do Goal que já existe com commit que não é dele é recusada; --adotar-ramo a aceita assim mesmo
graphow orquestrar --spec docs/pedido.md --repo . --ramo graphow/relatorio --adotar-ramo

# Conduzir o Goal que o gerente gravou, aprovar o plano e ver onde ele está e quanto custou
graphow orquestrar --goal goal-relatorio --repo .
graphow orquestrar --goal goal-relatorio --aprovar-plano
graphow orquestrar --goal goal-relatorio --status

# As saídas do humano, cada uma uma Decision dele, sempre com o motivo
graphow orquestrar --goal goal-relatorio --recusar-plano --motivo "o README fica para outro Goal"
graphow orquestrar --goal goal-relatorio --refazer-aceite C3 --motivo "o teste exige ponto, a spec aceita virgula"
graphow orquestrar --goal goal-relatorio --descartar-achado achado-goal-relatorio-v4-1 --motivo "aceito o risco"
graphow orquestrar --goal goal-relatorio --mais-ciclos 1 --motivo "falta so a borda do CRLF"
graphow orquestrar --goal goal-relatorio --retirar-criterio C4 --motivo "o CSV fica para o proximo Goal"
graphow orquestrar --goal goal-relatorio --cancelar --motivo "o pedido mudou"

# Quantos ciclos de correcao cada marco tem (padrao: 2); com 0, o primeiro bloqueante para e o humano decide
graphow orquestrar --spec docs/pedido.md --repo . --modo autonomo --ciclos-de-correcao 0

# Registrar o ciclo de vida de uma execução (chamado pelos hooks do ambiente).
# Sem --setor, a sessão nasce no ambiente padrão do repositório em que o comando roda
graphow harness --fase inicio --sessao sess-01 --modelo opus-5
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"

# O fim de um subagente (o hook SubagentStop antigo, que o setup não instala mais): um Run com os tokens e o modelo
graphow harness --fase subagente --entrada-hook

# Comparar Goals orquestrados sob configurações de modelo: retrabalho, rejeições na revisão e tokens
graphow orquestracao-medir --goal goal-padrao --goal goal-tudo-opus

# O mesmo, com uma linha por rodada do condutor da orquestração antiga: minutos, o que fechou, tokens e cota
graphow orquestracao-medir --goal goal-padrao --por-rodada

# Quando o trabalho mora num repositório git: conferir o Goal contra o ramo_base dele, o que o ramo base ganhou desde o merge-base,
# nos caminhos_de_colisao, e que colide com o que o Goal toca (sai com 1 se colidir, 2 se não der para conferir)
graphow base-colisoes --goal goal-migrations --repo . --sem-fetch

# Medir o tamanho da vista contra o despejo da sessão sobre o corpus gravado
graphow avaliar

# Medir a escala do grafo que está no banco: peso do canvas por recorte,
# custo de navegar, custo de buscar e o custo do rollup com o fechamento
graphow medir-escala

# Rodar uma arquitetura nas três demandas do laboratório, auditar a entrega e comparar com a linha de base
graphow bancada rodar --arquitetura enxuta --projeto todos --saida ../bancada-saida
graphow bancada rodar --arquitetura orquestrar --projeto todos --saida ../bancada-saida
graphow bancada auditar --execucao ../bancada-saida/enxuta-estoque-loja-20261011-153000
graphow bancada placar --saida ../bancada-saida

# Medir de novo a linha de base da bancada a partir dos logs do laboratório
graphow bancada medir-laboratorio --laboratorio ../graphow-lab

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
| Configurações (engrenagem da faixa de ícones, ou `Ctrl+P`) | A aba da governança: escopo Global ou projeto, os três presets em cartões, a tabela dos dezesseis gestos com o valor e a origem de cada um, as linhas sempre humanas, a operação do projeto (quando o gerente grava e, quando o trabalho mora num repositório git, ramo base e caminhos de colisão) e a auditoria do que o árbitro fez. O que o árbitro respondeu ou promoveu leva o selo "pelo árbitro", e o menu da `Task` libera a posse de outro autor |

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

`graphow setup --escrever-settings` grava os dois hooks (início e fim) no
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

## 🧭 Gerente: da demanda ao Goal

A orquestração começa num `Goal`, e o `Goal` é do humano: ele diz o que quer,
os agentes decidem como. O que vem antes (entender a demanda, separar
desenvolvimento de suporte, esclarecer as decisões de negócio, fixar restrições
e critérios de aceite) era trabalho que o humano fazia sozinho. A skill
`graphow-gerente`, em
[`.agents/skills/graphow-gerente`](.agents/skills/graphow-gerente/SKILL.md),
faz esse trabalho com ele, na sessão principal:

1. **Triar.** Entra no grafo o que trabalha como desenvolvimento e vira um Goal
   com entrega verificável; suporte do dia a dia é respondido e fica fora. O que
   entra é **melhoria** (poucos pontos do sistema, um Goal) ou **projeto**
   (muitos pontos, vários Goals, em geral sob um Setor próprio).
2. **Alinhar.** Pergunta só o que muda a conclusão, separa fato de hipótese e
   não avança de etapa sem o humano dizer que segue.
3. **Propor.** Mostra o rascunho inteiro: Goal, critérios de aceite (cada um
   verificável, com as bordas que o humano decidiu e o tipo de verificação,
   `teste` ou `checagem`), Constraints, Decisions com o motivo, o que ficou em
   aberto e o que ficou fora.
4. **Gravar.** Pela conexão `humano` da sessão, num `propor_patch`: cada
   critério num nó `Criterio` que escopa o Goal (`codigo`, `texto`,
   `verificacao`) e cada decisão numa `Decision` com o texto inteiro e o motivo.
   As Decisions orientam o Goal e descem a toda a decomposição.
5. **Entregar** o Goal ao `graphow orquestrar --goal <id> --repo <pasta>` e, ao
   fim, **revisar** a entrega contra o que foi decidido. O orquestrador monta a
   spec dos nós que o gerente gravou, com o texto inteiro de cada critério e de
   cada decisão, e grava o critério do humano como ele o escreveu: o planejador
   não o reescreve.

O gerente não é um papel novo do kernel: ele propõe e o humano decide, então
Goal, Criterio e Constraint continuam sendo gestos do humano. Quando ele grava é uma
propriedade operacional do Projeto, `gravacao_do_gerente`, na aba Configurações: `apos_aprovacao` (o padrão) só grava depois de o humano
aprovar o rascunho; `durante_alinhamento` grava cada Decision, Constraint ou
Evidence assim que o humano a confirma na conversa.

## 🎼 Orquestração em código: `graphow orquestrar`

A coordenação deixou de ser feita por LLMs. Até a fase 1, uma raiz despachava
rodadas a um condutor novo a cada rodada, que despachava exploradores,
executores, revisores e um executor só para fechar, com um árbitro ao lado; a
auditoria de campo de 10/10/2026 mediu que eles gastavam dois terços dos tokens
fazendo o que um laço de código faz, e os defeitos foram pegos por quem rodou o
programa contra o pedido, e não pela burocracia. A skill `graphow-orquestracao`
e os sete subagentes saíram. No lugar, `graphow orquestrar` (`src/graphow/orquestrador/`)
é um laço em código, e os LLMs entram só onde há julgamento:

1. **Área de trabalho.** O Goal trabalha num clone local só dele
   (`git clone --local`, objetos por hardlink quando a pasta está no mesmo
   disco, sem alternates), numa branch do Goal (`--ramo`, padrão
   `graphow/<slug>`) criada da base (`--base`, padrão a branch atual). O clone
   não tem remoto, tag, reflog nem hook, e só leva a branch do Goal e a base:
   o agente não enxerga ref nem configuração do humano, e o que ele fizer no git
   fica no clone. A branch do Goal no repositório do humano é só do orquestrador,
   que a cria e a avança puxando do clone (`git fetch <clone>` rodado no
   repositório do humano) depois de cada commit dele, só por fast-forward: a
   branch que andou fora do orquestrador não é sobrescrita, e a chamada para
   dizendo isso. O checkout do humano não é tocado até a integração. A branch
   que já existe com commit que não é do Goal (todo commit do orquestrador leva
   os trailers `Graphow-Goal` e, na fatia, `Graphow-Task`) é recusada, a menos
   que a chamada diga `--adotar-ramo`; a `--area` não pode ser o checkout do
   humano nem ficar dentro dele, e a branch do Goal não pode ser a base.
2. **Plano.** Uma sessão do planejador lê a spec e o código e devolve critérios
   de aceite C1..Cn (texto completo, `verificacao: teste|checagem`), decisões
   D1..Dn com o motivo, o comando da suíte, fatias verticais com critérios,
   arquivos, dependências, modelo sugerido e, quando pedem julgamento de
   domínio ou atravessam partes, a marca de `risco`, e os marcos que agrupam as
   fatias (um marco entrega critérios verificáveis; o último é a verificação
   final). O orquestrador grava os critérios como nós `Criterio`, as decisões
   como `Decision`, as fatias como `Task`, e commita `docs/goals/<slug>.md`, um
   texto só com duas leituras. No Goal que o gerente gravou, o critério do humano
   vale como ele o escreveu, diga o planejador o que disser.
3. **Aceite primeiro.** Uma sessão nova do autor de aceite, que não é o
   executor, escreve em arquivos novos de `aceite/` os testes executáveis de
   cada critério `teste` (de um a três por critério, cada um cita o código do
   critério) e a lista de checagem de cada critério `checagem`. O orquestrador
   confere a forma, recusa o que o autor mexeu fora de `aceite/` e roda cada
   teste lendo a saída do runner (pytest, unittest, node:test, jest, vitest,
   mocha; `orquestrador/resultado_de_teste.py`): antes da implementação, cada
   um tem de falhar numa asserção dele, com o nome dele na saída, e o erro de
   import ou de coleta, o comando que não existe, o nome errado e o teste
   pulado voltam ao autor; o que já passa precisa da justificativa
   (`ja_atendido`, que vale só para os testes que já passam). O que não confere
   volta à mesma sessão até duas vezes; esgotadas, a parada indica
   `--refazer-aceite`. Conferido, os testes vão num commit (o arquivo de
   `aceite/` que o `.gitignore` do projeto ignoraria entra com `git add -f` e
   faz parte da cópia intocada), e cada `Criterio`
   ganha a ligação aos seus testes. O autor roda no Sonnet por padrão, e o JSON
   dele leva um modelo de comando (`comando_do_teste`) em vez de um comando por
   teste.
4. **Portão do plano e dos testes.** No modo supervisionado (o padrão) o laço
   para depois do autor de aceite e espera `--aprovar-plano`: o humano aprova
   junto o plano e o que vai provar que o Goal está pronto, e a aprovação vale
   para o commit desses testes. O portão é do orquestrador, e o gesto
   `aprovar_plano` do escopo governado não o destrava. `--modo autonomo` segue
   direto. O modo fica gravado no Goal.
5. **Execução, marco a marco.** Para cada fatia pronta do marco atual, uma
   sessão nova do executor recebe o briefing montado por código: a spec, o texto
   inteiro dos critérios (com os testes de aceite que os provam) e das decisões,
   os arquivos, os commits das fatias anteriores e o diff resumido da última; na
   fatia de correção, o achado inteiro com a prova, as chamadas da verificação
   que falharam (o comando exato, o código de saída e o trecho da saída, para
   reproduzir) e o pedido de escrever o teste de regressão antes; quando a mesma
   falha volta no ciclo seguinte, também o diff da correção anterior e a
   verificação que a reprovou. A correção roda no Opus. O executor implementa e
   devolve `pronto`, `duvida` ou `falhou`. No modo autônomo, onde ninguém
   responde, o schema dele não oferece `duvida`: a incerteza que ele resolve
   pela spec vai em `decisoes` e vira `Decision` "decidida pelo agente", que
   orienta a fatia e aparece no `--status` e no documento do Goal para o humano
   revisar; a única parada é `teste_errado`, que pede ao autor de aceite, uma
   vez por critério, que refaça os testes dele com o argumento do executor no
   briefing (se o autor os mantém, o porquê volta ao executor, a fatia segue e o
   desacordo vai à verificação, que julga; as outras fatias seguem). O
   orquestrador confere o git, recusa a fatia que alterou, apagou ou moveu um
   teste de aceite (se o teste está errado, o caminho é a dúvida ou o
   `teste_errado`),
   roda a suíte ele mesmo, sem os testes de aceite, no mesmo bash da ferramenta
   Bash dos agentes (o Git Bash no Windows, nunca o do WSL; `GRAPHOW_SHELL`
   escolhe outro), passa a fatia de risco (a marcada, ou a que já falhou uma
   vez) por uma sessão nova de revisão, que julga o diff contra os critérios
   dela antes do commit, e commita na branch do Goal com a mensagem que cita a
   fatia e os critérios; o commit vira `Artifact`. Nas outras fatias não há
   revisão, e o problema da revisão que rejeita vira `Achado` da revisão (com a
   gravidade do código), e não Note. **O aceite fica intocado**
   (`orquestrador/aceite_intocado.py`): a fatia que mexe em `aceite/` (o
   arquivo ignorado pelo git inclusive) é recusada. A configuração de teste
   (conftest, pytest.ini, a seção de teste do pyproject e do setup.cfg,
   tox.ini, os scripts de teste do package.json, jest, vitest, mocha,
   sitecustomize, `.pth`, um `pytest.py` na raiz) o executor pode mudar, e a
   suíte do plano e os testes de aceite rodam com ela, com `aceite/` intocado;
   quando ela mudou, o aceite roda também com a do commit do aceite
   (`orquestrador/configuracao_do_aceite.py`), e a mudança que o plano não
   declarou na fatia só manda a fatia à revisão de risco, como sinal. As
   flags `skip-worktree` e `assume-unchanged` do índice saem e reprovam a
   tentativa (`git update-index` está nas regras negadas). A dúvida (no
   supervisionado) vira `Question` e pausa só aquela fatia, sem contar como
   falha; a falha ganha uma nova tentativa com o erro, e a segunda falha vira
   pendência e para o laço, menos na correção agrupada, que se divide numa
   fatia por achado. O que não vira commit vai para um `.patch` e sai da
   área.
6. **Verificação por marco.** A verificação tem três tipos, cada um com
   prompt, schema e modelo próprios (`orquestrador/tipo_da_verificacao.py`):
   a do **marco** intermediário (`marco`, Sonnet), a primeira dele, confere só
   os critérios do marco, rodando os testes e o programa, sem sondar bordas;
   a **caçada** (`caca`, Opus), adversarial e com sondagem de bordas, roda uma
   vez, na primeira verificação final, sobre o Goal inteiro; e a
   **conferência** (`conferencia`, Sonnet) roda depois de cada ciclo de
   correção, em qualquer marco, com um briefing curto (os achados que as
   correções trataram, as provas e as chamadas que os reproduzem, os pareceres
   de antes e o diff das correções): roda a suíte e o aceite, reproduz cada
   achado e confere regressão nos critérios que as correções tocaram. Na
   conferência, cada achado conferido ganha um parecer em `conferidos`,
   `corrigido` ou `persiste`, com a prova (faltar um é saída inválida, e a
   sessão volta uma vez); só o `corrigido` resolve o achado, e o que persiste é
   bloqueante, como o achado listado com `persiste` (o id dele) ou, sem ele,
   como o conferido era. A
   regressão de critério (`regressao`) segue a regra de sempre, e o achado novo
   que não é regressão vira acompanhamento marcado "achado novo da
   conferencia, sem regressao", sem segunda opinião (na bancada de 12/10, cada
   verificação depois de uma correção era outra caçada, que achava bordas
   novas, e o laço não convergia). O tipo vai na verificação e no `--status`,
   e a conferência final limpa no commit atual vale como a verificação final.
   Com as fatias do marco concluídas, uma sessão
   nova do verificador, sem nada de quem implementou, roda a suíte, os testes de
   aceite e o programa de verdade, executa as checagens, na caçada sonda as bordas que os
   critérios implicam (negativo, zero, vazio, enorme, codificação, Unicode,
   concorrência, Windows, código de saída, idioma) e dá um parecer por critério
   que o marco julga (na final, todos, e todas as decisões), com prova (o
   comando exato e o que viu) e os achados; também sonda os limites que as
   decisões implicam (datas máximas, tamanhos, quantidades, repetição). Com
   prova de menos de dez caracteres, a verificação não confere. Os comandos
   rodados ela não declara: o orquestrador os tira do stream da sessão, cada
   chamada da ferramenta Bash com o código de saída e um trecho da saída
   (`orquestrador/comandos_do_stream.py`), e os grava na verificação; a sessão
   que não rodou nenhum volta uma vez (na bancada, conferir os comandos que o
   verificador declarava custou quatro retomadas num Goal só). Depois, o
   próprio orquestrador roda, no commit verificado, com `aceite/` de volta ao
   commit do aceite e a configuração de teste entregue (e, se ela mudou, também
   com a daquele commit: o teste que só passa com a entregue e, com a do
   aceite, falha numa asserção reprova o critério; o que falha por import vai
   ao verificador, que deve um parecer), a suíte e os testes de aceite dos
   critérios que os marcos até este completaram (os dos anteriores, como
   regressão; na final, também todos de uma vez e a suíte
   junto com eles, num comando só, com a configuração do projeto): a suíte
   vermelha é bloqueante, e o teste de aceite que não passa (o pulado e o xfail
   inclusive) reprova o critério dele, diga o verificador o que disser. **A gravidade é do código**: o verificador diz, por
   achado, os critérios e as decisões que ele toca e o `alcance` da entrada
   (`uso_previsto`, a que a spec, as decisões ou um usuário normal produzem, ou
   `extremo`, a patológica, como NUL, id de 4300 dígitos ou o ano 9999, de cujo
   limite nenhuma decisão fala; a decisão que fala dele vai em
   `decisao_do_limite` e faz o achado de uso previsto). O achado de uso
   previsto que toca algum é bloqueante, mesmo o defeito que já existia; o que
   ele deixa sem citação ou julga extremo vai a uma segunda opinião, uma sessão
   curta sem ferramentas (Sonnet, só os critérios, as decisões e o achado, sem o
   alcance do verificador, com uma retomada quando o formato não confere), que
   também diz o que ele fere e o alcance. Ele só fica acompanhamento se ela
   também não citar nada ou também disser extremo (sem resposta, os dois não
   concordaram, e ele é bloqueante). Uma verificação abre no máximo 5
   bloqueantes: ficam os que o orquestrador viu falhar e depois os do
   verificador, na ordem dele; o resto vira acompanhamento marcado "excedeu o
   teto do ciclo", visível nas pendências. A verificação vira `Evidence` ligada ao Goal e cada achado um
   nó `Achado`, no mesmo lote do estado de cada `Criterio` julgado e das
   pendências. Os bloqueantes do ciclo viram uma fatia de correção só, que
   deriva de todos eles, mesmo em arquivos diferentes, e leva no briefing cada
   achado com a prova e as chamadas da verificação que o reproduzem
   (`orquestrador/correcoes.py`); só a verificação final, que cobra também os
   bloqueantes dos outros marcos, pode passar de 5 e se dividir em fatias de 5.
   A correção agrupada que falha duas vezes se divide numa fatia por achado.
   São até dois ciclos por marco (`--ciclos-de-correcao` muda o número,
   gravado no Goal). O marco intermediário que esgota os ciclos segue, com
   os bloqueantes abertos, para os marcos seguintes rodarem; a verificação final
   os cobra de novo, com os ciclos dela, e só esgotados esses o laço para. O
   acompanhamento fica como pendência do Goal, no documento e no `--status`.
7. **Fechamento.** O Goal só fecha com a verificação final limpa no commit
   atual, `atende` em cada critério e nenhum bloqueante aberto, e é o kernel
   que recusa o resto (`fechamento_sem_verificacao_limpa`); a regra e o laço só
   contam a verificação, o `Achado` e a revisão de risco que nasceram de um
   lote do orquestrador (a proveniência do nó no log). O livro do aceite não se
   reescreve (`kernel/livro_do_aceite.py`), e cada nó do lote é julgado pelo
   que ele é no fim do lote, e não operação a operação (a revisão forjou a
   verificação criando a `Evidence` sem `acao` e escrevendo a ação numa
   operação seguinte do mesmo lote): a verificação e os pareceres dela são
   imutáveis e só o orquestrador os cria; a ponta da branch, a condução, o plano
   e as ligações do `Criterio` são dele, e o `Criterio` não se remove; o
   `Achado` só anda pelas transições do livro (aberto a corrigido pelo
   orquestrador, com o commit da correção; a resolvido pelo orquestrador,
   quando uma conferência o deu por corrigido e a verificação do marco saiu
   limpa, ou, o que persistiu, quando o achado que o repete se encerrou; a
   descartado só pelo humano, com o motivo; nada volta a aberto); e o Goal conduzido vai a `concluido` só pelo
   orquestrador, num lote em que fechar é a única mudança (o humano cancela,
   com o motivo, mas não conclui). Antes de fechar, o orquestrador confere no
   git a ponta real da branch: o commit que o humano fez nela depois da
   verificação impede o fechamento. No modo autônomo, o orquestrador integra
   por fast-forward na base e fecha; no supervisionado, para com "pronto para
   integrar", e a chamada seguinte vê a branch integrada e fecha.

**Saídas do humano.** O Goal parado tem saída, e cada uma é um pedido gravado
como `Decision` do humano (`orquestrador/pedidos_do_humano.py`), sempre com
`--motivo`: `--recusar-plano` (antes de qualquer fatia: o planejador refaz o
plano com o recusado e o motivo no briefing, e o `Criterio` que sai fica
retirado), `--refazer-aceite C3` (o autor de aceite reescreve só os testes de
C3, e no supervisionado o portão volta; a dúvida do executor que marcou
`teste_errado` só leva ao mesmo lugar quando a resposta do humano começa por
`refazer`, e `manter` devolve a fatia ao executor com o teste como está),
`--descartar-achado` (o laço lê o estado do `Achado`, e não o veredito velho
da verificação), `--retirar-criterio C2` (o critério sai da conta do
fechamento: o pedido é a `Decision` do humano, aparece no `--status` e numa
seção do documento do Goal, e descarta os Achados abertos que ferem só ele),
`--mais-ciclos N` (para o marco atual) e `--cancelar`. **Descartar não aprova
critério**: o Goal com um critério `nao_atende` ou `parcial` na última
verificação não fecha por descarte (é a decisão do dono do processo, que vale
sobre o item 7 só nesse ponto); o descarte resolve só o Achado que não deixa
critério reprovado, e a parada indica `--retirar-criterio`, `--refazer-aceite`
ou `--cancelar`. **Erros da API.** O limite de uso (`usage_limit_reached`, o
`rate_limit_event` recusado num stream que não termina em sucesso) não é
falha da fatia: a tentativa em curso não conta e o laço para com
`limite_de_uso`, retomável; o limite que chega na revisão de risco não joga
fora a entrega do executor, que fica guardada, e a retomada refaz só a
revisão. O erro passageiro (429 sem limite de uso, 529 ou sobrecarga, 5xx)
repete a invocação depois de 30 s, 2 min e 5 min; o 4xx é permanente: a
sessão falha na hora, com o erro da API no motivo, sem espera.

O estado sai do livro-razão e do git, então rodar de novo retoma de onde parou,
inclusive depois de o processo cair no meio de uma sessão: o plano pago não se
paga de novo (vale o que o Goal guardou, ou o relido do stream da sessão), nem
os testes de aceite (a saída conferida do autor vai ao Goal antes do commit), a
fatia cujo commit já está na branch fecha pelo trailer, sem outro executor, e o
documento do Goal é sincronizado com as pendências do livro-razão. Todo
documento que o orquestrador escreve vai com quebras LF e só é commitado quando
muda de fato: a pendência com CRLF (a saída de um programa no Windows) não gera
mais um commit novo a cada chamada. A mesma spec
depois de o Goal fechar abre outro, com sufixo (`goal-soma-2`) no slug, nas
fatias e na branch. Toda falha de domínio (o git que recusa, o lote que o
kernel recusa, o pedido que não dá para conduzir) vira parada com o motivo,
nunca exceção.

| Garantia | Como |
| :--- | :--- |
| Nenhum agente escreve no grafo | As sessões rodam com `--strict-mcp-config` (sem servidor MCP) e `--setting-sources project` (sem os hooks, as skills e os subagentes do usuário); quem grava é o papel `orquestrador`, que nenhum servidor alcança |
| Saída validada por schema | `--json-schema` em cada sessão (o `structured_output` do resultado), conferido de novo em código, inclusive o sentido (ids, cobertura, ciclos); a saída que não confere volta à mesma sessão por `--resume`, uma vez (o autor de aceite, duas) |
| O aceite prova o que diz | O teste de aceite roda da cópia do commit do aceite, sem arquivo solto do executor, com a configuração de teste entregue e, quando ela mudou, também com a do commit do aceite (o teste que só passa com a entregue reprova o critério quando, com a do commit do aceite, falha numa asserção; quando falha por import ou coleta, o verificador deve um parecer `legitima` ou `ilegitima`), e conta como verde só quando a saída do runner diz que passou sem pular; o kernel recusa toda reescrita do livro do aceite (a verificação, o `Achado`, o `Criterio`, a ponta, o fechamento) |
| O agente não escreve no git do humano | O isolamento é o clone do Goal (`orquestrador/git_do_goal.py`): ele não divide ref, configuração nem hook com o repositório do humano, e esse repositório só muda pelo orquestrador (o fetch da branch do Goal e o fast-forward da integração). Dentro do clone, três camadas em profundidade (`orquestrador/trava_do_git.py`): as regras `--disallowedTools` negam o git de escrita, `git -c`, `git -C`, config, remote, fetch e push; o ambiente da sessão aponta `core.hooksPath` para os hooks `reference-transaction`, que aborta toda atualização de ref, e `pre-push`; e, depois de cada sessão, o clone volta ao que era (a branch do Goal no commit de antes, com o commit que escapou de volta à árvore por `reset --soft`, as outras refs, a configuração e os hooks), sem reprovar a sessão, porque no clone só o agente mexe. Nada fora do clone é conferido nem desfeito: o que o humano fizer no repositório dele durante a sessão (commit noutra branch, tag, configuração, remoto, stash) fica como ele deixou. Uma sonda real mostrou que `git -C . commit` passava pela regra sozinha e que `git -c core.hooksPath=<vazia>` passava pelo hook; num worktree, que dividia as refs com o humano, a conferência que tentava desfazer isso também desfazia o trabalho dele |
| Prompts sem divergência | Os prompts de papel moram no pacote (`orquestrador/prompts/`, cada um abaixo de 5 KB) e vão à sessão por `--append-system-prompt-file`; nada é instalado em `~/.claude` |
| Custo sob controle | Cada invocação vira uma linha de telemetria (`telemetria_de_sessoes`, no mesmo banco, fora do grafo): papel, fatia, sessão, modelo, custo, tokens, duração, erro e estado. A linha nasce `em_andamento` antes de a sessão abrir e fecha com o resultado; cada invocação tem stream próprio, e a refeita não apaga o da anterior; a que ficou em andamento porque o processo caiu é recuperada do stream na chamada seguinte. O total soma, por sessão, o último custo declarado, e o `--resume` que morre sem resultado não zera o que já se sabia. Há orçamento por Goal (`--orcamento-usd`, padrão 30), que também vai a cada sessão como `--max-budget-usd` |
| Saída legível | A CLI escreve em UTF-8 a saída que vai para um cano ou arquivo (no Windows o Python os abre em cp1252, e o acento chegava como caractere de substituição), e a saída da suíte é lida em UTF-8, ou na página de código da máquina quando não é |

Modelo por papel: `--modelo-planejador`, `--modelo-aceite`, `--modelo-executor`,
`--modelo-revisor`, `--modelo-verificador` (a caçada), `--modelo-marco`,
`--modelo-conferencia` e `--modelo-segunda_opiniao`, Opus
por padrão, menos o autor de aceite, a verificação do marco, a conferência e a
segunda opinião, Sonnet (`sugerido` no
executor segue o modelo que o plano sugeriu para a fatia). Modo de permissão das sessões:
`--permissao`, padrão `bypassPermissions`, o que a bancada usa. O estado de cada
Goal (o clone da área, os streams das sessões, os patches e a trava do git) fica
em `<pasta do banco>/orquestrar/<goal>/`; o clone sai quando o Goal fecha, e a
branch do Goal fica no repositório do humano. A área de uma versão anterior, que
era um worktree, dá lugar ao clone na chamada seguinte.

O teste de fumaça real da fase 2 (um repositório de brinquedo com `media` e
`mediana`, cinco critérios `teste` e um `checagem`, modo autônomo, Opus em todos
os papéis) fechou o Goal com quatro sessões, US$ 0,89 e 2,8 minutos: o plano
num marco só, o final; o autor de aceite escreveu 24 testes em `aceite/`, e o
orquestrador viu cada um vermelho antes da implementação; o executor fez a
fatia, a suíte do plano rodou sem os testes de aceite, e na verificação os 24
voltaram verdes, rodados pelo orquestrador. O verificador achou um problema que
não toca critério (inteiros enormes levantam `OverflowError`), que virou `Achado`
de acompanhamento e pendência, sem Note. Os seis nós `Criterio` terminaram
`atende`, e o lote que fechou o Goal veio depois da verificação final, feita no
commit do código que é a ponta da branch (o commit seguinte só registrou a
pendência no documento). Os 113 eventos do Goal são do papel `orquestrador`.

A fumaça da rodada 2 da fase 2 (uma calculadora de estatística em duas etapas,
`mediana` e `desvio` e depois a linha de comando e o README, onze critérios,
modo autônomo, os papéis no padrão) fechou o Goal com treze sessões, US$ 2,18
e 9,9 minutos, em dois marcos. O autor de aceite, no Sonnet, custou US$ 0,12 em
0,6 minuto, com dez testes, todos vermelhos por asserção antes da
implementação. O marco M1 saiu limpo; na final, o orquestrador rodou de novo
os testes de M1 e a suíte junto com o aceite, e o verificador achou dois
bloqueantes (o `desvio` de valores grandes com traceback na CLI e `nan` aceito
como número), que viraram uma fatia de correção só; a verificação seguinte
achou mais um (a `mediana` que transborda), corrigido no segundo ciclo, e a
quarta saiu limpa. Os três achados que o verificador não ligou a critério
passaram pela segunda opinião (três sessões sem ferramentas, US$ 0,05) e
ficaram acompanhamento. Nenhuma Note.

A fumaça da rodada 3 (a mesma calculadora, do estado inicial, com `aceite/` no
`.gitignore` do projeto, modo autônomo, `--ciclos-de-correcao 0` e US$ 3 de
orçamento) fechou o Goal pelo caminho do humano, com doze invocações, US$ 1,49
e 5,9 minutos. Os nove testes de aceite entraram no commit do aceite com
`git add -f`, apesar do `.gitignore`. Duas retomadas do autor de aceite vieram
de um defeito do orquestrador, que lia como exceção a linha FAILED que o pytest
corta na largura do terminal (`- Ass...`), corrigido em seguida. O executor, sem
`duvida` no schema, registrou oito decisões do agente (cinco nas fatias, três
na correção), que o `--status` e o documento mostram. Nenhuma das três verificações teve retomada: os comandos de
cada uma (de três a quatro chamadas Bash, com o código de saída) saíram do
stream, e eles sondaram 1e308, `nan`, `inf`, `1_000`, dígitos não ASCII e pasta
com espaço. A final achou dois bloqueantes (o traceback da CLI com valores
enormes e `nan` aceito como número); sem ciclo, o laço parou, e rodá-lo de novo
parado não fez commit. O humano descartou o do `nan` e deu um ciclo ao outro: a
correção rodou no Opus, e a verificação seguinte achou a causa nas funções
(`mediana` e `media` de 1e308 dão `inf`), com C1 e C2 `parcial`. Descartar esse
achado não fechou o Goal; o humano retirou C1 e C2, com o motivo, e o Goal
fechou na verificação final real, no commit do código que é a ponta, com o
documento listando os critérios retirados. Dos 282 eventos do Goal, os 14 do
humano são os pedidos e os descartes; o resto é do `orquestrador`. A fumaça
mostrou mais duas coisas, já corrigidas: a fatia de correção listava só o
primeiro arquivo que o local do achado cita, e o executor se ateve a ele; e a
parada da final com critério reprovado não avisava que o descarte não fecha.

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

## 🧪 Bancada: o portão medido de cada fase

`graphow avaliar` mede o tamanho da vista; não mede defeito entregue. A
bancada mede: as três demandas do laboratório de 10/10/2026 (uma CLI de
reservas, uma CLI de estoque e uma API em Node), rodadas do zero por uma
arquitetura, cada entrega auditada pelo mesmo prompt e as mesmas sondas, e
comparadas com a linha de base do graphow 0.4.4 e da arquitetura enxuta de
controle. As arquiteturas registradas são a `enxuta` e a `orquestrar`, o
`graphow orquestrar` em modo autônomo, medido pela telemetria dele. Custo, tokens e minutos saem do stream-json e das transcrições com
as definições do laboratório; critérios, sondas e defeitos bloqueantes saem da
linha `PLACAR:` do auditor.

```bash
graphow bancada rodar --arquitetura enxuta --projeto estoque-loja --saida ../bancada-saida
graphow bancada rodar --arquitetura orquestrar --projeto estoque-loja --saida ../bancada-saida
graphow bancada auditar --execucao ../bancada-saida/enxuta-estoque-loja-20261011-153000
graphow bancada placar --saida ../bancada-saida
```

Os dados (sementes, specs, sondas, prompts e a linha de base com a fonte de
cada número) vivem em `bancada/`, e o `bancada/README.md` diz o que cada
número significa, quanto uma rodada custa e como ler o placar. As sessões
`claude -p` passam por `graphow.sessoes`, o caminho único que acha o
executável (`GRAPHOW_CLAUDE`, depois o PATH), limpa o ambiente da sessão mãe e
dá a cada execução um banco próprio: os hooks nunca escrevem no banco do
usuário.

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
