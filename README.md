# Graphow 🌐

> **Substrato Bilateral de Grafo Agêntico para Coordenação Humano-IA**  
> *Common Ground compartilhado, governança em 4 portões (PatchBoard), log append-only determinístico (ActiveGraph) e divulgação progressiva com orçamento de tokens.*

---

## 📌 Visão Geral

O **Graphow** é uma plataforma de estado compartilhado (*common ground*) que atua como substrato bilateral para coordenação estruturada entre desenvolvedores humanos e agentes autônomos de Inteligência Artificial (Planejadores, Executores, Revisores).

A arquitetura do Graphow é fundamentada em quatro pilares inegociáveis:
1. **O Log é a Verdade (*ActiveGraph*):** Event store *append-only* bitemporal (SQLite local-first ou memória); o grafo é uma projeção puramente determinística e reconstruível do zero absoluto via *event replay*.
2. **Caminho Único de Escrita (*PatchBoard*):** Humanos e IAs submetem mutações utilizando o mesmo protocolo JSON Patch ([RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)), avaliado rigorosamente por um **Kernel de 4 Portões**.
3. **Divulgação Progressiva (*Progressive Disclosure*):** Agentes de IA consom recortes de contexto otimizados sob orçamento estrito de tokens, expandindo nós vizinhos sob demanda.
4. **Linhagem Causal e Reversibilidade:** Rastreabilidade reversa integral do `Artifact` até a intenção raiz (`Goal`), com ramificações históricas (*forks*) registradas como ponteiro `(ramo_base, seq_corte)`, sem cópia de prefixo.

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
- **`Aprendizado`**: Memória de longo prazo, o que sobrevive ao projeto. Nasce com origem obrigatória (`deriva_de`) e só alcança outros projetos quando o humano o promove (`vale_para` ou `alcance: global`).

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
| **`bloqueia`** | `Question` $\rightarrow$ `Task` | todos / **humano** | Bloqueia a conclusão da tarefa até resolução humana. |
| **`justifica`** | `Evidence` $\rightarrow$ `Decision` | humano, planejador, executor, revisor | Fundamentação empírica de decisões. |
| **`contradiz`** | `Evidence` $\rightarrow$ `Decision` / `Evidence` / `Aprendizado` | humano, executor, revisor | Registro de evidência conflitante; num `Aprendizado`, pedido de revisão. |
| **`substitui`** | `Decision` $\rightarrow$ `Decision`, `Task` $\rightarrow$ `Task`, `Aprendizado` $\rightarrow$ `Aprendizado` | humano, planejador | Evolução e invalidação histórica. O substituído segue visível, marcado. |
| **`escopa`** | `Constraint` $\rightarrow$ `Goal` / `Task` | **humano** | Restrição mandatória sobre a execução. |
| **`deriva_de`** | `Artifact` $\rightarrow$ `Task` / `Artifact`; `Evidence` $\rightarrow$ `Artifact` / `Task`; `Note` $\rightarrow$ `Task` / `Decision` / `Evidence` / `Artifact`; `Aprendizado` $\rightarrow$ `Evidence` / `Decision` / `Note` / `Artifact` / `Task` | humano, executor, revisor | Proveniência de artefatos, da evidência que avalia um trabalho, de notas reativas, da condensação de uma sessão e da origem de um aprendizado. |
| **`vale_para`** | `Aprendizado` $\rightarrow$ `Projeto` / `Setor` | **humano** | Alcance de um aprendizado promovido: entra na vista de toda tarefa sob esse contêiner. Nem a autonomia ilimitada a abre a agentes. |
| **`orienta`** | `Decision` $\rightarrow$ `Task` / `Goal` | humano, planejador | A decisão que vale para a tarefa ou o objetivo, herdada pela decomposição. Chega à vista de quem executa e de quem revisa mesmo tomada noutra sessão. O executor não a cria nem a remove: não mexe no que governa a própria tarefa. |

---

## 🛡️ Os 4 Portões de Governança (PatchBoard)

Toda mutação no grafo (seja humana ou de IA) é submetida via JSON Patch RFC 6902 e processada sequencialmente:

1. **Portão 1 — `SchemaGate`:** Sanitização estrita contra *prototype pollution* (`__proto__`, `constructor`, `__class__`), checagem de tipos e validação da tabela ontológica de pares válidos de arestas.
2. **Portão 2 — `RoleGate`:** Matriz de permissões por papel, aplicada sobre a identidade da *conexão*, nunca sobre um campo do payload:
   - **`humano`**: Acesso irrestrito (único autorizado a criar/editar `Constraint`, encerrar uma `Question` e estruturar a camada de navegação).
   - **`planejador`**: Cria `Task`, `Decision`, `Question`, `Note` e a `Evidence` do que leu no código, sempre localizada; decompõe, ordena e diz com `orienta` onde cada decisão vale; proibido de fechar tarefas.
   - **`executor`**: Cria `Artifact`, `Evidence`, `Question`, `Note`, `Aprendizado`; assume tarefas e trabalha nelas; proibido de criar tarefas ou alterar constraints.
   - **`revisor`**: Cria `Evidence`, `Question`, `Note`, `Aprendizado`; valida artefatos. Registra `Aprendizado` quem detém `deriva_de`: executor e revisor.
   - **`sistema`**: Telemetria (`Run`), a `Sessao` em que o harness roda e, quando o humano não configurou um Setor, o **ambiente padrão da memória**: o `Projeto` com o nome do repositório e o `Setor` `Memoria` dentro dele. Nada do grafo de trabalho, e nenhum papel de agente alcança `sistema`.

   Cinco regras valem para **todo** papel não humano, e valem no kernel, não no
   nome da ferramenta: mudar o status de uma `Question` para `respondida` ou
   `descartada`, remover uma `Question`, remover a aresta `bloqueia`, escrever
   `alcance` num `Aprendizado` ou criar `vale_para`, e remover um `Aprendizado`
   exigem sessão humana. Sem as três primeiras, um agente encerrava a própria
   escalação com um `propor_patch` e concluía a tarefa em seguida; sem as duas
   últimas, promoveria a própria memória a memória de todos.
3. **Portão 3 — `InvariantGate`:**
   - **Hierarquia Obrigatória:** Todo nó novo, exceto `Projeto`, precisa receber no mesmo lote uma aresta de contenção (`contem`, `produz` ou `decompoe`). Vale para todo papel, humano incluído: o nó solto só aparecia na pasta "Fora da hierarquia" e sumia de qualquer visão colapsada.
   - **Memória com Origem:** Todo `Aprendizado` novo precisa de ao menos uma aresta `deriva_de` partindo dele no mesmo lote; sem ela o lote cai com `aprendizado_sem_origem`. Memória sem origem é opinião com autoridade de memória.
   - **Leitura Localizada:** A `Evidence` do planejador, e qualquer `Evidence` que cite `linhas` ou `trecho`, carrega o ponteiro inteiro: `arquivo`, `linhas` (`120` ou `120-135`) e o `trecho` literal, que cabe na faixa. Vale na criação e na edição; sem isso o lote cai com `evidencia_sem_localizacao`. Uma interpretação sem o trecho que a sustenta não ganha autoridade de fato registrado.
   - **Detecção de Ciclos:** DFS iterativa impedindo ciclos em `depende_de`.
   - **Bloqueio por Dúvidas:** Impede que uma `Task` passe para `concluido` enquanto houver `Question` aberta com aresta `bloqueia`.
   - **Posse de Tarefa:** Nenhum agente move o status de uma `Task` sem deter o lock dela. Sem isso, dois executores na mesma tarefa não colidiam e o segundo sobrescrevia o primeiro em silêncio.
   - **Locks Exclusivos:** Impede mutações em tarefas travadas por outro escritor.
4. **Portão 4 — `WriteKernel`:** Geração dos `EventoLog`, persistência do lote inteiro em uma única transação (`BEGIN IMMEDIATE`/`ROLLBACK`, com `UNIQUE(ramo_id, seq)`) e notificação dos observadores — canal SSE e motor reativo.

---

## 🔌 Superfície de Ferramentas MCP (Model Context Protocol)

O `GraphowMCPServer` expõe 22 ferramentas para consumo por agentes de IA. O **papel do agente não é um argumento**: ele é fixado na abertura da sessão (`graphow mcp --papel <papel>`) e qualquer chamada que traga `papel` é recusada.

| Ferramenta | Descrição |
| :--- | :--- |
| **`ler_vista`** | Materializa o subgrafo do nó alvo formatado em Markdown, respeitando orçamentos estritos de tokens (ex: 1500, 500, 200). Num contêiner, traz o **panorama agregado** dos filhos em vez de listar a subárvore. Aceita `escopo="ativo"` para podar a navegação até o trabalho não concluído, e `perspectiva` para ler o alvo como outro papel o lê: é o teste do executor frio, feito pelo planejador antes de despachar. |
| **`expandir_no`** | Fornece visão detalhada sob demanda de propriedades e arestas incidentes de um nó específico. |
| **`propor_patch`** | Submete propostas de alteração via operações JSON Patch com validação atômica. |
| **`abrir_questao`** | Cria um nó `Question` e uma aresta `bloqueia` sobre uma `Task`, sinalizando dúvida ao humano. Aceita `titulo` curto — é o que o card mostra no canvas — e guarda o corpo da dúvida na propriedade `pergunta`; sem `titulo`, ele sai do começo da pergunta. |
| **`buscar`** | Busca textual *case-insensitive* ranqueada por relevância, cortada em `limite` (padrão 5, teto 50) e sempre acompanhada de `total` e `truncado`. Filtra por `TipoNo` e por `escopo`. |
| **`proximas_tarefas`** | Fila de trabalho da sessão ou do `Goal`: tarefas com dependências concluídas, sem dúvida aberta e sem posse de outro agente, em ordem de atendimento. Cada tarefa traz `modelo` e `arquivos_alvo`, com que o orquestrador escolhe o executor e o que roda em paralelo. |
| **`assumir_tarefa`** | Adquire a posse exclusiva de uma `Task` e a move para `em_andamento`. Exigido antes de qualquer mudança de status. |
| **`liberar_tarefa`** | Devolve a posse de uma `Task`, sem alterar o status registrado. Numa sessão humana, devolve a posse de qualquer autor: a de um subagente que terminou sem liberar. |
| **`minhas_questoes`** | Lista as dúvidas abertas por esta sessão, com a resposta humana quando já houver. |
| **`aguardar_resposta`** | Long-poll até o humano encerrar a dúvida, ou até o prazo expirar. Substitui o polling manual com `expandir_no`. |
| **`criar_projeto`** | Cria o nó `Projeto` raiz e define o nível de autonomia dos agentes nele. |
| **`criar_setor`** | Cria o `Setor` e a aresta `contem` que o liga ao `Projeto`. |
| **`criar_sessao`** | Cria a `Sessao` e a aresta `contem` que a liga ao `Setor`. |
| **`criar_tarefa`** | Cria uma `Task` com aresta `produz` e hierarquias opcionais. Para a orquestração, grava `modelo` (recusado sem `motivo_modelo`), `arquivos_alvo` e `corrige`, e liga à tarefa por `orienta` cada `Decision` listada em `decisoes`. |
| **`concluir_tarefa`** | Transiciona a `Task` para `concluido`, se nenhuma `Question` aberta a bloquear. |
| **`responder_questao`** | Registra a resposta e destrava a `Task`. **Somente sessão humana.** |
| **`configurar_autonomia_projeto`** | Ajusta a autonomia dos agentes no projeto. **Somente sessão humana.** |
| **`encerrar_sessao`** | Encerra a `Sessao`: status `concluida` e resumo opcional. A vista da sessão passa a abrir pelo **fechamento determinístico** (decisões vigentes, dúvidas abertas, restrições, último artefato). **Somente sessão humana**; o harness encerra pelo hook de fim. |
| **`registrar_aprendizado`** | Cria um `Aprendizado` pendurado na `Sessao` e ligado por `deriva_de` a cada nó de origem. Sem origem no mesmo lote, o `InvariantGate` recusa com `aprendizado_sem_origem`. |
| **`promover_aprendizado`** | Dá alcance ao `Aprendizado`: aresta `vale_para` um `Projeto` ou `Setor`, ou a marca `alcance: global`. A partir daí ele entra na seção **Aprendizados Aplicáveis** da vista de toda tarefa sob esse alcance. **Somente sessão humana.** |
| **`excluir_em_lote`** | Remove atomicamente uma coleção de nós e arestas. **Somente sessão humana.** |
| **`excluir_projeto`** | Remove o projeto e, opcionalmente, seus descendentes. **Somente sessão humana.** |

Quatro das ferramentas restritas são as que anulariam uma garantia se um agente as
executasse: `responder_questao` encerra a escalação ao humano e as demais desligam
governança ou apagam trabalho em cascata. `encerrar_sessao` é restrita por outro
motivo: encerrar é o gesto de quem abriu a sessão, o humano ou o harness, e é ele
que dispara a condensação. A recusa por nome de ferramenta é a primeira camada,
não a única: o `RoleGate` impõe as mesmas garantias contra qualquer caminho,
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
- **[🧩 Especificação Formal da Ontologia (`docs/ONTOLOGY.md`)](docs/ONTOLOGY.md)**: Vocabulário semântico, bitemporalidade, separação Navegação vs Trabalho e matriz das 13 arestas permitidas.

---

## 🚀 Instalação e Execução

### Pré-requisitos
- Python $\ge$ 3.11

### Instalação em Modo Editável
```bash
git clone https://github.com/seu-usuario/graphow.git
cd graphow
pip install -e .
```

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

# Instalar (ou atualizar) a skill do agente em ~/.claude/skills, onde todo projeto a vê
graphow skill-instalar

# Registrar o ciclo de vida de uma execução (chamado pelos hooks do ambiente).
# Sem --setor, a sessão nasce no ambiente padrão do repositório em que o comando roda
graphow harness --fase inicio --sessao sess-01 --modelo opus-5
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"

# O fim de um subagente (hook SubagentStop): um Run com os tokens, o modelo e as tarefas que ele assumiu
graphow harness --fase subagente --entrada-hook

# Comparar Goals orquestrados sob configurações de modelo: retrabalho, rejeições na revisão e tokens
graphow orquestracao-medir --goal goal-padrao --goal goal-tudo-opus

# Medir tokens por tarefa bem-sucedida sobre o corpus gravado
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
sem um cartão sobre o outro; dois mil e quinhentos nós levam 100 ms.

Quatro leituras sustentam a moldura, todas resolvidas no servidor:

| Rota | Para quê |
| :--- | :--- |
| `GET /api/canvas?setor=<id>` | Escopo por Setor, ao lado de `projeto` e `sessao`. Aberta uma Sessão, só ela e o que produziu vão para a tela |
| `GET /api/busca?termo=&tipos=&limite=` | Busca ranqueada sobre o ramo, com a sessão de cada nó e o trecho onde o termo casou |
| `GET /api/ontologia` | Tipos de nó, pares de aresta aceitos e vocabulário de status, lidos da tabela do `SchemaGate` — a tela não mantém cópia |
| `POST /api/nodes` com `contido_em` | Cria o contêiner e a aresta `contem` até o pai no mesmo lote: se o portão recusar a aresta, o nó também não entra |
| `GET /api/memoria` | Os aprendizados e as sessões do ramo para o painel de memória, na mesma leitura do acervo de notas. `POST /api/memoria/aprendizados` e `POST /api/memoria/promocoes` recebem do humano o registro e a promoção, sob a identidade do servidor |

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
  - `DESIGN_DO_SISTEMA` (`CICLO_DEPENDENCIA`, `ESTOURO_ORCAMENTO_TOKENS`, `TIPO_DESCONHECIDO`, `CONFLITO_CONCORRENCIA_LOCK`, `CAMINHO_INVALIDO`, `ESTRUTURA_INCOMPLETA`, `REFERENCIA_INEXISTENTE`, `PAR_DE_ARESTA_INVALIDO`, `NO_FORA_DA_HIERARQUIA`)
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
| **Harness (hooks)** | `IdentidadeHarness`, papel `sistema` | Papéis de agente são recusados na construção. |

A vista materializada carrega essa proveniência em cada linha (`por autor
(papel)`), e conteúdo de `Evidence` ou `Artifact` criado por agente chega ao
modelo marcado como **não confiável** — a defesa mínima contra injeção
persistente.

Junto dela viaja a **ordem**: cada nó carrega a sequência do evento que o criou
(`log #N` nas linhas da vista e no rodapé do card, com a data por extenso em
`expandir_no` e no inspetor). O carimbo de tempo diz a idade; a sequência diz
quem veio antes de quem, e é a única resposta confiável para isso, porque a web
e o MCP escrevem de processos distintos, cada um com o seu relógio. A sequência
fica fora do cabeçalho da vista de propósito: ele é obrigatório em toda leitura,
então tudo que entra ali sai do orçamento de tokens de todo agente.

Cada evento também declara **em qual vocabulário foi escrito**
(`versao_ontologia`, hoje `1.2.0`), gravado no log e devolvido na linha do tempo
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
primeira sessão e reaproveitados nas seguintes. Um `Projeto` que o humano já
criou com o nome do repositório é reaproveitado, e um `Setor` chamado `Memoria`
dentro dele também. É por isso que o papel `sistema` cria `Projeto` e `Setor`:
só o ambiente padrão, e nunca o grafo de trabalho. `--setor <id>` continua
valendo para quem quer a sessão em outro lugar.

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

A fiação pronta está em `.agents/hooks/graphow_harness_hooks.json`, e
`graphow docs-gerar --conferir` passa cada comando desse arquivo pelo analisador
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
| **Médio prazo** | O fechamento da sessão encerrada: decisões vigentes, dúvidas abertas, restrições, último artefato, e a condensação em prosa | O fechamento é projeção do log, recalculada a cada commit no rollup. A prosa é uma `Note` escrita por um agente a partir da `Task` de condensação que o próprio grafo abre quando a sessão encerra | `ler_vista` numa sessão encerrada abre pelo fechamento; o panorama do Setor mostra o fechamento de cada sessão |
| **Longo prazo** | O `Aprendizado`: o que sobrevive ao projeto, com origem obrigatória | `registrar_aprendizado` por qualquer papel; promoção pelo humano com `promover_aprendizado` | Seção **Aprendizados Aplicáveis** na vista de qualquer alvo: por herança pela hierarquia, por casamento lexical e, se injetado, por índice semântico |

Três princípios seguram o desenho. Nada derivado é gravado quando pode ser
projetado: o fechamento é uma dobra do estado, e uma sessão reaberta atualiza
sozinha. Memória diz de onde veio: um `Aprendizado` sem `deriva_de` no mesmo
lote é recusado no portão, como um nó sem aresta de contenção. E memória que
cai primeiro sob pressão de orçamento não é memória: a seção de aprendizados e
o fechamento retêm como `MEMORIA`, e só saem da vista no degrau em que a
navegação também sai.

Esquecer é marcar, nunca apagar: `substitui` entre aprendizados deixa o antigo
visível com `SUBSTITUIDO`, `contradiz` de uma `Evidence` nova o marca com
`CONTRADITO`, `valido_ate` tira o vencido da vista, e remover é do humano. O
índice semântico é opcional e injetável no `MaterializadorContexto`, com padrão
nulo: sem configurar, não custa nada e não traz dependência.

**A memória tem ambiente padrão e tem lugar na tela.** O hook de início não
precisa de um Setor criado à parte: a sessão nasce no `Projeto` com o nome do
repositório, dentro do `Setor` `Memoria`, que o harness cria na primeira vez e
reaproveita depois. E o canvas tem um painel de **Memória** na lateral esquerda:
os aprendizados do ramo com origem, alcance e marcas, promovidos ou não, e as
sessões com o fechamento e o estado da condensação. Registrar e promover ficam
ali, no inspetor e no menu de qualquer nó de trabalho; promover continua gesto
humano, e a tela escreve como humano.

**Os agentes ficam sabendo.** Três canais dizem ao agente o que o grafo
espera dele, sem depender de ninguém lembrar: a vista de retomada que o hook de
início imprime no contexto, as `instructions` do servidor MCP e a skill
`graphow-mcp`, que `graphow skill-instalar` copia para o diretório de skills do
ambiente (`~/.claude/skills` por padrão, `--destino` para outro) e atualiza a
cada execução, no lugar das cópias por projeto que envelhecem.

**O acervo de notas é projeção.** `graphow notas-gerar` renderiza um diretório
de notas em Markdown a partir dos aprendizados promovidos, uma nota por
aprendizado, no formato *afirmação, como se sabe, como aplicar*: a origem é
derivada das arestas `deriva_de`, com o identificador e a posição no log de
cada nó citado, e os links entre notas saem de `substitui` e `contradiz`. O
grafo é a fonte; o acervo é leitura, regenerável do zero, e `--conferir` acusa
qualquer nota escrita à mão. O hook de fim de sessão do ambiente escreve no
grafo pelo harness, e é dali que o motor reativo pede a condensação.

---

## 📊 Métrica Número Um: Tokens por Tarefa Bem-Sucedida

`graphow avaliar` mede essa métrica sobre um
corpus de **dez tarefas gravadas** (`src/graphow/avaliacao/`), comparando o
recorte do grafo com o despejo integral do subgrafo da sessão, e acrescenta os
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
declara os próprios limites: a taxa de patch rejeitado por rodada exige um
agente real e continua fora da medição.

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

O índice de rollup é recalculado **inteiro a cada commit**, dentro de
`ProjecaoSincronizada._registrar` — ponto único, porque o kernel adota a
projeção que ele mesmo dobrou após o commit. Não há manutenção incremental: a
agregação é uma dobra pura do estado, com a mesma garantia de determinismo do
resto da projeção.

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
